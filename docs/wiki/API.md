# API Documentation

NeXroll provides a REST API for programmatic control of prerolls, categories, schedules, sequences, and more.

## Base URL

```
http://localhost:9393
```

Replace with your server's address if running remotely.

## Authentication

NeXroll supports two authentication methods:

### Session Authentication (Web UI)

Used by the web interface. After logging in via `/auth/login`, a session cookie is set and included in subsequent requests.

### API Key Authentication (External Access)

For programmatic access, use API keys with the `/external/*` endpoints:

```http
Authorization: Bearer nx_your_api_key_here
```

Or as a query parameter:
```http
GET /external/status?api_key=nx_your_api_key_here
```

API keys are generated in **Settings → API Keys**. Keys can be scoped as **read-only** or **full access** and can have expiration dates.

### When Authentication is Disabled

If authentication is not enabled in Settings, all internal API endpoints are accessible without credentials. External API endpoints always require a valid API key.

---

## External API Endpoints

These endpoints are designed for external integrations and require an API key.

### System Status

```http
GET /external/status
```

Returns system status, connection info, and version.

### List Prerolls

```http
GET /external/prerolls
```

Returns all registered prerolls.

### List Schedules

```http
GET /external/schedules
```

Returns all schedules.

### Active Schedules

```http
GET /external/active-schedules
```

Returns detailed info on currently active schedules.

### Now Showing

```http
GET /external/now-showing
```

Returns the current active category, preroll string, and active schedules.

### List Categories

```http
GET /external/categories
```

Returns all categories with preroll counts.

### Coming Soon

```http
GET /external/coming-soon?source=both&limit=10
```

Returns upcoming movies/TV from NeX-Up.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `source` | `movies`, `shows`, or `both` | `both` |
| `limit` | Max items to return | 10 |

### List Sequences

```http
GET /external/sequences
```

Returns all saved sequences.

### Sync Plex

```http
POST /external/sync-plex
```

Triggers a Plex sync. Requires **full access** API key.

### Create Category

```http
POST /external/categories
Content-Type: application/json

{
  "name": "My Category",
  "description": "Optional description"
}
```

Requires **full access** API key.

### Register Preroll

```http
POST /external/prerolls/register
Content-Type: application/json

{
  "file_path": "/path/to/video.mp4",
  "display_name": "My Preroll",
  "category_id": 1
}
```

Registers an existing video file as a preroll. Requires **full access** API key.

### Assign Preroll to Category

```http
POST /external/prerolls/{preroll_id}/assign-category/{category_id}
```

Requires **full access** API key.

### Create Schedule

```http
POST /external/schedules
Content-Type: application/json

{
  "name": "My Schedule",
  "category_id": 1,
  "start_date": "2025-12-01",
  "end_date": "2025-12-25",
  "exclusive": true,
  "enabled": true
}
```

Requires **full access** API key.

### Delete Schedule

```http
DELETE /external/schedules/{id}
```

Requires **full access** API key.

### Toggle Schedule

```http
PUT /external/schedules/{id}/toggle
```

Enable or disable a schedule. Requires **full access** API key.

### Apply Category

```http
POST /external/apply-category/{category_id}
```

Immediately applies a category to Plex. Requires **full access** API key.

---

## Categories

### List Categories

```http
GET /categories
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Christmas",
    "description": "Holiday prerolls",
    "plex_mode": "shuffle",
    "preroll_count": 5
  }
]
```

### Create Category

```http
POST /categories
Content-Type: application/json

{
  "name": "Halloween",
  "description": "Spooky prerolls"
}
```

### Update Category

```http
PUT /categories/{id}
Content-Type: application/json

{
  "name": "Halloween 2025",
  "description": "Updated description"
}
```

### Delete Category

```http
DELETE /categories/{id}
```

### Apply Category to Plex

```http
POST /categories/{id}/apply-to-plex
```

Immediately applies the category's prerolls to Plex.

