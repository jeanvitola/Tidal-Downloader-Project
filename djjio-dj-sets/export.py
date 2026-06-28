# export.py
"""
Exporta playlists/capítulos a:
  --format m3u         →  playlist.m3u  (universal)
  --format rekordbox   →  rekordbox.xml (Pioneer Rekordbox)
  --format serato      →  Serato/_Serato_/Subcrates/<name>.crate  (m3u interno)

Input (uno de los dos):
  --chapters chapters.json   → exporta cada capítulo como playlist separada
  --playlist path1 path2 … → lista de rutas de audio directa
"""
import json
import argparse
import struct
import sys
from pathlib import Path
from datetime import date
import xml.etree.ElementTree as ET

# ── m3u ──────────────────────────────────────────────────────────────────────

def export_m3u(tracks, out_path):
    lines = ["#EXTM3U"]
    for t in tracks:
        dur = -1
        name = Path(t["path"]).stem
        lines.append(f"#EXTINF:{dur},{name}")
        lines.append(t["path"])
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  m3u → {out_path}")


# ── Rekordbox XML ─────────────────────────────────────────────────────────────

CUE_COLORS = {
    "Start":      (40,  200, 40),
    "Intro End":  (40,  120, 255),
    "Drop 1":     (255, 30,  30),
    "Breakdown":  (255, 190, 0),
    "Drop 2":     (255, 80,  0),
    "Outro":      (180, 40,  200),
}


def export_rekordbox(chapters_dict, out_path, hot_cues=None):
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    ET.SubElement(root, "PRODUCT", Name="rekordbox", Version="6.0.0", Company="Pioneer DJ")

    all_tracks = {}
    for ch_tracks in chapters_dict.values():
        for t in ch_tracks:
            if t["path"] not in all_tracks:
                all_tracks[t["path"]] = t

    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(all_tracks)))
    path_to_id = {}
    for tid, (path, t) in enumerate(all_tracks.items(), start=1):
        path_to_id[path] = tid
        attrs = {
            "TrackID": str(tid),
            "Name":    Path(path).stem,
            "Artist":  "",
            "Composer": "",
            "Album":   "",
            "TotalTime": "0",
            "Genre":   t.get("genero", ""),
            "AverageBpm": str(round(t.get("bpm", 0), 2)),
            "DateAdded": str(date.today()),
            "BitRate":  "0",
            "SampleRate": "44100",
            "Comments": f"Camelot: {t.get('camelot','?')} · Energy: {t.get('energy',0):.2f}",
            "PlayCount": "0",
            "Rating":   "0",
            "Location": "file://localhost" + path,
            "Remixer":  "",
            "Tonality": t.get("camelot", ""),
            "Label":    "",
            "Mix":      "",
        }
        track_el = ET.SubElement(collection, "TRACK", **attrs)

        # Hot cues
        if hot_cues and path in hot_cues:
            for num, (cue_name, cue_time) in enumerate(hot_cues[path].items()):
                if num >= 8:
                    break
                r, g, b = CUE_COLORS.get(cue_name, (255, 255, 255))
                ET.SubElement(track_el, "POSITION_MARK",
                    Name=cue_name, Type="0",
                    Start=f"{cue_time:.3f}",
                    Num=str(num),
                    Red=str(r), Green=str(g), Blue=str(b))

    playlists_node = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(playlists_node, "NODE", Type="0", Name="ROOT", Count=str(len(chapters_dict)))
    djjio_node = ET.SubElement(root_node, "NODE", Type="0", Name="Djjio", Count=str(len(chapters_dict)))

    for ch_name, ch_tracks in chapters_dict.items():
        if not ch_tracks:
            continue
        pl_node = ET.SubElement(
            djjio_node, "NODE",
            Type="1", Name=ch_name,
            Entries=str(len(ch_tracks)), KeyType="0"
        )
        for t in ch_tracks:
            ET.SubElement(pl_node, "TRACK", Key=str(path_to_id[t["path"]]))

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    with open(out_path, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False)
    print(f"  Rekordbox XML → {out_path}")


