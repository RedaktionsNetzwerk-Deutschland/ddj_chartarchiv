from django.shortcuts import render, redirect, get_object_or_404
from .forms import RegistrationForm
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from .models import Chart
import os
import requests
from openai import OpenAI
import pandas as pd
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth.decorators import login_required

# Create your views here.

def index(request):
    return render(request, 'index.html')

def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('index')
    else:
        form = RegistrationForm()
    return render(request, 'register.html', {'form': form})

def archive_main(request):
    return render(request, 'archive_main.html')

def chart_search(request):
    q = request.GET.get('q', '')
    print(f"Suchbegriff: {q}")  # Debug-Ausgabe
    data = {'results': [], 'total_count': 0}
    
    if q:
        # Erweiterte Suche über alle relevanten Textfelder
        query = Q(chart_id__icontains=q) | \
                Q(title__icontains=q) | \
                Q(description__icontains=q) | \
                Q(notes__icontains=q) | \
                Q(comments__icontains=q) | \
                Q(embed_js__icontains=q)
        
        total_count = Chart.objects.filter(query).count()
        print(f"Gefundene Einträge: {total_count}")  # Debug-Ausgabe
        
        charts = Chart.objects.filter(query).order_by('-published_date')[:100]
        print(f"Abgerufene Charts: {len(charts)}")  # Debug-Ausgabe
    else:
        total_count = Chart.objects.count()
        print(f"Gesamtanzahl Charts: {total_count}")  # Debug-Ausgabe
        charts = Chart.objects.all().order_by('-published_date')[:100]
    
    for chart in charts:
        # Debug-Ausgabe des Datums
        print(f"Chart {chart.chart_id} Datum: {chart.published_date}")
        
        # Extrahiere Tags aus den Custom Fields
        tags = []
        try:
            comments_lines = chart.comments.split('\n')
            for line in comments_lines:
                if line.startswith('tags:'):
                    tags = line.replace('tags:', '').strip()
                    break
        except:
            tags = ''
        
        data['results'].append({
            'chart_id': chart.chart_id,
            'title': chart.title,
            'description': chart.description,
            'notes': chart.notes,
            'tags': tags,  # Nur die Tags statt der kompletten Comments
            'thumbnail': chart.thumbnail.url if chart.thumbnail else '',
            'published_date': chart.published_date.isoformat() if chart.published_date else None
        })
    
    data['total_count'] = total_count
    print(f"Zurückgegebene Daten: {len(data['results'])} Einträge")  # Debug-Ausgabe
    return JsonResponse(data)

def chart_detail(request, chart_id):
    chart = get_object_or_404(Chart, chart_id=chart_id)
    return render(request, 'chart_detail.html', {'chart': chart})

