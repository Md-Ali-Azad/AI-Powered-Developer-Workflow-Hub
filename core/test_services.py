"""
Tests for team management services.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
import uuid

from .models import Team, Membership, TeamInvitation, Notification
from .services import InvitationService, TeamService

User = get_user_model()


class InvitationServiceTest(TestCase):
    """Test cases for InvitationService."""
    
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
        self.member = User.objects.create_user(
            username='member',
            email='member@test.com',
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
        Membership.objects.create(user=self.member, team=self.team, role='Developer')
    
    def test_send_invitation_success(self):
        """Test successful invitation sending."""
        invitation = InvitationService.send_invitation(
            team=self.team,
            inviter=self.owner,
            email='newuser@test.com',
            role='Developer'
        )
        
        self.assertIsNotNone(invitation)
        self.assertEqual(invitation.team, self.team)
        self.assertEqual(invitation.invited_by, self.owner)
        self.assertEqual(invitation.email, 'newuser@test.com')
        self.assertEqual(invitation.role, 'Developer')
        self.assertEqual(invitation.status, 'pending')
        self.assertIsNotNone(invitation.token)
        
        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Test Team', mail.outbox[0].subject)
        self.assertIn('newuser@test.com', mail.outbox[0].to)
    
    def test_send_invitation_to_existing_user(self):
        """Test sending invitation to existing user creates notification."""
        invitation = InvitationService.send_invitation(
            team=self.team,
            inviter=self.owner,
            email=self.external_user.email,
            role='Developer'
        )
        
        self.assertIsNotNone(invitation)
        self.assertEqual(invitation.invited_user, self.external_user)
        
        # Check notification was created
        notification = Notification.objects.filter(
            user=self.external_user,
            type='team_invitation'
        ).first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.payload['team_name'], 'Test Team')
    
    def test_send_invitation_permission_denied(self):
        """Test invitation sending with insufficient permissions."""
        with self.assertRaises(PermissionError):
            InvitationService.send_invitation(
                team=self.team,
                inviter=self.member,  # Member cannot invite
                email='newuser@test.com'
            )
    
    def test_send_invitation_duplicate_pending(self):
        """Test sending duplicate invitation fails."""
        # Send first invitation
        InvitationService.send_invitation(
            team=self.team,
            inviter=self.owner,
            email='newuser@test.com'
        )
        
        # Try to send duplicate
        with self.assertRaises(ValueError) as cm:
            InvitationService.send_invitation(
                team=self.team,
                inviter=self.owner,
                email='newuser@test.com'
            )
        
        self.assertIn('Pending invitation already exists', str(cm.exception))
    
    def test_send_invitation_existing_member(self):
        """Test sending invitation to existing team member fails."""
        with self.assertRaises(ValueError) as cm:
            InvitationService.send_invitation(
                team=self.team,
                inviter=self.owner,
                email=self.member.email
            )
        
        self.assertIn('already a member', str(cm.exception))
    
    def test_accept_invitation_success(self):
        """Test successful invitation acceptance."""
        invitation = InvitationService.send_invitation(
            team=self.team,
            inviter=self.owner,
            email=self.external_user.email
        )
        
        membership = InvitationService.accept_invitation(
            invitation_token=invitation.token,
            user=self.external_user
        )
        
        self.assertIsNotNone(membership)
        self.assertEqual(membership.user, self.external_user)
        self.assertEqual(membership.team, self.team)
        self.assertEqual(membership.role, invitation.role)
        
        # Check invitation status updated
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, 'accepted')
        
        # Check notifications created
        acceptance_notification = Notification.objects.filter(
            user=self.owner,
            type='invitation_accepted'
        ).first()
        self.assertIsNotNone(acceptance_notification)
    
    def test_accept_invitation_invalid_token(self):
        """Test accepting invitation with invalid token."""
        with self.assertRaises(ValueError) as cm:
            InvitationService.accept_invitation(
                invitation_token=uuid.uuid4(),
                user=self.external_user
            )
        
        self.assertIn('Invalid or expired invitation', str(cm.exception))
    
    def test_accept_invitation_expired(self):
        """Test accepting expired invitation."""
        invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            invited_user=self.external_user,
            email=self.external_user.email,
            expires_at=timezone.now() - timedelta(days=1)  # Expired
        )
        
        with self.assertRaises(ValueError) as cm:
            InvitationService.accept_invitation(
                invitation_token=invitation.token,
                user=self.external_user
            )
        
        self.assertIn('expired', str(cm.exception))
    
    def test_accept_invitation_email_mismatch(self):
        """Test accepting invitation with wrong user email."""
        invitation = InvitationService.send_invitation(
            team=self.team,
            inviter=self.owner,
            email='different@test.com'
        )
        
        with self.assertRaises(ValueError) as cm:
            InvitationService.accept_invitation(
                invitation_token=invitation.token,
                user=self.external_user  # Different email
            )
        
        self.assertIn('does not match', str(cm.exception))
    
    def test_decline_invitation_success(self):
        """Test successful invitation decline."""
        invitation = InvitationService.send_invitation(
            team=self.team,
            inviter=self.owner,
            email=self.external_user.email
        )
        
        result = InvitationService.decline_invitation(
            invitation_token=invitation.token,
            user=self.external_user
        )
        
        self.assertTrue(result)
        
        # Check invitation status updated
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, 'declined')
        
        # Check notification created for inviter
        decline_notification = Notification.objects.filter(
            user=self.owner,
            type='invitation_declined'
        ).first()
        self.assertIsNotNone(decline_notification)
    
    def test_get_pending_invitations(self):
        """Test getting pending invitations for user."""
        # Create invitations
        invitation1 = InvitationService.send_invitation(
            team=self.team,
            inviter=self.owner,
            email=self.external_user.email
        )
        
        # Create another team and invitation
        team2 = Team.objects.create(name='Team 2', owner=self.owner)
        Membership.objects.create(user=self.owner, team=team2, role='Admin')
        invitation2 = InvitationService.send_invitation(
            team=team2,
            inviter=self.owner,
            email=self.external_user.email
        )
        
        pending = InvitationService.get_pending_invitations(self.external_user)
        
        self.assertEqual(pending.count(), 2)
        self.assertIn(invitation1, pending)
        self.assertIn(invitation2, pending)
    
    def test_get_sent_invitations(self):
        """Test getting invitations sent by user."""
        invitation1 = InvitationService.send_invitation(
            team=self.team,
            inviter=self.owner,
            email='user1@test.com'
        )
        invitation2 = InvitationService.send_invitation(
            team=self.team,
            inviter=self.owner,
            email='user2@test.com'
        )
        
        sent = InvitationService.get_sent_invitations(self.owner)
        
        self.assertEqual(sent.count(), 2)
        self.assertIn(invitation1, sent)
        self.assertIn(invitation2, sent)
    
    def test_cleanup_expired_invitations(self):
        """Test cleanup of expired invitations."""
        # Create expired invitation
        expired_invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='expired@test.com',
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        # Create valid invitation
        valid_invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='valid@test.com',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        count = InvitationService.cleanup_expired_invitations()
        
        self.assertEqual(count, 1)
        
        expired_invitation.refresh_from_db()
        valid_invitation.refresh_from_db()
        
        self.assertEqual(expired_invitation.status, 'expired')
        self.assertEqual(valid_invitation.status, 'pending')
    
    def test_can_invite_members_owner(self):
        """Test team owner can invite members."""
        from .services import TeamPermissions
        can_invite = TeamPermissions.can_invite_members(self.owner, self.team)
        self.assertTrue(can_invite)
    
    def test_can_invite_members_admin(self):
        """Test admin member can invite members."""
        from .services import TeamPermissions
        can_invite = TeamPermissions.can_invite_members(self.admin, self.team)
        self.assertTrue(can_invite)
    
    def test_can_invite_members_regular_member(self):
        """Test regular member cannot invite members."""
        from .services import TeamPermissions
        can_invite = TeamPermissions.can_invite_members(self.member, self.team)
        self.assertFalse(can_invite)
    
    def test_can_invite_members_non_member(self):
        """Test non-member cannot invite members."""
        from .services import TeamPermissions
        can_invite = TeamPermissions.can_invite_members(self.external_user, self.team)
        self.assertFalse(can_invite)


class TeamServiceTest(TestCase):
    """Test cases for TeamService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
    
    def test_create_team(self):
        """Test team creation with owner membership."""
        team = TeamService.create_team(self.user, 'New Team')
        
        self.assertIsNotNone(team)
        self.assertEqual(team.name, 'New Team')
        self.assertEqual(team.owner, self.user)
        
        # Check owner membership created
        membership = Membership.objects.filter(user=self.user, team=team).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, 'Admin')
    
    def test_get_user_teams(self):
        """Test getting teams for a user."""
        team1 = TeamService.create_team(self.user, 'Team 1')
        team2 = Team.objects.create(name='Team 2', owner=self.user)
        Membership.objects.create(user=self.user, team=team2, role='Developer')
        
        # Create team user is not member of
        Team.objects.create(name='Other Team', owner=User.objects.create_user('other', 'other@test.com'))
        
        user_teams = TeamService.get_user_teams(self.user)
        
        self.assertEqual(user_teams.count(), 2)
        self.assertIn(team1, user_teams)
        self.assertIn(team2, user_teams)
    
    def test_can_invite_members(self):
        """Test permission checking through TeamService."""
        team = TeamService.create_team(self.user, 'Test Team')
        
        can_invite = TeamService.can_invite_members(self.user, team)
        self.assertTrue(can_invite)


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
    
    def test_role_permissions_definition(self):
        """Test that role permissions are properly defined."""
        from .services import TeamPermissions
        
        # Check Admin permissions
        admin_perms = TeamPermissions.ROLE_PERMISSIONS['Admin']
        self.assertIn('invite_members', admin_perms)
        self.assertIn('manage_members', admin_perms)
        self.assertIn('manage_projects', admin_perms)
        self.assertIn('view_team', admin_perms)
        
        # Check Developer permissions
        dev_perms = TeamPermissions.ROLE_PERMISSIONS['Developer']
        self.assertIn('view_team', dev_perms)
        self.assertIn('create_tasks', dev_perms)
        self.assertNotIn('invite_members', dev_perms)
        self.assertNotIn('manage_members', dev_perms)
        
        # Check Viewer permissions
        viewer_perms = TeamPermissions.ROLE_PERMISSIONS['Viewer']
        self.assertIn('view_team', viewer_perms)
        self.assertIn('view_projects', viewer_perms)
        self.assertNotIn('create_tasks', viewer_perms)
        self.assertNotIn('invite_members', viewer_perms)
    
    def test_has_permission_owner(self):
        """Test that team owner has all permissions."""
        from .services import TeamPermissions
        
        # Owner should have all permissions regardless of membership role
        self.assertTrue(TeamPermissions.has_permission(self.owner, self.team, 'invite_members'))
        self.assertTrue(TeamPermissions.has_permission(self.owner, self.team, 'manage_members'))
        self.assertTrue(TeamPermissions.has_permission(self.owner, self.team, 'manage_projects'))
        self.assertTrue(TeamPermissions.has_permission(self.owner, self.team, 'view_team'))
    
    def test_has_permission_admin(self):
        """Test admin permissions."""
        from .services import TeamPermissions
        
        self.assertTrue(TeamPermissions.has_permission(self.admin, self.team, 'invite_members'))
        self.assertTrue(TeamPermissions.has_permission(self.admin, self.team, 'manage_members'))
        self.assertTrue(TeamPermissions.has_permission(self.admin, self.team, 'manage_projects'))
        self.assertTrue(TeamPermissions.has_permission(self.admin, self.team, 'view_team'))
        self.assertTrue(TeamPermissions.has_permission(self.admin, self.team, 'create_tasks'))
    
    def test_has_permission_developer(self):
        """Test developer permissions."""
        from .services import TeamPermissions
        
        self.assertTrue(TeamPermissions.has_permission(self.developer, self.team, 'view_team'))
        self.assertTrue(TeamPermissions.has_permission(self.developer, self.team, 'create_tasks'))
        self.assertTrue(TeamPermissions.has_permission(self.developer, self.team, 'view_projects'))
        
        # Should not have admin permissions
        self.assertFalse(TeamPermissions.has_permission(self.developer, self.team, 'invite_members'))
        self.assertFalse(TeamPermissions.has_permission(self.developer, self.team, 'manage_members'))
        self.assertFalse(TeamPermissions.has_permission(self.developer, self.team, 'manage_projects'))
    
    def test_has_permission_viewer(self):
        """Test viewer permissions."""
        from .services import TeamPermissions
        
        self.assertTrue(TeamPermissions.has_permission(self.viewer, self.team, 'view_team'))
        self.assertTrue(TeamPermissions.has_permission(self.viewer, self.team, 'view_projects'))
        
        # Should not have write permissions
        self.assertFalse(TeamPermissions.has_permission(self.viewer, self.team, 'create_tasks'))
        self.assertFalse(TeamPermissions.has_permission(self.viewer, self.team, 'invite_members'))
        self.assertFalse(TeamPermissions.has_permission(self.viewer, self.team, 'manage_members'))
        self.assertFalse(TeamPermissions.has_permission(self.viewer, self.team, 'manage_projects'))
    
    def test_has_permission_non_member(self):
        """Test that non-members have no permissions."""
        from .services import TeamPermissions
        
        self.assertFalse(TeamPermissions.has_permission(self.external_user, self.team, 'view_team'))
        self.assertFalse(TeamPermissions.has_permission(self.external_user, self.team, 'invite_members'))
        self.assertFalse(TeamPermissions.has_permission(self.external_user, self.team, 'manage_members'))
    
    def test_get_user_role(self):
        """Test getting user role in team."""
        from .services import TeamPermissions
        
        self.assertEqual(TeamPermissions.get_user_role(self.owner, self.team), 'Admin')
        self.assertEqual(TeamPermissions.get_user_role(self.admin, self.team), 'Admin')
        self.assertEqual(TeamPermissions.get_user_role(self.developer, self.team), 'Developer')
        self.assertEqual(TeamPermissions.get_user_role(self.viewer, self.team), 'Viewer')
        self.assertIsNone(TeamPermissions.get_user_role(self.external_user, self.team))
    
    def test_is_team_member(self):
        """Test team membership checking."""
        from .services import TeamPermissions
        
        self.assertTrue(TeamPermissions.is_team_member(self.owner, self.team))
        self.assertTrue(TeamPermissions.is_team_member(self.admin, self.team))
        self.assertTrue(TeamPermissions.is_team_member(self.developer, self.team))
        self.assertTrue(TeamPermissions.is_team_member(self.viewer, self.team))
        self.assertFalse(TeamPermissions.is_team_member(self.external_user, self.team))
    
    def test_can_invite_members(self):
        """Test invite members permission check."""
        from .services import TeamPermissions
        
        self.assertTrue(TeamPermissions.can_invite_members(self.owner, self.team))
        self.assertTrue(TeamPermissions.can_invite_members(self.admin, self.team))
        self.assertFalse(TeamPermissions.can_invite_members(self.developer, self.team))
        self.assertFalse(TeamPermissions.can_invite_members(self.viewer, self.team))
        self.assertFalse(TeamPermissions.can_invite_members(self.external_user, self.team))
    
    def test_can_manage_members(self):
        """Test manage members permission check."""
        from .services import TeamPermissions
        
        self.assertTrue(TeamPermissions.can_manage_members(self.owner, self.team))
        self.assertTrue(TeamPermissions.can_manage_members(self.admin, self.team))
        self.assertFalse(TeamPermissions.can_manage_members(self.developer, self.team))
        self.assertFalse(TeamPermissions.can_manage_members(self.viewer, self.team))
        self.assertFalse(TeamPermissions.can_manage_members(self.external_user, self.team))
    
    def test_can_manage_projects(self):
        """Test manage projects permission check."""
        from .services import TeamPermissions
        
        self.assertTrue(TeamPermissions.can_manage_projects(self.owner, self.team))
        self.assertTrue(TeamPermissions.can_manage_projects(self.admin, self.team))
        self.assertFalse(TeamPermissions.can_manage_projects(self.developer, self.team))
        self.assertFalse(TeamPermissions.can_manage_projects(self.viewer, self.team))
        self.assertFalse(TeamPermissions.can_manage_projects(self.external_user, self.team))
    
    def test_can_view_team(self):
        """Test view team permission check."""
        from .services import TeamPermissions
        
        self.assertTrue(TeamPermissions.can_view_team(self.owner, self.team))
        self.assertTrue(TeamPermissions.can_view_team(self.admin, self.team))
        self.assertTrue(TeamPermissions.can_view_team(self.developer, self.team))
        self.assertTrue(TeamPermissions.can_view_team(self.viewer, self.team))
        self.assertFalse(TeamPermissions.can_view_team(self.external_user, self.team))
    
    def test_can_create_tasks(self):
        """Test create tasks permission check."""
        from .services import TeamPermissions
        
        self.assertTrue(TeamPermissions.can_create_tasks(self.owner, self.team))
        self.assertTrue(TeamPermissions.can_create_tasks(self.admin, self.team))
        self.assertTrue(TeamPermissions.can_create_tasks(self.developer, self.team))
        self.assertFalse(TeamPermissions.can_create_tasks(self.viewer, self.team))
        self.assertFalse(TeamPermissions.can_create_tasks(self.external_user, self.team))
    
    def test_filter_user_teams(self):
        """Test filtering user teams with roles."""
        from .services import TeamPermissions
        
        # Create another team where user is a member
        team2 = Team.objects.create(name='Team 2', owner=self.admin)
        Membership.objects.create(user=self.developer, team=team2, role='Developer')
        
        teams_info = TeamPermissions.filter_user_teams(self.developer)
        
        self.assertEqual(len(teams_info), 2)
        
        # Check first team (original team)
        team1_info = next(info for info in teams_info if info['team'] == self.team)
        self.assertEqual(team1_info['role'], 'Developer')
        self.assertFalse(team1_info['is_owner'])
        
        # Check second team
        team2_info = next(info for info in teams_info if info['team'] == team2)
        self.assertEqual(team2_info['role'], 'Developer')
        self.assertFalse(team2_info['is_owner'])
    
    def test_filter_user_teams_owner(self):
        """Test filtering teams for team owner."""
        from .services import TeamPermissions
        
        teams_info = TeamPermissions.filter_user_teams(self.owner)
        
        self.assertEqual(len(teams_info), 1)
        self.assertEqual(teams_info[0]['team'], self.team)
        self.assertEqual(teams_info[0]['role'], 'Admin')
        self.assertTrue(teams_info[0]['is_owner'])
    
    def test_filter_team_projects(self):
        """Test filtering team projects based on permissions."""
        from .services import TeamPermissions
        from .models import Project
        
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
    
    def test_get_permission_error_message(self):
        """Test permission error message generation."""
        from .services import TeamPermissions
        
        # Test non-member error
        error_msg = TeamPermissions.get_permission_error_message(
            self.external_user, self.team, 'invite_members'
        )
        self.assertIn('must be a member', error_msg)
        self.assertIn(self.team.name, error_msg)
        
        # Test insufficient role error
        error_msg = TeamPermissions.get_permission_error_message(
            self.developer, self.team, 'invite_members'
        )
        self.assertIn('Only team admins can invite', error_msg)
        self.assertIn('Developer', error_msg)
        
        # Test generic permission error
        error_msg = TeamPermissions.get_permission_error_message(
            self.viewer, self.team, 'unknown_permission'
        )
        self.assertIn("don't have permission", error_msg)
        self.assertIn('Viewer', error_msg)


