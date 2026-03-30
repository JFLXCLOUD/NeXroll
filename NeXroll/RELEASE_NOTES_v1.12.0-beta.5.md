# NeXroll v1.12.0-beta.5 Release Notes

**Release Date:** 03-29-2026
**Type:** Bug Fix (Critical)

---

## Critical Fix: Plugin Detection API Key Leak (#21)

This release fixes a critical bug where the Jellyfin and Emby plugin detection endpoints were creating thousands of orphaned API keys in the database.

### Root Cause

The `GET /jellyfin/plugin/detect` and `GET /emby/plugin/detect` endpoints were **not read-only** — they attempted to auto-configure the plugin (including generating a new API key) every time the plugin's `NexrollUrl` was empty. When the configuration push failed (common due to permissions or plugin version mismatches), the newly created API key was left orphaned in the database while `NexrollUrl` remained empty, causing the next detect call to repeat the cycle.

With the frontend calling detect on every page load, this created hundreds to thousands of orphaned keys per session.

### What Changed

1. **Detect endpoints are now read-only** — `GET /jellyfin/plugin/detect` and `GET /emby/plugin/detect` no longer create API keys or push configuration. They report plugin status and return `auto_configured: false` so the frontend knows to prompt the user to configure manually.

2. **Configure endpoints clean up old keys** — `POST /jellyfin/plugin/configure` and `POST /emby/plugin/configure` now delete all inactive auto-generated keys before creating a new one, preventing key accumulation from repeated configure attempts.

3. **Failed push rollback** — If the configuration push fails during a configure call, the newly created API key is deleted from the database instead of being left as an orphan.

### Impact

- Users who experienced API key accumulation (issue #21) will no longer see new keys being created on every page load
- Existing orphaned keys can be cleaned up using the bulk delete feature added in beta.4
- The configure button still works as expected — it creates a fresh key and pushes config to the plugin

---

## Upgrade Notes

- No database migration required
- Existing orphaned API keys from previous versions can be removed via Settings → API Keys → Select All → Delete Selected
