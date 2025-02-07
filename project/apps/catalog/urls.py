from django.urls import path
from .views import TeachersListView, TeacherModalView

urlpatterns = [
    path('teachers/', TeachersListView.as_view(), name='teachers_catalog'),
    path('modal/<int:pk>/', TeacherModalView.as_view(), name='modal'),
]