class TeamDashboardTest(TestCase):
    """Test cases for team dashboard functionality."""
    
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
        
        # Create projects
        from .models import Project, PullRequest
        self.project1 = Project.objects.create(
            team=self.team,
            name='Project 1',
            description='Test project 1'
        )
        self.project2 = Project.objects.create(
            team=self.team,
            name='Project 2',
            description='Test project 2'
        )
        
        # Create pull requests
        self.pr1 = PullRequest.objects.create(
            project=self.project1,
            number=1,
            title='Test PR 1',
            description='Test description',
            author='testuser',
            diff_url='http://example.com/diff1'
        )
        self.pr2 = PullRequest.objects.create(
            project=self.project2,
            number=2,
            title='Test PR 2',
            description='Test description',
            author='testuser',
            diff_url='http://example.com/diff2'
        )
        
        # Create invitations
        self.invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='newuser@test.com',
            role='Developer'
        )
    
    def test_team_dashboard_access_owner(self):
        """Test team dashboard access for team owner."""
        self.client.force_login(self.owner)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.team.name)
        self.assertContains(response, 'Team Dashboard')
        
        # Check context data
        self.assertEqual(response.context['team'], self.team)
        self.assertIn('team_members', response.context)
        self.assertIn('team_projects', response.context)
        self.assertIn('recent_prs', response.context)
        self.assertIn('stats', response.context)
        self.assertIn('user_permissions', response.context)
    
    def test_team_dashboard_access_admin(self):
        """Test team dashboard access for admin member."""
        self.client.force_login(self.admin)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.team.name)
        
        # Admin should see invite button
        self.assertContains(response, 'Invite Members')
    
    def test_team_dashboard_access_developer(self):
        """Test team dashboard access for developer member."""
        self.client.force_login(self.developer)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.team.name)
        
        # Developer should not see invite button
        self.assertNotContains(response, 'Invite Members')
    
    def test_team_dashboard_access_viewer(self):
        """Test team dashboard access for viewer member."""
        self.client.force_login(self.viewer)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.team.name)
        
        # Viewer should not see invite button
        self.assertNotContains(response, 'Invite Members')
    
    def test_team_dashboard_access_denied_non_member(self):
        """Test team dashboard access denied for non-members."""
        self.client.force_login(self.external_user)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        # Should redirect to dashboard with error message
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/')
    
    def test_team_dashboard_members_display(self):
        """Test team members are displayed correctly."""
        self.client.force_login(self.owner)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        # Check all team members are displayed
        self.assertContains(response, self.owner.username)
        self.assertContains(response, self.admin.username)
        self.assertContains(response, self.developer.username)
        self.assertContains(response, self.viewer.username)
        
        # Check roles are displayed
        self.assertContains(response, 'Admin')
        self.assertContains(response, 'Developer')
        self.assertContains(response, 'Viewer')
        
        # Check owner indicator
        self.assertContains(response, 'Owner')
    
    def test_team_dashboard_projects_display(self):
        """Test team projects are displayed correctly."""
        self.client.force_login(self.owner)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        # Check projects are displayed
        self.assertContains(response, self.project1.name)
        self.assertContains(response, self.project2.name)
        self.assertContains(response, self.project1.description)
        self.assertContains(response, self.project2.description)
    
    def test_team_dashboard_pull_requests_display(self):
        """Test recent pull requests are displayed correctly."""
        self.client.force_login(self.owner)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        # Check PRs are displayed
        self.assertContains(response, self.pr1.title)
        self.assertContains(response, self.pr2.title)
        self.assertContains(response, f'#{self.pr1.number}')
        self.assertContains(response, f'#{self.pr2.number}')
    
    def test_team_dashboard_stats_display(self):
        """Test team stats are calculated and displayed correctly."""
        self.client.force_login(self.owner)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        stats = response.context['stats']
        
        # Check stats values
        self.assertEqual(stats['total_members'], 4)  # owner, admin, developer, viewer
        self.assertEqual(stats['total_projects'], 2)
        self.assertEqual(stats['total_prs'], 2)
        self.assertEqual(stats['pending_invitations'], 1)
        
        # Check stats are displayed in template
        self.assertContains(response, '4')  # members count
        self.assertContains(response, '2')  # projects count
    
    def test_team_dashboard_invitations_display_admin_only(self):
        """Test pending invitations are only shown to admins."""
        # Admin should see invitations section with card header
        self.client.force_login(self.admin)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        # Should contain the full invitation card header (not just stats)
        self.assertContains(response, '<i class="fas fa-clock"></i> Pending Invitations')
        self.assertContains(response, self.invitation.email)
        
        # Developer should not see invitations section
        self.client.force_login(self.developer)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        # Check that the invitations card is not present (but stats might show "Pending Invites")
        self.assertNotContains(response, self.invitation.email)
        self.assertNotContains(response, '<i class="fas fa-clock"></i> Pending Invitations')
    
    def test_team_dashboard_user_permissions_context(self):
        """Test user permissions are correctly set in context."""
        # Test admin permissions
        self.client.force_login(self.admin)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        permissions = response.context['user_permissions']
        self.assertTrue(permissions['can_invite_members'])
        self.assertTrue(permissions['can_manage_members'])
        self.assertTrue(permissions['can_manage_projects'])
        self.assertEqual(permissions['user_role'], 'Admin')
        self.assertFalse(permissions['is_owner'])
        
        # Test developer permissions
        self.client.force_login(self.developer)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        permissions = response.context['user_permissions']
        self.assertFalse(permissions['can_invite_members'])
        self.assertFalse(permissions['can_manage_members'])
        self.assertFalse(permissions['can_manage_projects'])
        self.assertEqual(permissions['user_role'], 'Developer')
        self.assertFalse(permissions['is_owner'])
        
        # Test owner permissions
        self.client.force_login(self.owner)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        permissions = response.context['user_permissions']
        self.assertTrue(permissions['can_invite_members'])
        self.assertTrue(permissions['can_manage_members'])
        self.assertTrue(permissions['can_manage_projects'])
        self.assertEqual(permissions['user_role'], 'Admin')
        self.assertTrue(permissions['is_owner'])
    
    def test_team_dashboard_role_based_content_filtering(self):
        """Test that content is filtered based on user role."""
        # Create a project with sensitive information (admin only)
        from .models import Project
        sensitive_project = Project.objects.create(
            team=self.team,
            name='Sensitive Project',
            description='Admin only project'
        )
        
        # Admin should see all projects
        self.client.force_login(self.admin)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        self.assertContains(response, 'Sensitive Project')
        
        # All team members should see team projects (no filtering by role for projects)
        self.client.force_login(self.developer)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        self.assertContains(response, 'Sensitive Project')
        
        # Viewer should also see projects (read-only access)
        self.client.force_login(self.viewer)
        response = self.client.get(f'/teams/{self.team.id}/')
        
        self.assertContains(response, 'Sensitive Project')
    
    def test_team_dashboard_empty_states(self):
        """Test dashboard displays appropriate messages for empty states."""
        # Create team with no projects
        empty_team = Team.objects.create(name='Empty Team', owner=self.owner)
        Membership.objects.create(user=self.owner, team=empty_team, role='Admin')
        
        self.client.force_login(self.owner)
        response = self.client.get(f'/teams/{empty_team.id}/')
        
        # Should show empty state for projects
        self.assertContains(response, 'No projects yet')
        self.assertContains(response, 'Create your first team project')
        
        # Should show empty state for PRs
        self.assertContains(response, 'No recent pull requests')


