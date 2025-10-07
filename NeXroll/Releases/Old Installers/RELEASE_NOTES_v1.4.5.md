# NeXroll v1.4.5 Release Notes

## Security Updates

### Docker Image Security
- **Updated Base Image**: Changed Docker base image from `python:3.11-slim` to `python:3.13.7-slim` to address security vulnerabilities in the previous Python version.
- **Vulnerability Mitigation**: This update resolves multiple CVEs present in Python 3.11, improving the overall security posture of the Docker container.

## Technical Changes
- Updated Dockerfile to use the latest secure Python base image
- Maintained compatibility with existing functionality while enhancing security

## Installation
Download `NeXroll_Installer_1.4.5.exe` and run as administrator. The installer will guide you through the setup process.

## Checksums
See `CHECKSUMS_v1.4.5.txt` for SHA256 verification of the installer.

## Previous Versions
- [v1.4.4](RELEASE_NOTES_v1.4.4.md) - Video preview feature and bug fixes
- [v1.4.3](RELEASE_NOTES_v1.4.3.md) - Loading indicators for server application operations
- [v1.4.2](RELEASE_NOTES_v1.4.2.md) - Jellyfin integration improvements and selective preroll application
- [v1.4.1](RELEASE_NOTES_v1.4.1.md) - Jellyfin Local Intros plugin integration
- [v1.4.0](RELEASE_NOTES_v1.4.0.md) - Major Jellyfin support release