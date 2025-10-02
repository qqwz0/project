from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.db.models import F, Q
from django.http import FileResponse, HttpResponse
from django.urls import reverse
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
import re
from django.urls import path
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone

from docxtpl import DocxTemplate

from .models import CustomUser
from apps.catalog.models import (
    Stream,
    Slot,
    OnlyTeacher,
    OnlyStudent,
    TeacherTheme,
    Request,
    StudentTheme,
    Semestr,
    Department
)
from .export_service import export_requests_to_word

from django.contrib.admin import SimpleListFilter

class StreamFilter(SimpleListFilter):
    title = 'Потік'
    parameter_name = 'stream'

    def lookups(self, request, model_admin):
        streams = (
            model_admin.model.objects
            .select_related('slot__stream_id')
            .values_list('slot__stream_id__id', 'slot__stream_id__stream_code')
            .distinct()
        )
        return [
            (stream_id, stream_code)
            for stream_id, stream_code in streams
            if stream_id is not None
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(slot__stream_id__id=self.value())
        return queryset

class StudentAutocompleteField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name_with_patronymic()

class CustomUserChangeForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = '__all__'
        labels = {
            'first_name': _('Імʼя'),
            'last_name': _('Прізвище'),
            'patronymic': _('По батькові'),
            'email': _('Email'),
            'academic_group': _('Академічна група'),
            'department': _('Кафедра'),
            'role': _('Роль'),
            'profile_picture': _('Фото профілю'),
            'is_staff': _('Персонал'),
            'is_superuser': _('Суперкористувач'),
            'is_active': _('Активний'),
            'groups': _('Групи'),
            'user_permissions': _('Права доступу'),
        }
        help_texts = {
            'role': _('Роль користувача в системі'),
            'profile_picture': _('Фото, яке відображається у профілі користувача'),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # Зробити деякі поля необов'язковими
        self.fields['academic_group'].required = False
        self.fields['department'].required = False

        # Якщо користувач - адміністратор кафедри
        if self.current_user and self.current_user.groups.filter(name='department_admin').exists() and not self.current_user.is_superuser:
            department = self.current_user.get_department()
            if department:
                # Обмежити список кафедр лише своєю
                self.fields['department'].queryset = self.fields['department'].queryset.filter(pk=department.pk)

class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserChangeForm

    model = CustomUser

    list_display = (
        'email', 'last_name', 'first_name', 'patronymic', 'academic_group', 'role', 'is_staff'
    )

    list_filter = ('role', 'academic_group', 'is_staff', 'is_superuser')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('last_name', 'first_name', 'patronymic', 'academic_group', 'department')}),
        (_('Permissions'), {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'last_name', 'first_name', 'patronymic', 'academic_group', 'department', 'role',
                'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'
            ),
        }),
    )

    search_fields = [
        'first_name',
        'last_name',
        'patronymic',
        'email',
    ]

    ordering = ('email',)


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            return qs.filter(department=request.user.get_department())
        return qs

    @admin.display(description='ПІБ')
    def get_full_name(self, obj):
        return obj.get_full_name_with_patronymic()

    @admin.display(description='Група')
    def get_academic_group(self, obj):
        return obj.academic_group or "—"

    @admin.display(description='Кафедра')
    def get_department(self, obj):
        return obj.department or "—"

    
