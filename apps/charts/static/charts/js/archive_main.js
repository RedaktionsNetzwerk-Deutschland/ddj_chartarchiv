/**
 * JavaScript für die Archiv-Hauptseite
 * Enthält die Logik für die Suche und Anzeige von Grafiken
 */

// Namespace für die Archiv-Funktionalität
const ArchiveApp = {
    // Konfiguration
    config: {
        searchDelay: 300,  // Verzögerung für die Suche in ms
        pageSize: 50,      // Anzahl der Grafiken pro Seite
        currentPage: 1,    // Aktuelle Seite
        totalResults: 0,   // Gesamtanzahl der Ergebnisse
        searchQuery: '',   // Aktueller Suchbegriff
        selectedTags: [],  // Ausgewählte Tags
        isLoading: false   // Ladezustand
    },
    
    // Initialisierung
    init: function() {
        this.setupEventListeners();
        this.loadCharts();
        
        // Initialisiere Bootstrap-Komponenten
        this.initializeTooltips();
        this.initializePopovers();
    },
    
    // Event-Listener Setup
    setupEventListeners: function() {
        // Suchfeld
        $('#searchInput').on('input', this.debounce(() => {
            this.config.searchQuery = $('#searchInput').val();
            this.config.currentPage = 1;
            this.loadCharts();
        }, this.config.searchDelay));
        
        // Tag-Filter
        $('.tag-filter').on('click', (e) => {
            const tag = $(e.currentTarget).data('tag');
            this.toggleTag(tag);
        });
        
        // Pagination
        $('#loadMore').on('click', () => {
            this.config.currentPage++;
            this.loadCharts(true);
        });
        
        // Sortierung
        $('#sortSelect').on('change', () => {
            this.config.currentPage = 1;
            this.loadCharts();
        });
        
        // Filter-Reset
        $('#resetFilters').on('click', () => {
            this.resetFilters();
        });
    },
    
    // Grafiken laden
    loadCharts: function(append = false) {
        if (this.config.isLoading) return;
        this.config.isLoading = true;
        
        // Lade-Animation anzeigen
        if (!append) {
            $('#chartGrid').html('<div class="text-center"><div class="loading-spinner"></div></div>');
        }
        
        // API-Parameter
        const params = {
            q: this.config.searchQuery,
            tags: this.config.selectedTags,
            limit: this.config.pageSize,
            offset: (this.config.currentPage - 1) * this.config.pageSize,
            sort: $('#sortSelect').val()
        };
        
        // API-Anfrage
        RNDArchive.apiRequest('/charts/search/', { params })
            .then(response => {
                this.config.totalResults = response.total_count;
                this.updateResults(response.results, append);
                this.updatePagination();
            })
            .catch(error => {
                RNDArchive.showError('Fehler beim Laden der Grafiken');
                console.error('Fehler beim Laden der Grafiken:', error);
            })
            .finally(() => {
                this.config.isLoading = false;
            });
    },
    
    // Ergebnisse aktualisieren
    updateResults: function(charts, append = false) {
        const container = $('#chartGrid');
        
        if (!append) {
            container.empty();
        }
        
        if (charts.length === 0 && !append) {
            container.html(`
                <div class="text-center my-5">
                    <i class="fas fa-search fa-3x text-muted mb-3"></i>
                    <h4>Keine Grafiken gefunden</h4>
                    <p class="text-muted">Versuchen Sie es mit anderen Suchbegriffen oder Filtern.</p>
                </div>
            `);
            return;
        }
        
        const chartElements = charts.map(chart => this.createChartElement(chart));
        container.append(chartElements);
        
        // Initialisiere Tooltips für neue Elemente
        this.initializeTooltips();
    },
    
    // Grafik-Element erstellen
    createChartElement: function(chart) {
        return `
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card h-100">
                    <div class="card-img-top position-relative">
                        ${chart.thumbnail ? `
                            <img src="${chart.thumbnail}" class="img-fluid" alt="${chart.title}">
                        ` : `
                            <div class="placeholder-image">
                                <i class="fas fa-chart-bar fa-3x text-muted"></i>
                            </div>
                        `}
                        ${chart.is_archived ? `
                            <span class="badge bg-warning position-absolute top-0 end-0 m-2">
                                <i class="fas fa-archive"></i> Archiviert
                            </span>
                        ` : ''}
                    </div>
                    <div class="card-body">
                        <h5 class="card-title text-truncate" title="${chart.title}">
                            ${chart.title}
                        </h5>
                        <p class="card-text small text-muted mb-2">
                            <i class="fas fa-hashtag"></i> ${chart.chart_id}
                        </p>
                        <p class="card-text text-truncate" title="${chart.description}">
                            ${chart.description || 'Keine Beschreibung'}
                        </p>
                        <div class="tags mb-3">
                            ${chart.tags.map(tag => `
                                <span class="badge bg-secondary me-1">${tag}</span>
                            `).join('')}
                        </div>
                    </div>
                    <div class="card-footer bg-transparent">
                        <div class="d-flex justify-content-between align-items-center">
                            <small class="text-muted">
                                <i class="far fa-calendar-alt"></i>
                                ${RNDArchive.formatDate(chart.published_date)}
                            </small>
                            <div class="btn-group">
                                <a href="/charts/${chart.chart_id}/" class="btn btn-sm btn-outline-primary"
                                   title="Details anzeigen">
                                    <i class="fas fa-info-circle"></i>
                                </a>
                                <a href="/charts/${chart.chart_id}/print/" class="btn btn-sm btn-outline-secondary"
                                   title="Druckansicht">
                                    <i class="fas fa-print"></i>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },
    
    // Pagination aktualisieren
    updatePagination: function() {
        const totalPages = Math.ceil(this.config.totalResults / this.config.pageSize);
        const loadMoreBtn = $('#loadMore');
        
        if (this.config.currentPage >= totalPages) {
            loadMoreBtn.hide();
        } else {
            loadMoreBtn.show();
        }
        
        // Aktualisiere Ergebnis-Zähler
        $('#resultCount').text(
            `${this.config.totalResults} Grafik${this.config.totalResults !== 1 ? 'en' : ''} gefunden`
        );
    },
    
    // Tag-Filter umschalten
    toggleTag: function(tag) {
        const index = this.config.selectedTags.indexOf(tag);
        if (index === -1) {
            this.config.selectedTags.push(tag);
        } else {
            this.config.selectedTags.splice(index, 1);
        }
        
        // Aktualisiere UI
        $(`.tag-filter[data-tag="${tag}"]`).toggleClass('active');
        
        // Lade Grafiken neu
        this.config.currentPage = 1;
        this.loadCharts();
    },
    
    // Filter zurücksetzen
    resetFilters: function() {
        this.config.searchQuery = '';
        this.config.selectedTags = [];
        this.config.currentPage = 1;
        
        // UI zurücksetzen
        $('#searchInput').val('');
        $('.tag-filter').removeClass('active');
        $('#sortSelect').val('published_date');
        
        // Grafiken neu laden
        this.loadCharts();
    },
    
    // Bootstrap Tooltips initialisieren
    initializeTooltips: function() {
        $('[data-bs-toggle="tooltip"]').tooltip();
    },
    
    // Bootstrap Popovers initialisieren
    initializePopovers: function() {
        $('[data-bs-toggle="popover"]').popover();
    },
    
    // Debounce-Funktion für die Suche
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// Initialisierung nach dem Laden des Dokuments
$(document).ready(function() {
    ArchiveApp.init();
}); 