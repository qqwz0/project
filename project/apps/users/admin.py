from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.db.models import F, Q
from django.http import FileResponse, HttpResponse
from django.urls import reverse, path
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from django.shortcuts import render
import re
import requests
from django.urls import path
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone

from docxtpl import DocxTemplate

from .models import CustomUser, StudentExcelMapping, StudentRequestMapping
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
        (_('Personal info'), {'fields': ('last_name', 'first_name', 'patronymic', 'academic_group')}),
        (_('Permissions'), {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'last_name', 'first_name', 'patronymic', 'academic_group', 'role',
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
        # Прибираємо фільтрацію по кафедрі для CustomUser
        return qs

    @admin.display(description='ПІБ')
    def get_full_name(self, obj):
        return obj.get_full_name_with_patronymic()

    @admin.display(description='Група')
    def get_academic_group(self, obj):
        return obj.academic_group or "—"


    
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
        if obj.teacher_id and hasattr(obj.teacher_id, 'department') and obj.teacher_id.department:
            return obj.teacher_id.department.department_name
        return "—"

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
    "ФЕПВПК": '121ВПК "Високопродуктивний комп\'ютинг"',
    "ФЕІ": '122 "Комп\'ютерні науки"',
    "ФЕМ": '171 "Електроніка та комп\'ютерні системи"',
    "ФЕЛ": '176 "Сенсорні та діагностичні електронні системи"',
}

# Мапа повних назв кафедр до коротких
DEPARTMENT_SHORT_NAMES = {
    'Системного проектування': 'СП',
    'Оптоелектроніки та інформаційних технологій': 'КОІТ',
    'Радіофізики та комп\'ютерних технологій': 'РКТ',
    'Радіоелектронних і комп\'ютерних систем': 'РКС',
    'Фізичної та біомедичної електроніки': 'ФБМЕ',
    'Сенсорної та напівпровідникової електроніки': 'СНПЕ',
}

# Список дозволених кафедр (case insensitive)
ALLOWED_DEPARTMENTS = [
    'СП', 'КОІТ', 'РКТ', 'РКС', 'ФБМЕ', 'СНПЕ',  # Короткі назви
    'Системного проектування',
    'Оптоелектроніки та інформаційних технологій',
    'Радіофізики та комп\'ютерних технологій',
    'Радіоелектронних і комп\'ютерних систем',
    'Фізичної та біомедичної електроніки',
    'Сенсорної та напівпровідникової електроніки',
]

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
    list_display = ('get_full_name', 'academic_level', 'additional_email', 'phone_number', 'department')
    actions = ['import_teachers_from_excel']

    # Всі поля моделі
    fields = ('teacher_id', 'academic_level', 'additional_email', 'phone_number', 'profile_link', 'department')
    readonly_fields = ()  # всі редаговані

    search_fields = (
        'teacher_id__first_name',
        'teacher_id__last_name',
        'teacher_id__patronymic',
        'additional_email',
        'phone_number',
    )

    def view_on_site(self, obj):
        if obj.teacher_id and obj.teacher_id.pk:
            return reverse('profile_detail', args=[obj.teacher_id.pk])
        return None

    # Повний доступ: додавання, редагування, видалення
    def has_add_permission(self, request):
        return True

    def has_delete_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    @admin.display(description='Викладач')
    def get_full_name(self, obj):
        return f"{obj.teacher_id.first_name} {obj.teacher_id.last_name} {obj.teacher_id.patronymic or ''}"

    @admin.action(description='Імпорт викладачів з Excel файлу')
    def import_teachers_from_excel(self, request, queryset):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(reverse('import_teachers_excel'))



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
    # якщо треба редагувати user, прибери student_id з readonly
    readonly_fields = ('student_id',)  
    fields = ('group', 'department', 'additional_email', 'phone_number')

    # дозволяємо додавання
    def has_add_permission(self, request):
        return True  

    # дозволяємо видалення
    def has_delete_permission(self, request, obj=None):
        return True  

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
        if obj.student_id and obj.student_id.pk:
            return reverse('profile_detail', args=[obj.student_id.pk])
        return None

    
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
        if obj.student_id and obj.student_id.pk:
            return reverse('profile_detail', args=[obj.student_id.pk])
        return None

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

    @admin.display(description='Студент — Викладач')
    def get_student_teacher(self, obj):
        if not obj.student_id or not obj.teacher_id or not obj.teacher_id.teacher_id:
            return "—"
        student_name = obj.student_id.get_full_name_with_patronymic()
        teacher_name = obj.teacher_id.teacher_id.get_full_name_with_patronymic()
        return f"{student_name} — {teacher_name}"

    @admin.display(description='Кафедра викладача',
                   ordering='teacher_id__department__department_name')
    def get_teacher_department(self, obj):
        if obj.teacher_id and hasattr(obj.teacher_id, 'department') and obj.teacher_id.department:
            return obj.teacher_id.department.department_name
        return "—"

    @admin.display(description='Група студента',
                   ordering='student_id__academic_group')
    def get_student_group(self, obj):
        if not obj.student_id:
            return "—"
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
        if obj.student_id and obj.student_id.pk:
            return reverse('profile_detail', args=[obj.student_id.pk])
        return None
    
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
            'fields': ('department', 'academic_year', 'semestr', 'apply_to_all_departments'),
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
        try:
            user = request.user
            if not hasattr(user, "role"):
                return None
                
            if user.role == "Викладач":
                try:
                    ot = OnlyTeacher.objects.select_related('department').get(teacher_id=user)
                    if not ot.department:
                        return None
                    return ot.department
                except OnlyTeacher.DoesNotExist:
                    return None
                    
            elif user.role == "Студент":
                try:
                    os = OnlyStudent.objects.select_related('group__stream').get(student_id=user)
                    if os.group and os.group.stream and hasattr(os.group.stream, "department"):
                        return os.group.stream.department
                    if hasattr(os, "department"):
                        return os.department
                except OnlyStudent.DoesNotExist:
                    return None
                    
        except Exception:
            return None
            
        return None



    # ----- queryset and form scoping -----    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self._is_dept_admin(request):
            dept = self._get_user_department(request)
            if dept:
                return qs.filter(department=dept)
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
                # Блокуємо чекбокс для адмінів кафедр
                if 'apply_to_all_departments' in self2.fields:
                    if self._is_dept_admin(request):
                        self2.fields['apply_to_all_departments'].disabled = True
                        self2.fields['apply_to_all_departments'].help_text = "Доступно лише суперадміністраторам"
        return ScopedForm

    def save_model(self, request, obj, form, change):
        try:
            apply_all = form.cleaned_data.get('apply_to_all_departments', False)

            if apply_all and request.user.is_superuser:
                from django.db import transaction
                
                ay = obj.academic_year
                sem = obj.semestr
                d_student = obj.lock_student_requests_date
                d_teacher = obj.lock_teacher_editing_themes_date
                d_cancel = obj.lock_cancel_requests_date
                d_complete = obj.allow_complete_work_date

                created = 0
                skipped = 0
                errors = []

                with transaction.atomic():
                    for dept in Department.objects.all():
                        try:
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
                            s.save()
                            created += 1
                            
                        except Exception as e:
                            errors.append(f"Помилка для {dept.department_name}: {str(e)}")

                if errors:
                    self.message_user(
                        request,
                        f"Створено {created}, пропущено {skipped}. Помилки: {'; '.join(errors[:3])}",
                        level=messages.WARNING
                    )
                elif created:
                    self.message_user(
                        request,
                        f"Створено {created} семестр(и/ів) для всіх кафедр. Пропущено: {skipped}.",
                        level=messages.SUCCESS
                    )
                else:
                    self.message_user(
                        request,
                        "Усі відповідні семестри вже існують — нічого не створено.",
                        level=messages.INFO
                    )
                return

            if self._is_dept_admin(request):
                dept = self._get_user_department(request)
                if not dept:
                    self.message_user(
                        request, 
                        "Не знайдено кафедру для користувача.", 
                        level=messages.ERROR
                    )
                    return
                obj.department = dept

            super().save_model(request, obj, form, change)
            
        except Exception as e:
            self.message_user(
                request,
                f"Помилка збереження: {str(e)}",
                level=messages.ERROR
            )

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
        skipped = 0
        errors = []
        
        user_dept = None
        if self._is_dept_admin(request):
            user_dept = self._get_user_department(request)
            if not user_dept:
                self.message_user(request, "Не знайдено кафедру для користувача.", level=messages.ERROR)
                return
            
        for sem in queryset:
            if self._is_dept_admin(request):
                if not sem.department or sem.department != user_dept.id:
                    skipped += 1
                    continue
            try:
                count = sem.apply_student_request_cancellations()
                total += count
                processed += 1
            except Exception as e:
                errors.append(f"Помилка для {sem}: {str(e)}")    
            
        if errors:
            self.message_user(request, f"Помилки: {'; '.join(errors[:3])}", level=messages.ERROR)
        if total:
            self.message_user(request, f"Відхилено {total} запитів (семестрів: {processed}).", level=messages.SUCCESS)
        else:
            self.message_user(request, "Жодних запитів для відхилення не знайдено або дедлайни ще не настали.", level=messages.INFO)

    @admin.action(description="Відхилити запити, що очікують (після дедлайну)")
    def action_reject_pending_requests(self, request, queryset):
        total = 0
        processed = 0
        skipped = 0
        errors = []

        user_dept = None
        if self._is_dept_admin(request):
            user_dept = self._get_user_department(request)
            if not user_dept:
                self.message_user(request, "Не знайдено кафедру для вашого користувача.", level=messages.ERROR)
                return
        
        for sem in queryset:
            if self._is_dept_admin(request):
                if not sem.department or sem.department.id != user_dept.id:
                    skipped += 1
                    continue
            
            try:
                count = sem.apply_student_requests_cancellation()
                total += count
                processed += 1
            except Exception as e:
                errors.append(f"Помилка для {sem}: {str(e)}")
        
        if errors:
            self.message_user(request, f"Помилки: {'; '.join(errors[:3])}", level=messages.ERROR)
        
        if skipped > 0:
            self.message_user(request, f"Пропущено {skipped} семестрів (немає прав доступу).", level=messages.WARNING)
        
        if total:
            self.message_user(request, f"Відхилено {total} запитів у {processed} семестрах.", level=messages.SUCCESS)
        elif processed == 0:
            self.message_user(request, "Немає семестрів для обробки або немає прав доступу.", level=messages.INFO)
        else:
            self.message_user(request, "Жодних запитів для відхилення не знайдено або дедлайни ще не настали.", level=messages.INFO)

    @admin.action(description="Заблокувати теми в активних роботах (після дедлайну)")
    def action_lock_active_themes(self, request, queryset):
        total = 0
        processed = 0
        skipped = 0
        errors = []
        
        user_dept = None
        if self._is_dept_admin(request):
            user_dept = self._get_user_department(request)
            if not user_dept:
                self.message_user(request, "Не знайдено кафедру для вашого користувача.", level=messages.ERROR)
                return
        
        for sem in queryset:
            if self._is_dept_admin(request):
                if not sem.department or sem.department.id != user_dept.id:
                    skipped += 1
                    continue
            
            try:
                count = sem.apply_teacher_editing_lock()
                total += count
                processed += 1
            except Exception as e:
                errors.append(f"Помилка для {sem}: {str(e)}")
        
        if errors:
            self.message_user(request, f"Помилки: {'; '.join(errors[:3])}", level=messages.ERROR)
        
        if skipped > 0:
            self.message_user(request, f"Пропущено {skipped} семестрів (немає прав доступу).", level=messages.WARNING)
        
        if total:
            self.message_user(request, f"Заблоковано {total} тем у {processed} семестрах.", level=messages.SUCCESS)
        elif processed == 0:
            self.message_user(request, "Немає семестрів для обробки або немає прав доступу.", level=messages.INFO)
        else:
            self.message_user(request, "Жодних тем для блокування не знайдено або дедлайни ще не настали.", level=messages.INFO)

    @admin.action(description="Застосувати всі дедлайни (комплексна дія)")
    def action_apply_all(self, request, queryset):
        stats = {'rejected': 0, 'locked': 0, 'processed': 0, 'skipped': 0}
        errors = []
        
        # Отримуємо кафедру адміна тільки якщо це НЕ суперюзер
        user_dept = None
        if self._is_dept_admin(request):
            user_dept = self._get_user_department(request)
            if not user_dept:
                self.message_user(request, "Не знайдено кафедру для вашого користувача.", level=messages.ERROR)
                return
        
        for sem in queryset:
            # Перевіряємо права доступу ТІЛЬКИ для адмінів кафедр
            if self._is_dept_admin(request):
                if not sem.department or sem.department.id != user_dept.id:
                    stats['skipped'] += 1
                    continue
            
            try:
                result = sem.apply_all_deadlines()
                stats['rejected'] += result['rejected_pending']
                stats['locked'] += result['locked_themes']
                stats['processed'] += 1
            except Exception as e:
                errors.append(f"Помилка для {sem}: {str(e)}")
        
        if errors:
            self.message_user(request, f"Помилки: {'; '.join(errors[:3])}", level=messages.ERROR)
        
        if stats['skipped'] > 0:
            self.message_user(
                request,
                f"Пропущено {stats['skipped']} семестрів (немає прав доступу).",
                level=messages.WARNING
            )
        
        if stats['rejected'] or stats['locked']:
            self.message_user(
                request,
                f"Оброблено {stats['processed']} семестрів. Відхилено: {stats['rejected']}, Заблоковано: {stats['locked']}.",
                level=messages.SUCCESS
            )
        elif stats['processed'] == 0:
            self.message_user(
                request,
                "Немає семестрів для обробки або немає прав доступу.",
                level=messages.INFO
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

# Додаємо view для імпорту Excel файлів
def import_teachers_excel_view(request):
    """
    View для відображення форми імпорту Excel файлів викладачів
    """
    if request.method == 'POST':
        from django.http import JsonResponse
        from django.contrib import messages
        import pandas as pd
        from apps.catalog.models import Department, Stream, Slot, TeacherTheme, Faculty
        from apps.users.models import CustomUser, StudentExcelMapping, StudentRequestMapping
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            # Отримуємо файл з request
            excel_file = request.FILES.get('excel_file')
            if not excel_file:
                return JsonResponse({'error': 'Файл не вибрано'}, status=400)
            
            # Читаємо Excel файл
            df = pd.read_excel(excel_file, engine='openpyxl')
            
            # Валідація структури файлу (case insensitive)
            required_columns = ['Прізвище', 'Ім\'я', 'По-батькові', 'Адреса корпоративної скриньки', 'Кафедра']
            stream_columns = list(Stream.objects.values_list('stream_code', flat=True))
            
            # Створюємо мапінг колонок (оригінальна назва -> нормалізована)
            column_mapping = {}
            for col in df.columns:
                normalized_col = col.strip()  # Видаляємо пробіли
                column_mapping[normalized_col] = col
            
            # Перевіряємо наявність обов'язкових колонок (case insensitive)
            missing_columns = []
            for req_col in required_columns:
                found = False
                for df_col in df.columns:
                    if df_col.strip().lower() == req_col.lower():
                        found = True
                        break
                if not found:
                    missing_columns.append(req_col)
            
            if missing_columns:
                return JsonResponse({
                    'error': f'Відсутні обов\'язкові колонки: {", ".join(missing_columns)}'
                }, status=400)
            
            # Перевіряємо наявність колонок потоків (case insensitive)
            available_stream_columns = []
            for stream_col in stream_columns:
                for df_col in df.columns:
                    if df_col.strip().lower() == stream_col.lower():
                        available_stream_columns.append(df_col)  # Використовуємо оригінальну назву
                        break
            
            if not available_stream_columns:
                return JsonResponse({
                    'error': 'Не знайдено колонок з кількістю слотів для потоків'
                }, status=400)
            
            success_count = 0
            error_count = 0
            errors = []
            
            # Отримуємо перший факультет (або створюємо якщо немає)
            faculty = Faculty.objects.first()
            if not faculty:
                faculty = Faculty.objects.create(
                    name="Факультет електроніки та комп'ютерних технологій",
                    short_name="electronics"
                )
            
            # Створюємо мапінг для швидкого пошуку колонок (case insensitive)
            def find_column(df_columns, target_column):
                """Знаходить колонку в DataFrame нечутливо до регістру"""
                for col in df_columns:
                    if col.strip().lower() == target_column.lower():
                        return col
                return None
            
            # Обробляємо кожен рядок
            for index, row in df.iterrows():
                try:
                    # Знаходимо колонки (case insensitive)
                    last_name_col = find_column(df.columns, 'Прізвище')
                    first_name_col = find_column(df.columns, 'Ім\'я')
                    patronymic_col = find_column(df.columns, 'По-батькові')
                    email_col = find_column(df.columns, 'Адреса корпоративної скриньки')
                    department_col = find_column(df.columns, 'Кафедра')
                    
                    # Валідація обов'язкових полів
                    if pd.isna(row[last_name_col]) or pd.isna(row[first_name_col]) or pd.isna(row[email_col]):
                        errors.append(f'Рядок {index + 2}: Пропущено обов\'язкові поля')
                        error_count += 1
                        continue
                    
                    # Отримуємо дані користувача
                    last_name = str(row[last_name_col]).strip()
                    first_name = str(row[first_name_col]).strip()
                    patronymic = str(row[patronymic_col]).strip() if patronymic_col and not pd.isna(row[patronymic_col]) else ''
                    email = str(row[email_col]).strip()
                    department_name = str(row[department_col]).strip() if department_col and not pd.isna(row[department_col]) else ''
                    
                    # Валідація email
                    if '@lnu.edu.ua' not in email:
                        errors.append(f'Рядок {index + 2}: Невірний email {email}')
                        error_count += 1
                        continue
                    
                    # Знаходимо або створюємо кафедру (case insensitive)
                    department = None
                    if department_name:
                        # Валідація кафедри - перевіряємо, чи вона дозволена
                        department_name_clean = department_name.strip()
                        is_allowed_department = False
                        for allowed_dept in ALLOWED_DEPARTMENTS:
                            if department_name_clean.upper() == allowed_dept.upper():
                                is_allowed_department = True
                                break
                        
                        if not is_allowed_department:
                            errors.append(f'Рядок {index + 2}: Недозволена кафедра "{department_name_clean}". Дозволені: {", ".join(ALLOWED_DEPARTMENTS[:6])}')
                            error_count += 1
                            continue
                        
                        # Перевіряємо, чи це коротка назва кафедри (case insensitive)
                        full_department_name = None
                        for full_name, short_name in DEPARTMENT_SHORT_NAMES.items():
                            if department_name_clean.upper() == short_name.upper():
                                full_department_name = full_name
                                break
                        
                        # Якщо не знайшли в мапінгу, шукаємо в існуючих кафедрах (case insensitive)
                        if not full_department_name:
                            existing_departments = Department.objects.all()
                            for dept in existing_departments:
                                if dept.department_name.strip().upper() == department_name_clean.upper():
                                    full_department_name = dept.department_name
                                    break
                        
                        # Якщо все ще не знайшли, використовуємо оригінальну назву
                        final_department_name = full_department_name or department_name_clean
                        
                        # Перевіряємо, чи кафедра існує
                        try:
                            department = Department.objects.get(department_name__iexact=final_department_name)
                        except Department.DoesNotExist:
                            errors.append(f'Рядок {index + 2}: Кафедра "{final_department_name}" не існує в системі. Дозволені: {", ".join(ALLOWED_DEPARTMENTS[:6])}')
                            error_count += 1
                            continue
                    
                    # Створюємо або знаходимо користувача
                    user, user_created = CustomUser.objects.get_or_create(
                        email=email,
                        defaults={
                            'first_name': first_name,
                            'last_name': last_name,
                            'patronymic': patronymic,
                            'role': 'Викладач',
                            'is_active': True,
                            'is_staff': False,
                        }
                    )
                    
                    if not user_created:
                        # Оновлюємо існуючого користувача
                        user.first_name = first_name
                        user.last_name = last_name
                        user.patronymic = patronymic
                        user.save()
                    
                    # Створюємо або оновлюємо профіль викладача з profile_link
                    from apps.users.services.registration_services import create_teacher_profile
                    teacher_profile = create_teacher_profile(user, 'Викладач', department)
                    
                    # Створюємо слоти для потоків
                    for stream_col in available_stream_columns:
                        slots_count = row[stream_col]
                        if pd.notna(slots_count) and int(slots_count) > 0:
                            try:
                                # Визначаємо код потоку з назви колонки (case insensitive)
                                # Знаходимо відповідний код потоку зі списку stream_columns
                                stream_code = None
                                for expected_stream in stream_columns:
                                    if stream_col.strip().lower() == expected_stream.lower():
                                        stream_code = expected_stream
                                        break
                                
                                if not stream_code:
                                    errors.append(f'Рядок {index + 2}: Невідома колонка потоку: {stream_col}')
                                    error_count += 1
                                    continue
                                
                                # Знаходимо потік
                                stream = Stream.objects.get(stream_code=stream_code)
                                
                                # Створюємо або оновлюємо слот
                                slot, slot_created = Slot.objects.get_or_create(
                                    teacher_id=teacher_profile,
                                    stream_id=stream,
                                    defaults={'quota': int(slots_count), 'occupied': 0}
                                )
                                
                                if not slot_created:
                                    slot.quota = int(slots_count)
                                    slot.save()
                                
                                # Теми створюються окремо через систему імпорту тем
                                # Не створюємо автоматичні теми тут
                                
                            except Stream.DoesNotExist:
                                errors.append(f'Рядок {index + 2}: Потік {stream_code} не знайдено')
                                error_count += 1
                                continue
                            except Exception as e:
                                errors.append(f'Рядок {index + 2}: Помилка створення слоту для {stream_code}: {str(e)}')
                                error_count += 1
                                continue
                    
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f'Рядок {index + 2}: Загальна помилка: {str(e)}')
                    error_count += 1
                    continue
            
            # Оновлюємо зайнятість всіх слотів після імпорту
            from apps.catalog.models import Slot
            all_slots = Slot.objects.all()
            for slot in all_slots:
                slot.get_available_slots()  # Це оновить occupied для кожного слота
            
            # Логуємо результат імпорту
            logger.info(f"Імпорт тем завершено. Успішно: {success_count}, Помилок: {error_count}")
            if errors:
                logger.warning(f"Помилки при імпорті тем: {errors[:5]}")  # Логуємо перші 5 помилок
            
            # Формуємо результат
            result_message = f'Імпорт завершено. Успішно: {success_count}, Помилок: {error_count}'
            if errors:
                result_message += f'\nПомилки:\n' + '\n'.join(errors[:10])  # Показуємо перші 10 помилок
                if len(errors) > 10:
                    result_message += f'\n... та ще {len(errors) - 10} помилок'
            
            return JsonResponse({
                'success': True,
                'message': result_message,
                'success_count': success_count,
                'error_count': error_count
            })
            
        except Exception as e:
            logger.error(f'Помилка імпорту Excel: {str(e)}')
            return JsonResponse({'error': f'Помилка обробки файлу: {str(e)}'}, status=500)
    
    return render(request, 'admin/import_teachers_excel.html')


def import_students_excel_view(request):
    """
    View для відображення форми імпорту Excel файлів студентів
    """
    if request.method == 'POST':
        from django.http import JsonResponse
        import pandas as pd
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            excel_file = request.FILES.get('excel_file')
            if not excel_file:
                return JsonResponse({'error': 'Файл не вибрано'}, status=400)
            
            # Читаємо Excel файл
            df = pd.read_excel(excel_file, engine='openpyxl')
            
            # Валідація структури файлу (case insensitive)
            required_columns = ['Прізвище', 'Ім\'я', 'По-батькові', 'Кафедра', 'Група']
            
            # Перевіряємо наявність обов'язкових колонок (case insensitive)
            missing_columns = []
            for req_col in required_columns:
                found = False
                for df_col in df.columns:
                    if df_col.strip().lower() == req_col.lower():
                        found = True
                        break
                if not found:
                    missing_columns.append(req_col)
            
            if missing_columns:
                return JsonResponse({
                    'error': f'Відсутні обов\'язкові колонки: {", ".join(missing_columns)}'
                }, status=400)
            
            success_count = 0
            error_count = 0
            errors = []
            
            # Створюємо мапінг для швидкого пошуку колонок (case insensitive)
            def find_column(df_columns, target_column):
                """Знаходить колонку в DataFrame нечутливо до регістру"""
                for col in df_columns:
                    if col.strip().lower() == target_column.lower():
                        return col
                return None
            
            # Обробляємо кожен рядок
            for index, row in df.iterrows():
                try:
                    # Знаходимо колонки (case insensitive)
                    last_name_col = find_column(df.columns, 'Прізвище')
                    first_name_col = find_column(df.columns, 'Ім\'я')
                    patronymic_col = find_column(df.columns, 'По-батькові')
                    department_col = find_column(df.columns, 'Кафедра')
                    group_col = find_column(df.columns, 'Група')
                    
                    # Валідація обов'язкових полів
                    if pd.isna(row[last_name_col]) or pd.isna(row[first_name_col]) or pd.isna(row[group_col]):
                        errors.append(f'Рядок {index + 2}: Пропущено обов\'язкові поля')
                        error_count += 1
                        continue
                    
                    # Отримуємо дані студента
                    last_name = str(row[last_name_col]).strip()
                    first_name = str(row[first_name_col]).strip()
                    patronymic = str(row[patronymic_col]).strip() if patronymic_col and not pd.isna(row[patronymic_col]) else ''
                    department = str(row[department_col]).strip() if department_col and not pd.isna(row[department_col]) else ''
                    group = str(row[group_col]).strip()
                    
                    # Валідація кафедри - перевіряємо, чи вона дозволена
                    if department:
                        department_clean = department.strip()
                        is_allowed_department = False
                        for allowed_dept in ALLOWED_DEPARTMENTS:
                            if department_clean.upper() == allowed_dept.upper():
                                is_allowed_department = True
                                break
                        
                        if not is_allowed_department:
                            errors.append(f'Рядок {index + 2}: Nедозволена кафедра "{department_clean}". Дозволені: {", ".join(ALLOWED_DEPARTMENTS[:6])}')
                            error_count += 1
                            continue
                    
                    # Створюємо або оновлюємо запис мапінгу
                    mapping, created = StudentExcelMapping.objects.get_or_create(
                        last_name=last_name,
                        first_name=first_name,
                        patronymic=patronymic,
                        group=group,
                        defaults={'department': department}
                    )
                    
                    if not created:
                        # Оновлюємо існуючий запис
                        mapping.department = department
                        mapping.save()
                    
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f'Рядок {index + 2}: Загальна помилка: {str(e)}')
                    error_count += 1
                    continue
            
            # Формуємо результат
            result_message = f'Імпорт завершено. Успішно: {success_count}, Помилок: {error_count}'
            if errors:
                result_message += f'\nПомилки:\n' + '\n'.join(errors[:10])
                if len(errors) > 10:
                    result_message += f'\n... та ще {len(errors) - 10} помилок'
            
            return JsonResponse({
                'success': True,
                'message': result_message,
                'success_count': success_count,
                'error_count': error_count
            })
            
        except Exception as e:
            logger.error(f'Помилка імпорту Excel студентів: {str(e)}')
            return JsonResponse({'error': f'Помилка обробки файлу: {str(e)}'}, status=500)
    
    return render(request, 'admin/import_students_excel.html')


