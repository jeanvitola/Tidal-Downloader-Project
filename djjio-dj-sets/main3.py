import torch, librosa
from muq import MuQMuLan

device = 'cuda'
mulan = MuQMuLan.from_pretrained("OpenMuQ/MuQ-MuLan-large").to(device).eval()

# 1) Embedding del track
wav, sr = librosa.load("track2.mp3", sr=24000)
wavs = torch.tensor(wav).unsqueeze(0).to(device)
with torch.no_grad():
    audio_embeds = mulan(wavs=wavs)

# 2) Lista de géneros candidatos (ajústala a TU música de DJ)
# Lista de géneros candidatos (ajústala a TU música)
generos = [
    # --- House ---
    "house", "deep house", "tech house", "progressive house",
    "afro house", "minimal house", "disco house", "funky house",
    # --- Techno ---
    "techno", "minimal techno", "melodic techno", "hard techno",
    "dub techno", "industrial techno",
    # --- Otros electrónicos ---
    "trance", "drum and bass", "dubstep", "breakbeat", "garage",
    "electro", "synthwave", "ambient", "downtempo", "idm",
    "disco", "nu disco", "hardstyle",
    # --- Rock ---
    "rock", "classic rock", "hard rock", "punk rock", "indie rock",
    "alternative rock", "psychedelic rock", "progressive rock",
    "garage rock", "post rock", "grunge", "metal", "heavy metal",
    # --- Pop / mainstream ---
    "pop", "synth pop", "indie pop", "dance pop", "electropop",
    # --- Urbano / hip hop ---
    "hip hop", "trap", "reggaeton", "r&b", "lo-fi hip hop",
    # --- Otros ---
    "funk", "soul", "disco funk", "jazz", "blues", "reggae",
    "latin", "salsa", "afrobeat",
]
# El prompt "A <label> track" es el que el paper encontró que funciona mejor
prompts = [f"A {g} track" for g in generos]

with torch.no_grad():
    text_embeds = mulan(texts=prompts)

# 3) Similitud audio vs cada género
sim = mulan.calc_similarity(audio_embeds, text_embeds)   # shape [1, len(generos)]
scores = sim.squeeze(0)

# 4) Top-3 géneros
topk = torch.topk(scores, k=3)
print("Géneros más probables:")
for score, idx in zip(topk.values, topk.indices):
    print(f"  {generos[idx]:20s}  {score.item():.3f}")