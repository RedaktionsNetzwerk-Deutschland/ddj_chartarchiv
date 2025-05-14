#!/bin/bash
set -e

# Stelle sicher, dass die Media-Verzeichnisse existieren und korrekte Berechtigungen haben
echo "Erstelle und konfiguriere Media-Verzeichnisse..."
mkdir -p /code/media/thumbnails
mkdir -p /code/media/topic_tiles
chmod -R 777 /code/media

# Migrationen anwenden
echo "Führe Migrationen aus..."
python manage.py makemigrations

# Warten auf MySQL
echo "Warte auf MySQL..."
#until mysql -h db -u"$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1" &>/dev/null; do
until mysql -h db -u"$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1"; do
  echo "MySQL ist noch nicht verfügbar - warte..."
  sleep 1
done
echo "MySQL ist bereit!"

# Prüfen, ob die Datenbank bereits Tabellen enthält
tables=$(mysql -h db -u"$DB_USER" -p"$DB_PASSWORD" -e "USE $DB_NAME; SHOW TABLES;" 2>/dev/null | wc -l)

# Wenn keine oder wenige Tabellen, dann Import durchführen
if [ "$tables" -lt 2 ]; then
  echo "Neue Datenbank erkannt - importiere Daten..."
  if [ -f /code/db_backup.sql ]; then
    mysql -h db -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < /code/db_backup.sql
    echo "Datenbank erfolgreich importiert!"
  else
    echo "Keine Backup-Datei gefunden. Erstelle neue Datenbank..."
    python manage.py migrate
  fi
else
  echo "Datenbank existiert bereits, führe nur Migrationen aus..."
  python manage.py migrate
fi

# Sammle statische Dateien
echo "Sammle statische Dateien..."
python manage.py collectstatic --noinput

# Starte den Django-Server
echo "Starte den Django-Server..."
exec "$@" 