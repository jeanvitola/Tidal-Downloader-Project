// Mock & Real Hybrid Music Database
const MOCK_DATABASE = [
    {
        id: "1",
        title: "Symphony No. 5 in C minor (Op. 67)",
        artist: "Ludwig van Beethoven",
        album: "Classic Masterpieces",
        duration: "06:42",
        cover: "https://images.unsplash.com/photo-1507838153414-b4b713384a76?w=400&q=80",
        license: "pd", // public domain
        licenseText: "Dominio Público",
        qualities: ["FLAC 24-bit", "MP3 320kbps"],
        sizeMb: 45.2,
        camelotKey: "5A",
        musicalKey: "C Minor",
        bpm: 108
    },
    {
        id: "2",
        title: "Clair de Lune",
        artist: "Claude Debussy",
        album: "Suite bergamasque",
        duration: "05:05",
        cover: "https://images.unsplash.com/photo-1465847899084-d164df4dedc6?w=400&q=80",
        license: "pd", // public domain
        licenseText: "Dominio Público",
        qualities: ["FLAC 16-bit", "MP3 320kbps"],
        sizeMb: 28.4,
        camelotKey: "3B",
        musicalKey: "Db Major",
        bpm: 70
    },
    {
        id: "3",
        title: "We Are The Resistors",
        artist: "Eric Skiff",
        album: "Resistor Anthems",
        duration: "02:51",
        cover: "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=400&q=80",
        license: "cc", // creative commons
        licenseText: "Creative Commons BY 4.0",
        qualities: ["MP3 320kbps", "OGG Vorbis"],
        sizeMb: 6.8,
        camelotKey: "9B",
        musicalKey: "G Major",
        bpm: 120
    },
    {
        id: "4",
        title: "Spring (The Four Seasons)",
        artist: "Antonio Vivaldi",
        album: "The Four Seasons",
        duration: "03:36",
        cover: "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?w=400&q=80",
        license: "pd",
        licenseText: "Dominio Público",
        qualities: ["FLAC 24-bit", "MP3 320kbps"],
        sizeMb: 32.1,
        camelotKey: "12B",
        musicalKey: "E Major",
        bpm: 110
    },
    {
        id: "5",
        title: "Canyon Breeze",
        artist: "Jason Shaw",
        album: "Audionautix Acoustic",
        duration: "04:12",
        cover: "https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=400&q=80",
        license: "cc",
        licenseText: "Creative Commons BY 3.0",
        qualities: ["MP3 320kbps"],
        sizeMb: 9.6,
        camelotKey: "9B",
        musicalKey: "G Major",
        bpm: 96
    },
    {
        id: "8",
        title: "Retro Soul",
        artist: "BenSound",
        album: "Royalty Free Grooves",
        duration: "03:43",
        cover: "https://images.unsplash.com/photo-1498038432885-c6f3f1b912ee?w=400&q=80",
        license: "user", // user catalog/licensed
        licenseText: "Licencia de Usuario Autorizada",
        qualities: ["AAC 256kbps", "MP3 320kbps"],
        sizeMb: 8.5,
        camelotKey: "8A",
        musicalKey: "A Minor",
        bpm: 115
    }
];

// App State
const state = {
    currentTab: "search",
    searchQuery: "",
    activeFilter: "all", // "all", "cc", "pd", "user"
    downloads: [],
    library: [],
    settings: {
        destinationFolder: "C:\\Users\\USUARIO\\Music\\TIDAL",
        format: "flac",
        quality: "lossless",
        maxConcurrent: 2
    },
    currentlyPlaying: null,
    isPlaying: false,
    searchResults: [], // Real time Tidal search results cached
    trackCache: {} // Cache of all track metadata by ID
};

