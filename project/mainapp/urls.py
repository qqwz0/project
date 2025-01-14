from django.urls import path
from . import views

urlpatterns = [
    path('', views.teachers_page, name='teachers_page'),
]