class HasSlotsFilter(admin.SimpleListFilter):
    title = 'є вільні місця'
    parameter_name = 'has_slots'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Так'),
            ('no', 'Ні'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.annotate(avail=F('quota') - F('occupied')).filter(avail__gt=0)
        if self.value() == 'no':
            return queryset.annotate(avail=F('quota') - F('occupied')).filter(avail__lte=0)
        return queryset

# Фільтр за кафедрами викладачів
class DepartmentFilter(admin.SimpleListFilter):
    title = 'Кафедра'
    parameter_name = 'department'

    def lookups(self, request, model_admin):
        depts = OnlyTeacher.objects.filter(department__isnull=False).values_list('department__department_name', flat=True).distinct()
        return [(dept, dept) for dept in depts if dept]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(teacher_id__department=self.value())
        return queryset
    
class SlotForm(forms.ModelForm):
    """
    Форма для Slot з українськими підписами.
    """
    class Meta:
        model = Slot
        fields = ('teacher_id', 'stream_id', 'quota', 'occupied')
        labels = {
            'teacher_id': 'Викладач',
            'stream_id':  'Потік',
            'quota':      'Квота',
            'occupied':   'Зайнято',
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        if self.current_user and self.current_user.groups.filter(name='department_admin').exists() and not self.current_user.is_superuser:
            self.fields['occupied'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get('teacher_id')
        stream = cleaned_data.get('stream_id')

        if teacher and stream:
            existing = Slot.objects.filter(teacher_id=teacher, stream_id=stream)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if commit:
            obj.save()
        return obj

class SlotAdmin(admin.ModelAdmin):
    form = SlotForm

    list_display = (
        'get_teacher_name',
        'get_department',
        'get_stream_code',
        'get_quota',
        'available_slots',
    )
    list_display_links = ('get_quota',)
    ordering = (
        'teacher_id__teacher_id__last_name',
        'teacher_id__teacher_id__first_name',
    )

    search_fields = (
        'teacher_id__teacher_id__last_name',
        'teacher_id__teacher_id__first_name',
        'stream_id__stream_code',
    )

    autocomplete_fields = ('teacher_id', 'stream_id')

    list_filter = (
        DepartmentFilter,
        'stream_id',
        HasSlotsFilter,
    )

    def get_form(self, request, obj=None, **kwargs):
        kwargs['form'] = self.form
        form = super().get_form(request, obj, **kwargs)
        form.current_user = request.user
        return form

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            qs = qs.filter(teacher_id__department=request.user.get_department())
        return qs

    @admin.display(description='Викладач', ordering='teacher_id__teacher_id__last_name')
    def get_teacher_name(self, obj):
        u = obj.teacher_id.teacher_id
        parts = [u.last_name, u.first_name]
        if u.patronymic:
            parts.append(u.patronymic)
        return " ".join(parts)

    @admin.display(description='Кафедра', ordering='teacher_id__department__department_name')
    def get_department(self, obj):
        return obj.teacher_id.get_department_name() if obj.teacher_id.get_department_name() else "—"

    @admin.display(description='Потік', ordering='stream_id__stream_code')
    def get_stream_code(self, obj):
        return obj.stream_id.stream_code
    
    @admin.display(description='Квота', ordering='quota')
    def get_quota(self, obj):
        return obj.quota

    @admin.display(description='Вільні місця')
    def available_slots(self, obj):
        return obj.quota - obj.occupied

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher_id" and request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            kwargs['queryset'] = OnlyTeacher.objects.filter(
                teacher_id__department=request.user.get_department()
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            return ['occupied']
        return []

class TeacherThemeForm(forms.ModelForm):
    class Meta:
        model = TeacherTheme
        fields = ['teacher_id', 'theme', 'theme_description', 'is_occupied', 'is_active', 'streams']
        labels = {
            'teacher_id': 'Викладач',
            'theme': 'Тема',
            'theme_description': 'Опис',
            'is_occupied': 'Зайнята',
            'is_active': 'Активна',
            'streams': 'Потоки',
        }
        help_texts = {
            'theme': 'Формулювання теми, доступне для вибору студентом',
            'theme_description': 'Додаткові деталі або специфікація теми (необовʼязково)',
            'is_active': 'Деактивовані теми не відображаються в списках для вибору',
            'streams': 'Потоки, до яких прикріплена тема',
        }

class TeacherThemeAdmin(admin.ModelAdmin):
    form = TeacherThemeForm

    list_display = ('get_teacher_full_name', 'get_teacher_theme', 'is_occupied', 'is_active', 'get_streams_display')
    readonly_fields = ('is_occupied',)

    search_fields = (
        'teacher_id__teacher_id__last_name',
        'teacher_id__teacher_id__first_name',
        'teacher_id__teacher_id__patronymic',
        'theme',
    )

    list_filter = ('is_occupied', 'is_active', 'teacher_id__department', 'streams')
    ordering = ('teacher_id__teacher_id__last_name', 'teacher_id__teacher_id__first_name')

    autocomplete_fields = ('teacher_id',)
    filter_horizontal = ('streams',)  # Для зручного вибору потоків
    
    actions = ['activate_themes', 'deactivate_themes']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            return qs.filter(teacher_id__department=request.user.get_department())
        return qs

    @admin.display(
        description="Викладач",
        ordering='teacher_id__teacher_id__last_name'
    )
    def get_teacher_full_name(self, obj):
        t = obj.teacher_id.teacher_id
        return f"{t.last_name} {t.first_name} {t.patronymic or ''}".strip()

    @admin.display(
        description="Тема",
        ordering='theme'
    )
    def get_teacher_theme(self, obj):
        return obj.theme

    @admin.display(
        description="Потоки"
    )
    def get_streams_display(self, obj):
        streams = obj.streams.all()
        if streams:
            return ', '.join([stream.stream_code for stream in streams])
        return '-'

    @admin.action(description='Активувати вибрані теми')
    def activate_themes(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Активовано {updated} тем.')

    @admin.action(description='Деактивувати вибрані теми')
    def deactivate_themes(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Деактивовано {updated} тем.')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher_id":
            if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
                kwargs["queryset"] = OnlyTeacher.objects.filter(teacher_id__department=request.user.get_department())
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def delete_model(self, request, obj):
        if Request.objects.filter(teacher_theme=obj, request_status__in=['Активний', 'Очікує']).exists():
            self.message_user(
                request,
                f"Неможливо видалити тему «{obj.theme}», оскільки вона прив'язана до активного або очікуючого запиту.",
                messages.ERROR
            )
        else:
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        linked_themes = []
        for theme in queryset:
            if Request.objects.filter(teacher_theme=theme, request_status__in=['Активний', 'Очікує']).exists():
                linked_themes.append(theme.theme)

        if linked_themes:
            themes_str = ", ".join(f"«{t}»" for t in linked_themes)
            self.message_user(
                request,
                f"Неможливо виконати видалення. Наступні теми прив'язані до активних запитів або запитів в очікуванні: {themes_str}.",
                messages.ERROR
            )
        else:
            super().delete_queryset(request, queryset)

# Мапа префіксів до назв спеціальностей
PREFIX_MAP = {
    "ФЕС": '126 "Інформаційні системи та технології"',
    "ФЕП": '121 "Інженерія програмного забезпечення"',
    "ФЕІ": '122 "Комп\'ютерні науки"',
    "ФЕМ": '171 "Електроніка та комп\'ютерні системи"',
    "ФЕЛ": '176 "Сенсорні та діагностичні електронні системи"',
}

class StreamForm(forms.ModelForm):
    """
    Форма адмінки для Stream:
    - Поля stream_code та specialty_name відображаються
    - specialty_name не є обов'язковим на формі
    """
    # Явно визначаємо поле, щоб вимкнути required на рівні форми
    class Meta:
        model = Stream
        fields = ('stream_code',)
        help_texts = {
            'stream_code': 'Введіть код потоку, який повинен починатися з абревіатури спеціальності (ФЕС, ФЕП, ФЕІ, ФЕМ, ФЕЛ) та номеру потоку. Для магістрів додайте букву "м" після номеру потоку (наприклад, ФЕІ-2м).'
        }
    def clean_specialty_name(self):
        code = self.cleaned_data.get('stream_code', '') or ''
        # Автозаповнюємо спеціальність на основі префіксу
        if code:
            for prefix, title in PREFIX_MAP.items():
                if code.startswith(prefix):
                    return title
        return ''

    def clean(self):
        # Інші валідації залишаються стандартними
        return super().clean()

class StreamAdmin(admin.ModelAdmin):
    """
    Адмінка для моделі Stream:
    - stream_code та specialty_name у формі
    - specialty_name необов'язкове, автозаповнюється за need
    """
    form = StreamForm

    @admin.display(ordering='specialty_name', description='Назва спеціальності')
    def specialty(self, obj):
        return obj.specialty_name

    @admin.display(ordering='stream_code', description='Код потоку')
    def code(self, obj):
        return obj.stream_code
    
    list_display       = ('specialty', 'code')
    list_display_links = ('code',)
    search_fields      = ('specialty_name', 'stream_code')
    ordering           = ('stream_code', 'specialty_name')

    def _is_super(self, request, obj=None):
        return request.user.is_superuser

    has_module_permission = _is_super
    has_view_permission   = _is_super
    has_add_permission    = _is_super
    has_change_permission = _is_super
    has_delete_permission = _is_super

    def save_model(self, request, obj, form, change):
        # Остаточне автозаповнення перед збереженням
        code = obj.stream_code or ''
        if not obj.specialty_name and code:
            for prefix, title in PREFIX_MAP.items():
                if code.startswith(prefix):
                    obj.specialty_name = title
                    break
        super().save_model(request, obj, form, change)

admin.site.unregister(OnlyTeacher)

class OnlyTeacherForm(forms.ModelForm):
    class Meta:
        model = OnlyTeacher
        fields = ['academic_level']
        labels = {
            'academic_level': 'Академічний рівень',
        }

class OnlyTeacherAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_academic_level')

    # Показати тільки потрібні поля
    fields = ('teacher_id', 'academic_level')  # видимі поля в формі
    readonly_fields = ('teacher_id',)

    search_fields = (
        'teacher_id__first_name',
        'teacher_id__last_name',
        'teacher_id__patronymic',
    )

    def view_on_site(self, obj):
        return reverse('profile_detail', args=[obj.teacher_id.pk])

    # Дозволити зміну, але лише поля academic_level
    def has_add_permission(self, request):
        return False  # нових додавати не можна

    def has_delete_permission(self, request, obj=None):
        return False  # видаляти не можна

    # Дозволити редагування
    def has_change_permission(self, request, obj=None):
        return True

    @admin.display(description='Викладач')
    def get_full_name(self, obj):
        return f"{obj.teacher_id.first_name} {obj.teacher_id.last_name} {obj.teacher_id.patronymic or ''}"

    @admin.display(description='Академічний рівень')
    def get_academic_level(self, obj):
        return obj.academic_level

@admin.register(OnlyStudent)
class OnlyStudentAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_group', 'get_course', 'get_specialty')
    list_filter = ('group__stream__specialty__faculty', 'group__stream')
    search_fields = (
        'student_id__last_name',
        'student_id__first_name', 
        'student_id__patronymic',
        'group__group_code'
    )
    readonly_fields = ('student_id',)
    fields = ('student_id', 'group', 'additional_email', 'phone_number')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='ПІБ студента')
    def get_full_name(self, obj):
        return obj.student_id.get_full_name_with_patronymic()

    @admin.display(description='Група')
    def get_group(self, obj):
        return obj.group.group_code

    @admin.display(description='Курс')
    def get_course(self, obj):
        return obj.course

    @admin.display(description='Спеціальність')
    def get_specialty(self, obj):
        return obj.specialty.name

    def view_on_site(self, obj):
        return reverse('profile_detail', args=[obj.student_id.pk])

    
@admin.register(StudentTheme)
class StudentThemeAdmin(admin.ModelAdmin):
    list_display = ('get_student_full_name', 'theme')
    search_fields = (
        'student_id__last_name',
        'student_id__first_name',
        'student_id__patronymic',
        'theme',
    )
    autocomplete_fields = ('student_id',)  # саме так, як у моделі

    @admin.display(description='Студент')
    def get_student_full_name(self, obj):
        u = obj.student_id
        return f"{u.last_name} {u.first_name} {u.patronymic or ''}".strip()

    def view_on_site(self, obj):
        return reverse('profile_detail', args=[obj.student_id.pk])

class RequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = '__all__'
        # Українські лейбли
        labels = {
            'student_id': 'Студент',
            'teacher_id': 'Викладач',
            'teacher_theme': 'Тема викладача',
            'approved_student_theme': 'Затверджена тема студента',
            'custom_student_theme': 'Довільна тема студента',
            'request_status': 'Статус',
            
        }
    def clean(self):
        """
        Додає комплексну валідацію для запиту:
        1. Перевіряє, чи є у викладача вільні місця для потоку студента.
        2. Перевіряє, чи обрана тема викладача не є зайнятою або видаленою.
        """
        cleaned_data = super().clean()
        teacher_theme = cleaned_data.get('teacher_theme')
        teacher_profile = cleaned_data.get('teacher_id')
        student = cleaned_data.get('student_id')

        # Перевіряємо лише при створенні нового запиту або зміні ключових полів
        is_new_request = not self.instance.pk

        # 1. Валідація слота (наявності вільних місць)
        if is_new_request and student and teacher_profile:
            try:
                # Визначаємо потік студента за його групою
                is_master = student.academic_group.endswith('м')
                match = re.match(r'([А-ЯІЇЄҐ]+)-(\d)', student.academic_group)
                if match:
                    student_stream = match.group(1) + '-' + match.group(2) + ('м' if is_master else '')
                stream = Stream.objects.get(stream_code__iexact=student_stream)

                # Шукаємо відповідний слот
                slot = Slot.objects.get(teacher_id=teacher_profile, stream_id=stream)

                if (slot.quota - slot.occupied) < 1:
                    raise forms.ValidationError(
                        "У цього викладача немає вільних місць для потоку, до якого належить студент."
                    )
            except Stream.DoesNotExist:
                raise forms.ValidationError(
                    f"Не вдалося знайти потік для групи студента «{student.academic_group}»."
                )
            except Slot.DoesNotExist:
                raise forms.ValidationError(
                    "Викладач не має відкритих слотів для потоку, до якого належить студент."
                )

        # 2. Валідація теми викладача
        if teacher_theme:
            # Перевіряємо, чи тема нова для цього запиту
            is_new_or_changed_theme = is_new_request or self.instance.teacher_theme != teacher_theme
            
            if is_new_or_changed_theme:
                if teacher_theme.is_occupied:
                    raise forms.ValidationError({
                        'teacher_theme': "Ця тема вже зайнята іншим студентом і не може бути обрана."
                    })
                if getattr(teacher_theme, 'is_deleted', False):
                    raise forms.ValidationError({
                        'teacher_theme': "Ця тема була видалена і не може бути обрана."
                    })

        return cleaned_data   

class RequestAdmin(admin.ModelAdmin):
    form = RequestForm

    # Автокомплит для полів student_id та teacher_id
    autocomplete_fields = (
        'student_id',
        'teacher_id',
        'teacher_theme',
        'approved_student_theme',
    )

    # Які колонки показувати у списку
    base_list_display = [
        'get_student_teacher',
        'get_teacher_department',
        'get_student_group',
        'get_theme_display',
        'get_work_type', 
        'request_status',
    ]
    extra_list_display = ['display_grade']

    list_filter = (
        'request_status',
        'work_type',
        StreamFilter,
        'teacher_id__department',
        'academic_year',
    )

    search_fields = (
        'student_id__last_name',
        'student_id__first_name',
        'student_id__patronymic',
        'teacher_id__teacher_id__last_name',
        'teacher_id__teacher_id__first_name',
        'teacher_id__teacher_id__patronymic',
        'work_type',
        'topic_name',  # Додали пошук по темі
    )

    export_fields = [
        'student_id',
        'teacher_id',
        'teacher_theme',
        'approved_student_theme',
        'request_status',
        'academic_year',
        'work_type', 
    ]

    actions = ['export_to_word']

    MAX_THEME_LENGTH = 30

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'student_id':
            kwargs['queryset'] = CustomUser.objects.filter(role='Студент')
            kwargs['form_class'] = StudentAutocompleteField
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_list_display(self, request):
        ds = list(self.base_list_display)
        if request.GET.get('request_status') == 'Завершено':
            ds += self.extra_list_display
        return ds

    def get_fields(self, request, obj=None):
        """
        У формі додавання показуємо тільки ключові поля.
        При редагуванні (obj!=None) — усе, як є.
        """
        if obj is None:
            return [
                'student_id',
                'teacher_id',
                'teacher_theme',
                'approved_student_theme',
                'custom_student_theme',
                'request_status',
                'work_type',
                'topic_name',  # Додали можливість вручну встановлювати тему
            ]
        return super().get_fields(request, obj)

    @admin.display(description='Студент — Викладач')
    def get_student_teacher(self, obj):
        student_name = obj.student_id.get_full_name_with_patronymic()
        teacher_name = obj.teacher_id.teacher_id.get_full_name_with_patronymic()
        return f"{student_name} — {teacher_name}"

    @admin.display(description='Кафедра викладача',
                   ordering='teacher_id__department__department_name')
    def get_teacher_department(self, obj):
        return obj.teacher_id.get_department_name() if obj.teacher_id.get_department_name() else "—"

    @admin.display(description='Група студента',
                   ordering='student_id__academic_group')
    def get_student_group(self, obj):
        return obj.student_id.academic_group
    
    @admin.display(description='Тип роботи', ordering='work_type')
    def get_work_type(self, obj):
        return capfirst(obj.work_type)+' роботи' if obj.work_type else '—'

    @admin.display(description='Тема')
    def get_theme_display(self, obj):
        # Пріоритет: topic_name (після підтвердження) > довільна тема студента > затверджена тема студента > тема викладача
        if obj.topic_name:
            text = obj.topic_name
        elif obj.custom_student_theme:
            text = obj.custom_student_theme
        elif obj.approved_student_theme:
            text = obj.approved_student_theme.theme
        elif obj.teacher_theme:
            text = obj.teacher_theme.theme
        else:
            text = ''
        
        # truncate it
        if len(text) > self.MAX_THEME_LENGTH:
            return text[: self.MAX_THEME_LENGTH - 3] + '...'
        return text

    @admin.display(description='Оцінка')
    def display_grade(self, obj):
        return obj.grade if obj.request_status == 'Завершено' else ''

    def view_on_site(self, obj):
        return reverse('profile_detail', args=[obj.student_id.pk])
    
    def save_model(self, request, obj, form, change):
        # 1. Track the old status and old theme
        old_status = None
        old_theme  = None
        if change:
            old = Request.objects.get(pk=obj.pk)
            old_status = old.request_status
            old_theme  = old.teacher_theme

        # 2. Save the Request
        super().save_model(request, obj, form, change)

        # 3. Sync Slot occupancy (as before)
        if obj.request_status == 'Активний' and old_status != 'Активний':
            obj.slot.update_occupied_slots(increment=1)
        elif change and old_status == 'Активний' and obj.request_status != 'Активний':
            obj.slot.update_occupied_slots(increment=-1)

        # 4. Sync TeacherTheme.is_occupied
        #   a) If we switched **to** Активний, mark the new theme occupied
        if obj.request_status == 'Активний' and obj.teacher_theme:
            theme = obj.teacher_theme
            if not theme.is_occupied:
                theme.is_occupied = True
                theme.save(update_fields=['is_occupied'])

        #   b) If we switched **away from** Активний, free up the old theme
        if change and old_status == 'Активний' and old_theme:
            # Only free it if no other active Request references it
            still_active = Request.objects.filter(
                teacher_theme=old_theme,
                request_status='Активний'
            ).exists()
            if not still_active and old_theme.is_occupied:
                old_theme.is_occupied = False
                old_theme.save(update_fields=['is_occupied'])

    # def export_to_word_from_template(self, request, queryset):
    #     if not queryset:
    #         self.message_user(request, "Нічого не обрано.", level=messages.WARNING)
    #         return

    #     # 1. Collect the sets
    #     groups  = set(q.student_id.academic_group     for q in queryset)
    #     streams = set(q.slot.stream_id.specialty_name for q in queryset)
    #     depts   = set(q.teacher_id.teacher_id.department for q in queryset)
    #     years   = set(q.academic_year                   for q in queryset)

    #     # 2. Streams and years *still* must be uniform
    #     for name, s in (("потоку", streams), ("року", years)):
    #         if len(s) != 1:
    #             self.message_user(request,
    #                 f"Виберіть запити лише з одного {name}.", level=messages.ERROR)
    #             return
        
    #     stream = streams.pop()
    #     year   = years.pop()
    #     dept   = depts.pop().lower()

    #     # 3. Decide on group header / filename part
    #     if len(groups) == 1:
    #         the_group = groups.pop()
    #         group_header = f"групи {the_group}"
    #         group_filename = the_group
    #     else:
    #         # multiple or zero groups
    #         group_header = f"різних груп"
    #         # safe filename fragment: join with underscore or just a generic tag
    #         group_filename = "multiple_groups"

    #     # 4. Build context; include each row’s actual group if you want
    #     items = []
    #     for req in queryset:
    #         # student
    #         nm = req.student_id.get_full_name_with_patronymic()
    #         student_name = " ".join(nm.split()[:2])

    #         # theme
    #         theme_text = (req.approved_student_theme or req.teacher_theme).theme

    #         # teacher formatting...
    #         ot = req.teacher_id
    #         lvl = ot.academic_level.lower()
    #         u = ot.teacher_id
    #         teacher_str = f"{lvl}. {u.last_name} {u.first_name[:1]}. {(u.patronymic or '')[:1]}."

    #         # each row can carry its own group if you want
    #         items.append({
    #             'student': student_name,
    #             'theme': theme_text,
    #             'teacher': teacher_str,
    #         })

    #     context = {
    #         'group_display':  group_header,
    #         'stream':         stream,
    #         'department':     dept,
    #         'year':           year,
    #         'items':          items,
    #     }

    #     # 5. Render the .docx
    #     tpl_path = 'templates/request_report_template.docx'
    #     doc = DocxTemplate(tpl_path)
    #     doc.render(context)

    #     # 6. Return a FileResponse with a proper filename
    #     buffer = BytesIO()
    #     doc.save(buffer)
    #     buffer.seek(0)

    #     raw_fname = f"Report_{str(group_filename)}_{str(stream)}_{str(year)}.docx"
    #     quoted    = urlquote(raw_fname)

    #     response = FileResponse(
    #         buffer,
    #         as_attachment=True,
    #         # filename=fname,
    #         content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    #     )
    #     response['Content-Disposition'] = (
    #         f'attachment; filename="{raw_fname}"; filename*=UTF-8\'\'{quoted}'
    #     )
    #     return response
    # export_to_word_from_template.short_description = "Експортувати шаблон запитів у Word"

    def export_to_word(self, request, queryset):
        try:
            return export_requests_to_word(queryset)
        except ValueError as e:
            self.message_user(request, str(e), level=messages.ERROR)
    export_to_word.short_description = "Експортувати шаблон запитів у Word"

class SemestrAdminForm(forms.ModelForm):
    apply_to_all_departments = forms.BooleanField(
        required=False,
        label="Створити для всіх кафедр",
        help_text="Створить семестр для кожної кафедри, якщо ще не існує."
    )

    class Meta:
        model = Semestr
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        # позначимо інстанс прапорцем, щоб модель знала, що перевірки можна послабити
        if cleaned.get('apply_to_all_departments'):
            setattr(self.instance, "_apply_all_departments", True)
        return cleaned

    def validate_unique(self):
        """
        Коли створюємо 'для всіх кафедр', пропускаємо валідацію унікальності
        (бо ми все одно не зберігаємо цей obj, а створюємо окремі екземпляри у save_model).
        """
        if getattr(self.instance, "_apply_all_departments", False):
            return
        return super().validate_unique()
        
class SemestrAdmin(admin.ModelAdmin):
    form = SemestrAdminForm
    list_display = (
        'department',
        'academic_year',
        'semestr',
        'lock_student_requests_date',
        'get_student_lock_status',
        'lock_teacher_editing_themes_date',
        'get_teacher_lock_status',
        'lock_cancel_requests_date',
        'allow_complete_work_date',
        'can_complete_requests_display',
    )
    list_filter = ('academic_year', 'semestr', 'department')
    search_fields = ('academic_year', 'department__department_name')
    readonly_fields = ('student_requests_locked_at', 'teacher_editing_locked_at')
    actions = ['action_reject_pending_requests', 'action_lock_active_themes', 'action_apply_all']
    actions_on_top = True
    actions_on_bottom = False

    fieldsets = (
        ('Основна інформація', {
            'fields': ('department', 'academic_year', 'semestr'),
            'description': (
                "Налаштування семестру для конкретної кафедри. "
                "Комбінація «Кафедра + Рік + Семестр» має бути унікальною."
            )
        }),
        ('Дедлайни та застосування дій', {
            'fields': (
                'lock_student_requests_date',
                'student_requests_locked_at',
                'lock_teacher_editing_themes_date',
                'teacher_editing_locked_at',
                'lock_cancel_requests_date',
                'allow_complete_work_date',
            ),
            'description': (
                "<b>Інструкція:</b><br>"
                "• Після настання дат дедлайнів скористайтеся діями вгорі списку, щоб застосувати зміни.<br>"
                "• «Відхилити запити, що очікують» — відхиляє всі запити зі статусом «Очікує».<br>"
                "• «Заблокувати теми в активних роботах» — увімкне блокування редагування тем (is_topic_locked=True).<br>"
                "• «Застосувати всі» — виконує обидві дії за потреби.<br>"
                "• Поля «...заблоковано о» заповнюються автоматично після виконання відповідних дій."
            )
        }),
    )

    # ----- access helpers (use OnlyTeacher.department) -----
    def _is_dept_admin(self, request):
        return request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser

    def _get_user_department(self, request):
        user = request.user  # <-- виправлено тут!
        if hasattr(user, "role") and user.role == "Викладач":
            try:
                ot = OnlyTeacher.objects.select_related('department').get(teacher_id=user)
                return ot.department
            except OnlyTeacher.DoesNotExist:
                return None
        elif hasattr(user, "role") and user.role == "Студент":
            try:
                os = OnlyStudent.objects.select_related('group__stream').get(student_id=user)
                if os.group and os.group.stream and hasattr(os.group.stream, "department"):
                    return os.group.stream.department
                if hasattr(os, "department"):
                    return os.department
            except OnlyStudent.DoesNotExist:
                return None
        return None

    def _allowed(self, request, obj):
        if request.user.is_superuser:
            return True
        if not self._is_dept_admin(request):
            return False
        user_dept = self._get_user_department(request)
        return user_dept and obj.department_id == user_dept.id

    # ----- queryset and form scoping -----
    
    def get_fieldsets(self, request, obj=None):
        base = super().get_fieldsets(request, obj)
        result = []
        for title, opts in base:
            opts = dict(opts)  # копія словника
            if 'fields' in opts:
                fields = list(opts['fields'])
                if request.user.is_superuser and 'apply_to_all_departments' not in fields:
                    fields.append('apply_to_all_departments')
                opts['fields'] = tuple(fields)
            result.append((title, opts))
        return result
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self._is_dept_admin(request):
            dept = self._get_user_department(request)
            if dept:
                return qs.filter(department=dept)
            # if no OnlyTeacher department, show nothing
            return qs.none()
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'department' and self._is_dept_admin(request):
            dept = self._get_user_department(request)
            kwargs['queryset'] = Department.objects.filter(pk=dept.pk) if dept else Department.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        if self._is_dept_admin(request):
            dept = self._get_user_department(request)
            if dept:
                data['department'] = dept.pk
        return data

    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)
        class ScopedForm(Form):
            def __init__(self2, *a, **k):
                super().__init__(*a, **k)
                # Показуємо чекбокс лише суперюзеру
                if not request.user.is_superuser and 'apply_to_all_departments' in self2.fields:
                    self2.fields.pop('apply_to_all_departments')
        return ScopedForm

    def save_model(self, request, obj, form, change):
        apply_all = form.cleaned_data.get('apply_to_all_departments', False)

        # Випадок для суперкористувача: пакетне створення
        if apply_all and request.user.is_superuser:
            ay = obj.academic_year
            sem = obj.semestr
            d_student = obj.lock_student_requests_date
            d_teacher = obj.lock_teacher_editing_themes_date
            d_cancel = obj.lock_cancel_requests_date
            d_complete = obj.allow_complete_work_date

            created = 0
            skipped = 0

            for dept in Department.objects.all():
                exists = Semestr.objects.filter(
                    department=dept, academic_year=ay, semestr=sem
                ).exists()
                if exists:
                    skipped += 1
                    continue

                s = Semestr(
                    department=dept,
                    academic_year=ay,
                    semestr=sem,
                    lock_student_requests_date=d_student,
                    lock_teacher_editing_themes_date=d_teacher,
                    lock_cancel_requests_date=d_cancel,
                    allow_complete_work_date=d_complete,
                )
                # clean() викликається у вашому save()
                s.save()
                created += 1

            if created:
                self.message_user(
                    request,
                    f"Створено {created} семестр(и/ів) для всіх кафедр. Пропущено (вже існували): {skipped}.",
                    level=messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    "Усі відповідні семестри вже існують — нічого не створено.",
                    level=messages.INFO
                )
            # Не зберігаємо поточний obj — це «шаблон» для розмноження
            return

        # Звичайна гілка: діє ваша існуюча логіка доступів
        if self._is_dept_admin(request):
            dept = self._get_user_department(request)
            if not dept:
                self.message_user(request, "Не знайдено кафедру для користувача в OnlyTeacher.", level=messages.ERROR)
                return
            obj.department = dept

        super().save_model(request, obj, form, change)

    # ----- object-level permissions -----
    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not self._is_dept_admin(request):
            return False
        if obj is None:
            return True
        return self._allowed(request, obj)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not self._is_dept_admin(request):
            return False
        if obj is None:
            return True
        return self._allowed(request, obj)

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not self._is_dept_admin(request):
            return False
        if obj is None:
            return False
        return self._allowed(request, obj)

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        if not self._is_dept_admin(request):
            return False
        return self._get_user_department(request) is not None



    @admin.display(description="Статус блокування подачі")
    def get_student_lock_status(self, obj):
        if obj.student_requests_locked_at:
            return f"Застосовано {obj.student_requests_locked_at.strftime('%d.%m.%Y %H:%M')}"
        if obj.lock_student_requests_date:
            today = timezone.now().date()
            return ("Дедлайн минув, очікує застосування"
                    if today >= obj.lock_student_requests_date
                    else f"Дедлайн {obj.lock_student_requests_date.strftime('%d.%m.%Y')}")
        return "—"

    @admin.display(description="Статус блокування тем")
    def get_teacher_lock_status(self, obj):
        if obj.teacher_editing_locked_at:
            return f"Застосовано {obj.teacher_editing_locked_at.strftime('%d.%m.%Y %H:%M')}"
        if obj.lock_teacher_editing_themes_date:
            today = timezone.now().date()
            return ("Дедлайн минув, очікує застосування"
                    if today >= obj.lock_teacher_editing_themes_date
                    else f"Дедлайн {obj.lock_teacher_editing_themes_date.strftime('%d.%m.%Y')}")
        return "—"

    @admin.display(description="Можна завершувати роботи")
    def can_complete_requests_display(self, obj):
        if obj.can_complete_requests():
            return "Так"
        if obj.allow_complete_work_date:
            return f"З {obj.allow_complete_work_date.strftime('%d.%m.%Y')}"
        return "Ні"

    @admin.action(description="Відхилити запити, що очікують (після дедлайну)")
    def action_reject_pending_requests(self, request, queryset):
        total = 0
        processed = 0
        for sem in queryset:
            if not self._allowed(request, sem):
                self.message_user(request, f"Немає прав для {sem}", level=messages.WARNING)
                continue
            count = sem.apply_student_requests_cancellation()
            total += count
            processed += 1
        if total:
            self.message_user(request, f"Успішно відхилено {total} запитів (семестрів: {processed}).", level=messages.SUCCESS)
        else:
            self.message_user(request, "Жодних запитів для відхилення не знайдено або дедлайни ще не настали.", level=messages.INFO)

    @admin.action(description="Заблокувати теми в активних роботах (після дедлайну)")
    def action_lock_active_themes(self, request, queryset):
        total = 0
        processed = 0
        for sem in queryset:
            if not self._allowed(request, sem):
                self.message_user(request, f"Немає прав для {sem}", level=messages.WARNING)
                continue
            count = sem.apply_teacher_editing_lock()
            total += count
            processed += 1
        if total:
            self.message_user(request, f"Заблоковано {total} тем (семестрів: {processed}).", level=messages.SUCCESS)
        else:
            self.message_user(request, "Жодних тем для блокування не знайдено або дедлайни ще не настали.", level=messages.INFO)

    @admin.action(description="Застосувати всі дедлайни (комплексна дія)")
    def action_apply_all(self, request, queryset):
        stats = {'rejected': 0, 'locked': 0, 'processed': 0}
        for sem in queryset:
            if not self._allowed(request, sem):
                self.message_user(request, f"Немає прав для {sem}", level=messages.WARNING)
                continue
            result = sem.apply_all_deadlines()
            stats['rejected'] += result['rejected_pending']
            stats['locked'] += result['locked_themes']
            stats['processed'] += 1
        if stats['rejected'] or stats['locked']:
            self.message_user(
                request,
                f"Оброблено {stats['processed']} семестрів. Відхилено: {stats['rejected']}, Заблоковано: {stats['locked']}.",
                level=messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                f"Оброблено {stats['processed']} семестрів. Змін не виявлено.",
                level=messages.INFO
            )
# І нарешті реєструємо модель:
admin.site.register(Stream, StreamAdmin)

admin.site.register(OnlyTeacher, OnlyTeacherAdmin)

admin.site.register(Request, RequestAdmin)

# Реєструємо модель TeacherTheme в адмінці з новою конфігурацією
admin.site.register(TeacherTheme, TeacherThemeAdmin)

# Correctly register the model with the admin site:
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Slot, SlotAdmin)
admin.site.register(Semestr, SemestrAdmin)