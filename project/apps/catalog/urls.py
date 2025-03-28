from django.urls import path
from .views import TeachersListView, TeacherModalView, TeachersCatalogView

urlpatterns = [
    path('teachers/', TeachersCatalogView.as_view(), name='teachers_catalog'),
    path('teachers_list/', TeachersListView.as_view(), name='teachers_list'),
    path('modal/<int:pk>/', TeacherModalView.as_view(), name='modal'),
]