// Elements DOM
const elements = {
    navItems: document.querySelectorAll('.nav-item'),
    sections: document.querySelectorAll('.view-section'),
    searchInput: document.getElementById('search-input'),
    filterTags: document.querySelectorAll('.filter-tag'),
    resultsGrid: document.getElementById('results-grid'),
    downloadQueue: document.getElementById('download-queue'),
    libraryList: document.getElementById('library-list'),
    
    // Settings
    folderInput: document.getElementById('dest-folder'),
    btnBrowse: document.getElementById('btn-browse'),
    selectFormat: document.getElementById('pref-format'),
    selectQuality: document.getElementById('pref-quality'),
    rangeConcurrent: document.getElementById('limit-concurrent'),
    valConcurrent: document.getElementById('val-concurrent'),
    
    // Player
    playerCover: document.getElementById('player-cover'),
    playerTitle: document.getElementById('player-title'),
    playerArtist: document.getElementById('player-artist'),
    btnPlay: document.getElementById('btn-play'),
    timelineSlider: document.getElementById('timeline-slider'),
    timeCurrent: document.getElementById('time-current'),
    timeTotal: document.getElementById('time-total'),
    
    // Mini Download Status footer
    miniDlStatus: document.getElementById('mini-dl-status'),
    miniDlCount: document.getElementById('mini-dl-count'),
    
    toastContainer: document.getElementById('toast-container'),
    realAudioElement: document.getElementById('real-audio-element')
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    // Populate cache with mock database
    MOCK_DATABASE.forEach(song => {
        state.trackCache[song.id] = song;
    });

    initNavigation();
    initFilters();
    initSearch();
    initSettings();
    initPlayer();
    
    // Render initial grid
    renderSearchGrid();
    renderLibrary();
});

// 1. Navigation Flow
function initNavigation() {
    elements.navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetTab = item.getAttribute('data-tab');
            switchTab(targetTab);
        });
    });
}

