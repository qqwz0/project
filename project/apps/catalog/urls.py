from django.urls import path
from .views import (
    TeachersListView, 
    TeacherModalView, 
    AcceptRequestView, 
    CompleteRequestView, 
    load_tab_content,
    reject_request
)

urlpatterns = [
    path('teachers/', TeachersListView.as_view(), name='teachers_catalog'),
    path('modal/<int:pk>/', TeacherModalView.as_view(), name='modal'),
    path('request/accept/<int:pk>/', AcceptRequestView.as_view(), name='accept_request'),
    path('request/reject/<int:request_id>/', reject_request, name='reject_request'),
    path('request/complete/<int:pk>/', CompleteRequestView.as_view(), name='complete_request'),
    path('load-tab/<str:tab_name>/', load_tab_content, name='load_tab'),
]