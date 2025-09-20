# GitHub Integration Guide

This guide explains how to set up and use GitHub integration in CodeFlow.

## Overview

CodeFlow's GitHub integration provides:
- **Repository Validation**: Verify GitHub URLs and check accessibility
- **Automatic Data Sync**: Import repository descriptions and metadata
- **Pull Request Import**: Fetch PR details directly from GitHub
- **Real-time Updates**: Get live data from your repositories
- **Enhanced Project Management**: Link projects to repositories seamlessly

## Setup Instructions

### 1. Install Dependencies

First, install the required Python package:

```bash
pip install PyGithub
```

### 2. Create GitHub Personal Access Token

1. Go to [GitHub Settings > Personal Access Tokens](https://github.com/settings/tokens)
2. Click **"Generate new token"** > **"Generate new token (classic)"**
3. Give it a descriptive name like "CodeFlow Integration"
4. Set expiration as needed (recommended: 90 days or no expiration for development)
5. Select the following scopes:
   - `repo` - Full control of private repositories
   - `public_repo` - Access to public repositories
   - `read:org` - Read organization membership (if needed)
6. Click **"Generate token"** and copy the token immediately

### 3. Configure the Token

#### Option A: Using Management Command (Recommended)
```bash
python manage.py setup_github --token YOUR_TOKEN_HERE
```

#### Option B: Manual Configuration
Add to your `.env` file:
```env
GITHUB_TOKEN=your_github_token_here
```

### 4. Verify Setup

Check your configuration:
```bash
python manage.py setup_github --check
```

### 5. Restart Django Server

After setting the token, restart your Django development server:
```bash
python manage.py runserver
```

## Features

### Project Creation with GitHub Integration

When creating a project:
1. Enter your GitHub repository URL (e.g., `https://github.com/username/repository`)
2. Click **"Validate"** to check repository accessibility
3. If accessible, the project description will be auto-filled from the repository
4. Repository information will be displayed in the project

### Pull Request Management

#### Creating Pull Requests
1. Navigate to your project
2. Click **"New Pull Request"**
3. Enter the PR number from GitHub
4. Enable **"Automatically fetch PR details from GitHub"**
5. The form will auto-populate with:
   - PR title
   - Description
   - Author
   - Status (open/closed/merged)

#### Importing Existing Pull Requests
1. Go to your project detail page
2. Click **"GitHub Sync"**
3. Configure import options:
   - Choose PR state (open, closed, or all)
   - Set import limit (1-50 PRs)
4. Click **"Start Sync"** to import PRs

### GitHub Sync Features

Access GitHub sync from the project detail page:

#### Repository Information
- View repository statistics (stars, forks, language)
- See creation and last update dates
- Check repository visibility (public/private)

#### Sync Options
- **Project Sync**: Update project description from repository
- **Pull Request Import**: Bulk import recent PRs
- **Single PR Import**: Import specific PRs by number

### API Endpoints

The integration provides several API endpoints:

#### Validate Repository
```http
POST /api/github/validate-repo/
Content-Type: application/json

{
    "repo_url": "https://github.com/username/repository"
}
```

#### Fetch Pull Request
```http
POST /api/github/fetch-pr/
Content-Type: application/json

{
    "repo_url": "https://github.com/username/repository",
    "pr_number": 123
}
```

#### Import Pull Request
```http
POST /api/github/import-pr/
Content-Type: application/json

{
    "project_id": 1,
    "pr_number": 123
}
```

## Troubleshooting

### Common Issues

#### "GitHub API not configured" Error
- Ensure `GITHUB_TOKEN` is set in your `.env` file
- Restart the Django server after setting the token
- Run `python manage.py setup_github --check` to verify

#### "Repository not found or not accessible" Error
- Check if the repository URL is correct
- Verify the repository exists and is accessible
- For private repositories, ensure your token has `repo` scope
- For organization repositories, you may need `read:org` scope

#### "Access denied" Error
- Your token may not have sufficient permissions
- For private repos, ensure `repo` scope is enabled
- For organization repos, check if you have access to the organization

#### Rate Limiting
- GitHub API has rate limits (5000 requests/hour for authenticated users)
- The integration handles rate limiting gracefully
- If you hit limits frequently, consider caching or reducing API calls

### Token Security

**Important Security Practices:**

1. **Never commit tokens to version control**
   - Add `.env` to your `.gitignore` file
   - Use environment variables in production

2. **Use minimal required permissions**
   - Only enable scopes you actually need
   - Regularly review and rotate tokens

3. **Monitor token usage**
   - Check GitHub's token usage in settings
   - Revoke unused or compromised tokens

4. **Production deployment**
   - Use environment variables instead of `.env` files
   - Consider using GitHub Apps for organization-wide access

### Debugging

Enable debug logging by adding to your Django settings:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'core.github_service': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

## Limitations

### Current Limitations
- Only supports GitHub (not GitLab, Bitbucket, etc.)
- No webhook support for real-time updates
- Limited to 50 PRs per import operation
- No support for GitHub Enterprise Server

### Planned Features
- Webhook integration for real-time updates
- Support for GitHub Enterprise
- Automated changelog generation from commits
- Issue tracking integration
- Branch and commit monitoring

## FAQ

**Q: Do I need a GitHub account to use CodeFlow?**
A: No, GitHub integration is optional. You can use CodeFlow without it, but you'll miss out on automatic repository sync features.

**Q: Can I use this with private repositories?**
A: Yes, ensure your token has the `repo` scope for private repository access.

**Q: What happens if my token expires?**
A: GitHub integration will stop working. You'll need to generate a new token and update your configuration.

**Q: Can multiple users share the same token?**
A: While possible, it's not recommended. Each user should have their own token for better security and rate limit management.

**Q: Does this work with GitHub Enterprise?**
A: Currently, only GitHub.com is supported. GitHub Enterprise support is planned for future releases.

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Run the configuration check: `python manage.py setup_github --check`
3. Check Django logs for error messages
4. Verify your GitHub token permissions and expiration

For additional help, please refer to the main project documentation or create an issue in the project repository.