# autogroup.py
import json
import argparse
from pathlib import Path
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
from scipy.spatial import ConvexHull

INDEX_DIR = Path("index")
OUT_HTML  = "scatter_groups.html"


# ── Clustering ───────────────────────────────────────────────────────────────

def best_k(embeddings, k_min=2, k_max=10):
    best, best_k = -1, k_min
    for k in range(k_min, min(k_max + 1, len(embeddings))):
        labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(embeddings)
        score = silhouette_score(embeddings, labels)
        print(f"  k={k}  silhouette={score:.3f}")
        if score > best:
            best, best_k = score, k
    return best_k


def cluster(embeddings, k):
    km = KMeans(n_clusters=k, random_state=42, n_init=15)
    labels = km.fit_predict(embeddings)
    return labels.tolist()


# ── Scatter HTML with group hulls ────────────────────────────────────────────

PALETTE = [
    "#378ADD", "#1D9E75", "#D85A30", "#7F77DD", "#EF9F27",
    "#D4537E", "#639922", "#E24B4A", "#0F6E56", "#534AB7",
    "#C8A951", "#5B8FA8",
]


def proyectar_2d(embeddings):
    try:
        import umap
        n = len(embeddings)
        reducer = umap.UMAP(
            n_neighbors=min(15, max(2, n - 1)),
            min_dist=0.1, n_components=2, metric="cosine", random_state=42,
        )
        return reducer.fit_transform(embeddings)
    except ImportError:
        pca = PCA(n_components=2, random_state=42)
        return pca.fit_transform(embeddings)


def hull_path(points_2d):
    if len(points_2d) < 3:
        return None
    try:
        hull = ConvexHull(points_2d)
        verts = points_2d[hull.vertices].tolist()
        verts.append(verts[0])  # cerrar
        return verts
    except Exception:
        return None


def generar_html(coords, fichas, labels):
    n_groups = max(labels) + 1
    group_colors = {g: PALETTE[g % len(PALETTE)] for g in range(n_groups)}

    puntos = []
    for (x, y), f, g in zip(coords, fichas, labels):
        puntos.append({
            "x": float(x), "y": float(y),
            "name": Path(f["path"]).name,
            "bpm": f["bpm"], "camelot": f["camelot"],
            "genero": f["genero"], "energy": f["energy"],
            "group": g, "color": group_colors[g],
        })

    hulls = []
    for g in range(n_groups):
        pts = np.array([[p["x"], p["y"]] for p in puntos if p["group"] == g])
        path = hull_path(pts)
        if path:
            hulls.append({"group": g, "color": group_colors[g], "points": path})

    template = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Auto Groups · Djjio</title>
