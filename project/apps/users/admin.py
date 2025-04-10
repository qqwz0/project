from django.contrib import admin
from .models import CustomUser

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from .models import CustomUser
from apps.catalog.models import Slot, OnlyTeacher, TeacherTheme  # Ensure Slot is imported from the correct module
# Ensure CustomUserAdmin is imported if defined in another module, otherwise it's defined below

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
    list_display = ('get_teacher_email', 'quota')
    ordering = ('quota',)
    readonly_fields = ('occupied',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Фільтрація слотів за відділом викладача,
        # використовуючи ланцюгове звернення: OnlyTeacher → CustomUser.
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            qs = qs.filter(
                teacher_id__teacher_id__department=request.user.department, 
                teacher_id__teacher_id__role="Викладач"
            )
        return qs

    def get_teacher_email(self, obj):
        # obj.teacher_id повертає об'єкт OnlyTeacher,
        # а teacher_id.teacher_id повертає об'єкт CustomUser, звідки беремо email.
        return obj.teacher_id.teacher_id.email
    get_teacher_email.short_description = "Email викладача"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Обмежуємо список викладачів при виборі для поля teacher_id
        if db_field.name == "teacher_id":
            if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
                kwargs["queryset"] = OnlyTeacher.objects.filter(teacher_id__department=request.user.department)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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

# Реєструємо модель TeacherTheme в адмінці з новою конфігурацією
admin.site.register(TeacherTheme, TeacherThemeAdmin)


# Correctly register the model with the admin site:
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Slot, SlotAdmin)
