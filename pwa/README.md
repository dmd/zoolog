# Zoolog PWA

A mobile-first, installable **Progressive Web App** for reading and searching the
family journal. Warm, book-like reading experience; full-text search; works fully
offline once loaded. **No backend** — it's a static site plus a JSON data bundle.

## How it works

```
build_data.py   reads ../posts/*.txt  →  data/posts.json (+ data/meta.json)
index.html      app shell
styles.css      warm & literary theme (light + dark)
app.js          feed, client-side full-text search, reader, routing
sw.js           service worker: offline app shell + data cache
manifest.webmanifest
icons/          app icons (generate_icons.py rebuilds the PNGs)
data/           generated bundle
```

`build_data.py` parses each entry: decodes quoted-printable, takes the date from
the filename, derives the author/category (A, D, Uncle J, AHNS, Grandpa) from the
filename, and stores the markdown body. The whole corpus (~3.2 MB across ~5,200
entries) ships as one JSON file. The app loads it once, builds an in-memory
inverted index for search, and caches everything for offline use.

### Reading

The source text is hard-wrapped at ~74 columns. The reader **re-flows** wrapped
prose into natural paragraphs (a line ≥ 64 chars is treated as a soft wrap), while
**preserving intentional line breaks** — list-style entries (early Uncle J) and
dialogue stay one line per line. Blank lines separate paragraphs.

### Search

- Type to filter; matches are highlighted.
- Prefix matching as you type (`pump` → `pumpkin`, `pumpkins`).
- Multiple words are AND-ed together.
- `"quoted phrases"` match the exact phrase.
- Author chips (All / Us / A / D / Uncle J / AHNS / Grandpa) scope results. The
  feed is always newest-first. Earlier/Later in the reader navigate within the
  current filtered/searched set, and Back returns to the feed in one step.

## Build

```bash
cd pwa
./build_data.py        # regenerate data/ after posts change (uses uv)
./generate_icons.py    # only needed if you change the icon (uses uv + Pillow)
```

## Run locally

It must be served over HTTP (not opened as a `file://`) for the service worker
and `fetch` to work:

```bash
cd pwa
python3 -m http.server 8123
# open http://localhost:8123
```

Tip: append `?nosw` to the URL during development to skip the service worker so
edits show up without cache fights (e.g. `http://localhost:8123/?nosw`).

## Deploy

Copy the entire `pwa/` directory to any static host (Netlify, GitHub Pages,
Cloudflare Pages, S3, a plain web server …). There is nothing to run server-side.
After deploying, open the site on a phone and use **Add to Home Screen** to install
it; it then launches full-screen and works offline.

### Updating after new entries

Just rebuild the data — `./build_data.py` (or run `../make_omnibus`, which does it
at the end). The service worker treats `data/` as **network-first**, so the new
bundle shows up the next time the app is loaded while online (a cheap `304` when
unchanged, a full fetch when rebuilt); the cached copy is only used offline. No
version bump needed for content changes.

### Updating the app itself (HTML/CSS/JS)

Bump `VERSION` in `sw.js` (e.g. `zoolog-v5` → `zoolog-v6`). The new service worker
installs, re-caches the shell, and takes over; reload once or twice to land on it.
(The shell is stale-while-revalidate, so it also self-heals one load later even
without a bump — the version bump just makes it immediate.)

## Persistent hosting (this Mac, over Tailscale)

This repo also runs the app as a tiny always-on server on the owner's Mac, reachable
from a phone over Tailscale. Two pieces:

- **`serve-daemon.sh`** — serves this directory on `127.0.0.1:8123` (localhost only,
  not exposed on the LAN) and re-asserts the Tailscale HTTPS proxy. It locates its
  own directory, so it has no hardcoded paths.
- **A macOS LaunchAgent** at `~/Library/LaunchAgents/org.dmd.zoolog-pwa.plist` (not in
  the repo — it's machine-specific and references the absolute project path). It runs
  `serve-daemon.sh` at login with `RunAtLoad` + `KeepAlive`, so it starts on boot and
  restarts if it ever dies. Logs go to `~/Library/Logs/zoolog-pwa.log`.

The public entry point is the Tailscale HTTPS URL, e.g.
`https://<machine>.<tailnet>.ts.net/`. Because Tailscale provides a trusted cert, the
PWA's secure-context features (service worker, install, offline) all work on the phone.

Manage it:

```bash
launchctl bootout   gui/$(id -u)/org.dmd.zoolog-pwa                       # stop + disable
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/org.dmd.zoolog-pwa.plist  # enable
launchctl kickstart -k gui/$(id -u)/org.dmd.zoolog-pwa                    # restart now
tailscale serve --https=443 off                                          # drop public proxy
```

> If you move the project folder, update the path inside the plist. `tailscaled`
> persists its own `serve` config across reboots; `serve-daemon.sh` re-asserts it
> anyway as a safety net.
