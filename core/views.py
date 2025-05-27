from django.shortcuts import render, redirect, get_object_or_404
from .forms import RegistrationForm, LoginForm, PasswordResetRequestForm, CustomSetPasswordForm
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from .models import Chart, RegistrationConfirmation, PasswordResetToken, TopicTile, ChartBlacklist, SystemMessage
import os
import requests
from openai import OpenAI
import pandas as pd
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.conf import settings
import datetime
from django.utils import timezone
import io
from django.contrib import messages
from django.contrib.auth.models import User
from .utils import generate_token, send_confirmation_email, send_password_reset_email, custom_login_required
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import transaction
from django.core.files.base import ContentFile
try:
    from PIL import Image
except ImportError:
    print("WARNUNG: PIL/Pillow ist nicht installiert, die Thumbnail-Generierung wird nicht funktionieren")
import re
from ftplib import FTP, FTP_TLS

# Create your views here.

def index(request):
    # Prüfen, ob wir bereits eine login_form aus dem Context haben
    if hasattr(request, '_login_form'):
        login_form = request._login_form
    else:
        login_form = LoginForm()
    
    # Lade aktive Systemnachrichten für die Startseite
    from django.utils import timezone
    from django.db import models as db_models
    current_time = timezone.now()
    
    system_messages = SystemMessage.objects.filter(
        is_active=True,
        show_on_index=True
    ).filter(
        # Nachrichten die entweder kein Ablaufdatum haben oder noch gültig sind
        db_models.Q(valid_until__isnull=True) | db_models.Q(valid_until__gte=current_time)
    ).order_by('-created_at')
    
    return render(request, 'index.html', {
        'login_form': login_form,
        'system_messages': system_messages
    })

def register(request):
    print("DEBUG: register VIEW - ANFANG")
    if request.method == "POST":
        print("DEBUG: register VIEW - POST-Request erhalten")
        form = RegistrationForm(request.POST)
        if form.is_valid():
            print("DEBUG: register VIEW - Formular ist GÜLTIG")
            # Extrahiere die Daten aus dem Formular
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            
            print("DEBUG: register VIEW - Vor Aufruf von generate_token()")
            # Erzeuge ein Token für die Bestätigung
            token = generate_token()
            
            # Prüfen, ob es bereits einen Benutzer mit dieser E-Mail gibt in der auth_user-Tabelle
            if User.objects.filter(email=email).exists():
                print(f"DEBUG: Ein aktiver Benutzer mit der E-Mail {email} existiert bereits in auth_user")
                login_url = reverse('index')
                reset_url = reverse('password_reset_request')
                error_message = mark_safe(
                    f'Ein Konto mit der E-Mail-Adresse {email} existiert bereits. '
                    f'<a href="{login_url}" style="color: #007bff; text-decoration: underline;">Bitte logge dich ein</a>. '
                    f'Wenn du ein neues Passwort benötigst, <a href="{reset_url}" style="color: #007bff; text-decoration: underline;">klicke hier</a>.'
                )
                messages.error(request, error_message)
                return redirect('register')
            
            # Da kein Benutzer in auth_user existiert, können wir neu registrieren
            # Prüfen, ob es bereits einen Eintrag in der RegistrationConfirmation gibt
            try:
                # Versuche, die Registrierungsbestätigung zu finden
                registration = RegistrationConfirmation.objects.get(email=email)
                
                # Überprüfe, ob die Registrierung bereits bestätigt ist, aber kein zugehöriger Benutzer existiert
                # (Dies kann passieren, wenn ein Benutzer im Admin-Bereich gelöscht wurde)
                if registration.confirmed and not User.objects.filter(email=email).exists():
                    print(f"DEBUG: Bestätigte Registrierung für {email} gefunden, aber kein Benutzer existiert. Registrierung wird zurückgesetzt.")
                    registration.confirmed = False
                    registration.confirmed_at = None
                    registration.token = token
                    registration.created_at = timezone.now()
                    registration.save()
                    
                    # Sende die Bestätigungsmail
                    print("DEBUG: register VIEW - Vor Aufruf von send_confirmation_email() (Neuregistrierung nach Löschung)")
                    email_sent = send_confirmation_email(name, email, token, request)
                    print(f"DEBUG: register VIEW - email_sent: {email_sent}")
                    
                    if email_sent:
                        messages.success(request, "Wir haben dir einen neuen Bestätigungslink geschickt. Bitte schau in dein Postfach.")
                    else:
                        messages.error(request, "Leider konnte die Bestätigungsmail nicht gesendet werden. Bitte versuche es später erneut.")
                    
                    return redirect('index')
                
                # Überprüfe, ob die Registrierung schon zu alt ist (älter als 24 Stunden)
                if (timezone.now() - registration.created_at).days >= 1:
                    print(f"DEBUG: Alte Registrierung für {email} gefunden, lösche und erstelle neu")
                    # Lösche den alten Eintrag und erstelle einen neuen
                    registration.delete()
                    registration = RegistrationConfirmation.objects.create(
                        name=name,
                        email=email,
                        token=token
                    )
                else:
                    # Aktualisiere den bestehenden Eintrag, unabhängig davon, ob er bestätigt wurde oder nicht
                    # (Da kein entsprechender Benutzer in auth_user existiert)
                    print(f"DEBUG: Aktualisiere bestehende Registrierung für {email}")
                    registration.name = name
                    registration.token = token
                    registration.created_at = timezone.now()
                    registration.confirmed = False  # Zurücksetzen auf unbestätigt
                    registration.confirmed_at = None
                    registration.save()
            except RegistrationConfirmation.DoesNotExist:
                # Wenn keine Registrierungsbestätigung existiert, erstelle eine neue
                print(f"DEBUG: Erstelle neue Registrierungsbestätigung für {email}")
                registration = RegistrationConfirmation.objects.create(
                    name=name,
                    email=email,
                    token=token
                )
            
            # Sende die Bestätigungsmail
            print("DEBUG: register VIEW - Vor Aufruf von send_confirmation_email()")
            email_sent = send_confirmation_email(name, email, token, request)
            print(f"DEBUG: register VIEW - email_sent: {email_sent}")
            
            if email_sent:
                # Bestätigungsmeldung hinzufügen
                messages.success(request, "Wir haben dir einen Bestätigungslink geschickt. Bitte schau in dein Postfach.")
            else:
                # Fehlermeldung, wenn die E-Mail nicht gesendet werden konnte
                messages.error(request, "Leider konnte die Bestätigungsmail nicht gesendet werden. Bitte versuche es später erneut.")
            
            return redirect('index')
        else:
            print("DEBUG: register VIEW - Formular ist UNGÜLTIG")
            print(f"DEBUG: register VIEW - Formularfehler: {form.errors.as_json()}")
    else:
        print("DEBUG: register VIEW - KEIN POST-Request (GET oder anderes)")
        form = RegistrationForm()
    return render(request, 'register.html', {'form': form})

