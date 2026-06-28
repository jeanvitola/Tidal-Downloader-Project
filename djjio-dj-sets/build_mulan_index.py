# build_mulan_index.py — computa embeddings MuLan de audio para búsqueda por texto
import os
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import json
import gc
import argparse
from pathlib import Path

import torch
import librosa
import numpy as np
from muq import MuQMuLan

INDEX_DIR = Path("index")
DEVICE = os.getenv("DJJIO_DEVICE", "cuda")
if DEVICE == "cuda" and not torch.cuda.is_available():
    DEVICE = "cpu"

CHUNK_SEC = 15
SR = 24000


def embed_audio(mulan, path):
    wav, _ = librosa.load(path, sr=SR, mono=True)
    wavs = torch.tensor(wav[:CHUNK_SEC * SR]).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        emb = mulan(wavs=wavs)
    emb = emb / emb.norm(dim=-1, keepdim=True)
    result = emb.squeeze(0).cpu().numpy().astype("float32")
    del wavs, emb
    if DEVICE == "cuda":
        torch.cuda.empty_cache()
    gc.collect()
    return result


def main():
    ap = argparse.ArgumentParser(
        description="Genera mulan_embeddings.npy para búsqueda semántica por texto."
    )
    ap.add_argument("--index", default=str(INDEX_DIR))
    args = ap.parse_args()

    idx = Path(args.index)
    with open(idx / "biblioteca.json", encoding="utf-8") as f:
        fichas = json.load(f)

    out_path = idx / "mulan_embeddings.npy"
    if out_path.exists():
        print(f"Ya existe {out_path}. Usa --force para reconstruir.")

    print("Cargando MuQ-MuLan…")
    mulan = MuQMuLan.from_pretrained("OpenMuQ/MuQ-MuLan-large").to(DEVICE).eval()
    print(f"Modelo listo en {DEVICE}.\n")

    embeddings = []
    failed = []

    for i, f in enumerate(fichas, 1):
        try:
            emb = embed_audio(mulan, f["path"])
            embeddings.append(emb)
            print(f"  [{i}/{len(fichas)}] ✓  {Path(f['path']).name}")
        except Exception as e:
            print(f"  [{i}/{len(fichas)}] ✗  {Path(f['path']).name} — {e}")
            embeddings.append(np.zeros(mulan.config.hidden_size if hasattr(mulan, 'config') else 512, dtype="float32"))
            failed.append(f["path"])

    matrix = np.stack(embeddings).astype("float32")
    np.save(out_path, matrix)
    print(f"\nGuardado: {out_path}  {matrix.shape}")
    if failed:
        print(f"{len(failed)} tracks fallaron.")


if __name__ == "__main__":
    main()
