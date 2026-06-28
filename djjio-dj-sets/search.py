# search.py — búsqueda semántica de tracks por texto usando MuQ-MuLan
import os
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import json
import argparse
from pathlib import Path

import torch
import numpy as np
from muq import MuQMuLan

INDEX_DIR = Path("index")
DEVICE = os.getenv("DJJIO_DEVICE", "cuda")
if DEVICE == "cuda" and not torch.cuda.is_available():
    DEVICE = "cpu"


def search(query: str, embeddings: np.ndarray, fichas: list, k: int = 10):
    print(f"Cargando MuQ-MuLan…")
    mulan = MuQMuLan.from_pretrained("OpenMuQ/MuQ-MuLan-large").to(DEVICE).eval()

    with torch.no_grad():
        text_emb = mulan(texts=[query])
    text_emb = text_emb / text_emb.norm(dim=-1, keepdim=True)
    text_vec = text_emb.squeeze(0).cpu().numpy().astype("float32")

    sims = embeddings @ text_vec
    top_idx = np.argsort(sims)[::-1][:k]

    print(f'\nResultados para: "{query}"\n')
    print(f"  {'Score':>6}  {'Track':<45}  {'BPM':>6}  {'Key':>4}  Género")
    print(f"  {'─'*6}  {'─'*45}  {'─'*6}  {'─'*4}  {'─'*16}")
    for i, idx in enumerate(top_idx, 1):
        f = fichas[idx]
        name = Path(f["path"]).stem[:43]
        print(f"  {sims[idx]:>6.3f}  {name:<45}  {f['bpm']:>6.1f}  {f['camelot']:>4}  {f['genero']}")

    return [(int(idx), float(sims[idx])) for idx in top_idx]


def main():
    ap = argparse.ArgumentParser(
        description="Búsqueda semántica de tracks por texto usando MuQ-MuLan."
    )
    ap.add_argument("query", nargs="+", help='Query en texto. Ej: "dark techno energético 130 BPM"')
    ap.add_argument("--index", default=str(INDEX_DIR))
    ap.add_argument("-k", type=int, default=8, help="Número de resultados (default: 8)")
    args = ap.parse_args()

    idx = Path(args.index)
    emb_path = idx / "mulan_embeddings.npy"

    if not emb_path.exists():
        print(f"No existe {emb_path}.")
        print("Primero ejecuta:  python build_mulan_index.py")
        return

    embeddings = np.load(emb_path).astype("float32")
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / (norms + 1e-8)

    with open(idx / "biblioteca.json", encoding="utf-8") as f:
        fichas = json.load(f)

    query = " ".join(args.query)
    search(query, embeddings, fichas, k=args.k)


if __name__ == "__main__":
    main()
