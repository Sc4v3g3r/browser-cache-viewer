# Browser Cache Viewer

A lightweight web app for inspecting **Chrome/Chromium** and **Firefox** browser
cache files. It parses the on-disk cache formats, lists every cached resource
with its URL, timestamps and content type, and lets you preview or download the
original cached payload directly in the browser.

Built as a learning project in browser forensics — the same category of tooling
used in digital forensics and incident response to reconstruct a user's web
activity from local artifacts.


> own or are explicitly permitted to examine. See [Security notes](#security-notes).

---

## Features

- **Chrome & Chromium** — parses the Simple Cache format via the bundled
  [`ccl_chromium_reader`](https://github.com/cclgroupltd/ccl_chromium_reader).
- **Firefox** — parses the `cache2` on-disk format (metadata, headers, payload).
- **Automatic decompression** of `gzip`, `brotli` and `deflate` responses so
  previews show the real content.
- **Preview or download** any cached asset (images, HTML, JSON, etc.) with the
  correct MIME type.
- **Drag-and-drop a `.zip`** of a collected cache folder to analyse it without
  touching the live profile.
- **Modern single-page UI** (dark theme, no build step, plain HTML/CSS/JS).

## Tech stack

Python · Flask · `ccl_chromium_reader` · vanilla HTML/CSS/JS · Docker

---

## Project layout

```
browser-cache-viewer/
├── app.py                 # Flask app: routes + upload handling
├── cache_parser.py        # Chrome & Firefox cache parsing logic
├── templates/index.html   # Single-page front end
├── static/                # Static assets (currently empty)
├── ccl_chromium_reader/   # Vendored Chrome-cache reader (MIT, CCL Solutions Group)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Getting started

### Quickest: run the published image

No cloning, no build. Pull and run the container, then open the app and
**drag-and-drop a `.zip` of a browser cache folder** to analyse it:

```bash
docker pull sc4v3g3r/browser-cache-viewer
docker run --rm -p 5000:5000 sc4v3g3r/browser-cache-viewer:latest
```

Then open **http://127.0.0.1:5000** and use the upload panel.

To analyse a cache **already on your machine** (live analysis), mount it
read-only and point the app at it. On **Linux/macOS**:

```bash
docker run --rm -p 5000:5000 \
  -e CHROME_CACHE_DIR=/data/chromium/Default/Cache/Cache_Data \
  -e FIREFOX_CACHE_BASE=/data/firefox \
  -v "$HOME/.cache/chromium:/data/chromium:ro" \
  -v "$HOME/.cache/mozilla/firefox:/data/firefox:ro" \
  sc4v3g3r/browser-cache-viewer:latest
```

On **Windows (PowerShell)** — the drag-and-drop `.zip` upload is the simplest
route, but to mount live caches use the Windows paths:

```powershell
docker run --rm -p 5000:5000 -e CHROME_CACHE_DIR=/data/chromium/Cache_Data -v "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache\Cache_Data:/data/chromium/Cache_Data:ro" sc4v3g3r/browser-cache-viewer:latest
```

### 1. Run locally (Python)

Requires **Python 3.10+** and **git** (for one dependency).

```bash
# clone your repo, then:
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then edit paths for your machine (optional)
python app.py
```

Open **http://127.0.0.1:5000**.

### 2. Run with Docker

```bash
# Point these at your own browser caches, then bring it up:
HOST_CHROME_CACHE=~/.cache/chromium \
HOST_FIREFOX_CACHE=~/.cache/mozilla/firefox \
docker compose up --build
```

---

## Configuration

All settings come from environment variables (see `.env.example`):

| Variable             | Default                                          | Purpose                                        |
|----------------------|--------------------------------------------------|------------------------------------------------|
| `CHROME_CACHE_DIR`   | `~/.cache/chromium/Default/Cache/Cache_Data`     | Default Chrome cache dir shown in the UI        |
| `FIREFOX_CACHE_BASE` | `~/.cache/mozilla/firefox/`                       | Firefox profiles dir; auto-scanned for `cache2` |
| `HOST`               | `127.0.0.1`                                       | Interface to bind                              |
| `PORT`               | `5000`                                            | Port to bind                                   |
| `FLASK_DEBUG`        | `0`                                               | Flask debug mode (leave off outside dev)       |
| `MAX_UPLOAD_MB`      | `500`                                             | Max `.zip` upload size                          |

Typical cache locations:

- **Chrome (Linux):** `~/.config/google-chrome/Default/Cache/Cache_Data`
- **Chrome (macOS):** `~/Library/Caches/Google/Chrome/Default/Cache/Cache_Data`
- **Chrome (Windows):** `%LocalAppData%\Google\Chrome\User Data\Default\Cache\Cache_Data`
- **Firefox:** inside `<profile>/cache2/entries` under your OS Firefox profiles folder.

---

## Publishing updates to Docker Hub

After changing the code, rebuild and push a new image:

```bash
docker build -t sc4v3g3r/browser-cache-viewer:latest .
docker login
docker push sc4v3g3r/browser-cache-viewer:latest
```

---

## How it works

1. `CacheParser` detects whether a directory is a Chrome Simple Cache or a
   Firefox `cache2` store.
2. For **Chrome**, it delegates to `ccl_chromium_reader` to enumerate keys and
   read metadata + payloads.
3. For **Firefox**, it reads each cache file directly: locating the metadata
   block, parsing headers, and extracting the response body.
4. Content is decompressed when needed and served back to the browser with the
   right content type for inline preview or download.

---

## Security notes

This is a personal/analysis tool, not a hardened service. Before running it:

- **Bind to localhost.** The default `HOST` is `127.0.0.1`. Only expose it on a
  network you control, and never on the public internet.
- **The `dir` parameter reads arbitrary paths** on the host so you can point it
  at any cache location. That flexibility means you should not expose the app to
  untrusted users.
- **Keep `FLASK_DEBUG=0`** outside development — debug mode enables an
  interactive code-execution console.
- Uploaded archives are extracted with a **path-traversal (zip-slip) guard**.

---

## Credits & license

- This project's own code is released under the **MIT License** — see [`LICENSE`](LICENSE).
- Chrome cache parsing uses the vendored **`ccl_chromium_reader`** by
  [CCL Solutions Group](https://github.com/cclgroupltd/ccl_chromium_reader)
  (MIT). Its license is preserved in `ccl_chromium_reader/LICENSE`.
- Firefox `cache2` parsing is an original implementation informed by public
  documentation of the on-disk format.

Contributions and issues are welcome.
