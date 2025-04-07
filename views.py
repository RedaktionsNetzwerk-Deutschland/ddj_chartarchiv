# In der chart_search-Funktion, innerhalb der Ergebnisschleife
results.append({
    'chart_id': chart.chart_id,
    'title': chart.title,
    'description': chart.description,
    'notes': chart.notes,
    'tags': tags,
    'thumbnail': chart.thumbnail.url if chart.thumbnail else '',
    'published_date': chart.published_date.isoformat() if chart.published_date else None,
    'evergreen': chart.evergreen,
    'patch': chart.patch,
    'regional': chart.regional
}) 