function switchTab(tabName) {
    state.currentTab = tabName;
    
    // Update active navbar item
    elements.navItems.forEach(item => {
        if (item.getAttribute('data-tab') === tabName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
    
    // Update section visibility
    elements.sections.forEach(sec => {
        if (sec.id === `${tabName}-section`) {
            sec.classList.add('active');
        } else {
            sec.classList.remove('active');
        }
    });
}

// 2. Search & Filters
function initFilters() {
    elements.filterTags.forEach(tag => {
        tag.addEventListener('click', () => {
            elements.filterTags.forEach(t => t.classList.remove('active'));
            tag.classList.add('active');
            state.activeFilter = tag.getAttribute('data-filter');
            renderSearchGrid();
        });
    });
}

function initSearch() {
    let debounceTimer;
    elements.searchInput.addEventListener('input', (e) => {
        state.searchQuery = e.target.value.toLowerCase();
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            renderSearchGrid();
        }, 300); // Debounce to prevent API flooding
    });
}

async function renderSearchGrid() {
    const queryVal = state.searchQuery;
    
    if (!queryVal) {
        // Render local mock database if search is empty
        state.searchResults = MOCK_DATABASE;
        renderGridList(state.searchResults);
        return;
    }
    
    elements.resultsGrid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 48px; color: var(--text-muted);">
            <p>Buscando en catálogo de Tidal...</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(queryVal)}`);
        if (!response.ok) throw new Error("Search failed");
        
        const realSongs = await response.json();
        
        // Populate track cache
        realSongs.forEach(song => {
            state.trackCache[song.id] = song;
        });
        
        // Merge mock database and real songs for demonstration
        state.searchResults = [...realSongs];
        renderGridList(state.searchResults);
    } catch (err) {
        console.error("Search error, falling back to mock database:", err);
        // Fallback to local mock database matching search
        const fallback = MOCK_DATABASE.filter(song => {
            return song.title.toLowerCase().includes(queryVal) ||
                   song.artist.toLowerCase().includes(queryVal) ||
                   song.album.toLowerCase().includes(queryVal);
        });
        state.searchResults = fallback;
        renderGridList(state.searchResults);
    }
}

function renderGridList(songsList) {
    elements.resultsGrid.innerHTML = "";
    
    const filteredSongs = songsList.filter(song => {
        // Tag Filter
        return state.activeFilter === "all" || song.license === state.activeFilter;
    });
    
    if (filteredSongs.length === 0) {
        elements.resultsGrid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 48px; color: var(--text-muted);">
                <p>No se encontraron canciones con la licencia seleccionada.</p>
            </div>
        `;
        return;
    }
    
    filteredSongs.forEach(song => {
        const isDownloading = state.downloads.some(d => d.songId === song.id && (d.status === 'downloading' || d.status === 'queued'));
        const isCompleted = state.downloads.some(d => d.songId === song.id && d.status === 'completed');
        
        let buttonHtml = '';
        if (isCompleted) {
            buttonHtml = `<button class="btn btn-secondary" style="flex: 1;" disabled>Completado</button>`;
        } else if (isDownloading) {
            buttonHtml = `<button class="btn btn-secondary" style="flex: 1;" disabled>Descargando...</button>`;
        } else {
            buttonHtml = `<button class="btn btn-primary" style="flex: 1;" onclick="startDownload('${song.id}')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                Descargar
            </button>`;
        }

        let previewButtonHtml = '';
        if (song.license === 'user') { // it's a real track from Tidal search
            previewButtonHtml = `<button class="btn btn-secondary btn-icon-only" title="Escuchar Vista Previa" onclick="playSong('${song.id}', true)" style="margin-right: 4px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </button>`;
        }

        const card = document.createElement('div');
        card.className = "music-card";
        card.innerHTML = `
            <div class="card-cover-container">
                <img class="card-cover" src="${song.cover}" alt="${song.title}" onerror="this.src='https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80'">
                <div class="legal-indicator ${song.license}">${song.licenseText}</div>
            </div>
            <div class="card-info">
                <div class="card-title" title="${song.title}">${song.title}</div>
                <div class="card-artist" title="${song.artist}">${song.artist}</div>
                <div class="card-meta">
                    <span>${song.duration}</span>
                    <span class="card-quality">${song.qualities[0]}</span>
                    ${song.camelotKey ? `<span class="camelot-badge" title="Clave Armónica: ${song.musicalKey}">${song.camelotKey}</span>` : ''}
                    ${song.bpm ? `<span class="bpm-badge" title="Tempo: ${song.bpm} BPM">${song.bpm} BPM</span>` : ''}
                </div>
            </div>
            <div class="card-actions">
                ${previewButtonHtml}
                ${buttonHtml}
                <button class="btn btn-secondary btn-icon-only" title="Descargar Álbum Completo" onclick="startAlbumDownload('${song.album}')">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13M9 9H4a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h5a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2z"/></svg>
                </button>
            </div>
        `;
        elements.resultsGrid.appendChild(card);
    });
}

// 3. Settings Config
function initSettings() {
    // Destination Folder Input
    elements.folderInput.value = state.settings.destinationFolder;
    elements.folderInput.addEventListener('change', (e) => {
        state.settings.destinationFolder = e.target.value;
    });
    
    // Browse Folder Simulation
    elements.btnBrowse.addEventListener('click', () => {
        const mockPaths = [
            "C:\\Users\\USUARIO\\Music\\TIDAL",
            "D:\\Musica\\TidalDownloads",
            "C:\\Downloads\\TidalFiles"
        ];
        const randomPath = mockPaths[Math.floor(Math.random() * mockPaths.length)];
        state.settings.destinationFolder = randomPath;
        elements.folderInput.value = randomPath;
        showToast("Carpeta de destino actualizada correctamente");
    });
    
    // Format Selection
    elements.selectFormat.value = state.settings.format;
    elements.selectFormat.addEventListener('change', (e) => {
        state.settings.format = e.target.value;
        showToast(`Formato preferido cambiado a ${e.target.value.toUpperCase()}`);
    });
    
    // Quality Selection
    elements.selectQuality.value = state.settings.quality;
    elements.selectQuality.addEventListener('change', (e) => {
        state.settings.quality = e.target.value;
        showToast(`Calidad de descarga establecida a ${e.target.options[e.target.selectedIndex].text}`);
    });
    
    // Concurrent Limit Slider
    elements.rangeConcurrent.value = state.settings.maxConcurrent;
    elements.valConcurrent.innerText = state.settings.maxConcurrent;
    elements.rangeConcurrent.addEventListener('input', (e) => {
        state.settings.maxConcurrent = parseInt(e.target.value);
        elements.valConcurrent.innerText = e.target.value;
    });
}

