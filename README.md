<div align="center">
  <img src="assets/nexroll-logo-white.png#gh-dark-mode-only" alt="NeXroll" width="380" />
  <img src="assets/nexroll-logo-black.png#gh-light-mode-only" alt="NeXroll" width="380" />
  <p>Make the start of the movie part of the experience.</p>
  <p>
    <a href="https://github.com/JFLXCLOUD/NeXroll/releases">Downloads</a> ·
    <a href="docs/wiki/Getting-Started.md">Getting started</a> ·
    <a href="docs/wiki/Home.md">Documentation</a> ·
    <a href="https://discord.gg/R9eH7TbxEk">Discord</a> ·
    <a href="https://ko-fi.com/j_b__">Support on Ko-fi</a>
  </p>
  <p>
    <a href="https://github.com/JFLXCLOUD/NeXroll/releases/latest"><img src="https://badgen.net/github/release/JFLXCLOUD/NeXroll/stable?label=stable&amp;color=yellow" alt="Latest Stable Release" /></a>
    <a href="https://hub.docker.com/r/jbrns/nexroll"><img src="https://img.shields.io/docker/pulls/jbrns/nexroll" alt="Docker Pulls" /></a>
    <a href="https://github.com/JFLXCLOUD/NeXroll/releases"><img src="https://img.shields.io/github/downloads/JFLXCLOUD/NeXroll/total?include_prereleases&amp;color=DE7716" alt="GitHub Downloads" /></a>
  </p>
</div>

