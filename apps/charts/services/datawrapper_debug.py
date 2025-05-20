"""
Debug-Erweiterung für Datawrapper-Service.
Bietet eine einfache Funktion, um Metadaten einer Grafik zu debuggen.
"""

def debug_chart_metadata(self, chart_id):
    """
    Zeigt alle Metadaten einer Datawrapper-Grafik an.
    
    Diese Methode kann zur DatawrapperService-Klasse hinzugefügt werden.
    
    Args:
        chart_id: Die ID der zu debuggenden Grafik
    """
    import json
    import sys
    
    try:
        # Chart-Details abrufen
        chart_details = self.get_chart(chart_id)
        
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
        
        return chart_details
        
    except Exception as e:
        print(f"FEHLER beim Abrufen der Metadaten: {str(e)}")
        return None

# Beispiel für die Integration in die DatawrapperService-Klasse:
"""
# In apps/charts/services/datawrapper.py:
from apps.charts.services.datawrapper_debug import debug_chart_metadata

# Füge diese Zeile am Ende der DatawrapperService-Klasse hinzu:
DatawrapperService.debug_chart_metadata = debug_chart_metadata
""" 