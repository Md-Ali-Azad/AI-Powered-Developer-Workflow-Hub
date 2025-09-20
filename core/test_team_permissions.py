"""
Unit tests for team permission system.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404
from unittest.mock import Mock

from .models import Team, Membership, Project
from .services import TeamPermissions, require_team_permission, require_team_membership, check_team_permission, get_user_accessible_teams

User = get_user_model()


class TeamPermissionsTest(TestCase):
    """Test cases for TeamPermissions class."""
    
    def setUp(self):
        """Set up test data."""
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.developer = User.objects.create_user(
            username='developer',
            email='developer@test.com',
            password='testpass123'
        )
        self.viewer = User.objects.create_user(
            username='viewer',
            email='viewer@test.com',
            password='testpass123'
        )
        self.external_user = User.objects.create_user(
            username='external',
            email='external@test.com',
            password='testpass123'
        )
        
        self.team = Team.objects.create(name='Test Team', owner=self.owner)
        
        # Create memberships
        Membership.objects.create(user=self.owner, team=self.team, role='Admin')
        Membership.objects.create(user=self.admin, team=self.team, role='Admin')
        Membership.objects.create(user=self.developer, team=self.team, role='Developer')
        Membership.objects.create(user=self.viewer, team=self.team, role='Viewer')
    
    def test_role_permissions_completeness(self):
        """Test that all roles have defined permissions."""
        expected_roles = ['Admin', 'Developer', 'Viewer']
        
        for role in expected_roles:
            self.assertIn(role, TeamPermissions.ROLE_PERMISSIONS)
            permissions = TeamPermissions.ROLE_PERMISSIONS[role]
            self.assertIsInstance(permissions, list)
            self.assertGreater(len(permissions), 0)
    
    def test_admin_permissions(self):
        """Test Admin role has all expected permissions."""
        admin_perms = TeamPermissions.ROLE_PERMISSIONS['Admin']
        
        expected_permissions = [
            'invite_members',
            'manage_members',
            'manage_projects',
            'view_team',
            'create_projects',
            'delete_projects',
            'manage_team_settings',
            'view_projects',
            'create_tasks',
            'manage_tasks',
            'view_team_dashboard'
        ]
        
        for permission in expected_permissions:
            self.assertIn(permission, admin_perms)
    
    def test_developer_permissions(self):
        """Test Developer role has expected permissions."""
        dev_perms = TeamPermissions.ROLE_PERMISSIONS['Developer']
        
        expected_permissions = [
            'view_team',
            'view_projects',
            'create_tasks',
            'manage_own_tasks',
            'view_team_dashboard'
        ]
        
        for permission in expected_permissions:
            self.assertIn(permission, dev_perms)
        
        # Should not have admin permissions
        admin_only_permissions = [
            'invite_members',
            'manage_members',
            'manage_projects',
            'create_projects',
            'delete_projects'
        ]
        
        for permission in admin_only_permissions:
            self.assertNotIn(permission, dev_perms)
    
    def test_viewer_permissions(self):
        """Test Viewer role has minimal permissions."""
        viewer_perms = TeamPermissions.ROLE_PERMISSIONS['Viewer']
        
        expected_permissions = [
            'view_team',
            'view_projects',
            'view_team_dashboard'
        ]
        
        for permission in expected_permissions:
            self.assertIn(permission, viewer_perms)
        
        # Should not have write permissions
        write_permissions = [
            'create_tasks',
            'manage_tasks',
            'invite_members',
            'manage_members',
            'manage_projects'
        ]
        
        for permission in write_permissions:
            self.assertNotIn(permission, viewer_perms)
    
    def test_has_permission_owner_always_true(self):
        """Test that team owner always has all permissions."""
        test_permissions = [
            'invite_members',
            'manage_members',
            'manage_projects',
            'view_team',
            'create_tasks',
            'delete_projects',
            'manage_team_settings'
        ]
        
        for permission in test_permissions:
            self.assertTrue(
                TeamPermissions.has_permission(self.owner, self.team, permission),
                f"Owner should have {permission} permission"
            )
    
    def test_has_permission_by_role(self):
        """Test permission checking based on user role."""
        # Admin permissions
        self.assertTrue(TeamPermissions.has_permission(self.admin, self.team, 'invite_members'))
        self.assertTrue(TeamPermissions.has_permission(self.admin, self.team, 'manage_members'))
        self.assertTrue(TeamPermissions.has_permission(self.admin, self.team, 'view_team'))
        
        # Developer permissions
        self.assertTrue(TeamPermissions.has_permission(self.developer, self.team, 'view_team'))
        self.assertTrue(TeamPermissions.has_permission(self.developer, self.team, 'create_tasks'))
        self.assertFalse(TeamPermissions.has_permission(self.developer, self.team, 'invite_members'))
        self.assertFalse(TeamPermissions.has_permission(self.developer, self.team, 'manage_members'))
        
        # Viewer permissions
        self.assertTrue(TeamPermissions.has_permission(self.viewer, self.team, 'view_team'))
        self.assertTrue(TeamPermissions.has_permission(self.viewer, self.team, 'view_projects'))
        self.assertFalse(TeamPermissions.has_permission(self.viewer, self.team, 'create_tasks'))
        self.assertFalse(TeamPermissions.has_permission(self.viewer, self.team, 'invite_members'))
        
        # Non-member permissions
        self.assertFalse(TeamPermissions.has_permission(self.external_user, self.team, 'view_team'))
        self.assertFalse(TeamPermissions.has_permission(self.external_user, self.team, 'invite_members'))
    
    def test_get_user_role(self):
        """Test getting user role in team."""
        self.assertEqual(TeamPermissions.get_user_role(self.owner, self.team), 'Admin')
        self.assertEqual(TeamPermissions.get_user_role(self.admin, self.team), 'Admin')
        self.assertEqual(TeamPermissions.get_user_role(self.developer, self.team), 'Developer')
        self.assertEqual(TeamPermissions.get_user_role(self.viewer, self.team), 'Viewer')
        self.assertIsNone(TeamPermissions.get_user_role(self.external_user, self.team))
    
    def test_is_team_member(self):
        """Test team membership checking."""
        self.assertTrue(TeamPermissions.is_team_member(self.owner, self.team))
        self.assertTrue(TeamPermissions.is_team_member(self.admin, self.team))
        self.assertTrue(TeamPermissions.is_team_member(self.developer, self.team))
        self.assertTrue(TeamPermissions.is_team_member(self.viewer, self.team))
        self.assertFalse(TeamPermissions.is_team_member(self.external_user, self.team))
    
    def test_permission_helper_methods(self):
        """Test specific permission helper methods."""
        # can_invite_members
        self.assertTrue(TeamPermissions.can_invite_members(self.owner, self.team))
        self.assertTrue(TeamPermissions.can_invite_members(self.admin, self.team))
        self.assertFalse(TeamPermissions.can_invite_members(self.developer, self.team))
        self.assertFalse(TeamPermissions.can_invite_members(self.viewer, self.team))
        self.assertFalse(TeamPermissions.can_invite_members(self.external_user, self.team))
        
        # can_manage_members
        self.assertTrue(TeamPermissions.can_manage_members(self.owner, self.team))
        self.assertTrue(TeamPermissions.can_manage_members(self.admin, self.team))
        self.assertFalse(TeamPermissions.can_manage_members(self.developer, self.team))
        self.assertFalse(TeamPermissions.can_manage_members(self.viewer, self.team))
        
        # can_manage_projects
        self.assertTrue(TeamPermissions.can_manage_projects(self.owner, self.team))
        self.assertTrue(TeamPermissions.can_manage_projects(self.admin, self.team))
        self.assertFalse(TeamPermissions.can_manage_projects(self.developer, self.team))
        self.assertFalse(TeamPermissions.can_manage_projects(self.viewer, self.team))
        
        # can_view_team
        self.assertTrue(TeamPermissions.can_view_team(self.owner, self.team))
        self.assertTrue(TeamPermissions.can_view_team(self.admin, self.team))
        self.assertTrue(TeamPermissions.can_view_team(self.developer, self.team))
        self.assertTrue(TeamPermissions.can_view_team(self.viewer, self.team))
        self.assertFalse(TeamPermissions.can_view_team(self.external_user, self.team))
        
        # can_create_tasks
        self.assertTrue(TeamPermissions.can_create_tasks(self.owner, self.team))
        self.assertTrue(TeamPermissions.can_create_tasks(self.admin, self.team))
        self.assertTrue(TeamPermissions.can_create_tasks(self.developer, self.team))
        self.assertFalse(TeamPermissions.can_create_tasks(self.viewer, self.team))
        self.assertFalse(TeamPermissions.can_create_tasks(self.external_user, self.team))
    
    def test_filter_user_teams(self):
        """Test filtering user teams with role information."""
        # Create additional team where user is a member
        team2 = Team.objects.create(name='Team 2', owner=self.admin)
        Membership.objects.create(user=self.developer, team=team2, role='Developer')
        
        teams_info = TeamPermissions.filter_user_teams(self.developer)
        
        self.assertEqual(len(teams_info), 2)
        
        # Check team information structure
        for team_info in teams_info:
            self.assertIn('team', team_info)
            self.assertIn('role', team_info)
            self.assertIn('is_owner', team_info)
            self.assertIsInstance(team_info['team'], Team)
            self.assertIn(team_info['role'], ['Admin', 'Developer', 'Viewer'])
            self.assertIsInstance(team_info['is_owner'], bool)
        
        # Check specific team details
        team1_info = next(info for info in teams_info if info['team'] == self.team)
        self.assertEqual(team1_info['role'], 'Developer')
        self.assertFalse(team1_info['is_owner'])
        
        team2_info = next(info for info in teams_info if info['team'] == team2)
        self.assertEqual(team2_info['role'], 'Developer')
        self.assertFalse(team2_info['is_owner'])
    
    def test_filter_user_teams_owner(self):
        """Test filtering teams for team owner."""
        teams_info = TeamPermissions.filter_user_teams(self.owner)
        
        self.assertEqual(len(teams_info), 1)
        self.assertEqual(teams_info[0]['team'], self.team)
        self.assertEqual(teams_info[0]['role'], 'Admin')
        self.assertTrue(teams_info[0]['is_owner'])
    
    def test_filter_user_teams_no_duplicates(self):
        """Test that owned teams don't appear twice in filter results."""
        # Owner should only appear once even though they have membership
        teams_info = TeamPermissions.filter_user_teams(self.owner)
        
        team_ids = [info['team'].id for info in teams_info]
        self.assertEqual(len(team_ids), len(set(team_ids)))  # No duplicates
    
    def test_filter_team_projects(self):
        """Test filtering team projects based on permissions."""
        # Create projects
        project1 = Project.objects.create(team=self.team, name='Project 1', description='Test')
        project2 = Project.objects.create(team=self.team, name='Project 2', description='Test')
        
        # Team members should see all projects
        member_projects = TeamPermissions.filter_team_projects(self.developer, self.team)
        self.assertEqual(member_projects.count(), 2)
        self.assertIn(project1, member_projects)
        self.assertIn(project2, member_projects)
        
        # Non-members should see no projects
        external_projects = TeamPermissions.filter_team_projects(self.external_user, self.team)
        self.assertEqual(external_projects.count(), 0)
    
    def test_get_permission_error_message_non_member(self):
        """Test permission error message for non-members."""
        error_msg = TeamPermissions.get_permission_error_message(
            self.external_user, self.team, 'invite_members'
        )
        
        self.assertIn('must be a member', error_msg)
        self.assertIn(self.team.name, error_msg)
    
    def test_get_permission_error_message_insufficient_role(self):
        """Test permission error message for insufficient role."""
        error_msg = TeamPermissions.get_permission_error_message(
            self.developer, self.team, 'invite_members'
        )
        
        self.assertIn('Only team admins can invite', error_msg)
        self.assertIn('Developer', error_msg)
    
    def test_get_permission_error_message_generic(self):
        """Test generic permission error message."""
        error_msg = TeamPermissions.get_permission_error_message(
            self.viewer, self.team, 'unknown_permission'
        )
        
        self.assertIn("don't have permission", error_msg)
        self.assertIn('Viewer', error_msg)


