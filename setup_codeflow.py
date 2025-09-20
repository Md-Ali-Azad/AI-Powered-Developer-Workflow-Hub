#!/usr/bin/env python3
"""
CodeFlow Setup Script

This script helps set up CodeFlow with GitHub integration.
Run this after cloning the repository to get started quickly.
"""

import os
import sys
import subprocess
import getpass
from pathlib import Path


def run_command(command, description=""):
    """Run a shell command and handle errors."""
    print(f"Running: {description or command}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required.")
        sys.exit(1)
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")


def install_dependencies():
    """Install Python dependencies."""
    print("\n=== Installing Dependencies ===")
    
    # Install basic requirements
    if not run_command("pip install -r requirements.txt", "Installing basic requirements"):
        print("Failed to install basic requirements. Please check your pip installation.")
        return False
    
    # Install GitHub integration
    print("\nInstalling GitHub integration...")
    if not run_command("pip install PyGithub", "Installing PyGithub"):
        print("Warning: Failed to install PyGithub. GitHub integration will not be available.")
        return False
    
    return True


def setup_database():
    """Set up the database."""
    print("\n=== Setting up Database ===")
    
    if not run_command("python manage.py migrate", "Running database migrations"):
        print("Failed to set up database.")
        return False
    
    return True


def create_superuser():
    """Create Django superuser."""
    print("\n=== Creating Superuser ===")
    print("You'll need a superuser account to access the admin interface.")
    
    create = input("Create superuser now? (y/n): ").lower().strip()
    if create == 'y':
        if not run_command("python manage.py createsuperuser", "Creating superuser"):
            print("Failed to create superuser. You can create one later with: python manage.py createsuperuser")
            return False
    else:
        print("Skipping superuser creation. You can create one later with: python manage.py createsuperuser")
    
    return True


def setup_github_integration():
    """Set up GitHub integration."""
    print("\n=== GitHub Integration Setup ===")
    
    setup = input("Set up GitHub integration now? (y/n): ").lower().strip()
    if setup != 'y':
        print("Skipping GitHub setup. You can set it up later with: python manage.py setup_github")
        return True
    
    print("\nTo set up GitHub integration, you need a Personal Access Token.")
    print("1. Go to: https://github.com/settings/tokens")
    print("2. Click 'Generate new token' > 'Generate new token (classic)'")
    print("3. Select scopes: 'repo' and 'public_repo'")
    print("4. Copy the generated token")
    print()
    
    token = getpass.getpass("Enter your GitHub token (input will be hidden): ").strip()
    
    if not token:
        print("No token provided. Skipping GitHub setup.")
        return True
    
    if not run_command(f"python manage.py setup_github --token {token}", "Setting up GitHub integration"):
        print("Failed to set up GitHub integration.")
        return False
    
    print("✓ GitHub integration configured successfully!")
    return True


def create_env_file():
    """Create .env file if it doesn't exist."""
    env_file = Path(".env")
    
    if env_file.exists():
        print("✓ .env file already exists")
        return True
    
    print("\n=== Creating .env file ===")
    
    # Get Gemini API key
    print("CodeFlow uses Google Gemini AI for enhanced features.")
    print("Get your API key from: https://makersuite.google.com/app/apikey")
    
    gemini_key = input("Enter your Gemini API key (or press Enter to skip): ").strip()
    
    env_content = []
    
    if gemini_key:
        env_content.append(f"GEMINI_API_KEY={gemini_key}")
    else:
        env_content.append("GEMINI_API_KEY=your_gemini_api_key_here")
    
    # Add GitHub token placeholder
    env_content.append("# GitHub API Token - Get from https://github.com/settings/tokens")
    env_content.append("GITHUB_TOKEN=your_github_token_here")
    env_content.append("# GitHub Webhook Secret (optional, for webhook security)")
    env_content.append("GITHUB_WEBHOOK_SECRET=your_webhook_secret_here")
    
    try:
        with open(env_file, 'w') as f:
            f.write('\n'.join(env_content) + '\n')
        print(f"✓ Created {env_file}")
        return True
    except Exception as e:
        print(f"Failed to create .env file: {e}")
        return False


def main():
    """Main setup function."""
    print("🚀 CodeFlow Setup Script")
    print("=" * 50)
    
    # Check Python version
    check_python_version()
    
    # Check if we're in the right directory
    if not Path("manage.py").exists():
        print("Error: manage.py not found. Please run this script from the project root directory.")
        sys.exit(1)
    
    # Create .env file
    if not create_env_file():
        print("Setup failed at .env file creation.")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("Setup failed at dependency installation.")
        sys.exit(1)
    
    # Set up database
    if not setup_database():
        print("Setup failed at database setup.")
        sys.exit(1)
    
    # Create superuser
    if not create_superuser():
        print("Setup failed at superuser creation.")
        sys.exit(1)
    
    # Set up GitHub integration
    if not setup_github_integration():
        print("Setup failed at GitHub integration.")
        sys.exit(1)
    
    # Final instructions
    print("\n" + "=" * 50)
    print("🎉 Setup Complete!")
    print("=" * 50)
    print()
    print("Next steps:")
    print("1. Start the development server:")
    print("   python manage.py runserver")
    print()
    print("2. Open your browser and go to:")
    print("   http://127.0.0.1:8000")
    print()
    print("3. Create an account or log in with your superuser credentials")
    print()
    print("4. Create a team and start adding projects!")
    print()
    
    if Path(".env").exists():
        print("Configuration files:")
        print("• .env - Environment variables (keep this secure!)")
        print("• db.sqlite3 - Database file")
        print()
    
    print("Documentation:")
    print("• README.md - General information")
    print("• GITHUB_INTEGRATION.md - GitHub setup guide")
    print()
    print("Useful commands:")
    print("• python manage.py setup_github --check - Check GitHub config")
    print("• python manage.py createsuperuser - Create admin user")
    print("• python manage.py migrate - Update database")


if __name__ == "__main__":
    main()