def confirm_registration(request, token):
    try:
        # Nur nach Token suchen
        registration = RegistrationConfirmation.objects.get(token=token)
        
        print(f"DEBUG: confirm_registration für E-Mail: {registration.email}, Token: {token[:10]}..., Bereits bestätigt: {registration.confirmed}")
        print(f"DEBUG: User existiert: {User.objects.filter(email=registration.email).exists()}")
        
        # Prüfen ob bereits bestätigt UND ob ein Benutzer mit dieser E-Mail existiert
        if registration.confirmed:
            if User.objects.filter(email=registration.email).exists():
                messages.info(request, "Deine Registrierung ist jetzt bestätigt. Bitte logge dich ein.")
                return redirect('index')
            else:
                # Registrierung ist bestätigt, aber kein Benutzer existiert mehr
                # (Das kann passieren, wenn ein Admin den Benutzer gelöscht hat)
                print(f"DEBUG: Bestätigte Registrierung gefunden, aber kein Benutzer existiert für {registration.email}")
                
                # Setze die Registrierung zurück
                registration.confirmed = False
                registration.confirmed_at = None
                registration.save()
                
                # Weiterleitung zur Passwort-Einrichtungsseite
                print(f"DEBUG: Leite zur Passwort-Einrichtungsseite weiter mit Token: {token[:10]}...")
                return redirect('set_password', token=token)
        
        # Markiere die Registrierung als bestätigt
        registration.confirmed = True
        registration.confirmed_at = timezone.now()
        registration.save()
        
        # Weiterleitung zur Passwort-Einrichtungsseite
        print(f"DEBUG: Leite zur Passwort-Einrichtungsseite weiter mit Token: {token[:10]}...")
        return redirect('set_password', token=token)
        
    except RegistrationConfirmation.DoesNotExist:
        messages.error(request, "Ungültiger Bestätigungslink. Bitte registriere dich erneut.")
        return redirect('register')

def set_password(request, token):
    try:
        # Finde die Registrierungsbestätigung
        registration = RegistrationConfirmation.objects.get(token=token)
        
        print(f"DEBUG: set_password für E-Mail: {registration.email}, Token: {token[:10]}..., Bestätigt: {registration.confirmed}")
        
        # Prüfe, ob bereits ein Benutzer mit dieser E-Mail existiert
        user_exists = User.objects.filter(email=registration.email).exists()
        print(f"DEBUG: User existiert: {user_exists}")
        
        if user_exists:
            print(f"DEBUG: User existiert bereits für {registration.email}, leite zur Passwort-Reset-Seite weiter")
            password_reset_url = reverse('password_reset_request')
            error_message = mark_safe(
                f'Deine E-Mail-Adresse ist bereits registriert. <a href="{password_reset_url}" style="color: #4f80ff; text-decoration: underline;">Passwort vergessen?</a>'
            )
            messages.warning(request, error_message)
            return redirect('index')
        
        # Wir prüfen nicht mehr, ob die Registrierung bestätigt wurde
        # Solange ein gültiges Token vorhanden ist, erlauben wir die Passwort-Einrichtung
            
        if request.method == "POST":
            form = CustomSetPasswordForm(request.POST)
            if form.is_valid():
                # Erstelle einen Benutzernamen aus dem E-Mail-Teil vor dem @
                username = registration.email.split('@')[0]
                
                # Falls der Benutzername schon existiert, füge eine Nummer hinzu
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # Passwort aus Formular holen
                password = form.cleaned_data['new_password1']
                
                # Erstelle den Nutzer
                user = User.objects.create_user(
                    username=username,
                    email=registration.email,
                    password=password,
                    first_name=registration.name.split(' ')[0] if ' ' in registration.name else registration.name,
                    last_name=' '.join(registration.name.split(' ')[1:]) if ' ' in registration.name else ''
                )
                
                print(f"DEBUG: Benutzer erstellt für {registration.email} mit Benutzername {username}")
                
                # Markiere die Registrierung als bestätigt (falls sie es noch nicht ist)
                registration.confirmed = True
                registration.confirmed_at = timezone.now()
                registration.save()
                
                # Logge den Benutzer automatisch ein
                user = authenticate(username=username, password=password)
                if user is not None:
                    login(request, user)
                    messages.success(request, "Dein Passwort wurde angelegt, du bist jetzt eingeloggt.")
                    return redirect('archive_main')
                else:
                    messages.success(request, "Dein Passwort wurde angelegt. Du kannst dich jetzt anmelden.")
                    return redirect('index')
        else:
            form = CustomSetPasswordForm()
        
        # Extrahiere den Vornamen für die persönliche Anrede
        first_name = registration.name.split(' ')[0] if ' ' in registration.name else registration.name
        
        return render(request, 'set_password.html', {
            'form': form,
            'first_name': first_name,
            'token': token
        })
        
    except RegistrationConfirmation.DoesNotExist:
        print(f"DEBUG: Keine Registrierungsbestätigung gefunden für Token: {token[:10]}...")
        messages.error(request, "Ungültiger oder abgelaufener Link. Bitte registriere dich erneut.")
        return redirect('register')

@custom_login_required(login_url='index')
def archive_main(request):
    # Lade aktive Themenkacheln aus der Datenbank (nur Hauptkacheln)
    topic_tiles = TopicTile.objects.filter(is_active=True, show_in_main=True).order_by('order')
    
    # Lade aktive Systemnachrichten für die Hauptarchiv-Seite
    from django.utils import timezone
    from django.db import models as db_models
    current_time = timezone.now()
    
    system_messages = SystemMessage.objects.filter(
        is_active=True,
        show_on_main_archive=True
    ).filter(
        # Nachrichten die entweder kein Ablaufdatum haben oder noch gültig sind
        db_models.Q(valid_until__isnull=True) | db_models.Q(valid_until__gte=current_time)
    ).order_by('-created_at')
    
    return render(request, 'archive_main.html', {
        'topic_tiles': topic_tiles,
        'system_messages': system_messages
    })

@custom_login_required(login_url='index')
def subtopics_view(request, parent_id):
    """
    Zeigt die Unterthemen einer Hauptkachel an.
    """
    try:
        # Lade die übergeordnete Kachel
        parent_tile = TopicTile.objects.get(id=parent_id, is_active=True)
        
        # Lade Unterkacheln
        subtopic_tiles = TopicTile.objects.filter(
            parent=parent_tile,
            is_active=True
        ).order_by('order')
        
        context = {
            'parent_tile': parent_tile,
            'subtopic_tiles': subtopic_tiles
        }
        
        return render(request, 'subtopics.html', context)
    except TopicTile.DoesNotExist:
        # Falls die übergeordnete Kachel nicht existiert, Redirect zur Hauptseite
        return redirect('archive_main')

@custom_login_required(login_url='index')
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

