# AI-Powered-Developer-Workflow-Hub
A one-stop AI-enhanced developer workflow platform that combines task/project management, GitHub integration, AI-assisted code reviews, changelog automation, and collaboration tools.

## 🚀 Features

- **Team Management**: Create teams, invite members, manage roles and permissions
- **Project Management**: Organize projects with team-based access control
- **GitHub Integration**: Connect repositories, validate URLs, import pull requests automatically
- **AI-Powered Analysis**: Gemini AI integration for PR summaries, build log analysis, and task suggestions
- **Pull Request Tracking**: Monitor and analyze pull requests with risk detection
- **Task Management**: Create and track tasks within projects
- **Notifications**: Real-time notifications for team activities
- **Changelog Automation**: AI-generated changelogs from commit history

## 🔧 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd AI-Powered-Developer-Workflow-Hub

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start the server
python manage.py runserver
```

### 2. GitHub Integration Setup (Optional but Recommended)

GitHub integration enables automatic repository validation, PR import, and enhanced project management.

```bash
# Install GitHub integration
pip install PyGithub

# Set up GitHub token
python manage.py setup_github --token YOUR_GITHUB_TOKEN

# Verify setup
python manage.py setup_github --check
```

For detailed GitHub setup instructions, see [GITHUB_INTEGRATION.md](GITHUB_INTEGRATION.md).

### 3. AI Configuration

Set your Gemini API key in the `.env` file:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

## 📖 Documentation

- [GitHub Integration Guide](GITHUB_INTEGRATION.md) - Complete setup and usage guide for GitHub features
- [API Documentation](docs/api.md) - REST API reference (coming soon)
- [Team Management](docs/teams.md) - Team setup and permission management (coming soon)

## 🛠 Technology Stack

- **Backend**: Django 3.2+, Django REST Framework
- **Database**: SQLite (development), PostgreSQL (production ready)
- **AI Integration**: Google Gemini API
- **GitHub Integration**: PyGithub
- **Frontend**: Bootstrap 5, JavaScript
- **Authentication**: Django built-in authentication

## 🔐 Security Features

- Role-based access control (Admin, Developer, Viewer)
- Team-based project isolation
- Secure GitHub token management
- CSRF protection
- Input validation and sanitization

## 🚀 Deployment

The application is ready for deployment on various platforms:

- **Development**: SQLite database included
- **Production**: Configure PostgreSQL or MySQL
- **Environment Variables**: Use `.env` file for configuration
- **Static Files**: Configured for production serving

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- Check the [GitHub Integration Guide](GITHUB_INTEGRATION.md) for setup issues
- Review the troubleshooting section in documentation
- Create an issue for bugs or feature requests
