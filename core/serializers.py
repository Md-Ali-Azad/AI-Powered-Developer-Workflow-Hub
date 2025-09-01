from rest_framework import serializers
from .models import Project, Task, PullRequest, BuildLog, ChangelogEntry, Notification, Epic, Team, User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'name', 'owner', 'created_at']

class EpicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Epic
        fields = ['id', 'project', 'title', 'description', 'priority']

class ProjectSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    
    class Meta:
        model = Project
        fields = ['id', 'team', 'team_name', 'name', 'repo_url', 'description', 'created_at']

class TaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    assignee_name = serializers.CharField(source='assignee.username', read_only=True)
    epic_title = serializers.CharField(source='epic.title', read_only=True)
    
    class Meta:
        model = Task
        fields = ['id', 'project', 'project_name', 'epic', 'epic_title', 'parent_task', 
                 'title', 'description', 'status', 'priority', 'assignee', 'assignee_name', 
                 'due_date', 'created_at']

class PullRequestSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    class Meta:
        model = PullRequest
        fields = ['id', 'project', 'project_name', 'number', 'title', 'description', 
                 'author', 'status', 'diff_url', 'ai_summary', 'risk_flags', 'created_at']

class BuildLogSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    class Meta:
        model = BuildLog
        fields = ['id', 'project', 'project_name', 'pipeline_id', 'commit_sha', 
                 'status', 'log_text', 'ai_summary', 'created_at']

class ChangelogEntrySerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    class Meta:
        model = ChangelogEntry
        fields = ['id', 'project', 'project_name', 'version', 'category', 
                 'title', 'body', 'created_at']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user', 'type', 'payload', 'read_at', 'created_at']