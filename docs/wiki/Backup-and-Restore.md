# Backup and Restore

Found under **Settings → Backup & Restore**. There are two kinds of backup, and they answer different questions.

| | Database Backup (.json) | System Backup (.zip) |
|---|---|---|
| Size | Small (kilobytes) | Large (your whole library) |
| Video files | No | Yes |
| Settings and connections | Yes | Yes |
| Good for | Moving configuration, before an upgrade | Full disaster recovery |

---

## Database Backup (.json)

A portable text file containing everything except the videos:

- Prerolls (metadata, categories, tags, duration, hashes) — not the files
- Categories, including Plex mode and apply-to-Plex flags
- Schedules, with priority, exclusive/blend, holiday links and sequence links
- Saved sequences and their blocks
- Holiday presets, including date ranges
- Genre routing rules
- Ignored paths and community templates
- Sidebar favorites
- **Every setting** — media server URLs, Radarr/Sonarr/TMDB keys, path mappings, dashboard layout, NeX-Up and Generator defaults, logging, filler, timezone, ignored conflicts
- **Media server credentials** — the Plex token and the Jellyfin and Emby API keys. NeXroll keeps these in the system's secret store rather than its database, so they travel in their own section of the file. Backups made before 2.2.1 do not include them.

> **This file contains your server tokens and API keys.** Keep it somewhere private. Do not attach it to a public issue.

### What is deliberately excluded

- **User accounts and NeXroll API keys.** Restoring logins from a portable file is a credential transfer decision NeXroll does not make for you. Recreate accounts under **Settings → Users**. Favorites that belong to a user account stay behind with it.
- **Logs, sessions and audit history.** Transient.
- **Runtime state** — which schedule is active right now, last-sync timestamps, the onboarding flag. A restore should not drag the target install into a wizard or replay stale state.

### Restoring

Choose **Restore Database (.json)** and select the file. NeXroll replaces categories, prerolls, schedules, sequences, holidays and genre maps, then applies the settings and puts the media server credentials into this machine's secret store.

Foreign keys are remapped, not copied blindly: the ids in the file are translated to the new ids the restore assigns, so your NeX-Up category, filler category, filler sequence, active category and ignored schedule conflicts still point at the right rows even though the numbers changed. (Backups made before 2.2.1 do not record schedule ids, so their ignored conflicts are dropped rather than pointed at the wrong schedules.)

Absolute paths are handled carefully. `preroll_folder` and `nexup_storage_path` are only applied if the directory exists on the machine you are restoring to — so restoring a Windows backup into a container does not point storage at `C:\...`. The same goes for uploaded Generator logos, soundtracks and backdrops: they are applied only if the file exists here. The install keeps its own paths and tells you which it skipped.

After restoring, NeXroll rescans and reconciles the database against the files actually on disk.

---

## System Backup (.zip)

Everything above, plus the content:

- `database/nexroll.db` — a consistent copy of the database, including changes made moments before the backup
- `database/nexroll_data.json` — the same JSON export as above (credentials included), as a cross-version fallback
- `prerolls/` — every preroll video
- `thumbnails/` — every preview image
- `nexup/` — generated prerolls, Coming Soon lists, and uploaded brand assets (logos, audio)
- `settings/settings.json`

### What is left out, and why

**Downloaded movie and TV trailers.** NeX-Up re-downloads those on demand and they are usually the bulk of the folder. Including them would multiply the archive size for content that regenerates itself.

Generated prerolls *are* included, because they cannot be recreated — they are your authored output.

### Restoring

Choose **Restore System (.zip)**. NeXroll closes its database connections, replaces the database file, and writes the videos, thumbnails and generated content back into this install's own locations — not the paths baked into the archive. That is what makes a Windows backup restorable into Docker and vice versa.

Because generated prerolls live outside the prerolls folder, their database paths are relinked by filename after the files land, so entries do not end up pointing at a drive that does not exist here. Uploaded Generator logos, soundtracks and backdrops are relinked the same way, and a preroll folder or NeX-Up folder that does not exist on this machine is replaced by this install's own, so new NeX-Up downloads land beside the restored files. The media server credentials are put into this machine's secret store.

The archive is written to disk and unpacked a piece at a time, so a backup larger than the machine's memory restores fine.

**Restart NeXroll after restoring a system backup.** The process is running against the database it started with; the restore message says so. On restart NeXroll rescans the preroll folder and points every preroll at its file.

---

## Moving to another machine

1. Take a **System Backup** on the old install.
2. Install NeXroll on the new machine and let it start once.
3. Restore the ZIP.
4. Restart NeXroll.
5. Check **Settings → Path Mappings** — the new machine may see your media at a different path.
6. Check **Connect**. The credentials come with the backup, but if the new machine reaches your media server at a different address, update it there. A backup made before 2.2.1 has no credentials, so reconnect after restoring one.

Moving between Windows and Docker works, but paths will differ. The restore keeps the new install's own storage paths rather than the old machine's; mappings are the piece you may still need to adjust.

---

## Before you upgrade

Take a Database Backup. It is small, quick, and contains every setting — enough to put a fresh install back the way it was.

### Upgrading to 2.2.0

Existing schedules and saved sequences are migrated in place. Next-run metadata is refreshed while schedule identity, content, priority, enabled state, and history are retained. Review [Scheduling](Scheduling#upgrading-existing-schedules-to-220) for older Monthly/Yearly behavior and timing that needs repair.

Existing trailer blocks remain unrestricted, and existing availability conditions keep checking the upcoming pool. Older trailers receive available rating metadata on the next normal provider-backed NeX-Up sync; they are not redownloaded just to add ratings. See [NeX-Up](NeX-Up#rating-metadata-after-upgrading).

Sequence backups and exports retain new rating restrictions and availability choices. Restore or import them into 2.2.0 or later; earlier versions cannot be relied upon to enforce new restrictions. Keep a pre-upgrade backup if you may need to return to the previous release.

Library Trailer minimum targets are part of its saved settings and therefore travel with database/system configuration backups. They are not included in a sequence pattern: each receiving install chooses its own pool targets and download limits. Older settings without targets keep the original selection and rotation behavior.

---

## Troubleshooting

**Restore finished but my media server is not connected.**
Tokens are in the backup, but the server URL may not be reachable from the new machine. Re-check under [Connect](Connect). A backup made before 2.2.1 has no tokens: reconnect once and take a new backup.

**Restored prerolls show as missing.**
The videos were not in the backup — that is expected for a Database Backup. Restore a System Backup, or point NeXroll at the folder holding them via **Library → Add Prerolls**.

**Restore reports skipped paths.**
Expected when moving between machines. It means a folder from the source install does not exist here, so NeXroll kept its own. Nothing was lost.

---

## See also

- [Configuration](Configuration)
- [Path Mappings](Path-Mappings)
- [Docker Setup](Docker)
- [Troubleshooting](Troubleshooting)

### Stored audio conditions

Audio rules are optional fields in existing sequence block JSON; no audio-specific database migration is required. Saved sequences, schedule sequences, exports and backups retain those fields. Existing schedules/sequences without audio rules keep their behavior. Restore or import audio-conditioned sequences into 2.2.0 or later; older releases cannot evaluate them. See [Stored audio format](Advanced-Sequences#stored-audio-format-jellyfin--emby).
