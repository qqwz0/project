from django.urls import path
from .views import (
    TeachersCatalogView,
    TeachersListView,
    TeacherModalView,
    AcceptRequestView,
    CompleteRequestView,
    reject_request,
    load_tab_content,
    UploadFileView,
    DeleteFileView,
    DownloadFileView,
    AddCommentView,
    DeleteCommentView,
    archived_request_details
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', TeachersCatalogView.as_view(), name='teachers_catalog'),
    path('catalog/teachers/', TeachersListView.as_view(), name='teachers_list'),
    path('teacher/<int:pk>/', TeacherModalView.as_view(), name='modal'),
    path('accept-request/<int:pk>/', AcceptRequestView.as_view(), name='accept_request'),
    path('complete-request/<int:pk>/', CompleteRequestView.as_view(), name='complete_request'),
    path('reject-request/<int:request_id>/', reject_request, name='reject_request'),
    path('load-tab/<str:tab_name>/', load_tab_content, name='load_tab_content'),
    
    # File handling
    path('request/<int:request_id>/upload-file/', UploadFileView.as_view(), name='upload_file'),
    path('file/<int:pk>/delete/', DeleteFileView.as_view(), name='delete_file'),
    path('file/<int:pk>/download/', DownloadFileView.as_view(), name='download_file'),
    
    # Comments
    path('file/<int:file_id>/comment/', AddCommentView.as_view(), name='add_comment'),
    path('comment/<int:pk>/delete/', DeleteCommentView.as_view(), name='delete_comment'),
    path('archived-request-details/<int:request_id>/', archived_request_details, name='archived_request_details'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)