#!/usr/bin/env python
"""
Beispiel für die Verwendung des Datawrapper-Debuggers in einer Django-Shell.

Um dieses Skript in der Django-Shell zu verwenden:
1. python manage.py shell
2. exec(open('debug_chart_example.py').read())
3. debug_chart('chart_id_hier_einsetzen')
"""

from apps.charts.services.datawrapper import DatawrapperService
from apps.charts.services.datawrapper_debug import debug_chart_metadata

# Debug-Methode zur DatawrapperService-Klasse hinzufügen
DatawrapperService.debug_chart_metadata = debug_chart_metadata

def debug_chart(chart_id):
    """
    Debuggt die Metadaten einer Datawrapper-Grafik.
    
    Args:
        chart_id: Die ID der zu debuggenden Grafik
    """
    service = DatawrapperService()
    service.debug_chart_metadata(chart_id)
    
# Beispiel zur direkten Verwendung:
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        debug_chart(sys.argv[1])
    else:
        print("Verwendung: python debug_chart_example.py <chart_id>")
        print("Oder in der Django-Shell:")
        print("1. python manage.py shell")
        print("2. exec(open('debug_chart_example.py').read())")
        print("3. debug_chart('chart_id_hier_einsetzen')") 