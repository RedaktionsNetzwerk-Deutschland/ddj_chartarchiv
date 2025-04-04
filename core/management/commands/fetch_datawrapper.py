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
        """Holt alle Ordner von Datawrapper und erstellt zwei DataFrames:
        1. Ein DataFrame mit allen Ordnern und ihren Beziehungen
        2. Ein DataFrame mit allen Charts und deren Zuordnung zu Ordnern
        """
        try:
            url = "https://api.datawrapper.de/v3/folders"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folders_data = response.json()
            
            # Speichere die Ordnerdaten in eine Datei
            import json
            import os
            import pandas as pd
            from datetime import datetime
            
            # Erstelle Verzeichnis, falls es nicht existiert
            data_dir = os.path.join(settings.BASE_DIR, 'datawrapper_data')
            os.makedirs(data_dir, exist_ok=True)
            
            # Erstelle Dateinamen mit Zeitstempel
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(data_dir, f'datawrapper_folders_{timestamp}.json')
            
            # Speichere die Daten als JSON
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(folders_data.get('list', []), f, indent=4, ensure_ascii=False)
                
            self.stdout.write(f"Ordnerdaten gespeichert in: {filename}")
            
            # Erstelle leere Listen für die DataFrames
            folder_records = []
            chart_records = []
            
            # Rekursive Funktion zum Durchsuchen der Ordnerstruktur
            def process_folder(folder, parent=None, parent_id=None):
                folder_id = folder.get('id')
                folder_name = folder.get('name')
                
                if folder_id and folder_name:
                    # Auf Subfolders prüfen
                    subfolders = []
                    subfolder_ids = []
                    
                    if 'folders' in folder:
                        for subfolder in folder.get('folders', []):
                            if subfolder.get('id') and subfolder.get('name'):
                                subfolders.append(subfolder.get('name'))
                                # Umwandlung in String, um join() zu ermöglichen
                                subfolder_ids.append(str(subfolder.get('id')))
                    
                    # Füge den Ordner zum DataFrame hinzu
                    folder_record = {
                        'folder_id': folder_id,
                        'name': folder_name,
                        'parent': parent,
                        'parent_id': parent_id,
                        'subfolder': ', '.join(subfolders) if subfolders else None,
                        'subfolder_id': ', '.join(subfolder_ids) if subfolder_ids else None
                    }
                    folder_records.append(folder_record)
                    
                    # Verarbeite Charts in diesem Ordner
                    if 'charts' in folder and folder.get('charts'):
                        for chart in folder.get('charts'):
                            if isinstance(chart, dict) and 'id' in chart:
                                chart_record = {
                                    'chart_id': chart.get('id'),
                                    'title': chart.get('title', ''),
                                    'date': chart.get('createdAt'),
                                    'folder_name': folder_name,
                                    'folder_id': folder_id
                                }
                                chart_records.append(chart_record)
                    
                    # Rekursiv durch alle Unterordner gehen
                    if 'folders' in folder:
                        for subfolder in folder.get('folders', []):
                            process_folder(subfolder, folder_name, folder_id)
            
            # Starte mit den Hauptordnern in der Liste
            for item in folders_data.get('list', []):
                # Verarbeite Charts direkt im Root-Ordner (falls vorhanden)
                if 'charts' in item and item.get('charts') and item.get('name'):
                    for chart in item.get('charts'):
                        if isinstance(chart, dict) and 'id' in chart:
                            chart_record = {
                                'chart_id': chart.get('id'),
                                'title': chart.get('title', ''),
                                'date': chart.get('createdAt'),
                                'folder_name': item.get('name'),
                                'folder_id': item.get('id')
                            }
                            chart_records.append(chart_record)
                
                # Ignoriere Einträge vom Typ "user", verarbeite nur "team"
                if item.get('type') == 'team':
                    process_folder(item)
                    
                    # Verarbeite auch die Unterordner im "folders"-Key des Team-Ordners
                    for subfolder in item.get('folders', []):
                        process_folder(subfolder, item.get('name'), item.get('id'))
            
            # Erstelle die DataFrames aus den gesammelten Daten
            folders_df = pd.DataFrame(folder_records)
            charts_df = pd.DataFrame(chart_records)
            
            # doppelte Charts entfernen
            charts_df = charts_df.drop_duplicates(subset=['chart_id'])
            
            # Konvertiere Datumsstrings zu Datetime-Objekten im charts_df
            if not charts_df.empty and 'date' in charts_df.columns:
                charts_df['date'] = pd.to_datetime(charts_df['date'])
            
            # Ausgabe zur Info
            self.stdout.write(f"DataFrame mit {len(folders_df)} Ordnern erstellt")
            self.stdout.write(f"DataFrame mit {len(charts_df)} Charts erstellt")
            
            
                    
            return folders_df, charts_df
        except Exception as e:
            self.stderr.write(f'Fehler beim Abrufen der Ordner: {e}')
            return pd.DataFrame(), pd.DataFrame(), []


    def filter_folders(self, charts, folders, exclude_names=['printexport']):
        """Filtert Charts basierend auf ausgeschlossenen Ordnernamen"""
        try:
            # Finde alle Ordner, deren Name in exclude_names vorkommt
            subfolders = folders[folders["name"].isin(exclude_names)]
            
            # Starte mit einer Liste der auszuschließenden Ordnernamen
            filterfolders_names = list(subfolders["name"].unique())
            
            # Füge auch die Unterordner zur Ausschlussliste hinzu, falls vorhanden
            for subfolder_str in subfolders["subfolder"].dropna():
                # Teile die Komma-separierten Unterordnernamen auf
                subfolders_elements = [s.strip() for s in subfolder_str.split(",")]
                # Füge jeden Unterordnernamen zur Ausschlussliste hinzu
                filterfolders_names.extend(subfolders_elements)
            
            # Entferne Duplikate
            filterfolders_names = list(set(filterfolders_names))
            
            self.stdout.write(f"Folgende Ordner werden ausgeschlossen: {filterfolders_names}")
            
            # Filtere die Charts basierend auf den Ordnernamen
            charts_filtered = charts[~charts['folder_name'].isin(filterfolders_names)]
            
            return charts_filtered
        except Exception as e:
            self.stderr.write(f'Fehler beim Filtern der Ordner: {e}')
            # Im Fehlerfall die ungefilterten Charts zurückgeben
            return charts
        
        

    # def get_all_chart_ids(self, folders, start_date):
   
    #     """
    #     Extrahiert alle Chart-IDs aus den gefilterten Ordnern, die nach start_date erstellt wurden
        
    #     Args:
    #         folders: Liste der gefilterten Ordner
    #         start_date: datetime-Objekt für das Filterdatum
    #     """
    #     chart_ids = set()  # Verwende ein Set um Duplikate zu vermeiden
        
    #     # Füge die speziellen RND-Ordner-Charts hinzu
    #     rnd_folder_id = "NcuSh8hB"  # Case-sensitive ID
    #     try:
    #         response = requests.get(
    #             f"https://api.datawrapper.de/v3/folders/{rnd_folder_id}?expand=true",  # expand=true für vollständige Chart-Details
    #             headers=self.headers
    #         )
    #         if response.status_code == 200:
    #             rnd_folder = response.json()
    #             if 'charts' in rnd_folder:
    #                 for chart in rnd_folder['charts']:
    #                     try:
    #                         # Hole das Erstellungsdatum
    #                         if isinstance(chart, dict):
    #                             created_at = chart.get('createdAt')
    #                             chart_id = chart.get('id')
    #                         else:
    #                             # Wenn chart ein String ist, müssen wir die Details separat abrufen
    #                             chart_id = chart
    #                             chart_response = requests.get(
    #                                 f"https://api.datawrapper.de/v3/charts/{chart_id}",
    #                                 headers=self.headers
    #                             )
    #                             if chart_response.status_code == 200:
    #                                 chart_data = chart_response.json()
    #                                 created_at = chart_data.get('createdAt')
    #                             else:
    #                                 continue

    #                         if created_at:
    #                             # Konvertiere das Datum
    #                             created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    #                             # Füge die ID nur hinzu, wenn das Datum nach start_date liegt
    #                             if created_date > start_date:
    #                                 chart_ids.add(chart_id)
    #                     except Exception as e:
    #                         self.stderr.write(f'Fehler beim Verarbeiten der Chart {chart_id}: {e}')
    #                         continue

    #     except Exception as e:
    #         self.stderr.write(f'Fehler beim Abrufen des RND-Ordners: {e}')

        # # Füge Charts aus allen anderen gefilterten Ordnern hinzu
        # for chart_id in folders["folder_id"].unique():
            
            
            
        #     	try:
                    
        #             # Wenn chart ein String ist, müssen wir die Details separat abrufen
        #             chart_id = chart
        #             chart_response = requests.get(
        #                 f"https://api.datawrapper.de/v3/charts/{chart_id}",
        #                 headers=self.headers
        #             )
        #             if chart_response.status_code == 200:
        #                 chart_data = chart_response.json()
        #                 created_at = chart_data.get('createdAt')
        #             else:
        #                 continue

        #         if created_at:
        #             # Konvertiere das Datum
        #             created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        #             # Füge die ID nur hinzu, wenn das Datum nach start_date liegt
        #             if created_date > start_date:
        #                 chart_ids.add(chart_id)
        #     except Exception as e:
        #         self.stderr.write(f'Fehler beim Verarbeiten der Chart {chart_id}: {e}')
        #         continue

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
        start_date = datetime(2025, 4, 2, tzinfo=timezone.utc)  # Geändert auf 1. Juni 2024

        while True:
            self.stdout.write('Fetching charts from Datawrapper API...')
            
            # Prüfe zuerst auf gelöschte Grafiken
            # TODO: Später wieder einfügen
            #deleted_count = self.check_deleted_charts(self.headers)
            #self.stdout.write(f'Gelöschte Grafiken entfernt: {deleted_count}')
            
            # Hole alle Ordner
            all_folders, all_charts = self.get_all_folders(self.headers)
           
            self.stdout.write(f'Gefundene Ordner: {len(all_folders)}')
            
           
            # Filtere Grafiken heraus, die in unerwünschten Ordnern sind
            exclude_names = ['printexport']
            filtered_charts = self.filter_folders(all_charts, all_folders, exclude_names=exclude_names)
            self.stdout.write(f'Gefilterte Charts: {len(filtered_charts)}')
            
            # Hole existierende Chart-IDs aus der Datenbank
            existing_chart_ids = set(Chart.objects.values_list('chart_id', flat=True))
            all_chart_ids = filtered_charts["chart_id"].unique()
           
            # Filtere die bereits existierenden Charts aus
            new_chart_ids = [chart_id for chart_id in all_chart_ids if chart_id not in existing_chart_ids]
            self.stdout.write(f'Neue Chart-IDs zum Verarbeiten: {len(new_chart_ids)}')
            # für debug
            new_chart_ids = ["k5iKB"]
            # Verarbeite nur die neuen Charts
            for chart_id in new_chart_ids:
                try:
                    # Vollständige Metadaten abrufen
                    chart_details_url = f"https://api.datawrapper.de/v3/charts/{chart_id}?expand=true"
                    
                    try:
                        details_response = requests.get(chart_details_url, headers=self.headers)
                        details_response.raise_for_status()
                        chart_details = details_response.json()
                        print(chart_details)
                        
                        # Prüfe, ob die Grafik veröffentlicht wurde
                        if chart_details.get('publishedAt') is None:
                            self.stdout.write(f"Chart {chart_id} ist nicht veröffentlicht, überspringe...")
                            continue
                        title = chart_details.get('title', '')
                        description = chart_details.get('metadata', {}).get('describe', {}).get('intro', '')
                        notes = chart_details.get('metadata', {}).get('describe', {}).get('notes', '')
                        published_at_str = chart_details.get('publishedAt')
                        lastModified_at_str = chart_details.get('lastModifiedAt')
                        # Stelle sicher, dass iframe_url einen Wert hat
                        iframe_url = chart_details.get('publicUrl', '')  # Leerer String als Default
                        # Stelle sicher, dass embed_js einen Wert hat
                        embed_js = chart_details.get('metadata', {}).get('publish', {}).get('embed', '')
                        # Hole alle Custom Fields
                        custom_fields = self.get_custom_fields(chart_details)
                        
                        # Formatiere die Custom Fields für die Speicherung
                        comments = custom_fields["kommentar"]
                        tags = custom_fields["tags"]
                        patch = custom_fields["patch"]
                        evergreen = custom_fields["evergreen"]
                        
                        
                        
                        
                        
                        published_date = None
                        last_modified_date = None
                        if published_at_str:
                            try:
                                published_date = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                            except Exception:
                                pass
                        if lastModified_at_str:
                            try:
                                last_modified_date = datetime.fromisoformat(lastModified_at_str.replace('Z', '+00:00'))
                            except Exception:
                                pass

                        # Chart in der Datenbank speichern
                        chart_obj = Chart.objects.create(
                            published_date=published_date,
                            chart_id=chart_id,
                            title=title,
                            description=description,
                            notes=notes,
                            comments=comments,
                            tags=tags,
                            patch=patch,
                            evergreen=evergreen,
                            last_modified_date=last_modified_date,
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