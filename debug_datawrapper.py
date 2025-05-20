#!/usr/bin/env python
"""
Debug-Skript für Datawrapper-Grafiken.
Zeigt alle Metadaten einer Datawrapper-Grafik an.
"""

import json
import requests
import os
import sys
from django.conf import settings
from dotenv import load_dotenv

# Umgebungsvariablen aus .env laden (falls verwendet)
load_dotenv()

def debug_chart_metadata(chart_id):
    """
    Zeigt alle Metadaten einer Datawrapper-Grafik an.
    
    Args:
        chart_id: Die ID der zu debuggenden Grafik
    """
    # API-Key aus den Einstellungen oder der Umgebung holen
    api_key = getattr(settings, 'DATAWRAPPER_API_KEY', None) or os.environ.get('DATAWRAPPER_API_KEY')
    
    if not api_key:
        print("FEHLER: Datawrapper API-Key nicht gefunden")
        sys.exit(1)
    
    # API-Header erstellen
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Chart-Details abrufen
    try:
        # API-Anfrage für die Grafik mit allen Details (expand=true)
        chart_details_url = f"https://api.datawrapper.de/v3/charts/{chart_id}?expand=true"
        response = requests.get(chart_details_url, headers=headers)
        response.raise_for_status()  # Fehler bei HTTP-Status-Codes werfen
        chart_details = response.json()
        
        # Metadaten formatiert ausgeben
        print("\n===== DATAWRAPPER GRAFIK-METADATEN DEBUGGER =====")
        print(f"Chart-ID: {chart_id}")
        print(f"Titel: {chart_details.get('title', 'N/A')}")
        print(f"Typ: {chart_details.get('type', 'N/A')}")
        print(f"Theme: {chart_details.get('theme', 'N/A')}")
        print(f"Erstellt am: {chart_details.get('createdAt', 'N/A')}")
        print(f"Zuletzt geändert: {chart_details.get('lastModifiedAt', 'N/A')}")
        print(f"Veröffentlicht am: {chart_details.get('publishedAt', 'N/A') or 'Nicht veröffentlicht'}")
        print(f"Autor: {chart_details.get('author', {}).get('name', 'N/A')}")
        print(f"Öffentliche URL: {chart_details.get('publicUrl', 'N/A')}")
        print(f"Eingebettete URL: {chart_details.get('publicUrl', 'N/A')}")
        print("\n--- Beschreibende Metadaten ---")
        
        # Beschreibung und Notizen
        describe = chart_details.get('metadata', {}).get('describe', {})
        print(f"Einleitung: {describe.get('intro', 'N/A')}")
        print(f"Notizen: {describe.get('notes', 'N/A')}")
        print(f"Quellen: {describe.get('byline', 'N/A')}")
        
        # Veröffentlichungs-Metadaten
        print("\n--- Veröffentlichungs-Metadaten ---")
        publish = chart_details.get('metadata', {}).get('publish', {})
        
        # Embed-Codes
        embed_codes = publish.get('embed-codes', {})
        if embed_codes:
            print("Verfügbare Embed-Codes:")
            for key in embed_codes:
                print(f"  - {key}")
        
        # Custom fields
        print("\n--- Benutzerdefinierte Felder ---")
        custom_fields = chart_details.get('metadata', {}).get('custom', {})
        if custom_fields:
            for key, value in custom_fields.items():
                # Für bessere Lesbarkeit kurz fassen, wenn es sich um lange Inhalte handelt
                if isinstance(value, str) and len(value) > 100:
                    print(f"{key}: {value[:100]}... (gekürzt)")
                else:
                    print(f"{key}: {value}")
        
        # Datenwerte
        print("\n--- Datenstruktur (erste 5 Zeilen) ---")
        data = chart_details.get('data', {})
        if isinstance(data, dict) and 'data' in data:
            data_rows = data['data']
            if isinstance(data_rows, list):
                for i, row in enumerate(data_rows[:5]):
                    print(f"Zeile {i+1}: {row}")
                if len(data_rows) > 5:
                    print(f"... und {len(data_rows) - 5} weitere Zeilen")
        
        # Vollständige JSON-Ausgabe
        print("\n=== VOLLSTÄNDIGE METADATEN ===")
        print(json.dumps(chart_details, indent=2, ensure_ascii=False))
        
    except requests.exceptions.RequestException as e:
        print(f"FEHLER bei API-Anfrage: {str(e)}")
        if hasattr(e, 'response') and e.response:
            try:
                error_details = e.response.json()
                print(f"API-Fehlermeldung: {error_details.get('message', 'Keine Details verfügbar')}")
            except:
                print(f"Status-Code: {e.response.status_code}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Verwendung: python debug_datawrapper.py <chart_id>")
        sys.exit(1)
    
    chart_id = sys.argv[1]
    debug_chart_metadata(chart_id) 