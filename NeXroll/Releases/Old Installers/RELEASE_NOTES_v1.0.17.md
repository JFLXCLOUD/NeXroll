# NeXroll v1.0.17 Release Notes

## 🚀 Major Features & Enhancements

### 🔐 Secure Token Storage
- **Windows Credential Manager Integration**: Replaced plaintext `plex_config.json` with secure Windows Credential Manager storage
- **DPAPI Fallback**: Automatic fallback to Windows Data Protection API for environments without Credential Manager
- **Migration Support**: Automatic migration of existing plaintext tokens to secure storage
- **Cross-Platform Ready**: Extensible design for future Linux/macOS secure storage implementations

### 🩺 Diagnostics & Troubleshooting
- **Comprehensive Diagnostics Bundle**: New `/diagnostics/bundle` endpoint creates downloadable ZIP with:
  - System information and environment details
  - Database schema dump (SQLite introspection)
  - Application logs (app.log, service.log)
  - Sanitized configuration (tokens removed)
- **Enhanced System Introspection**: New endpoints for FFmpeg info, version info, and path resolution
- **Better Error Handling**: Improved error reporting and logging throughout the application

### 📡 Real-Time Updates
- **Server-Sent Events (SSE)**: New `/events` endpoint for live scheduler status streaming
- **Live Dashboard Updates**: Frontend automatically updates scheduler status without polling
- **Background Sync**: Service worker supports background synchronization when connection restored

### 🕐 Time Zone Correctness
- **UTC Storage**: All datetime values now stored as UTC in database
- **ISO-8601 API Responses**: All API responses return timestamps in ISO-8601 UTC format (ending with 'Z')
- **Local Display Conversion**: Frontend converts UTC timestamps to local time for display
- **Consistent Scheduling**: Scheduler operations use UTC internally for reliable cross-timezone behavior

### 📱 Progressive Web App (PWA)
- **Offline Functionality**: Service worker caches critical resources for offline access
- **Install Prompt**: Smart PWA install banner with native browser prompts
- **Enhanced Manifest**: Improved PWA manifest with better icons, descriptions, and categories
- **Cache Strategy**: Intelligent caching of API responses and static assets
- **Background Sync**: Automatic cache refresh when connection restored

### 📅 Calendar View Enhancement
- **Month/Year Visualization**: Interactive calendar showing schedule date blocks
- **Category Color Coding**: Visual distinction between different category schedules
- **Legend & Controls**: Calendar legend and range controls for better navigation
- **Responsive Design**: Calendar adapts to different screen sizes

### 🏗️ Architecture Improvements
- **Backend Consolidation**: Removed duplicate backend directories, consolidated to `nexroll_backend/`
- **Documentation Updates**: Updated README, PACKAGING.md, and release notes to reflect correct paths
- **Import Path Cleanup**: Standardized all backend imports to use `nexroll_backend` package

## 🔧 Technical Improvements

### Backend (FastAPI)
- **Secure Store Module**: New `secure_store.py` with Windows Credential Manager and DPAPI support
- **Enhanced Plex Connector**: Updated to use secure token storage with legacy migration
- **Time Zone Helpers**: Centralized UTC conversion utilities
- **Better Error Responses**: Consistent error handling and status codes
- **Schema Migrations**: Automatic database schema upgrades for new columns

### Frontend (React)
- **PWA Integration**: Service worker registration and install prompts
- **Time Zone Conversion**: Client-side UTC to local time conversion helpers
- **Calendar Component**: Full month/year calendar with schedule visualization
- **Real-time SSE**: EventSource integration for live updates
- **Enhanced Error Handling**: Better error boundaries and user feedback

### Database
- **UTC Timestamps**: All datetime fields now consistently use UTC
- **Schema Introspection**: New columns for secure token metadata
- **Migration Safety**: Backward-compatible schema changes

## 🐛 Bug Fixes
- **Thumbnail Path Normalization**: Fixed legacy thumbnail path issues
- **Calendar JSX**: Resolved HTML entity encoding issues in calendar component
- **Service Worker Caching**: Improved cache invalidation and update handling
- **Time Display**: Fixed inconsistent time formatting across components

## 📦 Packaging & Distribution
- **Updated Spec Files**: PyInstaller specs now correctly reference `nexroll_backend`
- **Build Process**: Streamlined build process with consolidated backend paths
- **Dependency Management**: Updated requirements and build dependencies

## 🧪 Testing & Quality
- **Integration Tests**: New `test_integration.py` script for end-to-end testing
- **API Validation**: Tests for new endpoints, time formats, and PWA functionality
- **Cross-Platform Testing**: Validation of secure storage across different environments

## 📚 Documentation
- **README Updates**: Corrected all backend path references
- **PACKAGING.md**: Updated build instructions and paths
- **API Documentation**: Enhanced endpoint documentation with examples
- **Troubleshooting Guide**: Added diagnostics bundle usage instructions

## 🔄 Migration Notes
- **Automatic Token Migration**: Existing `plex_config.json` tokens automatically migrated to secure storage
- **Database Schema**: Automatic schema upgrades handle new UTC timestamp requirements
- **Backward Compatibility**: All existing functionality preserved with improved security

## 🎯 Known Issues & Future Work
- **Linux/macOS Secure Storage**: Platform-specific secure storage implementations planned
- **Advanced Calendar Features**: Month/week view switching and schedule conflict detection
- **Push Notifications**: Browser push notifications for schedule events
- **Offline Queue**: Background sync for offline-scheduled operations

## 🙏 Acknowledgments
- Thanks to the Plex community for feedback and testing
- Special thanks to contributors who helped identify security and usability improvements
- PWA implementation inspired by modern web app best practices

---

**Installation**: Download `NeXroll_Installer_1.0.17.exe` from the [releases page](https://github.com/JFLXCLOUD/NeXroll/releases).

**Upgrade Notes**: This version includes automatic migration of existing tokens to secure storage. No manual intervention required.

**Support**: For issues or questions, please use [GitHub Issues](https://github.com/JFLXCLOUD/NeXroll/issues) or [Discussions](https://github.com/JFLXCLOUD/NeXroll/discussions).