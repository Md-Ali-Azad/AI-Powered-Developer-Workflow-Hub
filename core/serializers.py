from rest_framework import serializers
from .models import Project, Task, PullRequest, BuildLog, ChangelogEntry, Notification, Epic, Team, User, TeamInvitation, Membership

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class TeamSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Team
        fields = ['id', 'name', 'owner', 'owner_name', 'member_count', 'created_at']
    
    def get_member_count(self, obj):
        return obj.membership_set.count()

class MembershipSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    
    class Meta:
        model = Membership
        fields = ['id', 'user', 'user_name', 'user_email', 'team', 'team_name', 'role', 'created_at']

class TeamInvitationSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    invited_by_name = serializers.CharField(source='invited_by.username', read_only=True)
    invited_user_name = serializers.CharField(source='invited_user.username', read_only=True)
    
    class Meta:
        model = TeamInvitation
        fields = ['id', 'team', 'team_name', 'invited_by', 'invited_by_name', 
                 'invited_user', 'invited_user_name', 'email', 'role', 'status', 
                 'token', 'expires_at', 'created_at']
        read_only_fields = ['token', 'created_at']

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
    formatted_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = ['id', 'user', 'type', 'payload', 'read_at', 'created_at', 'formatted_message']
    
    def get_formatted_message(self, obj):
        """Generate a formatted message based on notification type and payload."""
        payload = obj.payload
        
        if obj.type == 'team_invitation':
            return f"{payload.get('invited_by_name', payload.get('invited_by', 'Someone'))} invited you to join {payload.get('team_name', 'a team')} as {payload.get('role', 'a member')}"
        elif obj.type == 'invitation_accepted':
            return f"{payload.get('accepted_by_name', payload.get('accepted_by', 'Someone'))} accepted your invitation to join {payload.get('team_name', 'the team')}"
        elif obj.type == 'invitation_declined':
            return f"Your invitation to {payload.get('declined_by_email', 'someone')} for {payload.get('team_name', 'the team')} was declined"
        elif obj.type == 'team_member_added':
            return f"{payload.get('new_member_name', payload.get('new_member', 'Someone'))} joined {payload.get('team_name', 'the team')} as {payload.get('role', 'a member')}"
        else:
            return f"New {obj.type.replace('_', ' ')} notification"