def chart_print(request, chart_id):
    chart = get_object_or_404(Chart, chart_id=chart_id)
    
    # Hole Farbcodes aus der Datawrapper-API
    api_key = os.getenv('DATAWRAPPER_API_KEY')
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        print(f"\n[DEBUG] Requesting data for chart {chart_id}")
        
        response = requests.get(
            f"https://api.datawrapper.de/v3/charts/{chart_id}",
            headers=headers
        )
        response.raise_for_status()
        chart_data = response.json()
        
        # Debug-Ausgabe der vollständigen API-Antwort
        print("\n[DEBUG] Complete API Response:")
        print(json.dumps(chart_data, indent=2))
        
        # Extrahiere die Farbcodes aus den Metadaten
        colors = []
        metadata = chart_data.get('metadata', {})
        visualize = metadata.get('visualize', {})
        
        print(f"\n[DEBUG] Chart type: {visualize.get('type')}")
        print(f"\n[DEBUG] Visualize section:")
        print(json.dumps(visualize, indent=2))
        
        # 1. Prüfe auf Pie-Chart spezifische Farben
        if visualize.get('type') == 'pie-chart':
            pie_data = visualize.get('pie', {})
            print(f"\n[DEBUG] Pie chart data:")
            print(json.dumps(pie_data, indent=2))
            
            pie_colors = pie_data.get('colors', [])
            if pie_colors:
                print(f"[DEBUG] Found pie colors: {pie_colors}")
                for i, color in enumerate(pie_colors):
                    colors.append((f'Segment {i+1}', color))
        
        # 2. Prüfe auf custom-colors
        custom_colors = visualize.get('custom-colors', {})
        if custom_colors:
            print(f"\n[DEBUG] Found custom colors:")
            print(json.dumps(custom_colors, indent=2))
            for label, color in custom_colors.items():
                colors.append((label, color))
        
        # 3. Prüfe auf color-category Map
        color_category = visualize.get('color-category', {})
        if color_category:
            print(f"\n[DEBUG] Found color category:")
            print(json.dumps(color_category, indent=2))
            color_map = color_category.get('map', {})
            for label, color in color_map.items():
                if color and isinstance(color, str):  # Prüfe ob der Farbwert gültig ist
                    colors.append((label, color))
                    print(f"[DEBUG] Added color: {label} -> {color}")
        
        # 4. Prüfe auf base color
        base_color = visualize.get('base-color')
        if base_color:
            print(f"\n[DEBUG] Found base color: {base_color}")
            colors.append(('Base', base_color))
        
        # 5. Prüfe auf column colors
        columns = visualize.get('columns', {})
        if columns:
            print(f"\n[DEBUG] Found column colors:")
            print(json.dumps(columns, indent=2))
            for col_name, col_data in columns.items():
                if isinstance(col_data, dict) and 'color' in col_data:
                    colors.append((col_name, col_data['color']))
                    print(f"[DEBUG] Added column color: {col_name} -> {col_data['color']}")
            
        print(f"\n[DEBUG] Final Colors List: {colors}")
        
        # Hole die Dimensionen der Grafik
        dimensions = metadata.get('publish', {}).get('chart-dimensions', {})
        pixels_per_mm = 96 / 25.4  # 96 DPI zu mm Umrechnung
        width_px = dimensions.get('width', 600)
        height_px = dimensions.get('height', 400)
        width_mm = round(width_px / pixels_per_mm)
        height_mm = round(height_px / pixels_per_mm)
            
    except Exception as e:
        print(f"Fehler beim Abrufen der Daten: {e}")
        colors = []
        width_mm = 210  # Standard A4 Breite in mm
        height_mm = 148  # Standard A4 Höhe (quer) in mm
    
    context = {
        'chart': chart,
        'colors': colors,
        'width': width_mm,
        'height': height_mm
    }
    
    return render(request, 'chart_print.html', context)

