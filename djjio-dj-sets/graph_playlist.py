# graph_playlist.py
import json
import argparse
from pathlib import Path
import numpy as np

INDEX_DIR = Path("index")
OUT_HTML = "graph_playlist.html"


def camelot_compat(c1, c2):
    if c1 == "?" or c2 == "?":
        return 0.5
    if c1 == c2:
        return 1.0
    try:
        n1, l1 = int(c1[:-1]), c1[-1]
        n2, l2 = int(c2[:-1]), c2[-1]
    except (ValueError, IndexError):
        return 0.5
    if n1 == n2:
        return 0.8
    diff = min(abs(n1 - n2), 12 - abs(n1 - n2))
    if l1 == l2 and diff == 1:
        return 0.7
    return 0.0


def bpm_compat(b1, b2):
    if not b1 or not b2:
        return 0.5
    for r in (1.0, 2.0, 0.5):
        ratio = (b1 / b2) / r
        if abs(ratio - 1.0) <= 0.05:
            return 1.0
        if abs(ratio - 1.0) <= 0.10:
            return 0.7
    return 0.0


def build_graph(embeddings, fichas, k=5):
    n = len(fichas)
    sim = (embeddings @ embeddings.T).clip(-1, 1)

    nodes = [
        {
            "id": i,
            "name": Path(f["path"]).name,
            "path": f["path"],
            "bpm": f["bpm"],
            "camelot": f["camelot"],
            "genero": f["genero"],
            "energy": f["energy"],
            "artwork": f.get("artwork", None),
            "artist": f.get("artist", ""),
            "title": f.get("title", Path(f["path"]).stem),
        }
        for i, f in enumerate(fichas)
    ]

    edges = []
    seen = set()

    for i in range(n):
        scores = [
            (
                0.5 * float(sim[i, j])
                + 0.3 * camelot_compat(fichas[i]["camelot"], fichas[j]["camelot"])
                + 0.2 * bpm_compat(fichas[i]["bpm"], fichas[j]["bpm"]),
                j,
            )
            for j in range(n)
            if j != i
        ]
        scores.sort(reverse=True)
        for s, j in scores[:k]:
            key = (min(i, j), max(i, j))
            if key not in seen:
                seen.add(key)
                edges.append({"source": i, "target": j, "score": round(s, 3)})

    return nodes, edges


def generar_html(nodes, edges):
    generos = sorted({n["genero"] for n in nodes})
    bpms = [n["bpm"] for n in nodes if n["bpm"]]
    bpm_min = int(min(bpms)) if bpms else 0
    bpm_max = int(max(bpms)) + 1 if bpms else 200

    palette = [
        "#C8A951", "#5B8FA8", "#C4603A", "#7B6BA8", "#4E9E6E",
        "#A85B6B", "#6B9E4E", "#5B7BA8", "#A87B3A", "#6B5BA8",
    ]
    color_de = {g: palette[i % len(palette)] for i, g in enumerate(generos)}
    for n in nodes:
        n["color"] = color_de[n["genero"]]

    genre_pills = " ".join(
        f'<button class="gpill active" data-genre="{g}" style="--gc:{color_de[g]}">{g}</button>'
        for g in generos
    )

    template = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Graph Playlist · Djjio</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #000; color: #e0e0e0; font-family: system-ui, sans-serif; height: 100vh; overflow: hidden; display: flex; flex-direction: column; }

