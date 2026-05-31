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

1. `./build_data.py` to regenerate `data/posts.json`.
2. Bump `VERSION` in `sw.js` (e.g. `zoolog-v1` → `zoolog-v2`) and redeploy. The new
   service worker re-caches the updated files on next visit. (Without bumping, the
   app still self-updates one load later via stale-while-revalidate, but bumping
   makes the refresh immediate and clean.)
