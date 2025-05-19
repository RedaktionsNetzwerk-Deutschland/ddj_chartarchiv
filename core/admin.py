from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Chart, ChartData, RegistrationConfirmation, PasswordResetToken, TopicTile, ChartBlacklist, AllowedEmailDomain, AllowedEmailAddress
from django.utils.html import format_html
from django.conf import settings
import os, base64, uuid
from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from django.shortcuts import render, redirect
from django.urls import path
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _

# Register your models here.
# Entferne die einfache Registrierung
# admin.site.register(Chart)
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
        
        # Hole das hochgeladene Bild aus dem Formular
        uploaded_image = self.cleaned_data.get('background_image')
        existing_image = self.cleaned_data.get('existing_image')
        
        # 1. Fall: Ein neues Bild wurde hochgeladen
        if uploaded_image:
            # Wenn ein neues Bild hochgeladen wird, setzen wir es und ignorieren das existing_image
            # Django's ModelForm kümmert sich automatisch um die Speicherung des hochgeladenen Bildes
            pass  # Das Bild wird bereits durch super().save() gesetzt
        
        # 2. Fall: Kein hochgeladenes Bild, aber ein bestehendes Bild ausgewählt
        elif existing_image:
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

# Benutzerdefiniertes Formular für Chart mit Clipboard-Unterstützung
class ChartAdminForm(forms.ModelForm):
    clipboard_image = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text="Füge ein Bild mit Strg+V ein"
    )

    class Meta:
        model = Chart
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        # Überprüfen, ob ein Clipboard-Bild vorhanden ist
        clipboard_data = cleaned_data.get('clipboard_image')
        if clipboard_data and clipboard_data.startswith('data:image'):
            # Bild aus Base64-Daten erstellen
            format, imgstr = clipboard_data.split(';base64,')
            ext = format.split('/')[-1]
            file_name = f"{uuid.uuid4()}.{ext}"
            data = ContentFile(base64.b64decode(imgstr))
            
            # Lösche das vorherige Bild, falls vorhanden
            if self.instance.pk and self.instance.thumbnail:
                self.instance.thumbnail.delete(save=False)
            
            # Speichere das neue Bild
            self.instance.thumbnail.save(file_name, data, save=False)
        
        return cleaned_data

# Admin-Klasse für Chart
class ChartAdmin(admin.ModelAdmin):
    form = ChartAdminForm
    list_display = ('title', 'chart_id', 'published_date', 'display_thumbnail', 'evergreen', 'regional')
    list_filter = ('published_date', 'evergreen', 'regional')
    search_fields = ('title', 'chart_id', 'description', 'tags')
    readonly_fields = ('last_modified_date', 'display_thumbnail')
    fieldsets = (
        (None, {
            'fields': ('title', 'chart_id', 'description', 'notes', 'comments', 'tags')
        }),
        ('Metadaten', {
            'fields': ('published_date', 'last_modified_date')
        }),
        ('Thumbnail', {
            'fields': ('thumbnail', 'clipboard_image', 'display_thumbnail'),
            'description': 'Du kannst ein Bild hochladen oder per Strg+V einfügen.'
        }),
        ('Eigenschaften', {
            'fields': ('evergreen', 'regional', 'patch')
        }),
        ('Embed-Code', {
            'fields': ('iframe_url', 'embed_js'),
            'classes': ('collapse',)
        }),
    )
    
    def display_thumbnail(self, obj):
        """Zeigt eine Vorschau des Thumbnails im Admin-Panel"""
        if obj.thumbnail:
            return format_html('<img src="{}" style="max-height: 200px; max-width: 400px;" />', 
                               obj.thumbnail.url)
        return "Kein Bild hochgeladen."
    
    display_thumbnail.short_description = 'Bildvorschau'
    
    def save_model(self, request, obj, form, change):
        """Aktualisiert das last_modified_date beim Speichern"""
        # Aktualisiere last_modified_date immer
        obj.last_modified_date = timezone.now()
        
        # Setze published_date auf den aktuellen Zeitstempel, wenn es nicht gesetzt ist
        if not obj.published_date:
            obj.published_date = timezone.now()
        
        super().save_model(request, obj, form, change)
    
    class Media:
        js = ('core/js/clipboard_image.js',)

