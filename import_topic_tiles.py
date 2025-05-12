import os
import django
import sys
from pathlib import Path

# Django Setup
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'archive_webapp.settings')
django.setup()

from core.models import TopicTile
from django.conf import settings
from django.core.files import File

# Lösche bestehende Kacheln (optional, bei Bedarf auskommentieren)
# TopicTile.objects.all().delete()

# Liste der Themenkacheln mit Daten
topic_tiles = [
    {
        'title': 'Bildung',
        'background_color': '#4f80ff',
        'search_terms': 'Bildung, Schule, Universität, Ausbildung, Lernen',
        'order': 1
    },
    {
        'title': 'Mobilitätskompass',
        'background_color': '#ff9944',
        'search_terms': 'Mobilitätskompass, Mobilität, Verkehr, Transport',
        'order': 2
    },
    {
        'title': 'Verkehr + Mobilität',
        'background_color': '#33aaff',
        'search_terms': 'Verkehr, Mobilität, Transport, Auto, Bahn, Flugzeug, ÖPNV',
        'order': 3
    },
    {
        'title': 'Bevölkerung',
        'background_color': '#55aa44',
        'search_terms': 'Bevölkerung, Demografie, Einwohner, Gesellschaft',
        'order': 4
    },
    {
        'title': 'Wirtschaft',
        'background_color': '#ffcc33',
        'search_terms': 'Wirtschaft, Inflation, BIP, Konjunktur, Arbeitsmarkt, Ökonomie',
        'order': 5
    },
    {
        'title': 'Gesundheit',
        'background_color': '#ff5566',
        'search_terms': 'Gesundheit, Medizin, Krankenhaus, Pflege, Ärzte, Corona',
        'order': 6
    },
    {
        'title': 'Umwelt + Klima',
        'background_color': '#44bb55',
        'search_terms': 'Umwelt, Klima, Klimawandel, Nachhaltigkeit, CO2, Ökologie',
        'order': 7
    },
    {
        'title': 'Sicherheit + Kriminalität',
        'background_color': '#aa4455',
        'search_terms': 'Sicherheit, Kriminalität, Polizei, Verbrechen, Strafverfolgung',
        'order': 8
    }
]

# Verzeichnis für die zu importierenden Bilder
IMPORT_IMAGES_DIR = 'import_images'

# Erstelle das Verzeichnis, falls es nicht existiert
if not os.path.exists(IMPORT_IMAGES_DIR):
    os.makedirs(IMPORT_IMAGES_DIR)
    print(f"Verzeichnis '{IMPORT_IMAGES_DIR}' erstellt. Bitte lege dort die Bilder ab.")

# Füge die Themenkacheln hinzu
for tile_data in topic_tiles:
    # Prüfe, ob bereits eine Kachel mit diesem Titel existiert
    existing_tile = TopicTile.objects.filter(title=tile_data['title']).first()
    
    if existing_tile:
        print(f"Kachel '{tile_data['title']}' existiert bereits, wird aktualisiert...")
        # Aktualisiere die Daten
        for key, value in tile_data.items():
            setattr(existing_tile, key, value)
        existing_tile.save()
        tile = existing_tile
    else:
        print(f"Erstelle neue Kachel: {tile_data['title']}")
        # Erstelle eine neue Kachel
        tile = TopicTile.objects.create(**tile_data)
    
    # Suche nach einem Bild für diese Kachel
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    found_image = False
    
    # Option 1: Suche nach einem Bild mit exaktem Titel
    for ext in image_extensions:
        image_path = os.path.join(IMPORT_IMAGES_DIR, f"{tile.title}{ext}")
        if os.path.exists(image_path):
            with open(image_path, 'rb') as img_file:
                tile.background_image.save(
                    os.path.basename(image_path),
                    File(img_file)
                )
            print(f"  → Bild '{os.path.basename(image_path)}' für Kachel '{tile.title}' hinzugefügt.")
            found_image = True
            break
    
    # Option 2: Suche nach einem Bild mit vereinfachtem Titel (ohne Sonderzeichen)
    if not found_image:
        simplified_title = ''.join(c for c in tile.title.lower() if c.isalnum())
        for ext in image_extensions:
            image_path = os.path.join(IMPORT_IMAGES_DIR, f"{simplified_title}{ext}")
            if os.path.exists(image_path):
                with open(image_path, 'rb') as img_file:
                    tile.background_image.save(
                        os.path.basename(image_path),
                        File(img_file)
                    )
                print(f"  → Bild '{os.path.basename(image_path)}' für Kachel '{tile.title}' hinzugefügt.")
                found_image = True
                break

print(f"Insgesamt {TopicTile.objects.count()} Themenkacheln in der Datenbank.")
print(f"\nHinweis: Lege Bilder im Verzeichnis '{IMPORT_IMAGES_DIR}' ab, um sie automatisch zu importieren.")
print("Nutze als Dateinamen den exakten Titel der Kachel (z.B. 'Bildung.jpg') oder")
print("eine vereinfachte Version ohne Sonderzeichen (z.B. 'bildung.jpg').") 