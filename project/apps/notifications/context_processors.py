from apps.notifications.models import Message

def user_messages(request):
    """Context processor to provide messages in all templates"""
    if request.user.is_authenticated:
        messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
        unread = Message.objects.filter(recipient=request.user, is_read=False).exists()
        unread_count = messages.filter(is_read=False).count()
        return {
            'message_list': messages,
            'unread': unread,
            'unread_count': unread_count
        }
    return {'message_list': [], 'unread': False}   