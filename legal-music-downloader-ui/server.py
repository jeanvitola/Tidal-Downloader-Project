"""
AetherMusic + Djjio — Servidor Unificado Flask
Puerto 8000 | Búsqueda Tidal + Preparación de Sets DJ con IA
"""
import json
import os
import gc
import time
import subprocess
import sys
import shutil
import urllib.parse
import urllib.request as ureq
import numpy as np
from pathlib import Path
from flask import Flask, jsonify, render_template, send_file, request, abort, Response, send_from_directory

# ── Flask App ────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=str(Path(__file__).parent), template_folder=str(Path(__file__).parent))
BASE_DIR = Path(__file__).parent
INDEX_DIR = BASE_DIR / "index"

# ── FFmpeg helper ─────────────────────────────────────────────────────────────
def locate_ffmpeg_and_update_path():
    try:
        if shutil.which("ffmpeg"):
            print("[FFmpeg] Already found on PATH")
            return
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

# ── Active downloads tracking ─────────────────────────────────────────────────
ACTIVE_DOWNLOADS = {}

# ── Camelot Key Map ───────────────────────────────────────────────────────────
CAMELOT_MAP = {
    ('C', 'MAJOR'): '8B',  ('C#', 'MAJOR'): '3B',  ('DB', 'MAJOR'): '3B',
    ('D', 'MAJOR'): '10B', ('D#', 'MAJOR'): '5B',  ('EB', 'MAJOR'): '5B',
    ('E', 'MAJOR'): '12B', ('F', 'MAJOR'): '7B',   ('F#', 'MAJOR'): '2B',
    ('GB', 'MAJOR'): '2B', ('G', 'MAJOR'): '9B',   ('G#', 'MAJOR'): '4B',
    ('AB', 'MAJOR'): '4B', ('A', 'MAJOR'): '11B',  ('A#', 'MAJOR'): '6B',
    ('BB', 'MAJOR'): '6B', ('B', 'MAJOR'): '1B',   ('CB', 'MAJOR'): '1B',
    ('C', 'MINOR'): '5A',  ('C#', 'MINOR'): '12A', ('DB', 'MINOR'): '12A',
    ('D', 'MINOR'): '7A',  ('D#', 'MINOR'): '2A',  ('EB', 'MINOR'): '2A',
    ('E', 'MINOR'): '9A',  ('F', 'MINOR'): '4A',   ('F#', 'MINOR'): '11A',
    ('GB', 'MINOR'): '11A',('G', 'MINOR'): '6A',   ('G#', 'MINOR'): '1A',
    ('AB', 'MINOR'): '1A', ('A', 'MINOR'): '8A',   ('A#', 'MINOR'): '3A',
    ('BB', 'MINOR'): '3A', ('B', 'MINOR'): '10A',  ('CB', 'MINOR'): '10A',
}

def get_camelot_key(key, key_scale):
    if not key or not key_scale:
        return ""
    k = str(key).upper().strip().replace("SHARP", "#").replace("FLAT", "B")
    s = str(key_scale).upper().strip()
    return CAMELOT_MAP.get((k, s), "")

# ── Djjio In-memory cache ─────────────────────────────────────────────────────
_cache = {}

PALETTE = ["#C8A951","#5B8FA8","#C4603A","#7B6BA8","#4E9E6E",
           "#A85B6B","#6B9E4E","#5B7BA8","#A87B3A","#6B5BA8"]

def genre_color(generos_sorted):
    return {g: PALETTE[i % len(PALETTE)] for i, g in enumerate(generos_sorted)}

def get_library():
    if "library" not in _cache:
        lib_path = INDEX_DIR / "biblioteca.json"
        if not lib_path.exists():
            return []
        with open(lib_path, encoding="utf-8") as f:
            _cache["library"] = json.load(f)
    return _cache["library"]

def get_embeddings():
    if "embeddings" not in _cache:
        emb_path = INDEX_DIR / "embeddings.npy"
        if not emb_path.exists():
            return None
        _cache["embeddings"] = np.load(emb_path).astype("float32")
    return _cache["embeddings"]

