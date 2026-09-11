# NeXroll app icons

The reusable icon is the glyph, with no wordmark. Exported files live in
`NeXroll/frontend/public/icons/` and are served at `/icons/` by NeXroll.
`assets/icons/nexroll-app-icons.zip` contains all exports for importing into other apps.

| File | Use |
| --- | --- |
| `nexroll-black-512.png` | Black glyph, transparent 512 x 512 canvas; light dashboards |
| `nexroll-white-512.png` | White glyph, transparent 512 x 512 canvas; dark dashboards |
| `nexroll-512.png` | Black glyph on white square; dashboards with unknown backgrounds |
| `nexroll-192.png` | Standard PWA icon |
| `nexroll-maskable-192.png`, `nexroll-maskable-512.png` | Opaque, padded icons for launcher masks |
| `apple-touch-icon.png` | Opaque 180 x 180 Apple home-screen icon |
| `nexroll.ico` | Multi-resolution Windows/browser icon, 16 through 256 pixels |

Black, white, and opaque PNGs are available at 16, 24, 32, 48, 64, 128,
192, 256, 512, and 1024 pixels. The wide logos remain suitable for headers.
The UI uses `nexroll-logo-black.png` and `nexroll-logo-white.png` from the same
public directory for the sidebar, sign-in screen, and onboarding. Their sources
are `assets/nexroll-logo-black.png` and `assets/nexroll-logo-white.png`; the original
wordmark pixels are preserved and only the adjacent icon has changed. These wide
logos are not launcher icons. `nexroll-master-white.png` is also available here
as a transparent white version of the square master.
The Unraid template uses the opaque 512-pixel icon; its GitHub URL will
resolve after these files are published to the main branch.

Rebuild exports on Windows from the repository root:

```powershell
./NeXroll/scripts/Build-AppIcons.ps1
```

Then run `npm run build` in `NeXroll/frontend` to include them in the app.
Existing installed shortcuts may need to be removed and added again to refresh
their operating-system icon cache.

Maskable artwork stays inside the [W3C maskable safe zone](https://www.w3.org/TR/appmanifest/#icon-masks).
The Apple icon follows [Apple's touch icon markup](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/ConfiguringWebApplications/ConfiguringWebApplications.html).

## Master provenance

`nexroll-master.png` was cleaned up from the supplied glyph using the built-in
imagegen tool. Export sizes and backgrounds are produced with System.Drawing.
Final generation prompt:

> Clean up the user's attached NeXroll glyph into a production app icon master. Preserve exactly the geometric stylized interlocked N/K-like glyph and squared open frame from the reference. Solid black geometric mark on a genuinely transparent background; remove the faint white edge artifacts. No full wordmark, no text, no shadows, no gradients, no new design. Square 1024x1024 canvas with mark centered and 10% transparent padding on all sides. Sharp clean edges, flat monochrome black silhouette. Output one image.

The generated master is 1254 x 1254; exports have the exact advertised sizes.
