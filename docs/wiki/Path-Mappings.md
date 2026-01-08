# Path Mappings

Path mappings are **critical** for NeXroll to work with Plex and Jellyfin when they're running on different systems or in containers.

## Why Path Mappings Matter

NeXroll stores preroll files at a certain path (e.g., `/data/prerolls` in Docker). But Plex might see that same folder at a different path (e.g., `Z:\Prerolls` on Windows or `/mnt/media/prerolls` on Linux).

Without proper mappings, Plex receives a path it can't access, and prerolls won't play.

## How It Works

1. NeXroll stores a preroll at: `/data/prerolls/christmas-intro.mp4`
2. You configure a mapping: `/data/prerolls` → `Z:\Prerolls`
3. When applying to Plex, NeXroll translates to: `Z:\Prerolls\christmas-intro.mp4`
4. Plex can now find and play the file

## Configuring Mappings

1. Go to **Settings**
2. Find **UNC/Local → Plex Path Mappings**
3. Add your mappings:
   - **Source Path**: The path as NeXroll sees it
   - **Destination Path**: The path as Plex/Jellyfin sees it

## Common Scenarios

### Docker NeXroll → Windows Plex

| NeXroll Path | Plex Path |
|--------------|-----------|
| `/data/prerolls` | `Z:\Prerolls` |
| `/data/prerolls` | `\\NAS\Media\Prerolls` |

### Docker NeXroll → Linux Plex

| NeXroll Path | Plex Path |
|--------------|-----------|
| `/data/prerolls` | `/mnt/media/prerolls` |
| `/data/prerolls` | `/volume1/media/prerolls` |

### Docker NeXroll → Docker Plex (Same Host)

If both containers mount the same host folder:

**docker-compose.yml:**
```yaml
services:
  nexroll:
    volumes:
      - /host/prerolls:/data/prerolls
  
  plex:
    volumes:
      - /host/prerolls:/media/prerolls
```

**Mapping:**
| NeXroll Path | Plex Path |
|--------------|-----------|
| `/data/prerolls` | `/media/prerolls` |

### Unraid NeXroll → Unraid Plex

Both typically use the same paths on Unraid:

| NeXroll Path | Plex Path |
|--------------|-----------|
| `/data/prerolls` | `/mnt/user/media/prerolls` |

**Note**: Make sure both containers have access to the same share.

### Windows NeXroll → Windows Plex (Same Machine)

Usually no mapping needed if using the same paths:

| NeXroll Path | Plex Path |
|--------------|-----------|
| `C:\Prerolls` | `C:\Prerolls` |

### Windows NeXroll → NAS Plex

| NeXroll Path | Plex Path |
|--------------|-----------|
| `\\NAS\Prerolls` | `\\NAS\Prerolls` |

Or with mapped drives:

| NeXroll Path | Plex Path |
|--------------|-----------|
| `Z:\Prerolls` | `/volume1/Prerolls` |

## Testing Mappings

**Always test before applying to Plex!**

1. Go to **Settings**
2. Find **Test Translation**
3. Enter a sample path from NeXroll
4. Verify the translated path matches what Plex expects

## Multiple Mappings

You can add multiple mappings for different scenarios. The **longest prefix match** wins.

**Example:**
```
/data/prerolls/holidays → \\NAS\Media\Holiday-Prerolls
/data/prerolls → \\NAS\Media\Prerolls
```

A file at `/data/prerolls/holidays/christmas.mp4` maps to:
`\\NAS\Media\Holiday-Prerolls\christmas.mp4`

A file at `/data/prerolls/default.mp4` maps to:
`\\NAS\Media\Prerolls\default.mp4`

## Path Separator Handling

NeXroll automatically handles path separators:

- **Windows destinations**: Uses backslashes (`\`)
- **Linux/Mac destinations**: Uses forward slashes (`/`)

You don't need to worry about escaping - just enter paths naturally.

## Troubleshooting

### Prerolls Not Playing in Plex

1. **Check Test Translation**: Does it produce a valid Plex path?
2. **Verify Plex Access**: Can Plex access the translated path?
3. **Check Permissions**: Does Plex have read permissions?
4. **Network Paths**: If using UNC paths, ensure Plex service can access network

### UNC Paths Not Working

Windows services (including Plex) may not have access to network shares by default.

**Solutions:**
- Use mapped drive letters instead of UNC paths
- Configure Plex service to run as a user with network access
- Use local paths with proper folder sharing

### Docker Volume Mismatch

Ensure the **same host folder** is mounted in both containers:

```yaml
# Both must mount the SAME host path
nexroll:
  volumes:
    - /host/path/prerolls:/data/prerolls  # Host: /host/path/prerolls

plex:
  volumes:
    - /host/path/prerolls:/media/prerolls  # Host: /host/path/prerolls (SAME!)
```

### Case Sensitivity

- **Windows**: Case-insensitive (paths match regardless of case)
- **Linux**: Case-sensitive (paths must match exactly)

## Best Practices

1. **Use consistent paths**: Keep your preroll folder structure simple
2. **Test before applying**: Always use Test Translation first
3. **Document your mappings**: Keep notes on your setup for future reference
4. **Use absolute paths**: Avoid relative paths which can be ambiguous
5. **Check after Docker updates**: Volume mounts can change between container recreations
