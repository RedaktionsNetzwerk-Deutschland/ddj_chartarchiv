"""
Datawrapper API Service.
Stellt Funktionen für die Interaktion mit der Datawrapper-API bereit.
"""

import os
import requests
from typing import Dict, List, Optional, Union
from django.conf import settings
from django.core.exceptions import ValidationError

class DatawrapperAPIError(Exception):
    """Basisklasse für Datawrapper-API-Fehler."""
    pass

class DatawrapperService:
    """
    Service-Klasse für die Interaktion mit der Datawrapper-API.
    Kapselt alle API-Aufrufe und Logik für die Kommunikation mit Datawrapper.
    """
    
    def __init__(self):
        """Initialisiert den Service mit API-Konfiguration."""
        self.api_key = settings.DATAWRAPPER_API_KEY
        if not self.api_key:
            raise ValueError("Datawrapper API-Key nicht konfiguriert")
            
        self.base_url = "https://api.datawrapper.de/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict:
        """
        Führt einen API-Request aus und behandelt Fehler.
        
        Args:
            method: HTTP-Methode (GET, POST, etc.)
            endpoint: API-Endpunkt
            params: Query-Parameter
            data: Request-Body
            
        Returns:
            Dict: API-Antwort
            
        Raises:
            DatawrapperAPIError: Bei API-Fehlern
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data
            )
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Datawrapper API Fehler: {str(e)}"
            if hasattr(e.response, 'json'):
                try:
                    error_details = e.response.json()
                    error_msg = f"{error_msg} - {error_details.get('message', '')}"
                except ValueError:
                    pass
            raise DatawrapperAPIError(error_msg)
    
    def get_chart(self, chart_id: str) -> Dict:
        """
        Holt die Informationen zu einer Grafik.
        
        Args:
            chart_id: Die ID der Grafik
            
        Returns:
            Dict: Grafik-Informationen
        """
        return self._make_request('GET', f'/charts/{chart_id}')
    
    def create_chart(self, title: str, chart_type: str, data: Optional[Dict] = None) -> Dict:
        """
        Erstellt eine neue Grafik.
        
        Args:
            title: Titel der Grafik
            chart_type: Typ der Grafik (z.B. 'd3-bars')
            data: Zusätzliche Daten für die Grafik
            
        Returns:
            Dict: Informationen zur erstellten Grafik
        """
        payload = {
            'title': title,
            'type': chart_type,
            **(data or {})
        }
        return self._make_request('POST', '/charts', data=payload)
    
    def update_chart(self, chart_id: str, data: Dict) -> Dict:
        """
        Aktualisiert eine bestehende Grafik.
        
        Args:
            chart_id: Die ID der Grafik
            data: Zu aktualisierende Daten
            
        Returns:
            Dict: Aktualisierte Grafik-Informationen
        """
        return self._make_request('PATCH', f'/charts/{chart_id}', data=data)
    
    def delete_chart(self, chart_id: str) -> None:
        """
        Löscht eine Grafik.
        
        Args:
            chart_id: Die ID der Grafik
        """
        self._make_request('DELETE', f'/charts/{chart_id}')
    
    def publish_chart(self, chart_id: str) -> Dict:
        """
        Veröffentlicht eine Grafik.
        
        Args:
            chart_id: Die ID der Grafik
            
        Returns:
            Dict: Informationen zur veröffentlichten Grafik
        """
        return self._make_request('POST', f'/charts/{chart_id}/publish')
    
    def copy_chart(self, chart_id: str, folder_id: Optional[str] = None) -> Dict:
        """
        Kopiert eine Grafik.
        
        Args:
            chart_id: Die ID der Grafik
            folder_id: Optional - ID des Zielordners
            
        Returns:
            Dict: Informationen zur kopierten Grafik
        """
        data = {'folderId': folder_id} if folder_id else {}
        return self._make_request('POST', f'/charts/{chart_id}/copy', data=data)
    
    def move_chart(self, chart_id: str, folder_id: str) -> Dict:
        """
        Verschiebt eine Grafik in einen anderen Ordner.
        
        Args:
            chart_id: Die ID der Grafik
            folder_id: ID des Zielordners
            
        Returns:
            Dict: Aktualisierte Grafik-Informationen
        """
        return self.update_chart(chart_id, {'folderId': folder_id})
    
    def get_folders(self) -> List[Dict]:
        """
        Holt alle verfügbaren Ordner.
        
        Returns:
            List[Dict]: Liste der Ordner
        """
        response = self._make_request('GET', '/folders')
        return response.get('list', [])
    
    def find_folder_by_name(self, name: str) -> Optional[Dict]:
        """
        Sucht einen Ordner anhand seines Namens.
        
        Args:
            name: Name des Ordners
            
        Returns:
            Optional[Dict]: Ordner-Informationen oder None
        """
        folders = self.get_folders()
        return next(
            (folder for folder in folders if folder.get('name', '').lower() == name.lower()),
            None
        )
    
    def export_chart(
        self,
        chart_id: str,
        format: str = 'pdf',
        params: Optional[Dict] = None
    ) -> bytes:
        """
        Exportiert eine Grafik in verschiedenen Formaten.
        
        Args:
            chart_id: Die ID der Grafik
            format: Exportformat ('pdf', 'png', 'svg')
            params: Zusätzliche Export-Parameter
            
        Returns:
            bytes: Die exportierte Datei
            
        Raises:
            DatawrapperAPIError: Bei ungültigem Format oder Exportfehler
        """
        valid_formats = ['pdf', 'png', 'svg']
        if format not in valid_formats:
            raise ValidationError(f"Ungültiges Format. Erlaubt sind: {', '.join(valid_formats)}")
        
        url = f"{self.base_url}/charts/{chart_id}/export/{format}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.content
            
        except requests.exceptions.RequestException as e:
            raise DatawrapperAPIError(f"Export fehlgeschlagen: {str(e)}") 