class PermissionDecoratorsTest(TestCase):
    """Test cases for permission decorators."""
    
    def setUp(self):
        """Set up test data."""
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.developer = User.objects.create_user(
            username='developer',
            email='developer@test.com',
            password='testpass123'
        )
        self.external_user = User.objects.create_user(
            username='external',
            email='external@test.com',
            password='testpass123'
        )
        
        self.team = Team.objects.create(name='Test Team', owner=self.owner)
        Membership.objects.create(user=self.owner, team=self.team, role='Admin')
        Membership.objects.create(user=self.developer, team=self.team, role='Developer')
    
    def test_require_team_permission_decorator_success(self):
        """Test require_team_permission decorator with sufficient permissions."""
        @require_team_permission('invite_members')
        def test_view(request, team_id):
            return f"Success for team {team_id}"
        
        # Mock request
        request = Mock()
        request.user = self.owner
        
        result = test_view(request, team_id=self.team.id)
        self.assertEqual(result, f"Success for team {self.team.id}")
    
    def test_require_team_permission_decorator_failure(self):
        """Test require_team_permission decorator with insufficient permissions."""
        @require_team_permission('invite_members')
        def test_view(request, team_id):
            return f"Success for team {team_id}"
        
        # Mock request with user lacking permission
        request = Mock()
        request.user = self.developer
        
        with self.assertRaises(PermissionDenied):
            test_view(request, team_id=self.team.id)
    
    def test_require_team_permission_decorator_nonexistent_team(self):
        """Test require_team_permission decorator with nonexistent team."""
        @require_team_permission('view_team')
        def test_view(request, team_id):
            return f"Success for team {team_id}"
        
        request = Mock()
        request.user = self.owner
        
        with self.assertRaises(Http404):
            test_view(request, team_id=99999)
    
    def test_require_team_membership_decorator_success(self):
        """Test require_team_membership decorator with team member."""
        @require_team_membership
        def test_view(request, team_id):
            return f"Success for team {team_id}"
        
        request = Mock()
        request.user = self.developer
        
        result = test_view(request, team_id=self.team.id)
        self.assertEqual(result, f"Success for team {self.team.id}")
    
    def test_require_team_membership_decorator_failure(self):
        """Test require_team_membership decorator with non-member."""
        @require_team_membership
        def test_view(request, team_id):
            return f"Success for team {team_id}"
        
        request = Mock()
        request.user = self.external_user
        
        with self.assertRaises(PermissionDenied):
            test_view(request, team_id=self.team.id)
    
    def test_decorator_adds_team_to_kwargs(self):
        """Test that decorators add team object to kwargs."""
        @require_team_membership
        def test_view(request, team_id, team=None):
            return team
        
        request = Mock()
        request.user = self.developer
        
        result = test_view(request, team_id=self.team.id)
        self.assertEqual(result, self.team)


