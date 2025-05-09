from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = 'Erstellt die Nutzergruppen "creator" und "buddies" für Zugriffskontrolle'

    def handle(self, *args, **options):
        # Erstelle die Gruppen, falls sie noch nicht existieren
        creator_group, created_creator = Group.objects.get_or_create(name='creator')
        if created_creator:
            self.stdout.write(self.style.SUCCESS('Gruppe "creator" erfolgreich erstellt.'))
        else:
            self.stdout.write(self.style.WARNING('Gruppe "creator" existiert bereits.'))
            
        buddies_group, created_buddies = Group.objects.get_or_create(name='buddies')
        if created_buddies:
            self.stdout.write(self.style.SUCCESS('Gruppe "buddies" erfolgreich erstellt.'))
        else:
            self.stdout.write(self.style.WARNING('Gruppe "buddies" existiert bereits.'))
            
        self.stdout.write(self.style.SUCCESS('Gruppen-Setup abgeschlossen.')) 