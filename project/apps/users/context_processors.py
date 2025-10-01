from django.templatetags.static import static
from .models import CustomUser
from django.core.files.storage import default_storage

def user_profile_picture(request):
    if request.user.is_authenticated:
        # Check if a profile picture value (a file name) exists in the database.
        if request.user.profile_picture and request.user.profile_picture.name:
            try:
                if default_storage.exists(request.user.profile_picture.name):
                    picture_url = default_storage.url(request.user.profile_picture.name)
                    return {'profile_picture_url': picture_url}
            except Exception:
                # If there's any error communicating with storage, fall back to default.
                pass

        # If there's no picture, or the file doesn't exist in Cloudinary, return the static default avatar.
        return {'profile_picture_url': static('images/default-avatar.jpg')}

    return {}

from django.templatetags.static import static
from django.core.files.storage import default_storage

def user_context(request):
    context = {}
    if request.user.is_authenticated:
        context['auth_user'] = request.user
        profile_pic_url = static('images/default-avatar.jpg')
        if request.user.profile_picture and request.user.profile_picture.name:
            try:
                if default_storage.exists(request.user.profile_picture.name):
                    profile_pic_url = default_storage.url(request.user.profile_picture.name)
            except Exception:
                pass
        context['profile_picture_url'] = profile_pic_url
    return context