import json
import psycopg2
import os

def migrate_auth_tables():
    print("Importiere Benutzerkonten und zugehörige Tabellen in PostgreSQL...")
    
    # PostgreSQL-Verbindungsparameter
    pg_params = {
        'dbname': 'webarchiv_DB',
        'user': 'webarchiv_DB',
        'password': "23_D!XYots3500?_$",
        'host': 'localhost',
        'port': '5432'
    }
    
    # JSON-Datei laden
    with open('datensicherung.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Verbindung zu PostgreSQL
    conn = psycopg2.connect(**pg_params)
    cursor = conn.cursor()
    
    # Liste der zu migrierenden Auth-Tabellen in der richtigen Reihenfolge
    auth_tables = [
        'auth_user',               # Zuerst Benutzer
        'auth_group',              # Dann Gruppen
        'auth_permission',         # Dann Berechtigungen
        'auth_user_groups',        # Dann Benutzer-Gruppen-Zuweisungen
        'auth_group_permissions',  # Dann Gruppen-Berechtigungen
        'django_admin_log',        # Admin-Logs
        'core_userprofile',        # Benutzerprofile
        'core_notification',       # Benachrichtigungen
        'core_comment',            # Kommentare
        'core_message',            # Nachrichten
        'core_subscription',       # Abonnements
        'core_chartblacklist'      # Chart-Blacklist
    ]
    
    # Importiere Tabelle für Tabelle
    for table_name in auth_tables:
        if table_name not in data:
            print(f"Tabelle {table_name} nicht in Datensicherung gefunden, überspringe...")
            continue
            
        table_data = data[table_name]
        print(f"Importiere Daten in Tabelle: {table_name}")
        rows = table_data.get('data', [])
        
        if not rows:
            print(f"  Keine Daten für {table_name}")
            continue
        
        # Zähler für erfolgreich eingefügte Zeilen
        inserted = 0
        
        # Bestehende Daten löschen
        print(f"  Lösche bestehende Daten aus {table_name}")
        cursor.execute(f'DELETE FROM "{table_name}";')
        conn.commit()
        
        for row in rows:
            columns = list(row.keys())
            
            # Werte vorbereiten
            values = []
            for col in columns:
                val = row[col]
                
                # Konvertiere 0/1 zu bool für typische Boolean-Felder
                is_boolean_field = (col in ['evergreen', 'patch', 'confirmed', 'active', 'published', 'regional'] or
                                    col.startswith('is_') or col.startswith('has_'))
                
                if is_boolean_field and isinstance(val, (int, float)):
                    val = bool(val)
                
                values.append(val)
            
            # SQL für INSERT
            placeholders = ', '.join(['%s'] * len(columns))
            columns_str = ', '.join([f'"{col}"' for col in columns])
            sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders});'
            
            try:
                cursor.execute(sql, values)
                inserted += 1
                
                # Regelmäßiges Commit
                if inserted % 100 == 0:
                    conn.commit()
                    print(f"  {inserted} Zeilen eingefügt...")
                    
            except Exception as e:
                print(f"  Fehler beim Einfügen in {table_name}: {e}")
                conn.rollback()
                
                # Bei Fehler Details ausgeben
                print(f"  Problematische Daten: {row}")
        
        # Commit für diese Tabelle
        conn.commit()
        print(f"  {inserted} von {len(rows)} Einträgen in {table_name} importiert")
    
    # Sequenzen aktualisieren
    print("Aktualisiere Sequenzen...")
    cursor.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE column_default LIKE 'nextval%';
    """)
    
    sequences = cursor.fetchall()
    for table, column in sequences:
        if table in auth_tables:
            print(f"  Aktualisiere Sequenz für {table}.{column}")
            cursor.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('"{table}"', '{column}'),
                    COALESCE(MAX("{column}"), 1),
                    MAX("{column}") IS NOT NULL
                )
                FROM "{table}";
            """)
    
    conn.commit()
    conn.close()
    print("Migration der Auth-Tabellen abgeschlossen!")

if __name__ == "__main__":
    # Stelle sicher, dass die PostgreSQL-Datenbankstruktur existiert
    if not os.path.exists('datensicherung.json'):
        print("Fehler: datensicherung.json nicht gefunden!")
    else:
        migrate_auth_tables() 