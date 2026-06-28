# hot_cues.py — detecta estructura musical y genera Hot Cues para Rekordbox
import json
import argparse
from pathlib import Path

import numpy as np
import librosa
from scipy.ndimage import gaussian_filter1d

INDEX_DIR = Path("index")

CUE_COLORS = {
    "Start":      (40,  200, 40),
    "Intro End":  (40,  120, 255),
    "Drop 1":     (255, 30,  30),
    "Breakdown":  (255, 190, 0),
    "Drop 2":     (255, 80,  0),
    "Outro":      (180, 40,  200),
}


def snap_to_bar(time: float, beat_times: np.ndarray, beats_per_bar: int = 4) -> float:
    """Ajusta el tiempo al inicio del compás más cercano."""
    if len(beat_times) < beats_per_bar:
        return time
    beat_idx = int(np.argmin(np.abs(beat_times - time)))
    bar_idx = round(beat_idx / beats_per_bar) * beats_per_bar
    bar_idx = max(0, min(bar_idx, len(beat_times) - 1))
    return float(beat_times[bar_idx])


def detect_structure(path: str) -> dict:
    """
    Retorna dict {nombre_cue: tiempo_segundos} con los puntos estructurales.
    Usa beat tracking + curva de energía RMS para encontrar:
    Start, Intro End, Drop 1, Breakdown, Drop 2, Outro.
    """
    y, sr = librosa.load(path, sr=22050, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    # Beat tracking
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    if len(beat_times) < 16:
        return {"Start": 0.0}

    # RMS por frame → interpolado en tiempos de beats
    hop = 512
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    rms_frame_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)
    beat_rms = np.interp(beat_times, rms_frame_times, rms)

    # Suavizar con ventana de ~4 beats
    beat_rms_smooth = gaussian_filter1d(beat_rms, sigma=3.5)
    rms_max = beat_rms_smooth.max() + 1e-8
    rms_norm = beat_rms_smooth / rms_max

    grad = np.gradient(rms_norm)

    beats_per_bar = 4
    skip = beats_per_bar * 2   # ignorar primeros 2 compases
    cues = {"Start": 0.0}

    # ── Drop 1: mayor gradiente positivo tras los primeros 2 compases ──
    search_end_drop1 = min(len(grad), int(len(beat_times) * 0.6))
    if skip >= search_end_drop1:
        return cues

    drop1_beat = skip + int(np.argmax(grad[skip:search_end_drop1]))
    drop1_time = snap_to_bar(beat_times[drop1_beat], beat_times, beats_per_bar)
    cues["Drop 1"] = drop1_time

    # ── Intro End: primer beat > 35% energía antes del Drop 1 ──
    threshold = 0.35
    pre_drop = np.where(rms_norm[:drop1_beat] > threshold)[0]
    if len(pre_drop) > 0:
        intro_beat = int(pre_drop[0])
        # redondear al compás anterior
        intro_beat = (intro_beat // beats_per_bar) * beats_per_bar
        intro_time = snap_to_bar(beat_times[intro_beat], beat_times, beats_per_bar)
        if intro_time < drop1_time - 4:
            cues["Intro End"] = intro_time

    # ── Breakdown: mínimo de energía tras Drop 1 (ventana 8..120 beats) ──
    bd_start = drop1_beat + beats_per_bar * 2
    bd_end   = min(len(rms_norm), drop1_beat + beats_per_bar * 30)
    if bd_start < bd_end:
        bd_beat = bd_start + int(np.argmin(rms_norm[bd_start:bd_end]))
        # Solo si hay caída notable (≥ 20% del pico)
        if rms_norm[bd_beat] < rms_norm[drop1_beat] * 0.80:
            bd_time = snap_to_bar(beat_times[bd_beat], beat_times, beats_per_bar)
            cues["Breakdown"] = bd_time

            # ── Drop 2: mayor gradiente tras Breakdown ──
            d2_start = bd_beat + beats_per_bar * 2
            d2_end   = min(len(grad), len(beat_times) - beats_per_bar * 4)
            if d2_start < d2_end:
                d2_beat = d2_start + int(np.argmax(grad[d2_start:d2_end]))
                d2_time = snap_to_bar(beat_times[d2_beat], beat_times, beats_per_bar)
                # Solo si es significativamente antes del final
                if d2_time < duration - 20 and d2_time > bd_time + 4:
                    cues["Drop 2"] = d2_time

    # ── Outro: 32 beats desde el final ──
    outro_beat = max(0, len(beat_times) - beats_per_bar * 8)
    outro_time = float(beat_times[outro_beat])
    last_drop = cues.get("Drop 2") or cues.get("Drop 1") or 0
    if outro_time > last_drop + 16:
        cues["Outro"] = outro_time

    return cues


def process_library(fichas: list, force: bool = False) -> dict:
    results = {}
    total = len(fichas)
    for i, f in enumerate(fichas, 1):
        path = f["path"]
        name = Path(path).name
        if not force and "hot_cues" in f:
            results[path] = f["hot_cues"]
            print(f"  [{i}/{total}] ↩  {name}  (cached)")
            continue
        try:
            cues = detect_structure(path)
            results[path] = cues
            cue_summary = "  ".join(f"{k}: {v:.1f}s" for k, v in cues.items())
            print(f"  [{i}/{total}] ✓  {name}")
            print(f"         {cue_summary}")
        except Exception as e:
            print(f"  [{i}/{total}] ✗  {name} — {e}")
            results[path] = {"Start": 0.0}
    return results


def main():
    ap = argparse.ArgumentParser(
        description="Detecta estructura musical y genera hot cues para Rekordbox."
    )
    ap.add_argument("--index",  default=str(INDEX_DIR))
    ap.add_argument("--force",  action="store_true", help="Re-analizar aunque ya existan cues")
    ap.add_argument("--track",  default=None, help="Analizar solo este archivo (debug)")
    ap.add_argument("--out",    default=None, help="JSON de salida (default: index/hot_cues.json)")
    args = ap.parse_args()

    if args.track:
        cues = detect_structure(args.track)
        print(f"\n{Path(args.track).name}")
        for name, t in cues.items():
            print(f"  {name:12s}: {t:.2f}s")
        return

    idx = Path(args.index)
    with open(idx / "biblioteca.json", encoding="utf-8") as f:
        fichas = json.load(f)

    print(f"Analizando {len(fichas)} tracks…\n")
    hot_cues = process_library(fichas, force=args.force)

    out_path = Path(args.out) if args.out else idx / "hot_cues.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(hot_cues, f, ensure_ascii=False, indent=2)
    print(f"\nHot cues guardados: {out_path}")


if __name__ == "__main__":
    main()
