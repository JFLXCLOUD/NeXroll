# Path Mappings

Plex plays prerolls straight from its own disk. NeXroll writes the full path of each preroll into Plex's **Movie pre-roll video** setting, and Plex then opens that path on the computer Plex runs on. So the path has to be the one **Plex** uses for the file, not the one NeXroll uses.

Often they are the same and there is nothing to do. When they differ, a path mapping tells NeXroll how to turn its path into Plex's.

> **Plex only.** Jellyfin and Emby never need a NeXroll path mapping. Their NeXroll Intros plugin downloads each preroll from NeXroll over the network. See [Jellyfin and Emby](#jellyfin-and-emby).

---

## Do I need one?

| Your setup | Mapping needed? |
|---|---|
| Jellyfin or Emby only | No |
| NeXroll and Plex installed normally on the same computer | Usually no |
| NeXroll runs in Docker | Usually yes |
| NeXroll and Plex run on different computers | Yes |
| Prerolls live on a NAS or network share | Usually yes |

You don't have to work it out yourself. From 2.2.1, **Settings > Path Mappings** opens with **Can Plex open your prerolls?**, which asks your Plex server directly. If it says Plex can open all of them, you're done.

---

## The quick way (2.2.1)

1. Connect Plex under [Connect](Connect) with the Plex server owner's account.
2. Go to **Settings > Path Mappings** and click **Find it for me**. NeXroll looks through the folders your Plex server can see for the one holding your prerolls. It only proposes a folder after finding some of your actual preroll files in it, subfolders included.
3. Click **Add this mapping**.
4. Apply a schedule or category, then click **Check again** under **Can Plex open your prerolls?**

The first-run setup wizard offers the same **Find it for me** on its **Paths** step, which appears whenever Plex is connected. It works even before you have added any prerolls: NeXroll puts a small, clearly named test file in the folder, looks for it from Plex, and removes it.

If **Find it for me** can't find the folder, click **Browse Plex** next to a mapping's Plex path and pick the folder yourself. The list shows exactly what Plex can see. If you can't find your preroll folder there either, Plex can't reach it; see [Troubleshooting](#troubleshooting).

---

## How a mapping works

A mapping pairs two ways of naming the **same folder**:

| Folder as NeXroll sees it | Same folder as Plex sees it |
|---|---|
| `/data/prerolls` | `/Volumes/Plex/PreRoll` |

For every preroll inside that folder, NeXroll swaps the first part:

```
NeXroll:  /data/prerolls/Halloween/Evil Dead 2.m4v
Plex:     /Volumes/Plex/PreRoll/Halloween/Evil Dead 2.m4v
```

- **The longest match wins.** With mappings for both `/data/prerolls` and `/data/prerolls/Holiday`, a file in `Holiday` uses the second.
- **Whole folder names only.** From 2.2.1, a mapping for `/data/pre` no longer also catches `/data/prerolls2`.
- **Separators follow the Plex side.** If the Plex path uses `\`, the translated path does too, so `/data/prerolls` → `\\NAS\PreRoll` works.
- **Case.** On a Windows NeXroll, the NeXroll side ignores letter case. The Plex side must match exactly on a Linux Plex server, where `/data/Prerolls` and `/data/prerolls` are different folders.
- **No match means no change.** A path that matches no mapping is sent to Plex as it is. That's right when both see the same path, and wrong otherwise. From 2.2.1, NeXroll checks with Plex first; see [What NeXroll checks for you](#what-nexroll-checks-for-you).

NeX-Up trailers go to Plex the same way. If your trailer storage folder is outside the preroll folder, it needs its own mapping.

---

## Finding the two paths yourself

**The NeXroll side.** Look in **Settings > Storage > Preroll Storage Folder**. In Docker, this is the path **inside the container**, the right-hand side of your volume line:

```yaml
volumes:
  - /Volumes/Plex/PreRoll:/data/prerolls   # NeXroll sees /data/prerolls
```

**The Plex side.** This is the path **on the computer Plex runs on**, which can differ from the computer NeXroll runs on. Three ways to find it:

- **Browse Plex** on the Path Mappings page (2.2.1).
- In Plex Web, start adding a library and use **Browse for media folder**. That browser shows Plex's own view of the disk. Cancel once you've found the folder.
- On the Plex computer, open the folder and copy its path. Use Finder on a Mac (Option-right-click > Copy as Pathname), File Explorer on Windows, or `pwd` on Linux.

The most common mistake is filling in the Plex side with a path from the NeXroll computer.

---

## Setups

### Both installed on the same Windows PC

No mapping needed. Both see `C:\ProgramData\NeXroll\Prerolls`.

If the prerolls are on a network drive, see [Plex on Windows](#plex-on-windows) below: Plex may not see drive letters.

### NeXroll in Docker, Plex installed on the same computer

```yaml
# NeXroll's docker-compose.yml
volumes:
  - /mnt/user/prerolls:/data/prerolls
```

| Folder as NeXroll sees it | Same folder as Plex sees it |
|---|---|
| `/data/prerolls` | `/mnt/user/prerolls` |

The Plex side is the left-hand side of the volume line, because Plex runs directly on that host.

### Both in Docker on the same computer

Each container has its own path for the shared folder:

```yaml
nexroll:
  volumes:
    - /mnt/user/prerolls:/data/prerolls
plex:
  volumes:
    - /mnt/user/prerolls:/prerolls
```

| Folder as NeXroll sees it | Same folder as Plex sees it |
|---|---|
| `/data/prerolls` | `/prerolls` |

**Tip:** mount the folder at the **same path in both containers** (for example `/prerolls` in each, with NeXroll's preroll folder set to `/prerolls`) and no mapping is needed.

### Unraid

Both containers usually reach the same share under `/mnt/user/...`, but what matters is the path **inside** each container. Read both from the containers' volume settings in the Docker tab: use NeXroll's container path on the left and Plex's on the right. It's the same as [Both in Docker](#both-in-docker-on-the-same-computer).

### Different computers sharing a NAS

For example, NeXroll runs in Docker on one machine, Plex runs on another, and the prerolls live on a NAS both can reach. The NeXroll side is the container path. The Plex side is wherever **the Plex computer** mounts the share.

#### Plex on a Mac

macOS mounts a share at `/Volumes/<share name>`:

| Folder as NeXroll sees it | Same folder as Plex sees it |
|---|---|
| `/data/prerolls` | `/Volumes/Plex/PreRoll` |

- The name comes from the share, and the Plex Mac may name it differently from the NeXroll machine. If something else already used that name, macOS adds a number, such as `/Volumes/Plex-1`. Check on the Plex Mac itself.
- Plex Media Server must be allowed to read network volumes: **System Settings > Privacy & Security > Files & Folders** (or **Full Disk Access**) > Plex Media Server.
- The share must be mounted when Plex needs it. Add it to **Login Items** so it reconnects after a restart.

#### Plex on Windows

| Folder as NeXroll sees it | Same folder as Plex sees it |
|---|---|
| `/data/prerolls` | `\\NAS\PreRoll` |

Prefer the network path (`\\NAS\PreRoll`) to a mapped drive letter (`Z:\PreRoll`). Drive letters belong to one signed-in user, so Plex can't see them if it runs as a Windows service or under another account.

#### Plex on Linux

| Folder as NeXroll sees it | Same folder as Plex sees it |
|---|---|
| `/data/prerolls` | `/mnt/nas/prerolls` |

Use the mount point from the Plex machine's `/etc/fstab`. If Plex runs in Docker there, use the path inside Plex's container.

### NeXroll on Windows, Plex on another computer

A folder on the Windows PC, such as `C:\ProgramData\NeXroll\Prerolls`, only exists on that PC. Plex on another computer can't open it, whatever the mapping says. Move the prerolls to a share both can reach:

1. Set **Settings > Storage > Preroll Storage Folder** to the share, for example `\\NAS\PreRoll`. NeXroll can move your existing files there.
2. Map it to the path Plex uses for the same share:

| Folder as NeXroll sees it | Same folder as Plex sees it |
|---|---|
| `\\NAS\PreRoll` | `/mnt/nas/PreRoll` |

---

## What NeXroll checks for you

From 2.2.1, NeXroll asks Plex about the files before it changes Plex's preroll setting. It uses the folder browser that Plex Web uses when you add a library, so the answer comes from Plex's own point of view.

- **Plex can see every file:** they're applied as usual.
- **Plex can see some of them:** the files it can't see are left out, and **System health** on the dashboard names them.
- **Plex can see none of them:** Plex's current prerolls are left in place instead of being replaced with files Plex can't open, and System health reports an error.
- **The check can't run** (NeXroll isn't connected with the owner account, the Plex version doesn't support it, or the network timed out): the prerolls are applied exactly as before 2.2.1.

**Test Translation** on the Path Mappings page also shows whether Plex can open each translated path.

To switch the check off, set the environment variable `NEXROLL_PLEX_PATH_CHECK=0`.

---

## Jellyfin and Emby

No NeXroll path mapping is needed. When a movie starts, the NeXroll Intros plugin asks NeXroll which prerolls to play and downloads them to its own cache.

The plugin's settings in Jellyfin or Emby have an optional **path prefix** pair. If the preroll share is also mounted on the Jellyfin or Emby server, fill it in and the plugin reads the files directly instead of downloading them. Leave it empty and everything still works.

---

## Troubleshooting

The Path Mappings page and System health explain each file Plex can't open.

**"Plex has no folder …"**
The Plex side of the mapping points somewhere that doesn't exist on the Plex computer. Use **Browse Plex** to pick the real folder.

**"Plex has /data/Prerolls, not /data/prerolls"**
Only the letter case differs, and it matters on this Plex server. Correct the mapping's Plex side.

**"Plex can see the folder … but cannot read anything in it"**
The folder exists but Plex isn't allowed to read inside it. This is a permissions problem:
- **macOS:** give Plex Media Server access to network volumes (see [Plex on a Mac](#plex-on-a-mac)).
- **NAS:** make sure the account Plex uses, or the container's PUID/PGID, can read the share.
- **Windows:** make sure the account the Plex service runs as can read the share.

**"This is a Windows path, but Plex runs on Linux"** (or macOS)
No mapping matched, so Plex was sent a path from the Windows computer. Add a mapping, or see [NeXroll on Windows, Plex on another computer](#nexroll-on-windows-plex-on-another-computer).

**Find it for me can't find the folder**
Plex can't reach the preroll folder at all. Check that the share is mounted on the Plex computer and that Plex has permission to read it. Then try **Browse Plex** to see what Plex can reach.

**Plex can open everything, but nothing plays**
The paths are fine; check the Plex side:
- In the Plex app on your TV or phone, **Cinema Trailers** must be set to 1 or more. Recheck after an app update.
- Each movie library's **Advanced** settings must have **Enable Cinema Trailers** on.
- Not every Plex app plays prerolls, so try another device.
- On Apple TV, playback can fail when **Settings > Extras > Include Cinema Trailers from new and upcoming movies** is on. Try switching those options off.

**My files moved into category folders**
When a preroll's main category changes, NeXroll files it in that category's folder and gives Plex the new path, so playback isn't affected.

**The dashboard says "Plex connected" but prerolls don't play**
"Connected" only means NeXroll can talk to Plex. **Plex can open prerolls** in System health tells you whether Plex can open the files.
