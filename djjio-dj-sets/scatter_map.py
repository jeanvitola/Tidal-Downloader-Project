# scatter_map.py
import json
from pathlib import Path
import numpy as np
import umap

INDEX_DIR = Path("index")
OUT_HTML = "scatter_map.html"


def cargar_indice():
    embeddings = np.load(INDEX_DIR / "embeddings.npy").astype("float32")
    with open(INDEX_DIR / "biblioteca.json", encoding="utf-8") as f:
        fichas = json.load(f)
    return embeddings, fichas


def proyectar_2d(embeddings):
    n = len(embeddings)
    # n_neighbors no puede ser >= número de tracks; lo acotamos
    n_neighbors = min(15, max(2, n - 1))
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=0.1,
        n_components=2,
        metric="cosine",      # coseno: coherente con embeddings normalizados
        random_state=42,
    )
    return reducer.fit_transform(embeddings)


def generar_html(coords, fichas):
    # Paleta de colores por género
    generos = sorted({f["genero"] for f in fichas})
    palette = ["#378ADD", "#1D9E75", "#D85A30", "#7F77DD", "#EF9F27",
               "#D4537E", "#639922", "#E24B4A", "#0F6E56", "#534AB7"]
    color_de = {g: palette[i % len(palette)] for i, g in enumerate(generos)}

    puntos = []
    for (x, y), f in zip(coords, fichas):
        puntos.append({
            "x": float(x), "y": float(y),
            "name": Path(f["path"]).name,
            "bpm": f["bpm"], "camelot": f["camelot"],
            "genero": f["genero"], "energy": f["energy"],
            "color": color_de[f["genero"]],
        })

    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Scatter Map · Mi biblioteca DJ</title>
<style>
  body { margin:0; background:#12161f; color:#e6ebf0; font-family:system-ui,sans-serif; }
  #wrap { display:flex; height:100vh; }
  #plot { flex:1; position:relative; }
  canvas { display:block; }
  #side { width:300px; padding:20px; background:#1a2230; overflow-y:auto; }
  h2 { font-size:15px; margin:0 0 12px; }
  .leg { display:flex; align-items:center; gap:8px; font-size:13px; margin:4px 0; }
  .dot { width:12px; height:12px; border-radius:50%; }
  #info { margin-top:20px; padding:14px; background:#222c3d; border-radius:8px; font-size:13px; min-height:80px; }
  #info .t { font-weight:600; margin-bottom:8px; }
  #info .r { color:#9fb0c4; margin:3px 0; }
  .hint { color:#6a7a8f; font-size:12px; margin-top:10px; }
</style></head><body>
<div id="wrap">
  <div id="plot"><canvas id="cv"></canvas></div>
  <div id="side">
    <h2>Géneros</h2>
    <div id="legend"></div>
    <div id="info"><div class="r">Pasa el mouse sobre un punto…</div></div>
    <div class="hint">Cercanía = compatibilidad musical. Arrastra para mover, scroll para zoom.</div>
  </div>
</div>
<script>
const PTS = __PUNTOS__;
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const plot = document.getElementById('plot');
let scale=1, ox=0, oy=0, drag=false, lx=0, ly=0;

function resize(){ cv.width=plot.clientWidth; cv.height=plot.clientHeight; draw(); }
window.addEventListener('resize', resize);

const xs=PTS.map(p=>p.x), ys=PTS.map(p=>p.y);
const minX=Math.min(...xs), maxX=Math.max(...xs), minY=Math.min(...ys), maxY=Math.max(...ys);
function sx(x){ return 60 + (x - minX) / (maxX - minX || 1) * (cv.width - 120); }
function sy(y){ return 60 + (y - minY) / (maxY - minY || 1) * (cv.height - 120); }

function draw(){
  ctx.setTransform(1,0,0,1,0,0);
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.setTransform(scale,0,0,scale,ox,oy);
  for(const p of PTS){
    const px=sx(p.x), py=sy(p.y);
    ctx.beginPath(); ctx.arc(px,py,7,0,Math.PI*2); ctx.fillStyle=p.color; ctx.fill();
    ctx.strokeStyle='rgba(255,255,255,.3)'; ctx.lineWidth=1; ctx.stroke();
  }
}

function screenToData(mx,my){ return { x:(mx-ox)/scale, y:(my-oy)/scale }; }

function findPoint(mx, my){
  const pt = screenToData(mx, my);
  for(const p of PTS){
    const dx = sx(p.x) - pt.x;
    const dy = sy(p.y) - pt.y;
    if(Math.hypot(dx, dy) < 10) return p;
  }
  return null;
}

cv.addEventListener('mousemove', e => {
  const rect = cv.getBoundingClientRect();
  const p = findPoint(e.clientX - rect.left, e.clientY - rect.top);
  const info = document.getElementById('info');
  if(p){
    info.innerHTML = `<div class="t">${p.name}</div>` +
      `<div class="r">Género: ${p.genero}</div>` +
      `<div class="r">BPM: ${p.bpm}</div>` +
      `<div class="r">Tonalidad: ${p.camelot}</div>` +
      `<div class="r">Energía: ${p.energy}</div>`;
  } else {
    info.innerHTML = '<div class="r">Pasa el mouse sobre un punto…</div>';
  }
});

cv.addEventListener('mousedown', e => { drag=true; lx=e.clientX; ly=e.clientY; });
window.addEventListener('mouseup', () => { drag=false; });
window.addEventListener('mousemove', e => {
  if(!drag) return;
  ox += e.clientX - lx;
  oy += e.clientY - ly;
  lx = e.clientX;
  ly = e.clientY;
  draw();
});

window.addEventListener('wheel', e => {
  e.preventDefault();
  const rect = cv.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  const delta = Math.sign(e.deltaY) * -0.1;
  const newScale = Math.max(0.3, Math.min(4, scale + delta));
  ox = mx - (mx - ox) * (newScale / scale);
  oy = my - (my - oy) * (newScale / scale);
  scale = newScale;
  draw();
}, { passive: false });

const legend = document.getElementById('legend');
const map = new Map(PTS.map(p => [p.genero, p.color]));
for(const [genero, color] of map){
  const item = document.createElement('div');
  item.className = 'leg';
  item.innerHTML = `<span class="dot" style="background:${color}"></span>${genero}`;
  legend.appendChild(item);
}

resize();
draw();
</script>
</body></html>"""
    html = html.replace('__PUNTOS__', json.dumps(puntos)).replace('__COLORS__', json.dumps(color_de))
    return html


def guardar_html(html, out_path=OUT_HTML):
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)


if __name__ == '__main__':
    embeddings, fichas = cargar_indice()
    coords = proyectar_2d(embeddings)
    html = generar_html(coords, fichas)
    guardar_html(html)
    print(f'HTML generado: {OUT_HTML}')
