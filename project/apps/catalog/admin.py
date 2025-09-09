from django.contrib import admin
from .models import OnlyTeacher, Announcement

admin.site.register(OnlyTeacher)

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "author_type", "author_faculty", "author_department", "announcement_type", "is_active", "created_at")
    list_filter = ("author_type", "announcement_type", "is_active", "author_department","author_faculty")
    search_fields = ("title", "content")