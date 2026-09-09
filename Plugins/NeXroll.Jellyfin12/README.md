# NeXroll Intros for Jellyfin 12

This is the .NET 10 / Jellyfin 12 build of the NeXroll Intros plugin.
It shares the provider and configuration source with the Jellyfin 10.11 build,
but has its own project, metadata, and package output.

| Jellyfin server | Plugin | Package |
| --- | --- | --- |
| 10.11.x | 1.14.0.0 | `NeXroll.Jellyfin-1.14.0.0.zip` |
| 12.x | 1.15.0.0 | `NeXroll.Jellyfin12-1.15.0.0.zip` |

Use the package for your server version. Both contain `NeXroll.Jellyfin.dll`
and use the same plugin ID and configuration, so install only one variant.

## Build

For installation and future automatic updates, use the [Jellyfin plugin repository](../jellyfin/README.md). Existing manual installations need the one-time migration described there.

Install the .NET 10 SDK, then run from this directory:

```powershell
./package.ps1
```

The package contains exactly `NeXroll.Jellyfin.dll`, `meta.json`, and `thumb.png`.
Do not copy the entire `publish` directory into Jellyfin: the other DLLs belong
to the server and bundling them can cause assembly conflicts.

## Install and test

1. Stop Jellyfin and back up the existing NeXroll plugin directory and settings.
2. Replace the old NeXroll plugin files with the three files from the 12.x ZIP.
   Remove any duplicate old NeXroll plugin DLL from other plugin directories.
3. Start Jellyfin and check that NeXroll Intros 1.15.0.0 loads without an
   incompatible-assembly error.
4. Open its configuration page, verify the NeXroll URL and API key, and use
   **Test Connection**. Existing settings should be retained.
5. With an active NeXroll preroll, start a movie from the beginning and verify
   that the preroll plays and hands off to the movie. Repeat on the actual
   client you use; clients can differ in intro support.

The NeXroll warning about permission to list Jellyfin plugins can also come from
its older connector authentication. Jellyfin 12 disables legacy token headers
by default: the same fresh API key returned 401 with `X-Emby-Token` and 200 with
`Authorization` in a clean server test. The connector fix is prepared for
NeXroll 2.2.0-beta.9. Installing this plugin alone does not update an older
NeXroll application's connector or change API-key permissions.