# ── Serato crate (.crate binary) ──────────────────────────────────────────────
# Serato crates usan un formato binario simple: header + entradas de ruta en UTF-16 BE.

def _serato_str(s):
    encoded = s.encode("utf-16-be")
    return struct.pack(">I", len(encoded)) + encoded


def _serato_field(tag, data):
    return tag.encode("ascii") + struct.pack(">I", len(data)) + data


def write_serato_crate(tracks, crate_path):
    Path(crate_path).parent.mkdir(parents=True, exist_ok=True)
    body = b""
    for t in tracks:
        # Serato espera rutas con '/' y sin drive letter en Linux
        path_field = _serato_field("ptrk", _serato_str(t["path"]))
        body += _serato_field("otrk", path_field)

    version = _serato_field("vrsn", _serato_str("1.0/Serato ScratchLive Crate"))
    with open(crate_path, "wb") as f:
        f.write(version + body)
    print(f"  Serato crate → {crate_path}")


def export_serato(chapters_dict, serato_dir):
    serato_dir = Path(serato_dir)
    subcrates = serato_dir / "_Serato_" / "Subcrates"
    subcrates.mkdir(parents=True, exist_ok=True)
    for ch_name, ch_tracks in chapters_dict.items():
        if not ch_tracks:
            continue
        crate_file = subcrates / f"Djjio%{ch_name}.crate"
        write_serato_crate(ch_tracks, crate_file)


# ── Main ─────────────────────────────────────────────────────────────────────

def load_chapters(chapters_path):
    with open(chapters_path, encoding="utf-8") as f:
        return json.load(f)


def tracks_from_paths(paths):
    return [{"path": str(Path(p).resolve()), "bpm": 0, "camelot": "?", "genero": "", "energy": 0}
            for p in paths if Path(p).exists()]


def main():
    ap = argparse.ArgumentParser(description="Exporta playlists/capítulos a m3u, Rekordbox o Serato.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--chapters", metavar="chapters.json",
                     help="JSON de capítulos generado por chapter_builder.py")
    src.add_argument("--playlist", nargs="+", metavar="AUDIO",
                     help="Lista de rutas de audio (se exporta como una sola playlist)")

    ap.add_argument("--format", choices=["m3u", "rekordbox", "serato", "all"],
                    default="all", help="Formato de exportación (default: all)")
    ap.add_argument("--out-dir", default=".", help="Directorio de salida (default: .)")
    ap.add_argument("--name",   default="Djjio_Set", help="Nombre base del archivo/crate")
    ap.add_argument("--index", default="index", help="Carpeta del índice (para hot_cues.json)")
    ap.add_argument("--serato-dir", default=str(Path.home() / "Music"),
                    help="Raíz de la biblioteca de Serato (default: ~/Music)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.chapters:
        chapters = load_chapters(args.chapters)
    else:
        chapters = {args.name: tracks_from_paths(args.playlist)}

    all_tracks = [t for ch in chapters.values() for t in ch]

    fmt = args.format

    if fmt in ("m3u", "all"):
        if args.chapters:
            for ch_name, ch_tracks in chapters.items():
                if ch_tracks:
                    export_m3u(ch_tracks, out_dir / f"{args.name}_{ch_name}.m3u")
        else:
            export_m3u(all_tracks, out_dir / f"{args.name}.m3u")

    if fmt in ("rekordbox", "all"):
        hot_cues = None
        hc_path = Path(args.index) / "hot_cues.json" if hasattr(args, "index") else Path("index/hot_cues.json")
        if hc_path.exists():
            with open(hc_path, encoding="utf-8") as f:
                hot_cues = json.load(f)
            print(f"  Hot cues cargados: {hc_path}")
        export_rekordbox(chapters, out_dir / f"{args.name}_rekordbox.xml", hot_cues=hot_cues)

    if fmt in ("serato", "all"):
        export_serato(chapters, args.serato_dir)

    print(f"\nExportación completa → {out_dir.resolve()}")


if __name__ == "__main__":
    main()
