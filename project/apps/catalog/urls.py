from django.urls import path
from .views import TeachersListView

urlpatterns = [
    path('teachers/', TeachersListView.as_view(), name='teachers_page'),
]