class PermissionHelperFunctionsTest(TestCase):
    """Test cases for permission helper functions."""
    
    def setUp(self):
        """Set up test data."""
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.developer = User.objects.create_user(
            username='developer',
            email='developer@test.com',
            password='testpass123'
        )
        self.external_user = User.objects.create_user(
            username='external',
            email='external@test.com',
            password='testpass123'
        )
        
        self.team = Team.objects.create(name='Test Team', owner=self.owner)
        Membership.objects.create(user=self.owner, team=self.team, role='Admin')
        Membership.objects.create(user=self.developer, team=self.team, role='Developer')
    
    def test_check_team_permission_with_exception(self):
        """Test check_team_permission with exception raising."""
        # Should not raise for valid permission
        result = check_team_permission(
            self.owner, self.team, 'invite_members', raise_exception=True
        )
        self.assertTrue(result)
        
        # Should raise for invalid permission
        with self.assertRaises(PermissionDenied):
            check_team_permission(
                self.developer, self.team, 'invite_members', raise_exception=True
            )
    
    def test_check_team_permission_without_exception(self):
        """Test check_team_permission without exception raising."""
        # Should return True for valid permission
        result = check_team_permission(
            self.owner, self.team, 'invite_members', raise_exception=False
        )
        self.assertTrue(result)
        
        # Should return False for invalid permission
        result = check_team_permission(
            self.developer, self.team, 'invite_members', raise_exception=False
        )
        self.assertFalse(result)
    
    def test_get_user_accessible_teams(self):
        """Test get_user_accessible_teams function."""
        # Create additional team
        team2 = Team.objects.create(name='Team 2', owner=self.developer)
        Membership.objects.create(user=self.developer, team=team2, role='Admin')
        
        teams_info = get_user_accessible_teams(self.developer)
        
        self.assertEqual(len(teams_info), 2)
        
        # Check structure of returned data
        for team_info in teams_info:
            required_keys = [
                'team', 'role', 'is_owner', 'permissions',
                'can_invite', 'can_manage_members', 'can_manage_projects'
            ]
            for key in required_keys:
                self.assertIn(key, team_info)
        
        # Check specific team permissions
        team1_info = next(info for info in teams_info if info['team'] == self.team)
        self.assertEqual(team1_info['role'], 'Developer')
        self.assertFalse(team1_info['can_invite'])
        self.assertFalse(team1_info['can_manage_members'])
        self.assertFalse(team1_info['can_manage_projects'])
        
        team2_info = next(info for info in teams_info if info['team'] == team2)
        self.assertEqual(team2_info['role'], 'Admin')
        self.assertTrue(team2_info['can_invite'])
        self.assertTrue(team2_info['can_manage_members'])
        self.assertTrue(team2_info['can_manage_projects'])
    
    def test_get_user_accessible_teams_no_teams(self):
        """Test get_user_accessible_teams for user with no teams."""
        teams_info = get_user_accessible_teams(self.external_user)
        self.assertEqual(len(teams_info), 0)