admin.site.register(Chart, ChartAdmin)

# Admin-Klasse für TopicTile
class TopicTileAdmin(admin.ModelAdmin):
    form = TopicTileAdminForm
    list_display = ('title', 'parent', 'order', 'is_active', 'show_in_main', 'display_image_thumbnail')
    list_editable = ('order', 'is_active', 'show_in_main')
    list_filter = ('is_active', 'show_in_main', 'parent')
    search_fields = ('title', 'search_terms')
    readonly_fields = ('image_preview', 'display_combined_search_terms')
    fieldsets = (
        (None, {
            'fields': ('title', 'background_color')
        }),
        ('Hierarchie', {
            'fields': ('parent', 'inherit_parent_search', 'show_in_main'),
            'description': 'Beziehung zu anderen Themenkacheln festlegen. Unterkacheln können unter übergeordneten Kacheln angezeigt werden.'
        }),
        ('Hintergrundbild', {
            'fields': ('existing_image', 'background_image', 'image_preview'),
            'description': 'Wähle entweder ein bestehendes Bild aus oder lade ein neues hoch.'
        }),
        ('Suchoptionen', {
            'fields': ('search_terms', 'display_combined_search_terms'),
            'description': 'Kommagetrennte Liste von Suchbegriffen, die beim Klick auf die Kachel verwendet werden.'
        }),
        ('Anzeige-Optionen', {
            'fields': ('order',),
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
    
    def display_combined_search_terms(self, obj):
        """Zeigt alle Suchbegriffe inklusive geerbter an"""
        if not obj.pk:  # Für neue Objekte, die noch nicht gespeichert wurden
            return "Verfügbar nach dem Speichern"
            
        own_terms = obj.search_terms.split(',') if obj.search_terms else []
        own_terms = [term.strip() for term in own_terms if term.strip()]
        
        if not obj.inherit_parent_search or not obj.parent:
            return format_html('<div>{}</div>', ', '.join(own_terms) or 'Keine Suchbegriffe definiert')
            
        # Zeige eigene und geerbte Begriffe an
        combined_terms = obj.get_search_terms_list()
        inherited_terms = [term for term in combined_terms if term not in own_terms]
        
        if not inherited_terms:
            return format_html('<div>{}</div>', ', '.join(own_terms) or 'Keine Suchbegriffe definiert')
            
        return format_html(
            '<div><strong>Eigene Begriffe:</strong> {}</div>'
            '<div><strong>Geerbte Begriffe:</strong> <span style="color: #4f80ff;">{}</span></div>'
            '<div><strong>Kombiniert:</strong> {}</div>',
            ', '.join(own_terms) or 'Keine',
            ', '.join(inherited_terms),
            ', '.join(combined_terms)
        )
    
    class Media:
        js = ('core/js/admin_image_preview.js',)
    
    display_image_thumbnail.short_description = 'Vorschau'
    image_preview.short_description = 'Bildvorschau'
    display_combined_search_terms.short_description = 'Kombinierte Suchbegriffe'

admin.site.register(TopicTile, TopicTileAdmin)

# Admin-Klasse für ChartBlacklist
class ChartBlacklistAdmin(admin.ModelAdmin):
    list_display = ('chart_id', 'reason', 'created_at', 'created_by')
    list_filter = ('created_at',)
    search_fields = ('chart_id', 'reason')
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {
            'fields': ('chart_id', 'reason')
        }),
        ('Metadaten', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        # Automatisch den aktuellen Benutzer als Ersteller setzen, wenn nicht angegeben
        if not change:  # Nur beim Erstellen, nicht beim Bearbeiten
            if not obj.created_by:
                obj.created_by = request.user
        super().save_model(request, obj, form, change)

admin.site.register(ChartBlacklist, ChartBlacklistAdmin)

# Admin-Klasse für AllowedEmailDomain
class AllowedEmailDomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'description', 'is_active', 'created_at', 'created_by')
    list_filter = ('is_active', 'created_at')
    search_fields = ('domain', 'description')
    list_editable = ('is_active',)
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {
            'fields': ('domain', 'description', 'is_active')
        }),
        ('Metadaten', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        # Automatisch den aktuellen Benutzer als Ersteller setzen, wenn nicht angegeben
        if not change:  # Nur beim Erstellen, nicht beim Bearbeiten
            if not obj.created_by:
                obj.created_by = request.user
        super().save_model(request, obj, form, change)

admin.site.register(AllowedEmailDomain, AllowedEmailDomainAdmin)

# Admin-Klasse für AllowedEmailAddress
class AllowedEmailAddressAdmin(admin.ModelAdmin):
    list_display = ('email', 'description', 'is_active', 'created_at', 'created_by')
    list_filter = ('is_active', 'created_at')
    search_fields = ('email', 'description')
    list_editable = ('is_active',)
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {
            'fields': ('email', 'description', 'is_active')
        }),
        ('Metadaten', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        # Automatisch den aktuellen Benutzer als Ersteller setzen, wenn nicht angegeben
        if not change:  # Nur beim Erstellen, nicht beim Bearbeiten
            if not obj.created_by:
                obj.created_by = request.user
        super().save_model(request, obj, form, change)

admin.site.register(AllowedEmailAddress, AllowedEmailAddressAdmin)

# Benutzeradmin erweitern, um Gruppenzuordnungen zu vereinfachen
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_groups')
    list_filter = ('is_staff', 'is_superuser', 'groups')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    def get_groups(self, obj):
        """Gibt die Gruppen eines Benutzers als kommagetrennte Liste zurück"""
        return ", ".join([group.name for group in obj.groups.all()])
    
    get_groups.short_description = 'Gruppen'
    
    def delete_related_user_data(self, email, user):
        """Löscht alle mit dem Benutzer verknüpften Daten"""
        if email:
            # Importiere hier, um zirkuläre Importe zu vermeiden
            from core.models import AllowedEmailAddress, RegistrationConfirmation, PasswordResetToken
            
            print(f"Lösche verknüpfte Daten für E-Mail: {email}")
            
            # Lösche den Eintrag in AllowedEmailAddress, wenn die E-Mail dort vorhanden ist
            deleted_email = AllowedEmailAddress.objects.filter(email=email).delete()
            print(f"Gelöschte AllowedEmailAddress-Einträge: {deleted_email}")
            
            # Lösche alle Registrierungsbestätigungen für diesen Benutzer
            deleted_reg = RegistrationConfirmation.objects.filter(email=email).delete()
            print(f"Gelöschte RegistrationConfirmation-Einträge: {deleted_reg}")
            
            # Lösche alle Password-Reset-Tokens für diesen Benutzer
            deleted_tokens = PasswordResetToken.objects.filter(user=user).delete()
            print(f"Gelöschte PasswordResetToken-Einträge: {deleted_tokens}")
            
            return True
        return False
    
    def delete_model(self, request, obj):
        """Überschriebene Methode zum Löschen eines Benutzers und aller verknüpften Daten"""
        email = obj.email
        # Zuerst verknüpfte Daten löschen
        self.delete_related_user_data(email, obj)
        # Dann den Benutzer selbst löschen
        super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Überschriebene Methode zum Löschen mehrerer Benutzer und ihrer verknüpften Daten"""
        for obj in queryset:
            self.delete_related_user_data(obj.email, obj)
        # Dann die Benutzer selbst löschen
        super().delete_queryset(request, queryset)

# Deregistriere den Standard-UserAdmin und registriere unseren benutzerdefinierten
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
