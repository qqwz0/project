from django.templatetags.static import static
from .models import CustomUser

def user_profile_picture(request):
    if request.user.is_authenticated:
        if request.user.profile_picture and hasattr(request.user.profile_picture, 'url'):
            picture_url = request.user.profile_picture.url
            if 'res.cloudinary.com' in picture_url:
                return {'profile_picture_url': picture_url}

        return {'profile_picture_url': static('images/default-avatar.jpg')}

    return {}
