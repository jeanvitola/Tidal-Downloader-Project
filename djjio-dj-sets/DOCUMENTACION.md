# Djjio — Documentación del Proyecto

Sistema de análisis, organización y visualización de biblioteca musical para DJs, construido con Python y Flask.

---

## Índice

1. [Visión general](#visión-general)
2. [Arquitectura](#arquitectura)
3. [Instalación](#instalación)
4. [Flujo de trabajo completo](#flujo-de-trabajo-completo)
5. [Módulos](#módulos)
6. [App web (Flask)](#app-web-flask)
7. [Estructura de archivos](#estructura-de-archivos)
8. [Formatos de datos](#formatos-de-datos)
9. [Referencia de comandos](#referencia-de-comandos)

---

## Visión general

Djjio analiza colecciones de música usando modelos de deep learning (MuQ / MuQ-MuLan) y DSP clásico (Essentia, librosa) para extraer:

- **BPM** y **tonalidad** (con notación Camelot)
- **Energía** normalizada (LUFS / RMS)
- **Género** por clasificación zero-shot
- **Embeddings** de audio para medir similitud musical

Con esos datos construye herramientas visuales e interactivas inspiradas en [djoid.io](https://www.djoid.io/):

| Herramienta | Descripción |
|---|---|
| Graph Playlist | Grafo de compatibilidad entre tracks con reproductor |
| Scatter Map | Mapa 2D UMAP de la biblioteca |
| Chapter Builder | Divide un set en bloques de energía narrativos |
| Auto Groups | Agrupa la biblioteca en "vibe islands" por clustering |
| Search | Búsqueda semántica por texto usando MuQ-MuLan |
| Export | Exporta a Rekordbox XML (con hot cues), Serato y m3u |

---

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                   PIPELINE DE ANÁLISIS               │
│                                                      │
│  Audio files                                         │
│      │                                               │
│      ▼                                               │
│  analizar_track.py ──► BPM, Key, Energy (Essentia)  │
│                    ──► Género zero-shot (MuQ-MuLan)  │
│                    ──► Embedding [1024] (MuQ base)   │
│      │                                               │
│      ▼                                               │
│  build_index.py ──► index/embeddings.npy             │
│                 ──► index/biblioteca.json            │
│                                                      │
│  extract_artwork.py ──► portadas + metadata ID3      │
│  hot_cues.py        ──► index/hot_cues.json          │
│  build_mulan_index.py ► index/mulan_embeddings.npy   │
│  autogroup.py       ──► groups.json                  │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                    APP WEB (Flask)                   │
│                                                      │
│  app.py                                              │
│  ├── /             Dashboard                         │
│  ├── /graph        Graph Playlist (D3 force)         │
│  ├── /scatter      Scatter Map (UMAP + canvas)       │
│  ├── /chapters     Chapter Builder                   │
│  ├── /search       Búsqueda semántica                │
│  ├── /groups       Auto Groups                       │
│  ├── /api/*        APIs JSON                         │
│  └── /audio/<id>   Streaming de audio                │
└─────────────────────────────────────────────────────┘
```

### Modelos usados

| Modelo | Fuente | Uso |
|---|---|---|
| `MuQ-large-msd-iter` | OpenMuQ/HuggingFace | Embeddings de audio (capa 10) para similitud y mapa |
| `MuQ-MuLan-large` | OpenMuQ/HuggingFace | Clasificación de género zero-shot y búsqueda semántica texto→audio |
| Essentia | MTG-UPF | BPM (RhythmExtractor2013), tonalidad (KeyExtractor), energía (LoudnessEBUR128) |
| librosa | librosa-dev | Carga de audio, beat tracking, RMS para hot cues |
| UMAP | umap-learn | Proyección 2D de embeddings para scatter map |
| KMeans | scikit-learn | Clustering para auto groups |
| FAISS | Facebook | Búsqueda de vecinos más cercanos en similares.py |

---

## Instalación

### Requisitos del sistema

- Python 3.10+
- CUDA (recomendado, funciona en CPU con `DJJIO_DEVICE=cpu`)
- ~8 GB RAM (modelos MuQ en memoria)

### Setup

```bash
# Clonar / entrar al directorio
cd /ruta/a/Djjio

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Instalar dependencias base
pip install torch librosa muq huggingface_hub transformers safetensors numpy scipy soundfile

# Dependencias adicionales
pip install essentia scikit-learn umap-learn faiss-cpu mutagen Pillow flask
```

### Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `DJJIO_DEVICE` | `cuda` | Dispositivo de inferencia (`cuda` o `cpu`) |
| `DJJIO_USE_FP16` | `0` | Usar FP16 para reducir VRAM (`1` activa, solo CUDA) |

---

## Flujo de trabajo completo

### Primera vez (biblioteca nueva)

```bash
# 1. Analizar toda la biblioteca y construir índice
python build_index.py /ruta/a/musica

# 2. Extraer portadas y metadata (artista, título, álbum)
python extract_artwork.py

# 3. Detectar hot cues (intro, drop, breakdown, outro)
python hot_cues.py

# 4. Agrupar por vibe (auto groups)
python autogroup.py

# 5. (Opcional) Construir índice MuLan para búsqueda semántica
python build_mulan_index.py

# 6. Lanzar la app web
python app.py
# → http://localhost:5000
```

### Uso diario

```bash
# Lanzar app
source venv/bin/activate && python app.py

# Agregar tracks nuevos al índice
python build_index.py /ruta/a/musica   # re-procesa toda la carpeta

# Buscar tracks similares por texto (CLI)
python search.py "dark melodic techno 130 bpm"
python search.py "chill deep house sunset" -k 5

# Encontrar tracks similares a uno dado (CLI)
python similares.py 3   # muestra los más similares al track #3

# Exportar set
python chapter_builder.py --group 0 --min-bpm 120 --max-bpm 135
python export.py --chapters chapters.json --out-dir exports/
```

---

## Módulos

### `analizar_track.py`

Núcleo de análisis. Carga los modelos MuQ y MuQ-MuLan una sola vez (al importar) y analiza tracks individuales.

**Función principal:**
```python
ficha = analizar_track("/ruta/track.mp3")
# Retorna dict con: path, bpm, key, scale, camelot, energy, genero, genero_score, embedding
```

**Configuración:**
- `EMBED_LAYER = 10` — capa de MuQ usada para el embedding (capa alta = semántica de género/estilo)
- `GENEROS` — lista de 14 géneros candidatos para clasificación zero-shot
- `CAMELOT` — mapa de (key, scale) → notación Camelot

**Cálculo de energía:**
1. Intenta LUFS integrado via `LoudnessEBUR128` (más preciso, perceptual)
2. Fallback: RMS normalizado

---

### `build_index.py`

Procesa una carpeta completa de audio y construye el índice.

```bash
python build_index.py /ruta/a/musica

# Extensiones soportadas: .mp3, .flac, .wav, .m4a, .aiff, .ogg
```

**Salida:**
- `index/embeddings.npy` — matriz `[N, 1024]` de embeddings MuQ (float32)
- `index/biblioteca.json` — lista de fichas con todos los metadatos

---

### `extract_artwork.py`

Extrae portadas embebidas en los tags del audio (ID3 para MP3, FLAC tags, MP4 covr). Si un track no tiene portada, genera un placeholder visual con:
- Gradiente radial del color de su género
- Inicial del artista centrada
- Nombre del artista en la parte inferior

```bash
python extract_artwork.py                  # procesa todos
python extract_artwork.py --force-generate # fuerza re-generación de placeholders
```

Actualiza `index/biblioteca.json` añadiendo los campos:
- `artwork` — imagen en base64 (`data:image/jpeg;base64,...`)
- `title`, `artist`, `album`, `year` — desde los ID3 tags

---

### `build_mulan_index.py`

Computa embeddings de audio con **MuQ-MuLan** (espacio compartido texto-audio). Necesario para la búsqueda semántica por texto.

```bash
python build_mulan_index.py
```

**Salida:** `index/mulan_embeddings.npy` — matriz `[N, D]` normalizada (float32)

> Solo necesita ejecutarse una vez. Los embeddings MuQ base (de `build_index.py`) son distintos y se usan para similitud/mapa. Los MuLan son para búsqueda texto→audio.

---

### `hot_cues.py`

Detecta la estructura musical de cada track usando beat tracking + análisis de energía RMS.

**Puntos detectados:**

| Cue | Color Rekordbox | Descripción |
|---|---|---|
| Start | Verde | Inicio del track (siempre 0.0s) |
| Intro End | Azul | Primera subida de energía significativa |
| Drop 1 | Rojo | Mayor gradiente positivo de energía |
| Breakdown | Amarillo | Mínimo de energía tras el Drop 1 |
| Drop 2 | Naranja | Mayor gradiente tras el Breakdown |
| Outro | Morado | ~32 beats antes del final |

Todos los puntos se **snapean al compás más cercano** (4 beats) para compatibilidad con DJ software.

```bash
python hot_cues.py                        # procesa toda la biblioteca
python hot_cues.py --track mi_track.mp3  # analiza un track específico
python hot_cues.py --force               # re-analiza aunque ya existan cues
```

**Salida:** `index/hot_cues.json`

---

### `autogroup.py`

Agrupa automáticamente la biblioteca en "vibe islands" usando KMeans sobre los embeddings MuQ.

```bash
python autogroup.py           # auto-detecta k óptimo (silhouette score)
python autogroup.py --k 5     # fuerza k grupos
python autogroup.py --k-min 3 --k-max 8  # rango para auto-detección
```

**Salida:**
- `groups.json` — tracks organizados por grupo
- `scatter_groups.html` — mapa 2D con convex hulls por grupo
- Añade campo `group` a cada track en `index/biblioteca.json`

**Score de silhouette:** mide qué tan bien separados están los clusters. Se prueba k=2..10 y se elige el mejor.

---

### `chapter_builder.py`

Construye un set con arco de energía narrativo: Intro → Build → Peak → Cooldown.

**Algoritmo:**
1. Filtra tracks por BPM, género, grupo
2. Asigna cada track a un capítulo según energía normalizada
3. Dentro de cada capítulo, ordena por **compatibilidad Camelot** (greedy path)

```bash
python chapter_builder.py                        # toda la biblioteca
python chapter_builder.py --group 0             # solo grupo 1
python chapter_builder.py --genero "deep house" --min-bpm 120 --max-bpm 130
```

**Salida:**
- `chapters.json` — capítulos con lista ordenada de tracks
- `chapters.html` — vista HTML con tabla por capítulo

---

### `similares.py`

Encuentra los tracks más similares a uno dado usando FAISS (producto interno sobre embeddings normalizados = similitud coseno).

```bash
python similares.py          # lista todos los tracks para elegir
python similares.py 3        # muestra los 5 más similares al track #3
```

---

### `search.py`

Búsqueda semántica de tracks por descripción en texto libre.

```bash
python search.py "dark energetic techno"
python search.py "chill melodic deep house at sunset" -k 5
python search.py "track for peak time festival"
```

Requiere `index/mulan_embeddings.npy` (generado por `build_mulan_index.py`).

**Cómo funciona:**
1. Carga MuQ-MuLan
2. Codifica el texto como vector en el espacio audio-texto compartido
3. Calcula similitud coseno contra todos los embeddings MuLan de audio
4. Retorna los k más similares

---

### `graph_playlist.py`

Genera `graph_playlist.html` — grafo interactivo standalone (sin servidor).

```bash
python graph_playlist.py              # k=5 vecinos por track
python graph_playlist.py --k 8       # más conexiones
python graph_playlist.py --out mi_grafo.html
```

**Score de compatibilidad entre tracks:**
```
score = 0.5 × similitud_embedding + 0.3 × compatibilidad_camelot + 0.2 × compatibilidad_bpm
```

**Compatibilidad Camelot:**
- Mismo key: 1.0
- Misma nota, diferente modo (A↔B): 0.8
- Adyacente en la rueda (±1): 0.7
- Resto: 0.0

**Compatibilidad BPM:**
- Misma velocidad (±5%): 1.0
- Doble/mitad tempo (±5%): 1.0
- Dentro del ±10%: 0.7
- Resto: 0.0

---

### `scatter_map.py`

Genera `scatter_map.html` — scatter plot 2D standalone usando UMAP.

```bash
python scatter_map.py
```

---

### `export.py`

Exporta playlists y capítulos a formatos DJ.

```bash
# Desde chapters.json (un archivo por capítulo)
python export.py --chapters chapters.json --out-dir exports/

# Lista de tracks directa (una sola playlist)
python export.py --playlist track1.mp3 track2.mp3 --format m3u

# Solo Rekordbox
python export.py --chapters chapters.json --format rekordbox

# Formato específico
python export.py --chapters chapters.json --format serato --serato-dir ~/Music
```

**Formatos:**

| Formato | Archivo | Notas |
|---|---|---|
| `m3u` | `<name>_<capítulo>.m3u` | Universal, funciona en cualquier software |
| `rekordbox` | `<name>_rekordbox.xml` | Incluye Hot Cues si existe `index/hot_cues.json` |
| `serato` | `~/Music/_Serato_/Subcrates/Djjio%<capítulo>.crate` | Formato binario nativo de Serato |

**Importar en Rekordbox:**
`File → Import Playlist → seleccionar <name>_rekordbox.xml`

---

## App web (Flask)

### Arrancar

```bash
source venv/bin/activate
python app.py
# → http://localhost:5000
```

### Rutas

| Ruta | Descripción |
|---|---|
| `GET /` | Dashboard con stats de la biblioteca |
| `GET /graph` | Graph Playlist interactivo |
| `GET /scatter` | Scatter Map UMAP |
| `GET /chapters` | Chapter Builder con filtros en vivo |
| `GET /search` | Búsqueda semántica |
| `GET /groups` | Auto Groups |

### API

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/library` | GET | Retorna `biblioteca.json` completo |
| `/api/graph?k=5` | GET | Nodos y aristas del grafo de compatibilidad |
| `/api/scatter` | GET | Coordenadas UMAP + metadata por track |
| `/api/chapters` | GET | Capítulos (soporta `?group=`, `?genero=`, `?min_bpm=`, `?max_bpm=`) |
| `/api/search` | POST `{query, k}` | Búsqueda semántica MuLan |
| `/api/reload` | POST | Invalida cache y recarga biblioteca |
| `/audio/<id>` | GET | Stream del archivo de audio (soporta HTTP range) |

### Cache

Los datos pesados se cachean en memoria al primer acceso:
- `biblioteca.json` — recargable via `/api/reload`
- `embeddings.npy` — cargado una vez
- Coordenadas UMAP — se guardan en `index/umap_coords.npy` al computarse
- Grafo `(k)` — una versión por valor de k usado
- Modelo MuLan — lazy load al primer search, permanece en memoria

---

## Estructura de archivos

```
Djjio/
├── app.py                  Flask app (servidor principal)
├── analizar_track.py       Análisis de un track (BPM, key, género, embedding)
├── build_index.py          Indexa una carpeta de música
├── build_mulan_index.py    Genera embeddings MuLan para búsqueda por texto
├── extract_artwork.py      Extrae portadas y metadata ID3
├── hot_cues.py             Detecta estructura musical (intro, drop, breakdown)
├── autogroup.py            Clustering KMeans de la biblioteca
├── chapter_builder.py      Construye sets con arco de energía
├── export.py               Exporta a Rekordbox XML, Serato, m3u
├── similares.py            CLI de tracks similares (FAISS)
├── search.py               CLI de búsqueda semántica por texto
├── graph_playlist.py       Genera graph_playlist.html standalone
├── scatter_map.py          Genera scatter_map.html standalone
│
├── templates/              Templates Flask (Jinja2)
│   ├── base.html           Layout base con sidebar y player global
│   ├── dashboard.html      Stats de la biblioteca
│   ├── graph.html          Graph Playlist
│   ├── scatter.html        Scatter Map
│   ├── chapters.html       Chapter Builder
│   ├── search.html         Búsqueda semántica
│   └── groups.html         Auto Groups
│
├── index/                  Índice de la biblioteca (generado)
│   ├── biblioteca.json     Metadata de todos los tracks
│   ├── embeddings.npy      Embeddings MuQ [N × 1024]
│   ├── mulan_embeddings.npy Embeddings MuLan [N × D] (opcional)
│   ├── hot_cues.json       Puntos de estructura por track (opcional)
│   └── umap_coords.npy     Coordenadas UMAP 2D (generado por app)
│
├── exports/                Archivos exportados (generado)
│   ├── *.m3u
│   └── *_rekordbox.xml
│
├── groups.json             Grupos de autogroup (generado)
├── chapters.json           Capítulos del último chapter_builder (generado)
├── requirements.txt        Dependencias Python
└── venv/                   Entorno virtual
```

---

## Formatos de datos

### `biblioteca.json`

Lista de objetos, uno por track:

```json
{
  "path": "/ruta/absoluta/track.mp3",
  "bpm": 128.0,
  "key": "A",
  "scale": "minor",
  "camelot": "8A",
  "energy": 0.842,
  "genero": "deep house",
  "genero_score": 0.312,
  "title": "Track Name",
  "artist": "Artist Name",
  "album": "Album Name",
  "year": "2023",
  "artwork": "data:image/jpeg;base64,...",
  "group": 2
}
```

### `hot_cues.json`

```json
{
  "/ruta/track.mp3": {
    "Start": 0.0,
    "Intro End": 16.0,
    "Drop 1": 32.0,
    "Breakdown": 96.0,
    "Drop 2": 128.0,
    "Outro": 192.0
  }
}
```

### `groups.json`

```json
{
  "0": [{"idx": 3, "name": "track.mp3", "bpm": 128.0, "camelot": "8A", ...}],
  "1": [...],
  "2": [...]
}
```

---

## Referencia de comandos

```bash
# ── Indexación ────────────────────────────────────────────────
python build_index.py /ruta/musica
python extract_artwork.py
python build_mulan_index.py          # solo si quieres búsqueda semántica
python hot_cues.py
python autogroup.py --k 6           # o sin --k para auto-detectar

# ── App web ───────────────────────────────────────────────────
python app.py                        # → http://localhost:5000

# ── CLI ───────────────────────────────────────────────────────
python similares.py 3               # tracks similares al track #3
python search.py "techno oscuro 130 bpm" -k 8

# ── Chapter Builder + Export ──────────────────────────────────
python chapter_builder.py
python chapter_builder.py --group 0 --min-bpm 120 --max-bpm 135
python export.py --chapters chapters.json --out-dir exports/
python export.py --chapters chapters.json --format rekordbox
python export.py --chapters chapters.json --format m3u

# ── Herramientas standalone (sin servidor) ────────────────────
python graph_playlist.py --k 5
python scatter_map.py
python autogroup.py --out-html scatter_groups.html

# ── Variables de entorno ──────────────────────────────────────
DJJIO_DEVICE=cpu python build_index.py /ruta  # sin GPU
DJJIO_USE_FP16=1 python build_index.py /ruta  # menos VRAM (solo CUDA)
```
