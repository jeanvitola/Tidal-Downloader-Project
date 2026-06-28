# extract_artwork.py — extrae portada real o genera placeholder, actualiza biblioteca.json
import json
import base64
import io
import argparse
import math
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.id3 import ID3NoHeaderError
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from PIL import Image, ImageDraw, ImageFilter

INDEX_DIR = Path("index")
THUMB_SIZE = 160  # px cuadrado

GENRE_PALETTES = {
    "techno":            ("#0a0a0a", "#C4603A"),
    "deep house":        ("#06111a", "#5B8FA8"),
    "tech house":        ("#0d0a00", "#C8A951"),
    "progressive house": ("#080d16", "#378ADD"),
    "melodic techno":    ("#0d0614", "#7B6BA8"),
    "afro house":        ("#0d0800", "#D85A30"),
    "disco":             ("#14060a", "#D4537E"),
    "drum and bass":     ("#060d06", "#4E9E6E"),
    "ambient":           ("#060a14", "#534AB7"),
    "rock":              ("#100606", "#E24B4A"),
    "classic rock":      ("#100800", "#EF9F27"),
    "hard rock":         ("#0d0606", "#C4603A"),
    "pop":               ("#0a0614", "#7F77DD"),
    "hip hop":           ("#080808", "#639922"),
    "jazz":              ("#0a0800", "#C8A951"),
}
DEFAULT_PALETTE = ("#080810", "#5B7BA8")


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def generate_placeholder(title: str, artist: str, genero: str, size: int = THUMB_SIZE) -> str:
    bg_hex, accent_hex = GENRE_PALETTES.get(genero.lower(), DEFAULT_PALETTE)
    bg    = hex_to_rgb(bg_hex)
    accent = hex_to_rgb(accent_hex)

    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2

    # Radial gradient: círculos concéntricos desde el centro con color accent
    for r in range(size // 2, 0, -1):
        t = 1 - (r / (size / 2))  # 0 en borde, 1 en centro
        t = t ** 1.6
        c = tuple(int(bg[i] + (accent[i] - bg[i]) * t * 0.65) for i in range(3))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)

    # Anillo decorativo exterior
    ring_r = int(size * 0.42)
    draw.ellipse(
        [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
        outline=(*accent, 60), width=1,
    )

    # Inicial del artista o título (grande, centrada)
    initial = (artist or title or "?")[:1].upper()
    font_size = int(size * 0.44)
    font = None
    for font_path in [
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/Vera.ttf",
    ]:
        try:
            from PIL import ImageFont
            font = ImageFont.truetype(font_path, font_size)
            break
        except Exception:
            continue

    if font:
        from PIL import ImageFont
        bbox = draw.textbbox((0, 0), initial, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = cx - tw // 2 - bbox[0]
        ty = cy - th // 2 - bbox[1]
        # Sombra suave
        draw.text((tx + 2, ty + 2), initial, fill=(*bg, 180), font=font)
        draw.text((tx, ty), initial, fill=(255, 255, 255, 210), font=font)

    # Nombre abreviado del artista/título abajo
    label = (artist or Path(title).stem)[:18]
    small_size = max(10, int(size * 0.095))
    small_font = None
    for font_path in [
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            from PIL import ImageFont
            small_font = ImageFont.truetype(font_path, small_size)
            break
        except Exception:
            continue

    if small_font:
        sb = draw.textbbox((0, 0), label, font=small_font)
        sw = sb[2] - sb[0]
        draw.text((cx - sw // 2, size - small_size - int(size * 0.09)),
                  label, fill=(*accent, 200), font=small_font)

    # Blur muy suave para suavizar los bordes del gradiente
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    enc = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{enc}"


def _resize_to_base64(data: bytes, fmt: str = "JPEG") -> str:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=85)
    enc = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/jpeg" if fmt == "JPEG" else "image/png"
    return f"data:{mime};base64,{enc}"


def extract_real_artwork(path: str):
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext == ".mp3":
            from mutagen.id3 import ID3
            id3 = ID3(path)
            for key in id3.keys():
                if key.startswith("APIC"):
                    return _resize_to_base64(id3[key].data)
        elif ext == ".flac":
            f = FLAC(path)
            if f.pictures:
                return _resize_to_base64(f.pictures[0].data)
        elif ext in (".m4a", ".aac", ".mp4"):
            f = MP4(path)
            covr = f.tags.get("covr") if f.tags else None
            if covr:
                fmt = "PNG" if covr[0].imageformat == MP4.MP4Cover.FORMAT_PNG else "JPEG"
                return _resize_to_base64(bytes(covr[0]), fmt)
        else:
            raw = MutagenFile(path)
            if raw and hasattr(raw, "pictures") and raw.pictures:
                return _resize_to_base64(raw.pictures[0].data)
    except Exception:
        pass
    return None


def extract_text_metadata(path: str) -> dict:
    p = Path(path)
    result = {"title": p.stem, "artist": "", "album": "", "year": ""}
    try:
        tags = MutagenFile(path, easy=True)
        if tags:
            result["title"]  = str(tags.get("title",  [p.stem])[0])
            result["artist"] = str(tags.get("artist", [""])[0])
            result["album"]  = str(tags.get("album",  [""])[0])
            result["year"]   = str(tags.get("date",   [""])[0])[:4]
    except Exception:
        pass
    return result


def main():
    ap = argparse.ArgumentParser(
        description="Extrae portada/metadata y actualiza biblioteca.json"
    )
    ap.add_argument("--index", default=str(INDEX_DIR))
    ap.add_argument("--force-generate", action="store_true",
                    help="Generar placeholder aunque haya portada real")
    args = ap.parse_args()

    idx = Path(args.index)
    lib_path = idx / "biblioteca.json"

    with open(lib_path, encoding="utf-8") as f:
        fichas = json.load(f)

    print(f"Procesando {len(fichas)} tracks…\n")
    real_count = gen_count = 0

    for i, ficha in enumerate(fichas, 1):
        meta = extract_text_metadata(ficha["path"])
        ficha.update(meta)

        artwork = None
        if not args.force_generate:
            artwork = extract_real_artwork(ficha["path"])

        if artwork:
            ficha["artwork"] = artwork
            real_count += 1
            src = "portada real"
        else:
            ficha["artwork"] = generate_placeholder(
                ficha["title"], ficha["artist"], ficha.get("genero", "")
            )
            gen_count += 1
            src = "generada"

        print(f"  [{i}/{len(fichas)}] {src:13s}  {ficha['artist'] or '?'} — {ficha['title'][:40]}")

    with open(lib_path, "w", encoding="utf-8") as f:
        json.dump(fichas, f, ensure_ascii=False, indent=2)

    print(f"\n✓ {real_count} portadas reales · {gen_count} generadas")
    print(f"biblioteca.json actualizado.")


if __name__ == "__main__":
    main()
