from django.urls import path
from .views import (
    TeachersCatalogView,
    TeachersListView,
    TeacherModalView,
    AcceptRequestView,
    CompleteRequestView,
    reject_request,
    load_tab_content
)

urlpatterns = [
    path('', TeachersCatalogView.as_view(), name='teachers_catalog'),
    path('teachers/', TeachersListView.as_view(), name='teachers_list'),
    path('teacher/<int:pk>/', TeacherModalView.as_view(), name='modal'),
    path('accept-request/<int:pk>/', AcceptRequestView.as_view(), name='accept_request'),
    path('complete-request/<int:pk>/', CompleteRequestView.as_view(), name='complete_request'),
    path('reject-request/<int:request_id>/', reject_request, name='reject_request'),
    path('load-tab/<str:tab_name>/', load_tab_content, name='load_tab_content'),
]