"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.catalog import views
from apps.users.admin import import_teachers_excel_view, import_students_excel_view, import_themes_excel_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('import-teachers-excel/', import_teachers_excel_view, name='import_teachers_excel'),
    path('import-students-excel/', import_students_excel_view, name='import_students_excel'),
    path('import-themes-excel/', import_themes_excel_view, name='import_themes_excel'),
    path('', views.home, name='home'),  # Home page
    path('users/', include('apps.users.urls')),
    path('catalog/', include('apps.catalog.urls')),
    path('notifications/', include('apps.notifications.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'apps.users.views.custom_404'
handler500 = 'apps.users.views.custom_500'  # Add this for 500 errors too

