from django.templatetags.static import static
from .models import CustomUser
from cloudinary_storage.storage import MediaCloudinaryStorage

def user_profile_picture(request):
    if request.user.is_authenticated:
        # Check if a profile picture value (a file name) exists in the database.
        if request.user.profile_picture and request.user.profile_picture.name:
            try:
                storage = MediaCloudinaryStorage()
                # First, check if the file actually exists in Cloudinary.
                if storage.exists(request.user.profile_picture.name):
                    # If it exists, get the URL.
                    picture_url = storage.url(request.user.profile_picture.name)
                    return {'profile_picture_url': picture_url}
            except Exception:
                # If there's any error communicating with storage, fall back to default.
                pass

        # If there's no picture, or the file doesn't exist in Cloudinary, return the static default avatar.
        return {'profile_picture_url': static('images/default-avatar.jpg')}

    return {}
