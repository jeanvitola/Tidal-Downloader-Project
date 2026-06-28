# app.py — Djjio Flask server
import json
import os
import gc
import time
import numpy as np
from pathlib import Path
from flask import Flask, jsonify, render_template, send_file, request, abort, Response

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
INDEX_DIR = BASE_DIR / "index"

# ── In-memory cache ───────────────────────────────────────────
_cache = {}

def get_library():
    if "library" not in _cache:
        with open(INDEX_DIR / "biblioteca.json", encoding="utf-8") as f:
            _cache["library"] = json.load(f)
    return _cache["library"]

def reload_library():
    _cache.pop("library", None)
    _cache.pop("graph", None)
    _cache.pop("scatter", None)
    return get_library()

def get_embeddings():
    if "embeddings" not in _cache:
        _cache["embeddings"] = np.load(INDEX_DIR / "embeddings.npy").astype("float32")
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

def get_hot_cues():
    path = INDEX_DIR / "hot_cues.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Compatibility helpers (no ML) ─────────────────────────────

PALETTE = ["#C8A951","#5B8FA8","#C4603A","#7B6BA8","#4E9E6E",
           "#A85B6B","#6B9E4E","#5B7BA8","#A87B3A","#6B5BA8"]

def genre_color(generos_sorted):
    return {g: PALETTE[i % len(PALETTE)] for i, g in enumerate(generos_sorted)}

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


# ── Graph computation ─────────────────────────────────────────

