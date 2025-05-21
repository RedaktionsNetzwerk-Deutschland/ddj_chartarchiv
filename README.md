# RND-Grafikarchiv

## Überblick

Das RND-Grafikarchiv ist eine Django-basierte Webanwendung für die zentrale Verwaltung, Speicherung und Nutzung von Datenvisualisierungen und interaktiven Grafiken. Die Plattform ermöglicht Redakteuren das einfache Suchen, Filtern und Exportieren von Grafiken sowie die Erstellung neuer Visualisierungen mit einem integrierten Chartmaker.

![RND-Grafikarchiv Screenshot](staticfiles/core/img/screenshot.png)

## Funktionen

- **Benutzerauthentifizierung**: Registrierung, Login, Passwort-Reset
- **Grafik-Archiv**: Zentrale Datenbank für Grafiken mit umfangreichen Filtermöglichkeiten
- **Thematische Organisation**: Hierarchische Kategorisierung von Grafiken in Haupt- und Unterthemen
- **Erweiterte Suche**: Feldspezifische Suche nach Titeln, Tags, Autoren etc.
- **Grafik-Detailansicht**: Umfassende Metadaten und Export-Optionen
- **Export-Funktionen**: Print-Export (PDF, DCX), Online-Export (Einbettungscode)
- **Chartmaker**: KI-gestütztes Tool zur Erstellung neuer Grafiken


## Technischer Stack

- **Backend**: Django 5.1
- **Datenbank**: MySQL/PostgreSQL
- **Frontend**: HTML, CSS, JavaScript
- **Containerisierung**: Docker, Docker-Compose
- **Datenwrapper-API**: Integration für Grafikerstellung und -bearbeitung
- **OpenAI-API**: KI-Unterstützung für Datenanalysen

## Installation

### Voraussetzungen

- Python 3.10+
- Docker und Docker-Compose (optional)
- MySQL oder PostgreSQL

### Installation mit Docker (empfohlen)

1. Repository klonen:
   ```bash
   git clone https://https://github.com/RedaktionsNetzwerk-Deutschland/ddj_chartarchiv.git
   cd ddj_chartarchiv
   ```

2. Umgebungsvariablen konfigurieren:
   ```bash
   cp .env.example .env
   # .env-Datei mit eigenen Werten bearbeiten
   ```

3. Container starten:
   ```bash
   docker-compose up -d
   ```

4. Datenbank-Migrationen durchführen:
   ```bash
   docker-compose exec web python manage.py migrate
   ```

5. Statische Dateien sammeln:
   ```bash
   docker-compose exec web python manage.py collectstatic
   ```

### Manuelle Installation

1. Repository klonen:
   ```bash
   git clone https://https://github.com/RedaktionsNetzwerk-Deutschland/ddj_chartarchiv.git
   cd archive_production
   ```

2. Virtuelle Umgebung erstellen und aktivieren:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Unix/macOS
   # oder
   venv\Scripts\activate  # Windows
   ```

3. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

4. Umgebungsvariablen konfigurieren:
   ```bash
   cp .env.example .env
   # .env-Datei bearbeiten
   ```

5. Datenbank-Migrationen durchführen:
   ```bash
   python manage.py migrate
   ```

6. Einen Admin-Benutzer erstellen:
   ```bash
   python manage.py createsuperuser
   ```

7. Entwicklungsserver starten:
   ```bash
   python manage.py runserver
   ```

## Konfiguration

### Umgebungsvariablen

Die Anwendung wird über `.env`-Dateien konfiguriert. Wichtige Variablen sind:

```
# Datenbankeinstellungen
DB_NAME=grafikarchiv
DB_USER=user
DB_PASSWORD=password
DB_HOST=localhost

# Django-Einstellungen
DJANGO_SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=localhost,grafikarchiv.rndtech.de

# Datawrapper-API
DATAWRAPPER_API_KEY=your-api-key

# E-Mail-Konfiguration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-password
```

### Datawrapper-Integration

Für die Nutzung des Chartmakers wird ein Datawrapper-API-Key benötigt. Diesen kannst du in deinem Datawrapper-Account erstellen und in der `.env`-Datei konfigurieren.

## Produktionsumgebung

Für den Einsatz in einer Produktionsumgebung beachte diese zusätzlichen Schritte:

1. Debug-Modus deaktivieren:
   ```
   DEBUG=False
   ```

2. Sichere HTTPS-Verbindung konfigurieren:
   ```
   SECURE_SSL_REDIRECT=True
   SESSION_COOKIE_SECURE=True
   CSRF_COOKIE_SECURE=True
   ```

3. ALLOWED_HOSTS anpassen:
   ```
   ALLOWED_HOSTS=grafikarchiv.rndtech.de
   ```

4. Webserver (Nginx/Apache) mit Gunicorn konfigurieren

## Entwicklung

### Lokale Entwicklung

1. Debug-Modus aktivieren:
   ```
   DEBUG=True
   ```

2. Entwicklungsserver starten:
   ```bash
   python manage.py runserver
   ```



