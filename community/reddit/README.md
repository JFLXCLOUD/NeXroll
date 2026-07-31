# NeXroll Reddit Community Manager

This directory contains the declarative configuration, content, branding, and
local moderator utility for `r/NeXroll`.

The utility is deliberately conservative:

- OAuth only; it never accepts or stores a Reddit password.
- Least-privilege moderator scopes.
- `plan` is read-only and `apply` requires the exact community name.
- A timestamped snapshot is taken before every live change.
- Managed items are created or updated in place. Unmanaged rules, flair, wiki
  pages, and widgets are not deleted.
- Posts and AutoModerator are separate, explicit operations.

## 1. Request Reddit Data API Access

Reddit currently requires Data API users to register their use case. Submit the
[Data API request form][api-request] and describe the tool truthfully as a
local, moderator-operated community setup utility. Disclose whether its use is
commercial or noncommercial.

Suggested description:

> A local, moderator-operated setup utility for r/NeXroll. It reads the
> community's current configuration and applies moderator-approved settings,
> rules, post-flair templates, wiki/sidebar content, structured sidebar
> widgets, community branding assets, and launch/welcome posts. It runs
> interactively for one community, provides a dry-run and backup before
> changes, and never scrapes, trains models, profiles users, sends messages, or
> stores Reddit user content. Expected usage is a few hundred requests during
> initial setup and occasional maintenance, below the published free limit.

For the form's Devvit question:

> Devvit does not provide the needed local, one-time reconciliation and export
> workflow across an existing community's settings, rules, flair, wiki,
> sidebar widgets, branding, and pinned posts. This utility also provides a
> reviewable dry-run and a local pre-change backup.

## 2. Create the OAuth App

After approval, open [Reddit app preferences][reddit-apps] while signed into the
moderator account:

1. Select **create another app**.
2. Choose **web app**.
3. Use `NeXroll Community Manager` as the name.
4. Set the redirect URI exactly to `http://localhost:8080`.
5. Record the client ID shown beneath the app name and the client secret.

For a dedicated moderator account, grant only the `config`, `flair`, `posts`,
and `wiki` subreddit permissions. A personal moderator account can authorize
the app directly.

## 3. Install Locally

From PowerShell:

```powershell
cd community/reddit
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally:

```dotenv
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_REDIRECT_URI=http://localhost:8080
REDDIT_USER_AGENT=windows:nexroll-community-manager:v1.0 (by /u/your_username)
```

Do not paste `.env`, client secrets, refresh tokens, cookies, or account
passwords into an issue, chat, screenshot, or commit. The repository ignores
`.env` files.

## 4. Authorize and Audit

```powershell
.\.venv\Scripts\python manage.py authorize
.\.venv\Scripts\python manage.py doctor
.\.venv\Scripts\python manage.py validate
.\.venv\Scripts\python manage.py snapshot
.\.venv\Scripts\python manage.py plan
```

`authorize` opens a one-time Reddit consent page and saves only the returned
refresh token to the local `.env`. The requested scopes are:

```text
identity read modconfig modflair modposts structuredstyles
wikiread wikiedit modwiki submit edit
```

Review the `plan` output and the newest file in `snapshots/` before applying
anything.

## 5. Apply Approved Sections

Core community setup:

```powershell
.\.venv\Scripts\python manage.py apply `
  --sections settings,rules,flair,wiki,widgets,appearance `
  --confirm r/NeXroll
```

Publishing the two prepared sticky posts is intentionally separate:

```powershell
.\.venv\Scripts\python manage.py apply `
  --sections posts `
  --publish-posts `
  --confirm r/NeXroll
```

AutoModerator is also separate because it changes live moderation behavior:

```powershell
.\.venv\Scripts\python manage.py apply `
  --sections automoderator `
  --confirm r/NeXroll
```

Run `plan` again after each apply. Reddit features that are unavailable through
the public API are reported as manual follow-up tasks instead of being silently
skipped.

## 6. Finish in Mod Tools

The utility will report these checks because Reddit does not expose every
current community control through a stable public write API:

1. Require post flair in **Mod Tools > Posts and Comments**.
2. Verify the community is eligible for discovery.
3. Unpin the obsolete `1.14 stable / v2 beta` post, preserve it as history, and
   assign the moderator-only **Archived Release** flair.
4. Confirm the two new sticky slots before publishing. The utility will not
   replace an unrelated sticky.
5. Review the prepared AutoModerator file before its separate apply.
6. Optionally schedule a monthly **Show Us Your Setup** thread in Reddit's
   Scheduled Posts UI.

## Package Layout

- `config/community.json`: managed settings, rules, flair, widgets, and posts.
- `content/`: sidebar, public wiki, post bodies, and AutoModerator policy.
- `assets/`: generated Reddit icon and desktop/mobile banners.
- `scripts/generate_brand_assets.ps1`: repeatable brand-asset generator.
- `snapshots/`: ignored local backups created from live moderator data.

[api-request]: https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164
[reddit-apps]: https://www.reddit.com/prefs/apps
