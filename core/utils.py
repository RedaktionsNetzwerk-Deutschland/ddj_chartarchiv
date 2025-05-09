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
    
    Args:
        name: Der Name des Nutzers
        email: Die E-Mail-Adresse des Nutzers
        token: Das Bestätigungstoken
        request: Das Request-Objekt für die Domain-Generierung
    
    Returns:
        bool: True, wenn die E-Mail erfolgreich gesendet wurde, sonst False
    """
    print("DEBUG: send_confirmation_email WURDE AUFGERUFEN")
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
        
        # Sende die E-Mail
        print("DEBUG: VOR email_message.send()")
        email_message.send()
        print("DEBUG: NACH email_message.send()")
        return True
    
    except Exception as e:
        print(f"Fehler beim Senden der Bestätigungs-E-Mail: {e}")
        return False 

def send_password_reset_email(user_email, token, request):
    """
    Sendet eine E-Mail zum Zurücksetzen des Passworts.
    """
    try:
        protocol = "https" if request.is_secure() else "http"
        domain = request.get_host()
        reset_url = f"{protocol}://{domain}{reverse('password_reset_confirm', kwargs={'token': token})}"
        
        context = {
            'reset_url': reset_url,
            'user': User.objects.get(email=user_email) # Für personalisierte Anrede
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
        email_message.send()
        print(f"DEBUG: Passwort-Reset E-Mail an {user_email} gesendet. URL: {reset_url}")
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