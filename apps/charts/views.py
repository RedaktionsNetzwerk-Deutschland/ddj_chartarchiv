"""
Views für die Charts-App.
Enthält alle View-Funktionen für die Verwaltung von Grafiken.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.contrib import messages
from .services.chart_service import ChartService
from .services.datawrapper import DatawrapperAPIError
import requests

chart_service = ChartService()

def archive_main(request):
    """
    Hauptseite des Archivs.
    Zeigt eine Liste aller Grafiken an.
    """
    return render(request, 'charts/archive_main.html')

def chart_search(request):
    """
    API-Endpunkt für die Grafiksuche.
    Unterstützt Textsuche, Tag-Filter und Pagination.
    """
    # Parameter aus Request holen
    query = request.GET.get('q', '')
    tags = request.GET.getlist('tags')
    is_published = request.GET.get('published')
    is_archived = request.GET.get('archived')
    limit = int(request.GET.get('limit', 100))
    offset = int(request.GET.get('offset', 0))
    
    # Boolean-Parameter konvertieren
    if is_published is not None:
        is_published = is_published.lower() == 'true'
    if is_archived is not None:
        is_archived = is_archived.lower() == 'true'
    
    try:
        # Suche durchführen
        result = chart_service.search_charts(
            query=query,
            tags=tags,
            is_published=is_published,
            is_archived=is_archived,
            limit=limit,
            offset=offset
        )
        
        # Ergebnisse formatieren
        data = {
            'results': [
                {
                    'chart_id': chart.chart_id,
                    'title': chart.title,
                    'description': chart.description,
                    'notes': chart.notes,
                    'tags': chart.get_tags_list(),
                    'thumbnail': chart.thumbnail.url if chart.thumbnail else None,
                    'published_date': chart.published_date.isoformat() if chart.published_date else None,
                    'is_published': chart.is_published,
                    'is_archived': chart.is_archived
                }
                for chart in result['results']
            ],
            'total_count': result['total_count'],
            'limit': result['limit'],
            'offset': result['offset']
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def chart_detail(request, chart_id):
    """
    Detailansicht einer Grafik.
    Zeigt alle Informationen zu einer spezifischen Grafik an.
    """
    try:
        chart = chart_service.get_chart(chart_id)
        return render(request, 'charts/chart_detail.html', {'chart': chart})
        
    except Exception as e:
        messages.error(request, f"Fehler beim Laden der Grafik: {str(e)}")
        return redirect('archive_main')

def chart_print(request, chart_id):
    """
    Druckansicht einer Grafik.
    Zeigt eine für den Druck optimierte Version der Grafik an.
    """
    try:
        chart = chart_service.get_chart(chart_id)
        
        # Hole Metadaten von Datawrapper
        dw_chart = chart_service.datawrapper.get_chart(chart_id)
        
        # Extrahiere Farbinformationen
        colors = []
        metadata = dw_chart.get('metadata', {})
        visualize = metadata.get('visualize', {})
        
        # Farben aus verschiedenen Quellen extrahieren
        if visualize.get('type') == 'pie-chart':
            pie_colors = visualize.get('pie', {}).get('colors', [])
            colors.extend((f'Segment {i+1}', color) for i, color in enumerate(pie_colors))
        
        custom_colors = visualize.get('custom-colors', {})
        colors.extend(custom_colors.items())
        
        color_category = visualize.get('color-category', {}).get('map', {})
        colors.extend(color_category.items())
        
        base_color = visualize.get('base-color')
        if base_color:
            colors.append(('Base', base_color))
        
        # Dimensionen berechnen
        dimensions = metadata.get('publish', {}).get('chart-dimensions', {})
        pixels_per_mm = 96 / 25.4  # 96 DPI zu mm Umrechnung
        width_px = dimensions.get('width', 600)
        height_px = dimensions.get('height', 400)
        width_mm = round(width_px / pixels_per_mm)
        height_mm = round(height_px / pixels_per_mm)
        
        context = {
            'chart': chart,
            'colors': colors,
            'width': width_mm,
            'height': height_mm
        }
        
        return render(request, 'charts/chart_print.html', context)
        
    except Exception as e:
        messages.error(request, f"Fehler beim Laden der Druckansicht: {str(e)}")
        return redirect('chart_detail', chart_id=chart_id)

@login_required
def export_chart_pdf(request, chart_id):
    """
    Exportiert eine Grafik als PDF.
    """
    try:
        # PDF von Datawrapper exportieren
        pdf_content = chart_service.export_chart(
            chart_id,
            format='pdf',
            params={
                'unit': 'mm',
                'mode': 'rgb',
                'scale': '1',
                'zoom': '1'
            }
        )
        
        # PDF-Response erstellen
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="chart_{chart_id}.pdf"'
        return response
        
    except Exception as e:
        messages.error(request, f"Fehler beim PDF-Export: {str(e)}")
        return redirect('chart_detail', chart_id=chart_id)

@login_required
@csrf_exempt
def duplicate_and_export_chart(request, chart_id):
    """
    Dupliziert eine Grafik und exportiert sie als PDF.
    """
    try:
        # Parameter aus Request holen
        data = request.POST.dict()
        
        # Hole alle Ordner
        folders_url = "https://api.datawrapper.de/v3/folders"
        headers = {
            "Authorization": f"Bearer {chart_service.datawrapper.api_key}",
            "Content-Type": "application/json"
        }
        
        folders_response = requests.get(folders_url, headers=headers)
        folders_response.raise_for_status()
        folders = folders_response.json().get('list', [])
        
        def print_folder_structure(folders, level=0):
            """Gibt die Ordnerstruktur übersichtlich aus"""
            for folder in folders:
                indent = "  " * level
                folder_id = folder.get('id', 'NO_ID')
                folder_name = folder.get('name', 'NO_NAME')
                print(f"{indent}[{folder_id}] {folder_name}")
                
                if 'folders' in folder:
                    print_folder_structure(folder['folders'], level + 1)
        
        # Debug: Gib die vollständige Ordnerstruktur aus
        print("\n=== Datawrapper Ordnerstruktur ===")
        print_folder_structure(folders)
        print("================================\n")
        
        # Rekursive Funktion zum Durchsuchen der Ordnerstruktur
        def find_nested_folder(folders, path):
            """
            Sucht einen Ordner basierend auf einem Pfad (z.B. ['Fam', 'RND', 'printexport'])
            """
            current_name = path[0].lower()
            
            for folder in folders:
                folder_name = folder.get('name', '').lower()
                if folder_name == current_name:
                    if len(path) == 1:
                        return folder
                    # Suche in Unterordnern weiter
                    if 'folders' in folder:
                        result = find_nested_folder(folder['folders'], path[1:])
                        if result:
                            return result
                # Suche auch in allen Unterordnern des aktuellen Ordners
                if 'folders' in folder:
                    result = find_nested_folder(folder['folders'], path)
                    if result:
                        return result
            return None

        # Suche den printexport-Ordner im Pfad Fam/RND/printexport
        folder_path = ['Fam', 'RND', 'printexport']
        printexport_folder = find_nested_folder(folders, folder_path)
        
        if not printexport_folder:
            raise ValidationError(f"Printexport-Ordner nicht gefunden im Pfad {'/'.join(folder_path)}")
            
        # Grafik direkt in den Zielordner kopieren
        copy_url = f"https://api.datawrapper.de/v3/charts/{chart_id}/copy"
        copy_data = {
            "folderId": printexport_folder['id']
        }
        
        print(f"Kopiere Grafik in Ordner: {printexport_folder['id']}")
        copy_response = requests.post(copy_url, headers=headers, json=copy_data)
        copy_response.raise_for_status()
        new_chart = copy_response.json()
        new_chart_id = new_chart['id']
        
        # Eigenschaften aktualisieren
        update_data = {}
        
        if data.get('title'):
            update_data['title'] = data['title']
        if data.get('description'):
            if 'metadata' not in update_data:
                update_data['metadata'] = {}
            update_data['metadata']['describe'] = {
                'intro': data['description']
            }
        
        # Dimensionen aktualisieren
        width_mm = data.get('width')
        height_mm = data.get('height')
        if width_mm or height_mm:
            if 'metadata' not in update_data:
                update_data['metadata'] = {}
            if 'publish' not in update_data['metadata']:
                update_data['metadata']['publish'] = {}
            
            # Konvertiere mm in Pixel
            pixels_per_mm = 96 / 25.4
            width_px = round(float(width_mm) * pixels_per_mm) if width_mm else None
            height_px = round(float(height_mm) * pixels_per_mm) if height_mm and height_mm != 'auto' else 'auto'
            
            update_data['metadata']['publish']['chart-dimensions'] = {
                'width': width_px,
                'height': height_px
            }
        
        # Farben aktualisieren
        if data.get('colors'):
            import json
            colors = json.loads(data['colors'])
            if 'metadata' not in update_data:
                update_data['metadata'] = {}
            if 'visualize' not in update_data['metadata']:
                update_data['metadata']['visualize'] = {}
            update_data['metadata']['visualize']['color-category'] = {
                'map': colors
            }
        
        # Grafik aktualisieren wenn nötig
        if update_data:
            update_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}"
            update_response = requests.patch(update_url, headers=headers, json=update_data)
            update_response.raise_for_status()
        
        # Grafik veröffentlichen
        publish_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}/publish"
        publish_response = requests.post(publish_url, headers=headers)
        publish_response.raise_for_status()
        
        # PDF exportieren
        export_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}/export/pdf"
        export_params = {
            'unit': 'mm',
            'mode': 'rgb',
            'scale': '0.7',
            'zoom': '1',
            'download': 'false',
            'fullVector': 'false',
            'ligatures': 'true',
            'transparent': 'true',
            'logo': 'auto',
            'dark': 'false'
        }
        
        export_response = requests.get(export_url, headers=headers, params=export_params)
        export_response.raise_for_status()
        
        # PDF-Response erstellen
        response = HttpResponse(export_response.content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="chart_{new_chart_id}.pdf"'
        return response
        
    except Exception as e:
        error_msg = str(e)
        if isinstance(e, requests.exceptions.RequestException) and hasattr(e, 'response'):
            error_msg = f"{error_msg} - API Response: {e.response.text}"
        return JsonResponse({'error': error_msg}, status=500) 