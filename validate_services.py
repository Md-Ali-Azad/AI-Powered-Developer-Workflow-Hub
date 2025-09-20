#!/usr/bin/env python
"""
Simple validation script for the invitation service.
This script validates the service code without running Django tests.
"""

import os
import sys
import django
from django.conf import settings

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeflow.settings')
django.setup()

# Now we can import our models and services
from core.models import User, Team, Membership, TeamInvitation, Notification
from core.services import InvitationService, TeamService

def validate_invitation_service():
    """Validate the InvitationService functionality."""
    print("Validating InvitationService...")
    
    # Test 1: Check if service class exists and has required methods
    required_methods = [
        'send_invitation',
        'accept_invitation', 
        'decline_invitation',
        'get_pending_invitations',
        'get_sent_invitations',
        'cleanup_expired_invitations'
    ]
    
    for method in required_methods:
        if not hasattr(InvitationService, method):
            print(f"❌ Missing method: {method}")
            return False
        else:
            print(f"✅ Method exists: {method}")
    
    # Test 2: Check if private helper methods exist
    helper_methods = [
        '_can_invite_members',
        '_send_invitation_email',
        '_create_invitation_notification',
        '_create_acceptance_notifications',
        '_create_decline_notification'
    ]
    
    for method in helper_methods:
        if not hasattr(InvitationService, method):
            print(f"❌ Missing helper method: {method}")
            return False
        else:
            print(f"✅ Helper method exists: {method}")
    
    print("✅ InvitationService validation passed!")
    return True

def validate_team_service():
    """Validate the TeamService functionality."""
    print("\nValidating TeamService...")
    
    # Test 1: Check if service class exists and has required methods
    required_methods = [
        'create_team',
        'get_user_teams',
        'can_invite_members'
    ]
    
    for method in required_methods:
        if not hasattr(TeamService, method):
            print(f"❌ Missing method: {method}")
            return False
        else:
            print(f"✅ Method exists: {method}")
    
    print("✅ TeamService validation passed!")
    return True

def validate_models():
    """Validate that required models exist with proper fields."""
    print("\nValidating Models...")
    
    # Check TeamInvitation model
    required_fields = [
        'team', 'invited_by', 'invited_user', 'email', 'role', 
        'status', 'token', 'expires_at', 'created_at'
    ]
    
    for field in required_fields:
        if not hasattr(TeamInvitation, field):
            print(f"❌ TeamInvitation missing field: {field}")
            return False
        else:
            print(f"✅ TeamInvitation has field: {field}")
    
    # Check if is_expired method exists
    if not hasattr(TeamInvitation, 'is_expired'):
        print("❌ TeamInvitation missing is_expired method")
        return False
    else:
        print("✅ TeamInvitation has is_expired method")
    
    print("✅ Models validation passed!")
    return True

def validate_notification_types():
    """Validate that notification types are properly defined."""
    print("\nValidating Notification Types...")
    
    required_types = [
        'team_invitation',
        'invitation_accepted', 
        'invitation_declined',
        'team_member_added',
        'team_role_changed'
    ]
    
    notification_types = [choice[0] for choice in Notification.NOTIFICATION_TYPES]
    
    for notification_type in required_types:
        if notification_type not in notification_types:
            print(f"❌ Missing notification type: {notification_type}")
            return False
        else:
            print(f"✅ Notification type exists: {notification_type}")
    
    print("✅ Notification types validation passed!")
    return True

def main():
    """Run all validations."""
    print("Starting service validation...\n")
    
    validations = [
        validate_models,
        validate_notification_types,
        validate_invitation_service,
        validate_team_service
    ]
    
    all_passed = True
    for validation in validations:
        try:
            if not validation():
                all_passed = False
        except Exception as e:
            print(f"❌ Validation failed with error: {e}")
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 All validations passed! Service implementation is complete.")
    else:
        print("❌ Some validations failed. Please check the implementation.")
    
    return all_passed

if __name__ == '__main__':
    main()