def import_themes_excel_view(request):
    """
    View для відображення форми імпорту Excel файлів тем викладачів
    """
    print(f"DEBUG: import_themes_excel_view викликано, method: {request.method}")
    print(f"DEBUG: request.FILES: {request.FILES}")
    if request.method == 'POST':
        from django.http import JsonResponse
        import pandas as pd
        import logging
        from apps.catalog.models import TeacherTheme, Stream, Slot, Request
        from apps.users.models import StudentExcelMapping
        
        logger = logging.getLogger(__name__)
        
        try:
            excel_file = request.FILES.get('excel_file')
            if not excel_file:
                return JsonResponse({'error': 'Файл не вибрано'}, status=400)
            
            # Читаємо Excel файл
            df = pd.read_excel(excel_file, engine='openpyxl')
            
            # Логуємо структуру файлу для дебагу
            print(f"DEBUG: Загальна кількість рядків: {len(df)}")
            print(f"DEBUG: Колонки в файлі: {list(df.columns)}")
            print(f"DEBUG: Перші 3 рядки:")
            print(df.head(3).to_string())
            
            # Валідація структури файлу (case insensitive)
            required_columns = ['Корпоративна скринька', 'Потік', 'Тема']  # Студент не обов'язковий
            
            # Перевіряємо наявність обов'язкових колонок (case insensitive)
            missing_columns = []
            for req_col in required_columns:
                found = False
                for df_col in df.columns:
                    if df_col.strip().lower() == req_col.lower():
                        found = True
                        break
                if not found:
                    missing_columns.append(req_col)
            
            if missing_columns:
                return JsonResponse({
                    'error': f'Відсутні обов\'язкові колонки: {", ".join(missing_columns)}'
                }, status=400)
            
            success_count = 0
            error_count = 0
            errors = []
            
            # Створюємо мапінг для швидкого пошуку колонок (case insensitive)
            def find_column(df_columns, target_column):
                """Знаходить колонку в DataFrame нечутливо до регістру"""
                for col in df_columns:
                    if col.strip().lower() == target_column.lower():
                        return col
                return None
            
            # Групуємо теми по викладачах та потоках
            themes_by_teacher_stream = {}
            
            # Обробляємо кожен рядок
            print(f"DEBUG: Починаємо обробку {len(df)} рядків для імпорту тем")
            processed_rows = 0
            for index, row in df.iterrows():
                processed_rows += 1
                if processed_rows % 10 == 0:  # Логуємо кожні 10 рядків
                    print(f"DEBUG: Оброблено {processed_rows}/{len(df)} рядків")
                try:
                    # Знаходимо колонки (case insensitive)
                    email_col = find_column(df.columns, 'Корпоративна скринька')
                    stream_col = find_column(df.columns, 'Потік')
                    theme_col = find_column(df.columns, 'Тема')
                    student_col = find_column(df.columns, 'Студент')
                    description_col = find_column(df.columns, 'Опис теми (за бажанням)')
                    
                    print(f"DEBUG: Колонки знайдені - email: {email_col}, stream: {stream_col}, theme: {theme_col}, student: {student_col}")
                    
                    # Валідація обов'язкових полів
                    if email_col is None or stream_col is None or theme_col is None:
                        errors.append(f'Рядок {index + 2}: Не знайдено обов\'язкові колонки')
                        error_count += 1
                        continue
                    
                    # Перевіряємо, чи не є обов'язкові поля порожніми або NaN
                    email_empty = pd.isna(row[email_col]) or str(row[email_col]).strip() == '' or str(row[email_col]).strip().lower() == 'nan'
                    stream_empty = pd.isna(row[stream_col]) or str(row[stream_col]).strip() == '' or str(row[stream_col]).strip().lower() == 'nan'
                    theme_empty = pd.isna(row[theme_col]) or str(row[theme_col]).strip() == '' or str(row[theme_col]).strip().lower() == 'nan'
                    
                    # Студент не обов'язковий
                    student_empty = True
                    if student_col and not (pd.isna(row[student_col]) or str(row[student_col]).strip() == '' or str(row[student_col]).strip().lower() == 'nan'):
                        student_empty = False
                    
                    if email_empty or stream_empty or theme_empty:
                        missing_fields = []
                        if email_empty: missing_fields.append('email')
                        if stream_empty: missing_fields.append('stream')
                        if theme_empty: missing_fields.append('theme')
                        
                        errors.append(f'Рядок {index + 2}: Пропущено обов\'язкові поля: {", ".join(missing_fields)}')
                        error_count += 1
                        continue
                    
                    # Отримуємо дані теми
                    teacher_email = str(row[email_col]).strip()
                    stream_code = str(row[stream_col]).strip()
                    theme_title = str(row[theme_col]).strip()
                    student_name = str(row[student_col]).strip() if not student_empty else ''
                    theme_description = str(row[description_col]).strip() if description_col and not pd.isna(row[description_col]) else ''
                    
                    # Нормалізуємо грецькі літери до кириличних
                    greek_to_cyrillic = {
                        'Φ': 'Ф',  # Greek Phi to Cyrillic Ef
                        'Ε': 'Е',  # Greek Epsilon to Cyrillic E
                        'Ι': 'І',  # Greek Iota to Cyrillic I
                        'Μ': 'М',  # Greek Mu to Cyrillic M
                        'Π': 'П',  # Greek Pi to Cyrillic P
                        'Σ': 'С',  # Greek Sigma to Cyrillic S
                        'Λ': 'Л',  # Greek Lambda to Cyrillic L
                    }
                    
                    # Замінюємо грецькі літери в коді потоку
                    original_stream_code = stream_code
                    for greek, cyrillic in greek_to_cyrillic.items():
                        stream_code = stream_code.replace(greek, cyrillic)
                    
                    # Логування для дебагу
                    if original_stream_code != stream_code:
                        logger.info(f"Нормалізовано код потоку: {original_stream_code} -> {stream_code}")
                    
                    logger.info(f"Обробляємо рядок {index + 2}: email={teacher_email}, stream={stream_code}, theme={theme_title}, student={student_name}")
                    print(f"DEBUG: Обробляємо рядок {index + 2}: email={teacher_email}, stream={stream_code}, theme={theme_title}, student={student_name}")
                    
                    # Додаємо детальне логування для дебагу
                    print(f"DEBUG: Знайдені колонки - email: {email_col}, stream: {stream_col}, theme: {theme_col}, student: {student_col}")
                    print(f"DEBUG: Дані рядка - email: '{teacher_email}', stream: '{stream_code}', theme: '{theme_title}', student: '{student_name}'")
                    
                    # Додаємо логування для перевірки порожніх полів
                    print(f"DEBUG: Перевірка полів - email isna: {pd.isna(row[email_col])}, stream isna: {pd.isna(row[stream_col])}, theme isna: {pd.isna(row[theme_col])}, student isna: {pd.isna(row[student_col])}")
                    print(f"DEBUG: Перевірка порожніх рядків - email empty: '{str(row[email_col]).strip() == ''}', stream empty: '{str(row[stream_col]).strip() == ''}', theme empty: '{str(row[theme_col]).strip() == ''}', student empty: '{str(row[student_col]).strip() == ''}'")
                    
                    # Валідація email
                    if '@lnu.edu.ua' not in teacher_email:
                        errors.append(f'Рядок {index + 2}: Невірний email викладача {teacher_email}')
                        error_count += 1
                        continue
                    
                    # Групуємо по викладачу + потоку + темі
                    key = (teacher_email, stream_code, theme_title)
                    if key not in themes_by_teacher_stream:
                        themes_by_teacher_stream[key] = {
                            'theme_title': theme_title,
                            'theme_description': theme_description,
                            'students': []
                        }
                    
                    # Додаємо студента тільки якщо він є (з детальною перевіркою)
                    if student_name and not pd.isna(student_name):
                        # Очищаємо від пробілів та невидимих символів
                        student_name_clean = str(student_name).strip()
                        # Видаляємо невидимі символи
                        student_name_clean = ''.join(char for char in student_name_clean if char.isprintable()).strip()
                        
                        # Додаткова перевірка на системні значення
                        invalid_values = {'nan', 'none', 'null', 'undefined', '0', '1', 'true', 'false', 'yes', 'no', 'да', 'ні', 'так', 'ні', ''}
                        
                        if student_name_clean and student_name_clean.lower() not in invalid_values:
                            themes_by_teacher_stream[key]['students'].append(student_name_clean)
                            print(f"DEBUG: Додано студента '{student_name_clean}' до теми '{theme_title}'")
                        else:
                            print(f"DEBUG: Пропущено невалідне ім'я студента для теми '{theme_title}' (оригінал: {repr(student_name)}, очищене: {repr(student_name_clean)})")
                    else:
                        print(f"DEBUG: Пропущено порожнє/NaN ім'я студента для теми '{theme_title}' (оригінал: {repr(student_name)})")
                    
                except Exception as e:
                    error_msg = f'Рядок {index + 2}: Загальна помилка: {str(e)}'
                    errors.append(error_msg)
                    error_count += 1
                    print(f"ERROR: {error_msg}")
                    print(f"ERROR: Дані рядка: email={teacher_email}, stream={stream_code}, theme={theme_title}, student={student_name}")
                    import traceback
                    print(f"ERROR: Traceback: {traceback.format_exc()}")
                    continue
            
            print(f"DEBUG: Завершено обробку {processed_rows} рядків")
            print(f"DEBUG: Зібрано {len(themes_by_teacher_stream)} унікальних тем")
            
            # Створюємо теми та запити
            print(f"DEBUG: Зібрано {len(themes_by_teacher_stream)} унікальних тем з Excel файлу")
            print(f"DEBUG: Список тем: {list(themes_by_teacher_stream.keys())}")
            print(f"DEBUG: Починаємо обробку {len(themes_by_teacher_stream)} тем")
            created_themes_count = 0
            for (teacher_email, stream_code, theme_title), theme_data in themes_by_teacher_stream.items():
                print(f"DEBUG: Обробляємо тему '{theme_title}' для викладача {teacher_email}, потік {stream_code}")
                try:
                    # Знаходимо викладача
                    try:
                        teacher_user = CustomUser.objects.get(email=teacher_email, role='Викладач')
                        teacher_profile = teacher_user.catalog_teacher_profile
                    except CustomUser.DoesNotExist:
                        errors.append(f'Викладач з email {teacher_email} не знайдено')
                        error_count += 1
                        continue
                    
                    # Знаходимо потік
                    try:
                        stream = Stream.objects.get(stream_code=stream_code)
                        logger.info(f"Знайдено потік: {stream_code}")
                    except Stream.DoesNotExist:
                        # Спробуємо знайти потік case-insensitive
                        try:
                            stream = Stream.objects.get(stream_code__iexact=stream_code)
                            logger.info(f"Знайдено потік (case-insensitive): {stream_code}")
                        except Stream.DoesNotExist:
                            # Покажемо всі доступні потоки для дебагу
                            available_streams = list(Stream.objects.values_list('stream_code', flat=True))
                            logger.error(f"Потік {stream_code} не знайдено. Доступні: {available_streams}")
                            errors.append(f'Потік {stream_code} не знайдено. Доступні: {", ".join(available_streams[:10])}')
                            error_count += 1
                            continue
                    
                    # Створюємо тему викладача
                    # Тема буде зайнята, якщо є студенти
                    has_students = len(theme_data['students']) > 0
                    print(f"DEBUG: Створюємо тему '{theme_data['theme_title']}' для викладача {teacher_email}, потік {stream_code}")
                    print(f"DEBUG: Студенти: {theme_data['students']} (кількість: {len(theme_data['students'])})")
                    print(f"DEBUG: has_students: {has_students}")
                    theme, theme_created = TeacherTheme.objects.get_or_create(
                        teacher_id=teacher_profile,
                        theme=theme_data['theme_title'],
                        defaults={
                            'theme_description': theme_data['theme_description'],
                            'is_active': True,
                            'is_occupied': has_students,  # Зайнята, якщо є студенти
                        }
                    )
                    
                    # Якщо тема вже існує, але тепер є студенти - позначаємо як зайняту
                    if not theme_created and has_students and not theme.is_occupied:
                        theme.is_occupied = True
                        theme.save()
                    print(f"DEBUG: Тема створена: {theme_created}, ID: {theme.id}")
                    
                    # Завжди додаємо тему до потоку, незалежно від того, чи є студенти
                    if not theme.streams.filter(pk=stream.pk).exists():
                        theme.streams.add(stream)
                        print(f"DEBUG: Додано тему '{theme.theme}' до потоку {stream.stream_code}")
                    else:
                        print(f"DEBUG: Тема '{theme.theme}' вже прив'язана до потоку {stream.stream_code}")
                    
                    # Показуємо фінальний стан теми
                    final_streams = [s.stream_code for s in theme.streams.all()]
                    print(f"DEBUG: Фінальний стан теми '{theme.theme}': is_occupied={theme.is_occupied}, потоки={final_streams}")
                    
                    # Оновлюємо статус теми, якщо тепер є студенти
                    if has_students and not theme.is_occupied:
                        theme.is_occupied = True
                        theme.save()
                    
                    # НЕ оновлюємо слоти тут - це буде зроблено автоматично при створенні запитів
                    
                    # Створюємо запити для студентів (тільки якщо є студенти)
                    created_requests = 0
                    if theme_data['students']:  # Тільки якщо є студенти
                        for student_name in theme_data['students']:
                            try:
                                # Шукаємо студента в системі
                                student_user = None
                                
                                # Спочатку шукаємо в мапінгу
                                name_parts = student_name.strip().split()
                                if len(name_parts) >= 2:
                                    last_name = name_parts[0]
                                    first_name = name_parts[1]
                                    patronymic = name_parts[2] if len(name_parts) > 2 else ''
                                    
                                    student_mapping = StudentExcelMapping.objects.filter(
                                        last_name__icontains=last_name,
                                        first_name__icontains=first_name
                                    ).first()
                                    
                                    if not student_mapping and patronymic:
                                        # Спробуємо з по-батькові
                                        student_mapping = StudentExcelMapping.objects.filter(
                                            last_name__icontains=last_name,
                                            first_name__icontains=first_name,
                                            patronymic__icontains=patronymic
                                        ).first()
                                    
                                    # Якщо знайшли мапінг, шукаємо користувача
                                    if student_mapping:
                                        student_user = CustomUser.objects.filter(
                                            last_name__icontains=last_name,
                                            first_name__icontains=first_name,
                                            role='Студент'
                                        ).first()
                                        
                                        if not student_user and patronymic:
                                            student_user = CustomUser.objects.filter(
                                                last_name__icontains=last_name,
                                                first_name__icontains=first_name,
                                                patronymic__icontains=patronymic,
                                                role='Студент'
                                            ).first()
                                
                                # Якщо не знайшли через мапінг, спробуємо прямий пошук
                                if not student_user:
                                    student_user = CustomUser.objects.filter(
                                        last_name__icontains=name_parts[0] if name_parts else '',
                                        first_name__icontains=name_parts[1] if len(name_parts) > 1 else '',
                                        role='Студент'
                                    ).first()
                                
                                if not student_user:
                                    # Якщо студент не зареєстрований, створюємо "віртуальний" запит
                                    # з порожнім student_id, але з правильним слотом
                                    print(f"DEBUG: Студент {student_name} не зареєстрований, створюємо віртуальний запит")
                                    
                                    # Знаходимо слот для цього викладача та потоку
                                    slot = Slot.objects.filter(
                                        teacher_id=teacher_profile,
                                        stream_id=stream
                                    ).first()
                                    
                                    if not slot:
                                        errors.append(f'Слот для викладача {teacher_email} та потоку {stream_code} не знайдено')
                                        error_count += 1
                                        continue
                                    
                                    # Перевіряємо чи є вільні місця в слоті (використовуємо правильний метод)
                                    available_slots = slot.get_available_slots()
                                    if available_slots <= 0:
                                        errors.append(f'Слот для викладача {teacher_email} та потоку {stream_code} вже заповнений (зайнято: {slot.occupied}/{slot.quota})')
                                        error_count += 1
                                        continue
                                    
                                    # Створюємо віртуальний запит без student_id
                                    request_obj, request_created = Request.objects.get_or_create(
                                        teacher_id=teacher_profile,
                                        teacher_theme=theme,
                                        topic_name=theme_title,
                                        defaults={
                                            'request_status': 'Активний',
                                            'motivation_text': f'Віртуальний запит для не зареєстрованого студента: {student_name}',
                                            'slot': slot,
                                            'topic_description': theme_data['theme_description']
                                        }
                                    )
                                    
                                    if request_created:
                                        created_requests += 1
                                        print(f"DEBUG: Створено віртуальний запит для {student_name}")
                                    
                                    # Створюємо запис в StudentRequestMapping для автоматичного створення запитів
                                    StudentRequestMapping.objects.get_or_create(
                                        teacher_email=teacher_email,
                                        stream=stream_code,
                                        student_name=student_name,
                                        defaults={
                                            'theme': theme_title,
                                            'theme_description': theme_data['theme_description']
                                        }
                                    )
                                    
                                    success_count += 1
                                    continue
                                
                                # Знаходимо слот для цього викладача та потоку
                                slot = Slot.objects.filter(
                                    teacher_id=teacher_profile,
                                    stream_id=stream
                                ).first()
                                
                                if not slot:
                                    errors.append(f'Слот для викладача {teacher_email} та потоку {stream_code} не знайдено')
                                    error_count += 1
                                    continue
                                
                                # Перевіряємо чи є вільні місця в слоті (використовуємо правильний метод)
                                available_slots = slot.get_available_slots()
                                if available_slots <= 0:
                                    errors.append(f'Слот для викладача {teacher_email} та потоку {stream_code} вже заповнений (зайнято: {slot.occupied}/{slot.quota})')
                                    error_count += 1
                                    continue
                                
                                # Створюємо запит
                                request_obj, request_created = Request.objects.get_or_create(
                                    teacher_id=teacher_profile,
                                    student_id=student_user,
                                    teacher_theme=theme,
                                    defaults={
                                        'request_status': 'Активний',
                                        'motivation_text': f'Автоматично створений запит для теми: {theme_title}',
                                        'slot': slot,
                                        'topic_name': theme_title,
                                        'topic_description': theme_data['theme_description']
                                    }
                                )
                                
                                if request_created:
                                    created_requests += 1
                                    
                                    # Створюємо запис в StudentRequestMapping для автоматичного створення запитів
                                    StudentRequestMapping.objects.get_or_create(
                                        teacher_email=teacher_email,
                                        stream=stream_code,
                                        student_name=student_name,
                                        defaults={
                                            'theme': theme_title,
                                            'theme_description': theme_data['theme_description']
                                        }
                                    )
                                
                                success_count += 1
                                
                            except Exception as e:
                                errors.append(f'Помилка створення запиту для студента {student_name}: {str(e)}')
                                error_count += 1
                                continue
                    
                    # Оновлюємо слоти після створення всіх запитів для теми
                    if created_requests > 0:
                        # Знаходимо слот для цього викладача та потоку
                        slot = Slot.objects.filter(
                            teacher_id=teacher_profile,
                            stream_id=stream
                        ).first()
                        
                        if slot:
                            # Оновлюємо зайнятість слота використовуючи правильний метод
                            slot.update_occupied_slots(increment=0)  # Просто перераховуємо
                            print(f"DEBUG: Оновлено слот {slot.id}: зайнято {slot.occupied}/{slot.quota}")
                    
                    created_themes_count += 1
                    print(f"DEBUG: Успішно оброблено тему '{theme_data['theme_title']}' ({created_themes_count}/{len(themes_by_teacher_stream)})")
                    
                except Exception as e:
                    error_msg = f'Загальна помилка обробки теми {theme_data["theme_title"]}: {str(e)}'
                    errors.append(error_msg)
                    error_count += 1
                    print(f"ERROR: {error_msg}")
                    print(f"ERROR: Дані теми: email={teacher_email}, stream={stream_code}, theme={theme_data['theme_title']}")
                    print(f"ERROR: Студенти: {theme_data['students']}")
                    import traceback
                    print(f"ERROR: Traceback: {traceback.format_exc()}")
                    continue
            
            print(f"DEBUG: Завершено створення тем. Створено: {created_themes_count}/{len(themes_by_teacher_stream)}")
            
            # Формуємо результат
            result_message = f'Імпорт завершено. Успішно: {success_count}, Помилок: {error_count}'
            if errors:
                result_message += f'\nПомилки:\n' + '\n'.join(errors)
        
            
            return JsonResponse({
                'success': True,
                'message': result_message,
                'success_count': success_count,
                'error_count': error_count
            })
            
        except Exception as e:
            logger.error(f'Помилка імпорту Excel тем: {str(e)}')
            return JsonResponse({'error': f'Помилка обробки файлу: {str(e)}'}, status=500)
    
    return render(request, 'admin/import_themes_excel.html')


