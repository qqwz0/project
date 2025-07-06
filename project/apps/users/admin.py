from django.contrib import admin
from .models import CustomUser
from apps.catalog.models import Stream

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from .models import CustomUser
from apps.catalog.models import Slot, OnlyTeacher, TeacherTheme  # Ensure Slot is imported from the correct module
# Ensure CustomUserAdmin is imported if defined in another module, otherwise it's defined below
from django.db.models import Q

class CustomUserChangeForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields optional for admin if needed
        self.fields['academic_group'].required = False
        self.fields['department'].required = False

class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserChangeForm
    ordering = ('email',)
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'department')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'patronymic', 'profile_picture')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Additional Info', {'fields': ('academic_group', 'department', 'role')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'first_name', 'last_name', 'patronymic', 'profile_picture', 'academic_group', 'department', 'role'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            return qs.filter(department=request.user.department)
        return qs
    

class SlotAdmin(admin.ModelAdmin):
    list_display = (
        'get_teacher_name',
        'get_teacher_email',
        'get_stream_code',
        'quota',
    )
    ordering = (
        'teacher_id__teacher_id__last_name',
        'teacher_id__teacher_id__first_name',
        'teacher_id__teacher_id__patronymic',
    )
    # прибираємо readonly_fields тут, бо будемо керувати динамічно
    # readonly_fields = ('occupied',)

    search_fields = (
        'teacher_id__first_name',
        'teacher_id__last_name',
        'teacher_id__email',
    )

    autocomplete_fields = ('teacher_id',)

    def get_search_results(self, request, queryset, search_term):
        """
        When Django calls autocomplete, it does:
           qs, distinct = self.get_search_results(request, Slot.objects.all(), term)
        We intercept that and turn it into “all slots whose teacher matches…”
        """
        # First, pull in the default logic (so filters like department_admin still apply)
        qs, use_distinct = super().get_search_results(request, queryset, search_term)

        # But override qs to only filter by related OnlyTeacher:
        teachers = OnlyTeacher.objects.filter(
            Q(teacher_id__first_name__icontains=search_term) |
            Q(teacher_id__last_name__icontains=search_term) |
            Q(teacher_id__patronymic__icontains=search_term) |
            Q(teacher_id__email__icontains=search_term)
        )

        # Return all slots whose FK is in that teacher set
        qs = queryset.filter(teacher_id__in=teachers)
        return qs, False  # False == no .distinct() needed

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            qs = qs.filter(
                teacher_id__teacher_id__department=request.user.department,
                teacher_id__teacher_id__role="Викладач"
            )
        return qs
    
    def get_teacher_name(self, obj):
        u = obj.teacher_id.teacher_id
        parts = [u.last_name, u.first_name]
        if u.patronymic:
            parts.append(u.patronymic)
        return " ".join(parts)
    get_teacher_name.short_description = "Викладач"
    # Let the “Викладач” header sort by last_name
    get_teacher_name.admin_order_field = 'teacher_id__teacher_id__last_name'

    def get_teacher_email(self, obj):
        return obj.teacher_id.teacher_id.email
    get_teacher_email.short_description = "Email викладача"

    def get_stream_code(self, obj):
        # use the actual FK name 'stream_id'
        return obj.stream_id.stream_code
    get_stream_code.short_description = "Потік"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher_id":
            if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
                kwargs["queryset"] = OnlyTeacher.objects.filter(
                    teacher_id__department=request.user.department
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        """
        Робимо occupied лише readonly для department_admin,
        для суперюзера — доступне до редагування.
        """
        readonly = []
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            readonly = ['occupied']
        return readonly


class TeacherThemeAdmin(admin.ModelAdmin):
    list_display = ('get_teacher_email', 'theme', 'is_occupied')
    readonly_fields = ('is_occupied',)  # Якщо поле is_occupied не потрібно редагувати вручну

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            # Фільтруємо теми за відділом викладача: OnlyTeacher -> CustomUser -> department.
            return qs.filter(teacher_id__teacher_id__department=request.user.department)
        return qs

    def get_teacher_email(self, obj):
        """
        Повертає email викладача.
        obj.teacher_id повертає об'єкт OnlyTeacher, який зберігає зв'язок з CustomUser через поле teacher_id.
        """
        return obj.teacher_id.teacher_id.email
    get_teacher_email.short_description = "Email викладача"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Обмежуємо вибір викладачів у полі teacher_id
        if db_field.name == "teacher_id":
            if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
                kwargs["queryset"] = OnlyTeacher.objects.filter(teacher_id__department=request.user.department)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
class StreamAdmin(admin.ModelAdmin):
    list_display = ('specialty_name', 'stream_code')
    search_fields = ('specialty_name', 'stream_code')
    ordering = ('stream_code',)

    # Покажемо розділ адмінки з потоками тільки суперкористувачу
    def has_module_permission(self, request):
        return request.user.is_superuser

    # І право перегляду списку записів — тільки суперкористувач
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    # Додавати нові потоки може тільки суперкористувач
    def has_add_permission(self, request):
        return request.user.is_superuser

    # Редагувати потоки — тільки суперкористувач
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    # Видаляти — тільки суперкористувач
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

admin.site.unregister(OnlyTeacher)

class OnlyTeacherAdmin(admin.ModelAdmin):
    list_display = ('get_teacher_email', 'get_teacher_department')
    search_fields = (
        'teacher_id__first_name',
        'teacher_id__last_name',
        'teacher_id__email',
    )

    def get_teacher_email(self, obj):
        return obj.teacher_id.email
    get_teacher_email.short_description = "Teacher Email"

    def get_teacher_department(self, obj):
        return obj.teacher_id.department
    get_teacher_department.short_description = "Department"

# І нарешті реєструємо модель:
admin.site.register(Stream, StreamAdmin)

admin.site.register(OnlyTeacher, OnlyTeacherAdmin)

# Реєструємо модель TeacherTheme в адмінці з новою конфігурацією
admin.site.register(TeacherTheme, TeacherThemeAdmin)


# Correctly register the model with the admin site:
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Slot, SlotAdmin)