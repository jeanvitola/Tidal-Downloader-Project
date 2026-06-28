# AetherMusic — Tidal Downloader PRO + Web UI

**AetherMusic** is a fork of [Tidal-Media-Downloader-PRO](https://github.com/yaronzz/Tidal-Media-Downloader-PRO) that adds a local web interface for searching, previewing, and downloading music from Tidal with automatic **BPM** and **Camelot Key** metadata injection — ideal for DJs and producers.

---

## Features

- **Web UI** — browser-based interface (`legal-music-downloader-ui`) served on `localhost:8000`
- **Search** — real-time Tidal catalog search with cover art, duration, and quality badges
- **Preview** — stream a track directly in the browser before downloading (proxied to avoid CORS)
- **Download** — background download via `tidal-dl` CLI; tracks saved to `~/Music/TIDAL/`
- **Camelot Key tagging** — automatically maps Tidal's `key` + `key_scale` to Camelot Wheel notation (e.g. `5A`, `12B`)
- **BPM metadata** — writes BPM to FLAC, M4A, and MP3 tags via `mutagen`
- **Multi-format support** — FLAC, M4A (AAC), MP3; quality selectable per download
- **Windows GUI** — original WPF desktop client (`TIDALDL-UI-PRO`) also included

---

## Project Structure

```
Tidal-Media-Downloader-PRO-1.2.1.10/
├── legal-music-downloader-ui/   # AetherMusic web UI (new)
│   ├── server.py                # Python HTTP server + REST API
│   ├── app.js                   # Frontend SPA logic
│   ├── index.html               # UI shell
│   └── style.css                # Styles
├── TIDALDL-UI-PRO/              # Original WPF Windows client
└── README.md
```

---

## Requirements

- Python 3.9+
- A valid **Tidal HiFi** subscription
- [`tidal-dl`](https://pypi.org/project/tidal-dl/) and `tidalapi` installed
- `mutagen` for metadata tagging
- `ffmpeg` (optional, for format conversion — auto-detected via WinGet on Windows)

---

## Installation

```bash
# 1. Install tidal-dl and dependencies
pip3 install tidal-dl tidalapi mutagen --upgrade

# 2. Log in to Tidal (first-time setup)
tidal-dl -l

# 3. Run the web server
cd legal-music-downloader-ui
python server.py
```

Then open `http://localhost:8000` in your browser.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/search?q=<query>` | Search Tidal catalog |
| GET | `/api/download?id=<track_id>&quality=<quality>` | Start background download |
| GET | `/api/download/status?ids=<id1,id2>` | Poll download status |
| GET | `/api/preview?id=<track_id>` | Stream audio preview |
| GET | `/api/stream?id=<track_id>` | Serve locally downloaded file |

**Quality values:** `lossless`, `high`, `low`

---

## Metadata Tagging

After a download completes, `server.py` automatically tags the file with:

| Tag | Format | Field |
|-----|--------|-------|
| Camelot Key | FLAC | `initialkey`, `key` |
| Camelot Key | M4A | `----:com.apple.iTunes:initialkey` |
| Camelot Key | MP3 | `initialkey` (EasyID3) |
| BPM | FLAC | `bpm` |
| BPM | M4A | `tmpo` |
| BPM | MP3 | `bpm` (EasyID3) |

Camelot notation is derived from Tidal's `key` and `key_scale` fields using a full 24-key map (major/minor).

---

## Disclaimer

- For **private use only**.
- Requires an active **Tidal HiFi** subscription.
- Do not use to distribute or pirate music.
- May be subject to legal restrictions in your country.

---

## Original Project

Based on [Tidal-Media-Downloader-PRO](https://github.com/yaronzz/Tidal-Media-Downloader-PRO) by [@yaronzz](https://github.com/yaronzz).
