# build_index.py
import sys, json, time
import os
import torch, gc

# Evitar que shells hijos activen xtrace heredando variables de entorno
for _var in ("BASH_ENV", "ENV", "SHELLOPTS", "PS4"):
    os.environ.pop(_var, None)
from pathlib import Path
import numpy as np
from analizar_track import analizar_track  # reutiliza los modelos ya cargados

AUDIO_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".aiff", ".ogg"}


def find_tracks(folder):
    root = Path(folder)
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in AUDIO_EXTS)


def build(folder, out_dir="index"):
    out = Path(out_dir)
    out.mkdir(exist_ok=True)

    tracks = find_tracks(folder)
    print(f"Encontrados {len(tracks)} tracks en {folder}\n")
    if not tracks:
        return

    fichas, embeddings, fallidos = [], [], []
    t0 = time.time()

    for i, p in enumerate(tracks, 1):
        try:
            f = analizar_track(str(p))
            emb = f.pop("embedding")          # saca el vector de la ficha
            fichas.append(f)
            embeddings.append(emb)
            print(f"  [{i}/{len(tracks)}] {p.name}  →  {f['bpm']} BPM · {f['camelot']} · {f['genero']}")
            # Liberar memoria CUDA fragmentada y coleccionar basura
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            gc.collect()
        except Exception as e:
            fallidos.append((str(p), str(e)))
            print(f"  [{i}/{len(tracks)}] FALLÓ: {p.name} — {e}")

    # Guardar
    matrix = np.stack(embeddings).astype("float32")   # [N, 1024]
    np.save(out / "embeddings.npy", matrix)
    with open(out / "biblioteca.json", "w", encoding="utf-8") as fp:
        json.dump(fichas, fp, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Listo en {time.time()-t0:.1f}s")
    print(f"  fichas:     {len(fichas)} → {out/'biblioteca.json'}")
    #print(f"  embeddings: {matrix.shape} → {out/'embeddings.npy'}")
    if fallidos:
        print(f"  {len(fallidos)} tracks fallaron")
        for path, err in fallidos:
            print(f"    - {Path(path).name}: {err}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python build_index.py /ruta/a/carpeta/de/musica")
        sys.exit(1)
    build(sys.argv[1])