// 4. Download Queue Logic & Simulation (Hybrid real + visual simulation)
function startDownload(songId) {
    const song = state.trackCache[songId] || state.searchResults.find(s => s.id === songId);
    if (!song) return;
    
    // Check if already in downloads
    if (state.downloads.some(d => d.songId === songId && d.status !== 'error')) {
        showToast("Esta canción ya está en la cola de descarga.");
        return;
    }
    
    const formatLabel = state.settings.format === 'flac' ? 'FLAC' : `MP3 ${state.settings.quality}kbps`;
    
    const newDownload = {
        id: "DL_" + Date.now() + "_" + Math.floor(Math.random()*1000),
        songId: song.id,
        title: song.title,
        artist: song.artist,
        cover: song.cover,
        quality: formatLabel,
        progress: 0,
        speed: "0 KB/s",
        status: "queued", // "queued", "downloading", "completed", "error"
        sizeMb: song.sizeMb
    };
    
    state.downloads.push(newDownload);
    renderSearchGrid();
    renderDownloadQueue();
    updateMiniDlStatus();
    
    showToast(`"${song.title}" añadida a la cola de descargas.`);
    
    // Process queue
    processQueue();
}

function startAlbumDownload(albumName) {
    const songs = state.searchResults.filter(s => s.album === albumName);
    songs.forEach(song => {
        startDownload(song.id);
    });
    showToast(`Iniciando descarga del álbum "${albumName}" (${songs.length} pistas)`);
}

function processQueue() {
    const activeCount = state.downloads.filter(d => d.status === 'downloading').length;
    
    if (activeCount >= state.settings.maxConcurrent) {
        return; // Limit reached
    }
    
    const nextInQueue = state.downloads.find(d => d.status === 'queued');
    if (nextInQueue) {
        simulateDownload(nextInQueue);
    }
}

