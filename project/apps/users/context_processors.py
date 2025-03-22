from .models import CustomUser

def user_profile_picture(request):
    if request.user.is_authenticated:
        return {
            'profile_picture_url': request.user.profile_picture.url if request.user.profile_picture else '/media/profile_pics/default-avatar.jpg'
        }
    return {}
