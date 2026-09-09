# NeXroll Intros plugin repository

Add the repository for your Jellyfin server version under **Dashboard > Plugins > Repositories**, using **NeXroll Intros** as the name.

**Jellyfin 12:**

```text
https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/Plugins/jellyfin/manifest.json
```

**Jellyfin 10.11:**

```text
https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/Plugins/jellyfin/manifest-10.11.json
```

Enable the repository, open **Catalog**, and install **NeXroll Intros**. Restart Jellyfin after installation. Future plugin versions are picked up by Jellyfin's **Update Plugins** scheduled task; restart Jellyfin after an update to load it.

Use only the repository matching your server. When upgrading Jellyfin from 10.11 to 12, remove the 10.11 repository and add the 12 repository, then install the compatible plugin.

## Already installed manually?

The original manual ZIPs contain `"autoUpdate": false`. Adding a repository alone does not change that setting. After adding the matching repository:

1. Stop Jellyfin.
2. Back up `meta.json` in the installed NeXroll plugin folder (inside Jellyfin's data directory under `plugins`).
3. Change only `"autoUpdate": false` to `"autoUpdate": true` and save the file.
4. Start Jellyfin again. Future versions can now be installed by the **Update Plugins** task.

This one-time change keeps the working plugin and its settings. Do not delete the plugin configuration or keep duplicate DLLs in different plugin directories. Reinstalling the same version from the catalog can fail on Windows because the running server locks the DLL. New catalog installations already enable automatic updates.

Plugin updates do not update the NeXroll application. The Jellyfin 12 API permission warning in older NeXroll versions requires the separate connector fix prepared for NeXroll 2.2.0-beta.9.

## Release maintenance

The plugin build workflow publishes both server variants. After both builds succeed, `update_repository.py` downloads the actual release ZIPs, validates their identity and contents, and publishes separate `-repository.zip` assets with automatic updates enabled. It verifies the uploaded DLL and thumbnail against the originals before writing the manifests. Jellyfin requires the ZIP's MD5 checksum in each manifest entry.

Original assets are never overwritten. A plugin version already in the catalog keeps its original URL and checksum, even when an application beta ships the same plugin again. Bump the plugin assembly and metadata versions together when plugin code changes. The catalog versions are numeric plugin versions, independent of the application's stable or beta version.

Run manually for an existing published release containing both plugin ZIPs:

```bash
python Plugins/jellyfin/update_repository.py --repository JFLXCLOUD/NeXroll --tag v2.0.5
```

Review and commit both manifest files after a manual run. The workflow commits them automatically after future tagged builds. For a workflow dispatch, select the ref containing the intended plugin source and supply the existing release tag.
