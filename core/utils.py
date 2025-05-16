import os
import uuid
import hashlib
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages

def generate_token():
    """
    Erzeugt ein eindeutiges Token für die E-Mail-Bestätigung.
    """
    random_uuid = uuid.uuid4()
    timestamp = timezone.now().timestamp()
    token_input = f"{random_uuid}_{timestamp}"
    
    # SHA-256 Hash generieren
    token = hashlib.sha256(token_input.encode()).hexdigest()
    return token

def send_confirmation_email(name, email, token, request):
    """
    Sendet eine Bestätigungsmail an den Nutzer.
    In der Entwicklungsumgebung wird die E-Mail in der Konsole angezeigt.
    
    Args:
        name: Der Name des Nutzers
        email: Die E-Mail-Adresse des Nutzers
        token: Das Bestätigungstoken
        request: Das Request-Objekt für die Domain-Generierung
    
    Returns:
        bool: True, wenn die E-Mail erfolgreich gesendet wurde, sonst False
    """
    try:
        # Erstelle den Bestätigungslink mit der aktuellen Domain
        protocol = "https" if request.is_secure() else "http"
        domain = request.get_host()
        confirmation_url = f"{protocol}://{domain}/confirm/{token}/"
        
        # Kontext für die E-Mail-Vorlage
        context = {
            'name': name,
            'confirmation_url': confirmation_url
        }
        
        # Rendere die HTML- und Text-Version der E-Mail
        html_content = render_to_string('email/confirmation_email.html', context)
        text_content = render_to_string('email/confirmation_email.txt', context)
        
        # Erstelle die E-Mail
        subject = "Bestätige deine Registrierung bei der rnd-Grafik-Bibliothek"
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@rnd.de')
        
        # Erstelle eine E-Mail mit Text- und HTML-Version
        email_message = EmailMultiAlternatives(
            subject,
            text_content,
            from_email,
            [email]
        )
        email_message.attach_alternative(html_content, "text/html")
        
        # Konsolen-Ausgabe für bessere Lesbarkeit in der Entwicklungsumgebung
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            console_separator = "\n" + "="*80 + "\n"
            print(console_separator)
            print(f"REGISTRIERUNGS-BESTÄTIGUNGS-E-MAIL")
            print(f"Gesendet an: {email} (Name: {name})")
            print(f"Betreff: {subject}")
            print(console_separator)
            print("TEXT VERSION:")
            print(text_content)
            print(console_separator)
            print("BESTÄTIGUNGS-LINK:")
            print(confirmation_url)
            print(console_separator)
        
        # Sende die E-Mail
        email_message.send()
        return True
    
    except Exception as e:
        print(f"Fehler beim Senden der Bestätigungs-E-Mail: {e}")
        return False 

def send_password_reset_email(user_email, token, request):
    """
    Sendet eine E-Mail zum Zurücksetzen des Passworts.
    In der Entwicklungsumgebung wird die E-Mail in der Konsole angezeigt.
    """
    try:
        protocol = "https" if request.is_secure() else "http"
        domain = request.get_host()
        reset_url = f"{protocol}://{domain}/password-reset-confirm/{token}/"
        
        # Nutzer holen für die personalisierte Anrede
        user = User.objects.get(email=user_email)

        context = {
            'reset_url': reset_url,
            'user': user
        }
        
        html_content = render_to_string('email/password_reset_email.html', context)
        text_content = render_to_string('email/password_reset_email.txt', context)
        
        subject = "Setze dein Passwort für die rnd-Grafik-Bibliothek zurück"
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@rnd.de')
        
        email_message = EmailMultiAlternatives(
            subject,
            text_content,
            from_email,
            [user_email]
        )
        email_message.attach_alternative(html_content, "text/html")
        
        # Konsolen-Ausgabe für bessere Lesbarkeit in der Entwicklungsumgebung
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            console_separator = "\n" + "="*80 + "\n"
            print(console_separator)
            print(f"PASSWORD RESET E-MAIL")
            print(f"Gesendet an: {user_email} (Benutzer: {user.username})")
            print(f"Betreff: {subject}")
            print(console_separator)
            print("TEXT VERSION:")
            print(text_content)
            print(console_separator)
            print("LINK ZUM ZURÜCKSETZEN:")
            print(reset_url)
            print(console_separator)
        
        # E-Mail senden (in Entwicklung an Konsole)
        email_message.send()
        return True
    except Exception as e:
        print(f"Fehler beim Senden der Passwort-Reset-E-Mail: {e}")
        return False 

def custom_login_required(function=None, redirect_field_name='next', login_url='index'):
    """
    Erweiterter login_required-Decorator, der eine Nachricht setzt, 
    wenn ein nicht eingeloggter Benutzer eine geschützte Seite aufrufen möchte.
    """
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    
    if function:
        # Wenn die Funktion direkt übergeben wurde
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                # Füge eine Nachricht hinzu, wenn der Benutzer nicht angemeldet ist
                messages.warning(
                    request, 
                    "Du musst dich anmelden oder registrieren, um auf diese Seite zuzugreifen."
                )
            return actual_decorator(function)(request, *args, **kwargs)
        return wrapper
    
    # Wenn der Decorator mit Argumenten aufgerufen wurde
    return lambda deferred_function: custom_login_required(deferred_function, redirect_field_name, login_url) 

def cleanup_stale_registrations(days=1):
    """
    Bereinigt veraltete Registrierungsbestätigungen, die älter als die angegebene Anzahl von Tagen sind.
    Dies betrifft sowohl bestätigte als auch unbestätigte Registrierungen, die keinen entsprechenden Benutzer
    in der auth_user-Tabelle haben.
    
    Args:
        days: Anzahl der Tage, nach denen eine Registrierung als veraltet gilt (Standard: 1)
        
    Returns:
        int: Anzahl der gelöschten Registrierungen
    """
    from django.utils import timezone
    from datetime import timedelta
    from core.models import RegistrationConfirmation
    from django.contrib.auth.models import User
    
    # Berechne das Cutoff-Datum
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Hole alle alten Registrierungen
    old_registrations = RegistrationConfirmation.objects.filter(created_at__lt=cutoff_date)
    
    count = 0
    for reg in old_registrations:
        # Prüfe, ob ein entsprechender Benutzer existiert
        if not User.objects.filter(email=reg.email).exists():
            print(f"Lösche veraltete Registrierung für {reg.email} (erstellt am {reg.created_at})")
            reg.delete()
            count += 1
    
    return count 