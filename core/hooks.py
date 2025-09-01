"""
PR Hooks for handling GitHub events and automating workflows
"""
import google.generativeai as genai
import os
from django.utils import timezone
from .models import Project, PullRequest, ChangelogEntry, Notification, User

# Configure Gemini API
from django.conf import settings
genai.configure(api_key=settings.GEMINI_API_KEY)

def handle_new_pr(project_id, pr_number, diff_url, **kwargs):
    """
    Handle new PR creation:
    - Generate AI summary
    - Notify reviewers
    - Check for risk flags
    """
    try:
        project = Project.objects.get(id=project_id)
        
        # Get or create PR record
        pr, created = PullRequest.objects.get_or_create(
            project=project,
            number=pr_number,
            defaults={
                'title': kwargs.get('title', f'PR #{pr_number}'),
                'description': kwargs.get('description', ''),
                'author': kwargs.get('author', 'unknown'),
                'diff_url': diff_url,
                'status': 'open'
            }
        )
        
        # Generate AI summary
        if created or not pr.ai_summary:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            prompt = f"""
            Analyze this Pull Request and provide insights:
            
            Title: {pr.title}
            Description: {pr.description}
            Author: {pr.author}
            Diff URL: {diff_url}
            
            Provide:
            1. Summary of changes (2-3 sentences)
            2. Potential risks or concerns
            3. Suggested reviewers based on changes
            4. Estimated review time
            """
            
            try:
                response = model.generate_content(prompt)
                pr.ai_summary = response.text
                
                # Extract risk flags (simple keyword detection)
                risk_keywords = ['breaking', 'migration', 'database', 'security', 'auth', 'payment']
                risks = []
                content_lower = response.text.lower()
                for keyword in risk_keywords:
                    if keyword in content_lower:
                        risks.append(keyword)
                
                if risks:
                    pr.risk_flags = {'detected_risks': risks, 'confidence': 'medium'}
                
                pr.save()
                
            except Exception as e:
                print(f"Error generating AI summary: {e}")
        
        # Notify team members
        team_members = User.objects.filter(membership__team=project.team)
        for member in team_members:
            Notification.objects.create(
                user=member,
                type='new_pr',
                payload={
                    'project_id': project_id,
                    'pr_number': pr_number,
                    'title': pr.title,
                    'author': pr.author,
                    'url': diff_url
                }
            )
        
        return {'status': 'success', 'pr_id': pr.id}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def handle_merge(project_id, pr_number, commits=None, **kwargs):
    """
    Handle PR merge:
    - Update PR status
    - Create changelog entry
    - Generate release notes
    """
    try:
        project = Project.objects.get(id=project_id)
        pr = PullRequest.objects.get(project=project, number=pr_number)
        
        # Update PR status
        pr.status = 'merged'
        pr.save()
        
        # Generate changelog entry
        if commits:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            commit_messages = '\n'.join([commit.get('message', '') for commit in commits])
            
            prompt = f"""
            Create a changelog entry for this merged PR:
            
            PR Title: {pr.title}
            PR Description: {pr.description}
            Commits:
            {commit_messages}
            
            Categorize as: feature, fix, chore, or breaking
            Provide a user-friendly title and description.
            """
            
            try:
                response = model.generate_content(prompt)
                
                # Simple categorization based on keywords
                category = 'chore'  # default
                response_lower = response.text.lower()
                if any(word in response_lower for word in ['add', 'new', 'feature', 'implement']):
                    category = 'feature'
                elif any(word in response_lower for word in ['fix', 'bug', 'resolve', 'patch']):
                    category = 'fix'
                elif any(word in response_lower for word in ['break', 'breaking', 'major']):
                    category = 'breaking'
                
                ChangelogEntry.objects.create(
                    project=project,
                    category=category,
                    title=pr.title,
                    body=response.text[:500],  # Limit length
                )
                
            except Exception as e:
                print(f"Error generating changelog: {e}")
        
        # Notify team about merge
        team_members = User.objects.filter(membership__team=project.team)
        for member in team_members:
            Notification.objects.create(
                user=member,
                type='pr_merged',
                payload={
                    'project_id': project_id,
                    'pr_number': pr_number,
                    'title': pr.title,
                    'author': pr.author
                }
            )
        
        return {'status': 'success', 'pr_id': pr.id}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def trigger_hook(hook_name, **kwargs):
    """
    Generic hook trigger function
    """
    hooks = {
        'on_new_pr': handle_new_pr,
        'on_merge': handle_merge,
    }
    
    if hook_name in hooks:
        return hooks[hook_name](**kwargs)
    else:
        return {'status': 'error', 'message': f'Unknown hook: {hook_name}'}