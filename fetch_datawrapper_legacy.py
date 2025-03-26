import time
import requests
import os
from datetime import datetime, timezone
from io import BytesIO

from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Chart

from dotenv import load_dotenv
from PIL import Image

# Laden der Umgebungsvariablen aus .env
load_dotenv()


class Command(BaseCommand):
    help = 'Fragt alle 2 Minuten die Datawrapper-API ab und speichert neue Grafiken ab dem 01.04.2024 in der Datenbank.'

    def check_deleted_charts(self, headers):
        """Prüft und löscht Grafiken, die in Datawrapper nicht mehr existieren"""
        deleted_count = 0
        for chart in Chart.objects.all():
            try:
                response = requests.get(
                    f"https://api.datawrapper.de/v3/charts/{chart.chart_id}",
                    headers=headers
                )
                if response.status_code == 404:
                    # Lösche das Thumbnail, falls es existiert
                    if chart.thumbnail:
                        thumbnail_path = os.path.join(settings.MEDIA_ROOT, chart.thumbnail.name)
                        if os.path.exists(thumbnail_path):
                            os.remove(thumbnail_path)
                    
                    # Lösche den Datenbank-Eintrag
                    chart.delete()
                    deleted_count += 1
                    self.stdout.write(f"Gelöschte Grafik entfernt: {chart.chart_id}")
                    
            except Exception as e:
                self.stderr.write(f'Fehler beim Prüfen von Chart {chart.chart_id}: {e}')
                
        return deleted_count

    def get_all_folders(self, headers):
        """Holt alle Ordner von Datawrapper"""
        folders = []
        next_link = "https://api.datawrapper.de/v3/folders"
        
        while next_link:
            try:
                response = requests.get(next_link, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                # Debug-Ausgabe
                self.stdout.write(f"Ordner-API Antwort: {data}")
                
                # Füge die Ordner dieser Seite hinzu
                current_folders = data.get('list', [])
                folders.extend(current_folders)
                self.stdout.write(f"Gefundene Ordner in diesem Durchgang: {len(current_folders)}")
                
                # Prüfe, ob es eine nächste Seite gibt
                next_link = data.get('next', None)
            except Exception as e:
                self.stderr.write(f'Fehler beim Abrufen der Ordner: {e}')
                break
        
        return folders

    def get_charts_from_folder(self, folder_id, headers):
        """Holt alle Grafiken aus einem bestimmten Ordner"""
        charts = []
        next_link = f"https://api.datawrapper.de/v3/folders/{folder_id}/charts"
        
        while next_link:
            try:
                response = requests.get(next_link, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                # Debug-Ausgabe
                self.stdout.write(f"Charts im Ordner {folder_id} - API Antwort: {data}")
                
                # Füge die Grafiken dieser Seite hinzu
                current_charts = data.get('list', [])
                charts.extend(current_charts)
                self.stdout.write(f"Gefundene Grafiken in diesem Ordner und Durchgang: {len(current_charts)}")
                
                # Prüfe, ob es eine nächste Seite gibt
                next_link = data.get('next', None)
            except Exception as e:
                self.stderr.write(f'Fehler beim Abrufen der Grafiken aus Ordner {folder_id}: {e}')
                break
        
        return charts

    def filter_charts_by_date(self, charts, start_date):
        """Filtert Charts nach dem Erstellungsdatum"""
        filtered_charts = []
        for chart in charts:
            created_at = chart.get('createdAt')
            if created_at:
                try:
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if created_date >= start_date:
                        filtered_charts.append(chart)
                except Exception as e:
                    self.stderr.write(f'Fehler beim Parsen des Erstellungsdatums für Chart {chart.get("id")}: {e}')
        return filtered_charts

    def get_custom_fields(self, chart_details):
        """Extrahiert alle Custom Fields aus den Chart-Details"""
        custom_fields = {}
        
        # Hole die Metadaten
        metadata = chart_details.get('metadata', {})
        
        # Prüfe verschiedene Orte für Custom Fields
        # 1. Direkte Custom Fields
        custom = metadata.get('custom', {})
        if custom:
            custom_fields.update(custom)
            
        # 2. Beschreibende Metadaten
        describe = metadata.get('describe', {})
        if describe:
            for key, value in describe.items():
                if value and key not in ['intro', 'notes', 'byline']:  # Ignoriere Standardfelder
                    custom_fields[f"describe_{key}"] = value
                    
        # 3. Visualisierungseinstellungen
        visualize = metadata.get('visualize', {})
        if visualize:
            for key, value in visualize.items():
                if value and isinstance(value, (str, int, float, bool)):
                    custom_fields[f"visualize_{key}"] = value
        
        # Konvertiere alle Werte zu Strings für die Speicherung
        return {k: str(v) for k, v in custom_fields.items() if v is not None}

    def handle(self, *args, **kwargs):
        api_key = os.getenv('DATAWRAPPER_API_KEY', 'XXXXXXXX')
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # Setze das Startdatum für die Filterung als offset-aware Datum (UTC)
        start_date = datetime(2024, 4, 1, tzinfo=timezone.utc)

        while True:
            self.stdout.write('Fetching charts from Datawrapper API...')
            
            # Prüfe zuerst auf gelöschte Grafiken
            deleted_count = self.check_deleted_charts(headers)
            self.stdout.write(f'Gelöschte Grafiken entfernt: {deleted_count}')
            
            # Hole zuerst alle Ordner
            folders = self.get_all_folders(headers)
            self.stdout.write(f'Gefundene Ordner: {len(folders)}')
            
            # Sammle alle Grafiken aus allen Ordnern
            all_charts = []
            for folder in folders:
                folder_id = folder.get('id')
                folder_name = folder.get('name', '')  # Setze leeren String als Default
                
                # Überspringe den printexport Ordner
                if folder_name and folder_name.lower() == 'printexport':
                    self.stdout.write(f'Überspringe printexport Ordner (ID: {folder_id})')
                    continue
                    
                self.stdout.write(f'Verarbeite Ordner: {folder_name} (ID: {folder_id})')
                folder_charts = self.get_charts_from_folder(folder_id, headers)
                all_charts.extend(folder_charts)
            
            # Hole auch die Grafiken ohne Ordner
            root_charts_url = "https://api.datawrapper.de/v3/charts?expand=true&limit=100"
            try:
                response = requests.get(root_charts_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                root_charts = data.get('list', [])
                self.stdout.write(f'Gefundene Root-Grafiken: {len(root_charts)}')
                all_charts.extend(root_charts)
            except Exception as e:
                self.stderr.write(f'Fehler beim Abrufen der Root-Grafiken: {e}')

            self.stdout.write(f'Insgesamt gefundene Grafiken: {len(all_charts)}')

            # Filtere Charts nach dem Erstellungsdatum
            filtered_charts = self.filter_charts_by_date(all_charts, start_date)
            self.stdout.write(f'Gefilterte Grafiken nach dem 1.4.2024: {len(filtered_charts)}')

            # Verarbeite nur die gefilterten Grafiken
            for chart in filtered_charts:
                chart_id = chart.get('id')
                if not chart_id:
                    continue

                if not Chart.objects.filter(chart_id=chart_id).exists():
                    # Vollständige Metadaten abrufen
                    chart_details_url = f"https://api.datawrapper.de/v3/charts/{chart_id}?expand=true"
                    try:
                        details_response = requests.get(chart_details_url, headers=headers)
                        details_response.raise_for_status()
                        chart_details = details_response.json()

                        # Prüfe, ob die Grafik zum printexport Ordner gehört
                        folder_id = chart_details.get('folderId')
                        if folder_id:
                            folder_response = requests.get(
                                f"https://api.datawrapper.de/v3/folders/{folder_id}",
                                headers=headers
                            )
                            if folder_response.status_code == 200:
                                folder_data = folder_response.json()
                                if folder_data.get('name', '').lower() == 'printexport':
                                    self.stdout.write(f"Chart {chart_id} ist im printexport Ordner, überspringe...")
                                    continue

                        title = chart_details.get('title', 'No title')
                        description = chart_details.get('metadata', {}).get('describe', {}).get('intro', '')
                        notes = chart_details.get('metadata', {}).get('describe', {}).get('notes', '')
                        
                        # Hole alle Custom Fields
                        custom_fields = self.get_custom_fields(chart_details)
                        
                        # Formatiere die Custom Fields für die Speicherung
                        comments = []
                        for field_key, field_value in custom_fields.items():
                            comments.append(f"{field_key}: {field_value}")
                        
                        # Verbinde alle Kommentare mit Zeilenumbrüchen
                        comments_text = "\n".join(comments)
                        
                        published_at_str = chart_details.get('publishedAt')
                        
                        # Stelle sicher, dass iframe_url einen Wert hat
                        iframe_url = chart_details.get('publicUrl')
                        if not iframe_url:
                            self.stderr.write(f'Keine iframe_url für Chart {chart_id} gefunden, überspringe...')
                            continue
                            
                        # Stelle sicher, dass embed_js einen Wert hat
                        embed_js = chart_details.get('metadata', {}).get('publish', {}).get('embed', '')
                        if not embed_js:
                            embed_js = ''  # Setze einen leeren String als Fallback
                        
                        published_date = None
                        if published_at_str:
                            try:
                                published_date = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                            except Exception:
                                pass

                        # Debug-Ausgabe der Custom Fields
                        self.stdout.write(f"\nGefundene Custom Fields für Chart {chart_id}:")
                        for field_key, field_value in custom_fields.items():
                            self.stdout.write(f"  {field_key}: {field_value}")

                        # Thumbnail erstellen
                        thumbnail_filename = f"thumbnail_{chart_id}.png"
                        thumbnail_dir = os.path.join(settings.MEDIA_ROOT, 'thumbnails')
                        os.makedirs(thumbnail_dir, exist_ok=True)
                        thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
                        
                        # Exportiere die Grafik als PNG und erstelle ein Thumbnail
                        export_url = f"https://api.datawrapper.de/v3/charts/{chart_id}/export/png"
                        try:
                            export_response = requests.get(export_url, headers=headers)
                            export_response.raise_for_status()
                            self.generate_thumbnail(export_response.content, thumbnail_path)
                            self.stdout.write(f"Thumbnail für Chart {chart_id} erstellt")
                        except Exception as e:
                            self.stderr.write(f'Fehler beim Erstellen des Thumbnails für {chart_id}: {e}')
                            continue

                        # Chart in der Datenbank speichern
                        chart_obj = Chart.objects.create(
                            published_date=published_date,
                            chart_id=chart_id,
                            title=title,
                            description=description,
                            notes=notes,
                            comments=comments_text,  # Füge die gesammelten Kommentare hinzu
                            iframe_url=iframe_url,
                            embed_js=embed_js
                        )
                        chart_obj.thumbnail.name = os.path.join('thumbnails', thumbnail_filename)
                        chart_obj.save()
                        self.stdout.write(f"Saved new chart: {title} (ID: {chart_id})")
                    except Exception as e:
                        self.stderr.write(f'Error fetching chart details for {chart_id}: {e}')
                        continue
                else:
                    self.stdout.write(f"Chart {chart_id} exists already. Skipping.")

            self.stdout.write('Sleeping for 120 seconds...')
            time.sleep(120)

    def generate_thumbnail(self, image_data, path):
        """
        Erstellt ein Thumbnail aus den exportierten Datawrapper-Daten
        """
        try:
            # Öffne das Bild aus den Binärdaten
            image = Image.open(BytesIO(image_data))
            
            # Berechne die neue Größe unter Beibehaltung des Seitenverhältnisses
            target_width = 800  # Erhöht von 200 auf 800px
            width_percent = (target_width / float(image.size[0]))
            target_height = int((float(image.size[1]) * float(width_percent)))
            
            # Resize das Bild mit hoher Qualität
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Speichere das Thumbnail mit hoher Qualität
            image.save(path, optimize=True, quality=90)  # Qualität auf 90 erhöht
            
        except Exception as e:
            raise Exception(f"Fehler beim Erstellen des Thumbnails: {e}") 