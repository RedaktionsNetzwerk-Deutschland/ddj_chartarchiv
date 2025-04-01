"""
Models für die Charts-App.
Definiert die Datenbankstruktur für die Verwaltung von Datawrapper-Grafiken.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

class Chart(models.Model):
    """
    Repräsentiert eine Datawrapper-Grafik im System.
    """
    
    # Basis-Informationen
    chart_id = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Grafik-ID",
        help_text="Die eindeutige ID der Datawrapper-Grafik"
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Titel",
        help_text="Der Titel der Grafik"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Beschreibung",
        help_text="Eine optionale Beschreibung der Grafik"
    )
    
    # Metadaten
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Aktualisiert am"
    )
    published_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Veröffentlicht am"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_charts',
        verbose_name="Erstellt von"
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='modified_charts',
        verbose_name="Zuletzt bearbeitet von"
    )
    
    # Technische Details
    embed_js = models.TextField(
        blank=True,
        verbose_name="Embed-Code",
        help_text="Der JavaScript-Code zum Einbetten der Grafik"
    )
    thumbnail = models.ImageField(
        upload_to='thumbnails/',
        null=True,
        blank=True,
        verbose_name="Vorschaubild"
    )
    
    # Zusätzliche Informationen
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen",
        help_text="Interne Notizen zur Grafik"
    )
    tags = models.TextField(
        blank=True,
        verbose_name="Tags",
        help_text="Komma-separierte Liste von Tags"
    )
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Benutzerdefinierte Felder",
        help_text="Zusätzliche Metadaten im JSON-Format"
    )
    
    # Status
    is_published = models.BooleanField(
        default=False,
        verbose_name="Veröffentlicht",
        help_text="Gibt an, ob die Grafik veröffentlicht wurde"
    )
    is_archived = models.BooleanField(
        default=False,
        verbose_name="Archiviert",
        help_text="Gibt an, ob die Grafik archiviert wurde"
    )
    
    class Meta:
        verbose_name = "Grafik"
        verbose_name_plural = "Grafiken"
        ordering = ['-published_date']
        indexes = [
            models.Index(fields=['chart_id']),
            models.Index(fields=['published_date']),
            models.Index(fields=['is_published']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.chart_id})"
    
    def save(self, *args, **kwargs):
        """Überschreibt die Save-Methode um zusätzliche Logik hinzuzufügen."""
        # Setze published_date wenn is_published sich ändert
        if self.is_published and not self.published_date:
            self.published_date = timezone.now()
        
        # Entferne published_date wenn is_published auf False gesetzt wird
        if not self.is_published:
            self.published_date = None
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        """Gibt die absolute URL der Grafik zurück."""
        from django.urls import reverse
        return reverse('chart_detail', args=[str(self.chart_id)])
    
    def get_tags_list(self):
        """Gibt die Tags als Liste zurück."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',')]
    
    def set_tags_list(self, tags):
        """Setzt die Tags aus einer Liste."""
        self.tags = ','.join(tags)
    
    def get_custom_field(self, field_name, default=None):
        """Holt ein benutzerdefiniertes Feld aus den Metadaten."""
        return self.custom_fields.get(field_name, default)
    
    def set_custom_field(self, field_name, value):
        """Setzt ein benutzerdefiniertes Feld in den Metadaten."""
        self.custom_fields[field_name] = value 

class ChartData(models.Model):
    """
    Speichert die Rohdaten, die für einen Chart verwendet werden.
    """
    
    # Verbindung zum Chart (optional, da Daten auch ohne Chart existieren können)
    chart = models.ForeignKey(
        Chart, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='data_sets',
        verbose_name="Zugehöriger Chart"
    )
    
    # Metadaten
    title = models.CharField(
        max_length=255,
        verbose_name="Titel",
        help_text="Ein beschreibender Titel für diesen Datensatz"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_data_sets',
        verbose_name="Erstellt von"
    )
    
    # Daten
    raw_data = models.TextField(
        verbose_name="Rohdaten",
        help_text="Die Rohdaten im CSV-Format oder anderen strukturierten Formaten"
    )
    
    # Datenanalyse
    analysis = models.TextField(
        blank=True,
        verbose_name="Analyse",
        help_text="Automatisch generierte Analyse der Daten"
    )
    
    # Metadaten der Daten
    header_metadata = models.TextField(
        blank=True,
        verbose_name="Header-Metadaten",
        help_text="Metadaten, die am Anfang der Daten gefunden wurden"
    )
    footer_metadata = models.TextField(
        blank=True,
        verbose_name="Footer-Metadaten",
        help_text="Metadaten, die am Ende der Daten gefunden wurden (z.B. Fußnoten)"
    )
    
    # Formatierung und Verarbeitung
    is_processed = models.BooleanField(
        default=False,
        verbose_name="Verarbeitet",
        help_text="Gibt an, ob die Daten bereits verarbeitet wurden"
    )
    file_type = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Dateityp",
        help_text="Ursprünglicher Dateityp der Daten (z.B. CSV, Excel)"
    )
    
    class Meta:
        verbose_name = "Chart-Daten"
        verbose_name_plural = "Chart-Daten"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Daten: {self.title} ({self.created_at.strftime('%d.%m.%Y')})" 