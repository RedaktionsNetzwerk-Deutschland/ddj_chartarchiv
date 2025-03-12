from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from core.models import Chart
import requests
import time
import json
from dateutil import parser

class Command(BaseCommand):
    help = 'Lädt Grafiken von Datawrapper herunter'

    def parse_date(self, date_str):
        """
        Parst ein Datum und stellt sicher, dass es timezone-aware ist
        """
        if not date_str:
            return None
        try:
            # Versuche das Datum zu parsen und stelle sicher, dass es UTC ist
            date = parser.parse(date_str)
            # Wenn das Datum keine Zeitzone hat, nehmen wir UTC an
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            else:
                # Konvertiere zu UTC wenn es eine andere Zeitzone hat
                date = date.astimezone(timezone.utc)
            return date
        except Exception as e:
            self.stderr.write(f'Fehler beim Parsen des Datums {date_str}: {str(e)}')
            return None

    def is_created_after_2025(self, date_str):
        """
        Prüft, ob ein Datum nach dem 1.1.2025 liegt
        """
        try:
            parsed_date = self.parse_date(date_str)
            if parsed_date is None:
                return False
                
            start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
            return parsed_date >= start_date
        except Exception as e:
            self.stderr.write(f'Fehler beim Vergleichen des Datums: {str(e)}')
            return False

    def is_created_in_2025(self, date_str):
        """
        Prüft, ob eine Grafik in 2025 erstellt wurde.
        Verwendet eine einfache String-Prüfung statt Datum-Parsing.
        """
        if not date_str:
            return False
        return date_str.startswith('2025-')

    def get_all_folders(self):
        url = 'https://api.datawrapper.de/v3/folders'
        response = requests.get(url, headers={'Authorization': 'Bearer YOUR_API_KEY'})
        if response.status_code == 200:
            return response.json().get('list', [])
        return []

    def get_charts_from_folder(self, folder_id):
        url = f'https://api.datawrapper.de/v3/folders/{folder_id}/charts'
        response = requests.get(url, headers={'Authorization': 'Bearer YOUR_API_KEY'})
        if response.status_code == 200:
            return response.json()
        return []

    def get_root_charts(self):
        url = 'https://api.datawrapper.de/v3/charts'
        response = requests.get(url, headers={'Authorization': 'Bearer YOUR_API_KEY'})
        if response.status_code == 200:
            return response.json().get('list', [])
        return []

    def process_chart(self, chart):
        """
        Verarbeitet eine einzelne Grafik.
        """
        try:
            chart_id = chart.get('id')
            title = chart.get('title', '')
            chart_type = chart.get('type', '')
            theme = chart.get('theme', '')
            created_at = chart.get('createdAt', '')
            
            # Hier können Sie die Grafik in Ihrer Datenbank speichern
            self.stdout.write(f"Grafik verarbeitet: ID={chart_id}, Titel={title}, Typ={chart_type}, Theme={theme}, Erstellt={created_at}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Fehler beim Verarbeiten der Grafik {chart.get('id', 'UNKNOWN')}: {str(e)}"))

    def check_deleted_charts(self):
        charts = Chart.objects.all()
        deleted_count = 0
        for chart in charts:
            try:
                url = f'https://api.datawrapper.de/v3/charts/{chart.chart_id}'
                response = requests.get(url, headers={'Authorization': 'Bearer YOUR_API_KEY'})
                if response.status_code == 404:
                    chart.delete()
                    deleted_count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Fehler beim Überprüfen der Grafik {chart.chart_id}: {str(e)}'))
        self.stdout.write(f'Gelöschte Grafiken entfernt: {deleted_count}')
        return deleted_count

    def handle(self, *args, **options):
        self.charts_2025 = 0  # Zähler für Grafiken aus 2025
        deleted_charts = self.check_deleted_charts()
        self.stdout.write(f"Gelöschte Grafiken entfernt: {deleted_charts}")
        
        # Hole alle Ordner
        folders = self.get_all_folders()
        if not folders:
            self.stdout.write(self.style.ERROR("Keine Ordner gefunden"))
            return
        
        self.stdout.write(f"Gefundene Ordner in diesem Durchgang: {len(folders)}")
        
        total_charts = []
        
        # Verarbeite jeden Ordner
        for folder in folders:
            folder_id = folder.get('id')
            folder_name = folder.get('name', '')
            self.stdout.write(f"Verarbeite Ordner: {folder_name} (ID: {folder_id})")
            
            try:
                folder_charts = self.get_charts_from_folder(folder_id)
                if folder_charts:
                    total_charts.extend(folder_charts)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Fehler beim Abrufen der Grafiken aus Ordner {folder_id}: {str(e)}"))
        
        # Hole Root-Grafiken
        root_charts = self.get_root_charts()
        if root_charts:
            self.stdout.write(f"Gefundene Root-Grafiken: {len(root_charts)}")
            total_charts.extend(root_charts)
        
        self.stdout.write(f"Insgesamt gefundene Grafiken: {len(total_charts)}")
        
        # Verarbeite alle Grafiken
        for chart in total_charts:
            try:
                chart_id = chart.get('id', 'UNKNOWN')
                created_at = chart.get('createdAt', '')
                
                if self.is_created_in_2025(created_at):
                    self.charts_2025 += 1
                    self.stdout.write(self.style.SUCCESS(f"Verarbeite Grafik aus 2025: {chart_id} (erstellt am {created_at})"))
                    self.process_chart(chart)
                else:
                    self.stdout.write(f"Überspringe Grafik (nicht aus 2025): {chart_id} (erstellt am {created_at})")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Fehler beim Verarbeiten der Grafik {chart.get('id', 'UNKNOWN')}: {str(e)}"))
                continue
        
        self.stdout.write(self.style.SUCCESS(f"Gefundene und verarbeitete Grafiken aus 2025: {self.charts_2025}"))
        self.stdout.write("Sleeping for 120 seconds...")
        time.sleep(120) 