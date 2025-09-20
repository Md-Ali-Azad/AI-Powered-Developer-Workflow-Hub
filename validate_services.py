#!/usr/bin/env python3
"""
Service Validation Script for CodeFlow

This script validates that all services are working correctly,
including GitHub integration and AI services.
"""

import os
import sys
import django
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeflow.settings')

try:
    django.setup()
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    print("Make sure you're in the project directory and dependencies are installed.")
    sys.exit(1)

from django.conf import settings


def test_github_integration():
    """Test GitHub integration."""
    print("=== Testing GitHub Integration ===")
    
    try:
        from core.github_service import GitHubService
        
        service = GitHubService()
        
        if not service.is_configured():
            print("❌ GitHub API not configured")
            print("   Set GITHUB_TOKEN in your .env file")
            print("   Run: python manage.py setup_github --token YOUR_TOKEN")
            return False
        
        print("✅ GitHub API configured")
        
        # Test with a public repository
        test_repo = "https://github.com/octocat/Hello-World"
        print(f"Testing repository validation with: {test_repo}")
        
        result = service.validate_repository_url(test_repo)
        
        if result['valid']:
            print("✅ Repository URL validation works")
            
            if result['accessible']:
                print("✅ Repository access works")
                repo_info = result['repo_info']
                print(f"   Repository: {repo_info['full_name']}")
                print(f"   Description: {repo_info['description']}")
            else:
                print("⚠️  Repository validation works but access failed")
                print(f"   Error: {result['error']}")
        else:
            print("❌ Repository validation failed")
            print(f"   Error: {result['error']}")
            return False
        
        # Test PR fetching
        print("Testing pull request fetching...")
        pr_result = service.get_pull_request_info(test_repo, 1)
        
        if pr_result['found']:
            print("✅ Pull request fetching works")
            pr_info = pr_result['pr_info']
            print(f"   PR: #{pr_info['number']} - {pr_info['title']}")
        else:
            print("⚠️  Pull request fetching test failed (this may be normal)")
            print(f"   Error: {pr_result['error']}")
        
        return True
        
    except ImportError:
        print("❌ PyGithub not installed")
        print("   Run: pip install PyGithub")
        return False
    except Exception as e:
        print(f"❌ GitHub integration error: {str(e)}")
        return False


def test_ai_integration():
    """Test AI integration."""
    print("\n=== Testing AI Integration ===")
    
    try:
        import google.generativeai as genai
        
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        
        if not api_key or api_key == 'your_gemini_api_key_here':
            print("❌ Gemini API key not configured")
            print("   Set GEMINI_API_KEY in your .env file")
            return False
        
        print("✅ Gemini API key configured")
        
        # Test API connection
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        test_prompt = "Say 'Hello from CodeFlow!' if you can read this."
        response = model.generate_content(test_prompt)
        
        if response and response.text:
            print("✅ Gemini API connection works")
            print(f"   Response: {response.text.strip()}")
            return True
        else:
            print("❌ Gemini API response empty")
            return False
            
    except ImportError:
        print("❌ google-generativeai not installed")
        print("   This should be included in requirements.txt")
        return False
    except Exception as e:
        print(f"❌ AI integration error: {str(e)}")
        return False


def test_database():
    """Test database connection."""
    print("\n=== Testing Database ===")
    
    try:
        from django.db import connection
        from core.models import User, Team, Project
        
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        print("✅ Database connection works")
        
        # Test model queries
        user_count = User.objects.count()
        team_count = Team.objects.count()
        project_count = Project.objects.count()
        
        print(f"   Users: {user_count}")
        print(f"   Teams: {team_count}")
        print(f"   Projects: {project_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return False


def test_environment():
    """Test environment configuration."""
    print("\n=== Testing Environment ===")
    
    # Check .env file
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file exists")
    else:
        print("⚠️  .env file not found")
    
    # Check required settings
    required_settings = ['SECRET_KEY', 'DEBUG']
    for setting in required_settings:
        if hasattr(settings, setting):
            print(f"✅ {setting} configured")
        else:
            print(f"❌ {setting} not configured")
    
    # Check optional settings
    optional_settings = {
        'GITHUB_TOKEN': 'GitHub integration',
        'GEMINI_API_KEY': 'AI features'
    }
    
    for setting, description in optional_settings.items():
        value = getattr(settings, setting, None)
        if value and value != f'your_{setting.lower()}_here':
            print(f"✅ {setting} configured ({description})")
        else:
            print(f"⚠️  {setting} not configured ({description} disabled)")
    
    return True


def main():
    """Run all validation tests."""
    print("🔍 CodeFlow Service Validation")
    print("=" * 50)
    
    results = []
    
    # Test environment
    results.append(test_environment())
    
    # Test database
    results.append(test_database())
    
    # Test GitHub integration
    results.append(test_github_integration())
    
    # Test AI integration
    results.append(test_ai_integration())
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Validation Summary")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print("🎉 All services are working correctly!")
        print("\nYour CodeFlow installation is ready to use.")
    else:
        print(f"⚠️  {passed}/{total} services are working correctly.")
        print("\nSome features may not be available. Check the errors above.")
    
    print("\nNext steps:")
    if passed < total:
        print("1. Fix any configuration issues shown above")
        print("2. Run this script again to verify fixes")
        print("3. Check the setup documentation for help")
    else:
        print("1. Start the server: python manage.py runserver")
        print("2. Open http://127.0.0.1:8000 in your browser")
        print("3. Create an account and start using CodeFlow!")
    
    print("\nFor help:")
    print("• README.md - General setup")
    print("• GITHUB_INTEGRATION.md - GitHub setup guide")
    print("• python manage.py setup_github --help - GitHub commands")


if __name__ == "__main__":
    main()