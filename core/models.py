from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Create your models here.

class Chart(models.Model):
    published_date = models.DateTimeField(null=True, blank=True)
    last_modified_date = models.DateTimeField(null=True, blank=True)
    chart_id = models.CharField(max_length=100)
    title = models.TextField()
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

    def get_tags_list(self):
        """Gibt die Tags als Liste zurück."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',')]

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

class RegistrationConfirmation(models.Model):
    """
    Speichert Informationen zu Registrierungsbestätigungen.
    """
    name = models.CharField(max_length=150, verbose_name="Name")
    email = models.EmailField(unique=True, verbose_name="E-Mail-Adresse")
    token = models.CharField(max_length=100, unique=True, verbose_name="Bestätigungstoken")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Erstellt am")
    confirmed = models.BooleanField(default=False, verbose_name="Bestätigt")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Bestätigt am")
    
    class Meta:
        verbose_name = "Registrierungsbestätigung"
        verbose_name_plural = "Registrierungsbestätigungen"
    
    def __str__(self):
        return f"{self.email} ({self.confirmed})"

class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"Token for {self.user.email}"

    class Meta:
        verbose_name = "Passwort Reset Token"
        verbose_name_plural = "Passwort Reset Tokens"

class TopicTile(models.Model):
    """
    Modell für die Themenkacheln auf der Hauptseite des Archivs.
    Erlaubt die einfache Verwaltung der Kacheln über das Admin-Panel.
    """
    title = models.CharField(
        max_length=100, 
        verbose_name="Titel",
        help_text="Der Text, der auf der Kachel angezeigt wird"
    )
    background_image = models.ImageField(
        upload_to='topic_tiles/', 
        blank=True,
        null=True,
        verbose_name="Hintergrundbild",
        help_text="Das Hintergrundbild für die Kachel (optimal: 5:1 Seitenverhältnis)"
    )
    background_color = models.CharField(
        max_length=20, 
        default="#4f80ff",
        verbose_name="Hintergrundfarbe",
        help_text="Hintergrundfarbe als HEX-Code (z.B. #4f80ff), falls kein Bild verwendet wird"
    )
    search_terms = models.TextField(
        verbose_name="Suchbegriffe",
        help_text="Kommagetrennte Liste von Suchbegriffen, die beim Klick gesucht werden sollen"
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Reihenfolge",
        help_text="Position der Kachel (niedrigere Zahlen erscheinen zuerst)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Legt fest, ob die Kachel angezeigt werden soll"
    )
    
    class Meta:
        verbose_name = "Themenkachel"
        verbose_name_plural = "Themenkacheln"
        ordering = ['order']
    
    def __str__(self):
        return self.title
    
    def get_search_terms_list(self):
        """Gibt die Suchbegriffe als Liste zurück."""
        if not self.search_terms:
            return []
        return [term.strip() for term in self.search_terms.split(',')]

class ChartBlacklist(models.Model):
    """
    Speichert eine Blacklist von Chart-IDs, die aus den Suchergebnissen ausgeschlossen werden sollen.
    """
    
    chart_id = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Grafik-ID",
        help_text="Die eindeutige ID der Datawrapper-Grafik, die ausgeschlossen werden soll"
    )
    
    reason = models.TextField(
        blank=True,
        verbose_name="Grund",
        help_text="Optional: Der Grund für die Blacklistung der Grafik"
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
        related_name='created_blacklist_entries',
        verbose_name="Erstellt von"
    )
    
    class Meta:
        verbose_name = "Blacklist-Eintrag"
        verbose_name_plural = "Blacklist-Einträge"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Blacklist: {self.chart_id} ({self.created_at.strftime('%d.%m.%Y')})"
