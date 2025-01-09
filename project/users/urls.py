from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),  # Register path
    path('login/', views.login, name='login'),        # Login path
]