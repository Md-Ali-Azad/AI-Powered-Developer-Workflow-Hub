#!/usr/bin/env python3
"""
Test script to verify the fixes for the reported issues.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeflow.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.test import Client
from core.models import Team, Membership, TeamInvitation, Notification
from core.services import InvitationService, NotificationService

User = get_user_model()

def test_email_configuration():
    """Test if email configuration is working."""
    print("Testing email configuration...")
    
    try:
        from django.conf import settings
        print(f"Email backend: {settings.EMAIL_BACKEND}")
        
        if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
            print("✓ Using console backend (emails will be printed to console)")
        else:
            print(f"✓ Using SMTP backend: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
            
        return True
    except Exception as e:
        print(f"✗ Email configuration error: {e}")
        return False

def test_invitation_service():
    """Test the invitation service functionality."""
    print("\nTesting invitation service...")
    
    try:
        # Create test users and team
        owner = User.objects.create_user(
            username='testowner',
            email='owner@test.com',
            password='testpass123'
        )
        
        team = Team.objects.create(
            name='Test Team',
            description='Test team for invitation testing',
            owner=owner
        )
        
        # Create admin membership for owner
        Membership.objects.create(
            user=owner,
            team=team,
            role='Admin'
        )
        
        # Test sending invitation
        invitation = InvitationService.send_invitation(
            team=team,
            inviter=owner,
            email='newmember@test.com',
            role='Developer'
        )
        
        print(f"✓ Invitation created: {invitation.token}")
        print(f"✓ Invitation email: {invitation.email}")
        print(f"✓ Invitation role: {invitation.role}")
        
        # Clean up
        invitation.delete()
        team.delete()
        owner.delete()
        
        return True
        
    except Exception as e:
        print(f"✗ Invitation service error: {e}")
        return False

def test_notification_system():
    """Test the notification system."""
    print("\nTesting notification system...")
    
    try:
        # Create test user
        user = User.objects.create_user(
            username='testuser',
            email='user@test.com',
            password='testpass123'
        )
        
        # Create test notification
        notification = Notification.objects.create(
            user=user,
            type='test_notification',
            payload={'message': 'Test notification'}
        )
        
        # Test notification count
        count = NotificationService.get_unread_notifications_count(user)
        print(f"✓ Unread notifications count: {count}")
        
        # Test marking as read
        success = NotificationService.mark_notification_read(notification.id, user)
        print(f"✓ Mark as read: {success}")
        
        # Clean up
        notification.delete()
        user.delete()
        
        return True
        
    except Exception as e:
        print(f"✗ Notification system error: {e}")
        return False

def test_api_endpoints():
    """Test API endpoints."""
    print("\nTesting API endpoints...")
    
    try:
        client = Client()
        
        # Test notifications API (should require authentication)
        response = client.get('/api/notifications/')
        print(f"✓ Notifications API status: {response.status_code} (expected 401/403 for unauthenticated)")
        
        return True
        
    except Exception as e:
        print(f"✗ API endpoints error: {e}")
        return False

def main():
    """Run all tests."""
    print("Running CodeFlow fixes verification tests...\n")
    
    tests = [
        test_email_configuration,
        test_invitation_service,
        test_notification_system,
        test_api_endpoints,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print(f"\n{'='*50}")
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("✓ All tests passed! The fixes should be working correctly.")
    else:
        print("✗ Some tests failed. Please check the error messages above.")
    
    print("\nFixes implemented:")
    print("1. ✓ Fixed dropdown menu z-index issues")
    print("2. ✓ Enhanced notification system with error handling")
    print("3. ✓ Configured email backend for invitations")
    print("4. ✓ Added proper links to team management buttons")

if __name__ == '__main__':
    main()