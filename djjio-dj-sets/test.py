# analizar_track.py
import sys
import os
import torch
import librosa
import numpy as np
import essentia.standard as es
from muq import MuQ, MuQMuLan

DEVICE = "cuda"

print("Cargando modelos…")
muq_base = MuQ.from_pretrained("OpenMuQ/MuQ-large-msd-iter").to(DEVICE).eval()
mulan = MuQMuLan.from_pretrained("OpenMuQ/MuQ-MuLan-large").to(DEVICE).eval()
print("Modelos listos.\n")

GENEROS = [
    "techno", "deep house", "tech house", "progressive house",
    "melodic techno", "afro house", "disco", "drum and bass", "ambient",
    "rock", "classic rock", "hard rock", "pop", "hip hop", "jazz",
]
PROMPTS = [f"A {g} track" for g in GENEROS]

CAMELOT = {
    ("C", "major"): "8B",  ("A", "minor"): "8A",
    ("G", "major"): "9B",  ("E", "minor"): "9A",
    ("D", "major"): "10B", ("B", "minor"): "10A",
    ("A", "major"): "11B", ("F#", "minor"): "11A",
    ("E", "major"): "12B", ("C#", "minor"): "12A",
    ("B", "major"): "1B",  ("G#", "minor"): "1A",
    ("F#", "major"): "2B", ("D#", "minor"): "2A",
    ("C#", "major"): "3B", ("A#", "minor"): "3A",
    ("G#", "major"): "4B", ("F", "minor"): "4A",
    ("D#", "major"): "5B", ("C", "minor"): "5A",
    ("A#", "major"): "6B", ("G", "minor"): "6A",
    ("F", "major"): "7B",  ("D", "minor"): "7A",
    ("Db", "major"): "3B", ("Db", "minor"): "12A",
    ("Eb", "major"): "5B", ("Eb", "minor"): "2A",
    ("Gb", "major"): "2B", ("Gb", "minor"): "11A",
    ("Ab", "major"): "4B", ("Ab", "minor"): "1A",
    ("Bb", "major"): "6B", ("Bb", "minor"): "3A",
}

EMBED_LAYER = 10
CHUNK_SEC = 15
SR = 24000


def _features_dsp(path):
    audio = es.MonoLoader(filename=path, sampleRate=44100)()
    bpm, _, _, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
    key, scale, _ = es.KeyExtractor()(audio)
    energy = _energy_normalized(audio)
    return {
        "bpm": round(float(bpm), 1),
        "key": key,
        "scale": scale,
        "camelot": CAMELOT.get((key, scale), "?"),
        "energy": round(energy, 3),
    }


def _energy_normalized(audio):
    try:
        stereo = np.array([audio, audio]).T.astype("float32")
        loud = es.LoudnessEBUR128(hopSize=0.1, sampleRate=44100)
        _, _, integrated, _ = loud(stereo)
        return float(np.clip((integrated + 30) / 25, 0, 1))
    except Exception:
        rms = np.sqrt(np.mean(audio ** 2))
        return float(np.clip(rms * 4, 0, 1))


def _genero_zero_shot(wavs, max_sec=CHUNK_SEC):
    sample = wavs[:, : max_sec * SR]
    with torch.no_grad():
        a = mulan(wavs=sample)
        t = mulan(texts=PROMPTS)
        sim = mulan.calc_similarity(a, t).squeeze(0)
    idx = int(sim.argmax())
    result = (GENEROS[idx], round(float(sim[idx]), 3))
    del a, t, sim, sample
    torch.cuda.empty_cache()
    return result


def _embedding(wavs, layer=EMBED_LAYER, chunk_sec=CHUNK_SEC):
    chunk = chunk_sec * SR
    n = wavs.shape[1]
    if n <= chunk:
        with torch.no_grad():
            out = muq_base(wavs, output_hidden_states=True)
        v = out.hidden_states[layer].mean(dim=1)
        del out
        torch.cuda.empty_cache()
    else:
        vecs = []
        for i in range(0, n, chunk):
            piece = wavs[:, i:i + chunk]
            if piece.shape[1] < SR:
                continue
            with torch.no_grad():
                out = muq_base(piece, output_hidden_states=True)
            vecs.append(out.hidden_states[layer].mean(dim=1))
            del out
            torch.cuda.empty_cache()
        v = torch.stack(vecs).mean(dim=0)
    v = v / v.norm(dim=-1, keepdim=True)
    result = v.squeeze(0).cpu().numpy().astype("float32")
    del v
    torch.cuda.empty_cache()
    return result


def analizar_track(path):
    wav, _ = librosa.load(path, sr=SR, mono=True)
    wavs = torch.tensor(wav).unsqueeze(0).to(DEVICE)
    genero, score = _genero_zero_shot(wavs)
    emb = _embedding(wavs)
    dsp = _features_dsp(path)
    del wavs
    torch.cuda.empty_cache()
    return {
        "path": path,
        **dsp,
        "genero": genero,
        "genero_score": score,
        "embedding": emb,
    }


if __name__ == "__main__":
    # Path por defecto; se puede sobrescribir pasándolo como argumento
    DEFAULT_MUSIC = "/home/jeancv/Documentos/Djjio/music"
    folder = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MUSIC

    # Construir lista de rutas robusta ante espacios no escapados en la línea de comandos.
    args = sys.argv[1:] if len(sys.argv) > 1 else [DEFAULT_MUSIC]
    paths = []
    if len(args) == 1:
        paths = args
    else:
        # Intentar tratar todos los args como una sola ruta (ruta con espacios)
        joined = " ".join(args)
        if os.path.exists(joined):
            paths = [joined]
        else:
            # Agrupar secuencias de args que formen rutas existentes
            i = 0
            while i < len(args):
                found = False
                # probar el segmento más largo primero
                for j in range(len(args), i, -1):
                    cand = " ".join(args[i:j])
                    if os.path.exists(cand):
                        paths.append(cand)
                        i = j
                        found = True
                        break
                if not found:
                    # si no encontramos grupo, usar el arg individual (posible ruta inválida)
                    paths.append(args[i])
                    i += 1

    for path in paths:
        if not os.path.exists(path):
            print(f"Archivo no encontrado: {path}")
            continue

        if os.path.isdir(path):
            AUDIO_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".aiff", ".ogg"}
            for root, _, files in os.walk(path):
                for fname in sorted(files):
                    p = os.path.join(root, fname)
                    if os.path.splitext(p)[1].lower() not in AUDIO_EXTS:
                        continue
                    ficha = analizar_track(p)
                    print(f"\n=== {p} ===")
                    for k, v in ficha.items():
                        if k == "embedding":
                            print(f"  embedding: vector[{v.shape[0]}], norma={np.linalg.norm(v):.2f}")
                        elif k == "path":
                            continue
                        else:
                            print(f"  {k}: {v}")
        else:
            ficha = analizar_track(path)
            print(f"\n=== {path} ===")
            for k, v in ficha.items():
                if k == "embedding":
                    print(f"  embedding: vector[{v.shape[0]}], norma={np.linalg.norm(v):.2f}")
                elif k == "path":
                    continue
                else:
                    print(f"  {k}: {v}")