@custom_login_required(login_url='index')
def chart_search(request):
    q = request.GET.get('q', '')
    page = int(request.GET.get('page', 0))
    items_per_page = int(request.GET.get('limit', 25))  # Anzahl der Items pro Seite, default 25
    offset = int(request.GET.get('offset', 0))  # Optional offset Parameter
    logical_op = request.GET.get('logical_op', 'OR').upper()  # Default ist OR, kann auf AND gesetzt werden
    
    # Neuer Parameter für die feldspezifische Suche
    search_fields = request.GET.get('search_fields', '')
    
    # Neuer Parameter für die themenspezifische Suche
    parent_scope = request.GET.get('parent_scope', None)
    parent_search_terms = None
    
    # Bei Verwendung von parent_scope, lade die Themenkachel und ihre Suchbegriffe
    parent_tile = None
    if parent_scope:
        try:
            from core.models import TopicTile
            parent_tile = TopicTile.objects.get(id=parent_scope)
            parent_search_terms = parent_tile.search_terms
            print(f"DEBUG[SERVER]: Suche innerhalb des Themenbereichs: {parent_tile.title} mit Suchbegriffen: {parent_search_terms}")
            print(f"DEBUG[SERVER]: Exakte Tag-Suche aktiviert: {parent_tile.exact_tag_search}")
        except Exception as e:
            print(f"DEBUG[SERVER]: Fehler beim Laden der Themenkachel: {e}")
    
    # Bei Verwendung von offset, berechnen wir die Seite entsprechend
    if offset > 0:
        page = offset // items_per_page
    
    print(f"DEBUG[SERVER]: Suchanfrage erhalten - Suchbegriff: '{q}', Seite: {page}, Limit: {items_per_page}, Offset: {offset}, LogicalOp: {logical_op}")
    print(f"DEBUG[SERVER]: Alle Request-Parameter: {dict(request.GET.items())}")
    
    # Bei aktiver Feldfilterung, bereite die Liste der zu durchsuchenden Felder vor
    selected_fields = []
    if search_fields:
        selected_fields = [field.strip() for field in search_fields.split(',') if field.strip()]
        print(f"DEBUG[SERVER]: Feldspezifische Suche in Feldern: {selected_fields}")
    
    # Hole blacklisted Chart-IDs einmal, um sie von allen Suchergebnissen auszuschließen
    blacklisted_chart_ids = ChartBlacklist.objects.values_list('chart_id', flat=True)
    print(f"DEBUG[SERVER]: Anzahl der Blacklist-Einträge: {len(blacklisted_chart_ids)}")
    
    # Erstelle eine Basisdatenbank-Abfrage für alle Grafiken
    base_query = Chart.objects.all()
    base_query = base_query.exclude(tags__icontains="Tägliche Updates")
    
    # Ausschluss von Grafiken auf der Blacklist
    if blacklisted_chart_ids:
        base_query = base_query.exclude(chart_id__in=blacklisted_chart_ids)
    
    # Wenn ein Themenbereich angegeben ist, wende zuerst einen Filter für die Themen-Suchbegriffe an
    if parent_scope and parent_search_terms:
        # Teile die Themensuchbegriffe in einzelne Wörter/Begriffe auf
        # Hier beachten wir Kommas und behandeln jede Phrase als separaten Suchbegriff
        parent_terms = [term.strip() for term in parent_search_terms.split(',') if term.strip()]
        print(f"DEBUG[SERVER]: Themenkachel-Suchbegriffe: {parent_terms}")
        
        # Erstelle eine AND-Abfrage für die Themensuchbegriffe
        parent_query = Q(pk__isnull=False)  # Grundfilter, der alle Einträge einschließt
        
        # Wir verarbeiten jeden Suchbegriff durch die create_field_query-Funktion, um feldspezifische Suchen zu ermöglichen
        for term in parent_terms:
            # Verwende dieselbe Funktion wie für Benutzer-Suchanfragen, aber mit der exact_tag_search-Option
            term_query = create_field_query(term, [], parent_tile.exact_tag_search if parent_tile else False)
            parent_query &= term_query  # AND-Verknüpfung statt OR
        
        # Filtere die Basisdatenbank-Abfrage mit den Themensuchbegriffen
        base_query = base_query.filter(parent_query)
        print(f"DEBUG[SERVER]: Themenfilter mit AND-Verknüpfung angewendet, verbleibende Ergebnisse: {base_query.count()}")
    
    # Jetzt wende den benutzerdefinierten Suchbegriff an, wenn vorhanden
    if q:
        # Teile die Suchanfrage in einzelne Wörter auf
        search_terms = q.strip().split()
        print(f"DEBUG[SERVER]: Suchbegriffe aufgeteilt: {search_terms}")
        
        if len(search_terms) > 1:
            # Initialisiere eine leere Q-Abfrage
            query = Q()
            
            # Je nach logical_op verwenden wir AND oder OR Verknüpfung
            if logical_op == 'AND':
                # Bei AND verwenden wir einen Grundfilter, der alle Einträge enthält
                query = Q(pk__isnull=False)  # Grundfilter, der alle Einträge einschließt
                
                # Jeder Suchbegriff wird mit AND hinzugefügt
                for term in search_terms:
                    if len(term) > 2:  # Ignoriere sehr kurze Wörter
                        # Erstelle eine Teil-Query abhängig von den ausgewählten Feldern
                        term_query = create_field_query(term, selected_fields, False)
                        # Füge diesen Suchbegriff mit UND hinzu
                        query &= term_query
                
                print(f"DEBUG[SERVER]: Verwende UND-Verknüpfung für mehrere Suchbegriffe")
            else:
                # Bei OR verwenden wir die bisherige Logik
                # Verknüpfe jeden Suchbegriff mit ODER
                for term in search_terms:
                    if len(term) > 2:  # Ignoriere sehr kurze Wörter
                        # Erstelle eine Teil-Query abhängig von den ausgewählten Feldern
                        term_query = create_field_query(term, selected_fields, False)
                        # Füge diesen Suchbegriff mit ODER hinzu
                        query |= term_query
                
                print(f"DEBUG[SERVER]: Verwende ODER-Verknüpfung für mehrere Suchbegriffe")
            
            # Anwenden der zusammengebauten Abfrage auf die bereits gefilterte Basisdatenbank-Abfrage
            charts_queryset = base_query.filter(query)
            
            total_count = charts_queryset.count()
            print(f"DEBUG[SERVER]: Gefundene Ergebnisse bei {logical_op}-Suche: {total_count}")
            
            # SQL-Abfrage loggen vor der Sortierung
            print(f"DEBUG[SERVER]: SQL vor Sortierung: {charts_queryset.query}")
            
            # Paginierte Ergebnisse
            charts_queryset = charts_queryset.order_by('-published_date')
            
            # SQL-Abfrage loggen nach der Sortierung
            print(f"DEBUG[SERVER]: SQL nach Sortierung: {charts_queryset.query}")
            
            # Überprüfe, ob Sorting korrekt angewendet wird
            if charts_queryset.exists():
                first_date = charts_queryset.first().published_date if charts_queryset.first().published_date else None
                last_date = charts_queryset.last().published_date if charts_queryset.last().published_date else None
                print(f"DEBUG[SERVER]: Erste Sortier-Datum: {first_date}, Letztes Sortier-Datum: {last_date}")
            
            # Berücksichtige die Paginierung mit offset und limit
            if offset > 0:
                charts = charts_queryset[offset:offset+items_per_page]
            else:
                charts = charts_queryset[page*items_per_page:(page+1)*items_per_page]
        else:
            # Bei einem einzelnen Suchbegriff OR-Verknüpfung verwenden (wie bisher)
            # Erstelle Query abhängig von den ausgewählten Feldern
            query = create_field_query(q, selected_fields, False)
            
            # Filter Ergebnisse auf der bereits gefilterten Basisdatenbank-Abfrage
            charts_queryset = base_query.filter(query)
            
            total_count = charts_queryset.count()
            print(f"DEBUG[SERVER]: Gefundene Ergebnisse bei ODER-Suche nach Ausschluss: {total_count}")
            
            # SQL-Abfrage loggen vor der Sortierung
            print(f"DEBUG[SERVER]: SQL vor Sortierung: {charts_queryset.query}")
            
            # Paginierte Ergebnisse
            charts_queryset = charts_queryset.order_by('-published_date')
            
            # SQL-Abfrage loggen nach der Sortierung
            print(f"DEBUG[SERVER]: SQL nach Sortierung: {charts_queryset.query}")
            
            # Überprüfe, ob Sorting korrekt angewendet wird
            if charts_queryset.exists():
                first_date = charts_queryset.first().published_date if charts_queryset.first().published_date else None
                last_date = charts_queryset.last().published_date if charts_queryset.last().published_date else None
                print(f"DEBUG[SERVER]: Erste Sortier-Datum: {first_date}, Letztes Sortier-Datum: {last_date}")
            
            # Berücksichtige die Paginierung mit offset und limit
            if offset > 0:
                charts = charts_queryset[offset:offset+items_per_page]
            else:
                charts = charts_queryset[page*items_per_page:(page+1)*items_per_page]
    else:
        # Wenn kein Suchbegriff angegeben ist, verwende die Basisdatenbank-Abfrage
        charts_queryset = base_query
            
        total_count = charts_queryset.count()
        print(f"DEBUG[SERVER]: Gesamtanzahl aller Charts nach Ausschluss: {total_count}")
        
        # SQL-Abfrage loggen vor der Sortierung
        print(f"DEBUG[SERVER]: SQL vor Sortierung: {charts_queryset.query}")
        
        # Paginierte Ergebnisse
        charts_queryset = charts_queryset.order_by('-published_date')
        
        # SQL-Abfrage loggen nach der Sortierung
        print(f"DEBUG[SERVER]: SQL nach Sortierung: {charts_queryset.query}")
        
        # Überprüfe, ob Sorting korrekt angewendet wird
        if charts_queryset.exists():
            first_date = charts_queryset.first().published_date if charts_queryset.first().published_date else None
            last_date = charts_queryset.last().published_date if charts_queryset.last().published_date else None
            print(f"DEBUG[SERVER]: Erste Sortier-Datum: {first_date}, Letztes Sortier-Datum: {last_date}")
        
        # Berücksichtige die Paginierung mit offset und limit
        if offset > 0:
            charts = charts_queryset[offset:offset+items_per_page]
        else:
            charts = charts_queryset[page*items_per_page:(page+1)*items_per_page]
    
    print(f"DEBUG[SERVER]: Anzahl der Charts in dieser Seite: {len(charts)}")
    if charts:
        print(f"DEBUG[SERVER]: Beispiel eines Chart-Objekts - Titel: '{charts[0].title}', Datum: {charts[0].published_date}")
    
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
        'has_more': (page + 1) * items_per_page < total_count if offset == 0 else offset + items_per_page < total_count
    }
    print(f"DEBUG[SERVER]: Sende {len(results)} Ergebnisse zurück")
    return JsonResponse(data)

