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
import essentia.standard as es
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
def _features_dsp(path):
    """BPM, tonalidad, Camelot y energía (0-1) vía DSP con essentia."""
    audio = es.MonoLoader(filename=path, sampleRate=44100)()

    # --- BPM ---
    bpm, _, _, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)

    # --- Key / tonalidad ---
    key, scale, _ = es.KeyExtractor()(audio)

    # --- Energía normalizada 0-1 ---
    energy = _energy_normalized(audio)

    return {
        "bpm": round(float(bpm), 1),
        "key": key,
        "scale": scale,
        "camelot": CAMELOT.get((key, scale), "?"),
        "energy": round(energy, 3),
    }


def _energy_normalized(audio):
    """Energía perceptual mapeada a 0-1. Usa LUFS si puede, si no RMS."""
    try:
        stereo = np.array([audio, audio]).T.astype("float32")
        loud = es.LoudnessEBUR128(hopSize=0.1, sampleRate=44100)
        _, _, integrated, _ = loud(stereo)
        # integrated en LUFS (típico -30 a -5) → 0-1
        return float(np.clip((integrated + 30) / 25, 0, 1))
    except Exception:
        # Fallback robusto: RMS normalizado
        rms = np.sqrt(np.mean(audio ** 2))
        return float(np.clip(rms * 4, 0, 1))


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
    wav, _ = librosa.load(path, sr=24000, mono=True)
    wavs = torch.tensor(wav).unsqueeze(0).to(DEVICE)
    # Si los modelos están en FP16 y CUDA, pasar el tensor a half
    if USE_FP16 and DEVICE == "cuda":
        try:
            wavs = wavs.half()
        except Exception:
            pass

    genero, score = _genero_zero_shot(wavs)
    emb = _embedding(wavs)
    dsp = _features_dsp(path)

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