<style>
body { margin:0; background:#000; color:#e6ebf0; font-family:system-ui,sans-serif; }
#wrap { display:flex; height:100vh; }
#plot { flex:1; position:relative; }
canvas { display:block; }
#side { width:280px; padding:20px; background:#0d0d0d; overflow-y:auto; border-left:1px solid rgba(255,255,255,0.06); }
h2 { font-size:13px; margin:0 0 12px; font-weight:700; letter-spacing:.5px; }
.leg { display:flex; align-items:center; gap:8px; font-size:12px; margin:5px 0; cursor:pointer; padding:4px 6px; border-radius:5px; }
.leg:hover { background:rgba(255,255,255,0.05); }
.dot { width:12px; height:12px; border-radius:50%; }
#info { margin-top:18px; padding:14px; background:#111; border-radius:8px; font-size:12px; min-height:80px; border:1px solid rgba(255,255,255,0.06); }
#info .t { font-weight:600; margin-bottom:8px; word-break:break-all; }
#info .r { color:#666; margin:3px 0; display:flex; justify-content:space-between; }
#info .r span:last-child { color:#bbb; }
.hint { color:#333; font-size:11px; margin-top:14px; line-height:1.6; }
</style></head><body>
<div id="wrap">
  <div id="plot"><canvas id="cv"></canvas></div>
  <div id="side">
    <h2>Grupos</h2>
    <div id="legend"></div>
    <div id="info"><div class="r" style="color:#444">Pasa el mouse sobre un punto…</div></div>
    <p class="hint">Cada grupo = vibe island.<br>Arrastra · Scroll para zoom.</p>
  </div>
</div>
<script>
const PTS   = __PUNTOS__;
const HULLS = __HULLS__;
const N_GROUPS = __N_GROUPS__;

const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const plot = document.getElementById('plot');
let scale=1, ox=0, oy=0, drag=false, lx=0, ly=0;
let hiddenGroups = new Set();

function resize(){ cv.width=plot.clientWidth; cv.height=plot.clientHeight; draw(); }
window.addEventListener('resize', resize);

const xs=PTS.map(p=>p.x), ys=PTS.map(p=>p.y);
const minX=Math.min(...xs), maxX=Math.max(...xs);
const minY=Math.min(...ys), maxY=Math.max(...ys);
const rngX = maxX-minX || 1, rngY = maxY-minY || 1;
function sx(x){ return 60 + (x-minX)/rngX*(cv.width-120); }
function sy(y){ return 60 + (y-minY)/rngY*(cv.height-120); }

function draw(){
  ctx.setTransform(1,0,0,1,0,0);
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.setTransform(scale,0,0,scale,ox,oy);

  // hulls
  HULLS.forEach(h => {
    if(hiddenGroups.has(h.group)) return;
    ctx.beginPath();
    h.points.forEach((p,i) => i===0 ? ctx.moveTo(sx(p[0]),sy(p[1])) : ctx.lineTo(sx(p[0]),sy(p[1])));
    ctx.closePath();
    ctx.fillStyle = h.color + '18';
    ctx.fill();
    ctx.strokeStyle = h.color + '55';
    ctx.lineWidth = 1.5;
    ctx.stroke();
  });

  // puntos
  PTS.forEach(p => {
    const px=sx(p.x), py=sy(p.y);
    const alpha = hiddenGroups.has(p.group) ? '22' : 'ff';
    ctx.beginPath(); ctx.arc(px,py,7,0,Math.PI*2);
    ctx.fillStyle = p.color + alpha; ctx.fill();
    ctx.strokeStyle='rgba(255,255,255,.15)'; ctx.lineWidth=1; ctx.stroke();
  });
}

function screenPt(mx,my){ return { x:(mx-ox)/scale, y:(my-oy)/scale }; }

function findPoint(mx,my){
  const pt=screenPt(mx,my);
  for(const p of PTS){
    if(hiddenGroups.has(p.group)) continue;
    if(Math.hypot(sx(p.x)-pt.x, sy(p.y)-pt.y)<10) return p;
  }
  return null;
}

cv.addEventListener('mousemove', e => {
  const rect=cv.getBoundingClientRect();
  const p=findPoint(e.clientX-rect.left, e.clientY-rect.top);
  const info=document.getElementById('info');
  if(p){
    info.innerHTML=`<div class="t">${p.name}</div>`+
      `<div class="r"><span>Grupo</span><span style="color:${p.color}">&#9679; ${p.group+1}</span></div>`+
      `<div class="r"><span>Género</span><span>${p.genero}</span></div>`+
      `<div class="r"><span>BPM</span><span>${p.bpm}</span></div>`+
      `<div class="r"><span>Camelot</span><span>${p.camelot}</span></div>`+
      `<div class="r"><span>Energía</span><span>${p.energy}</span></div>`;
  } else {
    info.innerHTML='<div class="r" style="color:#444">Pasa el mouse sobre un punto…</div>';
  }
});

cv.addEventListener('mousedown', e=>{drag=true;lx=e.clientX;ly=e.clientY;});
window.addEventListener('mouseup', ()=>{drag=false;});
window.addEventListener('mousemove', e=>{
  if(!drag) return;
  ox+=e.clientX-lx; oy+=e.clientY-ly; lx=e.clientX; ly=e.clientY; draw();
});
window.addEventListener('wheel', e=>{
  e.preventDefault();
  const rect=cv.getBoundingClientRect();
  const mx=e.clientX-rect.left, my=e.clientY-rect.top;
  const delta=Math.sign(e.deltaY)*-0.12;
  const ns=Math.max(0.2,Math.min(5,scale+delta));
  ox=mx-(mx-ox)*(ns/scale); oy=my-(my-oy)*(ns/scale); scale=ns; draw();
},{passive:false});

// Legend
const legend=document.getElementById('legend');
const groupColors=[...new Set(PTS.map(p=>p.color))];
groupColors.forEach((c,i)=>{
  const count=PTS.filter(p=>p.group===i).length;
  const el=document.createElement('div');
  el.className='leg';
  el.dataset.group=i;
  el.innerHTML=`<span class="dot" style="background:${c}"></span>Grupo ${i+1} <span style="color:#444;margin-left:auto">${count} tracks</span>`;
  el.addEventListener('click',()=>{
    if(hiddenGroups.has(i)) hiddenGroups.delete(i); else hiddenGroups.add(i);
    el.style.opacity=hiddenGroups.has(i)?'0.3':'1';
    draw();
  });
  legend.appendChild(el);
});

resize();
</script>
</body></html>"""

    return (
        template
        .replace("__PUNTOS__", json.dumps(puntos))
        .replace("__HULLS__",  json.dumps(hulls))
        .replace("__N_GROUPS__", str(n_groups))
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Agrupa la biblioteca en vibe islands.")
    ap.add_argument("--index", default=str(INDEX_DIR))
    ap.add_argument("--k", type=int, default=0,
                    help="Número de grupos. 0 = auto-detectar (default)")
    ap.add_argument("--k-min", type=int, default=2)
    ap.add_argument("--k-max", type=int, default=10)
    ap.add_argument("--out-html", default=OUT_HTML)
    ap.add_argument("--out-json", default="groups.json")
    args = ap.parse_args()

    idx = Path(args.index)
    embeddings = np.load(idx / "embeddings.npy").astype("float32")
    with open(idx / "biblioteca.json", encoding="utf-8") as f:
        fichas = json.load(f)

    print(f"{len(fichas)} tracks cargados.")

    if args.k == 0:
        print("Buscando k óptimo…")
        k = best_k(embeddings, args.k_min, args.k_max)
        print(f"→ k={k} seleccionado\n")
    else:
        k = args.k

    labels = cluster(embeddings, k)

    for i, f in enumerate(fichas):
        f["group"] = labels[i]

    with open(idx / "biblioteca.json", "w", encoding="utf-8") as fp:
        json.dump(fichas, fp, ensure_ascii=False, indent=2)

    groups_out = {}
    for i, (f, g) in enumerate(zip(fichas, labels)):
        groups_out.setdefault(g, []).append({"idx": i, "name": Path(f["path"]).name, **{k: f[k] for k in ("bpm","camelot","genero","energy")}})
    with open(args.out_json, "w", encoding="utf-8") as fp:
        json.dump(groups_out, fp, ensure_ascii=False, indent=2)
    print(f"Grupos guardados: {args.out_json}")

    print("Proyectando a 2D…")
    coords = proyectar_2d(embeddings)
    hulls_data = []
    for g in range(k):
        pts = np.array([coords[i] for i, lbl in enumerate(labels) if lbl == g])
        path = hull_path(pts)
        if path:
            hulls_data.append({"group": g, "color": PALETTE[g % len(PALETTE)], "points": path})

    html = generar_html(coords, fichas, labels)
    Path(args.out_html).write_text(html, encoding="utf-8")
    print(f"HTML generado: {args.out_html}")

    print(f"\nResumen:")
    for g in range(k):
        tracks = [f for f, lbl in zip(fichas, labels) if lbl == g]
        print(f"  Grupo {g+1}: {len(tracks)} tracks — géneros: {', '.join(set(t['genero'] for t in tracks))}")


if __name__ == "__main__":
    main()
