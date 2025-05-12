import os
import django
import sys
from pathlib import Path

# Django Setup
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'archive_webapp.settings')
django.setup()

from core.models import TopicTile
from django.core.files import File

try:
    # Suche die Kachel "Bevölkerung"
    tile = TopicTile.objects.get(title='Bevölkerung')
    print(f"Kachel '{tile.title}' gefunden.")

    # Pfad zum Hintergrundbild
    image_path = 'media/topic_tiles/bevölkerung.png'
    
    # Prüfe, ob die Datei existiert
    if os.path.exists(image_path):
        # Setze das Hintergrundbild
        with open(image_path, 'rb') as img_file:
            # Wenn bereits ein Bild existiert, lösche es
            if tile.background_image:
                tile.background_image.delete(save=False)
            
            # Setze das neue Bild
            tile.background_image.save(
                os.path.basename(image_path),
                File(img_file)
            )
        print(f"Hintergrundbild für Kachel '{tile.title}' wurde aktualisiert.")
    else:
        print(f"Fehler: Die Datei '{image_path}' existiert nicht.")
    
except TopicTile.DoesNotExist:
    print("Fehler: Kachel 'Bevölkerung' wurde nicht gefunden.")
except Exception as e:
    print(f"Fehler: {str(e)}") 