# Hilfsfunktion zum Erstellen der Feldabfrage basierend auf den ausgewählten Feldern
def create_field_query(term, selected_fields, exact_tag_search=False):
    """
    Erstellt eine Datenbankabfrage basierend auf dem Suchbegriff und den ausgewählten Feldern.
    
    Args:
        term: Der Suchbegriff
        selected_fields: Liste der Feldnamen, die durchsucht werden sollen
        exact_tag_search: Wenn True, werden Tag-Suchbegriffe exakt gesucht
    
    Returns:
        Django Q-Objekt für die Datenbankabfrage
    """
    # Überprüfe, ob es sich um einen Feldspezifischen Filter handelt (z.B. "tag: Bildung")
    field_specific_match = re.match(r'^(\w+):\s*(.+)$', term)
    
    if field_specific_match:
        field_type = field_specific_match.group(1).lower()
        search_value = field_specific_match.group(2).strip()
        
        print(f"DEBUG[SERVER]: Feldspezifische Suche erkannt - Feld: {field_type}, Wert: {search_value}")
        
        # Zuordnung der benutzerfreundlichen Feldnamen zu den tatsächlichen Datenbankfeldnamen
        field_mapping = {
            'tag': 'tags',
            'tags': 'tags',
            'titel': 'title',
            'title': 'title',
            'beschreibung': 'description',
            'description': 'description',
            'notiz': 'notes',
            'notes': 'notes',
            'kommentar': 'comments',
            'comment': 'comments',
            'comments': 'comments',
            'autor': 'author',
            'author': 'author',
            'id': 'chart_id',
            'chart_id': 'chart_id'
        }
        
        # Wenn das Feld im Mapping existiert, erstelle eine spezifische Abfrage
        if field_type in field_mapping:
            db_field = field_mapping[field_type]
            
            # Für Tag-Felder: Prüfe, ob exakte Suche aktiviert ist
            if db_field == 'tags' and exact_tag_search:
                print(f"DEBUG[SERVER]: Verwende exakte Tag-Suche für '{search_value}'")
                # Exakte Tag-Suche: Der Tag muss als ganzes Wort vorkommen
                # Verwende reguläre Ausdrücke für exakte Übereinstimmung
                # Der Tag kann am Anfang stehen, am Ende stehen oder von Kommas umgeben sein
                regex_pattern = f'(^|,)\\s*{re.escape(search_value)}\\s*(,|$)'
                return Q(**{f"{db_field}__iregex": regex_pattern})
            else:
                return Q(**{f"{db_field}__icontains": search_value})
        else:
            # Wenn das Feld nicht erkannt wird, führe eine Standardsuche durch
            print(f"DEBUG[SERVER]: Unbekanntes Feldspezifisches Suchfeld: {field_type}, verwende Standardsuche")
    
    # Wenn keine spezifischen Felder ausgewählt sind, suche in allen Standardfeldern
    if not selected_fields:
        return Q(chart_id__icontains=term) | \
               Q(title__icontains=term) | \
               Q(description__icontains=term) | \
               Q(notes__icontains=term) | \
               Q(comments__icontains=term) | \
               Q(embed_js__icontains=term) | \
               Q(tags__icontains=term)
    
    # Erstelle eine leere Q-Abfrage
    query = Q()
    
    # Füge für jedes ausgewählte Feld eine OR-Bedingung hinzu
    for field in selected_fields:
        if field == 'chart_id':
            query |= Q(chart_id__icontains=term)
        elif field == 'title':
            query |= Q(title__icontains=term)
        elif field == 'description':
            query |= Q(description__icontains=term)
        elif field == 'notes':
            query |= Q(notes__icontains=term)
        elif field == 'comments':
            query |= Q(comments__icontains=term)
        elif field == 'tags':
            query |= Q(tags__icontains=term)
        elif field == 'embed_js':
            query |= Q(embed_js__icontains=term)
        elif field == 'author':
            query |= Q(author__icontains=term)
    
    return query

