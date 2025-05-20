"""
Management Command zum Aktualisieren der neuen Felder in bestehenden Chart-Einträgen.

Dieses Command ruft für alle vorhandenen Chart-Einträge die Datawrapper-API auf
und aktualisiert die neuen bzw. geänderten Felder, die in den letzten Änderungen
hinzugefügt wurden.
"""

import time
import requests
import os
import pandas as pd
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Chart
import logging

# Logger konfigurieren
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Aktualisiert bestehende Chart-Einträge mit den neuen Feldern aus der Datawrapper-API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Anzahl der Charts, die pro Batch verarbeitet werden sollen'
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.5,
            help='Wartezeit zwischen API-Aufrufen in Sekunden'
        )
        parser.add_argument(
            '--chart-id',
            type=str,
            help='Einzelne Chart-ID aktualisieren (optional)'
        )
        parser.add_argument(
            '--skip-folders',
            action='store_true',
            help='Ordnerinformationen nicht aktualisieren (schnellere Ausführung)'
        )

    def get_all_folders(self, headers):
        """
        Holt alle Ordner von Datawrapper und erstellt ein chart_to_folders-Mapping.
        
        Args:
            headers (dict): API-Request-Header mit Authorization
            
        Returns:
            dict: Mapping von Chart-IDs zu Listen von Ordnernamen
        """
        self.stdout.write("Hole Ordnerinformationen von Datawrapper...")
        
        try:
            # API-Anfrage für alle Ordner
            url = "https://api.datawrapper.de/v3/folders"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folders_data = response.json()
            
            # Mapping von Chart-IDs zu Liste von Ordnernamen
            chart_to_folders = {}
            
            # Rekursive Funktion zum Durchsuchen der Ordnerstruktur
            def process_folder(folder, parent_path=None):
                """
                Verarbeitet rekursiv einen Ordner, seine Unterordner und Charts.
                
                Args:
                    folder (dict): Ordnerdaten aus der API
                    parent_path (str, optional): Pfad des übergeordneten Ordners
                """
                folder_id = folder.get('id')
                folder_name = folder.get('name')
                
                if not folder_id or not folder_name:
                    return
                
                # Aktuellen Ordnerpfad erstellen
                current_path = folder_name
                if parent_path:
                    current_path = f"{parent_path}, {folder_name}"
                
                # Charts in diesem Ordner verarbeiten
                if 'charts' in folder and folder.get('charts'):
                    for chart in folder.get('charts'):
                        if isinstance(chart, dict) and 'id' in chart:
                            chart_id = chart.get('id')
                            if chart_id:
                                # Chart dem Ordnerpfad zuordnen
                                if chart_id not in chart_to_folders:
                                    chart_to_folders[chart_id] = []
                                chart_to_folders[chart_id].append(current_path)
                
                # Rekursiv alle Unterordner durchgehen
                if 'folders' in folder:
                    for subfolder in folder.get('folders', []):
                        process_folder(subfolder, current_path)
            
            # Alle Hauptordner verarbeiten
            for item in folders_data.get('list', []):
                # Nur Team-Ordner verarbeiten, User-Ordner ignorieren
                if item.get('type') == 'team':
                    process_folder(item)
                    
                    # Unterordner des Team-Ordners verarbeiten
                    for subfolder in item.get('folders', []):
                        process_folder(subfolder, item.get('name'))
            
            # Debug-Ausgabe
            self.stdout.write(f"  {len(chart_to_folders)} Charts in Ordnern gefunden")
            return chart_to_folders
            
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f'API-Fehler beim Abrufen der Ordner: {e}'))
            return {}
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Allgemeiner Fehler beim Abrufen der Ordner: {e}'))
            return {}

    def handle(self, *args, **options):
        # API-Key aus Umgebungsvariablen laden
        api_key = os.getenv('DATAWRAPPER_API_KEY')
            
        if not api_key:
            self.stderr.write(self.style.ERROR('Kein Datawrapper API-Key gefunden in Umgebungsvariablen.'))
            return
            
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # Ermittle die zu aktualisierenden Charts
        if options['chart_id']:
            charts = Chart.objects.filter(chart_id=options['chart_id'])
            self.stdout.write(f"Aktualisiere Chart mit ID {options['chart_id']}")
        else:
            charts = Chart.objects.all()
            self.stdout.write(f"Aktualisiere {charts.count()} Charts")
        
        # Hole Ordnerinformationen, wenn nicht übersprungen
        chart_to_folders = {}
        if not options['skip_folders']:
            chart_to_folders = self.get_all_folders(headers)

        # Aktualisiere die Charts in Batches
        batch_size = options['batch_size']
        sleep_time = options['sleep']
        
        updated_count = 0
        error_count = 0
        
        # Verarbeite die Charts in Batches
        for i in range(0, charts.count(), batch_size):
            batch = charts[i:i+batch_size]
            self.stdout.write(f"Verarbeite Batch {i//batch_size + 1} ({len(batch)} Charts)")
            
            for chart in batch:
                try:
                    # API-Anfrage für die Chart-Details
                    url = f"https://api.datawrapper.de/v3/charts/{chart.chart_id}?expand=true"
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()
                    chart_details = response.json()
                    
                    # Extrahiere die benötigten Felder
                    # 1. Preview URL (publicURL)
                    preview_url = chart_details.get('publicUrl', '')
                    
                    # 2. Notes aus annotate statt describe
                    notes = chart_details.get('metadata', {}).get('annotate', {}).get('notes', '')
                    
                    # 3. Autor und E-Mail
                    author = chart_details.get('author', {}).get('name', '')
                    author_email = chart_details.get('author', {}).get('email', '')
                    
                    # Stelle sicher, dass author und author_email nicht None sind (da die Felder NOT NULL sind)
                    author = author or ''
                    author_email = author_email or ''
                    
                    # Debug-Ausgabe
                    self.stdout.write(f"  Chart {chart.chart_id}: author='{author}', email='{author_email}'")
                    
                    # 4. Thumbnail URLs
                    thumbnails = chart_details.get('thumbnails', {})
                    pic_url_full = thumbnails.get('full', '')
                    pic_url_small = thumbnails.get('plain', '')
                    
                    # 5. Archive-Flag aus custom fields
                    custom_fields = chart_details.get('metadata', {}).get('custom', {})
                    archive = custom_fields.get('archiv', False)
                    archive = True if str(archive).lower() == 'true' else False
                    
                    # 6. Responsive iframe URL aus embed-method-responsive
                    embed_codes = chart_details.get('metadata', {}).get('publish', {}).get('embed-codes', {})
                    iframe_url = embed_codes.get('embed-method-responsive', '')
                    
                    # Fallbacks für iframe_url, falls embed-method-responsive nicht gefunden wird
                    if not iframe_url:
                        # Versuche zuerst den alten responsive-Key
                        iframe_url = embed_codes.get('responsive', '')
                        
                        # Dann den alten API-Pfad
                        if not iframe_url:
                            iframe_url = chart_details.get('metadata', {}).get('publish', {}).get('embed-responsive', '')
                            
                            # Schließlich die publicUrl als letzten Fallback
                            if not iframe_url:
                                iframe_url = chart_details.get('publicUrl', '')
                    
                    # Stelle sicher, dass iframe_url nicht zu lang ist (max 990 Zeichen)
                    if len(iframe_url) > 990:
                        self.stdout.write(f"  Warnung: iframe_url für Chart {chart.chart_id} wurde gekürzt (Originallänge: {len(iframe_url)})")
                        iframe_url = iframe_url[:990]
                    
                    # 7. Ordnerinformationen
                    folder_paths = chart_to_folders.get(chart.chart_id, [])
                    folder_string = ', '.join(folder_paths)
                    
                    # Wenn URLs mit // beginnen, füge https: hinzu
                    if pic_url_full and pic_url_full.startswith('//'):
                        pic_url_full = f"https:{pic_url_full}"
                    if pic_url_small and pic_url_small.startswith('//'):
                        pic_url_small = f"https:{pic_url_small}"
                    
                    # Aktualisiere das Chart-Objekt
                    chart.preview_url = preview_url
                    chart.notes = notes
                    chart.author = author
                    chart.author_email = author_email
                    chart.pic_url_full = pic_url_full
                    chart.pic_url_small = pic_url_small
                    chart.archive = archive
                    chart.iframe_url = iframe_url
                    
                    # Nur Ordnerinformationen aktualisieren, wenn Ordner abgefragt wurden
                    if not options['skip_folders']:
                        chart.folder = folder_string
                        
                    chart.save()
                    
                    updated_count += 1
                    if updated_count % 10 == 0:
                        self.stdout.write(f"  {updated_count} Charts aktualisiert")
                    
                    # Kurze Pause einlegen, um Rate-Limits zu vermeiden
                    time.sleep(sleep_time)
                    
                except requests.exceptions.RequestException as e:
                    error_count += 1
                    err_msg = f"API-Fehler bei Chart {chart.chart_id}: {str(e)}"
                    self.stderr.write(self.style.ERROR(err_msg))
                    logger.error(err_msg)
                    
                    # Bei HTTP-Fehler 429 (Too Many Requests) längere Pause einlegen
                    if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                        wait_time = 30
                        self.stdout.write(f"Rate-Limit erreicht. Warte {wait_time} Sekunden...")
                        time.sleep(wait_time)
                        
                except Exception as e:
                    error_count += 1
                    err_msg = f"Fehler bei Chart {chart.chart_id}: {str(e)}"
                    self.stderr.write(self.style.ERROR(err_msg))
                    logger.error(err_msg)
        
        # Ausgabe der Zusammenfassung
        self.stdout.write(self.style.SUCCESS(f'Aktualisierung abgeschlossen.'))
        self.stdout.write(f'Erfolgreich aktualisierte Charts: {updated_count}')
        self.stdout.write(f'Fehler: {error_count}') 