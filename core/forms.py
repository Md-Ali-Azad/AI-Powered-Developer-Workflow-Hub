from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Team, Membership, Project, PullRequest
from .github_service import get_github_service, validate_github_repository_url

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        max_length=30, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class TeamInviteForm(forms.Form):
    """Form for sending team invitations."""
    
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address to invite'
        }),
        help_text="Enter the email address of the person you want to invite to your team."
    )
    
    role = forms.ChoiceField(
        choices=Membership.ROLE_CHOICES,
        initial='Developer',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the role for the invited team member."
    )
    
    def __init__(self, *args, **kwargs):
        self.team = kwargs.pop('team', None)
        super().__init__(*args, **kwargs)
    
    def clean_email(self):
        email = self.cleaned_data['email']
        
        if not self.team:
            raise forms.ValidationError("Team is required for validation.")
        
        # Check if user is already a team member
        try:
            user = User.objects.get(email=email)
            if Membership.objects.filter(user=user, team=self.team).exists():
                raise forms.ValidationError(f"User with email {email} is already a member of this team.")
        except User.DoesNotExist:
            # User doesn't exist yet, which is fine for invitations
            pass
        
        # Check for existing pending invitation
        from .models import TeamInvitation
        existing_invitation = TeamInvitation.objects.filter(
            team=self.team,
            email=email,
            status='pending'
        ).first()
        
        if existing_invitation and not existing_invitation.is_expired():
            raise forms.ValidationError(f"A pending invitation already exists for {email}.")
        
        return email


class ProjectForm(forms.ModelForm):
    """Enhanced form for creating/editing projects with GitHub integration."""
    
    class Meta:
        model = Project
        fields = ['name', 'description', 'repo_url', 'team']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter project name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your project'
            }),
            'repo_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://github.com/username/repository'
            }),
            'team': forms.Select(attrs={'class': 'form-select'})
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter teams to only those the user can manage
        if self.user:
            from .services import TeamPermissions
            user_teams_info = TeamPermissions.filter_user_teams(self.user)
            manageable_teams = [
                team_info['team'] for team_info in user_teams_info 
                if TeamPermissions.has_permission(self.user, team_info['team'], 'manage_projects')
            ]
            self.fields['team'].queryset = Team.objects.filter(id__in=[t.id for t in manageable_teams])
    
    def clean_repo_url(self):
        """Validate GitHub repository URL."""
        repo_url = self.cleaned_data.get('repo_url')
        
        if repo_url:
            try:
                validate_github_repository_url(repo_url)
            except forms.ValidationError as e:
                # Add more user-friendly error messages
                error_msg = str(e)
                if 'API not configured' in error_msg:
                    raise forms.ValidationError(
                        'GitHub API is not configured. The URL format is valid, but repository '
                        'accessibility cannot be verified. Please ensure the repository exists and is accessible.'
                    )
                raise e
        
        return repo_url
    
    def clean(self):
        """Additional form validation."""
        cleaned_data = super().clean()
        repo_url = cleaned_data.get('repo_url')
        
        # If GitHub URL is provided, try to fetch repository info for auto-filling
        if repo_url and not self.errors:
            service = get_github_service()
            if service.is_configured():
                result = service.validate_repository_url(repo_url)
                if result['accessible'] and result['repo_info']:
                    repo_info = result['repo_info']
                    
                    # Auto-fill description if empty
                    if not cleaned_data.get('description') and repo_info.get('description'):
                        cleaned_data['description'] = repo_info['description']
                        self.cleaned_data['description'] = repo_info['description']
        
        return cleaned_data


class PullRequestForm(forms.ModelForm):
    """Enhanced form for creating pull requests with GitHub integration."""
    
    fetch_from_github = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Automatically fetch PR details from GitHub'
    )
    
    class Meta:
        model = PullRequest
        fields = ['number', 'title', 'description', 'author', 'diff_url']
        widgets = {
            'number': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'PR number from GitHub'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Pull request title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Pull request description'
            }),
            'author': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Author username'
            }),
            'diff_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://github.com/username/repo/pull/123'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        
        # Pre-fill author with current user if available
        if hasattr(self, 'initial') and 'request' in kwargs:
            request = kwargs['request']
            if hasattr(request, 'user') and request.user.is_authenticated:
                self.fields['author'].initial = request.user.username
    
    def clean_number(self):
        """Validate PR number and check for duplicates."""
        number = self.cleaned_data.get('number')
        
        if number and self.project:
            # Check if PR already exists in this project
            existing_pr = PullRequest.objects.filter(
                project=self.project,
                number=number
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_pr.exists():
                raise forms.ValidationError(f'Pull request #{number} already exists in this project.')
        
        return number
    
    def clean(self):
        """Enhanced validation with GitHub integration."""
        cleaned_data = super().clean()
        number = cleaned_data.get('number')
        fetch_from_github = cleaned_data.get('fetch_from_github', False)
        
        # If fetch_from_github is enabled and we have a project with repo_url
        if fetch_from_github and number and self.project and self.project.repo_url:
            service = get_github_service()
            
            if service.is_configured():
                pr_info_result = service.get_pull_request_info(self.project.repo_url, number)
                
                if pr_info_result['found']:
                    pr_info = pr_info_result['pr_info']
                    
                    # Auto-fill fields from GitHub
                    if not cleaned_data.get('title'):
                        cleaned_data['title'] = pr_info['title']
                        self.cleaned_data['title'] = pr_info['title']
                    
                    if not cleaned_data.get('description'):
                        cleaned_data['description'] = pr_info['body'] or ''
                        self.cleaned_data['description'] = pr_info['body'] or ''
                    
                    if not cleaned_data.get('author'):
                        cleaned_data['author'] = pr_info['author']
                        self.cleaned_data['author'] = pr_info['author']
                    
                    if not cleaned_data.get('diff_url'):
                        cleaned_data['diff_url'] = pr_info['html_url']
                        self.cleaned_data['diff_url'] = pr_info['html_url']
                    
                    # Set status based on GitHub state
                    if pr_info['merged']:
                        self.instance.status = 'merged'
                    elif pr_info['state'] == 'closed':
                        self.instance.status = 'closed'
                    else:
                        self.instance.status = 'open'
                
                elif pr_info_result['error']:
                    # Add warning but don't fail validation
                    self.add_error('number', f'Could not fetch from GitHub: {pr_info_result["error"]}')
        
        return cleaned_data


class GitHubSyncForm(forms.Form):
    """Form for syncing project with GitHub repository."""
    
    sync_description = forms.BooleanField(
        required=False,
        initial=True,
        label='Update project description from repository',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    import_pull_requests = forms.BooleanField(
        required=False,
        initial=False,
        label='Import recent pull requests',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    pr_limit = forms.IntegerField(
        required=False,
        initial=10,
        min_value=1,
        max_value=50,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '50'
        }),
        help_text='Number of recent PRs to import (max 50)'
    )
    
    pr_state = forms.ChoiceField(
        choices=[
            ('open', 'Open PRs only'),
            ('closed', 'Closed PRs only'),
            ('all', 'All PRs')
        ],
        initial='all',
        widget=forms.Select(attrs={'class': 'form-select'})
    )