"""
Management Command zum Aktualisieren der neuen Felder in bestehenden Chart-Einträgen.

Dieses Command ruft für alle vorhandenen Chart-Einträge die Datawrapper-API auf
und aktualisiert die neuen bzw. geänderten Felder, die in den letzten Änderungen
hinzugefügt wurden.
"""

import time
import requests
import os
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