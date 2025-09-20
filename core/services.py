"""
Service layer for team management and invitation handling.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.core.exceptions import PermissionDenied
from datetime import timedelta
import logging
from functools import wraps

from .models import TeamInvitation, Team, Membership, Notification

User = get_user_model()
logger = logging.getLogger(__name__)


class InvitationService:
    """Service class for handling team invitation operations."""
    
    @staticmethod
    def send_invitation(team, inviter, email, role='Developer'):
        """
        Send a team invitation to the specified email address.
        
        Args:
            team: Team instance to invite user to
            inviter: User instance who is sending the invitation
            email: Email address to send invitation to
            role: Role to assign to the invited user (default: 'Developer')
            
        Returns:
            TeamInvitation instance if successful, None if validation fails
            
        Raises:
            ValueError: If validation fails
            PermissionError: If inviter lacks permission
        """
        # Validate inviter permissions
        if not TeamPermissions.can_invite_members(inviter, team):
            error_msg = TeamPermissions.get_permission_error_message(inviter, team, 'invite_members')
            raise PermissionError(error_msg)
        
        # Check for existing pending invitation
        existing_invitation = TeamInvitation.objects.filter(
            team=team,
            email=email,
            status='pending'
        ).first()
        
        if existing_invitation and not existing_invitation.is_expired():
            raise ValueError(f"Pending invitation already exists for {email}")
        
        # Check if user is already a team member
        try:
            user = User.objects.get(email=email)
            if Membership.objects.filter(user=user, team=team).exists():
                raise ValueError(f"User {email} is already a member of team {team.name}")
        except User.DoesNotExist:
            user = None
        
        # Create invitation with transaction to ensure consistency
        with transaction.atomic():
            # Mark any existing invitations as expired
            TeamInvitation.objects.filter(
                team=team,
                email=email,
                status='pending'
            ).update(status='expired')
            
            # Create new invitation
            invitation = TeamInvitation.objects.create(
                team=team,
                invited_by=inviter,
                invited_user=user,
                email=email,
                role=role,
                expires_at=timezone.now() + timedelta(days=7)
            )
            
            # Send email notification
            InvitationService._send_invitation_email(invitation)
            
            # Create in-app notification if user exists
            if user:
                InvitationService._create_invitation_notification(invitation, user)
            
            logger.info(f"Invitation sent to {email} for team {team.name} by {inviter.username}")
            return invitation
    
    @staticmethod
    def accept_invitation(invitation_token, user):
        """
        Accept a team invitation using the invitation token.
        
        Args:
            invitation_token: UUID token from the invitation
            user: User instance accepting the invitation
            
        Returns:
            Membership instance if successful, None if validation fails
            
        Raises:
            ValueError: If invitation is invalid or expired
        """
        try:
            invitation = TeamInvitation.objects.get(
                token=invitation_token,
                status='pending'
            )
        except TeamInvitation.DoesNotExist:
            raise ValueError("Invalid or expired invitation token")
        
        # Check if invitation is expired
        if invitation.is_expired():
            invitation.status = 'expired'
            invitation.save()
            raise ValueError("Invitation has expired")
        
        # Validate that the user matches the invitation
        if invitation.email != user.email:
            raise ValueError("Invitation email does not match user email")
        
        # Check if user is already a team member
        if Membership.objects.filter(user=user, team=invitation.team).exists():
            raise ValueError(f"User is already a member of team {invitation.team.name}")
        
        # Accept invitation with transaction
        with transaction.atomic():
            # Create membership
            membership = Membership.objects.create(
                user=user,
                team=invitation.team,
                role=invitation.role
            )
            
            # Update invitation status
            invitation.status = 'accepted'
            invitation.invited_user = user
            invitation.save()
            
            # Create notifications
            InvitationService._create_acceptance_notifications(invitation, user)
            
            logger.info(f"User {user.username} accepted invitation to team {invitation.team.name}")
            return membership
    
    @staticmethod
    def decline_invitation(invitation_token, user=None):
        """
        Decline a team invitation using the invitation token.
        
        Args:
            invitation_token: UUID token from the invitation
            user: Optional user instance declining the invitation
            
        Returns:
            True if successful, False if validation fails
            
        Raises:
            ValueError: If invitation is invalid or expired
        """
        try:
            invitation = TeamInvitation.objects.get(
                token=invitation_token,
                status='pending'
            )
        except TeamInvitation.DoesNotExist:
            raise ValueError("Invalid or expired invitation token")
        
        # Check if invitation is expired
        if invitation.is_expired():
            invitation.status = 'expired'
            invitation.save()
            raise ValueError("Invitation has expired")
        
        # Validate user if provided
        if user and invitation.email != user.email:
            raise ValueError("Invitation email does not match user email")
        
        # Decline invitation
        with transaction.atomic():
            invitation.status = 'declined'
            if user:
                invitation.invited_user = user
            invitation.save()
            
            # Create notification for inviter
            InvitationService._create_decline_notification(invitation)
            
            logger.info(f"Invitation to {invitation.email} for team {invitation.team.name} was declined")
            return True
    
    @staticmethod
    def get_pending_invitations(user):
        """
        Get all pending invitations for a user.
        
        Args:
            user: User instance to get invitations for
            
        Returns:
            QuerySet of pending TeamInvitation instances
        """
        return TeamInvitation.objects.filter(
            email=user.email,
            status='pending'
        ).select_related('team', 'invited_by')
    
    @staticmethod
    def get_sent_invitations(user, team=None):
        """
        Get invitations sent by a user, optionally filtered by team.
        
        Args:
            user: User instance who sent the invitations
            team: Optional team to filter by
            
        Returns:
            QuerySet of TeamInvitation instances
        """
        queryset = TeamInvitation.objects.filter(
            invited_by=user
        ).select_related('team', 'invited_user')
        
        if team:
            queryset = queryset.filter(team=team)
            
        return queryset.order_by('-created_at')
    
    @staticmethod
    def cleanup_expired_invitations():
        """
        Mark expired invitations as expired.
        This method can be called periodically to clean up old invitations.
        
        Returns:
            Number of invitations marked as expired
        """
        expired_count = TeamInvitation.objects.filter(
            status='pending',
            expires_at__lt=timezone.now()
        ).update(status='expired')
        
        if expired_count > 0:
            logger.info(f"Marked {expired_count} invitations as expired")
        
        return expired_count
    

    
    @staticmethod
    def _send_invitation_email(invitation):
        """
        Send invitation email to the invited user.
        
        Args:
            invitation: TeamInvitation instance
        """
        try:
            # Build invitation URL (this would need to be updated with actual URL pattern)
            invitation_url = f"http://localhost:8000/invitations/{invitation.token}/accept/"
            
            subject = f"You're invited to join {invitation.team.name}"
            message = f"""
