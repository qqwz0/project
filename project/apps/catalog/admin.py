from django.contrib import admin
from .models import OnlyTeacher, Announcement, Department

admin.site.register(OnlyTeacher)

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author_type",
        "author_faculty",
        "author_department",
        "announcement_type",
        "is_active",
        "created_at",
    )
    list_filter = (
        "author_type",
        "announcement_type",
        "is_active",
        "author_department",
        "author_faculty",
    )
    search_fields = ("title", "content")

    # ---- обмеження queryset ----
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user

        if user.is_superuser:
            return qs

        if user.groups.filter(name="department_admin").exists():
            dept = user.get_department()
            return qs.filter(author_department=dept) if dept else qs.none()

        if user.groups.filter(name="faculty_admin").exists():
            faculty = user.get_faculty()
            return qs.filter(author_faculty=faculty) if faculty else qs.none()

        return qs.none()

    # ---- які поля можна редагувати ----
    def get_readonly_fields(self, request, obj=None):
        user = request.user
        if user.is_superuser:
            return ()
        if user.groups.filter(name="department_admin").exists():
            return ("author_type", "author_faculty", "author_department")
        if user.groups.filter(name="faculty_admin").exists():
            return ("author_faculty",)
        return ()

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        user = request.user
        if user.groups.filter(name="department_admin").exists():
            # ховаємо службові поля
            for f in ("author_type", "author_faculty", "author_department"):
                if f in fields:
                    fields.remove(f)
        elif user.groups.filter(name="faculty_admin").exists():
            # ховаємо службові поля
            for f in ("author_faculty",):
                if f in fields:
                    fields.remove(f)
        return fields

    # ---- підстановка даних при збереженні ----
    def save_model(self, request, obj, form, change):
        user = request.user
        if not user.is_superuser:
            if user.groups.filter(name="department_admin").exists():
                obj.author_type = "department"
                obj.author_department = user.get_department()
                obj.author_faculty = user.get_faculty()
            elif user.groups.filter(name="faculty_admin").exists():
                obj.author_type = "faculty"
                obj.author_faculty = user.get_faculty()
                # кафедру лишаємо порожньою для факультет-адміна
        super().save_model(request, obj, form, change)

    # ---- обмеження вибору кафедр для faculty_admin ----
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "author_department" and request.user.groups.filter(name="faculty_admin").exists():
            faculty = request.user.get_faculty()
            kwargs["queryset"] = Department.objects.filter(faculty=faculty) if faculty else Department.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
