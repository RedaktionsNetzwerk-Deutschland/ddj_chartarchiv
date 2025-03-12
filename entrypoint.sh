#!/bin/sh

# Warte, bis die Datenbank erreichbar ist
echo "Warte auf die Datenbank..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 0.1
done
echo "Datenbank ist erreichbar."

# Migrationen erstellen und anwenden
echo "Führe Migrationen aus..."
python manage.py makemigrations
python manage.py migrate

# Sammle statische Dateien
echo "Sammle statische Dateien..."
python manage.py collectstatic --noinput

# Starte den Django-Server
echo "Starte den Django-Server..."
exec "$@" 