> **2.2.0 beta.** This README describes the upcoming 2.2.0 release. [Try 2.2.0-beta.11](https://github.com/JFLXCLOUD/NeXroll/releases/tag/v2.2.0-beta.11), or use the [latest stable release](https://github.com/JFLXCLOUD/NeXroll/releases/latest).

NeXroll manages prerolls for **Plex, Jellyfin, and Emby**. Organize your intro videos, build a sequence for movie night, and schedule something different for a holiday or a season. NeX-Up adds trailers from your Radarr and Sonarr libraries, plus tools for creating your own welcome screens, announcements, and Coming Soon videos.

Run it on Windows, in Docker, or on Unraid. Manage everything from your browser.

![The NeXroll dashboard showing the current selection, upcoming schedules, and library activity](docs/screenshots/v2.2.0/dashboard.png)

*Screenshots show the 2.2.0 beta interface with example data and demonstration artwork.*

## What's new in 2.2.0

- **A sequence that reacts to what's about to play.** A block can play only when a rule holds, with something else in its place when it doesn't. Match the genre of the film that's starting, the time of night, whether a block is a movie or an episode, or whether there are trailers worth showing at all.
- **Flow view for the sequence builder.** See the whole preshow as a workflow, with conditional blocks drawn as branches, instead of reading it as a list.
- **Trailers for the movies you already own.** NeX-Up keeps library trailers from Radarr, using trailer files already sitting beside your movies or downloading the rest, so a sequence can run them the way a cinema does.
- **Use every media server at once.** Connect Plex, Jellyfin, and Emby together. Whatever you schedule applies to all of them.
- **A clearer view of your setup.** See what's playing, what comes next, and what needs attention. Library filters, schedule controls, and connection pages follow a consistent layout, with navigation that adapts to smaller screens.
- **Eight themes across the whole app.** Choose Midnight, Daylight, Cinema, Nocturne, Parchment, Terminal, Neon, or Carbon.
- **NeX-Up Generator Studio.** Create a preroll with a live preview, then adjust the template, text, typeface, colors, timing, and soundtrack. Add your own logo or video backdrop, write a custom message, or include a QR code.
- **More useful calendar views.** Browse schedules by month, week, or day. See filler coverage, open a day for details, and review overlapping schedules and their priorities.
- **Community browsing improvements.** Filter by category, creator, or platform, and select several prerolls to download together.
- **Generator API access.** Start a dynamic preroll or Coming Soon render from another tool and check its progress through the External API.
- **Jellyfin 12 support.** A separate plugin build supports Jellyfin 12, alongside the existing Jellyfin 10.11 build. The connector also uses the authentication header required by Jellyfin 12.

See the [changelog](NeXroll/CHANGELOG.md) for the full set of changes and fixes.

## Build your preshow

### Keep your collection organized

Upload or import prerolls, preview them, and organize them with categories and tags. A video can belong to more than one category. Filters help you find the videos you want without mixing your permanent collection with automatically managed trailers and generator output.

<details>
<summary>View the preroll library</summary>

![Preroll library with category filters, thumbnails, and video details](docs/screenshots/v2.2.0/library.png)

</details>

### Set the schedule once

Create recurring schedules or use a date range for a one-off event. Choose a category or a saved sequence, set its priority, and decide how it behaves when schedules overlap. Filler provides a selection for the gaps between schedules.

<details>
<summary>View schedules and the calendar</summary>

![Schedule management with named schedules, timing, and playback rules](docs/screenshots/v2.2.0/schedules.png)

![Calendar showing seasonal selections, individual events, and filler coverage](docs/screenshots/v2.2.0/calendar.png)

</details>

### Put the sequence together

Combine fixed videos, random selections from categories, and pauses in a saved sequence. Use the same sequence in more than one schedule. Random selections cycle through eligible videos before repeating.

Switch the builder to **Advanced** and a block can decide when it plays. Give it a rule and an alternative: play it only when the film starting is a horror movie, only between 22:00 and 03:00 at weekends, only before films rather than episodes, or only when there are trailers downloaded to show. When the rule isn't met, the block can be skipped or replaced by prerolls from a category or by trailers. A summary reads the whole condition back in plain English.

Genre and movie-or-episode rules work on **Jellyfin and Emby**, which tell NeXroll what is starting at the moment playback begins. Plex is given its preroll list in advance and never says which film is next, so on Plex those blocks play their alternative instead, and the builder shows you which rules each server you've connected can actually answer. One sequence can serve all of them.

**Flow view** draws the same sequence as a workflow rather than a list, with a conditional block shown as a branch: one path when the rule holds, another to whatever plays in its place. Drag blocks to arrange the canvas, and move a block earlier or later in the running order with the arrows. Layout and running order stay separate, so tidying the picture never changes what your viewers see.

![Flow view showing a sequence that plays NeX-Up trailers when trailers are available and falls back to a category when they are not](docs/screenshots/v2.2.0/sequence-flow.png)

Preview the sequence to see which conditional blocks play, which play their alternative, and which are skipped. For genre rules you can preview as Plex or as any genre the sequence uses, so you can check both cases before scheduling it.

### Bring upcoming releases into the mix

Connect Radarr and Sonarr to NeX-Up to find and download trailers for upcoming movies and TV releases. Choose how many to include, manage the downloaded files, and set when old trailers should be removed.

**Library Trailers** covers the films already in your library, so a sequence can show trailers for what you own the way a cinema shows them before the feature. NeXroll uses trailer files already stored beside your movies, in the naming Plex, Jellyfin, and Emby all recognize, and only ever reads those. For the rest it can download the trailer Radarr has on record. Pick films by hand from your library, or by filters for genre, age rating, language, release year, review scores, how recently they were added, and Radarr tags. Storage and count limits apply to downloads only. On Jellyfin and Emby a library trailers block can match the genre of the film that's starting, and it never picks the trailer for the film about to play.

Use Generator Studio to create a welcome video, an announcement, a QR code screen, or a Coming Soon list with your own presentation style.

<details>
<summary>View Generator Studio</summary>

![NeX-Up Generator Studio with a live preroll preview and presentation controls](docs/screenshots/v2.2.0/generator.png)

</details>

YouTube can restrict downloads through rate limits, IP blocks, or authentication checks. NeX-Up includes download diagnostics and PO-token support, but it cannot guarantee access to every trailer or remove a YouTube block.

### Find something from the community

Search and browse Community Prerolls by theme, category, creator, or platform. Preview a selection, choose a category, and add it to your library.

Community Prerolls is powered by [TypicalNerds](https://typicalnerds.uk/). A big thank you to TypicalNerds for making the collection available, and to the creators who contribute their prerolls for everyone to enjoy.

<details>
<summary>View Community Prerolls</summary>

![Community browsing with filters and a list of example prerolls](docs/screenshots/v2.2.0/community.png)

The titles and collection names in this screenshot are demonstration content.

</details>

## Choose your media server

Connect as many as you run. Plex in the lounge and Jellyfin for the kids can share one NeXroll, and whatever you schedule applies to every server you've connected. A server that is unreachable no longer stops the others getting their prerolls, and the scheduler log names the server so a partial failure reads as one.

| Server | How NeXroll connects |
| --- | --- |
| **Plex** | Updates the server's preroll selection from your active schedule or filler settings. Plex needs access to the video files through paths it can read. |
| **Jellyfin** | The NeXroll Intros plugin requests the current selection when Jellyfin asks for intros. Install the plugin build that matches your Jellyfin server version. |
| **Emby** | The NeXroll Intros plugin requests intros from NeXroll. Configure it for the movies or episodes you want to include. |

Plex's preroll setting is shared across the server. Playback-triggered changes are best effort, and a change may wait while a movie is playing. Jellyfin and Emby use their plugin intro flow; playback behavior also depends on the client.

Setup guides: [Plex and connections](docs/wiki/Connect.md), [Jellyfin](docs/wiki/Jellyfin.md), [Jellyfin 12 plugin](Plugins/NeXroll.Jellyfin12/README.md), [Emby](docs/wiki/Emby.md).

## Install NeXroll

### Windows

1. Download the Windows installer from [GitHub Releases](https://github.com/JFLXCLOUD/NeXroll/releases).
2. Run the installer and choose where to keep your prerolls. You can also install the Windows service and tray app.
3. Open `http://localhost:9393` and follow the setup wizard.

Windows 10 or 11, 64-bit, is supported. You do not need to install Python. FFmpeg is used for thumbnails and video generation; see the [installation guide](docs/wiki/Installation.md) for setup options.

### Docker

Create a `compose.yaml` file:

```yaml
services:
  nexroll:
    image: jbrns/nexroll:latest
    container_name: nexroll
    ports:
      - "9393:9393"
    environment:
      TZ: America/New_York
      NEXROLL_DB_DIR: /data
      NEXROLL_SECRETS_DIR: /data
      NEXROLL_PREROLL_PATH: /data/prerolls
    volumes:
      - ./nexroll-data:/data
      - /path/to/prerolls:/data/prerolls
      - /path/to/trailers:/data/nexup_trailers
    restart: unless-stopped
```

Replace the host paths and timezone with your own, then run:

```bash
docker compose up -d
```

Open `http://YOUR_SERVER:9393`. If you use the separate trailer folder above, set NeX-Up's storage path to `/data/nexup_trailers`.

The Docker image supports AMD64 and ARM64. The `latest` tag follows stable releases; `beta` follows prereleases. See the [Docker guide](docs/wiki/Docker.md) for permissions and additional configuration.

### Unraid

Find **NeXroll** in Community Applications. Set the app-data, preroll, and optional trailer paths, check your timezone, then open the WebUI and complete setup.

### Check your file paths

A successful connection does not mean the media server can read your videos. For Plex, map NeXroll's paths to the paths visible inside Plex's own container or service. For example, `/data/prerolls` in NeXroll might be `/media/prerolls` in Plex.

Jellyfin and Emby plugins can use mapped local paths or download intros through NeXroll's streaming URL. Make sure the plugin can reach NeXroll and has access to its cache location.

Read the [path-mapping guide](docs/wiki/Path-Mappings.md) if the connection works but prerolls do not play.

## Start with one movie night

1. Connect your media server in **Connect**.
2. Add a few videos to **Library** and put them in a category.
3. Create a schedule, or use the category as your filler selection.
4. Start a movie from the beginning on your usual playback client and check the full preroll-to-movie flow.
5. Add sequences, seasonal schedules, or NeX-Up when you're ready.

## Updating and backups

Create a backup in **Settings > Backup & Restore** before updating.

On Windows, run the newer installer over your existing installation. For Docker:

```bash
docker compose pull
docker compose up -d
```

Keep your existing data volumes and media folders. See [backup and restore](docs/wiki/Backup-and-Restore.md) for moving an installation or restoring a backup.

## Help and documentation

- [Getting started](docs/wiki/Getting-Started.md)
- [Scheduling](docs/wiki/Scheduling.md) and [sequences](docs/wiki/Sequences.md)
- [NeX-Up](docs/wiki/NeX-Up.md)
- [External API](docs/wiki/API.md)
- [Troubleshooting](docs/wiki/Troubleshooting.md)
- [Building from source](docs/wiki/Building-from-Source.md)

For support, join [Discord](https://discord.gg/R9eH7TbxEk) or [r/NeXroll](https://www.reddit.com/r/NeXroll/). Report reproducible bugs through [GitHub Issues](https://github.com/JFLXCLOUD/NeXroll/issues), with your NeXroll version, installation type, media server and client versions, and relevant logs. Remove tokens and API keys before sharing.

## Support NeXroll

If NeXroll adds something to your movie nights, you can [support its development on Ko-fi](https://ko-fi.com/j_b__). Donations help support continued development and maintenance. Thank you to everyone who contributes, shares feedback, or helps other users get set up.

## License

NeXroll is released under the [MIT License](LICENSE). Third-party components and community media retain their own licenses and usage terms.