#topbar {
  display: flex; align-items: center; gap: 16px;
  padding: 10px 18px; background: rgba(0,0,0,0.92);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  flex-shrink: 0; flex-wrap: wrap; z-index: 10;
}
#topbar .logo { font-size: 13px; font-weight: 700; letter-spacing: 1px; color: #fff; margin-right: 4px; }
.sep { width: 1px; height: 18px; background: rgba(255,255,255,0.1); }
.filter-group { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.filter-group label { font-size: 11px; color: #444; text-transform: uppercase; letter-spacing: .6px; }
.filter-group input[type=number] {
  width: 58px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
  border-radius: 4px; color: #ccc; padding: 3px 7px; font-size: 12px;
}
.filter-group input[type=number]:focus { outline: none; border-color: rgba(255,255,255,0.3); }
#genre-filters { display: flex; gap: 6px; flex-wrap: wrap; }
.gpill {
  font-size: 11px; padding: 3px 10px; border-radius: 20px; cursor: pointer;
  border: 1px solid var(--gc); color: var(--gc); background: transparent;
  transition: background .15s, color .15s; white-space: nowrap;
}
.gpill.active { background: var(--gc); color: #000; }

#graph { flex: 1; position: relative; overflow: hidden; }
svg { width: 100%; height: 100%; display: block; }

.link { stroke: rgba(255,255,255,0.08); fill: none; transition: opacity .2s; }
.link.highlighted { stroke: rgba(255,255,255,0.45); stroke-width: 1.5 !important; }
.link.dimmed { opacity: 0.02; }

.node { cursor: pointer; }
.node image { transition: opacity .2s; }
.node circle.shadow { fill: rgba(0,0,0,0.5); }
.node circle.border { fill: none; stroke: rgba(255,255,255,0.2); stroke-width: 1.5; transition: stroke .2s, stroke-width .2s, opacity .2s; }
.node circle.ring  { fill: none; stroke: #fff; stroke-width: 2.5; opacity: 0; transition: opacity .25s; }
.node circle.pulse { fill: none; stroke: rgba(255,255,255,0.5); stroke-width: 1.5; opacity: 0; }
.node.selected circle.ring { opacity: 1; }
.node.playing  circle.ring { opacity: 1; }
.node.playing  circle.pulse { animation: ripple 1.8s ease-out infinite; }
.node.dimmed image { opacity: 0.07; }
.node.dimmed circle.border { opacity: 0.07; }
.node.dimmed circle.ring   { opacity: 0 !important; }
.node.dimmed text { opacity: 0.06; }
.node text { pointer-events: none; }
.node text.ln  { font-size: 10px; fill: rgba(255,255,255,0.5); text-anchor: middle; }
.node text.lart { font-size: 9px; fill: rgba(255,255,255,0.28); text-anchor: middle; }

/* Camelot badge */
.node .badge rect { rx: 4; fill: rgba(0,0,0,0.72); }
.node .badge text { font-size: 9px; font-weight: 700; fill: #fff; text-anchor: middle; dominant-baseline: central; }

@keyframes ripple {
  0%   { opacity: 0.55; }
  100% { opacity: 0; }
}

/* Info card */
#infocard {
  position: absolute; top: 16px; right: 16px; width: 230px;
  background: rgba(6,6,6,0.94); border: 1px solid rgba(255,255,255,0.09);
  border-radius: 12px; overflow: hidden; display: none; backdrop-filter: blur(16px);
}
#infocard.visible { display: block; }
#ic-art { width: 100%; aspect-ratio: 1; object-fit: cover; display: block; }
#ic-body { padding: 14px; }
#ic-title  { font-size: 13px; font-weight: 600; color: #fff; margin-bottom: 2px; word-break: break-word; line-height: 1.3; }
#ic-artist { font-size: 11px; color: #555; margin-bottom: 10px; }
.ic-row { color: #555; margin: 4px 0; display: flex; justify-content: space-between; font-size: 12px; }
.ic-row span:last-child { color: #aaa; }
.ic-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }
.ic-play {
  margin-top: 12px; width: 100%; padding: 8px; border: none; border-radius: 7px;
  background: rgba(255,255,255,0.1); color: #fff; font-size: 12px; cursor: pointer;
  transition: background .15s;
}
.ic-play:hover { background: rgba(255,255,255,0.18); }

/* Player bar */
#playerbar {
  display: flex; align-items: center; gap: 18px;
  padding: 0 20px; height: 68px; flex-shrink: 0;
  background: rgba(5,5,5,0.98); border-top: 1px solid rgba(255,255,255,0.07);
  z-index: 20;
}
#pl-art { width: 42px; height: 42px; border-radius: 6px; object-fit: cover; flex-shrink: 0; background: #111; }
#pl-info { min-width: 0; width: 200px; flex-shrink: 0; }
#pl-title  { font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #ddd; }
#pl-artist { font-size: 11px; color: #444; margin-top: 2px; }
#pl-controls { display: flex; align-items: center; gap: 10px; }
#pl-controls button {
  background: none; border: none; color: #666; cursor: pointer; font-size: 15px;
  padding: 4px; border-radius: 4px; transition: color .15s; display: flex; align-items: center;
}
#pl-controls button:hover { color: #fff; }
#pl-play { width: 38px; height: 38px; border-radius: 50% !important;
  background: #fff !important; color: #000 !important; font-size: 14px !important;
  justify-content: center !important; padding: 0 !important; line-height: 1; }
#pl-play:hover { background: #ddd !important; }
#pl-progress-wrap { flex: 1; display: flex; align-items: center; gap: 10px; min-width: 0; }
#pl-time { font-size: 11px; color: #444; white-space: nowrap; min-width: 90px; text-align: center; }
#pl-bar {
  flex: 1; height: 3px; background: rgba(255,255,255,0.1); border-radius: 2px;
  cursor: pointer;
}
#pl-fill { height: 100%; background: #fff; border-radius: 2px; width: 0%; pointer-events: none; transition: width .1s linear; }
#pl-vol { width: 70px; accent-color: #666; cursor: pointer; }
</style>
</head><body>

<div id="topbar">
  <span class="logo">DJJIO</span>
  <div class="sep"></div>
  <div class="filter-group">
    <label>BPM</label>
    <input type="number" id="bpmMin" value="__BPM_MIN__">
    <span style="color:#333">—</span>
    <input type="number" id="bpmMax" value="__BPM_MAX__">
  </div>
  <div class="sep"></div>
  <div class="filter-group">
    <label>Géneros</label>
    <div id="genre-filters">__GENRE_PILLS__</div>
  </div>
</div>

<div id="graph">
  <div id="infocard">
    <img id="ic-art" src="" alt="">
    <div id="ic-body">
      <div id="ic-title">—</div>
      <div id="ic-artist">—</div>
      <div class="ic-row"><span>Camelot</span><span id="ic-camelot">—</span></div>
      <div class="ic-row"><span>BPM</span><span id="ic-bpm">—</span></div>
      <div class="ic-row"><span>Energía</span><span id="ic-energy">—</span></div>
      <div class="ic-row"><span>Género</span><span id="ic-genre">—</span></div>
      <button class="ic-play" id="ic-play-btn">&#9654; Reproducir</button>
    </div>
  </div>
</div>

<div id="playerbar">
  <img id="pl-art" src="" alt="">
  <div id="pl-info">
    <div id="pl-title">Sin track</div>
    <div id="pl-artist">—</div>
  </div>
  <div id="pl-controls">
    <button id="pl-prev" title="Anterior">&#9664;&#9664;</button>
    <button id="pl-play" title="Play / Pause">&#9654;</button>
    <button id="pl-next" title="Siguiente compatible">&#9654;&#9654;</button>
  </div>
  <div id="pl-progress-wrap">
    <span id="pl-time">0:00 / 0:00</span>
    <div id="pl-bar"><div id="pl-fill"></div></div>
    <input type="range" id="pl-vol" min="0" max="1" step="0.01" value="0.8" title="Volumen">
  </div>
</div>

<audio id="audio"></audio>

<script>
const NODES = __NODES__;
const EDGES = __EDGES__;

const graphEl = document.getElementById('graph');
let W = graphEl.clientWidth, H = graphEl.clientHeight;

const svg = d3.select('#graph').append('svg');
const zoomG = svg.append('g');
svg.call(d3.zoom().scaleExtent([0.08, 8]).on('zoom', e => zoomG.attr('transform', e.transform)));

const R = d => 26 + d.energy * 14;

const defs = svg.append('defs');

// Clip paths circulares por nodo
NODES.forEach(d => {
  defs.append('clipPath').attr('id', 'clip_' + d.id)
    .append('circle').attr('r', R(d));
});

// Sombra difusa
const filter = defs.append('filter').attr('id', 'shadow').attr('x','-30%').attr('y','-30%').attr('width','160%').attr('height','160%');
filter.append('feDropShadow').attr('dx',0).attr('dy',2).attr('stdDeviation',6).attr('flood-color','rgba(0,0,0,0.8)');

const sim = d3.forceSimulation(NODES)
  .force('link', d3.forceLink(EDGES).id(d => d.id).distance(d => 200 - d.score * 130).strength(0.42))
  .force('charge', d3.forceManyBody().strength(-500))
  .force('center', d3.forceCenter(W / 2, H / 2))
  .force('collision', d3.forceCollide(d => R(d) + 10));

const linkSel = zoomG.append('g').selectAll('line')
  .data(EDGES).join('line').attr('class', 'link')
  .attr('stroke-width', d => Math.max(0.5, d.score * 2.5));

const nodeSel = zoomG.append('g').selectAll('g')
  .data(NODES).join('g').attr('class', 'node')
  .call(d3.drag()
    .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
    .on('end',   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

// Sombra detrás
nodeSel.append('circle').attr('class','shadow').attr('r', d => R(d) + 3).attr('filter','url(#shadow)');

// Imagen circular de portada
nodeSel.append('image')
  .attr('href', d => d.artwork || '')
  .attr('x', d => -R(d)).attr('y', d => -R(d))
  .attr('width', d => R(d) * 2).attr('height', d => R(d) * 2)
  .attr('clip-path', d => 'url(#clip_' + d.id + ')')
  .attr('preserveAspectRatio', 'xMidYMid slice');

// Borde del círculo
nodeSel.append('circle').attr('class','border').attr('r', R);

// Anillo de selección/reproducción
nodeSel.append('circle').attr('class','ring').attr('r', d => R(d) + 5);

// Pulso animado (playing)
nodeSel.append('circle').attr('class','pulse').attr('r', d => R(d) + 12);

// Badge Camelot (esquina inferior derecha)
const badge = nodeSel.append('g').attr('class','badge');
badge.append('rect')
  .attr('x', d => R(d) * 0.45).attr('y', d => R(d) * 0.45)
  .attr('width', 22).attr('height', 14).attr('rx', 4)
  .attr('fill', d => d.color + 'cc');
badge.append('text')
  .attr('x', d => R(d) * 0.45 + 11).attr('y', d => R(d) * 0.45 + 7)
  .attr('font-size', 9).attr('font-weight', 700).attr('fill', '#fff')
  .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
  .text(d => d.camelot);

// Label nombre (debajo)
nodeSel.append('text').attr('class','ln').attr('dy', d => R(d) + 14)
  .text(d => (d.title || d.name.replace(/\\.[^.]+$/, '')).slice(0, 22));
nodeSel.append('text').attr('class','lart').attr('dy', d => R(d) + 25)
  .text(d => d.artist ? d.artist.slice(0, 20) : '');

sim.on('tick', () => {
  linkSel.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
         .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  nodeSel.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
});

// ── State ────────────────────────────────────────────────────
let selectedId = null, playingId = null, history = [];

const adj = {};
NODES.forEach(n => { adj[n.id] = []; });
EDGES.forEach(e => {
  const s = typeof e.source === 'object' ? e.source.id : e.source;
  const t = typeof e.target === 'object' ? e.target.id : e.target;
  adj[s].push({id: t, score: e.score});
  adj[t].push({id: s, score: e.score});
});
Object.values(adj).forEach(a => a.sort((x, y) => y.score - x.score));
function nodeById(id) { return NODES.find(n => n.id === id); }

// ── Highlight ────────────────────────────────────────────────
function highlightNode(id) {
  const conn = new Set([id]);
  adj[id].forEach(a => conn.add(a.id));
  nodeSel.classed('selected', d => d.id === id && d.id !== playingId)
         .classed('playing',  d => d.id === playingId)
         .classed('dimmed',   d => !conn.has(d.id));
  linkSel.classed('highlighted', e => {
    const s = typeof e.source === 'object' ? e.source.id : e.source;
    const t = typeof e.target === 'object' ? e.target.id : e.target;
    return s === id || t === id;
  }).classed('dimmed', e => {
    const s = typeof e.source === 'object' ? e.source.id : e.source;
    const t = typeof e.target === 'object' ? e.target.id : e.target;
    return s !== id && t !== id;
  });
}
function clearHighlight() {
  nodeSel.classed('selected', false).classed('dimmed', false)
         .classed('playing', d => d.id === playingId);
  linkSel.classed('highlighted', false).classed('dimmed', false);
}

// ── Info card ────────────────────────────────────────────────
function showInfoCard(d) {
  document.getElementById('ic-art').src = d.artwork || '';
  document.getElementById('ic-title').textContent  = d.title || d.name.replace(/\\.[^.]+$/, '');
  document.getElementById('ic-artist').textContent = d.artist || '—';
  document.getElementById('ic-camelot').textContent = d.camelot;
  document.getElementById('ic-bpm').textContent    = Math.round(d.bpm) + ' BPM';
  document.getElementById('ic-energy').textContent = d.energy;
  document.getElementById('ic-genre').innerHTML    =
    '<span class="ic-dot" style="background:' + d.color + '"></span>' + d.genero;
  document.getElementById('ic-play-btn').onclick = () => loadTrack(d, true);
  document.getElementById('infocard').classList.add('visible');
}

nodeSel.on('click', (e, d) => {
  e.stopPropagation();
  if (selectedId === d.id) {
    selectedId = null; clearHighlight();
    document.getElementById('infocard').classList.remove('visible');
    return;
  }
  selectedId = d.id;
  highlightNode(d.id);
  showInfoCard(d);
});
svg.on('click', () => {
  selectedId = null; clearHighlight();
  document.getElementById('infocard').classList.remove('visible');
});

// ── Audio player ─────────────────────────────────────────────
const audio = document.getElementById('audio');
audio.volume = 0.8;

function fmt(s) {
  if (!isFinite(s)) return '0:00';
  return Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0');
}

function loadTrack(d, autoplay) {
  history.push(playingId);
  playingId = d.id;
  audio.src = 'file://' + d.path;
  document.getElementById('pl-art').src       = d.artwork || '';
  document.getElementById('pl-title').textContent  = d.title || d.name.replace(/\\.[^.]+$/, '');
  document.getElementById('pl-artist').textContent = d.artist || d.genero;
  nodeSel.classed('playing',  n => n.id === playingId)
         .classed('selected', n => n.id === selectedId && n.id !== playingId);
  if (autoplay !== false) audio.play().catch(() => {});
}

audio.addEventListener('timeupdate', () => {
  if (!audio.duration) return;
  document.getElementById('pl-fill').style.width = (audio.currentTime / audio.duration * 100) + '%';
  document.getElementById('pl-time').textContent = fmt(audio.currentTime) + ' / ' + fmt(audio.duration);
});
audio.addEventListener('play',  () => { document.getElementById('pl-play').innerHTML = '&#9646;&#9646;'; });
audio.addEventListener('pause', () => { document.getElementById('pl-play').innerHTML = '&#9654;'; });
audio.addEventListener('ended', playNext);

document.getElementById('pl-play').addEventListener('click', () => {
  if (!audio.src) return;
  audio.paused ? audio.play() : audio.pause();
});
document.getElementById('pl-next').addEventListener('click', playNext);
document.getElementById('pl-prev').addEventListener('click', playPrev);

function playNext() {
  if (playingId === null) return;
  const next = (adj[playingId] || []).find(a => a.id !== playingId);
  if (next) loadTrack(nodeById(next.id), true);
}
function playPrev() {
  const prev = history.filter(id => id !== null).pop();
  if (prev === undefined) return;
  history = history.slice(0, -1);
  playingId = null;
  loadTrack(nodeById(prev), true);
}

document.getElementById('pl-bar').addEventListener('click', e => {
  if (!audio.duration) return;
  const rect = e.currentTarget.getBoundingClientRect();
  audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
});
document.getElementById('pl-vol').addEventListener('input', e => { audio.volume = +e.target.value; });

// ── Filters ──────────────────────────────────────────────────
function applyFilters() {
  const bpmMin = +document.getElementById('bpmMin').value;
  const bpmMax = +document.getElementById('bpmMax').value;
  const active = new Set(Array.from(document.querySelectorAll('.gpill.active')).map(b => b.dataset.genre));
  const vis = new Set(NODES.filter(n => n.bpm >= bpmMin && n.bpm <= bpmMax && active.has(n.genero)).map(n => n.id));
  nodeSel.classed('dimmed', d => !vis.has(d.id));
  linkSel.classed('dimmed', e => {
    const s = typeof e.source === 'object' ? e.source.id : e.source;
    const t = typeof e.target === 'object' ? e.target.id : e.target;
    return !vis.has(s) || !vis.has(t);
  }).classed('highlighted', false);
}
document.getElementById('bpmMin').addEventListener('input', applyFilters);
document.getElementById('bpmMax').addEventListener('input', applyFilters);
document.querySelectorAll('.gpill').forEach(b =>
  b.addEventListener('click', () => { b.classList.toggle('active'); applyFilters(); }));

window.addEventListener('resize', () => {
  W = graphEl.clientWidth; H = graphEl.clientHeight;
  sim.force('center', d3.forceCenter(W / 2, H / 2)).alpha(0.1).restart();
});
</script>
</body></html>"""

    return (
        template
        .replace("__BPM_MIN__", str(bpm_min))
        .replace("__BPM_MAX__", str(bpm_max))
        .replace("__GENRE_PILLS__", genre_pills)
        .replace("__NODES__", json.dumps(nodes))
        .replace("__EDGES__", json.dumps(edges))
    )


def main():
    ap = argparse.ArgumentParser(
        description="Genera un grafo interactivo de compatibilidad entre tracks."
    )
    ap.add_argument("--index", default=str(INDEX_DIR))
    ap.add_argument("--out", default=OUT_HTML)
    ap.add_argument("--k", type=int, default=5, help="Vecinos por track (default: 5)")
    args = ap.parse_args()

    idx = Path(args.index)
    embeddings = np.load(idx / "embeddings.npy").astype("float32")
    with open(idx / "biblioteca.json", encoding="utf-8") as f:
        fichas = json.load(f)

    print(f"Construyendo grafo ({len(fichas)} tracks, k={args.k})…")
    nodes, edges = build_graph(embeddings, fichas, k=args.k)
    print(f"  {len(nodes)} nodos · {len(edges)} aristas")

    html = generar_html(nodes, edges)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"HTML generado: {args.out}")


if __name__ == "__main__":
    main()