### Get Category Prerolls

```http
GET /categories/{id}/prerolls
```

Returns all prerolls assigned to a category.

---

## Prerolls

### List Prerolls

```http
GET /prerolls
```

**Response:**
```json
[
  {
    "id": 1,
    "filename": "christmas_intro.mp4",
    "display_name": "Christmas Intro",
    "full_path": "/prerolls/christmas_intro.mp4",
    "category_id": 1,
    "tags": ["holiday", "winter"],
    "duration": 15.5,
    "file_size": 25000000
  }
]
```

### Upload Preroll

```http
POST /prerolls/upload
Content-Type: multipart/form-data

file: [binary]
category_id: 1
tags: "holiday,winter"
description: "My preroll"
```

**Limits**: Maximum file size 500MB. Allowed extensions: `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.ts`, `.mpg`, `.mpeg`.

### Update Preroll

```http
PUT /prerolls/{id}
Content-Type: application/json

{
  "display_name": "New Name",
  "category_id": 2,
  "tags": ["updated", "tags"]
}
```

### Delete Preroll

```http
DELETE /prerolls/{id}
```

### Check Duplicate

```http
POST /prerolls/check-duplicate
Content-Type: multipart/form-data

file: [binary]
```

Returns whether a file with the same hash already exists.

---

## Schedules

### List Schedules

```http
GET /schedules
```

### Create Schedule

```http
POST /schedules
Content-Type: application/json

{
  "name": "Christmas 2025",
  "category_id": 1,
  "start_date": "2025-12-01",
  "end_date": "2025-12-25",
  "exclusive": true,
  "enabled": true
}
```

### Update Schedule

```http
PUT /schedules/{id}
Content-Type: application/json

{
  "name": "Christmas 2025 Updated",
  "enabled": false
}
```

### Delete Schedule

```http
DELETE /schedules/{id}
```

### Get Active Schedules

```http
GET /schedules/active
```

Returns schedules currently active based on date/time.

---

## Sequences

### List Sequences

```http
GET /sequences
```

### Create Sequence

```http
POST /sequences
Content-Type: application/json

{
  "name": "My Sequence",
  "description": "Description here",
  "blocks": [
    {"type": "random", "category_id": 1, "count": 2}
  ]
}
```

### Update Sequence

```http
PUT /sequences/{id}
Content-Type: application/json

{
  "name": "Updated Name",
  "blocks": [...]
}
```

### Delete Sequence

```http
DELETE /sequences/{id}
```

### Export Sequence

```http
POST /sequences/{id}/export?export_mode=with_community_ids
```

Export modes: `pattern_only`, `with_community_ids`, `with_preroll_data`, `full_bundle`

### Import Sequence

```http
POST /sequences/import
Content-Type: multipart/form-data

file: [.nexseq or .zip file]
auto_download: true
```

---

## Settings

### Get Settings

```http
GET /settings
```

### Update Settings

```http
PUT /settings
Content-Type: application/json

{
  "plex_url": "http://192.168.1.100:32400",
  "plex_token": "your-token-here"
}
```

### Test Plex Connection

```http
POST /settings/test-plex
Content-Type: application/json

{
  "url": "http://192.168.1.100:32400",
  "token": "your-token"
}
```

### Test Jellyfin Connection

```http
POST /settings/test-jellyfin
Content-Type: application/json

{
  "url": "http://192.168.1.100:8096",
  "api_key": "your-api-key"
}
```

### Filler Settings

```http
GET /settings/filler
PUT /settings/filler
Content-Type: application/json

{
  "enabled": true,
  "type": "category",
  "category_id": 1
}
```

Filler types: `category`, `sequence`, `coming_soon`

---

## Path Mappings

### Get Path Mappings

```http
GET /path-mappings
```

### Update Path Mappings

```http
PUT /path-mappings
Content-Type: application/json

{
  "mappings": [
    {
      "nexroll_path": "/prerolls",
      "plex_path": "/media/prerolls"
    }
  ]
}
```

