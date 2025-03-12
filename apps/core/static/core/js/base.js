/**
 * Basis-JavaScript für das RND Archive Projekt
 * Enthält grundlegende Funktionen, die auf allen Seiten verwendet werden
 */

// Namespace für die Anwendung
const RNDArchive = {
    // Konfiguration
    config: {
        apiBaseUrl: '/api/v1',
        debugMode: false,
        toastDuration: 5000
    },
    
    // Initialisierung
    init: function() {
        this.setupEventListeners();
        this.setupTooltips();
        this.setupToasts();
        
        if (this.config.debugMode) {
            console.log('RND Archive initialized');
        }
    },
    
    // Event-Listener Setup
    setupEventListeners: function() {
        // Globaler Ajax-Error-Handler
        $(document).ajaxError(function(event, jqXHR, settings, error) {
            RNDArchive.showError('Ein Fehler ist aufgetreten: ' + error);
        });
        
        // Logout-Bestätigung
        $('.logout-link').on('click', function(e) {
            e.preventDefault();
            if (confirm('Möchten Sie sich wirklich abmelden?')) {
                window.location = this.href;
            }
        });
    },
    
    // Bootstrap Tooltips initialisieren
    setupTooltips: function() {
        $('[data-bs-toggle="tooltip"]').tooltip();
    },
    
    // Bootstrap Toasts initialisieren
    setupToasts: function() {
        $('.toast').toast({
            autohide: true,
            delay: this.config.toastDuration
        });
    },
    
    // Hilfsfunktionen für UI-Feedback
    
    /**
     * Zeigt eine Erfolgsmeldung an
     * @param {string} message - Die anzuzeigende Nachricht
     */
    showSuccess: function(message) {
        this.showToast(message, 'success');
    },
    
    /**
     * Zeigt eine Fehlermeldung an
     * @param {string} message - Die anzuzeigende Nachricht
     */
    showError: function(message) {
        this.showToast(message, 'danger');
    },
    
    /**
     * Zeigt einen Toast an
     * @param {string} message - Die anzuzeigende Nachricht
     * @param {string} type - Der Typ des Toasts (success, danger, warning, info)
     */
    showToast: function(message, type = 'info') {
        const toast = `
            <div class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Schließen"></button>
                </div>
            </div>
        `;
        
        $('.toast-container').append(toast);
        $('.toast').toast('show');
    },
    
    /**
     * Zeigt einen Lade-Spinner an
     * @param {string} containerId - Die ID des Containers für den Spinner
     * @param {string} message - Optional: Eine Nachricht, die angezeigt werden soll
     */
    showSpinner: function(containerId, message = 'Laden...') {
        const spinner = `
            <div class="text-center">
                <div class="loading-spinner"></div>
                <p class="mt-2">${message}</p>
            </div>
        `;
        $(`#${containerId}`).html(spinner);
    },
    
    /**
     * Formatiert ein Datum in deutsches Format
     * @param {string} dateString - Das zu formatierende Datum
     * @returns {string} Das formatierte Datum
     */
    formatDate: function(dateString) {
        const options = { 
            year: 'numeric', 
            month: '2-digit', 
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        };
        return new Date(dateString).toLocaleDateString('de-DE', options);
    },
    
    /**
     * Führt eine API-Anfrage aus
     * @param {string} endpoint - Der API-Endpunkt
     * @param {Object} options - Optionen für die Anfrage
     * @returns {Promise} Ein Promise mit der Antwort
     */
    apiRequest: async function(endpoint, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            }
        };
        
        try {
            const response = await fetch(
                `${this.config.apiBaseUrl}${endpoint}`,
                { ...defaultOptions, ...options }
            );
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            this.showError('API-Anfrage fehlgeschlagen');
            throw error;
        }
    },
    
    /**
     * Holt das CSRF-Token aus dem Cookie
     * @returns {string} Das CSRF-Token
     */
    getCsrfToken: function() {
        return document.cookie.split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1] || '';
    }
};

// Initialisierung nach dem Laden des Dokuments
$(document).ready(function() {
    RNDArchive.init();
}); 