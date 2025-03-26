from django.views.generic import ListView, View
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Notification



class NotificationListView(ListView):
    model = Notification
    template_name = 'notifications/notification_list.html'
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        notifications = context['notifications']
        
        # Для кожної нотифікації додаємо ID в контекст 
        for notification in notifications:
            notification.notification_id = notification.id
            
            # Визначаємо статус на основі тексту
            notification.status = None
            if "прийняв" in notification.message:
                notification.status = "прийняв"
            elif "відхилив" in notification.message:
                notification.status = "відхилив"
                
        return context

class MarkAsReadView(LoginRequiredMixin, View):
    def get(self, request, notification_id):
        notification = get_object_or_404(
            Notification, 
            id=notification_id, 
            recipient=request.user
        )
        notification.is_read = True
        notification.save()
         