function simulateDownload(downloadItem) {
    downloadItem.status = "downloading";
    renderDownloadQueue();
    updateMiniDlStatus();
    
    const qualityVal = state.settings.quality === 'lossless' ? 'hires' : 
                      state.settings.quality === '320' ? 'high' : 'low';
    
    // Call the actual Python backend to start background download via tidal_mvp
    fetch(`/api/download?id=${downloadItem.songId}&out=${encodeURIComponent(state.settings.destinationFolder)}&quality=${qualityVal}`)
        .then(res => {
            if (!res.ok) throw new Error("Failed to start backend download");
            return res.json();
        })
        .catch(err => {
            console.error("Backend trigger failed:", err);
            // If API fails, fall back to pure simulation
        });

    const intervalTime = 500;
    let visualProgress = 0;
    
    let timer = setInterval(async () => {
        if (downloadItem.status === 'cancelled') {
            clearInterval(timer);
            return;
        }

        if (downloadItem.status === 'error') {
            clearInterval(timer);
            return;
        }

        // Advance visual progress slowly up to 92%
        if (visualProgress < 92) {
            visualProgress += (92 - visualProgress) * 0.1 + 1.5;
            if (visualProgress > 92) visualProgress = 92;
            downloadItem.progress = visualProgress;
            
            const currentSpeed = (2.2 + Math.random() * 3.5).toFixed(1);
            downloadItem.speed = `${currentSpeed} MB/s`;
            renderDownloadQueue();
        }

        // Poll backend process status
        try {
            const statusRes = await fetch(`/api/download/status?ids=${downloadItem.songId}`);
            if (statusRes.ok) {
                const statusMap = await statusRes.json();
                const backendStatus = statusMap[downloadItem.songId];
                
                if (backendStatus === 'completed') {
                    downloadItem.progress = 100;
                    downloadItem.status = "completed";
                    downloadItem.speed = "0 KB/s";
                    clearInterval(timer);
                    
                    // Add to library
                    addToLibrary(downloadItem.songId);
                    
                    showToast(`¡Descarga completada! "${downloadItem.title}"`);
                    renderSearchGrid();
                    renderDownloadQueue();
                    updateMiniDlStatus();
                    
                    // Trigger next
                    processQueue();
                } else if (backendStatus === 'error') {
                    downloadItem.status = "error";
                    downloadItem.speed = "0 KB/s";
                    clearInterval(timer);
                    showToast(`Error al descargar "${downloadItem.title}".`);
                    renderDownloadQueue();
                    updateMiniDlStatus();
                    processQueue();
                }
            }
        } catch (e) {
            console.error("Error polling backend status:", e);
        }
    }, intervalTime);
}

function cancelDownload(downloadId) {
    const item = state.downloads.find(d => d.id === downloadId);
    if (!item) return;
    
    if (item.status === 'downloading') {
        item.status = 'cancelled';
    }
    
    state.downloads = state.downloads.filter(d => d.id !== downloadId);
    renderSearchGrid();
    renderDownloadQueue();
    updateMiniDlStatus();
    
    showToast(`Descarga de "${item.title}" cancelada.`);
    processQueue(); // Start next if slots freed
}

function retryDownload(downloadId) {
    const item = state.downloads.find(d => d.id === downloadId);
    if (!item) return;
    
    item.status = "queued";
    item.progress = 0;
    item.speed = "0 KB/s";
    
    renderDownloadQueue();
    updateMiniDlStatus();
    processQueue();
}

function renderDownloadQueue() {
    elements.downloadQueue.innerHTML = "";
    
    const activeDownloads = state.downloads.filter(d => d.status !== 'completed');
    
    if (activeDownloads.length === 0) {
        elements.downloadQueue.innerHTML = `
            <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                <p>La cola de descargas está vacía.</p>
            </div>
        `;
        return;
    }
    
    activeDownloads.forEach(item => {
        let statusText = '';
        let statusClass = '';
        let actionBtn = '';
        
        if (item.status === 'queued') {
            statusText = 'En cola';
            statusClass = 'queued';
            actionBtn = `<button class="btn btn-secondary btn-icon-only" onclick="cancelDownload('${item.id}')" title="Cancelar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>`;
        } else if (item.status === 'downloading') {
            statusText = 'Descargando';
            statusClass = 'downloading';
            actionBtn = `<button class="btn btn-secondary btn-icon-only" onclick="cancelDownload('${item.id}')" title="Cancelar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>`;
        } else if (item.status === 'error') {
            statusText = 'Error';
            statusClass = 'error';
            actionBtn = `
                <button class="btn btn-secondary btn-icon-only" onclick="retryDownload('${item.id}')" title="Reintentar" style="border-color: var(--warning); color: var(--warning);">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
                </button>
                <button class="btn btn-secondary btn-icon-only" onclick="cancelDownload('${item.id}')" title="Eliminar">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            `;
        }
        
        const card = document.createElement('div');
        card.className = "download-item";
        card.innerHTML = `
            <img class="download-item-cover" src="${item.cover}" alt="${item.title}" onerror="this.src='https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=100&q=80'">
            <div class="download-item-details">
                <span class="download-item-name">${item.title}</span>
                <span class="download-item-artist">${item.artist}</span>
            </div>
            <div class="download-progress-container">
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: ${item.progress}%"></div>
                </div>
                <div class="download-progress-meta">
                    <span>${Math.round(item.progress)}% • ${item.speed}</span>
                    <span>${(item.sizeMb * (item.progress/100)).toFixed(1)} / ${item.sizeMb.toFixed(1)} MB</span>
                </div>
            </div>
            <div style="margin: 0 10px;">
                <span class="download-status-badge ${statusClass}">${statusText}</span>
            </div>
            <div class="download-item-actions">
                ${actionBtn}
            </div>
        `;
        elements.downloadQueue.appendChild(card);
    });
}