def build_graph_data(k=5):
    cache_key = f"graph_{k}"
    if cache_key in _cache:
        return _cache[cache_key]

    fichas = get_library()
    embeddings = get_embeddings()
    generos = sorted({f["genero"] for f in fichas})
    colors = genre_color(generos)
    n = len(fichas)
    sim = (embeddings @ embeddings.T).clip(-1, 1)

    nodes = [
        {
            "id": i,
            "name": Path(f["path"]).name,
            "title": f.get("title", Path(f["path"]).stem),
            "artist": f.get("artist", ""),
            "bpm": f["bpm"],
            "camelot": f["camelot"],
            "genero": f["genero"],
            "energy": f["energy"],
            "color": colors.get(f["genero"], "#888"),
            "artwork": f.get("artwork"),
        }
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


# ── Scatter / UMAP ────────────────────────────────────────────

def get_scatter_data():
    if "scatter" in _cache:
        return _cache["scatter"]

    coords_path = INDEX_DIR / "umap_coords.npy"
    fichas = get_library()
    generos = sorted({f["genero"] for f in fichas})
    colors = genre_color(generos)

    if coords_path.exists():
        coords = np.load(coords_path)
    else:
        import umap as umap_lib
        embs = get_embeddings()
        n = len(embs)
        reducer = umap_lib.UMAP(n_neighbors=min(15, max(2, n-1)), min_dist=0.1,
                                 n_components=2, metric="cosine", random_state=42)
        coords = reducer.fit_transform(embs)
        np.save(coords_path, coords)

    points = [
        {
            "id": i,
            "x": float(coords[i,0]), "y": float(coords[i,1]),
            "name": Path(f["path"]).name,
            "title": f.get("title", Path(f["path"]).stem),
            "artist": f.get("artist", ""),
            "bpm": f["bpm"], "camelot": f["camelot"],
            "genero": f["genero"], "energy": f["energy"],
            "color": colors.get(f["genero"], "#888"),
            "artwork": f.get("artwork"),
            "group": f.get("group"),
        }
        for i, f in enumerate(fichas)
    ]
    _cache["scatter"] = points
    return points


# ── Chapter computation ───────────────────────────────────────

def build_chapters(group=None, genero=None, min_bpm=0, max_bpm=9999):
    from chapter_builder import assign_chapters, greedy_camelot_path, CHAPTER_NAMES
    fichas = get_library()
    tracks = [
        {**f, "idx": i} for i, f in enumerate(fichas)
        if min_bpm <= f["bpm"] <= max_bpm
        and (genero is None or f["genero"] == genero)
        and (group is None or f.get("group") == group)
    ]
    if not tracks:
        return {}
    chapters = assign_chapters(tracks)
    for name in CHAPTER_NAMES:
        chapters[name] = greedy_camelot_path(chapters[name])
    out = {}
    for name in CHAPTER_NAMES:
        out[name] = [
            {"id": t["idx"], "title": t.get("title", Path(t["path"]).stem),
             "artist": t.get("artist",""), "bpm": t["bpm"],
             "camelot": t["camelot"], "genero": t["genero"],
             "energy": t["energy"], "artwork": t.get("artwork")}
            for t in chapters[name]
        ]
    return out


# ── Page routes ───────────────────────────────────────────────

@app.route("/")
def dashboard():
    fichas = get_library()
    bpms = [f["bpm"] for f in fichas if f["bpm"]]
    generos = {}
    for f in fichas:
        generos[f["genero"]] = generos.get(f["genero"], 0) + 1
    stats = {
        "total": len(fichas),
        "bpm_min": round(min(bpms), 1) if bpms else 0,
        "bpm_max": round(max(bpms), 1) if bpms else 0,
        "generos": sorted(generos.items(), key=lambda x: -x[1]),
        "has_artwork": sum(1 for f in fichas if f.get("artwork")),
        "has_hot_cues": (INDEX_DIR / "hot_cues.json").exists(),
        "has_mulan": (INDEX_DIR / "mulan_embeddings.npy").exists(),
        "has_groups": any(f.get("group") is not None for f in fichas),
    }
    return render_template("dashboard.html", stats=stats)

@app.route("/graph")
def graph():
    fichas = get_library()
    generos = sorted({f["genero"] for f in fichas})
    bpms = [f["bpm"] for f in fichas if f["bpm"]]
    return render_template("graph.html",
        generos=generos,
        bpm_min=int(min(bpms)) if bpms else 0,
        bpm_max=int(max(bpms))+1 if bpms else 200)

@app.route("/scatter")
def scatter():
    return render_template("scatter.html")

@app.route("/chapters")
def chapters():
    fichas = get_library()
    generos = sorted({f["genero"] for f in fichas})
    groups = sorted({f["group"] for f in fichas if f.get("group") is not None})
    bpms = [f["bpm"] for f in fichas if f["bpm"]]
    return render_template("chapters.html",
        generos=generos, groups=groups,
        bpm_min=int(min(bpms)) if bpms else 0,
        bpm_max=int(max(bpms))+1 if bpms else 200)

@app.route("/search")
def search():
    has_mulan = (INDEX_DIR / "mulan_embeddings.npy").exists()
    return render_template("search.html", has_mulan=has_mulan)

@app.route("/groups")
def groups_page():
    return render_template("groups.html")


# ── API routes ────────────────────────────────────────────────

@app.route("/api/graph")
def api_graph():
    k = int(request.args.get("k", 5))
    return jsonify(build_graph_data(k=k))

@app.route("/api/scatter")
def api_scatter():
    return jsonify(get_scatter_data())

@app.route("/api/chapters")
def api_chapters():
    group  = request.args.get("group")
    genero = request.args.get("genero")
    min_bpm = float(request.args.get("min_bpm", 0))
    max_bpm = float(request.args.get("max_bpm", 9999))
    group = int(group) if group else None
    genero = genero if genero else None
    data = build_chapters(group=group, genero=genero, min_bpm=min_bpm, max_bpm=max_bpm)
    return jsonify(data)

@app.route("/api/search", methods=["POST"])
def api_search():
    query = (request.json or {}).get("query", "").strip()
    k = int((request.json or {}).get("k", 10))
    if not query:
        return jsonify({"error": "query vacío"}), 400

    mulan_embs = get_mulan_embeddings()
    if mulan_embs is None:
        return jsonify({"error": "mulan_embeddings.npy no existe. Ejecuta build_mulan_index.py primero."}), 503

    # Lazy-load MuLan model
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

    results = [
        {
            "id": int(idx),
            "score": float(sims[idx]),
            "title": fichas[idx].get("title", Path(fichas[idx]["path"]).stem),
            "artist": fichas[idx].get("artist", ""),
            "bpm": fichas[idx]["bpm"],
            "camelot": fichas[idx]["camelot"],
            "genero": fichas[idx]["genero"],
            "energy": fichas[idx]["energy"],
            "artwork": fichas[idx].get("artwork"),
            "color": colors.get(fichas[idx]["genero"], "#888"),
        }
        for idx in top_idx
    ]
    return jsonify(results)

@app.route("/api/library")
def api_library():
    return jsonify(get_library())

@app.route("/api/reload", methods=["POST"])
def api_reload():
    reload_library()
    return jsonify({"ok": True})

@app.route("/audio/<int:track_id>")
def audio(track_id):
    fichas = get_library()
    if track_id >= len(fichas):
        abort(404)
    path = fichas[track_id]["path"]
    if not Path(path).exists():
        abort(404)
    return send_file(path, conditional=True)


if __name__ == "__main__":
    print("\n  Djjio corriendo en http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
