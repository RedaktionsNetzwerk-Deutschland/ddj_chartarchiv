from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# Create your models here.

class Chart(models.Model):
    published_date = models.DateTimeField(null=True, blank=True)
    last_modified_date = models.DateTimeField(null=True, blank=True)
    chart_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    comments = models.TextField(blank=True)
    tags = models.TextField(blank=True)
    patch = models.BooleanField(default=False)
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    iframe_url = models.URLField(blank=True)
    embed_js = models.TextField(blank=True)
    evergreen = models.BooleanField(default=False)
    regional = models.BooleanField(default=False)

    def __str__(self):
        return self.title

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
        blank=True,
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
