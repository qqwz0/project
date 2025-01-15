from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.microsoft_register, name='register'),  # Register path
    path('login/', views.login, name='login'),        # Login path
    path("microsoft-register/", views.microsoft_register, name="microsoft_register"),
    path('callback/', views.microsoft_callback, name='microsoft_callback'),
]