Hello,

{invitation.invited_by.get_full_name() or invitation.invited_by.username} has invited you to join the team "{invitation.team.name}" as a {invitation.role}.

To accept this invitation, click the link below:
{invitation_url}

This invitation will expire on {invitation.expires_at.strftime('%B %d, %Y at %I:%M %p')}.

If you don't want to join this team, you can ignore this email.

Best regards,
The CodeFlow Team
            """.strip()
            
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@codeflow.com'),
                recipient_list=[invitation.email],
                fail_silently=False
            )
            
            logger.info(f"Invitation email sent to {invitation.email}")
            
        except Exception as e:
            logger.error(f"Failed to send invitation email to {invitation.email}: {str(e)}")
            # Don't raise the exception to avoid breaking the invitation creation
    
    @staticmethod
    def _create_invitation_notification(invitation, user):
        """
        Create in-app notification for team invitation.
        
        Args:
            invitation: TeamInvitation instance
            user: User instance to notify
        """
        try:
            Notification.objects.create(
                user=user,
                type='team_invitation',
                payload={
                    'team_id': invitation.team.id,
                    'team_name': invitation.team.name,
                    'invited_by': invitation.invited_by.username,
                    'invited_by_name': invitation.invited_by.get_full_name() or invitation.invited_by.username,
                    'role': invitation.role,
                    'invitation_token': str(invitation.token),
                    'expires_at': invitation.expires_at.isoformat()
                }
            )
            logger.info(f"Created invitation notification for user {user.username}")
        except Exception as e:
            logger.error(f"Failed to create invitation notification: {str(e)}")
    
    @staticmethod
    def _create_acceptance_notifications(invitation, user):
        """
        Create notifications when an invitation is accepted.
        
        Args:
            invitation: TeamInvitation instance
            user: User who accepted the invitation
        """
        try:
            # Notify the inviter
            Notification.objects.create(
                user=invitation.invited_by,
                type='invitation_accepted',
                payload={
                    'team_id': invitation.team.id,
                    'team_name': invitation.team.name,
                    'accepted_by': user.username,
                    'accepted_by_name': user.get_full_name() or user.username,
                    'role': invitation.role
                }
            )
            
            # Notify team admins (excluding the inviter)
            admin_members = Membership.objects.filter(
                team=invitation.team,
                role='Admin'
            ).exclude(user=invitation.invited_by).select_related('user')
            
            for membership in admin_members:
                Notification.objects.create(
                    user=membership.user,
                    type='team_member_added',
                    payload={
                        'team_id': invitation.team.id,
                        'team_name': invitation.team.name,
                        'new_member': user.username,
                        'new_member_name': user.get_full_name() or user.username,
                        'role': invitation.role,
                        'invited_by': invitation.invited_by.username
                    }
                )
            
            logger.info(f"Created acceptance notifications for invitation to {invitation.email}")
        except Exception as e:
            logger.error(f"Failed to create acceptance notifications: {str(e)}")
    
    @staticmethod
    def _create_decline_notification(invitation):
        """
        Create notification when an invitation is declined.
        
        Args:
            invitation: TeamInvitation instance
        """
        try:
            Notification.objects.create(
                user=invitation.invited_by,
                type='invitation_declined',
                payload={
                    'team_id': invitation.team.id,
                    'team_name': invitation.team.name,
                    'declined_by_email': invitation.email,
                    'role': invitation.role
                }
            )
            logger.info(f"Created decline notification for invitation to {invitation.email}")
        except Exception as e:
            logger.error(f"Failed to create decline notification: {str(e)}")


class TeamPermissions:
    """
    Centralized permission system for team-based operations.
    Implements role-based access control for team management.
    """
    
    # Define permissions for each role
    ROLE_PERMISSIONS = {
        'Admin': [
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
        ],
        'Developer': [
            'view_team',
            'view_projects', 
            'create_tasks',
            'manage_own_tasks',
            'view_team_dashboard'
        ],
        'Viewer': [
            'view_team',
            'view_projects',
            'view_team_dashboard'
        ]
    }
    
    @staticmethod
    def has_permission(user, team, permission):
        """
        Check if user has specific permission in team.
        
        Args:
            user: User instance to check permissions for
            team: Team instance to check permissions against  
            permission: String permission name to check
            
        Returns:
            Boolean indicating if user has the permission
        """
        # Team owner always has all permissions
        if team.owner == user:
            return True
            
        # Get user's role in the team
        try:
            membership = Membership.objects.get(user=user, team=team)
            user_role = membership.role
        except Membership.DoesNotExist:
            return False
            
        # Check if role has the requested permission
        role_permissions = TeamPermissions.ROLE_PERMISSIONS.get(user_role, [])
        return permission in role_permissions
    
    @staticmethod
    def get_user_role(user, team):
        """
        Get user's role in a team.
        
        Args:
            user: User instance
            team: Team instance
            
        Returns:
            String role name or None if user is not a member
        """
        # Team owner is always Admin
        if team.owner == user:
            return 'Admin'
            
        try:
            membership = Membership.objects.get(user=user, team=team)
            return membership.role
        except Membership.DoesNotExist:
            return None
    
    @staticmethod
    def is_team_member(user, team):
        """
        Check if user is a member of the team.
        
        Args:
            user: User instance
            team: Team instance
            
        Returns:
            Boolean indicating team membership
        """
        if team.owner == user:
            return True
        return Membership.objects.filter(user=user, team=team).exists()
    
    @staticmethod
    def can_invite_members(user, team):
        """
        Check if user can invite members to team.
        
        Args:
            user: User instance
            team: Team instance
            
        Returns:
            Boolean indicating permission
        """
        return TeamPermissions.has_permission(user, team, 'invite_members')
    
    @staticmethod
    def can_manage_members(user, team):
        """
        Check if user can manage team members (change roles, remove members).
        
        Args:
            user: User instance
            team: Team instance
            
        Returns:
            Boolean indicating permission
        """
        return TeamPermissions.has_permission(user, team, 'manage_members')
    
    @staticmethod
    def can_manage_projects(user, team):
        """
        Check if user can manage team projects (create, delete, modify).
        
        Args:
            user: User instance
            team: Team instance
            
        Returns:
            Boolean indicating permission
        """
        return TeamPermissions.has_permission(user, team, 'manage_projects')
    
    @staticmethod
    def can_view_team(user, team):
        """
        Check if user can view team information and dashboard.
        
        Args:
            user: User instance
            team: Team instance
            
        Returns:
            Boolean indicating permission
        """
        return TeamPermissions.has_permission(user, team, 'view_team')
    
    @staticmethod
    def can_create_tasks(user, team):
        """
        Check if user can create tasks in team projects.
        
        Args:
            user: User instance
            team: Team instance
            
        Returns:
            Boolean indicating permission
        """
        return TeamPermissions.has_permission(user, team, 'create_tasks')
    
    @staticmethod
    def filter_user_teams(user):
        """
        Get all teams user has access to with their roles.
        
        Args:
            user: User instance
            
        Returns:
            List of dictionaries with team and role information
        """
        teams_with_roles = []
        
        # Get teams where user is owner
        owned_teams = Team.objects.filter(owner=user)
        for team in owned_teams:
            teams_with_roles.append({
                'team': team,
                'role': 'Admin',
                'is_owner': True
            })
        
        # Get teams where user is a member
        memberships = Membership.objects.filter(user=user).select_related('team')
        for membership in memberships:
            # Skip if already added as owner
            if membership.team.owner != user:
                teams_with_roles.append({
                    'team': membership.team,
                    'role': membership.role,
                    'is_owner': False
                })
        
        return teams_with_roles
    
    @staticmethod
    def filter_team_projects(user, team):
        """
        Filter team projects based on user's permissions.
        
        Args:
            user: User instance
            team: Team instance
            
        Returns:
            QuerySet of Project instances user can access
        """
        from .models import Project
        
        # If user can view team, they can see all team projects
        if TeamPermissions.can_view_team(user, team):
            return Project.objects.filter(team=team)
        else:
            # Return empty queryset if no access
            return Project.objects.none()
    
    @staticmethod
    def get_permission_error_message(user, team, permission):
        """
        Get appropriate error message for permission denial.
        
        Args:
            user: User instance
            team: Team instance  
            permission: Permission that was denied
            
        Returns:
            String error message
        """
        if not TeamPermissions.is_team_member(user, team):
            return f"You must be a member of team '{team.name}' to perform this action."
        
        user_role = TeamPermissions.get_user_role(user, team)
        
        permission_messages = {
            'invite_members': f"Only team admins can invite new members. Your role: {user_role}",
            'manage_members': f"Only team admins can manage team members. Your role: {user_role}",
            'manage_projects': f"Only team admins can manage projects. Your role: {user_role}",
            'create_projects': f"Only team admins can create projects. Your role: {user_role}",
            'delete_projects': f"Only team admins can delete projects. Your role: {user_role}",
            'manage_team_settings': f"Only team admins can modify team settings. Your role: {user_role}",
        }
        
        return permission_messages.get(
            permission, 
            f"You don't have permission to perform this action. Your role: {user_role}"
        )


class TeamService:
    """Service class for team management operations."""
    
    @staticmethod
    def create_team(owner, name):
        """
        Create a new team with the owner as admin.
        
        Args:
            owner: User instance who will own the team
            name: Name of the team
            
        Returns:
            Team instance
        """
        with transaction.atomic():
            team = Team.objects.create(name=name, owner=owner)
            Membership.objects.create(user=owner, team=team, role='Admin')
            logger.info(f"Team '{name}' created by {owner.username}")
            return team
    
    @staticmethod
    def get_user_teams(user):
        """
        Get all teams a user belongs to.
        
        Args:
            user: User instance
            
        Returns:
            QuerySet of Team instances
        """
        return Team.objects.filter(
            membership__user=user
        ).select_related('owner').prefetch_related('membership_set__user')
    
    @staticmethod
    def can_invite_members(user, team):
        """
        Check if user can invite members to team.
        
        Args:
            user: User instance
            team: Team instance
            
        Returns:
            Boolean indicating permission
        """
        return TeamPermissions.can_invite_members(user, team)

# Helper functions for view-level permission checking

def require_team_permission(permission):
    """
    Decorator to require specific team permission for view functions.
    
    Usage:
        @require_team_permission('invite_members')
        def my_view(request, team_id):
            # View logic here
    
    Args:
        permission: String permission name to require
        
    Returns:
        Decorator function
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Extract team_id from kwargs or args
            team_id = kwargs.get('team_id') or kwargs.get('pk')
            if not team_id and args:
                team_id = args[0]
            
            if not team_id:
                raise Http404("Team not found")
            
            # Get team and check permission
            team = get_object_or_404(Team, id=team_id)
            
            if not TeamPermissions.has_permission(request.user, team, permission):
                error_msg = TeamPermissions.get_permission_error_message(
                    request.user, team, permission
                )
                raise PermissionDenied(error_msg)
            
            # Add team to kwargs for convenience
            kwargs['team'] = team
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_team_membership(view_func):
    """
    Decorator to require team membership for view functions.
    
    Usage:
        @require_team_membership
        def my_view(request, team_id):
            # View logic here
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Extract team_id from kwargs or args
        team_id = kwargs.get('team_id') or kwargs.get('pk')
        if not team_id and args:
            team_id = args[0]
        
        if not team_id:
            raise Http404("Team not found")
        
        # Get team and check membership
        team = get_object_or_404(Team, id=team_id)
        
        if not TeamPermissions.is_team_member(request.user, team):
            raise PermissionDenied(f"You must be a member of team '{team.name}' to access this page.")
        
        # Add team to kwargs for convenience
        kwargs['team'] = team
        return view_func(request, *args, **kwargs)
    return wrapper


def check_team_permission(user, team, permission, raise_exception=True):
    """
    Helper function to check team permissions with optional exception raising.
    
    Args:
        user: User instance
        team: Team instance
        permission: Permission string to check
        raise_exception: Whether to raise PermissionDenied on failure
        
    Returns:
        Boolean indicating permission status
        
    Raises:
        PermissionDenied: If permission denied and raise_exception=True
    """
    has_perm = TeamPermissions.has_permission(user, team, permission)
    
    if not has_perm and raise_exception:
        error_msg = TeamPermissions.get_permission_error_message(user, team, permission)
        raise PermissionDenied(error_msg)
    
    return has_perm


def get_user_accessible_teams(user):
    """
    Get all teams accessible to a user with their permissions.
    
    Args:
        user: User instance
        
    Returns:
        List of dictionaries with team info and permissions
    """
    teams_info = []
    
    for team_info in TeamPermissions.filter_user_teams(user):
        team = team_info['team']
        role = team_info['role']
        
        # Get all permissions for this role
        permissions = TeamPermissions.ROLE_PERMISSIONS.get(role, [])
        
        teams_info.append({
            'team': team,
            'role': role,
            'is_owner': team_info['is_owner'],
            'permissions': permissions,
            'can_invite': 'invite_members' in permissions,
            'can_manage_members': 'manage_members' in permissions,
            'can_manage_projects': 'manage_projects' in permissions,
        })
    
    return teams_info


def validate_team_action(user, team, action):
    """
    Validate if user can perform a specific team action.
    
    Args:
        user: User instance
        team: Team instance  
        action: Action string (maps to permission)
        
    Returns:
        Tuple of (success: bool, error_message: str)
    """
    # Map actions to permissions
    action_permission_map = {
        'invite': 'invite_members',
        'manage_members': 'manage_members',
        'create_project': 'manage_projects',
        'delete_project': 'manage_projects',
        'view_dashboard': 'view_team',
        'create_task': 'create_tasks',
    }
    
    permission = action_permission_map.get(action)
    if not permission:
        return False, f"Unknown action: {action}"
    
    if TeamPermissions.has_permission(user, team, permission):
        return True, ""
    else:
        error_msg = TeamPermissions.get_permission_error_message(user, team, permission)
        return False, error_msg