def get_mulan_embeddings():
    if "mulan" not in _cache:
        path = INDEX_DIR / "mulan_embeddings.npy"
        if not path.exists():
            return None
        embs = np.load(path).astype("float32")
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        _cache["mulan"] = embs / (norms + 1e-8)
    return _cache["mulan"]

def camelot_compat(c1, c2):
    if c1 == "?" or c2 == "?": return 0.5
    if c1 == c2: return 1.0
    try:
        n1, l1 = int(c1[:-1]), c1[-1]
        n2, l2 = int(c2[:-1]), c2[-1]
    except Exception: return 0.5
    if n1 == n2: return 0.8
    diff = min(abs(n1 - n2), 12 - abs(n1 - n2))
    return 0.7 if l1 == l2 and diff == 1 else 0.0

def bpm_compat(b1, b2):
    if not b1 or not b2: return 0.5
    for r in (1.0, 2.0, 0.5):
        ratio = (b1 / b2) / r
        if abs(ratio - 1.0) <= 0.05: return 1.0
        if abs(ratio - 1.0) <= 0.10: return 0.7
    return 0.0

def build_graph_data(k=5):
    cache_key = f"graph_{k}"
    if cache_key in _cache:
        return _cache[cache_key]
    fichas = get_library()
    if not fichas:
        return {"nodes": [], "edges": []}
    embeddings = get_embeddings()
    if embeddings is None:
        return {"nodes": [], "edges": []}
    generos = sorted({f["genero"] for f in fichas})
    colors = genre_color(generos)
    n = len(fichas)
    sim = (embeddings @ embeddings.T).clip(-1, 1)
    nodes = [
        {"id": i, "name": Path(f["path"]).name,
         "title": f.get("title", Path(f["path"]).stem), "artist": f.get("artist", ""),
         "bpm": f["bpm"], "camelot": f["camelot"], "genero": f["genero"],
         "energy": f["energy"], "color": colors.get(f["genero"], "#888"),
         "artwork": f.get("artwork")}
        for i, f in enumerate(fichas)
    ]
    edges, seen = [], set()
    for i in range(n):
        scores = sorted([
            (0.5*float(sim[i,j]) + 0.3*camelot_compat(fichas[i]["camelot"], fichas[j]["camelot"])
             + 0.2*bpm_compat(fichas[i]["bpm"], fichas[j]["bpm"]), j)
            for j in range(n) if j != i
        ], reverse=True)
        for s, j in scores[:k]:
            key = (min(i,j), max(i,j))
            if key not in seen:
                seen.add(key)
                edges.append({"source": i, "target": j, "score": round(s, 3)})
    result = {"nodes": nodes, "edges": edges}
    _cache[cache_key] = result
    return result

# ── Tidal metadata injector ───────────────────────────────────────────────────
def inject_metadata(track_id):
    try:
        from tidal_mvp.cli import get_session
        s = get_session()
        t = s.track(track_id)
        t_key = getattr(t, 'key', None)
        t_scale = getattr(t, 'key_scale', None)
        camelot_key = get_camelot_key(t_key, t_scale)
        bpm = getattr(t, 'bpm', None)
        if not camelot_key and not bpm:
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
            return
        file_path = matching_files[0]
        if file_path.suffix == ".flac":
            from mutagen.flac import FLAC
            audio = FLAC(file_path)
            if camelot_key: audio["initialkey"] = camelot_key; audio["key"] = camelot_key
            if bpm: audio["bpm"] = str(bpm)
            audio.save()
        elif file_path.suffix in (".m4a", ".mp4"):
            from mutagen.mp4 import MP4
            audio = MP4(file_path)
            if bpm:
                try: audio["tmpo"] = [int(float(bpm))]
                except: pass
            if camelot_key:
                try: audio["----:com.apple.iTunes:initialkey"] = [camelot_key.encode('utf-8')]
                except: pass
            audio.save()
        elif file_path.suffix == ".mp3":
            from mutagen.easyid3 import EasyID3
            audio = EasyID3(file_path)
            if camelot_key: audio["initialkey"] = camelot_key
            if bpm: audio["bpm"] = str(bpm)
            audio.save()
    except Exception as e:
        print(f"[Metadata] Error: {e}")

