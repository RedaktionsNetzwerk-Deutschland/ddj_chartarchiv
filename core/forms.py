from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.safestring import mark_safe
import re
from .models import AllowedEmailDomain, AllowedEmailAddress, RegistrationConfirmation

class RegistrationForm(forms.Form):
    name = forms.CharField(
        label="Name",
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'Vorname Name',
            'autocomplete': 'name',
        }),
        error_messages={
            'required': 'Bitte gib deinen Namen ein.'
        }
    )
    email = forms.EmailField(
        label="E-Mail",
        widget=forms.EmailInput(attrs={
            'placeholder': 'name@beispiel.de',
            'autocomplete': 'email',
        }),
        error_messages={
            'required': 'Bitte gib deine E-Mail-Adresse ein.',
            'invalid': 'Bitte gib eine gültige E-Mail-Adresse ein.'
        }
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # Vorhandene Regex-Validierung (oft von Django EmailField abgedeckt, aber hier beibehalten)
        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValidationError("Bitte gib eine gültige E-Mail-Adresse ein.")
            
        # NEUE PRÜFUNG: Überprüfen, ob die E-Mail-Adresse in der Whitelist ist
        # 1. Prüfen, ob die vollständige E-Mail-Adresse in der AllowedEmailAddress-Tabelle ist
        email_allowed = AllowedEmailAddress.objects.filter(email=email, is_active=True).exists()
        
        # 2. Wenn nicht, prüfen, ob die E-Mail-Domain in der AllowedEmailDomain-Tabelle ist
        if not email_allowed:
            domain = email.split('@')[-1].lower()
            domain_allowed = AllowedEmailDomain.objects.filter(domain=domain, is_active=True).exists()
            
            if not domain_allowed:
                raise ValidationError("Deine E-Mail-Adresse oder Domain ist nicht für die Registrierung berechtigt. Bitte wende dich zur Freischaltung an christoph.knoop@rnd.de")

        # NEUE PRÜFUNG: Existiert die E-Mail bereits in der User-Tabelle? (auth_user)
        if User.objects.filter(email=email).exists():
            password_reset_url = reverse('password_reset_request')
            error_html = mark_safe(
                f'Deine E-Mail ist bereits registriert. <a href="{password_reset_url}" style="color: #007bff; text-decoration: underline;">Passwort vergessen?</a>'
            )
            raise ValidationError(error_html)
            
        # NEUE PRÜFUNG: Prüfe, ob eine bestätigte Registrierung existiert, aber kein Benutzer
        try:
            reg = RegistrationConfirmation.objects.get(email=email)
            if reg.confirmed and not User.objects.filter(email=email).exists():
                # Wir haben eine bestätigte Registrierung ohne Benutzer gefunden
                # Wir setzen sie automatisch zurück
                reg.confirmed = False
                reg.confirmed_at = None
                reg.token = None  # Das neue Token wird später beim Speichern generiert
                reg.save()
                print(f"DEBUG: Eine bestätigte Registrierung ohne Benutzer für {email} wurde automatisch zurückgesetzt")
        except RegistrationConfirmation.DoesNotExist:
            pass  # Keine Registrierung gefunden, alles in Ordnung
            
        return email

class LoginForm(forms.Form):
    email = forms.EmailField(
        label="E-Mail",
        widget=forms.EmailInput(attrs={
            'placeholder': 'E-Mail-Adresse eingeben',
            'autocomplete': 'username email',
            'name': 'username',
        }),
        error_messages={
            'required': 'Bitte gib deine E-Mail-Adresse ein.',
            'invalid': 'Bitte gib eine gültige E-Mail-Adresse ein.'
        }
    )
    password = forms.CharField(
        label="Passwort",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Passwort eingeben',
            'autocomplete': 'current-password',
            'data-lpignore': 'false',
        }),
        error_messages={
            'required': 'Bitte gib dein Passwort ein.'
        }
    )
    remember_me = forms.BooleanField(
        label="Eingeloggt bleiben",
        required=False,
        initial=True,
        widget=forms.CheckboxInput()
    )

class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="E-Mail-Adresse",
        widget=forms.EmailInput(attrs={
            'placeholder': 'name@beispiel.de',
            'autocomplete': 'email'
        }),
        error_messages={
            'required': 'Bitte gib deine E-Mail-Adresse ein.',
            'invalid': 'Bitte gib eine gültige E-Mail-Adresse ein.'
        }
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Prüfe nur in der auth_user-Tabelle, ob die E-Mail existiert
        if not User.objects.filter(email=email).exists():
            register_url = reverse('register')
            error_html = mark_safe(
                f'Es existiert kein aktives Konto mit dieser E-Mail-Adresse. <a href="{register_url}" style="color: #007bff; text-decoration: underline;">Bitte registrieren!</a>'
            )
            raise ValidationError(error_html)
        return email

class CustomSetPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label="Neues Passwort",
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'placeholder': 'Neues Passwort eingeben'
        }),
        error_messages={
            'required': 'Bitte gib ein neues Passwort ein.'
        }
    )
    new_password2 = forms.CharField(
        label="Neues Passwort bestätigen",
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'placeholder': 'Neues Passwort wiederholen'
        }),
        error_messages={
            'required': 'Bitte bestätige dein neues Passwort.'
        }
    )

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError("Die Passwörter stimmen nicht überein.")
        if password2 and len(password2) < 8:
            raise ValidationError("Das Passwort muss mindestens 8 Zeichen lang sein.")
        return password2 