from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.microsoft_register, name='register'),  # Register path
    path('login/', views.microsoft_login, name='login'),        # Login pathS
    path('fake_login/', views.fake_login, name='fake_login'),        # Login pathS
    path('callback/', views.microsoft_callback, name='microsoft_callback'),
    path("profile/", views.profile, name="profile"),
    path('profile/<int:user_id>/', views.profile, name='profile_detail'),  # Чужий профіль
    path('logout/', views.logout_view, name='logout'),
    path('approve_request/<int:request_id>/', views.approve_request, name='approve_request'),
    path('reject_request/<int:request_id>/', views.reject_request, name='reject_request'),
    path('update-profile-picture/', views.update_profile_picture, name='update_profile_picture'),
    path('crop-profile-picture/', views.crop_profile_picture, name='crop_profile_picture'),
    path('teacher/profile/edit/', views.teacher_profile_edit, name='teacher_profile_edit'),
    path('student/profile/edit/', views.student_profile_edit, name='student_profile_edit')
]