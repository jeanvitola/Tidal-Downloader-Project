import http.server
import socketserver
import json
import urllib.parse
import subprocess
import sys
import os
from pathlib import Path
import shutil
from tidal_mvp.cli import get_session

def locate_ffmpeg_and_update_path():
    try:
        # Check if ffmpeg is already on PATH
        if shutil.which("ffmpeg"):
            print("[FFmpeg] Already found on PATH")
            return
            
        # Search in Microsoft WinGet Packages
        winget_path = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
        if winget_path.exists():
            ffmpeg_exes = list(winget_path.glob("**/ffmpeg.exe"))
            if ffmpeg_exes:
                ffmpeg_dir = str(ffmpeg_exes[0].parent)
                print(f"[FFmpeg] Located and adding to PATH: {ffmpeg_dir}")
                os.environ["PATH"] += os.pathsep + ffmpeg_dir
                return
        print("[FFmpeg] ffmpeg.exe not found in winget packages")
    except Exception as e:
        print(f"[FFmpeg] Error locating FFmpeg: {e}")

locate_ffmpeg_and_update_path()

PORT = 8000
ACTIVE_DOWNLOADS = {}  # track_id -> Popen object


# Camelot Key mappings (Musical Key, Scale -> Camelot Code)
CAMELOT_MAP = {
    # MAJOR (B)
    ('C', 'MAJOR'): '8B',
    ('C#', 'MAJOR'): '3B',
    ('DB', 'MAJOR'): '3B',
    ('D', 'MAJOR'): '10B',
    ('D#', 'MAJOR'): '5B',
    ('EB', 'MAJOR'): '5B',
    ('E', 'MAJOR'): '12B',
    ('F', 'MAJOR'): '7B',
    ('F#', 'MAJOR'): '2B',
    ('GB', 'MAJOR'): '2B',
    ('G', 'MAJOR'): '9B',
    ('G#', 'MAJOR'): '4B',
    ('AB', 'MAJOR'): '4B',
    ('A', 'MAJOR'): '11B',
    ('A#', 'MAJOR'): '6B',
    ('BB', 'MAJOR'): '6B',
    ('B', 'MAJOR'): '1B',
    ('CB', 'MAJOR'): '1B',

    # MINOR (A)
    ('C', 'MINOR'): '5A',
    ('C#', 'MINOR'): '12A',
    ('DB', 'MINOR'): '12A',
    ('D', 'MINOR'): '7A',
    ('D#', 'MINOR'): '2A',
    ('EB', 'MINOR'): '2A',
    ('E', 'MINOR'): '9A',
    ('F', 'MINOR'): '4A',
    ('F#', 'MINOR'): '11A',
    ('GB', 'MINOR'): '11A',
    ('G', 'MINOR'): '6A',
    ('G#', 'MINOR'): '1A',
    ('AB', 'MINOR'): '1A',
    ('A', 'MINOR'): '8A',
    ('A#', 'MINOR'): '3A',
    ('BB', 'MINOR'): '3A',
    ('B', 'MINOR'): '10A',
    ('CB', 'MINOR'): '10A',
}

def get_camelot_key(key, key_scale):
    if not key or not key_scale:
        return ""
    k = str(key).upper().strip()
    s = str(key_scale).upper().strip()
    # Normalize word representations of sharps/flats to symbols
    k = k.replace("SHARP", "#").replace("FLAT", "B")
    return CAMELOT_MAP.get((k, s), "")

def inject_metadata(track_id):
    try:
        s = get_session()
        t = s.track(track_id)
        
        t_key = getattr(t, 'key', None)
        t_scale = getattr(t, 'key_scale', None)
        camelot_key = get_camelot_key(t_key, t_scale)
        bpm = getattr(t, 'bpm', None)
        
        if not camelot_key and not bpm:
            print(f"[Metadata] No camelot key or bpm for track {track_id}")
            return
            
        def _sanitize(name):
            return "".join(c for c in name if c not in '<>:"/\\|?*')
        
        title_prefix = _sanitize(f"{t.artist.name} - {t.title}")
        out_dir = Path.home() / "Music" / "TIDAL"
        
        matching_files = []
        for ext in (".m4a", ".flac", ".mp3", ".mp4"):
            path_check = out_dir / f"{title_prefix}{ext}"
            if path_check.exists() and path_check.stat().st_size > 0:
                matching_files.append(path_check)
                
        if not matching_files:
            print(f"[Metadata] Downloaded file not found for track {track_id}")
            return
            
        file_path = matching_files[0]
        print(f"[Metadata] Tagging {file_path} with key={camelot_key}, bpm={bpm}")
        
        if file_path.suffix == ".flac":
            from mutagen.flac import FLAC
            audio = FLAC(file_path)
            if camelot_key:
                audio["initialkey"] = camelot_key
                audio["key"] = camelot_key
            if bpm:
                audio["bpm"] = str(bpm)
            audio.save()
            print(f"[Metadata] Successfully tagged FLAC: {file_path}")
            
        elif file_path.suffix in (".m4a", ".mp4"):
            from mutagen.mp4 import MP4
            audio = MP4(file_path)
            if bpm:
                try:
                    audio["tmpo"] = [int(float(bpm))]
                except Exception as e:
                    print("[Metadata] Error setting tmpo:", e)
            if camelot_key:
                try:
                    audio["----:com.apple.iTunes:initialkey"] = [camelot_key.encode('utf-8')]
                except Exception:
                    try:
                        audio["----:com.apple.iTunes:initialkey"] = [camelot_key]
                    except Exception as e:
                        print("[Metadata] Error setting M4A key:", e)
            audio.save()
            print(f"[Metadata] Successfully tagged M4A: {file_path}")
            
        elif file_path.suffix == ".mp3":
            from mutagen.easyid3 import EasyID3
            audio = EasyID3(file_path)
            if camelot_key:
                audio["initialkey"] = camelot_key
            if bpm:
                audio["bpm"] = str(bpm)
            audio.save()
            print(f"[Metadata] Successfully tagged MP3: {file_path}")
            
    except Exception as e:
        print(f"[Metadata] Error injecting metadata: {e}")



