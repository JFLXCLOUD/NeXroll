# Production Folder

This folder contains the clean source code and Docker-related files for NeXroll.

## Contents:
- `backend/` - FastAPI backend application
- `frontend/` - React frontend application
- `scripts/` - Python scripts for Windows service, tray app, etc.
- `Dockerfile` - Docker image build configuration
- `docker-compose.yml` - Docker Compose configuration
- `requirements.txt` - Python dependencies
- `version.py` - Version management
- `.dockerignore` - Docker ignore patterns

## Usage:

### For Docker builds:
```bash
docker build -t nexroll:latest .
docker-compose up
```

### For development:
```bash
# Backend
cd backend
python main.py

# Frontend
cd frontend
npm install
npm start
```

### Before creating Windows installer:
1. Build the frontend:
   ```bash
   cd frontend
   npm run build
   ```
2. The build output will be in `frontend/build/` which the installer references
