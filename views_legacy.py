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
        data['results'].append({
            'chart_id': chart.chart_id,
            'title': chart.title,
            'description': chart.description,
            'notes': chart.notes,
            'comments': chart.comments,
            'thumbnail': chart.thumbnail.url if chart.thumbnail else '',
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
        response = requests.get(
            f"https://api.datawrapper.de/v3/charts/{chart_id}",
            headers=headers
        )
        response.raise_for_status()
        chart_data = response.json()
        
        # Extrahiere die Farbcodes aus den Metadaten
        colors = []
        metadata = chart_data.get('metadata', {})
        
        # Hole die Farben aus der color-category Map
        color_category = metadata.get('visualize', {}).get('color-category', {})
        color_map = color_category.get('map', {})
        
        # Füge alle Farben aus der Map hinzu
        for label, color in color_map.items():
            colors.append((label, color))
            
        # Hole die Dimensionen der Grafik
        dimensions = metadata.get('publish', {}).get('chart-dimensions', {})
        # Konvertiere Pixel in mm (bei 96 DPI)
        pixels_per_mm = 96 / 25.4  # 96 DPI zu mm Umrechnung
        width_px = dimensions.get('width', 600)
        height_px = dimensions.get('height', 400)
        width_mm = round(width_px / pixels_per_mm)  # Pixel in mm umrechnen
        height_mm = round(height_px / pixels_per_mm)  # Pixel in mm umrechnen
            
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
        
        # Debug: Print request data
        print("Request POST data:", request.POST)
        
        # 1. Grafik duplizieren
        duplicate_url = f"https://api.datawrapper.de/v3/charts/{chart_id}/copy"
        print(f"\n[API Call] Duplicate Chart:")
        print(f"URL: {duplicate_url}")
        print(f"Method: POST")
        print(f"Headers: {headers}")
        
        duplicate_response = requests.post(duplicate_url, headers=headers)
        duplicate_response.raise_for_status()
        new_chart_data = duplicate_response.json()
        new_chart_id = new_chart_data['id']
        print(f"Response: {new_chart_data}")
        print(f"Successfully duplicated chart. New ID: {new_chart_id}")
        
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
            'fullVector': 'false',
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

@csrf_exempt
def analyze_data(request):
    """Analysiert hochgeladene Datendateien mit OpenAI"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'Keine Datei gefunden'}, status=400)
            
        file = request.FILES['file']
        
        # Debug: Dateiinhalt prüfen
        content = file.read().decode('utf-8', errors='ignore')
        if not content.strip():
            return JsonResponse({'error': 'Die Datei ist leer'}, status=400)
            
        # Zeilen in Liste aufteilen
        lines = content.split('\n')
        
        # Suche nach dem tatsächlichen Datenanfang
        header_metadata = []
        data_start_index = 0
        
        # Sammle Metadaten am Anfang und finde den Datenbeginn
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line:  # Überspringe leere Zeilen
                continue
                
            # Prüfe, ob die Zeile vollständig gefüllt ist (keine leeren Felder)
            parts = [p.strip() for p in line.replace(';', ',').split(',')]
            if all(len(p) > 0 for p in parts) and len(parts) > 1:
                # Prüfe die nächsten Zeilen, ob sie das gleiche Format haben
                next_lines_valid = True
                for j in range(1, 3):  # Prüfe die nächsten 2 Zeilen
                    if i + j < len(lines):
                        next_line = lines[i + j].strip()
                        if next_line:
                            next_parts = [p.strip() for p in next_line.replace(';', ',').split(',')]
                            if len(next_parts) != len(parts) or not all(len(p) > 0 for p in next_parts):
                                next_lines_valid = False
                                break
                
                if next_lines_valid:
                    data_start_index = i
                    break
            
            # Sammle alle Zeilen vor dem Datenbeginn als Metadaten
            header_metadata.append(stripped_line)
        
        # Suche nach Fußnoten am Ende
        footer_metadata = []
        data_end_index = len(lines)
        
        for i in range(len(lines) - 1, data_start_index, -1):
            stripped_line = lines[i].strip()
            if not stripped_line:  # Überspringe leere Zeilen
                continue
            
            # Prüfe, ob die Zeile das gleiche Format wie die Datenzeilen hat
            parts = [p.strip() for p in stripped_line.replace(';', ',').split(',')]
            if len(parts) != len([p.strip() for p in lines[data_start_index].replace(';', ',').split(',')]):
                footer_metadata.insert(0, stripped_line)
            else:
                data_end_index = i + 1
                break
        
        # Extrahiere nur die Datenzeilen
        data_content = '\n'.join(lines[data_start_index:data_end_index])
        
        print(f"Gefundene Header-Metadaten:\n{header_metadata}")
        print(f"Gefundene Footer-Metadaten:\n{footer_metadata}")
        print(f"Datenbereich: Zeilen {data_start_index + 1} bis {data_end_index}")
        
        # Lese die Datei basierend auf dem Dateityp
        if file.name.endswith('.csv'):
            # Versuche verschiedene Trennzeichen und Encodings
            separators = [';', ',', '\t', '|']  # Setze ; an erste Stelle, da es häufiger vorkommt
            encodings = ['utf-8', 'latin1', 'cp1252']
            df = None
            error_messages = []
            
            for encoding in encodings:
                for sep in separators:
                    try:
                        # Lese nur die Datenzeilen
                        df = pd.read_csv(
                            pd.StringIO(data_content),
                            sep=sep,
                            encoding=encoding,
                            engine='python'
                        )
                        
                        print(f"Erfolgreich eingelesen mit Encoding {encoding} und Trennzeichen '{sep}'")
                        print(f"Gefundene Spalten: {list(df.columns)}")
                        
                        if len(df.columns) > 1:  # Mindestens 2 Spalten erwartet
                            break
                    except Exception as e:
                        error_messages.append(f"Versuch mit '{sep}' und {encoding}: {str(e)}")
                        
                if df is not None and len(df.columns) > 1:
                    break
            
            if df is None or len(df.columns) <= 1:
                return JsonResponse({
                    'error': f'Konnte die CSV-Datei nicht korrekt einlesen.\nDateiinhalt:\n{content[:500]}\n\nVersuche Trennzeichen: {", ".join(separators)}.\nFehler: {"; ".join(error_messages)}'
                }, status=400)
                
        elif file.name.endswith(('.xls', '.xlsx')):
            try:
                df = pd.read_excel(file)
            except Exception as e:
                return JsonResponse({
                    'error': f'Fehler beim Einlesen der Excel-Datei: {str(e)}'
                }, status=400)
        else:
            return JsonResponse({'error': 'Nicht unterstütztes Dateiformat'}, status=400)
            
        # Konvertiere die ersten paar Zeilen in einen String für die Analyse
        sample_data = df.head(5).to_string()
        
        # Initialisiere OpenAI Client
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Bereite den Kontext für GPT vor
        context = []
        if header_metadata:
            context.append("Metadaten am Dateianfang:\n" + "\n".join(header_metadata))
        if footer_metadata:
            context.append("Fußnoten am Dateiende:\n" + "\n".join(footer_metadata))
        context.append(f"Datenauszug:\n{sample_data}")
        
        # Sende Anfrage an OpenAI
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Du bist ein Datenanalyst. Analysiere den folgenden Datensatz und gib eine kurze, prägnante Einschätzung auf Deutsch."},
                {"role": "user", "content": "\n\n".join(context) + "\n\nGib eine kurze Einschätzung zum Aufbau und Inhalt des Datensatzes."}
            ]
        )
        
        analysis = response.choices[0].message.content
        
        return JsonResponse({
            'success': True,
            'analysis': analysis,
            'preview': df.head(5).to_dict('records'),
            'metadata': {
                'header': header_metadata,
                'footer': footer_metadata
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)