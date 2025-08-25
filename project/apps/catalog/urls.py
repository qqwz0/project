from django.urls import path
from .views import (
    TeachersCatalogView,
    TeachersListView,
    TeacherModalView,
    CompleteRequestView,
    reject_request,
    load_tab_content,
    UploadFileView,
    DeleteFileView,
    DownloadFileView,
    AddCommentView,
    DeleteCommentView,
    delete_theme,
    add_comment,
    AutocompleteView,
    ThemeTeachersView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', TeachersCatalogView.as_view(), name='teachers_catalog'),
    path('teachers/', TeachersListView.as_view(), name='teachers_list'),
    path('teacher/<int:pk>/', TeacherModalView.as_view(), name='modal'),

    path('complete-request/<int:pk>/', CompleteRequestView.as_view(), name='complete_request'),
    path('reject-request/<int:request_id>/', reject_request, name='reject_request'),
    path('load-tab/<str:tab_name>/', load_tab_content, name='load_tab_content'),
    
    # File handling
    path('request/<int:request_id>/upload-file/', UploadFileView.as_view(), name='upload_file'),
    path('file/<int:pk>/delete/', DeleteFileView.as_view(), name='delete_file'),
    path('file/<int:pk>/download/', DownloadFileView.as_view(), name='download_file'),
    
    # Comments
    path('file/<int:file_id>/comment/', add_comment, name='add_comment'),
    path('comment/<int:pk>/delete/', DeleteCommentView.as_view(), name='delete_comment'),
    
    # Search and autocomplete
    path('autocomplete/', AutocompleteView.as_view(), name='autocomplete'),
    path('autocomplete/theme/<int:theme_id>/teachers/', ThemeTeachersView.as_view(), name='theme_teachers'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)