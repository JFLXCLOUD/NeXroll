# NeXroll v1.4.6 Release Notes

## Security Updates

### Runtime Environment Updates
- **Updated Python Base Image**: Changed Docker base image from `python:3.11-slim` to `python:3.13.7-slim` to address security vulnerabilities in the previous Python version.
- **Updated Node.js Version**: Upgraded Node.js from version 20 to 22 in Docker builds for improved security and performance.
- **Updated Python Dependencies**: Updated several Python packages to their latest secure versions:
  - requests: 2.31.0 → 2.32.5
  - plexapi: 4.15.1 → 4.17.1
  - python-multipart: 0.0.6 → 0.0.20
  - jinja2: 3.1.2 → 3.1.6

### GitHub Actions CI/CD
- Updated GitHub Actions workflow to use the secure Python 3.13.7-slim base image
- Updated hardcoded dependency versions in CI pipeline to match current requirements

## Technical Changes
- Enhanced security posture across all runtime environments
- Maintained compatibility with existing functionality while improving security
- Updated CI/CD pipeline to use latest secure base images

## Installation
Download `NeXroll_Installer_1.4.6.exe` and run as administrator. The installer will guide you through the setup process.

## Checksums
See `CHECKSUMS_v1.4.6.txt` for SHA256 verification of the installer.

## Previous Versions
- [v1.4.5](RELEASE_NOTES_v1.4.5.md) - Docker image security update
- [v1.4.4](RELEASE_NOTES_v1.4.4.md) - Video preview feature and bug fixes
- [v1.4.3](RELEASE_NOTES_v1.4.3.md) - Loading indicators for server application operations
- [v1.4.2](RELEASE_NOTES_v1.4.2.md) - Jellyfin integration improvements and selective preroll application
- [v1.4.1](RELEASE_NOTES_v1.4.1.md) - Jellyfin Local Intros plugin integration
- [v1.4.0](RELEASE_NOTES_v1.4.0.md) - Major Jellyfin support release