class PermissionEdgeCasesTest(TestCase):
    """Test edge cases in permission system."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.team = Team.objects.create(name='Test Team', owner=self.user)
    
    def test_permission_with_deleted_membership(self):
        """Test permission checking after membership is deleted."""
        # Create and then delete membership
        membership = Membership.objects.create(user=self.user, team=self.team, role='Admin')
        membership.delete()
        
        # Owner should still have permissions
        self.assertTrue(TeamPermissions.has_permission(self.user, self.team, 'invite_members'))
    
    def test_permission_with_invalid_role(self):
        """Test permission checking with invalid role in database."""
        # This shouldn't happen in normal operation, but test defensive coding
        membership = Membership.objects.create(user=self.user, team=self.team, role='Admin')
        
        # Manually set invalid role (bypassing model validation)
        Membership.objects.filter(id=membership.id).update(role='InvalidRole')
        
        # Should handle gracefully (owner permissions should still work)
        self.assertTrue(TeamPermissions.has_permission(self.user, self.team, 'invite_members'))
    
    def test_permission_with_nonexistent_permission(self):
        """Test checking for nonexistent permission."""
        result = TeamPermissions.has_permission(self.user, self.team, 'nonexistent_permission')
        self.assertFalse(result)  # Should return False for unknown permissions