---

## Genre Mappings

### Get Genre Mappings

```http
GET /genre-mappings
```

### Update Genre Mapping

```http
PUT /genre-mappings
Content-Type: application/json

{
  "genre": "Horror",
  "category_id": 5
}
```

---

## Authentication Endpoints

### Auth Status

```http
GET /auth/status
```

Returns whether authentication is enabled and session info.

### Login

```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password",
  "remember_me": false
}
```

### Logout

```http
POST /auth/logout
```

### Register First User

```http
POST /auth/register
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password",
  "role": "admin"
}
```

### User Management

```http
GET /auth/users                        # List all users
POST /auth/users                       # Create user
DELETE /auth/users/{user_id}           # Delete user
PUT /auth/users/{user_id}/toggle       # Enable/disable user
POST /auth/change-password             # Change password
```

### Auth Settings

```http
GET /auth/settings                     # Get auth settings
PUT /auth/settings                     # Update auth settings
```

### Audit Logs

```http
GET /auth/audit-logs                   # View authentication events
DELETE /auth/audit-logs                # Clear audit logs
```

---

## API Keys

### Manage API Keys

```http
GET /api/keys                          # List all API keys
POST /api/keys                         # Create new API key
PUT /api/keys/{key_id}                 # Update API key
DELETE /api/keys/{key_id}              # Revoke API key
GET /api/keys/validate                 # Validate an API key
```

---

## Logging Endpoints

### View Logs

```http
GET /logs?level=ERROR&category=scheduler&search=failed&limit=100
```

| Parameter | Description |
|-----------|-------------|
| `level` | Filter by log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `category` | Filter by category: system, scheduler, api, user, plex, jellyfin, nexup |
| `search` | Search in log messages |
| `limit` | Max results to return |

### Log Statistics

```http
GET /logs/stats
```

Returns counts by level and category.

### Export Logs

```http
GET /logs/export?format=json
```

Formats: `json`, `csv`

### Log File

```http
GET /logs/file
```

Returns the raw log file contents.

### Clear Logs

```http
DELETE /logs
```

### Log Settings

```http
GET /logs/settings
PUT /logs/settings
Content-Type: application/json

{
  "log_level": "INFO",
  "retention_days": 30,
  "enable_db_logging": true,
  "enable_request_logging": true,
  "enable_scheduler_logging": true,
  "enable_api_logging": true
}
```

---

## NeX-Up Endpoints

### Settings

```http
GET /nexup/settings                    # Get NeX-Up settings
PUT /nexup/settings                    # Update NeX-Up settings
```

### Radarr

```http
POST /nexup/radarr/connect             # Connect to Radarr
DELETE /nexup/radarr/disconnect         # Disconnect Radarr
GET /nexup/radarr/upcoming             # Get upcoming movies
```

### Sonarr

```http
POST /nexup/sonarr/connect             # Connect to Sonarr
DELETE /nexup/sonarr/disconnect         # Disconnect Sonarr
GET /nexup/sonarr/upcoming             # Get upcoming shows
```

### Dynamic Preroll Generation

```http
POST /nexup/preroll/generate                      # Generate dynamic intro
POST /nexup/preroll/generate-coming-soon-list      # Generate Coming Soon List video
POST /nexup/preroll/generate-from-preview          # Generate from preview settings
```

### Sync Progress

```http
GET /nexup/sync-progress               # Get current sync/download progress
```

---

## Health & Status

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.11.0"
}
```

### Version

```http
GET /version
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message here"
}
```

Common HTTP status codes:

| Code | Description |
|------|-------------|
| `200` | Success |
| `201` | Created |
| `400` | Bad Request (invalid input) |
| `401` | Unauthorized (missing or invalid credentials) |
| `403` | Forbidden (insufficient permissions) |
| `404` | Not Found |
| `413` | Payload Too Large (file exceeds upload limit) |
| `500` | Server Error |
