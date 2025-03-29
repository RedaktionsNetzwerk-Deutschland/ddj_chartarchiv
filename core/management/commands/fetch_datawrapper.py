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
        start_time = time.time()
        self.stdout.write("Prüfe auf gelöschte Grafiken...")
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
        end_time = time.time()
        self.stdout.write(f"Gelöschte Grafiken geprüft in {end_time - start_time:.2f} Sekunden")
        return deleted_count

    def get_all_folders(self, headers):
        """Holt alle Ordner von Datawrapper und erstellt ein DataFrame"""
        try:
            url = "https://api.datawrapper.de/v3/folders"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folders_data = response.json()
            
            all_folders = []
            
            def process_folder(folder):
                folder_info = {
                    'id': folder.get('id'),
                    'name': folder.get('name'),
                    'charts': folder.get('charts', []),
                    'children': folder.get('children', [])
                }
                # Nur Ordner mit gültiger ID und Namen hinzufügen
                if folder_info['id'] and folder_info['name']:
                    all_folders.append(folder_info)
                
                # Rekursiv durch Unterordner gehen
                for child in folder.get('children', []):
                    process_folder(child)
            
            # Verarbeite jeden Root-Ordner
            for folder in folders_data.get('list', []):
                process_folder(folder)
                
            return all_folders
        except Exception as e:
            self.stderr.write(f'Fehler beim Abrufen der Ordner: {e}')
            return []

    def filter_folders(self, folders, exclude_names=['printexport']):
        """Filtert Ordner basierend auf ausgeschlossenen Namen"""
        filtered_folders = []
        exclude_names_lower = [name.lower() for name in exclude_names]
        
        for folder in folders:
            folder_name = folder.get('name')
            if folder_name is None:
                continue
            
            if folder_name.lower() not in exclude_names_lower:
                filtered_folders.append(folder)
            
        return filtered_folders

    def get_all_chart_ids(self, folders, start_date):
        """
        Extrahiert alle Chart-IDs aus den gefilterten Ordnern, die nach start_date erstellt wurden
        
        Args:
            folders: Liste der gefilterten Ordner
            start_date: datetime-Objekt für das Filterdatum
        """
        chart_ids = set()  # Verwende ein Set um Duplikate zu vermeiden
        
        # Füge die speziellen RND-Ordner-Charts hinzu
        rnd_folder_id = "NcuSh8hB"  # Case-sensitive ID
        try:
            response = requests.get(
                f"https://api.datawrapper.de/v3/folders/{rnd_folder_id}?expand=true",  # expand=true für vollständige Chart-Details
                headers=self.headers
            )
            if response.status_code == 200:
                rnd_folder = response.json()
                if 'charts' in rnd_folder:
                    for chart in rnd_folder['charts']:
                        try:
                            # Hole das Erstellungsdatum
                            if isinstance(chart, dict):
                                created_at = chart.get('createdAt')
                                chart_id = chart.get('id')
                            else:
                                # Wenn chart ein String ist, müssen wir die Details separat abrufen
                                chart_id = chart
                                chart_response = requests.get(
                                    f"https://api.datawrapper.de/v3/charts/{chart_id}",
                                    headers=self.headers
                                )
                                if chart_response.status_code == 200:
                                    chart_data = chart_response.json()
                                    created_at = chart_data.get('createdAt')
                                else:
                                    continue

                            if created_at:
                                # Konvertiere das Datum
                                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                # Füge die ID nur hinzu, wenn das Datum nach start_date liegt
                                if created_date > start_date:
                                    chart_ids.add(chart_id)
                        except Exception as e:
                            self.stderr.write(f'Fehler beim Verarbeiten der Chart {chart_id}: {e}')
                            continue

        except Exception as e:
            self.stderr.write(f'Fehler beim Abrufen des RND-Ordners: {e}')

        # Füge Charts aus allen anderen gefilterten Ordnern hinzu
        for folder in folders:
            if 'charts' in folder:
                for chart in folder['charts']:
                    try:
                        # Hole das Erstellungsdatum
                        if isinstance(chart, dict):
                            created_at = chart.get('createdAt')
                            chart_id = chart.get('id')
                        else:
                            # Wenn chart ein String ist, müssen wir die Details separat abrufen
                            chart_id = chart
                            chart_response = requests.get(
                                f"https://api.datawrapper.de/v3/charts/{chart_id}",
                                headers=self.headers
                            )
                            if chart_response.status_code == 200:
                                chart_data = chart_response.json()
                                created_at = chart_data.get('createdAt')
                            else:
                                continue

                        if created_at:
                            # Konvertiere das Datum
                            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            # Füge die ID nur hinzu, wenn das Datum nach start_date liegt
                            if created_date > start_date:
                                chart_ids.add(chart_id)
                    except Exception as e:
                        self.stderr.write(f'Fehler beim Verarbeiten der Chart {chart_id}: {e}')
                        continue
        
        return list(chart_ids)

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
        # API-Key aus der .env Datei laden
        api_key = os.getenv('DATAWRAPPER_API_KEY', 'XXXXXXXX')
        self.headers = {"Authorization": f"Bearer {api_key}"}
        
        # Setze das Startdatum für die Filterung als offset-aware Datum (UTC)
        start_date = datetime(2024, 6, 1, tzinfo=timezone.utc)  # Geändert auf 1. Juni 2024

        while True:
            self.stdout.write('Fetching charts from Datawrapper API...')
            
            # Prüfe zuerst auf gelöschte Grafiken
            # TODO: Später wieder einfügen
            #deleted_count = self.check_deleted_charts(self.headers)
            #self.stdout.write(f'Gelöschte Grafiken entfernt: {deleted_count}')
            
            # Hole alle Ordner
            all_folders = self.get_all_folders(self.headers)
            self.stdout.write(f'Gefundene Ordner: {len(all_folders)}')
           
            # Filtere unerwünschte Ordner
            filtered_folders = self.filter_folders(all_folders, exclude_names=['printexport'])
            self.stdout.write(f'Gefilterte Ordner: {len(filtered_folders)}')
            

            # Hole alle Chart-IDs mit Datumsfilter
            all_chart_ids = self.get_all_chart_ids(filtered_folders, start_date)
            self.stdout.write(f'Gefundene Chart-IDs nach {start_date}: {len(all_chart_ids)}')
            
            
            # Hole existierende Chart-IDs aus der Datenbank
            existing_chart_ids = set(Chart.objects.values_list('chart_id', flat=True))
            
            # Filtere die bereits existierenden Charts aus
            new_chart_ids = [chart_id for chart_id in all_chart_ids if chart_id not in existing_chart_ids]
            self.stdout.write(f'Neue Chart-IDs zum Verarbeiten: {len(new_chart_ids)}')
           
            # Verarbeite nur die neuen Charts
            for chart_id in new_chart_ids:
                try:
                    # Vollständige Metadaten abrufen
                    chart_details_url = f"https://api.datawrapper.de/v3/charts/{chart_id}?expand=true"
                    
                    try:
                        details_response = requests.get(chart_details_url, headers=self.headers)
                        details_response.raise_for_status()
                        chart_details = details_response.json()
                        
                        
                        # Prüfe, ob die Grafik zum printexport Ordner gehört
                        folder_id = chart_details.get('folderId')
                        if folder_id:
                            folder_response = requests.get(
                                f"https://api.datawrapper.de/v3/folders/{folder_id}",
                                headers=self.headers
                            )
                            if folder_response.status_code == 200:
                                folder_data = folder_response.json()
                                if folder_data.get('name', '').lower() == 'printexport':
                                    self.stdout.write(f"Chart {chart_id} ist im printexport Ordner, überspringe...")
                                    continue
                        # Prüfe, ob die Grafik veröffentlicht wurde
                        if chart_details.get('publishedAt') is None:
                            self.stdout.write(f"Chart {chart_id} ist nicht veröffentlicht, überspringe...")
                            continue
                        title = chart_details.get('title', '')
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
                        iframe_url = chart_details.get('publicUrl', '')  # Leerer String als Default
                        
                        # Stelle sicher, dass embed_js einen Wert hat
                        embed_js = chart_details.get('metadata', {}).get('publish', {}).get('embed', '')
                        
                        published_date = None
                        if published_at_str:
                            try:
                                published_date = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                            except Exception:
                                pass

                        # Chart in der Datenbank speichern
                        chart_obj = Chart.objects.create(
                            published_date=published_date,
                            chart_id=chart_id,
                            title=title,
                            description=description,
                            notes=notes,
                            comments=comments_text,
                            iframe_url=iframe_url or '',  # Stellt sicher, dass mindestens ein leerer String gesetzt wird
                            embed_js=embed_js,
                            evergreen=False  # Setze einen Default-Wert für evergreen
                        )

                        # Thumbnail erstellen nur wenn eine URL vorhanden ist
                        if iframe_url:
                            thumbnail_filename = f"thumbnail_{chart_id}.png"
                            thumbnail_dir = os.path.join(settings.MEDIA_ROOT, 'thumbnails')
                            os.makedirs(thumbnail_dir, exist_ok=True)
                            thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
                            
                            try:
                                export_url = f"https://api.datawrapper.de/v3/charts/{chart_id}/export/png"
                                export_response = requests.get(export_url, headers=self.headers)
                                export_response.raise_for_status()
                                self.generate_thumbnail(export_response.content, thumbnail_path)
                                chart_obj.thumbnail.name = os.path.join('thumbnails', thumbnail_filename)
                            except Exception as e:
                                self.stderr.write(f'Warnung: Thumbnail konnte nicht erstellt werden für {chart_id}: {e}')

                        chart_obj.save()
                        self.stdout.write(f"Saved new chart: {title} (ID: {chart_id})")
                        
                    except Exception as e:
                        self.stderr.write(f'Warnung: Probleme beim Abrufen der Chart-Details für {chart_id}: {e}')
                        continue
                        
                except Exception as e:
                    self.stderr.write(f'Fehler bei der Verarbeitung von Chart {chart_id}: {e}')
                    continue

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