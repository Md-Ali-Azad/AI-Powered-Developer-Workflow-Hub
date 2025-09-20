"""
Unit tests for team management models.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta
import uuid

from .models import Team, Membership, TeamInvitation, Notification

User = get_user_model()


class TeamModelTest(TestCase):
    """Test cases for Team model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
    
    def test_team_creation(self):
        """Test basic team creation."""
        team = Team.objects.create(
            name='Test Team',
            owner=self.user
        )
        
        self.assertEqual(team.name, 'Test Team')
        self.assertEqual(team.owner, self.user)
        self.assertIsNotNone(team.created_at)
        self.assertEqual(str(team), 'Test Team')
    
    def test_team_name_max_length(self):
        """Test team name maximum length constraint."""
        long_name = 'x' * 201  # Exceeds 200 character limit
        
        with self.assertRaises(ValidationError):
            team = Team(name=long_name, owner=self.user)
            team.full_clean()
    
    def test_team_owner_cascade_delete(self):
        """Test that team is deleted when owner is deleted."""
        team = Team.objects.create(name='Test Team', owner=self.user)
        team_id = team.id
        
        self.user.delete()
        
        with self.assertRaises(Team.DoesNotExist):
            Team.objects.get(id=team_id)


class MembershipModelTest(TestCase):
    """Test cases for Membership model."""
    
    def setUp(self):
        """Set up test data."""
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.member = User.objects.create_user(
            username='member',
            email='member@test.com',
            password='testpass123'
        )
        self.team = Team.objects.create(name='Test Team', owner=self.owner)
    
    def test_membership_creation(self):
        """Test basic membership creation."""
        membership = Membership.objects.create(
            user=self.member,
            team=self.team,
            role='Developer'
        )
        
        self.assertEqual(membership.user, self.member)
        self.assertEqual(membership.team, self.team)
        self.assertEqual(membership.role, 'Developer')
        self.assertIsNotNone(membership.created_at)
        self.assertEqual(str(membership), f"{self.member.username} - {self.team.name} (Developer)")
    
    def test_membership_role_choices(self):
        """Test membership role choices validation."""
        # Valid roles
        for role in ['Admin', 'Developer', 'Viewer']:
            membership = Membership(user=self.member, team=self.team, role=role)
            membership.full_clean()  # Should not raise
        
        # Invalid role
        with self.assertRaises(ValidationError):
            membership = Membership(user=self.member, team=self.team, role='InvalidRole')
            membership.full_clean()
    
    def test_membership_unique_constraint(self):
        """Test unique constraint on user-team combination."""
        Membership.objects.create(
            user=self.member,
            team=self.team,
            role='Developer'
        )
        
        # Try to create duplicate membership
        with self.assertRaises(IntegrityError):
            Membership.objects.create(
                user=self.member,
                team=self.team,
                role='Admin'
            )
    
    def test_membership_cascade_delete_user(self):
        """Test membership deletion when user is deleted."""
        membership = Membership.objects.create(
            user=self.member,
            team=self.team,
            role='Developer'
        )
        membership_id = membership.id
        
        self.member.delete()
        
        with self.assertRaises(Membership.DoesNotExist):
            Membership.objects.get(id=membership_id)
    
    def test_membership_cascade_delete_team(self):
        """Test membership deletion when team is deleted."""
        membership = Membership.objects.create(
            user=self.member,
            team=self.team,
            role='Developer'
        )
        membership_id = membership.id
        
        self.team.delete()
        
        with self.assertRaises(Membership.DoesNotExist):
            Membership.objects.get(id=membership_id)


