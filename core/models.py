from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid
from django.utils import timezone
from datetime import timedelta

class User(AbstractUser):
    email = models.EmailField(unique=True)
    
    def __str__(self):
        return self.username

class Team(models.Model):
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_teams')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class Membership(models.Model):
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Developer', 'Developer'),
        ('Viewer', 'Viewer'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'team')
    
    def __str__(self):
        return f"{self.user.username} - {self.team.name} ({self.role})"

class TeamInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]
    
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='invitations')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    invited_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='received_invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Membership.ROLE_CHOICES, default='Developer')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('team', 'email', 'status')
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['email', 'status']),
            models.Index(fields=['expires_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)  # Default 7 days expiration
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"Invitation to {self.email} for {self.team.name} ({self.status})"

class Project(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    repo_url = models.URLField(blank=True, null=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class Epic(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.IntegerField(default=1)
    
    def __str__(self):
        return self.title

class Task(models.Model):
    STATUS_CHOICES = [
        ('backlog', 'Backlog'),
        ('in_progress', 'In Progress'),
        ('review', 'Review'),
        ('done', 'Done'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    epic = models.ForeignKey(Epic, on_delete=models.CASCADE, null=True, blank=True)
    parent_task = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='backlog')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    assignee = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

class PullRequest(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('merged', 'Merged'),
        ('closed', 'Closed'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    number = models.IntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField()
    author = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    diff_url = models.URLField()
    ai_summary = models.TextField(null=True, blank=True)
    risk_flags = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('project', 'number')
    
    def __str__(self):
        return f"PR #{self.number}: {self.title}"

class BuildLog(models.Model):
    STATUS_CHOICES = [
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    pipeline_id = models.CharField(max_length=100)
    commit_sha = models.CharField(max_length=40)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    log_text = models.TextField()
    ai_summary = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Build {self.pipeline_id} - {self.status}"

class ChangelogEntry(models.Model):
    CATEGORY_CHOICES = [
        ('feature', 'Feature'),
        ('fix', 'Fix'),
        ('chore', 'Chore'),
        ('breaking', 'Breaking Change'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    version = models.CharField(max_length=50, null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.category}: {self.title}"

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('general', 'General'),
        ('team_invitation', 'Team Invitation'),
        ('invitation_accepted', 'Invitation Accepted'),
        ('invitation_declined', 'Invitation Declined'),
        ('team_member_added', 'Team Member Added'),
        ('team_role_changed', 'Team Role Changed'),
        ('pr_created', 'Pull Request Created'),
        ('pr_merged', 'Pull Request Merged'),
        ('build_failed', 'Build Failed'),
        ('build_passed', 'Build Passed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, default='general')
    payload = models.JSONField(default=dict)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'read_at']),
            models.Index(fields=['type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Notification for {self.user.username}: {self.type}"

class Comment(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment by {self.author.username}"

# Legacy models for backward compatibility
class Repository(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name

class Commit(models.Model):
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE)
    hash = models.CharField(max_length=40, unique=True)
    message = models.TextField()
    author = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.hash[:8]} - {self.message[:50]}"

class Issue(models.Model):
    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('In Progress', 'In Progress'),
        ('Closed', 'Closed'),
    ]
    
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
