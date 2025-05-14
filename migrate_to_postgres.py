import json
import psycopg2
import os

CLEAR_EXISTING_DATA = True  # Von False auf True ändern

def import_from_json():
    print("Importiere Daten aus datensicherung.json in PostgreSQL...")
    
    # PostgreSQL-Verbindungsparameter
    pg_params = {
        'dbname': 'webarchiv_db',
        'user': 'webarchiv_db_user',
        'password': "adfhLHoihol34",  # Hier anpassen!
        'host': 'localhost',
        'port': '5432'
    }
    
    
    # JSON-Datei laden
    with open('datensicherung.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Verbindung zu PostgreSQL
    conn = psycopg2.connect(**pg_params)
    cursor = conn.cursor()
    
    # Am Anfang deiner import_from_json-Funktion nach dem Verbindungsaufbau:
    #cursor.execute("SET session_replication_role = 'replica';")  # Deaktiviert Fremdschlüssel-Prüfungen
    
    # Importiere Tabelle für Tabelle
    exclude_tables = [
        # Auth-Tabellen
        'auth_user', 'auth_user_groups', 'auth_group', 'auth_permission', 
        'auth_group_permissions', 'django_admin_log',
        
        # Tabellen mit Fremdschlüssel-Problemen
        'core_chartblacklist', 
        
        # Weitere Tabellen mit möglichen Beziehungen zu Benutzern
        'core_userprofile', 'core_notification', 'core_comment',
        'core_message', 'core_subscription'
    ]
    for table_name, table_data in data.items():
        if table_name in exclude_tables:
            print(f"Überspringe Tabelle {table_name} (potenzielle Fremdschlüssel-Konflikte)")
            continue
            
        print(f"Importiere Daten in Tabelle: {table_name}")
        rows = table_data.get('data', [])
        
        if not rows:
            print(f"  Keine Daten für {table_name}")
            continue
        
        # Zähler für erfolgreich eingefügte Zeilen
        inserted = 0
        
        # Definiere alle bekannten Boolean-Felder in deinen Modellen
        boolean_fields = [
            'evergreen', 'patch', 'published', 'active', 'is_public', 'featured',
            'is_published', 'is_draft', 'confirmed', 'is_active', 'regional'
        ]
        
        if CLEAR_EXISTING_DATA and table_name not in ['django_content_type', 'auth_permission']:
            print(f"  Lösche bestehende Daten aus {table_name}")
            cursor.execute(f'DELETE FROM "{table_name}";')
            conn.commit()
        
        for row in rows:
            columns = list(row.keys())
            
            # Werte vorbereiten
            values = []
            for col in columns:
                val = row[col]
                
                # Konvertiere 0/1 zu bool für alle typischen Boolean-Felder
                is_boolean_field = (col in ['evergreen', 'patch', 'confirmed', 'active', 'published', 'regional'] or
                                    col.startswith('is_') or col.startswith('has_'))
                
                if is_boolean_field and isinstance(val, (int, float)):
                    val = bool(val)
                
                if isinstance(val, str) and len(val) > 250:  # Etwas Puffer lassen
                    val = val[:250]  # Schneide Text auf 250 Zeichen ab
                
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
                
                # Versuche mit bereinigten Daten
                try:
                    clean_values = []
                    for val in values:
                        if isinstance(val, str):
                            # Ersetze problematische Zeichen
                            clean_val = ''.join(c if ord(c) < 128 else '?' for c in val)
                            clean_values.append(clean_val)
                        else:
                            clean_values.append(val)
                    
                    cursor.execute(sql, clean_values)
                    inserted += 1
                except Exception as e2:
                    print(f"  Auch bereinigte Daten konnten nicht eingefügt werden: {e2}")
        
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
    # Am Ende vor dem Schließen der Verbindung:
    #cursor.execute("SET session_replication_role = 'origin';")  # Reaktiviert Fremdschlüssel-Prüfungen
    conn.close()
    print("Datenimport abgeschlossen!")

if __name__ == "__main__":
    # Stelle sicher, dass die PostgreSQL-Datenbankstruktur existiert
    if not os.path.exists('datensicherung.json'):
        print("Fehler: datensicherung.json nicht gefunden!")
    else:
        import_from_json()