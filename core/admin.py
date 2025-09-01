from django.contrib import admin
from .models import (User, Team, Membership, TeamInvitation, Project, Epic, Task, Repository, 
                    PullRequest, Commit, Issue, Notification, BuildLog, 
                    ChangelogEntry, Comment)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active')
    search_fields = ('username', 'email')

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'created_at')
    search_fields = ('name',)

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'team', 'role', 'created_at')
    list_filter = ('role',)

@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'team', 'invited_by', 'role', 'status', 'expires_at', 'created_at')
    list_filter = ('status', 'role', 'team')
    search_fields = ('email', 'team__name', 'invited_by__username')
    readonly_fields = ('token', 'created_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('team', 'invited_by', 'invited_user')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'created_at')
    list_filter = ('team',)
    search_fields = ('name',)

@admin.register(Epic)
class EpicAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'priority')
    list_filter = ('project', 'priority')
    search_fields = ('title',)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'epic', 'assignee', 'status', 'priority', 'due_date')
    list_filter = ('status', 'priority', 'project')
    search_fields = ('title',)

@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'url')
    search_fields = ('name',)

@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    list_display = ('number', 'title', 'project', 'author', 'status', 'created_at')
    list_filter = ('status', 'project')
    search_fields = ('title', 'author')

@admin.register(BuildLog)
class BuildLogAdmin(admin.ModelAdmin):
    list_display = ('pipeline_id', 'project', 'status', 'commit_sha', 'created_at')
    list_filter = ('status', 'project')
    search_fields = ('pipeline_id', 'commit_sha')

@admin.register(ChangelogEntry)
class ChangelogEntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'category', 'version', 'created_at')
    list_filter = ('category', 'project')
    search_fields = ('title', 'version')

@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    list_display = ('hash', 'repo', 'author', 'created_at')
    search_fields = ('hash', 'author')

@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ('title', 'repo', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('title',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'read_at', 'created_at')
    list_filter = ('type', 'read_at')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'content_type', 'object_id', 'created_at')
    list_filter = ('content_type', 'created_at')
