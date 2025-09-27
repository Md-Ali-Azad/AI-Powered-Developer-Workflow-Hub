# CodeFlow Database Design Documentation

## Overview

CodeFlow is an AI-powered developer workflow hub that manages teams, projects, pull requests, and development activities. The database is designed to support collaborative development workflows with comprehensive tracking and AI-powered insights.

## Database Schema

### Core Entities

#### 1. User Management

**User** (extends Django's AbstractUser)
```
- id: Primary Key
- username: Unique username
- email: Unique email address
- first_name: User's first name
- last_name: User's last name
- password: Encrypted password
- is_active: Account status
- date_joined: Registration timestamp
```

#### 2. Team Management

**Team**
```
- id: Primary Key
- name: Team name (max 200 chars)
- owner: Foreign Key to User (team creator)
- created_at: Timestamp
```

**Membership** (Many-to-Many relationship between User and Team)
```
- id: Primary Key
- user: Foreign Key to User
- team: Foreign Key to Team
- role: Choice field (Admin, Developer, Viewer)
- created_at: Timestamp
- Unique constraint: (user, team)
```

**TeamInvitation**
```
- id: Primary Key
- team: Foreign Key to Team
- invited_by: Foreign Key to User
- invited_user: Foreign Key to User (nullable)
- email: Email address of invitee
- role: Choice field (Admin, Developer, Viewer)
- status: Choice field (pending, accepted, declined, expired)
- token: UUID for invitation link
- expires_at: Expiration timestamp
- created_at: Timestamp
- Unique constraint: (team, email, status)
- Indexes: token, (email, status), expires_at
```

#### 3. Project Management

**Project**
```
- id: Primary Key
- team: Foreign Key to Team
- name: Project name (max 200 chars)
- repo_url: GitHub repository URL (optional)
- description: Text description
- created_at: Timestamp
```

**Epic**
```
- id: Primary Key
- project: Foreign Key to Project
- title: Epic title (max 200 chars)
- description: Text description
- priority: Integer (default 1)
```

**Task**
```
- id: Primary Key
- project: Foreign Key to Project
- epic: Foreign Key to Epic (optional)
- parent_task: Self-referencing Foreign Key (optional)
- title: Task title (max 200 chars)
- description: Text description
- status: Choice field (backlog, in_progress, review, done)
- priority: Choice field (low, medium, high)
- assignee: Foreign Key to User (optional)
- due_date: Date field (optional)
- created_at: Timestamp
```

#### 4. Version Control Integration

**PullRequest**
```
- id: Primary Key
- project: Foreign Key to Project
- number: Integer (PR number)
- title: PR title (max 200 chars)
- description: Text description
- author: String (GitHub username)
- status: Choice field (open, merged, closed)
- diff_url: URL to diff
- ai_summary: AI-generated summary (optional)
- risk_flags: JSON field for risk analysis (optional)
- created_at: Timestamp
- Unique constraint: (project, number)
```

**BuildLog**
```
- id: Primary Key
- project: Foreign Key to Project
- pipeline_id: String (max 100 chars)
- commit_sha: String (40 chars for Git SHA)
- status: Choice field (passed, failed)
- log_text: Text field
- ai_summary: AI-generated summary (optional)
- created_at: Timestamp
```

**ChangelogEntry**
```
- id: Primary Key
- project: Foreign Key to Project
- version: String (max 50 chars, optional)
- category: Choice field (feature, fix, chore, breaking)
- title: Entry title (max 200 chars)
- body: Text description
- created_at: Timestamp
```

#### 5. Communication & Notifications

**Notification**
```
- id: Primary Key
- user: Foreign Key to User
- type: Choice field (general, team_invitation, pr_created, etc.)
- payload: JSON field for notification data
- read_at: Timestamp (nullable)
- created_at: Timestamp
- Indexes: (user, read_at), type, created_at
```

**Comment** (Generic Foreign Key for commenting on any object)
```
- id: Primary Key
- content_type: Foreign Key to ContentType
- object_id: Positive Integer
- content_object: Generic Foreign Key
- author: Foreign Key to User
- body: Text content
- created_at: Timestamp
```

#### 6. Legacy Models (Backward Compatibility)

**Repository**
```
- id: Primary Key
- name: Repository name (max 200 chars)
- url: Repository URL
- project: Foreign Key to Project
```

**Commit**
```
- id: Primary Key
- repo: Foreign Key to Repository
- hash: Commit hash (40 chars, unique)
- message: Commit message
- author: Author name (max 100 chars)
- created_at: Timestamp
```

**Issue**
```
- id: Primary Key
- repo: Foreign Key to Repository
- title: Issue title (max 200 chars)
- description: Text description
- status: Choice field (Open, In Progress, Closed)
- created_at: Timestamp
```

## Database Relationships Diagram

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    User     │    │ Membership  │    │    Team     │
│             │◄──►│             │◄──►│             │
│ - id        │    │ - user_id   │    │ - id        │
│ - username  │    │ - team_id   │    │ - name      │
│ - email     │    │ - role      │    │ - owner_id  │
└─────────────┘    └─────────────┘    └─────────────┘
       │                                      │
       │                                      │
       ▼                                      ▼
┌─────────────┐                      ┌─────────────┐
│TeamInvitation│                     │   Project   │
│             │                      │             │
│ - token     │                      │ - id        │
│ - email     │                      │ - name      │
│ - status    │                      │ - team_id   │
└─────────────┘                      └─────────────┘
                                             │
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
            ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
            │    Epic     │        │    Task     │        │PullRequest  │
            │             │        │             │        │             │
            │ - id        │◄──────►│ - id        │        │ - id        │
            │ - title     │        │ - title     │        │ - number    │
            │ - project_id│        │ - epic_id   │        │ - project_id│
            └─────────────┘        │ - parent_id │        │ - ai_summary│
                                   └─────────────┘        └─────────────┘
                                           │
                                           │
                                           ▼
                                   ┌─────────────┐
                                   │  BuildLog   │
                                   │             │
                                   │ - id        │
                                   │ - project_id│
                                   │ - status    │
                                   └─────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│Notification │    │   Comment   │    │ChangelogEntry│
│             │    │             │    │             │
│ - user_id   │    │ - author_id │    │ - project_id│
│ - type      │    │ - body      │    │ - category  │
│ - payload   │    │ - object_id │    │ - title     │
└─────────────┘    └─────────────┘    └─────────────┘
```

## Key Design Decisions

### 1. Team-Centric Architecture
- All projects belong to teams
- Users join teams through invitations
- Role-based permissions at team level

### 2. Flexible Task Hierarchy
- Tasks can have parent tasks (subtasks)
- Tasks can belong to epics for organization
- Self-referencing relationship allows unlimited nesting

### 3. AI Integration Points
- `ai_summary` fields in PullRequest and BuildLog
- `risk_flags` JSON field for AI risk analysis
- Notification system supports AI-generated alerts

### 4. Generic Comment System
- Uses Django's ContentType framework
- Can attach comments to any model
- Extensible for future entity types

### 5. Invitation System
- Token-based invitations with expiration
- Supports inviting non-users via email
- Tracks invitation lifecycle

### 6. GitHub Integration
- Repository URL validation
- Pull request synchronization
- Build log tracking

## Indexes and Performance

### Critical Indexes
1. **TeamInvitation**: `token`, `(email, status)`, `expires_at`
2. **Notification**: `(user, read_at)`, `type`, `created_at`
3. **Membership**: `(user, team)` - unique constraint serves as index
4. **PullRequest**: `(project, number)` - unique constraint

### Query Optimization
- Foreign key relationships automatically indexed
- Composite indexes for common query patterns
- JSON fields for flexible data storage without schema changes

## Security Considerations

### 1. Access Control
- Team ownership model
- Role-based permissions (Admin, Developer, Viewer)
- Invitation token security with expiration

### 2. Data Validation
- URL validation for repository links
- Email validation for invitations
- Choice field constraints for status fields

### 3. Audit Trail
- `created_at` timestamps on all entities
- Notification system for activity tracking
- Comment system for communication history

## Scalability Features

### 1. Horizontal Scaling
- Stateless design with external session storage
- JSON fields reduce need for schema migrations
- Generic foreign keys for extensibility

### 2. Caching Strategy
- User permissions cacheable by team membership
- Notification counts for real-time updates
- Project statistics for dashboard performance

### 3. Data Archival
- Soft delete patterns for important entities
- Changelog entries for historical tracking
- Build logs with retention policies

## Migration Strategy

### Current State
- All models defined with proper relationships
- Indexes created for performance
- Constraints ensure data integrity

### Future Enhancements
- Add soft delete fields where needed
- Implement data retention policies
- Add audit logging for sensitive operations
- Extend AI integration points

## API Considerations

### REST Endpoints
- Team-based resource scoping
- Permission checks at view level
- Pagination for large datasets
- Filtering and search capabilities

### Real-time Features
- WebSocket support for notifications
- Live updates for pull request status
- Real-time collaboration features

This database design provides a solid foundation for CodeFlow's collaborative development workflow while maintaining flexibility for future AI-powered features and integrations.