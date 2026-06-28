# chapter_builder.py
import json
import argparse
from pathlib import Path
import numpy as np

INDEX_DIR = Path("index")

CHAPTER_NAMES = ["Intro", "Build", "Peak", "Cooldown"]

ENERGY_THRESHOLDS = {
    "Intro":    (0.00, 0.35),
    "Build":    (0.25, 0.60),
    "Peak":     (0.50, 1.00),
    "Cooldown": (0.00, 0.40),
}

CAMELOT_ORDER = {
    str(i) + l: i * 2 + (0 if l == "A" else 1)
    for i in range(1, 13) for l in "AB"
}


# ── Camelot greedy path ───────────────────────────────────────────────────────

def camelot_dist(c1, c2):
    if c1 == "?" or c2 == "?":
        return 6
    try:
        n1, l1 = int(c1[:-1]), c1[-1]
        n2, l2 = int(c2[:-1]), c2[-1]
    except (ValueError, IndexError):
        return 6
    if c1 == c2:
        return 0
    if n1 == n2:
        return 1
    diff = min(abs(n1 - n2), 12 - abs(n1 - n2))
    return diff if l1 == l2 else diff + 1


def greedy_camelot_path(tracks):
    if not tracks:
        return []
    remaining = list(tracks)
    path = [remaining.pop(0)]
    while remaining:
        last = path[-1]["camelot"]
        best = min(remaining, key=lambda t: camelot_dist(last, t["camelot"]))
        remaining.remove(best)
        path.append(best)
    return path


# ── Energy arc assignment ─────────────────────────────────────────────────────