# ════════════════════════════════════════════════════════════════════════════════
# RUTAS ESTÁTICAS — servir HTML/CSS/JS del frontend
# ════════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    safe = BASE_DIR / filename
    try:
        safe.relative_to(BASE_DIR)
    except ValueError:
        abort(403)
    if not safe.exists() or safe.is_dir():
        abort(404)
    return send_from_directory(BASE_DIR, filename)

# ════════════════════════════════════════════════════════════════════════════════
# API TIDAL — Búsqueda, descarga, preview, stream
# ════════════════════════════════════════════════════════════════════════════════

@app.route("/api/search")
def api_search_tidal():
    q_str = request.args.get("q", "").strip()
    if not q_str:
        return jsonify([])
    try:
        from tidal_mvp.cli import get_session
        s = get_session()
        if not s.check_login():
            return jsonify({"error": "Tidal session expired"}), 401
        res = s.search(q_str)
        tracks = res.get('tracks', [])
        output = []
        for t in tracks:
            dur_sec = getattr(t, 'duration', 0)
            minutes, seconds = dur_sec // 60, dur_sec % 60
            cover_url = ""
            try:
                if t.album: cover_url = t.album.image(320)
            except: pass
            if not cover_url:
                cover_url = "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80"
            t_key = getattr(t, 'key', None)
            t_scale = getattr(t, 'key_scale', None)
            camelot_key = get_camelot_key(t_key, t_scale)
            output.append({
                "id": str(t.id), "title": t.title,
                "artist": t.artist.name if t.artist else "Artista Desconocido",
                "album": t.album.name if t.album else "Álbum Desconocido",
                "duration": f"{minutes:02d}:{seconds:02d}",
                "cover": cover_url, "license": "user", "licenseText": "Catálogo Tidal",
                "qualities": [str(t.audio_quality), "MP3 320kbps"],
                "sizeMb": round(dur_sec * 0.15, 1),
                "camelotKey": camelot_key,
                "musicalKey": f"{t_key} {t_scale.capitalize()}" if t_key and t_scale else "",
                "bpm": getattr(t, 'bpm', 0)
            })
        return jsonify(output)
    except Exception as e:
        print("Search error:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/download")
