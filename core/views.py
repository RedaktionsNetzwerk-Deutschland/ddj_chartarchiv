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
from django.conf import settings
import datetime
import io
from django.contrib import messages

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

def topic_view(request, topic):
    """
    Zeigt eine thematische Übersicht mit vorgefiltertem Inhalt.
    Die Seite ist identisch zur Hauptarchivseite, aber mit einer vordefinierten Suche.
    """
    # Konvertiere den übergebenen Topic-Slug in einen lesbaren Text mit Grossbuchstaben am Anfang
    topic_display = topic.replace('-', ' ').capitalize()
    
    # Kontext mit dem Suchbegriff
    context = {
        'topic': topic,
        'topic_display': topic_display,
        'initial_search': topic_display  # Das ist der anfängliche Suchbegriff
    }
    
    return render(request, 'topic_view.html', context)

def chart_search(request):
    q = request.GET.get('q', '')
    page = int(request.GET.get('page', 0))
    items_per_page = 100  # Anzahl der Items pro Seite
    
    print(f"Debug: Suche nach '{q}' auf Seite {page}")
    
    if q:
        # Teile die Suchanfrage in einzelne Wörter auf
        search_terms = q.strip().split()
        
        if len(search_terms) > 1:
            # Bei mehreren Suchbegriffen AND-Verknüpfung verwenden
            # Beginne mit allen Objekten
            query = Q()
            
            # Initialisiere einen leeren Filter
            charts_queryset = Chart.objects.all()
            
            # Filtere nacheinander nach jedem Suchbegriff (AND-Verknüpfung)
            for term in search_terms:
                if len(term) > 2:  # Ignoriere sehr kurze Wörter
                    term_query = Q(chart_id__icontains=term) | \
                               Q(title__icontains=term) | \
                               Q(description__icontains=term) | \
                               Q(notes__icontains=term) | \
                               Q(comments__icontains=term) | \
                               Q(embed_js__icontains=term) | \
                               Q(tags__icontains=term)
                    # Filtere die Ergebnisse weiter (AND)
                    charts_queryset = charts_queryset.filter(term_query)
            
            total_count = charts_queryset.count()
            print(f"Debug: Gefundene Ergebnisse bei UND-Suche: {total_count}")
            # Paginierte Ergebnisse
            charts = charts_queryset.order_by('-published_date')[page*items_per_page:(page+1)*items_per_page]
        else:
            # Bei einem einzelnen Suchbegriff OR-Verknüpfung verwenden (wie bisher)
            query = Q(chart_id__icontains=q) | \
                    Q(title__icontains=q) | \
                    Q(description__icontains=q) | \
                    Q(notes__icontains=q) | \
                    Q(comments__icontains=q) | \
                    Q(embed_js__icontains=q) | \
                    Q(tags__icontains=q)
            
            total_count = Chart.objects.filter(query).count()
            print(f"Debug: Gefundene Ergebnisse bei ODER-Suche: {total_count}")
            # Paginierte Ergebnisse
            charts = Chart.objects.filter(query).order_by('-published_date')[page*items_per_page:(page+1)*items_per_page]
    else:
        total_count = Chart.objects.count()
        print(f"Debug: Gesamtanzahl aller Charts: {total_count}")
        # Paginierte Ergebnisse
        charts = Chart.objects.all().order_by('-published_date')[page*items_per_page:(page+1)*items_per_page]
    
    print(f"Debug: Anzahl der Charts in dieser Seite: {len(charts)}")
    
    results = []
    for chart in charts:
        # Verwende direkt das tags-Feld aus dem Modell
        results.append({
            'chart_id': chart.chart_id,
            'title': chart.title,
            'description': chart.description,
            'notes': chart.notes,
            'tags': chart.tags,  # Verwende direkt chart.tags
            'thumbnail': chart.thumbnail.url if chart.thumbnail else '',
            'published_date': chart.published_date.isoformat() if chart.published_date else None,
            'evergreen': chart.evergreen,
            'patch': chart.patch,
            'regional': chart.regional
        })
    
    data = {
        'results': results,
        'total_count': total_count,
        'has_more': (page + 1) * items_per_page < total_count
    }
    print(f"Debug: Sende {len(results)} Ergebnisse zurück")
    return JsonResponse(data)

