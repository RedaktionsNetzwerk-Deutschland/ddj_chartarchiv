"""
Datawrapper API Abfrage und Datenbanksynchronisierung.

Dieses Skript fragt regelmäßig die Datawrapper-API ab, um neue und gelöschte 
Grafiken zu identifizieren und diese in der lokalen Datenbank zu synchronisieren.
"""

import time
import requests
import os
import json
import pandas as pd
import logging
from datetime import datetime, timezone
from io import BytesIO

from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Chart

from dotenv import load_dotenv
from PIL import Image

# Umgebungsvariablen aus .env laden
load_dotenv()

# Logger konfigurieren
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django-Management-Command zur Synchronisierung von Datawrapper-Grafiken mit der Datenbank."""
    
    help = 'Fragt die Datawrapper-API regelmäßig ab und speichert neue Grafiken ab dem 01.04.2024 in der Datenbank.'

    def check_deleted_charts(self, headers):
        """
        Prüft und löscht Grafiken, die in Datawrapper nicht mehr existieren.
        
        Args:
            headers (dict): API-Request-Header mit Authorization
            
        Returns:
            int: Anzahl der gelöschten Grafiken
        """
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
                    logger.info(f"Gelöschte Grafik entfernt: {chart.chart_id}")
                    
            except Exception as e:
                logger.error(f'Fehler beim Prüfen von Chart {chart.chart_id}: {e}')
                
        logger.info(f"Gelöschte Grafiken geprüft in {time.time() - start_time:.2f} Sekunden")
        return deleted_count

    def get_all_folders(self, headers):
        """
        Holt alle Ordner von Datawrapper und erstellt zwei DataFrames:
        1. Ein DataFrame mit allen Ordnern und ihren Beziehungen
        2. Ein DataFrame mit allen Charts und deren Zuordnung zu Ordnern
        
        Args:
            headers (dict): API-Request-Header mit Authorization
            
        Returns:
            tuple: (folders_df, charts_df) - DataFrames mit Ordnern und Charts
        """
        try:
            # API-Anfrage für alle Ordner
            url = "https://api.datawrapper.de/v3/folders"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            folders_data = response.json()
            
            # # Speichere Ordnerdaten zur Nachverfolgung in Datei
            # data_dir = os.path.join(settings.BASE_DIR, 'datawrapper_data')
            # os.makedirs(data_dir, exist_ok=True)
            # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # filename = os.path.join(data_dir, f'datawrapper_folders_{timestamp}.json')
            # 
            # with open(filename, 'w', encoding='utf-8') as f:
            #     json.dump(folders_data.get('list', []), f, indent=4, ensure_ascii=False)
                
            # Listen für die DataFrames vorbereiten
            folder_records = []
            chart_records = []
            
            # Rekursive Funktion zum Durchsuchen der Ordnerstruktur
            def process_folder(folder, parent=None, parent_id=None):
                """
                Verarbeitet rekursiv einen Ordner, seine Unterordner und Charts.
                
                Args:
                    folder (dict): Ordnerdaten aus der API
                    parent (str, optional): Name des übergeordneten Ordners
                    parent_id (str, optional): ID des übergeordneten Ordners
                """
                folder_id = folder.get('id')
                folder_name = folder.get('name')
                
                if folder_id and folder_name:
                    # Unterordner verarbeiten
                    subfolders = []
                    subfolder_ids = []
                    
                    if 'folders' in folder:
                        for subfolder in folder.get('folders', []):
                            if subfolder.get('id') and subfolder.get('name'):
                                subfolders.append(subfolder.get('name'))
                                subfolder_ids.append(str(subfolder.get('id')))
                    
                    # Ordner zum DataFrame hinzufügen
                    folder_record = {
                        'folder_id': folder_id,
                        'name': folder_name,
                        'parent': parent,
                        'parent_id': parent_id,
                        'subfolder': ', '.join(subfolders) if subfolders else None,
                        'subfolder_id': ', '.join(subfolder_ids) if subfolder_ids else None
                    }
                    folder_records.append(folder_record)
                    
                    # Charts in diesem Ordner verarbeiten
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
                    
                    # Rekursiv alle Unterordner durchgehen
                    if 'folders' in folder:
                        for subfolder in folder.get('folders', []):
                            process_folder(subfolder, folder_name, folder_id)
            
            # Hauptordner in der Liste verarbeiten
            for item in folders_data.get('list', []):
                # Charts im Root-Ordner verarbeiten
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
                
                # Nur Team-Ordner verarbeiten, User-Ordner ignorieren
                if item.get('type') == 'team':
                    process_folder(item)
                    
                    # Unterordner des Team-Ordners verarbeiten
                    for subfolder in item.get('folders', []):
                        process_folder(subfolder, item.get('name'), item.get('id'))
            
            # DataFrames aus den gesammelten Daten erstellen
            folders_df = pd.DataFrame(folder_records)
            charts_df = pd.DataFrame(chart_records)
            
            # Duplikate Charts entfernen
            charts_df = charts_df.drop_duplicates(subset=['chart_id'])
            
            # Datumsstrings in Datetime-Objekte umwandeln
            if not charts_df.empty and 'date' in charts_df.columns:
                charts_df['date'] = pd.to_datetime(charts_df['date'])
                    
            return folders_df, charts_df
            
        except requests.exceptions.RequestException as e:
            logger.error(f'API-Fehler beim Abrufen der Ordner: {e}')
            if hasattr(e, 'response') and e.response:
                logger.error(f'API-Antwort: {e.response.status_code} - {e.response.text}')
            return pd.DataFrame(), pd.DataFrame()
        except Exception as e:
            logger.error(f'Allgemeiner Fehler beim Abrufen der Ordner: {e}')
            return pd.DataFrame(), pd.DataFrame()

    def filter_folders(self, charts, folders, exclude_names=['printexport']):
        """
        Filtert Charts basierend auf ausgeschlossenen Ordnernamen.
        
        Args:
            charts (DataFrame): DataFrame mit allen Charts
            folders (DataFrame): DataFrame mit allen Ordnern
            exclude_names (list): Liste von Ordnernamen, die ausgeschlossen werden sollen
            
        Returns:
            DataFrame: Gefiltertes DataFrame mit Charts
        """
        try:
            # Ordner finden, deren Name in der Ausschlussliste vorkommt
            subfolders = folders[folders["name"].isin(exclude_names)]
            
            # Liste der auszuschließenden Ordnernamen erstellen
            filterfolders_names = list(subfolders["name"].unique())
            
            # Unterordner zur Ausschlussliste hinzufügen
            for subfolder_str in subfolders["subfolder"].dropna():
                subfolders_elements = [s.strip() for s in subfolder_str.split(",")]
                filterfolders_names.extend(subfolders_elements)
            
            # Duplikate entfernen
            filterfolders_names = list(set(filterfolders_names))
            
            # Charts basierend auf Ordnernamen filtern
            charts_filtered = charts[~charts['folder_name'].isin(filterfolders_names)]
            
            return charts_filtered
        except Exception as e:
            logger.error(f'Fehler beim Filtern der Ordner: {e}')
            return charts

    def get_custom_fields(self, chart_details):
        """
        Extrahiert Custom Fields aus den Chart-Details.
        
        Args:
            chart_details (dict): Chart-Details aus der API
            
        Returns:
            dict: Dictionary mit custom_fields und deren Werten
        """
        # Initialisiere custom_fields mit Standardwerten
        custom_fields = {
            "kommentar": "",
            "tags": "",
            "patch": "false",
            "evergreen": "false",
            "regional": "false"
        }
        
        # Metadaten holen
        metadata = chart_details.get('metadata', {})
        
        # 1. Direkte Custom Fields auslesen
        custom = metadata.get('custom', {})
        if custom:
            for key, value in custom.items():
                if value is not None:
                    custom_fields[key] = str(value)
            
        # 2. Beschreibende Metadaten auslesen
        describe = metadata.get('describe', {})
        if describe:
            for key, value in describe.items():
                if value and key not in ['intro', 'notes', 'byline']:
                    custom_fields[f"describe_{key}"] = str(value)
                    
        # 3. Visualisierungseinstellungen auslesen
        visualize = metadata.get('visualize', {})
        if visualize:
            for key, value in visualize.items():
                if value and isinstance(value, (str, int, float, bool)):
                    custom_fields[f"visualize_{key}"] = str(value)
        
        return custom_fields

    def generate_thumbnail(self, image_data, path):
        """
        Erstellt ein Thumbnail aus den exportierten Datawrapper-Daten.
        
        Args:
            image_data (bytes): Bild-Daten aus der API
            path (str): Pfad zum Speichern des Thumbnails
            
        Raises:
            Exception: Wenn das Erstellen des Thumbnails fehlschlägt
        """
        try:
            # Bild aus Binärdaten öffnen
            image = Image.open(BytesIO(image_data))
            
            # Neue Größe berechnen (Seitenverhältnis beibehalten)
            target_width = 800
            width_percent = (target_width / float(image.size[0]))
            target_height = int((float(image.size[1]) * float(width_percent)))
            
            # Bild in hoher Qualität resizen
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Thumbnail in hoher Qualität speichern
            image.save(path, optimize=True, quality=90)
            
        except Exception as e:
            raise Exception(f"Fehler beim Erstellen des Thumbnails: {e}") 

    def handle(self, *args, **kwargs):
        """
        Hauptmethode zur Ausführung des Management-Commands.
        
        Führt folgende Schritte aus:
        1. Lädt API-Credentials
        2. Holt alle Ordner und Charts von Datawrapper
        3. Filtert Charts nach Ordnern
        4. Identifiziert und verarbeitet neue Charts
        5. Erstellt Thumbnails und speichert alles in der Datenbank
        6. Wiederholt den Vorgang alle 15 Minuten
        """
        # API-Key aus der .env Datei laden
        api_key = os.getenv('DATAWRAPPER_API_KEY')
        if not api_key:
            logger.error("Kein API-Key gefunden. Bitte DATAWRAPPER_API_KEY in .env definieren.")
            return
            
        self.headers = {"Authorization": f"Bearer {api_key}"}
        
        # Startdatum für die Filterung (UTC)
        start_date = datetime(2025, 4, 1, tzinfo=timezone.utc)

        while True:
            self.stdout.write('Datawrapper-API wird abgefragt...')
            
            # Gelöschte Grafiken prüfen
            deleted_count = self.check_deleted_charts(self.headers)
            self.stdout.write(f'Gelöschte Grafiken entfernt: {deleted_count}')
            
            # Alle Ordner und Charts holen
            folders_df, charts_df = self.get_all_folders(self.headers)
            if folders_df.empty or charts_df.empty:
                logger.error('Keine Ordner oder Charts gefunden.')
                time.sleep(900)  # 15 Minuten warten
                continue
                
            logger.info(f'Gefundene Ordner: {len(folders_df)}')
            logger.info(f'Gefundene Charts: {len(charts_df)}')
            
            # Unerwünschte Ordner aus den Charts filtern
            exclude_names = ['printexport']
            filtered_charts = self.filter_folders(charts_df, folders_df, exclude_names=exclude_names)
            logger.info(f'Gefilterte Charts: {len(filtered_charts)}')
            
            # Bereits existierende Charts identifizieren
            existing_chart_ids = set(Chart.objects.values_list('chart_id', flat=True))
            all_chart_ids = filtered_charts["chart_id"].unique()
            
            # Neue Charts identifizieren
            new_chart_ids = [chart_id for chart_id in all_chart_ids if chart_id not in existing_chart_ids]
            logger.info(f'Neue Charts zum Verarbeiten: {len(new_chart_ids)}')
            
            # Neue Charts verarbeiten
            for chart_id in new_chart_ids:
                logger.debug(f"Verarbeite Chart ID: {chart_id}")
                try:
                    # Chart-Details abrufen
                    chart_details_url = f"https://api.datawrapper.de/v3/charts/{chart_id}?expand=true"
                    details_response = requests.get(chart_details_url, headers=self.headers)
                    details_response.raise_for_status()
                    chart_details = details_response.json()
                    
                    # Prüfen, ob die Grafik veröffentlicht wurde
                    if chart_details.get('publishedAt') is None:
                        logger.info(f"Chart {chart_id} ist nicht veröffentlicht, überspringe...")
                        continue
                        
                    # Basisdaten extrahieren
                    title = chart_details.get('title', '')
                    description = chart_details.get('metadata', {}).get('describe', {}).get('intro', '')
                    notes = chart_details.get('metadata', {}).get('describe', {}).get('notes', '')
                    published_at_str = chart_details.get('publishedAt')
                    lastModified_at_str = chart_details.get('lastModifiedAt')
                    
                    # Responsive Iframe aus den Metadaten extrahieren
                    iframe_url = chart_details.get('metadata', {}).get('publish', {}).get('embed-codes', {}).get('responsive', '')
                    
                    # Debug-Ausgabe der Metadaten-Struktur für embed-codes
                    embed_codes = chart_details.get('metadata', {}).get('publish', {}).get('embed-codes', {})
                    logger.debug(f"Embed-Codes Struktur für Chart {chart_id}: {json.dumps(embed_codes, indent=2)[:500] + '...' if embed_codes else 'Keine embed-codes gefunden'}")
                    
                    # Fallback zur alten API-Struktur oder zur publicUrl, falls der responsive Iframe nicht gefunden wird
                    if not iframe_url:
                        # Versuche zuerst, den alten Pfad zu nutzen
                        iframe_url = chart_details.get('metadata', {}).get('publish', {}).get('embed-responsive', '')
                        
                        # Wenn auch das nicht funktioniert, verwende die publicUrl als Fallback
                        if not iframe_url:
                            iframe_url = chart_details.get('publicUrl', '')
                    
                    # Debug-Ausgabe für iframe_url
                    if iframe_url:
                        logger.debug(f"Iframe URL für Chart {chart_id}: {iframe_url[:100]}... (verkürzt)" if len(iframe_url) > 100 else iframe_url)
                    else:
                        logger.warning(f"Keine Iframe URL für Chart {chart_id} gefunden")
                    
                    # Embed-Code aus den Metadaten extrahieren
                    embed_js = chart_details.get('metadata', {}).get('publish', {}).get('embed-codes', {}).get('embed', '')
                    # Fallback zur alten API-Struktur, falls der neue Pfad leer ist
                    if not embed_js:
                        embed_js = chart_details.get('metadata', {}).get('publish', {}).get('embed', '')
                    
                    # Wenn embed_js immer noch leer ist, eigenen Code generieren
                    if not embed_js:
                        embed_js = f'<script src="https://static.rndtech.de/share/rnd/datenrecherche/script/dw_chart_min.js" defer></script>\n<dw-chart\n    chart-id="{chart_id}">\n</dw-chart>'
                    
                    # Custom Fields extrahieren
                    custom_fields = self.get_custom_fields(chart_details)
                    comments = custom_fields.get("kommentar", "")
                    tags = custom_fields.get("tags", "") or ""
                    
                    # Ordnername zu Tags hinzufügen
                    # Schritt 1: Ordnername aus Filtern Charts extrahieren
                    chart_filter = filtered_charts[filtered_charts["chart_id"] == chart_id]
                    if not chart_filter.empty and "folder_name" in chart_filter.columns and len(chart_filter["folder_name"].values) > 0:
                        folder_name = chart_filter["folder_name"].values[0]
                        
                        # Schritt 2: Wenn der Ordnername "RND" oder leer ist, überspringe, ansonsten Ordnername zu Tags hinzufügen
                        while folder_name and folder_name != "RND" and folder_name != "":
                            if tags.strip():
                                tags = tags.strip().rstrip(',') + ", " + folder_name.strip()
                            else:
                                tags = folder_name.strip()
                                
                            # Prüfen, ob der Ordner in folders_df existiert und einen parent hat
                            parent_filter = folders_df[folders_df["name"] == folder_name]
                            if parent_filter.empty or "parent" not in parent_filter.columns or len(parent_filter["parent"].values) == 0:
                                break
                                
                            parent = parent_filter["parent"].values[0]
                            if parent is None:
                                break
                                
                            folder_name = parent
                        
                    # Boolean-Felder extrahieren
                    patch = custom_fields.get("patch", "false")
                    evergreen = custom_fields.get("evergreen", "false")
                    regional = custom_fields.get("regional", "false")
                    
                    # Datumswerte konvertieren
                    published_date = None
                    last_modified_date = None
                    if published_at_str:
                        try:
                            published_date = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                        except Exception as e:
                            logger.warning(f"Fehler beim Konvertieren des Veröffentlichungsdatums für Chart {chart_id}: {e}")
                    if lastModified_at_str:
                        try:
                            last_modified_date = datetime.fromisoformat(lastModified_at_str.replace('Z', '+00:00'))
                        except Exception as e:
                            logger.warning(f"Fehler beim Konvertieren des Änderungsdatums für Chart {chart_id}: {e}")

                    # Chart in der Datenbank speichern
                    try:
                        # Prüfe, ob die Chart bereits existiert
                        chart_obj = Chart.objects.get(chart_id=chart_id)
                        
                        # Aktualisiere die bestehende Chart
                        chart_obj.published_date = published_date
                        chart_obj.title = title
                        chart_obj.description = description
                        chart_obj.notes = notes
                        chart_obj.comments = comments
                        chart_obj.tags = tags
                        chart_obj.patch = True if patch.lower() == 'true' else False
                        chart_obj.evergreen = True if evergreen.lower() == 'true' else False
                        chart_obj.regional = True if regional.lower() == 'true' else False
                        chart_obj.last_modified_date = last_modified_date
                        chart_obj.iframe_url = iframe_url or ''
                        chart_obj.embed_js = embed_js
                        chart_obj.save()
                        
                        logger.info(f"Bestehendes Chart aktualisiert: {title} (ID: {chart_id})")
                    except Chart.DoesNotExist:
                        # Erstelle eine neue Chart
                        chart_obj = Chart.objects.create(
                            published_date=published_date,
                            chart_id=chart_id,
                            title=title,
                            description=description,
                            notes=notes,
                            comments=comments,
                            tags=tags,
                            patch=True if patch.lower() == 'true' else False,
                            evergreen=True if evergreen.lower() == 'true' else False,
                            regional=True if regional.lower() == 'true' else False,
                            last_modified_date=last_modified_date,
                            iframe_url=iframe_url or '',
                            embed_js=embed_js,
                        )
                        logger.info(f"Neues Chart gespeichert: {title} (ID: {chart_id})")

                    # Thumbnail erstellen, wenn URL vorhanden
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
                            chart_obj.save()
                        except Exception as e:
                            logger.warning(f'Thumbnail konnte nicht erstellt werden für {chart_id}: {e}')

                    logger.info(f"Neue Grafik gespeichert: {title} (ID: {chart_id})")
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f'API-Fehler bei der Verarbeitung von Chart {chart_id}: {e}')
                    if hasattr(e, 'response') and e.response:
                        logger.error(f'API-Antwort: {e.response.status_code} - {e.response.text[:200]}')
                except Exception as e:
                    logger.error(f'Allgemeiner Fehler bei der Verarbeitung von Chart {chart_id}: {e}')
                    continue

            # Warten bis zum nächsten Durchlauf
            logger.info('Warte 15 Minuten bis zum nächsten Durchlauf...')
            time.sleep(900) 