class TeamInvitationModelTest(TestCase):
    """Test cases for TeamInvitation model."""
    
    def setUp(self):
        """Set up test data."""
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.invitee = User.objects.create_user(
            username='invitee',
            email='invitee@test.com',
            password='testpass123'
        )
        self.team = Team.objects.create(name='Test Team', owner=self.owner)
    
    def test_invitation_creation(self):
        """Test basic invitation creation."""
        invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            invited_user=self.invitee,
            email=self.invitee.email,
            role='Developer'
        )
        
        self.assertEqual(invitation.team, self.team)
        self.assertEqual(invitation.invited_by, self.owner)
        self.assertEqual(invitation.invited_user, self.invitee)
        self.assertEqual(invitation.email, self.invitee.email)
        self.assertEqual(invitation.role, 'Developer')
        self.assertEqual(invitation.status, 'pending')  # Default status
        self.assertIsNotNone(invitation.token)
        self.assertIsNotNone(invitation.expires_at)
        self.assertIsNotNone(invitation.created_at)
    
    def test_invitation_without_user(self):
        """Test invitation creation for non-registered user."""
        invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='newuser@test.com',
            role='Developer'
        )
        
        self.assertIsNone(invitation.invited_user)
        self.assertEqual(invitation.email, 'newuser@test.com')
    
    def test_invitation_status_choices(self):
        """Test invitation status choices validation."""
        # Valid statuses
        for status in ['pending', 'accepted', 'declined', 'expired']:
            invitation = TeamInvitation(
                team=self.team,
                invited_by=self.owner,
                email='test@test.com',
                status=status
            )
            invitation.full_clean()  # Should not raise
        
        # Invalid status
        with self.assertRaises(ValidationError):
            invitation = TeamInvitation(
                team=self.team,
                invited_by=self.owner,
                email='test@test.com',
                status='invalid_status'
            )
            invitation.full_clean()
    
    def test_invitation_role_choices(self):
        """Test invitation role choices validation."""
        # Valid roles (same as Membership)
        for role in ['Admin', 'Developer', 'Viewer']:
            invitation = TeamInvitation(
                team=self.team,
                invited_by=self.owner,
                email='test@test.com',
                role=role
            )
            invitation.full_clean()  # Should not raise
    
    def test_invitation_unique_constraint(self):
        """Test unique constraint on team-email-status combination."""
        TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='test@test.com',
            status='pending'
        )
        
        # Try to create duplicate pending invitation
        with self.assertRaises(IntegrityError):
            TeamInvitation.objects.create(
                team=self.team,
                invited_by=self.owner,
                email='test@test.com',
                status='pending'
            )
    
    def test_invitation_different_status_allowed(self):
        """Test that same email can have invitations with different statuses."""
        TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='test@test.com',
            status='declined'
        )
        
        # Should be able to create new pending invitation
        invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='test@test.com',
            status='pending'
        )
        
        self.assertEqual(invitation.status, 'pending')
    
    def test_invitation_token_uniqueness(self):
        """Test that invitation tokens are unique."""
        invitation1 = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='test1@test.com'
        )
        invitation2 = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='test2@test.com'
        )
        
        self.assertNotEqual(invitation1.token, invitation2.token)
    
    def test_invitation_auto_expiration(self):
        """Test automatic expiration date setting."""
        invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='test@test.com'
        )
        
        # Should have expiration date set (default 7 days)
        self.assertIsNotNone(invitation.expires_at)
        self.assertGreater(invitation.expires_at, timezone.now())
        
        # Should be approximately 7 days from now
        expected_expiry = timezone.now() + timedelta(days=7)
        time_diff = abs((invitation.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 60)  # Within 1 minute
    
    def test_invitation_custom_expiration(self):
        """Test setting custom expiration date."""
        custom_expiry = timezone.now() + timedelta(days=3)
        invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='test@test.com',
            expires_at=custom_expiry
        )
        
        self.assertEqual(invitation.expires_at, custom_expiry)
    
    def test_invitation_is_expired_method(self):
        """Test is_expired method."""
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
        
        self.assertTrue(expired_invitation.is_expired())
        self.assertFalse(valid_invitation.is_expired())
    
    def test_invitation_string_representation(self):
        """Test invitation string representation."""
        invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='test@test.com',
            status='pending'
        )
        
        expected_str = f"Invitation to test@test.com for {self.team.name} (pending)"
        self.assertEqual(str(invitation), expected_str)
    
    def test_invitation_indexes(self):
        """Test that database indexes are properly created."""
        # This test verifies the Meta.indexes configuration
        # We can't directly test index creation, but we can verify the configuration exists
        indexes = TeamInvitation._meta.indexes
        
        # Check that we have the expected number of indexes
        self.assertEqual(len(indexes), 3)
        
        # Check index field names
        index_fields = [index.fields for index in indexes]
        self.assertIn(['token'], index_fields)
        self.assertIn(['email', 'status'], index_fields)
        self.assertIn(['expires_at'], index_fields)
    
    def test_invitation_cascade_delete_team(self):
        """Test invitation deletion when team is deleted."""
        invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='test@test.com'
        )
        invitation_id = invitation.id
        
        self.team.delete()
        
        with self.assertRaises(TeamInvitation.DoesNotExist):
            TeamInvitation.objects.get(id=invitation_id)
    
    def test_invitation_cascade_delete_invited_by(self):
        """Test invitation deletion when inviter is deleted."""
        invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            email='test@test.com'
        )
        invitation_id = invitation.id
        
        self.owner.delete()
        
        with self.assertRaises(TeamInvitation.DoesNotExist):
            TeamInvitation.objects.get(id=invitation_id)
    
    def test_invitation_cascade_delete_invited_user(self):
        """Test invitation behavior when invited user is deleted."""
        invitation = TeamInvitation.objects.create(
            team=self.team,
            invited_by=self.owner,
            invited_user=self.invitee,
            email=self.invitee.email
        )
        
        self.invitee.delete()
        
        # Invitation should still exist but invited_user should be None
        invitation.refresh_from_db()
        self.assertIsNone(invitation.invited_user)
        self.assertEqual(invitation.email, 'invitee@test.com')


