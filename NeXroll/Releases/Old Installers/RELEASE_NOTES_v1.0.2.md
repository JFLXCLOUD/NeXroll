# NeXroll v1.0.2 Release Notes

## 🚀 Major Improvements

### ✨ Enhanced Installation Experience

**One-Click PowerShell Installation**
- **New Feature**: One-liner PowerShell installation command:
  ```powershell
  irm https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/install.ps1 | iex
  ```
- **Automated Setup**: Installs Python, FFmpeg, downloads NeXroll, configures Plex, and starts the application
- **User-Friendly**: Interactive prompts with clear instructions and error handling

**Improved Batch Scripts**
- **install_windows.bat**: Complete installation with Plex token setup
- **start_windows.bat**: Enhanced startup with automatic token configuration
- **Better Error Handling**: Clear error messages and troubleshooting guidance

### 🔧 Plex Integration Enhancements

**Windows Registry Support**
- **New Feature**: Automatic detection of Plex tokens from Windows Registry
- **Fallback Methods**: Registry → Preferences.xml → Manual entry
- **Smart Detection**: Checks multiple possible locations for Plex configuration

**Enhanced Token Setup**
- **Interactive Setup**: User-friendly prompts during installation
- **Multiple Methods**: Registry, file-based, and manual token entry
- **Better Diagnostics**: Clear error messages and troubleshooting steps

### 🐛 Bug Fixes

**Static File Serving**
- **Fixed**: 404 errors for CSS and JS files in production builds
- **Root Cause**: Incorrect static file directory paths in backend
- **Solution**: Updated paths to serve from correct `static/css/` and `static/js/` directories

**Installation Process**
- **Fixed**: Batch file execution issues with complex conditional logic
- **Improved**: Error handling and user feedback throughout installation
- **Enhanced**: Virtual environment setup and dependency installation

### 📚 Documentation Updates

**Comprehensive README**
- **Quick Start Section**: Prominent one-liner installation command
- **Installation Options**: PowerShell, manual, and development setups
- **Windows-Focused**: Streamlined for Windows users (Linux/macOS support planned)
- **Clear Instructions**: Step-by-step guidance for all installation methods

### 🛠️ Technical Improvements

**PowerShell Script Quality**
- **PSScriptAnalyzer Compliant**: Fixed all unapproved verb warnings
- **Best Practices**: Proper PowerShell cmdlet naming conventions
- **Error Handling**: Comprehensive try/catch blocks and user feedback

**Code Quality**
- **Registry Integration**: Added Windows Registry access for Plex tokens
- **Path Resolution**: Improved file path detection and validation
- **User Experience**: Better prompts, messages, and error recovery

## 📋 What's New

### For New Users
- **Zero-Configuration Setup**: One command installs everything
- **Automatic Plex Detection**: Finds Plex tokens automatically
- **Guided Installation**: Clear prompts and helpful error messages
- **Desktop Integration**: Automatic shortcut creation

### For Existing Users
- **Seamless Updates**: Improved startup scripts with better error handling
- **Registry Support**: Automatic token detection from Windows Registry
- **Better Diagnostics**: Clear troubleshooting information

## 🔄 Migration Notes

- **No Breaking Changes**: Existing installations continue to work
- **Enhanced Scripts**: Updated batch files provide better user experience
- **Registry Priority**: New installations prefer Registry-based token detection

## 🐛 Issues Resolved

- ✅ 404 errors for CSS/JS files in production
- ✅ Greyed-out "Connect with Stable Token" button
- ✅ Complex installation process for new users
- ✅ Missing Plex token configuration during setup
- ✅ PowerShell script analyzer warnings
- ✅ Poor error handling in installation scripts

