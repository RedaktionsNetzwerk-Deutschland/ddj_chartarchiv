from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Chart, ChartData, RegistrationConfirmation, PasswordResetToken

# Register your models here.
admin.site.register(Chart)
admin.site.register(ChartData)
admin.site.register(RegistrationConfirmation)
admin.site.register(PasswordResetToken)

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
