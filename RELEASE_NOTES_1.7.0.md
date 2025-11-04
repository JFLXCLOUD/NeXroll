# NeXroll v1.7.0 Release Notes

## Major Release: v1.5.12 → v1.7.0

**Release Date:** November 3, 2025

---

## Major New Features

### 1. **Community Prerolls**
- **Fair Use Integration**: Access thousands of community-curated prerolls from `https://prerolls.typicalnerds.uk/`
- **Smart Search Engine**: Advanced search with synonym expansion (e.g., "turkey" → "thanksgiving")
- **Local Index System**: Unlimited-depth directory scanning with no rate limits
- **Platform Filtering**: Filter by Plex, Jellyfin, or show all
- **Smart Synonyms**: Built-in holiday and theme recognition
- **Random Preroll**: Discover new prerolls with one-click random selection
- **Direct Downloads**: One-click download integration
- **Fair Use Policy**: User acceptance tracking with timestamp

### 2. **Enhanced Plex Connection**
- **Multiple Connection Methods**:
  - Manual URL + Token
  - OAuth via Plex.tv (recommended for Docker)
  - Saved Token Auto-connect
  - Docker Auto-discovery
- **Secure Token Storage**: Windows Credential Manager integration
- **Token Migration**: Automatic migration from legacy plaintext storage
- **Enhanced Status Display**: Shows token source, server info, and detailed error messages
- **Improved Error Handling**: Specific error codes with actionable messages

### 3. **Database Schema Migration**
- **Automatic Migration**: Seamless upgrade from v1.5.12 → v1.7.0
- **Missing Column Detection**: Auto-adds all new columns
- **Migration Logging**: Detailed console output for troubleshooting
- **Schema Validation**: Ensures database compatibility

---

## Improvements & Enhancements

### Backend Improvements
- **Complete Schema Migration**: Added 8 missing columns for v1.5.12 upgrades:
  - `jellyfin_api_key`
  - `community_fair_use_accepted`
  - `community_fair_use_accepted_at`
  - `genre_auto_apply`
  - `genre_priority_mode`
  - `genre_override_ttl_seconds`
  - `dashboard_tile_order`
  - `dashboard_layout`

- **Enhanced Error Messages**: 
  - Detailed error codes: `not_configured`, `missing_token`, `missing_url`, `connection_failed`, `migration_failed`
  - User-friendly error messages with actionable guidance
  - Token source tracking (secure_store vs database)

- **Improved Logging**:
  - Migration status with visual indicators (✓, ⚠, ℹ, ✗)
  - Token migration tracking
  - Connection attempt logging
  - Schema migration completion logs

### Frontend Improvements
- **Plex Status Display**:
  - Shows server URL, token status, token source
  - Displays storage provider (Windows Credential Manager)
  - Shows server name and version
  - Error messages with color-coded alerts

- **Community Prerolls UI**:
  - Modern search interface with 60% width search bar
  - Purple glow effects on focus
  - Platform filter chips
  - Result limit dropdown
  - Improved empty state messaging
  - Better search hints: "Search by theme, holiday, genre, or franchise"

- **GitHub Integration**:
  - Bug report button with pre-filled template
  - Feature request button with template
  - View all issues link
  - Before reporting checklist
  - Auto-populated version info

### Security Improvements
- **Secure Token Storage**: All tokens now stored in Windows Credential Manager
- **No Plaintext Secrets**: Configuration files no longer contain plaintext tokens
- **Migration Safety**: Legacy tokens automatically migrated to secure storage
- **Sanitized Configs**: Config files rewritten without sensitive data

---

## Bug Fixes

### Critical Fixes
1. **Scheduler Crash on Upgrade** (Issue: v1.5.12 users)
   - Fixed: Missing `dashboard_layout` column causing scheduler to crash
   - Added: All missing columns to migration function
   - Impact: Users upgrading from v1.5.12 can now connect to Plex

2. **Token Migration Issues**
   - Fixed: Automatic token migration from plaintext to secure store
   - Fixed: Config file path migration from CWD to system directory
   - Fixed: Silent migration failures

3. **Database Schema Errors**
   - Fixed: `OperationalError` when querying missing columns
   - Fixed: Auto-migration trigger on `/plex/status` endpoint
   - Fixed: Schema validation for all Setting model columns

### Minor Fixes
- Fixed: Plex status showing form input values instead of actual server info
- Fixed: Error messages returning generic "connected: false"
- Fixed: Token source not visible to users
- Improved: Search hint text to reflect actual capabilities

---

## Technical Changes

### API Endpoints Added/Modified
- `/plex/status`: Enhanced with token source tracking and detailed errors
- `/plex/connect`: Improved logging and error handling
- `/plex/auto-connect`: Docker-aware auto-discovery
- `/community/*`: New endpoints for Community Prerolls feature
- `/community/fair-use/*`: Fair Use Policy acceptance tracking

