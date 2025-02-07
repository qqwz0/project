from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.microsoft_register, name='register'),  # Register path
    path('login/', views.microsoft_login, name='login'),        # Login pathS
    path('callback/', views.microsoft_callback, name='microsoft_callback'),
    path("profile/", views.profile, name="profile"),
    path('profile/<int:user_id>/', views.profile, name='profile_detail'),  # Чужий профіль
    path('logout/', views.logout_view, name='logout')
]