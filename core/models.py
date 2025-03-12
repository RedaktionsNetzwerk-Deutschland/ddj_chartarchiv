from django.db import models

# Create your models here.

class Chart(models.Model):
    published_date = models.DateTimeField(null=True, blank=True)
    chart_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    comments = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    iframe_url = models.URLField(blank=True)
    embed_js = models.TextField(blank=True)

    def __str__(self):
        return self.title
