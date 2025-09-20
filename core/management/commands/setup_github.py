"""
Management command to help set up GitHub integration.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Help set up GitHub integration for CodeFlow'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Check current GitHub configuration status',
        )
        parser.add_argument(
            '--token',
            type=str,
            help='Set GitHub token (will be saved to .env file)',
        )

    def handle(self, *args, **options):
        if options['check']:
            self.check_github_config()
        elif options['token']:
            self.set_github_token(options['token'])
        else:
            self.show_setup_instructions()

    def check_github_config(self):
        """Check current GitHub configuration."""
        self.stdout.write(self.style.SUCCESS('=== GitHub Configuration Status ==='))
        
        # Check if PyGithub is installed
        try:
            import github
            self.stdout.write(self.style.SUCCESS('✓ PyGithub package is installed'))
        except ImportError:
            self.stdout.write(self.style.ERROR('✗ PyGithub package is NOT installed'))
            self.stdout.write('  Run: pip install PyGithub')
            return

        # Check token configuration
        github_token = getattr(settings, 'GITHUB_TOKEN', None)
        if github_token and github_token != 'your_github_token_here':
            self.stdout.write(self.style.SUCCESS('✓ GitHub token is configured'))
            
            # Test the token
            try:
                from core.github_service import GitHubService
                service = GitHubService()
                if service.is_configured():
                    self.stdout.write(self.style.SUCCESS('✓ GitHub API connection successful'))
                else:
                    self.stdout.write(self.style.ERROR('✗ GitHub API connection failed'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ GitHub API test failed: {str(e)}'))
        else:
            self.stdout.write(self.style.ERROR('✗ GitHub token is NOT configured'))
            self.stdout.write('  Set GITHUB_TOKEN in your .env file')

        # Check .env file
        env_file = os.path.join(settings.BASE_DIR, '.env')
        if os.path.exists(env_file):
            self.stdout.write(self.style.SUCCESS('✓ .env file exists'))
        else:
            self.stdout.write(self.style.WARNING('⚠ .env file does not exist'))

    def set_github_token(self, token):
        """Set GitHub token in .env file."""
        env_file = os.path.join(settings.BASE_DIR, '.env')
        
        # Read existing .env content
        env_content = []
        github_token_set = False
        
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if line.strip().startswith('GITHUB_TOKEN='):
                        env_content.append(f'GITHUB_TOKEN={token}\n')
                        github_token_set = True
                    else:
                        env_content.append(line)
        
        # Add token if not found
        if not github_token_set:
            env_content.append(f'GITHUB_TOKEN={token}\n')
        
        # Write back to .env file
        with open(env_file, 'w') as f:
            f.writelines(env_content)
        
        self.stdout.write(self.style.SUCCESS(f'✓ GitHub token saved to {env_file}'))
        self.stdout.write(self.style.WARNING('⚠ Please restart the Django server to apply changes'))

    def show_setup_instructions(self):
        """Show setup instructions for GitHub integration."""
        self.stdout.write(self.style.SUCCESS('=== GitHub Integration Setup ==='))
        self.stdout.write('')
        
        self.stdout.write('1. Install PyGithub package:')
        self.stdout.write('   pip install PyGithub')
        self.stdout.write('')
        
        self.stdout.write('2. Create a GitHub Personal Access Token:')
        self.stdout.write('   • Go to https://github.com/settings/tokens')
        self.stdout.write('   • Click "Generate new token" > "Generate new token (classic)"')
        self.stdout.write('   • Give it a descriptive name like "CodeFlow Integration"')
        self.stdout.write('   • Select scopes:')
        self.stdout.write('     - repo (for private repositories)')
        self.stdout.write('     - public_repo (for public repositories)')
        self.stdout.write('     - read:org (if you need organization access)')
        self.stdout.write('   • Click "Generate token" and copy the token')
        self.stdout.write('')
        
        self.stdout.write('3. Set the token in your environment:')
        self.stdout.write('   Option A: Use this command:')
        self.stdout.write('   python manage.py setup_github --token YOUR_TOKEN_HERE')
        self.stdout.write('')
        self.stdout.write('   Option B: Manually edit .env file:')
        self.stdout.write('   Add: GITHUB_TOKEN=your_token_here')
        self.stdout.write('')
        
        self.stdout.write('4. Restart your Django server')
        self.stdout.write('')
        
        self.stdout.write('5. Test the configuration:')
        self.stdout.write('   python manage.py setup_github --check')
        self.stdout.write('')
        
        self.stdout.write(self.style.WARNING('Security Notes:'))
        self.stdout.write('• Keep your GitHub token secure and never commit it to version control')
        self.stdout.write('• The .env file should be in your .gitignore')
        self.stdout.write('• Use environment variables in production')
        self.stdout.write('')
        
        self.stdout.write(self.style.SUCCESS('Features enabled with GitHub integration:'))
        self.stdout.write('• Repository URL validation')
        self.stdout.write('• Automatic project description sync')
        self.stdout.write('• Pull request auto-import from GitHub')
        self.stdout.write('• Repository statistics and information')
        self.stdout.write('• Real-time PR data fetching')