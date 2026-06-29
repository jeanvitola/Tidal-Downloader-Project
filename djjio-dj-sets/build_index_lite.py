"""
build_index_lite.py — Analizador ligero (solo librosa + numpy)
No requiere muq, essentia, torch ni CUDA.
Extrae: BPM, clave armonica (Camelot), energia, titulo/artista de metadata.
"""
import sys, json, time, os
import numpy as np
from pathlib import Path

try:
    import librosa
except ImportError:
    print("ERROR: librosa no esta instalado. Ejecuta: pip install librosa")
    sys.exit(1)

try:
    from mutagen import File as MuFile
except ImportError:
    MuFile = None

AUDIO_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".aiff", ".ogg", ".opus"}

# Mapa de notas → Camelot (deteccion simplificada via chroma)
CHROMA_NOTES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
CAMELOT_MAJOR = ['8B','3B','10B','5B','12B','7B','2B','9B','4B','11B','6B','1B']
CAMELOT_MINOR = ['5A','12A','7A','2A','9A','4A','11A','6A','1A','8A','3A','10A']


def get_metadata(path):
    """Lee titulo, artista y genero de las etiquetas ID3/FLAC/MP4."""
    path_obj = Path(path)
    title, artist, genre = path_obj.stem, "", "sin clasificar"
    if MuFile is not None:
        try:
            tags = MuFile(path, easy=True)
            if tags:
                title  = (tags.get("title")  or [title])[0]
                artist = (tags.get("artist") or [""])[0]
                genre  = (tags.get("genre")  or ["sin clasificar"])[0]
        except Exception:
            pass

    genre = str(genre).strip().lower()
    
    # Fallback al nombre de la carpeta contenedora si no tiene genero en metadata
    GENERIC_FOLDERS = {"music", "tidal", "downloads", "temp", "desktop", "musica", "descargas", "new folder", "nueva carpeta", "index", "legal-music-downloader-ui"}
    if genre in ("", "sin clasificar", "unknown", "other", "sin_clasificar"):
        parent_name = path_obj.parent.name.strip().lower()
        if parent_name and parent_name not in GENERIC_FOLDERS:
            genre = parent_name
            
    return str(title), str(artist), genre



def analyze_lite(path):
    """Analiza un track con librosa y devuelve su ficha."""
    # Cargar audio (mono, 22050 Hz, max 3 min para velocidad)
    y, sr = librosa.load(path, sr=22050, mono=True, duration=180)

    # BPM
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = round(float(np.atleast_1d(tempo)[0]), 1)

    # Clave armonica via chroma
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    note_idx = int(np.argmax(chroma_mean))

    # Detectar mayor vs menor con spectral centroid como proxy de brillo
    centroid = float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())
    is_major = centroid > 2200  # umbral empírico simple
    camelot = CAMELOT_MAJOR[note_idx] if is_major else CAMELOT_MINOR[note_idx]
    note_name = CHROMA_NOTES[note_idx]
    scale = "major" if is_major else "minor"

    # Energia 0-1 via RMS
    rms = float(np.sqrt(np.mean(y ** 2)))
    energy = float(np.clip(rms * 6, 0, 1))

    # Embedding ligero: media y std de chroma como vector de 24 dims
    emb = np.concatenate([chroma_mean, chroma.std(axis=1)]).astype("float32")
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb /= norm

    # Metadata
    title, artist, genre = get_metadata(path)

    return {
        "path": str(path),
        "title": title,
        "artist": artist,
        "bpm": bpm,
        "key": note_name,
        "scale": scale,
        "camelot": camelot,
        "energy": round(energy, 3),
        "genero": genre,
        "genero_score": 1.0,
        "embedding": emb,
    }



def find_tracks(folder):
    root = Path(folder)
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in AUDIO_EXTS)


def build(folder, out_dir=None):
    if out_dir is None:
        out_dir = Path(__file__).parent / "index"
    out = Path(out_dir)
    out.mkdir(exist_ok=True)

    tracks = find_tracks(folder)
    print(f"Encontrados {len(tracks)} tracks en {folder}")
    if not tracks:
        print("No se encontraron archivos de audio.")
        return

    fichas, embeddings, fallidos = [], [], []
    t0 = time.time()

    for i, p in enumerate(tracks, 1):
        try:
            f = analyze_lite(str(p))
            emb = f.pop("embedding")
            fichas.append(f)
            embeddings.append(emb)
            print(f"  [{i}/{len(tracks)}] {p.name}  ->  {f['bpm']} BPM · {f['camelot']} · {f['key']} {f['scale']}")
        except Exception as e:
            fallidos.append((str(p), str(e)))
            print(f"  [{i}/{len(tracks)}] FALLO: {p.name} — {e}")

    if not fichas:
        print("No se pudo analizar ningun track.")
        return

    matrix = np.stack(embeddings).astype("float32")
    np.save(out / "embeddings.npy", matrix)
    with open(out / "biblioteca.json", "w", encoding="utf-8") as fp:
        json.dump(fichas, fp, ensure_ascii=False, indent=2)

    print(f"\nListo en {time.time()-t0:.1f}s")
    print(f"  fichas:     {len(fichas)} -> {out / 'biblioteca.json'}")
    print(f"  embeddings: {matrix.shape} -> {out / 'embeddings.npy'}")
    if fallidos:
        print(f"  {len(fallidos)} tracks fallaron:")
        for path, err in fallidos:
            print(f"    - {Path(path).name}: {err}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python build_index_lite.py /ruta/a/carpeta [/ruta/salida]")
        sys.exit(1)
    out = sys.argv[2] if len(sys.argv) > 2 else None
    build(sys.argv[1], out)
