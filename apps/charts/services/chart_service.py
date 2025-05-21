"""
Service für die Verwaltung von Grafiken.
Enthält Logik für die Suche, das Abrufen und die Manipulation von Grafiken.
"""

from django.db.models import Q
from django.db import transaction
from core.models import Chart, ChartBlacklist
from .datawrapper import DatawrapperService

class ChartService:
    """
    Service für die Verwaltung von Grafiken.
    Enthält Methoden für die Suche, das Abrufen und die Manipulation von Grafiken.
    """
    
    def __init__(self):
        """
        Initialisiert den Chart-Service.
        """
        self.datawrapper = DatawrapperService()
    
    def search_charts(self, query='', tags=None, exclude_tags=None, is_published=None, is_archived=None, limit=100, offset=0, sort='-published_date'):
        """
        Sucht nach Grafiken basierend auf verschiedenen Kriterien.
        
        Args:
            query: Suchbegriff
            tags: Liste von Tags
            exclude_tags: Liste von Tags, die ausgeschlossen werden sollen
            is_published: Filter nach Veröffentlichungsstatus
            is_archived: Filter nach Archivierungsstatus
            limit: Maximale Anzahl von Ergebnissen
            offset: Offset für Pagination
            sort: Sortierfeld (z.B. '-published_date' für neueste zuerst)
            
        Returns:
            Dict: Suchergebnisse und Metadaten
        """
        # Basisabfrage
        queryset = Chart.objects.all()
        
        # Textsuche
        if query:
            text_query = Q(chart_id__icontains=query) | \
                        Q(title__icontains=query) | \
                        Q(description__icontains=query) | \
                        Q(notes__icontains=query) | \
                        Q(tags__icontains=query)
            queryset = queryset.filter(text_query)
        
        # Tag-Filter
        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__icontains=tag)
        
        # Filter nach Veröffentlichungsstatus
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published)
            
        # Filter nach Archivierungsstatus
        if is_archived is not None:
            queryset = queryset.filter(is_archived=is_archived)
        
        # Ausschluss von Grafiken mit den Tags "Tägliche Updates" und "Wöchentliche Updates"
        # Immer diese Tags ausschließen, es sei denn, sie werden explizit in der Suche gefordert
        default_exclude_tags = ["Tägliche Updates", "Wöchentliche Updates"]
        
        # Ausschluss der Standard-Tags und zusätzlich übergebener Tags
        exclude_tags_set = set(default_exclude_tags) if exclude_tags is None else set(default_exclude_tags + exclude_tags)
        
        # Ausschluss von Tags, aber nur wenn sie nicht explizit in tags gesucht werden
        if tags:
            exclude_tags_set = exclude_tags_set - set(tags)
            
        # Debug-Ausgabe
        print(f"Auszuschließende Tags: {exclude_tags_set}")
        
        # Ausschluss der Tags aus der Abfrage
        for tag in exclude_tags_set:
            queryset = queryset.exclude(tags__icontains=tag)
        
        # Debug-Ausgabe - temporär für Fehlerbehebung
        print(f"SQL-Query nach Ausschluss von Tags: {queryset.query}")
        
        # Ausschluss von Grafiken auf der Blacklist
        blacklisted_chart_ids = ChartBlacklist.objects.values_list('chart_id', flat=True)
        if blacklisted_chart_ids:
            queryset = queryset.exclude(chart_id__in=blacklisted_chart_ids)
        
        # Gesamtzahl der Ergebnisse
        total_count = queryset.count()
        
        # Sortierung und Pagination
        queryset = queryset.order_by(sort)[offset:offset+limit]
        
        return {
            'results': queryset,
            'total_count': total_count,
            'limit': limit,
            'offset': offset
        }
    
    def get_chart(self, chart_id):
        """
        Holt eine einzelne Grafik anhand ihrer ID.
        
        Args:
            chart_id: ID der Grafik
            
        Returns:
            Chart: Die gefundene Grafik
        """
        return Chart.objects.get(chart_id=chart_id)
    
    def create_chart(self, data):
        """
        Erstellt eine neue Grafik.
        
        Args:
            data: Daten für die neue Grafik
            
        Returns:
            Chart: Die erstellte Grafik
        """
        with transaction.atomic():
            chart = Chart(**data)
            chart.save()
            return chart
    
    def update_chart(self, chart_id, data):
        """
        Aktualisiert eine bestehende Grafik.
        
        Args:
            chart_id: ID der Grafik
            data: Zu aktualisierende Daten
            
        Returns:
            Chart: Die aktualisierte Grafik
        """
        with transaction.atomic():
            chart = self.get_chart(chart_id)
            for key, value in data.items():
                setattr(chart, key, value)
            chart.save()
            return chart
    
    def delete_chart(self, chart_id):
        """
        Löscht eine Grafik.
        
        Args:
            chart_id: ID der Grafik
        """
        chart = self.get_chart(chart_id)
        chart.delete()
    
    def export_chart(self, chart_id, format='pdf', params=None):
        """
        Exportiert eine Grafik in einem bestimmten Format.
        
        Args:
            chart_id: ID der Grafik
            format: Exportformat (pdf, png, svg)
            params: Zusätzliche Parameter
            
        Returns:
            bytes: Exportierte Datei als Binärdaten
        """
        return self.datawrapper.export_chart(chart_id, format, params) 