def api_download():
    track_id = request.args.get("id")
    out_dir = request.args.get("out", str(Path.home() / "Music" / "TIDAL"))
    quality = request.args.get("quality", "lossless")
    if not track_id:
        return jsonify({"error": "Missing id"}), 400
    try:
        args = [sys.executable, "-m", "tidal_mvp", "dl",
                f"https://tidal.com/track/{track_id}", "--out", out_dir, "--quality", quality]
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ACTIVE_DOWNLOADS[track_id] = {"proc": proc, "tagged": False}
        return jsonify({"status": "started", "track_id": track_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/download/status")
def api_download_status():
    ids_str = request.args.get("ids", "")
    id_list = [i.strip() for i in ids_str.split(",") if i.strip()]
    output = {}
    for tid in id_list:
        if tid not in ACTIVE_DOWNLOADS:
            output[tid] = "unknown"
        else:
            info = ACTIVE_DOWNLOADS[tid]
            if not isinstance(info, dict):
                info = {"proc": info, "tagged": False}
                ACTIVE_DOWNLOADS[tid] = info
            exit_code = info["proc"].poll()
            if exit_code is None:
                output[tid] = "downloading"
            elif exit_code == 0:
                if not info["tagged"]:
                    inject_metadata(tid)
                    info["tagged"] = True
                output[tid] = "completed"
            else:
                output[tid] = "error"
    return jsonify(output)

@app.route("/api/preview")
def api_preview():
    track_id = request.args.get("id")
    if not track_id:
        return jsonify({"error": "Missing id"}), 400
    try:
        import tidalapi
        from tidal_mvp.cli import get_session
        s = get_session()
        s.audio_quality = getattr(tidalapi.Quality, 'low_320k', tidalapi.Quality.low_320k)
        t = s.track(track_id)
        st = t.get_stream()
        manifest = st.get_stream_manifest()
        urls = manifest.get_urls()
        if not urls:
            abort(404)
        url = str(urls[0])
        try:
            mime_type = manifest.get_mimetype() or "audio/mp4"
        except:
            mime_type = "audio/mp4"
        req = ureq.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
        with ureq.urlopen(req, timeout=20) as resp:
            content_length = resp.headers.get("Content-Length")
            def generate():
                while True:
                    chunk = resp.read(65536)
                    if not chunk: break
                    yield chunk
            headers = {"Content-Type": mime_type, "Accept-Ranges": "bytes"}
            if content_length:
                headers["Content-Length"] = content_length
            return Response(generate(), headers=headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stream")
def api_stream():
    track_id = request.args.get("id")
    if not track_id:
        return jsonify({"error": "Missing id"}), 400
    try:
        from tidal_mvp.cli import get_session
        s = get_session()
        t = s.track(track_id)
        def _sanitize(name):
            return "".join(c for c in name if c not in '<>:"/\\|?*')
        title_prefix = _sanitize(f"{t.artist.name} - {t.title}")
        out_dir = Path.home() / "Music" / "TIDAL"
        for ext in (".m4a", ".flac", ".mp4", ".ts"):
            path_check = out_dir / f"{title_prefix}{ext}"
            if path_check.exists() and path_check.stat().st_size > 0:
                ct = {"flac": "audio/flac", "m4a": "audio/mp4", "mp4": "audio/mp4"}.get(ext.lstrip("."), "audio/mpeg")
                return send_file(path_check, mimetype=ct)
        abort(404)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ════════════════════════════════════════════════════════════════════════════════
# API DJJIO — Sets de DJ, grafo de compatibilidad, búsqueda por mood
# ════════════════════════════════════════════════════════════════════════════════

@app.route("/api/dj/library")
def api_dj_library():
    """Devuelve la biblioteca analizada (biblioteca.json del índice Djjio)"""
    return jsonify(get_library())

@app.route("/api/dj/stats")
def api_dj_stats():
    """Estadísticas del set: total tracks, géneros, BPM range, etc."""
    fichas = get_library()
    if not fichas:
        return jsonify({"total": 0, "ready": False})
    bpms = [f["bpm"] for f in fichas if f.get("bpm")]
    generos = {}
    for f in fichas:
        generos[f["genero"]] = generos.get(f["genero"], 0) + 1
    return jsonify({
        "total": len(fichas),
        "ready": True,
        "bpm_min": round(min(bpms), 1) if bpms else 0,
        "bpm_max": round(max(bpms), 1) if bpms else 0,
        "generos": sorted(generos.items(), key=lambda x: -x[1]),
        "has_embeddings": (INDEX_DIR / "embeddings.npy").exists(),
        "has_mulan": (INDEX_DIR / "mulan_embeddings.npy").exists(),
    })

@app.route("/api/dj/graph")
def api_dj_graph():
    """Grafo de compatibilidad entre tracks (BPM + Camelot + embeddings)"""
    k = int(request.args.get("k", 5))
    return jsonify(build_graph_data(k=k))

@app.route("/api/dj/mood-search", methods=["POST"])
def api_dj_mood_search():
    """Búsqueda semántica por texto usando MuQ-MuLan"""
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    k = int(data.get("k", 10))
    if not query:
        return jsonify({"error": "query vacío"}), 400
    mulan_embs = get_mulan_embeddings()
    if mulan_embs is None:
        return jsonify({
            "error": "Índice MuLan no encontrado. Ejecuta build_mulan_index.py en djjio-dj-sets/ primero.",
            "setup_needed": True
        }), 503
    try:
        if "mulan_model" not in _cache:
            import torch
            from muq import MuQMuLan
            device = "cuda" if __import__("torch").cuda.is_available() else "cpu"
            _cache["mulan_model"] = MuQMuLan.from_pretrained("OpenMuQ/MuQ-MuLan-large").to(device).eval()
            _cache["mulan_device"] = device
        mulan = _cache["mulan_model"]
        device = _cache["mulan_device"]
        import torch
        with torch.no_grad():
            text_emb = mulan(texts=[query])
        text_vec = (text_emb / text_emb.norm(dim=-1, keepdim=True)).squeeze(0).cpu().numpy()
        sims = mulan_embs @ text_vec
        top_idx = np.argsort(sims)[::-1][:k]
        fichas = get_library()
        generos = sorted({f["genero"] for f in fichas})
        colors = genre_color(generos)
        results = [{
            "id": int(idx), "score": round(float(sims[idx]), 3),
            "title": fichas[idx].get("title", Path(fichas[idx]["path"]).stem),
            "artist": fichas[idx].get("artist", ""),
            "bpm": fichas[idx]["bpm"], "camelot": fichas[idx]["camelot"],
            "genero": fichas[idx]["genero"], "energy": fichas[idx]["energy"],
            "artwork": fichas[idx].get("artwork"),
            "color": colors.get(fichas[idx]["genero"], "#888"),
        } for idx in top_idx]
        return jsonify(results)
    except ImportError:
        return jsonify({
            "error": "Librería MuQ no instalada. Ejecuta: pip install muq torch librosa",
            "setup_needed": True
        }), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/dj/analyze", methods=["POST"])
def api_dj_analyze():
    """Lanza build_index.py (full IA) o build_index_lite.py (solo librosa) y transmite progreso SSE"""
    data = request.get_json() or {}
    folder = data.get("folder", "").strip()

    if not folder:
        return jsonify({"error": "Introduce la ruta de tu carpeta de musica."}), 400
    if not Path(folder).exists():
        return jsonify({"error": f"La carpeta no existe: {folder}"}), 400

    djjio_dir = BASE_DIR.parent / "djjio-dj-sets"
    script_full = djjio_dir / "build_index.py"
    script_lite = djjio_dir / "build_index_lite.py"

    # Verificar si tenemos las deps de IA completas
    ai_missing = []
    for lib in ("torch", "librosa"):
        try:
            __import__(lib)
        except ImportError:
            ai_missing.append(lib)

    # Verificar muq por separado (puede estar instalado pero roto)
    muq_ok = False
    try:
        import muq  # noqa
        muq_ok = True
    except Exception:
        ai_missing.append("muq")

    # Decidir que script usar
    if ai_missing or not script_full.exists():
        # Fallback: modo lite (solo librosa)
        script = script_lite
        mode = "lite"
        if not script_lite.exists():
            return jsonify({"error": "build_index_lite.py no encontrado. Reinstala el proyecto."}), 404
        # Verificar solo librosa para el modo lite
        try:
            import librosa  # noqa
        except ImportError:
            return jsonify({
                "error": "librosa no esta instalado.",
                "setup_needed": True,
                "install_cmd": "pip install librosa mutagen"
            }), 503
    else:
        script = script_full
        mode = "full"

    INDEX_DIR.mkdir(exist_ok=True)

    def generate():
        if mode == "lite":
            yield f"data: {json.dumps({'type':'info', 'msg': 'Modo lite (sin IA): solo librosa. BPM, clave Camelot, energia.'})}\n\n"
        else:
            yield f"data: {json.dumps({'type':'info', 'msg': 'Modo completo (IA): cargando modelos MuQ...'})}\n\n"

        yield f"data: {json.dumps({'type':'start', 'msg': f'Analizando: {folder}'})}\n\n"

        try:
            proc = subprocess.Popen(
                [sys.executable, str(script), folder, str(INDEX_DIR)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=str(djjio_dir),
                text=True, encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    yield f"data: {json.dumps({'type':'log', 'msg': line})}\n\n"
            proc.wait()
            if proc.returncode == 0:
                _cache.pop("library", None)
                _cache.pop("embeddings", None)
                for k in list(_cache):
                    if k.startswith("graph_"):
                        _cache.pop(k, None)
                yield f"data: {json.dumps({'type':'done', 'msg': 'Analisis completado exitosamente!'})}\n\n"
            else:
                yield f"data: {json.dumps({'type':'error', 'msg': f'El proceso termino con codigo {proc.returncode}. Revisa los logs.'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error', 'msg': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})



@app.route("/api/dj/reload", methods=["POST"])
def api_dj_reload():
    _cache.pop("library", None)
    _cache.pop("embeddings", None)
    _cache.pop("mulan", None)
    for key in list(_cache.keys()):
        if key.startswith("graph_"):
            _cache.pop(key, None)
    return jsonify({"ok": True, "message": "Caché del índice recargado"})

@app.route("/api/dj/clear", methods=["POST"])
def api_dj_clear():
    """Borra todos los archivos del índice para empezar de cero sin errores"""
    try:
        _cache.clear()
        if INDEX_DIR.exists():
            for p in INDEX_DIR.iterdir():
                if p.is_file():
                    try:
                        p.unlink()
                    except Exception:
                        pass
        return jsonify({"ok": True, "message": "Índice borrado completamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/dj/chapters")
def api_dj_chapters():
    """Retorna las canciones distribuidas en capítulos (Intro, Build, Peak, Cooldown) ordenadas armónicamente"""
    try:
        fichas = get_library()
        if not fichas:
            return jsonify({})
        
        # 1. Distancia Camelot
        def camelot_dist(c1, c2):
            if c1 == "?" or c2 == "?": return 6
            try:
                n1, l1 = int(c1[:-1]), c1[-1]
                n2, l2 = int(c2[:-1]), c2[-1]
            except: return 6
            if c1 == c2: return 0
            if n1 == n2: return 1
            diff = min(abs(n1 - n2), 12 - abs(n1 - n2))
            return diff if l1 == l2 else diff + 1

        # Camino greedy compatible armónica y con progresión de BPM ascendente
        def greedy_camelot_bpm_path(tracks_list):
            if not tracks_list: return []
            # Ordenar primero por BPM para empezar con la de menor velocidad
            remaining = sorted(tracks_list, key=lambda t: t["bpm"])
            path = [remaining.pop(0)]
            while remaining:
                last = path[-1]
                def get_cost(cand):
                    c_dist = camelot_dist(last["camelot"], cand["camelot"])
                    bpm_diff = cand["bpm"] - last["bpm"]
                    # Penalizar bajadas de BPM para favorecer progresión de menos a más
                    if bpm_diff >= 0:
                        bpm_cost = bpm_diff
                    else:
                        bpm_cost = abs(bpm_diff) * 6.0
                    return c_dist * 4.0 + bpm_cost
                
                best = min(remaining, key=get_cost)
                remaining.remove(best)
                path.append(best)
            return path

        # 2. Segmentar por energía normalizada
        energies = [t["energy"] for t in fichas]
        e_min, e_max = min(energies), max(energies)
        e_range = e_max - e_min or 1.0

        def norm(e):
            return (e - e_min) / e_range

        chapters = {"Intro": [], "Build": [], "Peak": [], "Cooldown": []}
        unassigned = []

        for idx, t in enumerate(fichas):
            t_with_idx = {**t, "idx": idx}
            ne = norm(t["energy"])
            assigned = False
            if ne <= 0.30:
                chapters["Intro"].append(t_with_idx)
                assigned = True
            if 0.20 <= ne <= 0.65:
                chapters["Build"].append(t_with_idx)
                assigned = True
            if ne >= 0.55:
                chapters["Peak"].append(t_with_idx)
                assigned = True
            if not assigned:
                unassigned.append(t_with_idx)

        for t in unassigned:
            ne = norm(t["energy"])
            centers = {"Intro": 0.15, "Build": 0.425, "Peak": 0.775, "Cooldown": 0.15}
            best = min(centers, key=lambda c: abs(centers[c] - ne))
            chapters[best].append(t)

        if len(chapters["Intro"]) > 2:
            intro_sorted = sorted(chapters["Intro"], key=lambda t: t["energy"])
            split = max(1, len(intro_sorted) // 2)
            chapters["Cooldown"] = intro_sorted[:split]
            chapters["Intro"] = intro_sorted[split:]

        # 3. Aplicar orden armonico y progresion de BPM por capitulo
        res = {}
        for name in ["Intro", "Build", "Peak", "Cooldown"]:
            res[name] = greedy_camelot_bpm_path(chapters[name])
            
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ── Servir audio del índice Djjio ─────────────────────────────────────────────
@app.route("/api/dj/audio/<int:track_id>")
def api_dj_audio(track_id):
    fichas = get_library()
    if track_id >= len(fichas):
        abort(404)
    path = Path(fichas[track_id]["path"])
    if not path.exists():
        abort(404)
    return send_file(path, conditional=True)

# ════════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    Path(Path.home() / "Music" / "TIDAL").mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(exist_ok=True)
    print("\n  AetherMusic + Djjio — Puerto 8000")
    print("  http://localhost:8000\n")
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
