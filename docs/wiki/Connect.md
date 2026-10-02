# Connect

The Connect page links NeXroll to your media server. Until one is connected, NeXroll can organise and schedule prerolls but has nowhere to send them.

NeXroll supports **Plex**, **Jellyfin** and **Emby**, and you can connect as many of them as you run. Whatever you schedule plays on every connected server.

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
- Verify that the paths it sends are ones the server can open

### Verify playback

Use **Test connection** to confirm NeXroll can still reach the server, and apply a schedule to confirm the server accepts the preroll path. A successful apply that still plays nothing is nearly always a path problem, not a connection problem — see below.

### Cinema Trailers (Plex)

With Plex connected, the Connect page also shows Plex's own **Cinema Trailers** settings: whether Plex takes trailers from movies in your library and, with Plex Pass, from new movies in theaters and on Blu-ray. Changes save straight to your Plex server.

**To play only your prerolls**, click **Turn off Plex trailers**. Then, in each Plex app, set **Cinema Trailers** to **Play 1 before movie** (on Apple TV: **Settings > Player Experience > Cinema Trailers**). Plex has no trailers of its own left to add, so it plays your prerolls and then the movie. Trailers in your NeXroll sequences still play, because they are part of the preroll list NeXroll sends.

Use this instead of the app's **Play Pre-roll Only** option. Plex's new Apple TV and iOS apps (2026.18, September 2026) skip prerolls when that option is chosen, and the Android TV beta before them did the same. **Play 1 before movie** works on old and new apps alike.

---

## Paths are the usual problem

NeXroll and your media server frequently see the same file under different names. NeXroll might write to `/data/prerolls/holiday/xmas.mp4` inside a container while Plex sees `/mnt/media/prerolls/holiday/xmas.mp4`.

When the path is wrong the server accepts the setting and then quietly plays nothing — there is no error to notice.

Set this up under **Settings → Path Mappings**, or answer the Paths step during first-run setup if you installed with Docker. Full guide: [Path Mappings](Path-Mappings).

---

## Using more than one server

Plex, Jellyfin and Emby can all be connected at once — for example Plex in the lounge and Jellyfin for the kids. Connecting another server does not disconnect the one you already have, and there is nothing to choose between: the same schedules, sequences and categories apply to all of them.

Each server is reached its own way. Plex has the preroll setting written to it directly, while Jellyfin and Emby ask the NeXroll Intros plugin what to play when playback starts. So one server being offline does not stop the others, and the scheduler log names which server an apply succeeded or failed on.

Disconnecting a server only removes that destination. Your library, categories and schedules are untouched.

### Removing a server NeXroll can't reach

> **New in 2.2.2.**

If a server is saved but doesn't answer, because it is off, has moved, or its API key or token changed, its card shows **Can't connect** with the saved address and a **Remove** button. Opening its settings shows the same choice above the connect form. **Remove** clears the saved address and key, exactly like Disconnect. To keep the server, start it or connect again with its new address or key instead.

Before 2.2.2 the card only offered Disconnect while the server answered, so a retired server could not be removed.

Before 2.2.0-beta.10, NeXroll allowed only one server and asked you to disconnect the first before connecting another. That limit is gone.

---

## Troubleshooting

**"Connection failed" with a correct URL.**
Check that NeXroll can reach the address *from where NeXroll runs*. In Docker, `localhost` means the container, not your host — use `host.docker.internal` or the host's LAN address. See [Docker Setup](Docker).

**Plex sign-in never completes.**
The request times out after ten minutes. Start it again; if the tab never opened, use the direct link shown on the page.

**A server shows Can't connect and you no longer use it.**
Click **Remove** on its card. See [Removing a server NeXroll can't reach](#removing-a-server-nexroll-cant-reach).

**Connected, applies cleanly, nothing plays.**
A path mapping issue. See [Path Mappings](Path-Mappings).

**Prerolls stopped after a Plex app update.**
If the app's **Cinema Trailers** option is **Play Pre-roll Only**, change it to **Play 1 before movie** and turn Plex's trailers off. See [Cinema Trailers](#cinema-trailers-plex).

More: [Troubleshooting](Troubleshooting).

---

## See also

- [Jellyfin Setup](Jellyfin)
- [Emby Setup](Emby)
- [Path Mappings](Path-Mappings)
- [Docker Setup](Docker)
