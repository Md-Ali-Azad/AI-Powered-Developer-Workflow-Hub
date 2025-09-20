"""
GitHub Integration Service for CodeFlow

This service handles GitHub API interactions including:
- Repository validation and data fetching
- Pull request information retrieval
- Webhook handling for real-time updates
- Authentication and permission management
"""

import re
import logging
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse
from django.conf import settings
from django.core.exceptions import ValidationError
try:
    from github import Github, GithubException
    from github.Repository import Repository
    from github.PullRequest import PullRequest as GithubPR
    GITHUB_AVAILABLE = True
except ImportError:
    # PyGithub not installed
    Github = None
    GithubException = Exception
    Repository = None
    GithubPR = None
    GITHUB_AVAILABLE = False
from .models import Project, PullRequest

logger = logging.getLogger(__name__)


class GitHubService:
    """Service class for GitHub API interactions."""
    
    def __init__(self):
        """Initialize GitHub service with API token."""
        self.github_token = getattr(settings, 'GITHUB_TOKEN', None)
        self.github = None
        
        if not GITHUB_AVAILABLE:
            logger.warning("PyGithub not installed. GitHub integration will be limited.")
            return
        
        if self.github_token and self.github_token != 'your_github_token_here':
            try:
                self.github = Github(self.github_token)
                # Test the connection
                self.github.get_user().login
                logger.info("GitHub API connection established successfully")
            except Exception as e:
                logger.error(f"Failed to connect to GitHub API: {str(e)}")
                self.github = None
        else:
            logger.warning("GitHub token not configured. GitHub integration will be limited.")
    
    def is_configured(self) -> bool:
        """Check if GitHub API is properly configured."""
        return GITHUB_AVAILABLE and self.github is not None
    
    def parse_github_url(self, url: str) -> Optional[Tuple[str, str]]:
        """
        Parse GitHub URL to extract owner and repository name.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repo_name) or None if invalid
        """
        if not url:
            return None
        
        # Handle different GitHub URL formats
        patterns = [
            r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$',
            r'github\.com/([^/]+)/([^/]+)/.*',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                owner, repo = match.groups()
                # Clean up repo name (remove .git suffix if present)
                repo = repo.rstrip('.git')
                return owner, repo
        
        return None
    
    def validate_repository_url(self, url: str) -> Dict[str, any]:
        """
        Validate GitHub repository URL and fetch basic info.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Dictionary with validation result and repository info
        """
        result = {
            'valid': False,
            'error': None,
            'repo_info': None,
            'accessible': False
        }
        
        # Parse URL
        parsed = self.parse_github_url(url)
        if not parsed:
            result['error'] = 'Invalid GitHub URL format'
            return result
        
        owner, repo_name = parsed
        result['valid'] = True
        
        # If GitHub API is not configured, we can only validate URL format
        if not GITHUB_AVAILABLE:
            result['error'] = 'PyGithub not installed. Repository accessibility cannot be verified.'
            result['repo_info'] = {
                'owner': owner,
                'name': repo_name,
                'full_name': f"{owner}/{repo_name}",
                'url': url,
                'description': 'Repository info unavailable (PyGithub not installed)',
                'private': None,
                'default_branch': 'main'
            }
            return result
        elif not self.is_configured():
            result['error'] = 'GitHub API not configured. Repository accessibility cannot be verified.'
            result['repo_info'] = {
                'owner': owner,
                'name': repo_name,
                'full_name': f"{owner}/{repo_name}",
                'url': url,
                'description': 'Repository info unavailable (API not configured)',
                'private': None,
                'default_branch': 'main'
            }
            return result
        
        # Fetch repository information from GitHub API
        try:
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            result['accessible'] = True
            result['repo_info'] = {
                'owner': repo.owner.login,
                'name': repo.name,
                'full_name': repo.full_name,
                'url': repo.html_url,
                'description': repo.description or 'No description available',
                'private': repo.private,
                'default_branch': repo.default_branch,
                'language': repo.language,
                'stars': repo.stargazers_count,
                'forks': repo.forks_count,
                'created_at': repo.created_at,
                'updated_at': repo.updated_at
            }
            
        except GithubException as e:
            if e.status == 404:
                result['error'] = 'Repository not found or not accessible'
            elif e.status == 403:
                result['error'] = 'Access denied. Check if repository is private and token has proper permissions.'
            else:
                result['error'] = f'GitHub API error: {e.data.get("message", str(e))}'
            
            # Still provide basic info even if API call fails
            result['repo_info'] = {
                'owner': owner,
                'name': repo_name,
                'full_name': f"{owner}/{repo_name}",
                'url': url,
                'description': 'Repository info unavailable',
                'private': None,
                'default_branch': 'main'
            }
        
        except Exception as e:
            result['error'] = f'Unexpected error: {str(e)}'
            logger.error(f"Error validating GitHub repository {owner}/{repo_name}: {str(e)}")
        
        return result
    
    def get_pull_request_info(self, repo_url: str, pr_number: int) -> Dict[str, any]:
        """
        Fetch pull request information from GitHub.
        
        Args:
            repo_url: GitHub repository URL
            pr_number: Pull request number
            
        Returns:
            Dictionary with PR information
        """
        result = {
            'found': False,
            'error': None,
            'pr_info': None
        }
        
        # Parse repository URL
        parsed = self.parse_github_url(repo_url)
        if not parsed:
            result['error'] = 'Invalid GitHub repository URL'
            return result
        
        if not GITHUB_AVAILABLE:
            result['error'] = 'PyGithub not installed'
            return result
        elif not self.is_configured():
            result['error'] = 'GitHub API not configured'
            return result
        
        owner, repo_name = parsed
        
        try:
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            pr = repo.get_pull(pr_number)
            
            result['found'] = True
            result['pr_info'] = {
                'number': pr.number,
                'title': pr.title,
                'body': pr.body or '',
                'state': pr.state,
                'author': pr.user.login,
                'author_avatar': pr.user.avatar_url,
                'created_at': pr.created_at,
                'updated_at': pr.updated_at,
                'merged_at': pr.merged_at,
                'html_url': pr.html_url,
                'diff_url': pr.diff_url,
                'patch_url': pr.patch_url,
                'base_branch': pr.base.ref,
                'head_branch': pr.head.ref,
                'commits': pr.commits,
                'additions': pr.additions,
                'deletions': pr.deletions,
                'changed_files': pr.changed_files,
                'mergeable': pr.mergeable,
                'merged': pr.merged,
                'draft': pr.draft if hasattr(pr, 'draft') else False
            }
            
            # Get file changes
            try:
                files = pr.get_files()
                result['pr_info']['files'] = [
                    {
                        'filename': f.filename,
                        'status': f.status,
                        'additions': f.additions,
                        'deletions': f.deletions,
                        'changes': f.changes,
                        'patch': f.patch[:1000] if f.patch else None  # Limit patch size
                    }
                    for f in files
                ]
            except Exception as e:
                logger.warning(f"Could not fetch PR files: {str(e)}")
                result['pr_info']['files'] = []
            
        except GithubException as e:
            if e.status == 404:
                result['error'] = f'Pull request #{pr_number} not found in repository'
            elif e.status == 403:
                result['error'] = 'Access denied to repository or pull request'
            else:
                result['error'] = f'GitHub API error: {e.data.get("message", str(e))}'
        
        except Exception as e:
            result['error'] = f'Unexpected error: {str(e)}'
            logger.error(f"Error fetching PR {pr_number} from {owner}/{repo_name}: {str(e)}")
        
        return result
    
    def sync_project_repository(self, project: Project) -> Dict[str, any]:
        """
        Sync project with its GitHub repository.
        
        Args:
            project: Project instance to sync
            
        Returns:
            Dictionary with sync results
        """
        result = {
            'success': False,
            'error': None,
            'updated_fields': [],
            'repo_info': None
        }
        
        if not project.repo_url:
            result['error'] = 'No repository URL configured for project'
            return result
        
        # Validate and get repository info
        validation = self.validate_repository_url(project.repo_url)
        
        if not validation['valid']:
            result['error'] = validation['error']
            return result
        
        result['repo_info'] = validation['repo_info']
        
        # Update project description if it's empty and we have repo description
        if validation['accessible'] and validation['repo_info']:
            repo_info = validation['repo_info']
            
            if not project.description and repo_info.get('description'):
                project.description = repo_info['description']
                result['updated_fields'].append('description')
            
            # You could add more sync logic here
            # For example, sync project name, tags, etc.
            
            if result['updated_fields']:
                project.save()
                result['success'] = True
            else:
                result['success'] = True  # No updates needed, but sync was successful
        
        return result
    
    def create_pull_request_from_github(self, project: Project, pr_number: int) -> Tuple[Optional[PullRequest], str]:
        """
        Create a PullRequest instance from GitHub data.
        
        Args:
            project: Project instance
            pr_number: GitHub PR number
            
        Returns:
            Tuple of (PullRequest instance or None, error message)
        """
        if not project.repo_url:
            return None, 'Project has no repository URL configured'
        
        # Check if PR already exists
        existing_pr = PullRequest.objects.filter(
            project=project,
            number=pr_number
        ).first()
        
        if existing_pr:
            return existing_pr, 'Pull request already exists'
        
        # Fetch PR info from GitHub
        pr_info_result = self.get_pull_request_info(project.repo_url, pr_number)
        
        if not pr_info_result['found']:
            return None, pr_info_result['error'] or 'Pull request not found'
        
        pr_info = pr_info_result['pr_info']
        
        try:
            # Create PullRequest instance
            pr = PullRequest.objects.create(
                project=project,
                number=pr_info['number'],
                title=pr_info['title'],
                description=pr_info['body'],
                author=pr_info['author'],
                status='merged' if pr_info['merged'] else ('closed' if pr_info['state'] == 'closed' else 'open'),
                diff_url=pr_info['html_url']  # Use HTML URL as diff URL
            )
            
            return pr, 'Pull request created successfully'
            
        except Exception as e:
            logger.error(f"Error creating PR from GitHub data: {str(e)}")
            return None, f'Error creating pull request: {str(e)}'
    
    def get_repository_pull_requests(self, repo_url: str, state: str = 'all', limit: int = 50) -> Dict[str, any]:
        """
        Get pull requests from a GitHub repository.
        
        Args:
            repo_url: GitHub repository URL
            state: PR state ('open', 'closed', 'all')
            limit: Maximum number of PRs to fetch
            
        Returns:
            Dictionary with PR list and metadata
        """
        result = {
            'success': False,
            'error': None,
            'pull_requests': [],
            'total_count': 0
        }
        
        parsed = self.parse_github_url(repo_url)
        if not parsed:
            result['error'] = 'Invalid GitHub repository URL'
            return result
        
        if not GITHUB_AVAILABLE:
            result['error'] = 'PyGithub not installed'
            return result
        elif not self.is_configured():
            result['error'] = 'GitHub API not configured'
            return result
        
        owner, repo_name = parsed
        
        try:
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            prs = repo.get_pulls(state=state)
            
            pr_list = []
            count = 0
            
            for pr in prs:
                if count >= limit:
                    break
                
                pr_list.append({
                    'number': pr.number,
                    'title': pr.title,
                    'state': pr.state,
                    'author': pr.user.login,
                    'created_at': pr.created_at,
                    'updated_at': pr.updated_at,
                    'html_url': pr.html_url,
                    'merged': pr.merged,
                    'draft': pr.draft if hasattr(pr, 'draft') else False
                })
                count += 1
            
            result['success'] = True
            result['pull_requests'] = pr_list
            result['total_count'] = count
            
        except GithubException as e:
            if e.status == 404:
                result['error'] = 'Repository not found or not accessible'
            elif e.status == 403:
                result['error'] = 'Access denied to repository'
            else:
                result['error'] = f'GitHub API error: {e.data.get("message", str(e))}'
        
        except Exception as e:
            result['error'] = f'Unexpected error: {str(e)}'
            logger.error(f"Error fetching PRs from {owner}/{repo_name}: {str(e)}")
        
        return result


# Utility functions for views and forms

def validate_github_repository_url(url: str) -> None:
    """
    Django form/model validation function for GitHub URLs.
    
    Args:
        url: GitHub repository URL to validate
        
    Raises:
        ValidationError: If URL is invalid or inaccessible
    """
    if not url:
        return  # Allow empty URLs
    
    service = GitHubService()
    result = service.validate_repository_url(url)
    
    if not result['valid']:
        raise ValidationError(f"Invalid GitHub URL: {result['error']}")
    
    if result['error'] and not result['accessible']:
        # Log warning but don't fail validation if API is not configured
        if 'API not configured' not in result['error']:
            raise ValidationError(f"Repository not accessible: {result['error']}")


def get_github_service() -> GitHubService:
    """
    Get a configured GitHub service instance.
    
    Returns:
        GitHubService instance
    """
    return GitHubService()