def assign_chapters(tracks):
    if not tracks:
        return {name: [] for name in CHAPTER_NAMES}

    energies = [t["energy"] for t in tracks]
    e_min, e_max = min(energies), max(energies)
    e_range = e_max - e_min or 1

    def norm(e):
        return (e - e_min) / e_range

    chapters = {name: [] for name in CHAPTER_NAMES}
    unassigned = []

    for t in tracks:
        ne = norm(t["energy"])
        assigned = False
        if ne <= 0.30:
            chapters["Intro"].append(t)
            assigned = True
        if 0.20 <= ne <= 0.65:
            chapters["Build"].append(t)
            assigned = True
        if ne >= 0.55:
            chapters["Peak"].append(t)
            assigned = True
        if not assigned:
            unassigned.append(t)

    # Distribute unassigned to nearest chapter by energy
    for t in unassigned:
        ne = norm(t["energy"])
        centers = {"Intro": 0.15, "Build": 0.425, "Peak": 0.775, "Cooldown": 0.15}
        best = min(centers, key=lambda c: abs(centers[c] - ne))
        chapters[best].append(t)

    # Cooldown = lowest-energy tracks from Intro not needed there
    if len(chapters["Intro"]) > 2:
        intro_sorted = sorted(chapters["Intro"], key=lambda t: t["energy"])
        split = max(1, len(intro_sorted) // 2)
        chapters["Cooldown"] = intro_sorted[:split]
        chapters["Intro"] = intro_sorted[split:]

    return chapters


# ── HTML output ───────────────────────────────────────────────────────────────

CHAPTER_COLORS = {
    "Intro":    "#5B8FA8",
    "Build":    "#4E9E6E",
    "Peak":     "#C4603A",
    "Cooldown": "#7B6BA8",
}

CHAPTER_DESC = {
    "Intro":    "Energía baja · Abre el set",
    "Build":    "Energía media · Construye tensión",
    "Peak":     "Energía alta · Momento cumbre",
    "Cooldown": "Cierre suave · Baja la energía",
}


def generar_html(chapters, meta):
    rows = []
    for name in CHAPTER_NAMES:
        tracks = chapters[name]
        if not tracks:
            continue
        color = CHAPTER_COLORS[name]
        desc  = CHAPTER_DESC[name]
        track_rows = "".join(
            f"""<tr>
              <td class="idx">{i+1}</td>
              <td class="tname">{Path(t['path']).name}</td>
              <td class="tag">{t['camelot']}</td>
              <td class="tag">{round(t['bpm'])} BPM</td>
              <td class="tag">{t['genero']}</td>
              <td class="energy-cell">
                <div class="ebar" style="width:{int(t['energy']*100)}%;background:{color}44"></div>
                <span>{t['energy']:.2f}</span>
              </td>
            </tr>"""
            for i, t in enumerate(tracks)
        )
        rows.append(f"""
        <div class="chapter">
          <div class="ch-header" style="border-left:3px solid {color}">
            <div>
              <span class="ch-name" style="color:{color}">{name}</span>
              <span class="ch-desc">{desc}</span>
            </div>
            <span class="ch-count">{len(tracks)} tracks</span>
          </div>
          <table>
            <thead><tr><th>#</th><th>Track</th><th>Key</th><th>BPM</th><th>Género</th><th>Energía</th></tr></thead>
            <tbody>{track_rows}</tbody>
          </table>
        </div>""")

    total = sum(len(v) for v in chapters.values())
    filter_info = f" · Filtro: {meta['filter']}" if meta.get("filter") else ""

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Chapter Builder · Djjio</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:#000; color:#ddd; font-family:system-ui,sans-serif; padding:32px; max-width:960px; margin:0 auto; }}
h1 {{ font-size:18px; font-weight:700; letter-spacing:.5px; margin-bottom:4px; }}
.subtitle {{ font-size:12px; color:#444; margin-bottom:32px; }}
.chapter {{ margin-bottom:32px; }}
.ch-header {{ display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:#0d0d0d; border-radius:6px 6px 0 0; margin-bottom:1px; }}
.ch-name {{ font-size:14px; font-weight:700; margin-right:10px; }}
.ch-desc {{ font-size:11px; color:#555; }}
.ch-count {{ font-size:11px; color:#444; }}
table {{ width:100%; border-collapse:collapse; background:#080808; border-radius:0 0 6px 6px; overflow:hidden; }}
th {{ font-size:10px; color:#444; text-align:left; padding:8px 12px; border-bottom:1px solid #111; text-transform:uppercase; letter-spacing:.5px; }}
td {{ font-size:12px; padding:9px 12px; border-bottom:1px solid #0f0f0f; vertical-align:middle; }}
tr:last-child td {{ border-bottom:none; }}
tr:hover td {{ background:#0f0f0f; }}
.idx {{ color:#333; width:30px; }}
.tname {{ color:#ccc; max-width:320px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.tag {{ color:#666; white-space:nowrap; }}
.energy-cell {{ display:flex; align-items:center; gap:8px; }}
.ebar {{ height:6px; border-radius:3px; min-width:2px; }}
.energy-cell span {{ color:#555; font-size:11px; }}
</style></head><body>
<h1>Chapter Builder</h1>
<p class="subtitle">{total} tracks · {sum(1 for v in chapters.values() if v)} capítulos{filter_info}</p>
{"".join(rows)}
</body></html>"""
    return html


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Construye un set con arco de energía narrativo.")
    ap.add_argument("--index",  default=str(INDEX_DIR))
    ap.add_argument("--group",  type=int, default=None,
                    help="Filtrar por grupo de autogroup (requiere groups.json)")
    ap.add_argument("--genero", default=None, help="Filtrar por género")
    ap.add_argument("--min-bpm", type=float, default=0)
    ap.add_argument("--max-bpm", type=float, default=9999)
    ap.add_argument("--out-html", default="chapters.html")
    ap.add_argument("--out-json", default="chapters.json")
    args = ap.parse_args()

    idx = Path(args.index)
    with open(idx / "biblioteca.json", encoding="utf-8") as f:
        fichas = json.load(f)

    tracks = [
        {**f, "idx": i}
        for i, f in enumerate(fichas)
        if args.min_bpm <= f["bpm"] <= args.max_bpm
        and (args.genero is None or f["genero"] == args.genero)
        and (args.group is None or f.get("group") == args.group)
    ]

    filter_parts = []
    if args.group is not None:   filter_parts.append(f"Grupo {args.group + 1}")
    if args.genero is not None:  filter_parts.append(args.genero)
    if args.min_bpm > 0:         filter_parts.append(f"BPM ≥ {args.min_bpm}")
    if args.max_bpm < 9999:      filter_parts.append(f"BPM ≤ {args.max_bpm}")

    print(f"{len(tracks)} tracks tras filtros.")
    if not tracks:
        print("Sin tracks — ajusta los filtros.")
        return

    chapters = assign_chapters(tracks)

    for name in CHAPTER_NAMES:
        chapters[name] = greedy_camelot_path(chapters[name])

    # JSON output
    out = {}
    for name in CHAPTER_NAMES:
        out[name] = [
            {
                "idx": t["idx"],
                "name": Path(t["path"]).name,
                "path": t["path"],
                "bpm":  t["bpm"],
                "camelot": t["camelot"],
                "genero": t["genero"],
                "energy": t["energy"],
            }
            for t in chapters[name]
        ]
    with open(args.out_json, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    print(f"Capítulos guardados: {args.out_json}")

    html = generar_html(chapters, {"filter": ", ".join(filter_parts)})
    Path(args.out_html).write_text(html, encoding="utf-8")
    print(f"HTML generado: {args.out_html}")

    print("\nResumen:")
    for name in CHAPTER_NAMES:
        ts = chapters[name]
        if ts:
            print(f"  {name:10s}: {len(ts)} tracks  "
                  f"(energía {min(t['energy'] for t in ts):.2f}–{max(t['energy'] for t in ts):.2f})")


if __name__ == "__main__":
    main()