class TeamPermissionHelpersTest(TestCase):
    """Test cases for team permission helper functions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.team = Team.objects.create(name='Test Team', owner=self.user)
        Membership.objects.create(user=self.user, team=self.team, role='Admin')
    
    def test_check_team_permission_success(self):
        """Test successful permission check."""
        from .services import check_team_permission
        
        result = check_team_permission(
            self.user, self.team, 'invite_members', raise_exception=False
        )
        self.assertTrue(result)
    
    def test_check_team_permission_failure_no_exception(self):
        """Test failed permission check without exception."""
        from .services import check_team_permission
        
        external_user = User.objects.create_user('external', 'external@test.com')
        
        result = check_team_permission(
            external_user, self.team, 'invite_members', raise_exception=False
        )
        self.assertFalse(result)
    
    def test_check_team_permission_failure_with_exception(self):
        """Test failed permission check with exception."""
        from django.core.exceptions import PermissionDenied
        from .services import check_team_permission
        
        external_user = User.objects.create_user('external', 'external@test.com')
        
        with self.assertRaises(PermissionDenied):
            check_team_permission(
                external_user, self.team, 'invite_members', raise_exception=True
            )
    
    def test_get_user_accessible_teams(self):
        """Test getting user accessible teams with permissions."""
        from .services import get_user_accessible_teams
        
        teams_info = get_user_accessible_teams(self.user)
        
        self.assertEqual(len(teams_info), 1)
        team_info = teams_info[0]
        
        self.assertEqual(team_info['team'], self.team)
        self.assertEqual(team_info['role'], 'Admin')
        self.assertTrue(team_info['is_owner'])
        self.assertTrue(team_info['can_invite'])
        self.assertTrue(team_info['can_manage_members'])
        self.assertTrue(team_info['can_manage_projects'])
        self.assertIsInstance(team_info['permissions'], list)
    
    def test_validate_team_action_success(self):
        """Test successful team action validation."""
        from .services import validate_team_action
        
        success, error_msg = validate_team_action(self.user, self.team, 'invite')
        self.assertTrue(success)
        self.assertEqual(error_msg, "")
    
    def test_validate_team_action_failure(self):
        """Test failed team action validation."""
        from .services import validate_team_action
        
        external_user = User.objects.create_user('external', 'external@test.com')
        
        success, error_msg = validate_team_action(external_user, self.team, 'invite')
        self.assertFalse(success)
        self.assertIn('must be a member', error_msg)
    
    def test_validate_team_action_unknown(self):
        """Test validation with unknown action."""
        from .services import validate_team_action
        
        success, error_msg = validate_team_action(self.user, self.team, 'unknown_action')
        self.assertFalse(success)
        self.assertIn('Unknown action', error_msg)