def export_chart_pdf(request, chart_id):
    """Exportiert eine Grafik als PDF über die Datawrapper-API"""
    try:
        api_key = os.getenv('DATAWRAPPER_API_KEY')
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # PDF von Datawrapper abrufen
        response = requests.get(
            f"https://api.datawrapper.de/v3/charts/{chart_id}/export/pdf",
            headers=headers
        )
        response.raise_for_status()
        
        # PDF-Response erstellen
        pdf_response = HttpResponse(response.content, content_type='application/pdf')
        pdf_response['Content-Disposition'] = f'attachment; filename="chart_{chart_id}.pdf"'
        return pdf_response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def duplicate_and_export_chart(request, chart_id):
    """Dupliziert eine Grafik, aktualisiert sie und exportiert sie als PDF"""
    try:
        print(f"Starting duplicate process for chart {chart_id}")
        api_key = os.getenv('DATAWRAPPER_API_KEY')
        if not api_key:
            raise Exception("API Key nicht gefunden")
            
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # Hole alle Ordner
        folders_url = "https://api.datawrapper.de/v3/folders"
        print(f"\n[API Call] Get Folders:")
        print(f"URL: {folders_url}")
        print(f"Method: GET")
        
        folders_response = requests.get(folders_url, headers=headers)
        folders_response.raise_for_status()
        folders = folders_response.json().get('list', [])
        
        # Suche den RND-Ordner
        rnd_folder = None
        for folder in folders:
            if folder.get('name') == 'RND':
                rnd_folder = folder
                break
                
        if not rnd_folder:
            raise Exception("RND-Ordner nicht gefunden")
            
        # Suche den printexport-Ordner in RND
        printexport_folder = None
        if 'folders' in rnd_folder:
            print("..............................")
            
            for subfolder in rnd_folder['folders']:
                print(subfolder)
                if subfolder.get('name') == 'printexport':
                    printexport_folder = subfolder
                    break
        
        # Erstelle printexport-Ordner falls nicht vorhanden
        if not printexport_folder:
            print("\n[API Call] Create printexport folder")
            create_folder_url = "https://api.datawrapper.de/v3/folders"
            create_folder_data = {
                "name": "printexport",
                "parentId": rnd_folder['id']
            }
            create_response = requests.post(
                create_folder_url,
                headers={**headers, 'Content-Type': 'application/json'},
                json=create_folder_data
            )
            create_response.raise_for_status()
            printexport_folder = create_response.json()
            print(f"Created printexport folder with ID: {printexport_folder['id']}")
        
        # Debug: Print request data
        print("Request POST data:", request.POST)
        
        # 1. Grafik duplizieren direkt in den printexport-Ordner
        duplicate_url = f"https://api.datawrapper.de/v3/charts/{chart_id}/copy"
        print(f"\n[API Call] Duplicate Chart:")
        print(f"URL: {duplicate_url}")
        print(f"Method: POST")
        print(f"Headers: {headers}")
        
        duplicate_data = {"folderId": printexport_folder['id']}
       
        duplicate_response = requests.post(
            duplicate_url,
            headers={**headers, 'Content-Type': 'application/json'},
            json=duplicate_data
        )
        duplicate_response.raise_for_status()
        new_chart_data = duplicate_response.json()
        new_chart_id = new_chart_data['id']
        print(f"Response: {new_chart_data}")
        print(f"Successfully duplicated chart. New ID: {new_chart_id}")
        
        # Duplicat wird in den printexport-Ordner geschrieben
        update_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}"
        update_data = {"folderId": printexport_folder['id']}
        update_response = requests.patch(update_url, headers=headers, json=update_data)
        update_response.raise_for_status()

        
        
        # 2. Änderungen aus dem Request holen
        data = request.POST
        properties_to_update = {}
        
        if data.get('title'):
            properties_to_update['title'] = data.get('title')
        if data.get('description'):
            properties_to_update['metadata'] = {
                'describe': {
                    'intro': data.get('description')
                }
            }
            
        # Dimensionen aktualisieren (mm zu Pixel konvertieren für die Grafik-Metadaten)
        width_mm = data.get('width')
        height_mm = data.get('height')
        pixels_per_mm = 96 / 25.4  # 96 DPI zu mm Umrechnung
        
        if width_mm or height_mm:
            if 'metadata' not in properties_to_update:
                properties_to_update['metadata'] = {}
            if 'publish' not in properties_to_update['metadata']:
                properties_to_update['metadata']['publish'] = {}
                
            # Konvertiere mm in Pixel für die Grafik-Dimensionen
            width_px = round(float(width_mm) * pixels_per_mm) if width_mm else 600
            
            # Behandle "auto" für die Höhe
            if height_mm == 'auto':
                height_px = 'auto'
            else:
                height_px = round(float(height_mm) * pixels_per_mm) if height_mm else 400
            
            properties_to_update['metadata']['publish']['chart-dimensions'] = {
                'width': width_px,
                'height': height_px
            }
            print(f"Updated dimensions: {width_mm}mm x {height_mm}mm -> {width_px}px x {height_px}px")
            
        # Farben aktualisieren
        if data.get('colors'):
            try:
                import json
                colors = json.loads(data.get('colors'))
                if 'metadata' not in properties_to_update:
                    properties_to_update['metadata'] = {}
                if 'visualize' not in properties_to_update['metadata']:
                    properties_to_update['metadata']['visualize'] = {}
                properties_to_update['metadata']['visualize']['color-category'] = {
                    'map': colors
                }
                print("Updated colors:", colors)
            except json.JSONDecodeError as e:
                print(f"Error decoding colors JSON: {e}")
                print("Raw colors data:", data.get('colors'))
        
        # 3. Grafik aktualisieren
        if properties_to_update:
            update_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}"
            print(f"\n[API Call] Update Chart:")
            print(f"URL: {update_url}")
            print(f"Method: PATCH")
            print(f"Headers: {headers}")
            print(f"Data: {properties_to_update}")
            
            update_response = requests.patch(
                update_url,
                headers={**headers, 'Content-Type': 'application/json'},
                json=properties_to_update
            )
            update_response.raise_for_status()
            print(f"Response: {update_response.json()}")
        
        # 4. Grafik publishen
        publish_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}/publish"
        print(f"\n[API Call] Publish Chart:")
        print(f"URL: {publish_url}")
        print(f"Method: POST")
        print(f"Headers: {headers}")
        
        publish_response = requests.post(publish_url, headers=headers)
        publish_response.raise_for_status()
        print(f"Response: {publish_response.json()}")
        
        # 5. PDF exportieren mit den korrekten Parametern
        export_params = {
            'unit': 'mm',  # Einheit auf mm setzen
            'mode': 'rgb',
            'plain': 'false',
            'scale': '0.7',   # Auf 0.7 für kleinere Schriftgröße
            'zoom': '1',    # Auf 1 für konsistente Schriftgröße
            'download': 'false',
            'fullVector': 'true',
            'ligatures': 'true',
            'transparent': 'true',
            'logo': 'auto',
            'dark': 'false'
        }
        
        # Füge Dimensionen in mm hinzu
        if width_mm:
            export_params['width'] = width_mm
        if height_mm:
            if height_mm == 'auto':
                export_params['height'] = 'auto'  # Als String übergeben
            else:
                export_params['height'] = height_mm
        else:
            export_params['height'] = 'auto'  # Standardmäßig auf "auto" setzen
            
        export_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}/export/pdf"
        print(f"\n[API Call] Export PDF:")
        print(f"URL: {export_url}")
        print(f"Method: GET")
        print(f"Headers: {headers}")
        print(f"Parameters: {export_params}")
        
        # Detaillierte Debug-Ausgabe des API-Calls
        print("\n[Vollständiger API-Call]")
        print("curl -X GET \\")
        print(f"  '{export_url}' \\")
        headers_str = '\n'.join([f"  -H '{k}: {v}' \\" for k, v in headers.items()])
        print(headers_str)
        params_str = '&'.join([f"{k}={v}" for k, v in export_params.items()])
        print(f"  '?{params_str}'")
        
        export_response = requests.get(
            export_url,
            headers=headers,
            params=export_params
        )
        export_response.raise_for_status()
        print("\n[API Response Status]:", export_response.status_code)
        print("PDF export successful")
        
        # PDF-Response erstellen
        pdf_response = HttpResponse(export_response.content, content_type='application/pdf')
        pdf_response['Content-Disposition'] = f'attachment; filename="chart_{new_chart_id}.pdf"'
        return pdf_response
        
    except Exception as e:
        print(f"Error during export process: {str(e)}")
        if isinstance(e, requests.exceptions.RequestException) and hasattr(e.response, 'text'):
            print(f"API response: {e.response.text}")
        return JsonResponse({'error': str(e)}, status=500)