function updateMiniDlStatus() {
    const activeDlCount = state.downloads.filter(d => d.status === 'downloading' || d.status === 'queued').length;
    if (activeDlCount > 0) {
        elements.miniDlStatus.style.display = "flex";
        elements.miniDlCount.innerText = `${activeDlCount} activa(s)`;
    } else {
        elements.miniDlStatus.style.display = "none";
    }
}

// 5. Library Management
function addToLibrary(songId) {
    if (state.library.some(id => id === songId)) return;
    state.library.push(songId);
    renderLibrary();
}

function renderLibrary() {
    elements.libraryList.innerHTML = "";
    
    if (state.library.length === 0) {
        elements.libraryList.innerHTML = `
            <div style="text-align: center; padding: 48px; color: var(--text-muted);">
                <p>Tu biblioteca local está vacía. Descarga música para verla aquí.</p>
            </div>
        `;
        return;
    }
    
    state.library.forEach(songId => {
        const song = state.trackCache[songId] || state.searchResults.find(s => s.id === songId);
        if (!song) return;
        
        const row = document.createElement('div');
        row.className = "download-item";
        row.innerHTML = `
            <img class="download-item-cover" src="${song.cover}" alt="${song.title}" onerror="this.src='https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=100&q=80'">
            <div class="download-item-details">
                <span class="download-item-name">${song.title}</span>
                <span class="download-item-artist">${song.artist} • ${song.album}</span>
            </div>
            <div style="margin-right: 20px; display: flex; align-items: center;">
                ${song.camelotKey ? `<span class="camelot-badge" title="Clave Armónica: ${song.musicalKey}" style="margin-right: 6px; margin-left: 0;">${song.camelotKey}</span>` : ''}
                ${song.bpm ? `<span class="bpm-badge" title="Tempo: ${song.bpm} BPM" style="margin-right: 12px; margin-left: 0;">${song.bpm} BPM</span>` : ''}
                <span style="color: var(--text-muted); font-size: 0.9rem;">${song.duration}</span>
            </div>
            <div style="margin-right: 20px;">
                <span class="legal-indicator ${song.license}" style="position: relative; top: 0; right: 0; display: inline-block;">${song.licenseText}</span>
            </div>
            <div class="download-item-actions">
                <button class="btn btn-primary btn-icon-only" onclick="playSong('${song.id}')" title="Reproducir">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                </button>
                <button class="btn btn-secondary btn-icon-only" onclick="openMockFolder()" title="Abrir ubicación de archivo">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                </button>
            </div>
        `;
        elements.libraryList.appendChild(row);
    });
}

function openMockFolder() {
    showToast(`Abriendo ubicación de archivo en: "${state.settings.destinationFolder}"`);
}

// 6. Audio Player Integration (Real HTML5 Audio)
let playerSliderDragging = false;

