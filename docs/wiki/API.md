# API Documentation

NeXroll provides a REST API for programmatic control of prerolls, categories, schedules, and sequences.

## Base URL

```
http://localhost:9393
```

Replace with your server's address if running remotely.

## Authentication

Currently, the API does not require authentication. Secure your NeXroll instance at the network level if exposed publicly.

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
  "name": "Halloween 2024",
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

**Response:**
```json
[
  {
    "id": 1,
    "name": "Christmas 2024",
    "category_id": 1,
    "start_date": "2024-12-01",
    "end_date": "2024-12-25",
    "exclusive": true,
    "enabled": true,
    "sequence_id": null
  }
]
```

### Create Schedule

```http
POST /schedules
Content-Type: application/json

{
  "name": "Christmas 2024",
  "category_id": 1,
  "start_date": "2024-12-01",
  "end_date": "2024-12-25",
  "exclusive": true,
  "enabled": true
}
```

### Update Schedule

```http
PUT /schedules/{id}
Content-Type: application/json

{
  "name": "Christmas 2024 Updated",
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

**Response:**
```json
[
  {
    "id": 1,
    "name": "Holiday Mix",
    "description": "Random holiday prerolls",
    "blocks": [
      {"type": "fixed", "preroll_ids": [1, 2]},
      {"type": "random", "category_id": 1, "count": 2}
    ],
    "created_at": "2024-12-01T10:00:00Z"
  }
]
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

**Response:**
```json
{
  "plex_url": "http://192.168.1.100:32400",
  "plex_connected": true,
  "jellyfin_url": null,
  "jellyfin_connected": false,
  "timezone": "America/New_York",
  "genre_auto_apply": true
}
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

**Response:**
```json
{
  "version": "1.11.0",
  "build": "2024-12-23"
}
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
- `200` - Success
- `201` - Created
- `400` - Bad Request (invalid input)
- `404` - Not Found
- `500` - Server Error
