from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """Prüft, ob ein Benutzer zu einer bestimmten Gruppe gehört."""
    try:
        group = Group.objects.get(name=group_name)
        return group in user.groups.all() or user.is_superuser
    except Group.DoesNotExist:
        return False 