@custom_login_required(login_url='index')
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

@custom_login_required(login_url='index')
def chart_online(request, chart_id):
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
    
    return render(request, 'chart_online.html', context)

@custom_login_required(login_url='index')
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

@custom_login_required(login_url='index')
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


@custom_login_required(login_url='index')
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
            # Wir setzen hier keinen Titel, um die automatische "(Kopie)" zu vermeiden
        }
        
        duplicate_response = requests.post(
            duplicate_url,
            headers={**headers, 'Content-Type': 'application/json'},
            json=duplicate_data
        )
        duplicate_response.raise_for_status()
        new_chart_data = duplicate_response.json()
        new_chart_id = new_chart_data['id']
        
        # 3. Aktualisiere die Metadaten der neuen Grafik
        properties_to_update = {
            "title": data.get('title', '') # Setze den Titel explizit
        }
            
        if data.get('description'):
            if 'metadata' not in properties_to_update:
                properties_to_update['metadata'] = {}
            properties_to_update['metadata']['describe'] = {
                'intro': data.get('description')
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
                width_px = round(float(width_mm) * pixels_per_mm) if width_mm and width_mm != 'auto' else None
                
                # Behandle "auto" für die Höhe
                if height_mm == 'auto' or not height_mm:
                    height_px = None
                else:
                    height_px = round(float(height_mm) * pixels_per_mm)
                
                chart_dimensions = {}
                if width_px:
                    chart_dimensions['width'] = width_px
                if height_px:
                    chart_dimensions['height'] = height_px
                    
                if chart_dimensions:
                    properties_to_update['metadata']['publish']['chart-dimensions'] = chart_dimensions
            except (ValueError, TypeError) as e:
                print(f"Fehler bei der Konvertierung der Dimensionen: {e}")
                print(f"width_mm: {width_mm}, height_mm: {height_mm}")
        
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

@custom_login_required(login_url='index')
def republish_chart(request, chart_id):
    """Dupliziert eine Grafik und aktualisiert sie mit neuen Metadaten"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST-Anfragen werden unterstützt'}, status=405)
    
    try:
        api_key = os.getenv('DATAWRAPPER_API_KEY')
        if not api_key:
            raise Exception("API Key nicht gefunden")
            
        headers = {"Authorization": f"Bearer {api_key}"}
        data = request.POST
        
        # Debug-Ausgabe
        print(f"DEBUG: Eingabedaten für republish_chart: {data}")
        
        # 1. Original-Grafik abrufen, um den Ursprungs-Ordner zu bestimmen
        original_chart_url = f"https://api.datawrapper.de/v3/charts/{chart_id}"
        
        original_response = requests.get(original_chart_url, headers=headers)
        original_response.raise_for_status()
        original_chart_data = original_response.json()
        
        # Ursprünglichen Ordner-ID bestimmen
        original_folder_id = original_chart_data.get('folderId')
        
        # 2. Grafik duplizieren im selben Ordner
        duplicate_url = f"https://api.datawrapper.de/v3/charts/{chart_id}/copy"
        
        # Erstelle die Duplizierungsdaten ohne Titel, um die "(Kopie)" zu vermeiden
        duplicate_data = {
            "folderId": original_folder_id
        }
        
        duplicate_response = requests.post(
            duplicate_url,
            headers={**headers, 'Content-Type': 'application/json'},
            json=duplicate_data
        )
        duplicate_response.raise_for_status()
        new_chart_data = duplicate_response.json()
        new_chart_id = new_chart_data['id']
        
        print(f"DEBUG: Neue Grafik erstellt mit ID: {new_chart_id}")
        
        # 3. Aktualisiere die Metadaten der neuen Grafik mit explizitem Titel
        properties_to_update = {}
        
        # Titel explizit setzen
        if data.get('title'):
            properties_to_update['title'] = data.get('title')
        
        # Beschreibung setzen
        if data.get('description'):
            if 'metadata' not in properties_to_update:
                properties_to_update['metadata'] = {}
            if 'describe' not in properties_to_update['metadata']:
                properties_to_update['metadata']['describe'] = {}
            
            properties_to_update['metadata']['describe']['intro'] = data.get('description')
            
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
                width_px = round(float(width_mm) * pixels_per_mm) if width_mm and width_mm != 'auto' else None
                
                # Behandle "auto" für die Höhe
                if height_mm == 'auto' or not height_mm:
                    height_px = None
                else:
                    height_px = round(float(height_mm) * pixels_per_mm)
                
                chart_dimensions = {}
                if width_px:
                    chart_dimensions['width'] = width_px
                if height_px:
                    chart_dimensions['height'] = height_px
                    
                if chart_dimensions:
                    properties_to_update['metadata']['publish']['chart-dimensions'] = chart_dimensions
            except (ValueError, TypeError) as e:
                print(f"Fehler bei der Konvertierung der Dimensionen: {e}")
                print(f"width_mm: {width_mm}, height_mm: {height_mm}")
        
        # Farben aktualisieren
        if data.get('colors'):
            try:
                import json
                colors = json.loads(data.get('colors'))
                if 'metadata' not in properties_to_update:
                    properties_to_update['metadata'] = {}
                if 'visualize' not in properties_to_update['metadata']:
                    properties_to_update['metadata']['visualize'] = {}
                properties_to_update['metadata']['visualize']['custom-colors'] = colors
            except json.JSONDecodeError as e:
                print(f"Error decoding colors JSON: {e}")
                print("Raw colors data:", data.get('colors'))
        
        # 4. Grafik aktualisieren, wenn Änderungen vorliegen
        if properties_to_update:
            update_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}"
            
            print(f"DEBUG: Update Metadaten: {properties_to_update}")
            
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
        
        # 6. Metadaten und Thumbnail für die Datenbank abrufen
        metadata_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}"
        metadata_response = requests.get(metadata_url, headers=headers)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        
        # Besorge das PNG direkt von der Export-API (besser als Thumbnail)
        export_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}/export/png"
        export_params = {
            'width': 1200,  # Höhere Auflösung für bessere Qualität
            'height': 800,  # Höhere Auflösung für bessere Qualität
            'plain': 'false',
            'zoom': '2',    # Erhöhter Zoom-Faktor für bessere Qualität
            'scale': '2',   # Erhöhter Skalierungsfaktor für bessere Qualität
            'transparent': 'false',
            'logo': 'auto',
            'dark': 'false'
        }
        
        export_response = requests.get(export_url, headers=headers, params=export_params)
        export_status = export_response.status_code
        
        # Logge das Ergebnis des Export-Aufrufs
        print(f"DEBUG: PNG-Export Status für {new_chart_id}: {export_status}")
        
        # 7. In der Datenbank speichern
        # Prüfen, ob die Grafik bereits in der Datenbank existiert
        existing_chart = Chart.objects.filter(chart_id=new_chart_id).first()
        
        if existing_chart:
            # Aktualisiere vorhandene Grafik
            chart_model = existing_chart
        else:
            # Erstelle neue Grafik
            chart_model = Chart(chart_id=new_chart_id)
        
        # Aktualisiere Metadaten
        # Verwende die Werte aus der Anfrage anstatt die von der API zurückgegebenen Werte
        chart_model.title = data.get('title') or metadata.get('title', '')
        chart_model.description = data.get('description') or metadata.get('metadata', {}).get('describe', {}).get('intro', '')
        chart_model.last_modified_date = timezone.now()
        chart_model.published_date = timezone.now()
        
        # URL für iframe und JS-Code
        chart_model.iframe_url = f"https://datawrapper.dwcdn.net/{new_chart_id}/1/"
        chart_model.embed_js = f'<script src="https://static.rndtech.de/share/rnd/datenrecherche/script/dw_chart_min.js" defer></script>\n<dw-chart\n    chart-id="{new_chart_id}">\n</dw-chart>'
        
        # Tags aus der alten Grafik übernehmen
        original_chart = Chart.objects.filter(chart_id=chart_id).first()
        if original_chart:
            chart_model.tags = original_chart.tags
            chart_model.evergreen = original_chart.evergreen
            chart_model.regional = original_chart.regional
            chart_model.patch = original_chart.patch
            chart_model.notes = original_chart.notes
        
        # Speichere das Modell, um eine ID zu erhalten (für Thumbnail)
        chart_model.save()
        
        # Thumbnail aus dem PNG erstellen und speichern
        if export_status == 200:
            try:
                # Erstelle Thumbnail-Dateinamen und -Pfad
                thumbnail_filename = f"{new_chart_id}.png"
                thumbnail_dir = os.path.join(settings.MEDIA_ROOT, 'thumbnails')
                os.makedirs(thumbnail_dir, exist_ok=True)
                thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
                
                # Bild laden und auf Thumbnail-Größe bringen (600x400px ist eine gute Größe für Thumbnails)
                with Image.open(io.BytesIO(export_response.content)) as img:
                    thumbnail_size = (600, 400)
                    
                    # Verwende LANCZOS, falls verfügbar, sonst ANTIALIAS für ältere PIL-Versionen
                    try:
                        img.thumbnail(thumbnail_size, Image.LANCZOS)
                    except AttributeError:
                        # Fallback für ältere PIL-Versionen
                        try:
                            img.thumbnail(thumbnail_size, Image.ANTIALIAS)
                        except AttributeError:
                            # Letzter Fallback ohne Filterangabe
                            img.thumbnail(thumbnail_size)
                    
                    # Speichere das Thumbnail auf der Festplatte
                    img.save(thumbnail_path, 'PNG')
                
                print(f"DEBUG: Thumbnail für {new_chart_id} gespeichert unter {thumbnail_path}")
                
                # Setze den relativen Pfad für das Thumbnail-Feld des Chart-Modells
                chart_model.thumbnail.name = os.path.join('thumbnails', thumbnail_filename)
                chart_model.save()
            except Exception as thumbnail_error:
                print(f"Fehler beim Speichern des Thumbnails: {thumbnail_error}")
                # Stelle sicher, dass kein Thumbnail-Attribut gesetzt ist
                chart_model.thumbnail = None
                chart_model.save()
        else:
            # Versuche alternativ, das Thumbnail direkt zu verwenden
            thumbnail_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}/thumbnail"
            thumbnail_response = requests.get(thumbnail_url, headers=headers)
            
            if thumbnail_response.status_code == 200:
                try:
                    # Erstelle Thumbnail-Dateinamen und -Pfad
                    thumbnail_filename = f"{new_chart_id}.png"
                    thumbnail_dir = os.path.join(settings.MEDIA_ROOT, 'thumbnails')
                    os.makedirs(thumbnail_dir, exist_ok=True)
                    thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
                    
                    # Bild laden und auf Thumbnail-Größe bringen (600x400px ist eine gute Größe für Thumbnails)
                    with Image.open(io.BytesIO(thumbnail_response.content)) as img:
                        thumbnail_size = (600, 400)
                        
                        # Verwende LANCZOS, falls verfügbar, sonst ANTIALIAS für ältere PIL-Versionen
                        try:
                            img.thumbnail(thumbnail_size, Image.LANCZOS)
                        except AttributeError:
                            # Fallback für ältere PIL-Versionen
                            try:
                                img.thumbnail(thumbnail_size, Image.ANTIALIAS)
                            except AttributeError:
                                # Letzter Fallback ohne Filterangabe
                                img.thumbnail(thumbnail_size)
                        
                        # Speichere das Thumbnail
                        img.save(thumbnail_path, 'PNG')
                    
                    print(f"DEBUG: Thumbnail aus Thumbnail-API für {new_chart_id} gespeichert unter {thumbnail_path}")
                    
                    # Setze den relativen Pfad für das Thumbnail-Feld des Chart-Modells
                    chart_model.thumbnail.name = os.path.join('thumbnails', thumbnail_filename)
                    chart_model.save()
                except Exception as thumbnail_error:
                    print(f"Fehler beim Speichern des Thumbnails (Fallback): {thumbnail_error}")
                    chart_model.thumbnail = None
                    chart_model.save()
            else:
                # Stelle sicher, dass kein Thumbnail-Attribut gesetzt ist
                chart_model.thumbnail = None
                chart_model.save()
                print(f"Konnte kein Thumbnail für {new_chart_id} erstellen")
        
        # Rückkehr zur neuen Grafik-Detailseite
        return JsonResponse({
            'success': True,
            'chart_id': new_chart_id,
            'redirect_url': f"/chart/{new_chart_id}/"
        })
        
    except Exception as e:
        error_message = str(e)
        if isinstance(e, requests.exceptions.RequestException) and hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_message = error_data.get('message', str(e))
            except:
                error_message = e.response.text or str(e)
        
        return JsonResponse({'error': f'Fehler beim Ausspielen der Grafik: {error_message}'}, status=500)

# Hilfsfunktionen zur Berechtigungsprüfung
def is_creator(user):
    return user.groups.filter(name='creator').exists()

def is_buddy(user):
    return user.groups.filter(name='buddies').exists()

@custom_login_required(login_url='index')
@user_passes_test(is_creator, login_url='archive_main')
def chartmaker(request):
    """View für den Chartmaker - nur für creator-Gruppe zugänglich"""
    return render(request, 'chartmaker.html')

@custom_login_required(login_url='index')
@user_passes_test(is_buddy, login_url='archive_main')
def databuddies(request):
    """View für die Databuddies-Seite - nur für buddies-Gruppe zugänglich"""
    return render(request, 'databuddies.html')


@custom_login_required(login_url='index')
@user_passes_test(is_buddy, login_url='archive_main')
def analyze_data(request):
    """Analysiert hochgeladene Datendateien oder Chat-Nachrichten - nur für buddies-Gruppe"""
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


@custom_login_required(login_url='index')
@user_passes_test(is_creator, login_url='archive_main')
def create_datawrapper_chart(request):
    """Erstellt eine neue Datawrapper-Grafik - nur für creator-Gruppe"""
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

def login_modal(request):
    if request.method == 'POST':
        # Passwort-Manager senden 'username' statt 'email', daher müssen wir das berücksichtigen
        post_data = request.POST.copy()
        if 'username' in post_data and 'email' not in post_data:
            # Kopiere den Wert von 'username' nach 'email' für die Formularvalidierung
            post_data['email'] = post_data['username']
        
        form = LoginForm(post_data)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data['remember_me']
            
            # Da das Django-Standard-Login mit username statt email arbeitet,
            # müssen wir erst den Nutzer anhand der E-Mail suchen
            try:
                user = User.objects.get(email=email)
                # Dann mit dem gefundenen Benutzernamen authentifizieren
                user = authenticate(request, username=user.username, password=password)
                if user is not None:
                    login(request, user)
                    
                    # Session-Ablaufzeit setzen (2 Wochen, wenn remember_me aktiviert ist)
                    if remember_me:
                        request.session.set_expiry(1209600)  # 2 Wochen in Sekunden
                    else:
                        request.session.set_expiry(0)  # Beim Schließen des Browsers löschen
                    
                    # Auf die Hauptseite des Archivs weiterleiten
                    return redirect('archive_main')
                else:
                    # Authentifizierung fehlgeschlagen
                    messages.error(request, "E-Mail-Adresse oder Passwort ist falsch.")
                    # Speichere die eingegebene E-Mail-Adresse für Wiederanzeige
                    login_form = LoginForm(initial={'email': email, 'remember_me': remember_me})
                    return render(request, 'index.html', {'login_form': login_form})
            except User.DoesNotExist:
                messages.error(request, "Kein Benutzer mit dieser E-Mail-Adresse gefunden.")
                # Speichere die eingegebene E-Mail-Adresse für Wiederanzeige
                login_form = LoginForm(initial={'email': email, 'remember_me': remember_me})
                return render(request, 'index.html', {'login_form': login_form})
        else:
            # Formular ungültig - wir geben die eingegebene E-Mail zurück
            if 'email' in form.data:
                email = form.data['email']
                remember_me = 'remember_me' in form.data
                login_form = LoginForm(initial={'email': email, 'remember_me': remember_me})
                return render(request, 'index.html', {'login_form': login_form})
    else:
        form = LoginForm()
    
    return redirect('index')

def password_reset_request_view(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            
            # Debug-Ausgabe zur Problemdiagnose
            print(f"DEBUG: Passwort-Reset angefragt für E-Mail: {email}")
            
            try:
                user = User.objects.get(email=email)
                print(f"DEBUG: Benutzer gefunden: {user.username} (ID: {user.id})")
                
                # Alten, unbenutzten Token für diesen User ggf. als benutzt markieren oder löschen
                old_tokens = PasswordResetToken.objects.filter(user=user, used=False)
                old_token_count = old_tokens.count()
                old_tokens.update(used=True)
                print(f"DEBUG: {old_token_count} alte Token(s) als benutzt markiert.")

                token_value = generate_token() # Wiederverwendung der bestehenden Token-Generierung
                print(f"DEBUG: Neuer Token generiert: {token_value[:10]}...")
                
                PasswordResetToken.objects.create(user=user, token=token_value)
                print(f"DEBUG: Token in Datenbank gespeichert.")
                
                email_sent = send_password_reset_email(email, token_value, request)
                if email_sent:
                    print(f"DEBUG: E-Mail erfolgreich versendet (bzw. in Konsole ausgegeben).")
                    messages.success(request, 'Wir haben dir eine E-Mail mit Anweisungen zum Zurücksetzen deines Passworts gesendet. Dies kann einige Minuten dauern. Bitte überprüfe dein Postfach.')
                else:
                    print(f"DEBUG: Fehler beim Versenden der E-Mail.")
                    messages.error(request, 'Die E-Mail zum Zurücksetzen des Passworts konnte nicht gesendet werden. Bitte versuche es später erneut.')
            
            except User.DoesNotExist:
                print(f"DEBUG: Kein Benutzer mit der E-Mail-Adresse {email} gefunden.")
                messages.error(request, f"Es existiert kein Konto mit der E-Mail-Adresse {email}.")
                return render(request, 'password_reset_request.html', {'form': form})
                
            return redirect('index') # Oder eine spezielle 'Passwort-Reset-E-Mail gesendet'-Seite
        else:
            # Bei ungültigen Formulardaten Fehler anzeigen
            print(f"DEBUG: Formular ungültig. Fehler: {form.errors}")
    else:
        form = PasswordResetRequestForm()
    
    return render(request, 'password_reset_request.html', {'form': form})

def password_reset_confirm_view(request, token):
    try:
        password_reset_token = PasswordResetToken.objects.get(token=token, used=False)
        # Token-Gültigkeitsdauer prüfen (z.B. 1 Stunde)
        if (timezone.now() - password_reset_token.created_at).total_seconds() > 3600:
            messages.error(request, 'Der Link zum Zurücksetzen des Passworts ist abgelaufen. Bitte fordere einen neuen an.')
            password_reset_token.used = True # Als verbraucht markieren
            password_reset_token.save()
            return redirect('password_reset_request')
    except PasswordResetToken.DoesNotExist:
        messages.error(request, 'Ungültiger oder bereits verwendeter Link zum Zurücksetzen des Passworts.')
        return redirect('password_reset_request')

    if request.method == 'POST':
        form = CustomSetPasswordForm(request.POST)
        if form.is_valid():
            user = password_reset_token.user
            user.set_password(form.cleaned_data['new_password1'])
            user.save()
            
            password_reset_token.used = True
            password_reset_token.save()
            
            # Wichtig, damit der User nicht mit alter Session eingeloggt bleibt, falls er es war
            # Wenn du Djangos auth views nutzt, passiert das oft automatisch.
            # Hier manuell, da wir nicht wissen, ob der User aktuell eingeloggt ist.
            # update_session_auth_hash(request, user) # Kann Fehler werfen, wenn User nicht eingeloggt ist.
            # Sicherer ist es, den User explizit auszuloggen, falls eine Session besteht.
            if request.user.is_authenticated and request.user.pk == user.pk:
                 logout(request) # Loggt den aktuellen User aus, wenn es der betroffene User ist.

            messages.success(request, 'Dein Passwort wurde erfolgreich zurückgesetzt. Du kannst dich jetzt mit deinem neuen Passwort anmelden.')
            return redirect('index') # Zum Login oder zur Startseite
    else:
        form = CustomSetPasswordForm()
    
    return render(request, 'password_reset_confirm.html', {
        'form': form,
        'token': token
    })

def clear_registration(request, email=None):
    """
    Admin-Funktion zum vollständigen Löschen einer Registrierung.
    Erfordert Admin-Rechte, da sie potenziell gefährlich ist.
    """
    if not request.user.is_superuser:
        messages.error(request, "Nur Administratoren können diese Funktion nutzen.")
        return redirect('index')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            messages.error(request, "Bitte gib eine E-Mail-Adresse an.")
            return render(request, 'clear_registration.html')
        
        # Registrierungen löschen
        reg_count = RegistrationConfirmation.objects.filter(email=email).delete()[0]
        
        # Passwort-Reset-Tokens löschen
        token_count = PasswordResetToken.objects.filter(user__email=email).delete()[0]
        
        # Benutzer löschen
        user_count = User.objects.filter(email=email).delete()[0]
        
        messages.success(request, f"Registrierung für {email} vollständig gelöscht. Gelöschte Datensätze: {reg_count} Registrierungen, {token_count} Tokens, {user_count} Benutzer.")
        return redirect('admin:index')
    
    return render(request, 'clear_registration.html', {'email': email})

@custom_login_required(login_url='index')
def export_chart_to_dcx(request, chart_id):
    """Exportiert eine Grafik als PDF und lädt sie auf den DCX-FTP-Server hoch"""
    try:
        # FTP-Zugangsdaten aus Umgebungsvariablen holen
        ftp_server = os.getenv('FTP_SERVER')
        ftp_user = os.getenv('FTP_USER')
        ftp_password = os.getenv('FTP_PASSWORD')
        
        # Prüfen, ob alle erforderlichen Zugangsdaten vorhanden sind
        if not all([ftp_server, ftp_user, ftp_password]):
            return JsonResponse({
                'success': False,
                'error': 'FTP-Zugangsdaten sind nicht vollständig konfiguriert.'
            }, status=500)
        
        # Parameter aus der Anfrage auslesen
        data = request.POST
        width_mm = data.get('width')
        height_mm = data.get('height', 'auto')
        title = data.get('title', '')
        description = data.get('description', '')
        ftp_folder = data.get('ftp_folder', 'Grafik')
        
        # API-Schlüssel und Header für Datawrapper-API
        api_key = os.getenv('DATAWRAPPER_API_KEY')
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # 1. Grafik duplizieren, um Änderungen zu übernehmen
        duplicate_url = f"https://api.datawrapper.de/v3/charts/{chart_id}/copy"
        
        duplicate_response = requests.post(duplicate_url, headers=headers)
        duplicate_response.raise_for_status()
        
        duplicate_data = duplicate_response.json()
        new_chart_id = duplicate_data.get('id')
        
        # 2. Eigenschaften der duplizierten Grafik aktualisieren
        properties_to_update = {}
        
        # Titel aktualisieren, falls vorhanden
        if title:
            properties_to_update['title'] = title
            properties_to_update['metadata'] = {
                'describe': {
                    'title': title
                }
            }
        
        # Beschreibung aktualisieren, falls vorhanden
        if description:
            if 'metadata' not in properties_to_update:
                properties_to_update['metadata'] = {}
            if 'describe' not in properties_to_update['metadata']:
                properties_to_update['metadata']['describe'] = {}
            properties_to_update['metadata']['describe']['intro'] = description
        
        # Dimensionen aktualisieren
        if width_mm or height_mm:
            if 'metadata' not in properties_to_update:
                properties_to_update['metadata'] = {}
            if 'publish' not in properties_to_update['metadata']:
                properties_to_update['metadata']['publish'] = {}
            
            # Berechne Pixel aus mm (96 DPI / 25.4 mm/inch)
            pixels_per_mm = 96 / 25.4
            
            chart_dimensions = {}
            if width_mm:
                if width_mm.isdigit() or (width_mm.replace('.', '', 1).isdigit() and width_mm.count('.') < 2):
                    chart_dimensions['width'] = round(float(width_mm) * pixels_per_mm)
            
            if height_mm and height_mm != 'auto':
                if height_mm.isdigit() or (height_mm.replace('.', '', 1).isdigit() and height_mm.count('.') < 2):
                    chart_dimensions['height'] = round(float(height_mm) * pixels_per_mm)
            
            if chart_dimensions:
                properties_to_update['metadata']['publish']['chart-dimensions'] = chart_dimensions
        
        # Farben aktualisieren
        if data.get('colors'):
            try:
                colors = json.loads(data.get('colors'))
                if 'metadata' not in properties_to_update:
                    properties_to_update['metadata'] = {}
                if 'visualize' not in properties_to_update['metadata']:
                    properties_to_update['metadata']['visualize'] = {}
                properties_to_update['metadata']['visualize']['color-category'] = {
                    'map': colors
                }
            except json.JSONDecodeError as e:
                print(f"Error decoding colors JSON: {e}")
                print("Raw colors data:", data.get('colors'))
        
        # 3. Grafik aktualisieren
        if properties_to_update:
            update_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}"
            
            update_response = requests.patch(
                update_url,
                headers={**headers, 'Content-Type': 'application/json'},
                json=properties_to_update
            )
            update_response.raise_for_status()
        
        # 4. Grafik publishen
        publish_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}/publish"
        
        publish_response = requests.post(publish_url, headers=headers)
        publish_response.raise_for_status()
        
        # 5. PDF exportieren mit den korrekten Parametern
        export_params = {
            'unit': 'mm',
            'mode': 'rgb',
            'plain': 'false',
            'scale': '0.7',
            'zoom': '1',
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
                export_params['height'] = height_mm
        except Exception as e:
            print(f"Fehler beim Setzen der Export-Parameter: {e}")
            export_params['width'] = '210'  # A4 Breite
            export_params['height'] = 'auto'
            
        export_url = f"https://api.datawrapper.de/v3/charts/{new_chart_id}/export/pdf"
        
        export_response = requests.get(
            export_url,
            headers=headers,
            params=export_params
        )
        export_response.raise_for_status()
        
        # PDF-Inhalt als Binärdaten
        pdf_content = export_response.content
        
        # 6. PDF auf FTP-Server hochladen
        # Erstelle einen sinnvollen Dateinamen
        safe_title = "".join([c if c.isalnum() or c in ['-', '_'] else '_' for c in title])
        if len(safe_title) > 30:
            safe_title = safe_title[:30]
        
        filename = f"{safe_title}_{chart_id}.pdf"
        
        # Verbindung zum FTP-Server herstellen mit FTPS (FTP mit TLS)
        ftps = FTP_TLS(ftp_server)
        ftps.login(ftp_user, ftp_password)
        ftps.prot_p()  # Daten-Verschlüsselung aktivieren
        
        # Prüfen, ob der Zielordner existiert
        try:
            # Versuche in den Zielordner zu wechseln
            ftps.cwd(ftp_folder)
        except Exception as e:
            # Ordner existiert nicht, versuche ihn zu erstellen
            try:
                ftps.mkd(ftp_folder)
                ftps.cwd(ftp_folder)
            except Exception as mkdir_error:
                ftps.quit()
                return JsonResponse({
                    'success': False,
                    'error': f'Fehler beim Erstellen des FTP-Ordners: {str(mkdir_error)}'
                }, status=500)
        
        # PDF hochladen
        try:
            ftps.storbinary(f'STOR {filename}', io.BytesIO(pdf_content))
            ftps.quit()
            
            return JsonResponse({
                'success': True,
                'message': 'PDF wurde erfolgreich auf den FTP-Server hochgeladen',
                'filename': filename,
                'destination': f'{ftp_folder}/{filename}'
            })
        except Exception as upload_error:
            ftps.quit()
            return JsonResponse({
                'success': False,
                'error': f'Fehler beim Hochladen des PDFs: {str(upload_error)}'
            }, status=500)
            
    except Exception as e:
        error_msg = str(e)
        if isinstance(e, requests.exceptions.RequestException) and hasattr(e, 'response'):
            error_msg = f"{error_msg} - API Response: {e.response.text}"
        
        print(f"Error during DCX export: {error_msg}")
        return JsonResponse({'success': False, 'error': error_msg}, status=500)