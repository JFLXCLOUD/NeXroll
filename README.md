# NeXroll - Plex Preroll Management System

<div align="center">
  <img src="frontend/NeXroll_Logo_WHT.png" alt="NeXroll Logo" width="200"/>
  <br>
  <p><strong>A comprehensive Plex preroll management system with web interface</strong></p>
  <p>
    <a href="#features">Features</a> •
    <a href="#installation">Installation</a> •
    <a href="#usage">Usage</a> •
    <a href="#configuration">Configuration</a> •
    <a href="#development">Development</a> •
    <a href="#contributing">Contributing</a>
  </p>
</div>

---

## 📋 Table of Contents

- [About](#-about)
- [Features](#-features)
- [Installation](#-installation)
- [Usage](#-usage)
- [Configuration](#-configuration)
- [Development](#-development)
- [Project Structure](#-project-structure)
- [API Documentation](#-api-documentation)
- [Contributing](#-contributing)
- [License](#-license)
- [Support](#-support)

## 🎯 About

NeXroll is a powerful, user-friendly application designed to manage preroll videos for Plex Media Server. It provides a modern web interface for uploading, organizing, and scheduling preroll content, with seamless integration with Plex's preroll system.

The application consists of:
- **Backend**: FastAPI-based REST API server
- **Frontend**: Modern React-based web interface
- **Database**: SQLite database for data persistence
- **Scheduler**: Automated preroll scheduling system

## ✨ Features

### 🎬 Preroll Management
- **Upload & Organize**: Upload multiple preroll videos with metadata
- **Category System**: Organize prerolls by categories (Default, Halloween, Christmas, etc.)
- **Thumbnail Generation**: Automatic thumbnail generation for uploaded videos
- **Tag System**: Add tags for better organization and filtering
- **Bulk Operations**: Upload multiple files simultaneously

### ⏰ Scheduling System
- **Flexible Scheduling**: Create schedules with various recurrence patterns
- **Holiday Presets**: Built-in holiday-themed scheduling presets
- **Priority System**: Set fallback categories for when no schedule is active
- **Real-time Status**: Monitor scheduler status and active schedules

### 🔗 Plex Integration
- **Seamless Connection**: Connect to Plex Media Server via URL and token
- **Stable Token Support**: Use stable tokens for persistent authentication
- **Category Sync**: Apply entire categories to Plex as preroll sequences
- **Status Monitoring**: Real-time connection status and server information

### 🎨 User Interface
- **Modern Design**: Clean, responsive React-based interface
- **Dark/Light Mode**: Toggle between themes
- **Intuitive Navigation**: Tabbed interface for easy access to features
- **Real-time Updates**: Live status updates and progress indicators

### 🔧 Advanced Features
- **Backup & Restore**: Database and file backup/restore functionality
- **Community Templates**: Share and import schedule templates
- **API Access**: RESTful API for programmatic access
- **Cross-Platform**: Works on Windows, Linux, and macOS

## 🚀 Installation

### Option 1: Pre-built Release (Recommended)

1. **Download** the latest release from [GitHub Releases](https://github.com/JFLXCLOUD/NeXroll/releases)
2. **Extract** the zip file to your desired location
3. **Run** the installation script:
   - Windows: Launch `install_windows.bat`, then run `start_windows.bat`
4. **Open** your browser to `http://localhost:9393`

### Option 2: Development Setup

#### Prerequisites
- Python 3.8+
- Node.js 16+
- FFmpeg (for video processing)
- Git

#### Backend Setup
```bash
# Clone the repository
git clone https://github.com/JFLXCLOUD/NeXroll.git
cd NeXroll

# Set up Python virtual environment
cd backend
python -m venv venv
venv\Scripts\activate  # On Windows
# source venv/bin/activate  # On Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

#### Frontend Setup
```bash
# In a new terminal
cd frontend
npm install
```

#### Database Setup
```bash
# Initialize the database (from backend directory)
python -c "from database import engine; from models import Base; Base.metadata.create_all(bind=engine)"
```

## 💻 Usage

### Starting the Application

#### Development Mode
```bash
# Backend (Terminal 1)
cd backend
venv\Scripts\activate
uvicorn main:app --reload --port 9393

# Frontend (Terminal 2)
cd frontend
npm start
```

#### Production Mode
```bash
# Build frontend
cd frontend
npm run build

# Start backend
cd backend
venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 9393
```

### Basic Workflow

1. **Connect to Plex**
   - Navigate to the "Plex" tab
   - Enter your Plex server URL and authentication token
   - Or use the stable token method for persistent authentication

2. **Upload Prerolls**
   - Go to the "Dashboard" tab
   - Select video files to upload
   - Add tags, select category, and provide description
   - Click "Upload" to process files

3. **Create Categories**
   - Use the "Categories" tab to organize your prerolls
   - Create custom categories or use built-in holiday presets

4. **Set Up Schedules**
   - Navigate to the "Schedules" tab
   - Create new schedules with date/time ranges
   - Choose categories and scheduling options
   - Enable/disable schedules as needed

5. **Apply to Plex**
   - Select a category in the "Categories" tab
   - Click "Apply to Plex" to sync with your Plex server
   - Monitor the connection status

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
# Database
DATABASE_URL=sqlite:///./nexroll.db

# Server
HOST=0.0.0.0
PORT=9393

# Plex (optional - can be configured via UI)
PLEX_URL=http://your-plex-server:32400
PLEX_TOKEN=your-plex-token
```

### Plex Configuration

#### Method 1: Manual Token
1. Open Plex Web at `http://localhost:32400/web`
2. Sign in and go to Settings → General → Advanced
3. Copy the "Authentication Token"
4. Enter URL and token in NeXroll's Plex configuration

#### Method 2: Stable Token (Recommended)
1. Run the setup script: `python setup_plex_token.py`
2. Follow the prompts to configure your stable token
3. Use the stable token connection method in NeXroll

## 🛠️ Development

### Project Structure

```
NeXroll/
├── backend/                 # FastAPI backend
│   ├── main.py             # Main application file
│   ├── models.py           # Database models
│   ├── database.py         # Database configuration
│   ├── plex_connector.py   # Plex integration
│   ├── scheduler.py        # Scheduling system
│   └── data/               # Application data
├── frontend/                # React frontend
│   ├── src/
│   │   ├── App.js          # Main React component
│   │   ├── App.css         # Styles
│   │   └── ...
│   └── public/             # Static assets
└── README.md               # This file
```

### Running Tests

```bash
# Backend tests
cd backend
python -m pytest

# Frontend tests
cd frontend
npm test
```

### Building for Production

```bash
# Build backend executable
python build_backend.py

# Build frontend
cd frontend
npm run build

# Create release package
python create_release.py
```

## 📁 Project Structure

### Backend Components

- **`main.py`**: FastAPI application with all endpoints
- **`models.py`**: SQLAlchemy models for database tables
- **`database.py`**: Database connection and session management
- **`plex_connector.py`**: Plex Media Server integration
- **`scheduler.py`**: Background job scheduling system

### Frontend Components

- **`App.js`**: Main React application component
- **`Dashboard`**: Preroll upload and management
- **`Schedules`**: Schedule creation and management
- **`Categories`**: Category organization and Plex sync
- **`Settings`**: Application configuration and utilities

### Database Schema

- **Prerolls**: Video files with metadata
- **Categories**: Organizational groupings
- **Schedules**: Automated playback schedules
- **Holiday Presets**: Pre-configured holiday schedules
- **Settings**: Application configuration
- **Community Templates**: Shareable schedule templates

## 📚 API Documentation

The backend provides a comprehensive REST API:

### Core Endpoints

- `GET /` - Health check
- `POST /plex/connect` - Connect to Plex server
- `POST /prerolls/upload` - Upload preroll videos
- `GET /prerolls` - List prerolls with filtering
- `POST /schedules` - Create schedules
- `GET /schedules` - List schedules
- `POST /categories` - Create categories
- `GET /categories` - List categories

### Advanced Endpoints

- `POST /plex/connect/stable-token` - Connect with stable token
- `POST /categories/{id}/apply-to-plex` - Sync category to Plex
- `POST /scheduler/start` - Start scheduler
- `GET /scheduler/status` - Get scheduler status
- `GET /backup/database` - Export database
- `POST /restore/database` - Import database

For detailed API documentation, see the interactive API docs at `http://localhost:9393/docs` when the server is running.

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/your-feature`
3. **Commit** your changes: `git commit -m 'Add your feature'`
4. **Push** to the branch: `git push origin feature/your-feature`
5. **Create** a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Use ESLint configuration for JavaScript/React
- Write tests for new features
- Update documentation for API changes
- Ensure cross-platform compatibility

### Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Include detailed steps to reproduce
- Provide system information and error logs
- Suggest potential solutions when possible

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Getting Help

- **Documentation**: Check this README and inline code comments
- **Issues**: [GitHub Issues](https://github.com/JFLXCLOUD/NeXroll/issues)
- **Discussions**: [GitHub Discussions](https://github.com/JFLXCLOUD/NeXroll/discussions)

### Support the Project

If you find NeXroll helpful, consider supporting the development:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Me-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/j_b__)


**Plex Connection Issues**:
- Ensure Plex server is running and accessible
- Verify authentication token is valid
- Check firewall settings allow connections

**Video Processing Errors**:
- Install FFmpeg for video thumbnail generation
- Ensure uploaded files are valid video formats
- Check file permissions for upload directories

---

<div align="center">
  <p><strong>Built with ❤️ for the Plex community</strong></p>
  <p>
    <a href="https://github.com/JFLXCLOUD/NeXroll">GitHub</a> •
    <a href="https://github.com/JFLXCLOUD/NeXroll/releases">Releases</a> •
    <a href="https://github.com/JFLXCLOUD/NeXroll/issues">Issues</a>
  </p>

</div>
