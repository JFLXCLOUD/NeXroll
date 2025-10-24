# Schema Migration Fix - Dashboard Layout Column

## Issue
Docker container was failing with the error:
```
Scheduler error: (sqlite3.OperationalError) no such column: settings.dashboard_layout
```

This occurred when the application tried to query the `dashboard_layout` column from the settings table, which didn't exist in existing databases.

## Root Cause
The `dashboard_layout` column was added to the `Setting` model in `models.py`, but the automatic schema migration function `ensure_schema()` in `main.py` was missing the migration rule to add this column to existing SQLite databases.

## Solution
Added the missing schema migration to `ensure_schema()` function in `NeXroll/backend/main.py`:

```python
# Settings: ensure dashboard layout column
if not _sqlite_has_column("settings", "dashboard_layout"):
    _sqlite_add_column("settings", "dashboard_layout TEXT")
```

This ensures that when the application starts:
1. It checks if the column exists
2. If not, it automatically creates it
3. Existing databases are seamlessly upgraded without data loss
4. New installations get the complete schema from the start

## How It Works
The `ensure_schema()` function runs early in application startup (line 209 of main.py) and again during request handling if needed (line 991). It:

- Detects the database type (SQLite in Docker/Windows deployments)
- Checks for missing columns using `PRAGMA table_info()`
- Adds missing columns with appropriate types and defaults
- Logs all schema changes for debugging

## Files Modified
- `NeXroll/backend/main.py` - Added dashboard_layout migration to ensure_schema()

## Testing
To verify the fix works in Docker:

```bash
# Pull the updated image
docker pull jbrns/nexroll:1.5.12

# Run with a persistent database volume
docker run -d \
  -v nexroll_data:/data \
  -p 9393:9393 \
  jbrns/nexroll:1.5.12
```

The container will now:
1. Detect existing database (if present)
2. Automatically add missing `dashboard_layout` column
3. Start without errors

## Backward Compatibility
✅ This fix is fully backward compatible:
- Existing databases are updated in-place
- No data is lost
- No manual migration steps required
- Works across all platforms (Windows, Docker, Linux)

## Related Columns
While fixing this issue, the migration also handles:
- `dashboard_tile_order` - For custom dashboard ordering
- `timezone` - For timezone support
- Genre-based preroll settings
- All other dynamic schema columns