### Database Changes
```sql
-- New columns added to settings table
ALTER TABLE settings ADD COLUMN jellyfin_api_key TEXT;
ALTER TABLE settings ADD COLUMN community_fair_use_accepted BOOLEAN;
ALTER TABLE settings ADD COLUMN community_fair_use_accepted_at DATETIME;
ALTER TABLE settings ADD COLUMN genre_auto_apply BOOLEAN;
ALTER TABLE settings ADD COLUMN genre_priority_mode TEXT;
ALTER TABLE settings ADD COLUMN genre_override_ttl_seconds INTEGER;
ALTER TABLE settings ADD COLUMN dashboard_tile_order TEXT;
ALTER TABLE settings ADD COLUMN dashboard_layout TEXT;
```

### Configuration Changes
- **Token Storage**: Moved from `plex_config.json` to Windows Credential Manager
- **Config Location**: Moved from `./plex_config.json` to `%PROGRAMDATA%/NeXroll/plex_config.json`
- **Sanitized Configs**: Config files now contain metadata only (no secrets)

---

## Installation & Upgrade

### New Installation
1. Download `NeXroll_Installer.exe` (90.92 MB)
2. Run installer as Administrator
3. Launch NeXroll from Start Menu or Desktop shortcut

### Upgrading from v1.5.12+
1. **Automatic Migration**: Your settings and database will be automatically migrated
2. **Token Migration**: Plex tokens will be moved to secure storage
3. **No Manual Steps Required**: Everything happens automatically on first launch

### What to Expect During Upgrade
**Console Output:**
```
>>> UPGRADE DETECTED: Migrating database schema for Plex settings...
>>> SCHEMA MIGRATION: Added settings.dashboard_layout (TEXT)
>>> MIGRATION SUCCESS: Database schema migration completed
>>> UPGRADE STATUS: Plex connection status after migration - connected: true
```

**Logs Location:** `%PROGRAMDATA%\NeXroll\logs\nexroll.log`

---

## Docker Support

### Enhanced Docker Compatibility
- **Plex.tv OAuth**: Recommended connection method for Docker environments
- **Auto-discovery**: Automatic detection of host.docker.internal and gateway addresses
- **Path Mappings**: Full support for container-to-host path translation
- **Environment Variables**: Docker-friendly configuration options

### Docker Compose Example
```yaml
version: '3.8'
services:
  nexroll:
    image: jbrns/nexroll:1.7.0
    container_name: nexroll
    ports:
      - "9393:9393"
    volumes:
      - /mnt/nas/prerolls:/data/prerolls
      - nexroll-data:/app/data
    environment:
      - PLEX_TOKEN=${PLEX_TOKEN}
    restart: unless-stopped

volumes:
  nexroll-data:
```

---

## Known Issues

1. **Genre-based Preroll Mapping**: Still experimental, Windows-only, requires environment variables
2. **Secure Store in Docker**: Not available in containerized environments (use environment variables instead)
3. **Path Mappings**: Requires manual configuration for Docker/NAS setups

---

## Acknowledgments

- **Community Prerolls**: Powered by `prerolls.typicalnerds.uk`
- **Contributors**: Thank you to all users who reported issues and tested features
- **Fair Use Policy**: Respecting content creators and copyright holders

---

## Statistics

- **Version:** 1.7.0
- **Installer Size:** 90.92 MB
- **Build Date:** November 3, 2025
- **Release Branch:** main
- **New Files:** 15+
- **Modified Files:** 20+
- **Lines Changed:** 2000+

---

## Links

- **GitHub Repository**: https://github.com/JFLXCLOUD/NeXroll
- **Issues**: https://github.com/JFLXCLOUD/NeXroll/issues
- **Bug Report Template**: https://github.com/JFLXCLOUD/NeXroll/issues/new?template=bug_report.md
- **Feature Request Template**: https://github.com/JFLXCLOUD/NeXroll/issues/new?template=feature_request.md

---

## Upgrade Priority

**Highly Recommended** for users on v1.5.12 or earlier due to:
- Critical bug fixes for Plex connection
- Security improvements (secure token storage)
- Database schema migration
- New Community Prerolls feature

**Migration Path:**
- v1.5.12 → v1.7.0: Fully supported with automatic migration
- v1.6.x → v1.7.0: Fully supported
- v1.4.x and earlier → v1.7.0: Test in staging environment first

---

## Support

- **Issues**: Submit via GitHub Issues page in Settings tab
- **Diagnostics**: Use "Download Diagnostics" button in Settings
- **Documentation**: Check README.md and inline help

---

**Thank you for using NeXroll!**
