from django import template
from django.db.models import Model
from django.utils.safestring import mark_safe
import json
from django.templatetags.static import static
try:
    from cloudinary_storage.storage import MediaCloudinaryStorage
except ImportError:
    MediaCloudinaryStorage = None

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Отримує елемент зі словника за ключем.
    Використання: {{ dictionary|get_item:key }}
    """
    if not dictionary:
        return []
    str_key = str(key)
    
    if str_key in dictionary:
        return dictionary[str_key]
    
    try:
        int_key = int(key)
        if int_key in dictionary:
            return dictionary[int_key]
    except (ValueError, TypeError):
        pass
    
    return []

@register.filter
def dictsortreversed(value, arg):
    """Sort a list of objects in reverse order by attribute."""
    def get_value(obj):
        if isinstance(obj, dict):
            return obj.get(arg)
        elif isinstance(obj, Model):
            return getattr(obj, arg)
        return None
    return sorted(value, key=get_value, reverse=True)

@register.filter
def to_json(value):
    """
    Перетворює значення у JSON-рядок.
    Використання: {{ value|to_json }}
    """
    return mark_safe(json.dumps(value))

@register.filter
def debug(value):
    """
    Виводить значення змінної у вигляді рядка.
    Використання: {{ value|debug }}
    """
    return f"DEBUG: {value} (type: {type(value)})"

@register.filter
def filter_status(requests, status):
    """
    Фільтрує запити за статусом.
    Використання: {{ requests|filter_status:'Активний' }}
    """
    return [req for req in requests if req.request_status == status]

@register.filter
def cloudinary_avatar(image_field):
    if image_field and image_field.name and MediaCloudinaryStorage:
        try:
            storage = MediaCloudinaryStorage()
            if storage.exists(image_field.name):
                return storage.url(image_field.name)
        except Exception:
            pass
    return static('images/default-avatar.jpg')
