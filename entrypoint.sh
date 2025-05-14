#!/bin/sh

# Stelle sicher, dass die Media-Verzeichnisse existieren und korrekte Berechtigungen haben
echo "Erstelle und konfiguriere Media-Verzeichnisse..."
mkdir -p /code/media/thumbnails
mkdir -p /code/media/topic_tiles
chmod -R 777 /code/media

# Migrationen anwenden
echo "Führe Migrationen aus..."
python manage.py makemigrations
python manage.py migrate

# Sammle statische Dateien
echo "Sammle statische Dateien..."
python manage.py collectstatic --noinput

# Starte den Django-Server
if [ $# -eq 0 ]; then
    echo "Starte Standard-Django-Server..."
    exec gunicorn archive_webapp.wsgi:application --bind 0.0.0.0:8000
else
    exec "$@"
fi
