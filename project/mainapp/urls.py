from django.urls import path
from .views import TeachersListView, TeacherDetailView

urlpatterns = [
    path('teachers/', TeachersListView.as_view(), name='teachers_page'),
    path('teachers/<int:pk>/', TeacherDetailView.as_view(), name='teacher_detail'),
]