def chartmaker(request):
    """View für den Chartmaker"""
    return render(request, 'chartmaker.html')

def databuddies(request):
    """View für die Databuddies-Seite"""
    return render(request, 'databuddies.html')

@csrf_exempt
def analyze_data(request):
    """Analysiert hochgeladene Datendateien oder Chat-Nachrichten mit OpenAI"""
    try:
        # Initialisiere OpenAI Client
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        if request.content_type == 'application/json':
            # Chat-Nachricht verarbeiten
            data = json.loads(request.body)
            user_message = data.get('message')
            
            if not user_message:
                return JsonResponse({'error': 'Keine Nachricht gefunden'}, status=400)
            
            # Sende Anfrage an OpenAI
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            return JsonResponse({
                'success': True,
                'response': response.choices[0].message.content
            })
            
        elif 'file' in request.FILES:
            # Dateianalyse durchführen
            file = request.FILES['file']
            
            # Lese den Dateiinhalt
            content = file.read().decode('utf-8', errors='ignore')
            if not content.strip():
                return JsonResponse({'error': 'Die Datei ist leer'}, status=400)
                
            # Begrenze den Inhalt auf die ersten 300 Zeilen
            lines = content.split('\n')
            limited_content = '\n'.join(lines[:300])
            total_lines = len(lines)
            
            # Sende Anfrage an OpenAI
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """Du bist ein Datenanalyst. Bitte untersuche den Datensatz und gib eine kurze Einschätzung ab. 
                    Verrate mir:
                    1. Um was für Daten es sich handelt
                    2. Wie sie aufgebaut sind
                    3. Was man damit für Grafiken machen könnte
                    
                    Gib deine Antwort in folgendem Format:
                    METADATEN: [Liste der gefundenen Metadaten am Anfang]
                    DATENANALYSE: [Beschreibung der Daten und ihrer Struktur]
                    VISUALISIERUNGSVORSCHLÄGE: [Vorschläge für mögliche Grafiken]
                    FUSSNOTEN: [Liste der gefundenen Fußnoten]
                    """},
                    {"role": "user", "content": f"Hier sind die ersten 300 Zeilen des Datensatzes (von insgesamt {total_lines} Zeilen):\n\n{limited_content}"}
                ]
            )
            
            analysis = response.choices[0].message.content
            
            # Extrahiere die verschiedenen Teile aus der Analyse
            parts = analysis.split('\n')
            metadata = []
            data_analysis = []
            visualization_suggestions = []
            footnotes = []
            
            current_section = None
            for part in parts:
                if part.startswith('METADATEN:'):
                    current_section = 'metadata'
                    continue
                elif part.startswith('DATENANALYSE:'):
                    current_section = 'analysis'
                    continue
                elif part.startswith('VISUALISIERUNGSVORSCHLÄGE:'):
                    current_section = 'visualization'
                    continue
                elif part.startswith('FUSSNOTEN:'):
                    current_section = 'footnotes'
                    continue
                    
                if part.strip() and current_section == 'metadata':
                    metadata.append(part.strip())
                elif part.strip() and current_section == 'analysis':
                    data_analysis.append(part.strip())
                elif part.strip() and current_section == 'visualization':
                    visualization_suggestions.append(part.strip())
                elif part.strip() and current_section == 'footnotes':
                    footnotes.append(part.strip())
            
            # Erstelle Warnungen basierend auf der Dateigröße
            warnings = []
            if total_lines > 300:
                warnings.append({
                    'type': 'info',
                    'message': f'Die Analyse basiert auf den ersten 300 von insgesamt {total_lines} Zeilen'
                })
            if total_lines > 1000:
                warnings.append({
                    'type': 'warning',
                    'message': 'Dies ist ein sehr großer Datensatz. Bitte prüfen Sie die Datenstruktur in den nicht analysierten Zeilen manuell.'
                })
            
            # Kombiniere Analyse und Visualisierungsvorschläge
            complete_analysis = '\n'.join(data_analysis)
            if visualization_suggestions:
                complete_analysis += '\n\nVisualisierungsvorschläge:\n' + '\n'.join(visualization_suggestions)
            
            return JsonResponse({
                'success': True,
                'analysis': complete_analysis,
                'metadata': {
                    'header': metadata,
                    'footer': footnotes
                },
                'warnings': warnings
            })
        else:
            return JsonResponse({'error': 'Keine Datei oder Nachricht gefunden'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)