def chart_detail(request, chart_id):
    chart = get_object_or_404(Chart, chart_id=chart_id)
    
    # Tags als Liste verarbeiten, wenn vorhanden
    if chart.tags:
        # Split tags and remove any whitespace
        tag_list = [tag.strip() for tag in chart.tags.split(',') if tag.strip()]
        context = {'chart': chart, 'tag_list': tag_list}
    else:
        context = {'chart': chart, 'tag_list': []}
    
    return render(request, 'chart_detail.html', context)

def chart_print(request, chart_id):
    chart = get_object_or_404(Chart, chart_id=chart_id)
    
    # Hole Farbcodes aus der Datawrapper-API
    api_key = os.getenv('DATAWRAPPER_API_KEY')
    
    if not api_key:
        # Fehlermeldung beibehalten
        print("WARNUNG: DATAWRAPPER_API_KEY nicht gefunden in Umgebungsvariablen")
        api_key = 'XXXXXXXX'  # Fallback nur wenn wirklich nötig
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        response = requests.get(
            f"https://api.datawrapper.de/v3/charts/{chart_id}",
            headers=headers
        )
        response.raise_for_status()
        chart_data = response.json()
        
        # Debug-Ausgabe für die Grafik-Metadaten
        print(f"DEBUG CHART {chart_id} TYPE: {chart_data.get('type', 'unknown')}")
        
        # Extrahiere die Farbcodes aus den Metadaten
        colors = []
        metadata = chart_data.get('metadata', {})
        visualize = metadata.get('visualize', {})
        
        # Debug-Ausgabe für die visualize-Sektion
        print(f"DEBUG VISUALIZE STRUCTURE: {json.dumps(visualize, indent=2)}")
        
        # 1. Prüfe auf Pie-Chart spezifische Farben
        if visualize.get('type') == 'pie-chart':
            pie_data = visualize.get('pie', {})
            
            pie_colors = pie_data.get('colors', [])
            if pie_colors:
                for i, color in enumerate(pie_colors):
                    colors.append((f'Segment {i+1}', color))
        
        # 2. Prüfe auf custom-colors
        custom_colors = visualize.get('custom-colors', {})
        if custom_colors:
            for label, color in custom_colors.items():
                colors.append((label, color))
        
        # 3. Prüfe auf color-category Map
        color_category = visualize.get('color-category', {})
        if color_category:
            color_map = color_category.get('map', {})
            for label, color in color_map.items():
                if color and isinstance(color, str):  # Prüfe ob der Farbwert gültig ist
                    colors.append((label, color))
        
        # 4. Prüfe auf base color
        base_color = visualize.get('base-color')
        if base_color:
            colors.append(('Base', base_color))
        
        # 5. Prüfe auf column colors
        columns = visualize.get('columns', {})
        if columns:
            for col_name, col_data in columns.items():
                if isinstance(col_data, dict) and 'color' in col_data:
                    colors.append((col_name, col_data['color']))
        
        # 6. Für Liniengrafiken: Prüfe auf Linienfarben in series
        series = visualize.get('series', {})
        if series:
            for series_name, series_data in series.items():
                if isinstance(series_data, dict) and 'color' in series_data:
                    colors.append((series_name, series_data['color']))
        
        # Hole die Dimensionen der Grafik
        dimensions = metadata.get('publish', {}).get('chart-dimensions', {})
        pixels_per_mm = 96 / 25.4  # 96 DPI zu mm Umrechnung
        width_px = dimensions.get('width', 600)
        height_px = dimensions.get('height', 400)
        width_mm = round(width_px / pixels_per_mm)
        height_mm = round(height_px / pixels_per_mm)
        
        # Debug-Ausgabe für die gefundenen Farben
        print(f"DEBUG FOUND COLORS: {colors}")
            
    except Exception as e:
        # Fehlermeldung beibehalten
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
        api_key = os.getenv('DATAWRAPPER_API_KEY')
        if not api_key:
            raise Exception("API Key nicht gefunden")
            
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # Hole alle Ordner
        folders_url = "https://api.datawrapper.de/v3/folders"
        
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
            for subfolder in rnd_folder['folders']:
                if subfolder.get('name') == 'printexport':
                    printexport_folder = subfolder
                    break
        
        # Erstelle printexport-Ordner falls nicht vorhanden
        if not printexport_folder:
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
        
        # Änderungen aus dem Request holen
        data = request.POST
        print("data:", data)
        
        # 1. Grafik duplizieren direkt in den printexport-Ordner
        duplicate_url = f"https://api.datawrapper.de/v3/charts/{chart_id}/copy"
        
        # Erstelle die Duplizierungsdaten mit dem Titel
        duplicate_data = {
            "folderId": printexport_folder['id'],
            "title": data.get('title', '')  # Setze den Titel direkt während der Duplizierung
        }
        print(duplicate_data)
        duplicate_response = requests.post(
            duplicate_url,
            headers={**headers, 'Content-Type': 'application/json'},
            json=duplicate_data
        )
        duplicate_response.raise_for_status()
        new_chart_data = duplicate_response.json()
        new_chart_id = new_chart_data['id']
        
        # Stelle sicher, dass der Titel korrekt gesetzt wurde
        if data.get('title'):
            print("Titel im Request:", data.get('title'))
            # Überprüfe den Titel und setze ihn nochmals, falls nötig
            check_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}"
            check_response = requests.get(check_url, headers=headers)
            check_response.raise_for_status()
            current_title = check_response.json().get('title', '')
            print("Aktueller Titel:", current_title)
            
            if current_title != data.get('title'):
                # Setze den Titel erneut, falls er nicht korrekt ist
                update_title_response = requests.patch(
                    check_url,
                    headers={**headers, 'Content-Type': 'application/json'},
                    json={"title": data.get('title')}
                )
                update_title_response.raise_for_status()
        
        # Duplicat wird in den printexport-Ordner geschrieben
        update_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}"
        update_data = {"folderId": printexport_folder['id']}
        update_response = requests.patch(update_url, headers=headers, json=update_data)
        update_response.raise_for_status()
        
        # 3. Weitere Änderungen aus dem Request holen
        properties_to_update = {}
            
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
            try:
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
            except (ValueError, TypeError) as e:
                print(f"Fehler bei der Konvertierung der Dimensionen: {e}")
                print(f"width_mm: {width_mm}, height_mm: {height_mm}")
                # Verwende Standardwerte bei Fehlern
                properties_to_update['metadata']['publish']['chart-dimensions'] = {
                    'width': 600,
                    'height': 400
                }
        
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
            except json.JSONDecodeError as e:
                # Fehlermeldung beibehalten
                print(f"Error decoding colors JSON: {e}")
                print("Raw colors data:", data.get('colors'))
        
        # 4. Grafik aktualisieren
        if properties_to_update:
            update_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}"
            
            update_response = requests.patch(
                update_url,
                headers={**headers, 'Content-Type': 'application/json'},
                json=properties_to_update
            )
            update_response.raise_for_status()
        
        # 5. Grafik publishen
        publish_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}/publish"
        
        publish_response = requests.post(publish_url, headers=headers)
        publish_response.raise_for_status()
        
        # 6. PDF exportieren mit den korrekten Parametern
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
        try:
            if width_mm:
                export_params['width'] = width_mm
            if height_mm:
                if height_mm == 'auto':
                    export_params['height'] = 'auto'  # Als String übergeben
                else:
                    export_params['height'] = height_mm
            else:
                export_params['height'] = 'auto'  # Standardmäßig auf "auto" setzen
        except Exception as e:
            print(f"Fehler beim Setzen der Export-Parameter: {e}")
            # Standardwerte für den Export verwenden
            export_params['width'] = '210'  # A4 Breite
            export_params['height'] = 'auto'
            
        export_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}/export/pdf"
        
        export_response = requests.get(
            export_url,
            headers=headers,
            params=export_params
        )
        export_response.raise_for_status()
        
        # PDF-Response erstellen
        pdf_response = HttpResponse(export_response.content, content_type='application/pdf')
        pdf_response['Content-Disposition'] = f'attachment; filename="chart_{new_chart_id}.pdf"'
        return pdf_response
        
    except Exception as e:
        # Fehlermeldung beibehalten
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
    """Analysiert hochgeladene Datendateien oder Chat-Nachrichten"""
    try:
        # Prüfe, ob OpenAI verwendet werden soll
        use_openai = os.getenv('OPENAI_API_KEY') is not None and os.getenv('USE_OPENAI', 'False').lower() == 'true'
        
        if request.content_type == 'application/json':
            # Chat-Nachricht verarbeiten
            data = json.loads(request.body)
            user_message = data.get('message')
            chartdata_id = data.get('chartdata_id')
            include_data = data.get('include_data', False)
            
            if not user_message:
                return JsonResponse({'error': 'Keine Nachricht gefunden'}, status=400)
            
            # Wenn Datensatz-ID und include_data gesetzt sind, lade den Datensatz
            if use_openai and chartdata_id and include_data:
                try:
                    from core.models import ChartData
                    
                    # Lade den Datensatz aus der Datenbank
                    chart_data = ChartData.objects.get(id=chartdata_id)
                    
                    # Extrahiere die rohen Daten
                    raw_data = chart_data.raw_data
                    
                    # Begrenze auf die ersten 300 Zeilen für die Analyse
                    lines = raw_data.split('\n')
                    limited_content = '\n'.join(lines[:300])
                    total_lines = len(lines)
                    
                    # Ergänze den Prompt mit den Daten für ChatGPT
                    enhanced_message = f"{user_message}\n\nHier sind die ersten 300 Zeilen des Datensatzes (von insgesamt {total_lines} Zeilen):\n\n{limited_content}"
                    
                    # Erstelle den client und sende die Anfrage
                    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "user", "content": enhanced_message}
                        ]
                    )
                    response_text = response.choices[0].message.content
                    
                    # Debug-Ausgabe
                    print(f"Datensatz gefunden und an ChatGPT gesendet (ID: {chartdata_id}, {total_lines} Zeilen)")
                    
                except ChartData.DoesNotExist:
                    return JsonResponse({'error': f'Datensatz mit ID {chartdata_id} nicht gefunden'}, status=404)
                except Exception as e:
                    print(f"Fehler beim Verarbeiten des Datensatzes: {str(e)}")
                    # Fallback zur normalen Verarbeitung
                    if use_openai:
                        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "user", "content": user_message}
                            ]
                        )
                        response_text = response.choices[0].message.content
                    else:
                        response_text = f"Ich habe deine Nachricht erhalten: {user_message}"
            else:
                # Standard-Verarbeitung ohne Datensatz
                if use_openai:
                    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "user", "content": user_message}
                        ]
                    )
                    response_text = response.choices[0].message.content
                else:
                    response_text = f"Ich habe deine Nachricht erhalten: {user_message}"
            
            return JsonResponse({
                'success': True,
                'response': response_text
            })
            
        elif 'file' in request.FILES or 'file' in request.POST:
            # Dateianalyse durchführen
            if 'file' in request.FILES:
                file = request.FILES['file']
                file_name = file.name
                file_type = file.name.split('.')[-1].lower() if '.' in file.name else 'unknown'
                
                # Prüfe, ob der Dateityp erlaubt ist
                allowed_file_types = ['csv', 'xlsx']
                if file_type not in allowed_file_types:
                    return JsonResponse({
                        'error': f'Dateityp nicht unterstützt. Bitte verwende CSV oder XLSX-Dateien.'
                    }, status=400)
                
                # Datei je nach Typ verarbeiten
                if file_type == 'csv':
                    # CSV-Datei direkt als Text lesen
                    content = file.read().decode('utf-8', errors='ignore')
                elif file_type == 'xlsx':
                    # Excel-Datei mit pandas lesen
                    try:
                        import pandas as pd
                        import io
                        
                        # Excel-Datei in DataFrame einlesen
                        excel_data = pd.read_excel(file)
                        
                        # DataFrame in CSV-String umwandeln
                        csv_buffer = io.StringIO()
                        excel_data.to_csv(csv_buffer, index=False)
                        content = csv_buffer.getvalue()
                    except Exception as e:
                        return JsonResponse({
                            'error': f'Fehler beim Verarbeiten der Excel-Datei: {str(e)}'
                        }, status=400)
            else:
                # Wenn die Daten als Teil des POST-Requests gesendet wurden
                content = request.POST.get('file', '')
                file_name = 'pasted_data.csv'
                file_type = 'csv'  # Annahme, dass eingefügte Daten CSV-Format haben
                
            if not content.strip():
                return JsonResponse({'error': 'Die Datei ist leer'}, status=400)
                
            # Begrenze den Inhalt auf die ersten 300 Zeilen für die Analyse
            lines = content.split('\n')
            limited_content = '\n'.join(lines[:300])
            total_lines = len(lines)
            
            # WICHTIG: Beim ersten Hochladen immer die einfache Analyse verwenden,
            # OpenAI erst bei explizitem Aufruf von deepAnalyzeData verwenden
            
            # Bestimme den Datensatztyp basierend auf den ersten Zeilen
            has_header = True
            delimiter = ',' if ',' in lines[0] else ('\t' if '\t' in lines[0] else ';')
            columns = []
            
            if lines and delimiter in lines[0]:
                columns = lines[0].split(delimiter)
            
            # Einfache Analyse erstellen
            metadata = ["Keine detaillierten Metadaten verfügbar."]
            
            data_analysis = [
                "Diese Daten scheinen in einem tabellarischen Format vorzuliegen.",
                f"Die Datei enthält {total_lines} Zeilen."
            ]
            
            if columns:
                data_analysis.append(f"Es wurden {len(columns)} Spalten erkannt: {', '.join(columns)}.")
            
            visualization_suggestions = [
                "Abhängig von den Daten könntest du folgende Visualisierungen erstellen:",
                "- Balkendiagramm für kategorische Vergleiche",
                "- Liniendiagramm für zeitliche Verläufe",
                "- Kreisdiagramm für prozentuale Anteile",
                "- Streudiagramm für Korrelationen zwischen zwei Variablen"
            ]
            
            footnotes = ["Hinweis: Diese Analyse wurde automatisch ohne KI-Unterstützung generiert."]
                
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
            
            # Speichere die Daten in der Datenbank
            from core.models import ChartData
            
            # Bestimme den Titel aus der Analyse oder dem Dateinamen
            data_title = file_name
            if data_analysis and len(data_analysis) > 0:
                # Versuche, einen aussagekräftigeren Titel aus der Analyse zu extrahieren
                first_sentence = data_analysis[0].strip()
                if len(first_sentence) > 10 and len(first_sentence) < 255:
                    data_title = first_sentence
            
            # Erstelle einen einfachen Analysetext
            analysis_text = "METADATEN:\n" + "\n".join(metadata) + "\n\nDATENANALYSE:\n" + "\n".join(data_analysis) + "\n\nVISUALISIERUNGSVORSCHLÄGE:\n" + "\n".join(visualization_suggestions) + "\n\nFUSSNOTEN:\n" + "\n".join(footnotes)
            
            # Speichere die Daten
            chart_data = ChartData.objects.create(
                title=data_title[:255],  # Beschränke auf max 255 Zeichen
                raw_data=content,
                analysis=analysis_text,
                header_metadata='\n'.join(metadata),
                footer_metadata='\n'.join(footnotes),
                file_type=file_type,
                created_by=request.user if request.user.is_authenticated else None
            )
            
            # Speichere die Datensatz-ID für die spätere Verwendung
            request.session['last_chartdata_id'] = chart_data.id
            
            return JsonResponse({
                'success': True,
                'analysis': complete_analysis,
                'chartdata_id': chart_data.id,
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

@csrf_exempt
def create_datawrapper_chart(request):
    """Erstellt eine neue Datawrapper-Grafik mit den gegebenen Parametern und Daten"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST-Anfragen werden unterstützt'}, status=405)
    
    try:
        # Daten aus dem Request auslesen
        data = json.loads(request.body)
        
        # Pflichtfelder prüfen
        required_fields = ['chart_type', 'chartdata_id']
        for field in required_fields:
            if field not in data:
                return JsonResponse({'error': f'Fehlendes Pflichtfeld: {field}'}, status=400)
        
        # Hole den Datawrapper API-Key
        api_key = os.getenv('DATAWRAPPER_API_KEY')
        if not api_key:
            return JsonResponse({'error': 'Datawrapper API-Key nicht gefunden'}, status=500)
        
        # Hole die ChartData aus der Datenbank
        from core.models import ChartData
        try:
            chart_data = ChartData.objects.get(id=data['chartdata_id'])
            raw_data = chart_data.raw_data
        except ChartData.DoesNotExist:
            return JsonResponse({'error': f'Datensatz mit ID {data["chartdata_id"]} nicht gefunden'}, status=404)
        
        # Erstelle die Header für die API-Anfragen
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # 1. Schritt: Erstelle eine neue Grafik
        create_chart_url = 'https://api.datawrapper.de/v3/charts'
        chart_params = {
            'type': data['chart_type'],
            'title': data.get('title', 'Neue Grafik'),  # Standard-Titel falls keiner angegeben
            'theme': 'datawrapper',  # Standard-Theme
            'language': 'de-DE',  # Deutsche Sprache
            'folderId': '309331'  # chartmaker-Unterordner im RND-Team
        }
        
        create_response = requests.post(
            create_chart_url,
            headers=headers,
            json=chart_params
        )
        create_response.raise_for_status()
        chart_info = create_response.json()
        chart_id = chart_info['id']
        
        print(f"Neue Grafik erstellt mit ID: {chart_id}")
        
        # 2. Schritt: Aktualisiere die Metadaten
        metadata = {
            'metadata': {
                'describe': {
                    'intro': data.get('subtitle', ''),
                    'byline': data.get('byline', ''),
                    'source-name': data.get('source_name', ''),
                    'source-url': data.get('source_url', '')
                }
            }
        }
        
        if data.get('tags'):
            metadata['metadata']['data'] = {
                'custom-metadata': {
                    'tags': data.get('tags', '')
                }
            }
        
        update_url = f'https://api.datawrapper.de/v3/charts/{chart_id}'
        update_response = requests.patch(
            update_url,
            headers=headers,
            json=metadata
        )
        update_response.raise_for_status()
        
        print(f"Metadaten aktualisiert für Grafik: {chart_id}")
        
        # 3. Schritt: Lade die Daten hoch
        data_url = f'https://api.datawrapper.de/v3/charts/{chart_id}/data'
        data_response = requests.put(
            data_url,
            headers={'Authorization': f'Bearer {api_key}'},
            data=raw_data
        )
        data_response.raise_for_status()
        
        print(f"Daten hochgeladen für Grafik: {chart_id}")
        
        # 4. Schritt: Veröffentliche die Grafik
        publish_url = f'https://api.datawrapper.de/v3/charts/{chart_id}/publish'
        publish_response = requests.post(publish_url, headers=headers)
        publish_response.raise_for_status()
        
        print(f"Grafik veröffentlicht: {chart_id}")
        
        # Erstelle eine Erfolgsmeldung mit allen relevanten Informationen
        result = {
            'success': True,
            'chart_id': chart_id,
            'title': chart_info['title'],
            'url': f'https://app.datawrapper.de/chart/{chart_id}/visualize'
        }
        
        return JsonResponse(result)
        
    except requests.exceptions.RequestException as e:
        print(f"API-Fehler: {str(e)}")
        error_message = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_message = error_data.get('message', str(e))
            except:
                error_message = e.response.text or str(e)
        
        return JsonResponse({'error': f'Datawrapper API-Fehler: {error_message}'}, status=500)
    except Exception as e:
        print(f"Unerwarteter Fehler: {str(e)}")
        return JsonResponse({'error': f'Unerwarteter Fehler: {str(e)}'}, status=500)