function initPlayer() {
    // Play / Pause button
    elements.btnPlay.addEventListener('click', () => {
        togglePlay();
    });

    // Audio Element Event Listeners
    elements.realAudioElement.addEventListener('timeupdate', () => {
        if (playerSliderDragging) return;
        
        const curTime = elements.realAudioElement.currentTime;
        const duration = elements.realAudioElement.duration || 1;
        
        // Update slider value
        elements.timelineSlider.value = (curTime / duration) * 100;
        
        // Update current time text
        elements.timeCurrent.innerText = formatTimeSeconds(curTime);
    });

    elements.realAudioElement.addEventListener('durationchange', () => {
        elements.timeTotal.innerText = formatTimeSeconds(elements.realAudioElement.duration);
    });

    elements.realAudioElement.addEventListener('play', () => {
        state.isPlaying = true;
        elements.btnPlay.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`;
    });

    elements.realAudioElement.addEventListener('pause', () => {
        state.isPlaying = false;
        elements.btnPlay.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>`;
    });

    elements.realAudioElement.addEventListener('ended', () => {
        state.isPlaying = false;
        elements.btnPlay.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>`;
        elements.timelineSlider.value = 0;
        elements.timeCurrent.innerText = "00:00";
    });

    // Slider dragging
    elements.timelineSlider.addEventListener('mousedown', () => {
        playerSliderDragging = true;
    });

    elements.timelineSlider.addEventListener('mouseup', () => {
        playerSliderDragging = false;
        const duration = elements.realAudioElement.duration || 0;
        elements.realAudioElement.currentTime = (elements.timelineSlider.value / 100) * duration;
    });

    elements.timelineSlider.addEventListener('change', () => {
        const duration = elements.realAudioElement.duration || 0;
        elements.realAudioElement.currentTime = (elements.timelineSlider.value / 100) * duration;
    });
}

function formatTimeSeconds(secondsNum) {
    if (isNaN(secondsNum)) return "00:00";
    const minutes = Math.floor(secondsNum / 60);
    const seconds = Math.floor(secondsNum % 60);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

function playSong(songId, isPreview = false) {
    const song = state.trackCache[songId] || state.searchResults.find(s => s.id === songId);
    if (!song) return;
    
    state.currentlyPlaying = song;
    
    // Set Audio Source
    if (isPreview) {
        elements.realAudioElement.src = `/api/preview?id=${songId}`;
        elements.playerTitle.innerText = song.title + " (Vista Previa)";
        showToast(`Escuchando vista previa de: "${song.title}"`);
    } else {
        elements.realAudioElement.src = `/api/stream?id=${songId}`;
        elements.playerTitle.innerText = song.title;
        showToast(`Reproduciendo archivo local: "${song.title}"`);
    }
    
    // Update player panel metadata
    elements.playerCover.src = song.cover;
    elements.playerArtist.innerText = song.artist;
    elements.timeTotal.innerText = song.duration;
    elements.timeCurrent.innerText = "00:00";
    elements.timelineSlider.value = 0;

    // Load and Play Audio
    elements.realAudioElement.load();
    elements.realAudioElement.play().catch(err => {
        console.error("Playback failed:", err);
        showToast("Error al reproducir. Verifica que el archivo esté descargado o la conexión.");
    });
}

function togglePlay() {
    if (!state.currentlyPlaying) {
        if (state.library.length > 0) {
            playSong(state.library[0]);
        } else {
            showToast("Primero reproduce una vista previa o descarga una canción.");
        }
        return;
    }
    
    if (elements.realAudioElement.paused) {
        elements.realAudioElement.play().catch(err => console.error("Play failed:", err));
        showToast(`Reanudando: "${state.currentlyPlaying.title}"`);
    } else {
        elements.realAudioElement.pause();
        showToast("Música en pausa");
    }
}

// 7. Toast Alerts UI Helper
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = "toast";
    toast.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4L12 14.01l-3-3"/></svg>
        <span class="toast-message">${message}</span>
    `;
    elements.toastContainer.appendChild(toast);
    
    // Remove toast after 3 seconds
    setTimeout(() => {
        toast.style.transform = "translateX(120%)";
        toast.style.opacity = "0";
        setTimeout(() => {
            elements.toastContainer.removeChild(toast);
        }, 300);
    }, 3000);
}