class HystericalServer(http.server.BaseHTTPRequestHandler):
    def end_headers(self):
        # Allow cross-origin requests just in case
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "OK")
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/search":
            self.handle_search(query)
        elif path == "/api/download":
            self.handle_download(query)
        elif path == "/api/download/status":
            self.handle_download_status(query)
        elif path == "/api/preview":
            self.handle_preview(query)
        elif path == "/api/stream":
            self.handle_stream(query)
        else:
            self.handle_static_file(path)

    def handle_static_file(self, path):
        if path == "/":
            path = "/index.html"
        
        # Static files directory is the same as server.py
        safe_path = Path(__file__).parent / path.lstrip("/")
        
        # Ensure path is inside root to prevent directory traversal attacks
        try:
            safe_path.relative_to(Path(__file__).parent)
        except ValueError:
            self.send_error(403, "Access Denied")
            return

        if not safe_path.exists() or safe_path.is_dir():
            self.send_error(404, "File Not Found")
            return

        # Determine MIME type
        content_type = "text/plain"
        if safe_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif safe_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif safe_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif safe_path.suffix == ".png":
            content_type = "image/png"
        elif safe_path.suffix == ".jpg" or safe_path.suffix == ".jpeg":
            content_type = "image/jpeg"
        elif safe_path.suffix == ".ico":
            content_type = "image/x-icon"

        try:
            data = safe_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(data))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {str(e)}")

    def handle_search(self, query):
        q_list = query.get('q', [''])
        q_str = q_list[0].strip()

        if not q_str:
            self.send_json([])
            return

        try:
            s = get_session()
            if not s.check_login():
                self.send_error(401, "Tidal API Session Expired or Not Logged In")
                return

            res = s.search(q_str)
            tracks = res.get('tracks', [])
            
            output = []
            for t in tracks:
                # Convert duration to MM:SS
                dur_sec = getattr(t, 'duration', 0)
                minutes = dur_sec // 60
                seconds = dur_sec % 60
                dur_str = f"{minutes:02d}:{seconds:02d}"

                # Handle album cover image
                cover_url = ""
                try:
                    if t.album:
                        cover_url = t.album.image(320)
                except Exception:
                    pass
                if not cover_url:
                    cover_url = "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80" # Fallback

                # License is user authorized catalog for real tracks
                license_type = "user"
                license_text = "Catálogo Tidal"

                # Check quality tags
                qual = str(t.audio_quality)
                
                # Fetch Camelot Key info
                t_key = getattr(t, 'key', None)
                t_scale = getattr(t, 'key_scale', None)
                camelot_key = get_camelot_key(t_key, t_scale)
                musical_key_str = f"{t_key} {t_scale.capitalize()}" if t_key and t_scale else ""
                
                output.append({
                    "id": str(t.id),
                    "title": t.title,
                    "artist": t.artist.name if t.artist else "Artista Desconocido",
                    "album": t.album.name if t.album else "Álbum Desconocido",
                    "duration": dur_str,
                    "cover": cover_url,
                    "license": license_type,
                    "licenseText": license_text,
                    "qualities": [qual, "MP3 320kbps"],
                    "sizeMb": round(dur_sec * 0.15, 1), # Simulated size
                    "camelotKey": camelot_key,
                    "musicalKey": musical_key_str,
                    "bpm": getattr(t, 'bpm', 0)
                })
            
            self.send_json(output)
        except Exception as e:
            print("Search error:", e)
            self.send_error(500, f"Error searching Tidal: {str(e)}")

    def handle_download(self, query):
        track_id = query.get('id', [None])[0]
        out_dir = query.get('out', [None])[0]
        quality = query.get('quality', ['lossless'])[0]

        if not track_id:
            self.send_error(400, "Missing 'id' parameter")
            return

        # Use default download directory if not specified
        if not out_dir:
            out_dir = str(Path.home() / "Music" / "TIDAL")

        try:
            # Start background process
            # Command: python -m tidal_mvp dl https://tidal.com/track/<id> --out "<out_dir>" --quality <quality>
            args = [
                sys.executable, "-m", "tidal_mvp", "dl",
                f"https://tidal.com/track/{track_id}",
                "--out", out_dir,
                "--quality", quality
            ]
            
            print(f"Running download: {' '.join(args)}")
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Save Popen reference and tag status
            ACTIVE_DOWNLOADS[track_id] = {
                "proc": proc,
                "tagged": False
            }
            
            self.send_json({"status": "started", "track_id": track_id})
        except Exception as e:
            self.send_error(500, f"Failed to start download: {str(e)}")

    def handle_download_status(self, query):
        track_ids = query.get('ids', [''])
        id_list = [i.strip() for i in track_ids[0].split(',') if i.strip()]

        output = {}
        for tid in id_list:
            if tid not in ACTIVE_DOWNLOADS:
                output[tid] = "unknown"
            else:
                info = ACTIVE_DOWNLOADS[tid]
                if isinstance(info, dict):
                    proc = info["proc"]
                else:
                    proc = info
                    info = {"proc": proc, "tagged": False}
                    ACTIVE_DOWNLOADS[tid] = info
                
                exit_code = proc.poll()
                if exit_code is None:
                    output[tid] = "downloading"
                elif exit_code == 0:
                    if not info["tagged"]:
                        inject_metadata(tid)
                        info["tagged"] = True
                    output[tid] = "completed"
                else:
                    output[tid] = "error"

        self.send_json(output)

    def handle_preview(self, query):
        track_id = query.get('id', [None])[0]
        if not track_id:
            self.send_error(400, "Missing 'id' parameter")
            return
        
        try:
            import tidalapi
            import urllib.request as ureq

            s = get_session()
            s.audio_quality = getattr(tidalapi.Quality, 'low_320k', tidalapi.Quality.low_320k)
            t = s.track(track_id)
            st = t.get_stream()
            manifest = st.get_stream_manifest()
            urls = manifest.get_urls()
            
            if not urls:
                self.send_error(404, "Preview URL not available")
                return
                
            url = str(urls[0])
            print(f"[Preview] Proxying audio for track {track_id}: {url[:80]}...")

            # Detect MIME type from manifest or fallback to audio/mp4
            try:
                mime_type = manifest.get_mimetype() or "audio/mp4"
            except Exception:
                mime_type = "audio/mp4"

            # Proxy the audio bytes directly (avoids browser CORS blocks on CDN redirects)
            req = ureq.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "*/*",
            })
            with ureq.urlopen(req, timeout=20) as resp:
                content_length = resp.headers.get("Content-Length")
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Accept-Ranges", "bytes")
                if content_length:
                    self.send_header("Content-Length", content_length)
                self.end_headers()
                # Stream in chunks
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except BrokenPipeError:
                        break

        except Exception as e:
            print(f"[Preview] Error: {e}")
            self.send_error(500, f"Error getting preview: {str(e)}")

    def handle_stream(self, query):
        track_id = query.get('id', [None])[0]
        if not track_id:
            self.send_error(400, "Missing 'id' parameter")
            return
            
        try:
            s = get_session()
            t = s.track(track_id)
            
            def _sanitize(name):
                return "".join(c for c in name if c not in '<>:"/\\|?*')
            
            title_prefix = _sanitize(f"{t.artist.name} - {t.title}")
            out_dir = Path.home() / "Music" / "TIDAL"
            
            matching_files = []
            for ext in (".m4a", ".flac", ".mp4", ".ts"):
                path_check = out_dir / f"{title_prefix}{ext}"
                if path_check.exists() and path_check.stat().st_size > 0:
                    matching_files.append(path_check)
            
            if not matching_files:
                self.send_error(404, "Audio file not downloaded or not found locally")
                return
                
            file_path = matching_files[0]
            data = file_path.read_bytes()
            
            content_type = "audio/mpeg"
            if file_path.suffix == ".flac":
                content_type = "audio/flac"
            elif file_path.suffix in (".m4a", ".mp4"):
                content_type = "audio/mp4"
            elif file_path.suffix == ".ts":
                content_type = "video/MP2T"
                
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(data))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f"Error streaming audio: {str(e)}")

    def send_json(self, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    # Ensure background folder exists
    Path(Path.home() / "Music" / "TIDAL").mkdir(parents=True, exist_ok=True)
    
    # Run server
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), HystericalServer) as httpd:
        print(f"Serving Legal Music Downloader hybrid API/Web at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
