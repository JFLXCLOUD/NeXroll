# Connect

The Connect page links NeXroll to your media server. Until one is connected, NeXroll can organise and schedule prerolls but has nowhere to send them.

NeXroll supports **Plex**, **Jellyfin** and **Emby**, one at a time.

---

## Plex

### Sign in with Plex (recommended)

Click **Sign in with Plex**. A Plex tab opens; approve NeXroll there. NeXroll then discovers your server and its token automatically — there is nothing to copy by hand.

This is also offered during first-run setup. If the tab does not open, your browser blocked the popup; the page shows a direct link to use instead.

### Server URL and token (manual)

If you would rather not sign in — or you run a server the account discovery does not reach — expand the manual section and provide:

- **Server URL**, for example `http://192.168.1.10:32400`
- **Plex token** — see [Finding an authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

Click **Test & Connect**.

---

## Jellyfin

Provide the server URL and an API key created under **Dashboard → API Keys** in Jellyfin, then connect. Full walkthrough: [Jellyfin Setup](Jellyfin).

## Emby

Provide the server URL and an API key created under **Settings → Advanced → API Keys** in Emby, then connect. Full walkthrough: [Emby Setup](Emby).

---

## After connecting

The page shows the connected server, its name and version, and a live status dot. NeXroll can now:

- Apply the active schedule's prerolls to the server
- Read your libraries for genre-based scheduling
- Verify that the paths it sends are ones the server can open

### Verify playback

Use **Test connection** to confirm NeXroll can still reach the server, and apply a schedule to confirm the server accepts the preroll path. A successful apply that still plays nothing is nearly always a path problem, not a connection problem — see below.

---

## Paths are the usual problem

NeXroll and your media server frequently see the same file under different names. NeXroll might write to `/data/prerolls/holiday/xmas.mp4` inside a container while Plex sees `/mnt/media/prerolls/holiday/xmas.mp4`.

When the path is wrong the server accepts the setting and then quietly plays nothing — there is no error to notice.

Set this up under **Settings → Path Mappings**, or answer the Paths step during first-run setup if you installed with Docker. Full guide: [Path Mappings](Path-Mappings).

---

## Switching servers

Connecting a second server type disconnects the first — NeXroll drives one server at a time. Your library, categories and schedules are untouched; only the destination changes.

---

## Troubleshooting

**"Connection failed" with a correct URL.**
Check that NeXroll can reach the address *from where NeXroll runs*. In Docker, `localhost` means the container, not your host — use `host.docker.internal` or the host's LAN address. See [Docker Setup](Docker).

**Plex sign-in never completes.**
The request times out after ten minutes. Start it again; if the tab never opened, use the direct link shown on the page.

**Connected, applies cleanly, nothing plays.**
A path mapping issue. See [Path Mappings](Path-Mappings).

More: [Troubleshooting](Troubleshooting).

---

## See also

- [Jellyfin Setup](Jellyfin)
- [Emby Setup](Emby)
- [Path Mappings](Path-Mappings)
- [Docker Setup](Docker)