class NotificationModelTest(TestCase):
    """Test cases for Notification model with team-related types."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
    
    def test_notification_team_types(self):
        """Test team-related notification types."""
        team_notification_types = [
            'team_invitation',
            'invitation_accepted',
            'invitation_declined',
            'team_member_added',
            'team_role_changed'
        ]
        
        for notification_type in team_notification_types:
            notification = Notification.objects.create(
                user=self.user,
                type=notification_type,
                payload={'test': 'data'}
            )
            
            self.assertEqual(notification.type, notification_type)
            self.assertEqual(notification.payload, {'test': 'data'})
            self.assertIsNone(notification.read_at)
            self.assertIsNotNone(notification.created_at)
    
    def test_notification_payload_structure(self):
        """Test notification payload structure for team invitations."""
        payload = {
            'team_id': 1,
            'team_name': 'Test Team',
            'invited_by': 'owner',
            'invited_by_name': 'Team Owner',
            'role': 'Developer',
            'invitation_token': str(uuid.uuid4()),
            'expires_at': timezone.now().isoformat()
        }
        
        notification = Notification.objects.create(
            user=self.user,
            type='team_invitation',
            payload=payload
        )
        
        self.assertEqual(notification.payload['team_name'], 'Test Team')
        self.assertEqual(notification.payload['role'], 'Developer')
        self.assertIn('invitation_token', notification.payload)
    
    def test_notification_indexes(self):
        """Test notification model indexes."""
        indexes = Notification._meta.indexes
        
        # Check that we have the expected indexes
        self.assertEqual(len(indexes), 3)
        
        # Check index field names
        index_fields = [index.fields for index in indexes]
        self.assertIn(['user', 'read_at'], index_fields)
        self.assertIn(['type'], index_fields)
        self.assertIn(['created_at'], index_fields)
    
    def test_notification_string_representation(self):
        """Test notification string representation."""
        notification = Notification.objects.create(
            user=self.user,
            type='team_invitation',
            payload={'team_name': 'Test Team'}
        )
        
        expected_str = f"Notification for {self.user.username}: team_invitation"
        self.assertEqual(str(notification), expected_str)