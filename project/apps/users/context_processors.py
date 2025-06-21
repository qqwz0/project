from django.templatetags.static import static
from .models import CustomUser
from cloudinary_storage.storage import MediaCloudinaryStorage

def user_profile_picture(request):
    if request.user.is_authenticated:
        # Check if a profile picture value (a file name) exists in the database.
        if request.user.profile_picture and request.user.profile_picture.name:
            try:
                # Manually create a storage instance and get the URL.
                # This bypasses the potentially broken .url property.
                storage = MediaCloudinaryStorage()
                picture_url = storage.url(request.user.profile_picture.name)
                return {'profile_picture_url': picture_url}
            except Exception:
                # If there's any error getting the URL (e.g., file not found in cloudinary), fall back.
                pass

        # If there's no picture or an error occurred, return the static default avatar.
        return {'profile_picture_url': static('images/default-avatar.jpg')}

    return {}
