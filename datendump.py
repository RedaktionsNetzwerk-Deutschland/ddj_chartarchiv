import os
import sys
import json
import sqlite3
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path

def fix_encoding(text):
    """Versucht, Kodierungsprobleme zu beheben"""
    if not isinstance(text, str) or not text:
        return text
    
    # Encodings, die wir ausprobieren werden
    encodings = ['latin-1', 'cp1252', 'iso-8859-1']
    
    # Durchlaufe alle Encodings
    for enc in encodings:
        try:
            fixed = text.encode('raw_unicode_escape').decode(enc)
            return fixed
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
    
    return text

def dump_sqlite_data():
    """Extrahiert Daten direkt aus der SQLite-Datenbank"""
    print("Starte direkten SQLite-Datendump...")
    
    # SQLite-Verbindung herstellen
    sqlite_path = 'db.sqlite3'
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Alle Tabellen abrufen
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'django_migrations';")
    tables = [row['name'] for row in cursor.fetchall()]
    
    all_data = {}
    
    for table in tables:
        print(f"Verarbeite Tabelle: {table}")
        
        # Schema der Tabelle abrufen
        cursor.execute(f"PRAGMA table_info({table});")
        columns = {col['name']: col['type'] for col in cursor.fetchall()}
        
        # Daten aus der Tabelle abrufen
        cursor.execute(f"SELECT * FROM {table};")
        rows = cursor.fetchall()
        
        if not rows:
            print(f"  Keine Daten in {table}")
            continue
        
        # Tabellendaten speichern
        table_data = []
        for row in rows:
            row_dict = {}
            for key in row.keys():
                value = row[key]
                # Bei Text-Feldern die Kodierung korrigieren
                if isinstance(value, str):
                    value = fix_encoding(value)
                row_dict[key] = value
            table_data.append(row_dict)
        
        all_data[table] = {
            'schema': columns,
            'data': table_data
        }
        print(f"  {len(table_data)} Einträge verarbeitet")
    
    # Als JSON speichern
    output_file = "datensicherung.json"
    
    # JSON-Encoder für spezielle Datentypen
    class JSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            return super().default(obj)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, cls=JSONEncoder, ensure_ascii=False, indent=4)
    
    print(f"\nDatendump abgeschlossen. Daten aus {len(all_data)} Tabellen gespeichert in {output_file}")
    conn.close()

if __name__ == "__main__":
    dump_sqlite_data()