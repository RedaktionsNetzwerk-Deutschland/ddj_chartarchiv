FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# Installiere Build-Abhängigkeiten für mysqlclient, inkl. pkg-config und netcat-openbsd
RUN apt-get update && apt-get install -y gcc pkg-config default-libmysqlclient-dev build-essential netcat-openbsd && rm -rf /var/lib/apt/lists/*

COPY . /code/

WORKDIR /code
ENV PYTHONPATH="/code"

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Erstelle media-Verzeichnisse
RUN mkdir -p /code/media/thumbnails /code/logs && chmod -R 777 /code/media && \
    touch /code/logs/django.log 


# Entrypoint-Skript kopieren und ausführbar machen
COPY entrypoint.sh /code/
RUN chmod +x /code/entrypoint.sh

ENTRYPOINT ["/code/entrypoint.sh"]

# Standard-Eingabebefehl (wird durch docker-compose überschrieben)
CMD ["gunicorn", "archive_webapp.wsgi:application", "--bind", "0.0.0.0:8000"] 