@admin.register(StudentExcelMapping)
class StudentExcelMappingAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'patronymic', 'department', 'group', 'created_at')
    list_filter = ('department', 'group', 'created_at')
    search_fields = ('last_name', 'first_name', 'patronymic', 'group')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('last_name', 'first_name')
    actions = ['import_students_from_excel']

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_url'] = reverse('import_students_excel')
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description='Імпорт студентів з Excel файлу')
    def import_students_from_excel(self, request, queryset):
        """
        Admin action для імпорту студентів з Excel файлу.
        Перенаправляє на форму завантаження файлу.
        """
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(reverse('import_students_excel'))


@admin.register(StudentRequestMapping)
class StudentRequestMappingAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'teacher_email', 'stream', 'theme', 'created_at')
    list_filter = ('stream', 'teacher_email', 'created_at')
    search_fields = ('student_name', 'teacher_email', 'theme')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('student_name', 'teacher_email')
    actions = ['import_themes_from_excel']

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_url'] = reverse('import_themes_excel')
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description='Імпорт тем викладачів з Excel файлу')
    def import_themes_from_excel(self, request, queryset):
        """
        Admin action для імпорту тем викладачів з Excel файлу.
        Перенаправляє на форму завантаження файлу.
        """
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(reverse('import_themes_excel'))
