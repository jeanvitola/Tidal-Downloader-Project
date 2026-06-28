# similares.py
import sys, json
from pathlib import Path
import numpy as np
import faiss

INDEX_DIR = Path("index")


def cargar_indice():
    embeddings = np.load(INDEX_DIR / "embeddings.npy").astype("float32")
    with open(INDEX_DIR / "biblioteca.json", encoding="utf-8") as f:
        fichas = json.load(f)
    return embeddings, fichas


def construir_faiss(embeddings):
    dim = embeddings.shape[1]
    # IndexFlatIP = producto interno. Como los vectores están normalizados L2,
    # el producto interno ES la similitud coseno.
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index


def similares(query_idx, embeddings, fichas, index, k=5):
    # +1 porque el primer resultado siempre es el track consigo mismo
    sims, idxs = index.search(embeddings[query_idx:query_idx + 1], k + 1)

    base = fichas[query_idx]
    print(f"\n🎵 Track base: {Path(base['path']).name}")
    print(f"   {base['bpm']} BPM · {base['camelot']} · {base['genero']}\n")
    print(f"   Más parecidos:")

    for sim, idx in zip(sims[0], idxs[0]):
        if idx == query_idx:
            continue   # saltar el track mismo
        f = fichas[idx]
        print(f"   [{sim:.3f}] {Path(f['path']).name}")
        print(f"           {f['bpm']} BPM · {f['camelot']} · {f['genero']}")


if __name__ == "__main__":
    embeddings, fichas = cargar_indice()
    index = construir_faiss(embeddings)

    # Sin argumento: lista los tracks para que elijas
    if len(sys.argv) < 2:
        print("Tracks en tu biblioteca:")
        for i, f in enumerate(fichas):
            print(f"  [{i}] {Path(f['path']).name}  ({f['genero']})")
        print(f"\nUso: python similares.py <número>")
        sys.exit(0)

    query_idx = int(sys.argv[1])
    similares(query_idx, embeddings, fichas, index)