# YouTube Music → NAS Downloader

Two pieces that work together:

1. **Userscript** (`userscript/yt-music-downloader.user.js`) — runs in Firefox via
   Tampermonkey/Greasemonkey on youtube.com + music.youtube.com. When you actually
   *listen* to a music video, it POSTs the video id to your NAS.
2. **Server** (`server/server.py`) — a tiny stdlib HTTP service that runs on your
   NAS, authenticates the request with a shared key, and hands the URL to
   `yt-dlp` to save as audio.

> Personal-archive use only. Downloading YouTube content conflicts with their
> ToS, so only run this against videos you have the right to archive (e.g.
> your own uploads, CC-licensed tracks, or private use of content you own).

## How it works

- The userscript watches for SPA navigation on YouTube. Once the `<video>`
  element has played for `minPlaybackSeconds` (default 5s), it checks the
  player metadata.
- If `microformat.category === "Music"` (or you're on `music.youtube.com`),
  it POSTs JSON to your NAS:
  ```json
  { "videoId": "dQw4w9WgXcQ", "title": "…", "author": "…", "durationSeconds": 213 }
  ```
- The server validates the video id, ignores the `url` field from the client,
  rebuilds `https://www.youtube.com/watch?v=<id>` itself, queues it, and a
  background worker runs `yt-dlp --extract-audio`.
- `yt-dlp --download-archive` makes re-runs idempotent — already-downloaded
  ids are skipped on the server side too, not just in the browser cache.

## Server setup (on your NAS)

```bash
# pick a location
sudo mkdir -p /srv/ytmd /srv/media/music/youtube
sudo cp server/server.py /srv/ytmd/
sudo pip install -r server/requirements.txt   # installs yt-dlp
# ffmpeg is required by yt-dlp's audio extraction:
sudo apt install ffmpeg                       # or: pacman -S ffmpeg, brew install ffmpeg, etc.
```

Run it directly to test:

```bash
YTMD_API_KEY='pick-a-long-random-string' \
YTMD_OUTPUT_DIR=/srv/media/music/youtube \
python3 /srv/ytmd/server.py
```

Or install the bundled systemd unit:

```bash
sudo cp server/ytmd.service /etc/systemd/system/
sudoedit /etc/systemd/system/ytmd.service     # set user, paths, API key
sudo systemctl daemon-reload
sudo systemctl enable --now ytmd
journalctl -u ytmd -f
```

Smoke-test it from the NAS itself:

```bash
curl -s http://localhost:8787/health
curl -s -X POST http://localhost:8787/download \
     -H 'Content-Type: application/json' \
     -H 'X-Api-Key: pick-a-long-random-string' \
     -d '{"videoId":"dQw4w9WgXcQ","title":"test"}'
```

### Environment variables

| Variable | Default | Notes |
|---|---|---|
| `YTMD_HOST` | `0.0.0.0` | Bind address |
| `YTMD_PORT` | `8787` | Listen port |
| `YTMD_API_KEY` | `change-me` | Must match the userscript |
| `YTMD_OUTPUT_DIR` | `./downloads` | Where files land |
| `YTMD_AUDIO_FORMAT` | `mp3` | `mp3`, `opus`, `m4a`, `flac`, … |
| `YTMD_AUDIO_QUALITY` | `0` | yt-dlp VBR quality (`0` = best) |
| `YTMD_YTDLP_BIN` | `yt-dlp` | Override if installed elsewhere |
| `YTMD_COOKIES_FILE` | — | Optional Netscape-format cookies for age-gated content |

## Browser setup

1. Install [Tampermonkey](https://www.tampermonkey.net/) (or Violentmonkey /
   Greasemonkey) in Firefox.
2. Open `userscript/yt-music-downloader.user.js` in Firefox and click
   **Install**. (Or paste its contents into a new Tampermonkey script.)
3. Open the Tampermonkey dashboard → this script → use the menu commands to set:
   - **Set NAS server URL** — e.g. `http://nas.local:8787/download`
   - **Set API key** — the same string as `YTMD_API_KEY`
4. Visit any music video and let it play for ~5 seconds. You should see a
   toast "Queued on NAS" and the download appear on disk.

### Exposing the NAS to the browser

The simplest setup is LAN-only: point the userscript at `http://nas.local:8787/download`
while your laptop is on the same network.

If you need HTTPS (e.g. Firefox blocks mixed content on `https://youtube.com`),
put the server behind a reverse proxy (Caddy, nginx, Traefik) with a cert from
your internal CA or Let's Encrypt, and point the userscript at the https URL.
The CORS headers are already permissive enough for the userscript to reach it.

## Troubleshooting

- **Nothing gets queued.** Open DevTools → Console on the YouTube tab. Look
  for `[yt-music-dl] send failed` — usually a wrong URL, wrong API key, or
  a mixed-content block (https page → http server).
- **Server logs show `yt-dlp not found`.** Install it in the same env the
  service runs under, or set `YTMD_YTDLP_BIN=/full/path/to/yt-dlp`.
- **Audio extraction fails.** Install `ffmpeg` on the NAS.
- **Re-downloads the same song.** The browser-side dedup is per-profile. The
  server-side `.downloaded-archive.txt` is the authoritative guard — don't
  delete it.
- **Non-music videos get queued.** Toggle "music-only filter" in the
  Tampermonkey menu back on. On `music.youtube.com` every video is treated
  as music because YouTube doesn't expose the category there.

## Layout

```
userscript/yt-music-downloader.user.js   # browser side
server/server.py                          # NAS side (stdlib only)
server/requirements.txt                   # yt-dlp
server/ytmd.service                       # example systemd unit
```
