from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Chart, ChartData, RegistrationConfirmation, PasswordResetToken, TopicTile
from django.utils.html import format_html
from django.conf import settings
import os
from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Register your models here.
admin.site.register(Chart)
admin.site.register(ChartData)
admin.site.register(RegistrationConfirmation)
admin.site.register(PasswordResetToken)

# Benutzerdefiniertes Formular für TopicTile
class TopicTileAdminForm(forms.ModelForm):
    existing_image = forms.ChoiceField(
        label="Bestehendes Bild auswählen",
        required=False,
        help_text="Wähle ein bereits hochgeladenes Bild aus oder lade ein neues Bild über das Feld 'Hintergrundbild' hoch."
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Liste der verfügbaren Bilder erstellen
        media_dir = os.path.join(settings.MEDIA_ROOT, 'topic_tiles')
        choices = [('', '--- Kein bestehendes Bild auswählen ---')]
        
        if os.path.exists(media_dir):
            for file in os.listdir(media_dir):
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    file_path = f'topic_tiles/{file}'
                    choices.append((file_path, file))
        
        self.fields['existing_image'].choices = choices
        
        # Aktuelles Bild als Standard setzen, falls vorhanden
        if self.instance and self.instance.background_image:
            current_image = str(self.instance.background_image)
            if current_image in [choice[0] for choice in choices]:
                self.fields['existing_image'].initial = current_image
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Wenn ein bestehendes Bild ausgewählt wurde und es sich vom aktuellen unterscheidet
        existing_image = self.cleaned_data.get('existing_image')
        if existing_image and not self.cleaned_data.get('background_image'):
            # Bestimme den vollständigen Pfad zur Datei
            file_path = os.path.join(settings.MEDIA_ROOT, existing_image)
            
            if os.path.exists(file_path):
                # Lösche das aktuelle Bild, falls vorhanden
                if instance.background_image:
                    instance.background_image.delete(save=False)
                
                # Öffne die ausgewählte Datei und weise sie dem background_image zu
                with open(file_path, 'rb') as f:
                    file_name = os.path.basename(file_path)
                    instance.background_image.save(file_name, ContentFile(f.read()), save=False)
        
        if commit:
            instance.save()
        
        return instance
    
    class Meta:
        model = TopicTile
        fields = '__all__'

# Admin-Klasse für TopicTile
class TopicTileAdmin(admin.ModelAdmin):
    form = TopicTileAdminForm
    list_display = ('title', 'order', 'is_active', 'display_image_thumbnail')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'search_terms')
    readonly_fields = ('image_preview',)
    fieldsets = (
        (None, {
            'fields': ('title', 'background_color')
        }),
        ('Hintergrundbild', {
            'fields': ('existing_image', 'background_image', 'image_preview'),
            'description': 'Wähle entweder ein bestehendes Bild aus oder lade ein neues hoch.'
        }),
        ('Suchoptionen', {
            'fields': ('search_terms',),
            'description': 'Kommagetrennte Liste von Suchbegriffen, die beim Klick auf die Kachel verwendet werden.'
        }),
        ('Anzeige-Optionen', {
            'fields': ('order', 'is_active')
        }),
    )
    
    def image_preview(self, obj):
        """Zeigt eine Vorschau des Hintergrundbilds im Admin-Panel"""
        if obj.background_image:
            return format_html('<img src="{}" style="max-height: 200px; max-width: 400px;" /><br>Bildpfad: {}', 
                               obj.background_image.url, obj.background_image.name)
        return "Kein Bild ausgewählt."
    
    def display_image_thumbnail(self, obj):
        """Zeigt eine kleine Vorschau des Hintergrundbilds in der Listendarstellung"""
        if obj.background_image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 100px;" />', 
                           obj.background_image.url)
        return format_html('<div style="width: 100px; height: 30px; background-color: {}; display: inline-block;"></div>', obj.background_color)
    
    display_image_thumbnail.short_description = 'Vorschau'
    image_preview.short_description = 'Bildvorschau'

admin.site.register(TopicTile, TopicTileAdmin)

# Benutzeradmin erweitern, um Gruppenzuordnungen zu vereinfachen
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_groups')
    list_filter = ('is_staff', 'is_superuser', 'groups')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    def get_groups(self, obj):
        """Gibt die Gruppen eines Benutzers als kommagetrennte Liste zurück"""
        return ", ".join([group.name for group in obj.groups.all()])
    
    get_groups.short_description = 'Gruppen'

# Deregistriere den Standard-UserAdmin und registriere unseren benutzerdefinierten
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
