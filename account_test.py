import os
import requests
import json
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# Hole API-Schlüssel aus Umgebungsvariablen
api_key = os.getenv('DATAWRAPPER_API_KEY')
if not api_key:
    print("FEHLER: Kein API-Schlüssel gefunden. Bitte stelle sicher, dass die DATAWRAPPER_API_KEY in der .env-Datei definiert ist.")
    exit(1)

# Setze Header mit API-Schlüssel
headers = {"Authorization": f"Bearer {api_key}"}

def get_folder_contents(folder_id=None, level=0):
    """Holt rekursiv den Inhalt eines Ordners und seiner Unterordner"""
    base_url = "https://api.datawrapper.de/v3/folders"
    url = f"{base_url}/{folder_id}" if folder_id else base_url
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        print(data)
        # Speichern
        with open('daten.json', 'w', encoding='utf-8') as datei:
            json.dump(data, datei, ensure_ascii=False, indent=4)
        # Konvertiere die Daten in ein pandas DataFrame
        import pandas as pd
        
        # Wenn es sich um einen einzelnen Ordner handelt
        if folder_id:
            # Erstelle DataFrame aus dem Ordner-Objekt
            df = pd.DataFrame([data])
        else:
            # Erstelle DataFrame aus der Liste der Ordner
            df = pd.DataFrame(data.get('list', []))
        
        # Zeige die ersten Zeilen des DataFrames an
        print(f"DataFrame für Ordner {folder_id if folder_id else 'Alle'}:")
        
       
        # Wenn es sich um einen einzelnen Ordner handelt
        if folder_id:
            folder_data = data
        else:
            # Wenn es sich um die Liste aller Ordner handelt
            folder_data = data.get('list', [])
            
        # Verarbeite jeden Ordner
        for folder in folder_data:
            folder_name = folder.get('name', 'Unbenannt')
            folder_id = folder.get('id')
            
            # Gib den aktuellen Ordner aus
            indent = "  " * level
            print(f"{indent}📁 {folder_name} {folder_id}")
            
            # Rekursiver Aufruf für Unterordner
            if 'folders' in folder and folder['folders']:
                get_folder_contents(folder_id, level + 1)
        return df
    
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        

print("Starte API-Abfrage für Datawrapper-Ordnerstruktur...")
df = get_folder_contents()









# def get_all_charts(headers):
#     """Holt alle Grafiken von Datawrapper"""
    
#     if not headers:
#         return []
    
#     charts = []
#     next_link = "https://api.datawrapper.de/v3/charts"
    
#     print("Starte API-Abfrage für alle Datawrapper-Charts...")
    
#     while next_link:
#         try:
#             response = requests.get(next_link, headers=headers)
#             response.raise_for_status()
#             data = response.json()
            
#             # Füge die Charts dieser Seite hinzu
#             current_charts = data.get('list', [])
#             charts.extend(current_charts)
#             print(f"Gefundene Charts in diesem Durchgang: {len(current_charts)}")
            
#             # Prüfe, ob es eine nächste Seite gibt
#             next_link = data.get('next', None)
#         except requests.exceptions.RequestException as e:
#             print(f'Fehler beim Abrufen der Charts: {e}')
#             break
    
#     return charts

# def organize_charts_by_folder(charts, folders):
#     """Ordnet Charts den jeweiligen Ordnern zu"""
    
#     # Erstelle ein Dictionary mit Ordner-ID als Schlüssel und einer Liste von Charts als Wert
#     folder_charts = {}
    
#     # Erstelle ein Dictionary für einfachen Zugriff auf Ordner nach ID
#     folder_dict = {folder.get('id'): folder for folder in folders}
    
#     # Initialisiere für jeden Ordner eine leere Chart-Liste
#     for folder_id in folder_dict:
#         folder_charts[folder_id] = []
    
#     # Füge eine Kategorie für Charts ohne Ordner hinzu
#     folder_charts['no_folder'] = []
    
#     # Ordne jeden Chart dem entsprechenden Ordner zu
#     for chart in charts:
#         folder_id = chart.get('folderId')
        
#         if folder_id and folder_id in folder_charts:
#             folder_charts[folder_id].append(chart)
#         else:
#             folder_charts['no_folder'].append(chart)
    
#     return folder_charts, folder_dict

# def main():
#     """Hauptfunktion, die die Ordner und Charts abruft und ausgibt"""
    
#     print("Datawrapper Account-Test")
#     print("------------------------")
    
#     # Hole API-Header
#     headers = get_api_headers()
    
#     if not headers:
#         print("Konnte keine API-Anfragen ohne gültigen API-Schlüssel durchführen.")
#         return
    
#     # Hole alle Ordner
#     folders = get_all_folders(headers)
#     print(f"\nInsgesamt gefundene Ordner: {len(folders)}")
    
#     # Hole alle Charts
#     charts = get_all_charts(headers)
#     print(f"Insgesamt gefundene Charts: {len(charts)}")
    
#     # Organisiere Charts nach Ordnern
#     folder_charts, folder_dict = organize_charts_by_folder(charts, folders)
    
#     # Gib Informationen zu Ordnern und ihren Charts aus
#     print("\nOrdner mit Charts:")
#     print("----------------")
    
#     # Zuerst normale Ordner
#     for folder_id, charts_list in folder_charts.items():
#         if folder_id == 'no_folder':
#             continue  # Diese werden später ausgegeben
            
#         folder_name = folder_dict[folder_id].get('name', 'Kein Name')
#         print(f"\nOrdner: {folder_name} (ID: {folder_id})")
#         print(f"Anzahl Charts: {len(charts_list)}")
        
#         if charts_list:
#             print("Charts in diesem Ordner:")
#             for i, chart in enumerate(charts_list[:5], 1):  # Zeige die ersten 5 Charts
#                 chart_id = chart.get('id', 'Keine ID')
#                 chart_title = chart.get('title', 'Kein Titel')
#                 print(f"  {i}. {chart_title} (ID: {chart_id})")
            
#             if len(charts_list) > 5:
#                 print(f"  ... und {len(charts_list) - 5} weitere Charts")
    
#     # Dann Charts ohne Ordner
#     no_folder_charts = folder_charts.get('no_folder', [])
#     if no_folder_charts:
#         print("\nCharts ohne Ordnerzuordnung:")
#         print(f"Anzahl: {len(no_folder_charts)}")
        
#         for i, chart in enumerate(no_folder_charts[:5], 1):  # Zeige die ersten 5 Charts
#             chart_id = chart.get('id', 'Keine ID')
#             chart_title = chart.get('title', 'Kein Titel')
#             print(f"  {i}. {chart_title} (ID: {chart_id})")
        
#         if len(no_folder_charts) > 5:
#             print(f"  ... und {len(no_folder_charts) - 5} weitere Charts")

# if __name__ == "__main__":
#     main() 