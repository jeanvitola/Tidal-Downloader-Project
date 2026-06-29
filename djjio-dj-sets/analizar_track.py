# analizar_track.py
import sys
import os

# Evitar fragmentación grande en CUDA: debe establecerse antes de importar torch.
# Alternativamente exportar en el shell:
#   export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
import librosa
import numpy as np
from muq import MuQ, MuQMuLan

DEVICE = os.getenv("DJJIO_DEVICE", "cuda")
# Si se pidió cuda pero no está disponible, caer a cpu.
if DEVICE == "cuda" and not torch.cuda.is_available():
    DEVICE = "cpu"

# ============================================================
#  Carga de modelos (UNA sola vez al importar)
# ============================================================
USE_FP16 = os.getenv("DJJIO_USE_FP16", "0") in ("1", "true", "True")

print("Cargando modelos…")
if USE_FP16 and DEVICE == "cpu":
    print("Advertencia: FP16 solo está disponible en CUDA; ignorando DJJIO_USE_FP16")

muq_base = MuQ.from_pretrained("OpenMuQ/MuQ-large-msd-iter").to(DEVICE)
mulan = MuQMuLan.from_pretrained("OpenMuQ/MuQ-MuLan-large").to(DEVICE)
if USE_FP16 and DEVICE == "cuda":
    try:
        muq_base = muq_base.half()
        mulan = mulan.half()
    except Exception:
        print("No se pudo convertir modelos a FP16; continuando en FP32")

muq_base = muq_base.eval()
mulan = mulan.eval()
print("Modelos listos.\n")

# ============================================================
#  Configuración
# ============================================================
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
}

EMBED_LAYER = 10  # capa alta de MuQ: buena para género/estilo


# ============================================================
#  Motores de análisis
# ============================================================
def _features_dsp(y, sr):
    """BPM, tonalidad, Camelot y energía (0-1) vía DSP con librosa."""
    # BPM
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = round(float(np.atleast_1d(tempo)[0]), 1)

    # Clave armonica via chroma
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    note_idx = int(np.argmax(chroma_mean))

    # Detectar mayor vs menor con spectral centroid como proxy de brillo
    centroid = float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())
    is_major = centroid > 2200

    CHROMA_NOTES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    CAMELOT_MAJOR = ['8B','3B','10B','5B','12B','7B','2B','9B','4B','11B','6B','1B']
    CAMELOT_MINOR = ['5A','12A','7A','2A','9A','4A','11A','6A','1A','8A','3A','10A']

    note_name = CHROMA_NOTES[note_idx]
    scale = "major" if is_major else "minor"
    camelot = CAMELOT_MAJOR[note_idx] if is_major else CAMELOT_MINOR[note_idx]

    # Energia 0-1 via RMS
    rms = float(np.sqrt(np.mean(y ** 2)))
    energy = float(np.clip(rms * 6, 0, 1))

    return {
        "bpm": bpm,
        "key": note_name,
        "scale": scale,
        "camelot": camelot,
        "energy": round(energy, 3),
    }


def _genero_zero_shot(wavs):
    """Género más probable de la lista de candidatos vía MuQ-MuLan."""
    with torch.no_grad():
        a = mulan(wavs=wavs)
        t = mulan(texts=PROMPTS)
        sim = mulan.calc_similarity(a, t).squeeze(0)
    idx = int(sim.argmax())
    return GENEROS[idx], round(float(sim[idx]), 3)


def _embedding(wavs, layer=EMBED_LAYER):
    """Embedding normalizado del track vía MuQ base (para similitud/mapa)."""
    with torch.no_grad():
        out = muq_base(wavs, output_hidden_states=True)
    v = out.hidden_states[layer].mean(dim=1)
    v = v / v.norm(dim=-1, keepdim=True)
    return v.squeeze(0).cpu().numpy().astype("float32")


# ============================================================
#  Función principal
# ============================================================
def analizar_track(path):
    """Devuelve la ficha completa de un track: DSP + género + embedding."""
    wav, sr = librosa.load(path, sr=24000, mono=True, duration=30)
    wavs = torch.tensor(wav).unsqueeze(0).to(DEVICE)
    # Si los modelos están en FP16 y CUDA, pasar el tensor a half
    if USE_FP16 and DEVICE == "cuda":
        try:
            wavs = wavs.half()
        except Exception:
            pass

    genero, score = _genero_zero_shot(wavs)
    emb = _embedding(wavs)
    dsp = _features_dsp(wav, sr)

    return {
        "path": path,
        **dsp,
        "genero": genero,
        "genero_score": score,
        "embedding": emb,
    }


# ============================================================
#  CLI de prueba
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analizar_track.py track.mp3 [track2.mp3 ...]")
        sys.exit(1)

    for path in sys.argv[1:]:
        ficha = analizar_track(path)
        print(f"\n=== {path} ===")
        for k, v in ficha.items():
            if k == "embedding":
                print(f"  embedding: vector[{v.shape[0]}], norma={np.linalg.norm(v):.2f}")
            elif k == "path":
                continue
            else:
                print(f"  {k}: {v}")