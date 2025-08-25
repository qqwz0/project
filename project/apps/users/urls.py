from django.urls import path, include
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('register/', views.microsoft_register, name='register'),  # Register path
    path('login/', views.microsoft_login, name='login'),        # Login pathS
    path('fake_login/', views.fake_login, name='fake_login'),        # Login pathS
    path('fake_student_login/', views.fake_student_login, name='fake_student_login'),
    path('fake_student_login_2/', views.fake_student_login_2, name='fake_student_login_2'),
    path('callback', views.microsoft_callback, name='microsoft_callback'),
    path("profile/", views.profile, name="profile"),
    path('profile/<int:user_id>/', views.profile, name='profile_detail'),  # Чужий профіль
    path('logout/', views.logout_view, name='logout'),

    path('reject_request/<int:request_id>/', views.reject_request, name='reject_request'),
    path('restore_request/<int:request_id>/', views.restore_request, name='restore_request'),
    path('update-profile-picture/', views.update_profile_picture, name='update_profile_picture'),
    path('crop-profile-picture/', views.crop_profile_picture, name='crop_profile_picture'),
    path('teacher/profile/edit/', views.teacher_profile_edit, name='teacher_profile_edit'),
    path('student/profile/edit/', views.student_profile_edit, name='student_profile_edit'),
    path('complete_request/<int:request_id>/', views.complete_request, name='complete_request'),
    path('profile/load-tab/<str:tab_name>/', views.load_profile_tab, name='load_profile_tab'),
    path('archived-request-details/<int:request_id>/', views.archived_request_details, name='archived_request_details'),
    path('request-files/<int:request_id>/', views.request_files_for_completion, name='request_files_for_completion'),
    path('request-details-for-approve/<int:request_id>/', views.request_details_for_approve, name='request_details_for_approve'),
    path('approve-request-with-theme/<int:request_id>/', views.approve_request_with_theme, name='approve_request_with_theme'),
    path('student-refuse-request/<int:request_id>/', views.student_refuse_request, name='student_refuse_request'),
    path('edit-request-theme/<int:request_id>/', views.edit_request_theme, name='edit_request_theme'),
    path('get-student-request-details/<int:request_id>/', views.get_student_request_details, name='get_student_request_details'),
    path('edit-student-request/<int:request_id>/', views.edit_student_request, name='edit_student_request'),
    path('teacher-theme/create/', views.create_teacher_theme, name='create_teacher_theme'),
    path('teacher-theme/deactivate/<int:theme_id>/', views.deactivate_teacher_theme, name='deactivate_teacher_theme'),
    path('teacher-theme/activate/<int:theme_id>/', views.activate_teacher_theme, name='activate_teacher_theme'),
    path('teacher-theme/delete/<int:theme_id>/', views.delete_teacher_theme, name='delete_teacher_theme'),
    path('teacher-theme/attach-streams/<int:theme_id>/', views.attach_theme_to_streams, name='attach_theme_to_streams'),
    path('teacher-theme/update/<int:theme_id>/', views.update_teacher_theme, name='update_teacher_theme'),
    path('cancel-request/<int:request_id>/', views.cancel_active_request, name='cancel_request')
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)