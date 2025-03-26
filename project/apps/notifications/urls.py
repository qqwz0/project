from django.urls import path
from .views import NotificationListView, MarkAsReadView

urlpatterns = [
    path('/get_notifications/', NotificationListView.as_view(), name='get_notifications'),
    path('/mark_as_read/<int:notification_id>/', MarkAsReadView.as_view(), name='mark_as_read'),
]