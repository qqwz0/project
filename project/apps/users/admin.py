from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.db.models import F, Q
from django.http import FileResponse, HttpResponse
from django.urls import reverse
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

from docxtpl import DocxTemplate

from .models import CustomUser
from apps.catalog.models import (
    Stream,
    Slot,
    OnlyTeacher,
    TeacherTheme,
    OnlyStudent,
    Request,
    StudentTheme,
)
from .export_service import export_requests_to_word

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
            department = self.current_user.department
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
            return qs.filter(department=request.user.department)
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
        depts = OnlyTeacher.objects.values_list('teacher_id__department', flat=True).distinct()
        return [(dept, dept) for dept in depts if dept]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(teacher_id__teacher_id__department=self.value())
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
            qs = qs.filter(teacher_id__teacher_id__department=request.user.department)
        return qs

    @admin.display(description='Викладач', ordering='teacher_id__teacher_id__last_name')
    def get_teacher_name(self, obj):
        u = obj.teacher_id.teacher_id
        parts = [u.last_name, u.first_name]
        if u.patronymic:
            parts.append(u.patronymic)
        return " ".join(parts)

    @admin.display(description='Кафедра', ordering='teacher_id__teacher_id__department')
    def get_department(self, obj):
        return obj.teacher_id.teacher_id.department

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
                teacher_id__department=request.user.department
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            return ['occupied']
        return []

class TeacherThemeForm(forms.ModelForm):
    class Meta:
        model = TeacherTheme
        fields = ['teacher_id', 'theme', 'theme_description', 'is_occupied']
        labels = {
            'teacher_id': 'Викладач',
            'theme': 'Тема',
            'theme_description': 'Опис',
            'is_occupied': 'Зайнята',
        }
        help_texts = {
            'theme': 'Формулювання теми, доступне для вибору студентом',
            'theme_description': 'Додаткові деталі або специфікація теми (необовʼязково)',
        }

class TeacherThemeAdmin(admin.ModelAdmin):
    form = TeacherThemeForm

    list_display = ('get_teacher_full_name', 'get_teacher_theme', 'is_occupied')
    readonly_fields = ('is_occupied',)

    search_fields = (
        'teacher_id__teacher_id__last_name',
        'teacher_id__teacher_id__first_name',
        'teacher_id__teacher_id__patronymic',
    )

    list_filter = ('is_occupied', 'teacher_id__teacher_id__department')
    ordering = ('teacher_id__teacher_id__last_name', 'teacher_id__teacher_id__first_name')

    autocomplete_fields = ('teacher_id',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
            return qs.filter(teacher_id__teacher_id__department=request.user.department)
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
        ordering='theme'  # This is a direct model field, so sortable as-is
    )

    def get_teacher_theme(self, obj):
        return obj.theme

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher_id":
            if request.user.groups.filter(name='department_admin').exists() and not request.user.is_superuser:
                kwargs["queryset"] = OnlyTeacher.objects.filter(teacher_id__department=request.user.department)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# Мапа префіксів до назв спеціальностей
PREFIX_MAP = {
    'ФЕС': 'Інформаційні системи та технології',
    'ФЕП': 'Інженерія програмного забезпечення',
    'ФЕІ': 'Комп’ютерні науки',
    'ФЕМ': 'Електроніка та комп’ютерні системи',
    'ФЕЛ': 'Сенсорні та діагностичні електронні системи',
}

class StreamForm(forms.ModelForm):
    """
    Форма адмінки для Stream:
    - Поля stream_code та specialty_name відображаються
    - specialty_name не є обов'язковим на формі
    """
    # Явно визначаємо поле, щоб вимкнути required на рівні форми
    specialty_name = forms.CharField(required=False, label='Назва спеціальності(-)')

    class Meta:
        model = Stream
        fields = ('stream_code', 'specialty_name')

    def clean_specialty_name(self):
        name = self.cleaned_data.get('specialty_name')
        code = self.cleaned_data.get('stream_code', '') or ''
        # Якщо адміністратор не ввів назву, спробуємо автозаповнити
        if not name and code:
            for prefix, title in PREFIX_MAP.items():
                if code.startswith(prefix):
                    return title
        return name

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
    
class OnlyStudentForm(forms.ModelForm):
    class Meta:
        model = OnlyStudent
        fields = ['course']  # редагується тільки курс
        labels = {
            'course': 'Курс',
        }

class OnlyStudentAdmin(admin.ModelAdmin):
    form = OnlyStudentForm

    list_display = ('get_full_name', 'get_course')
    search_fields = (
        'student_id__last_name',
        'student_id__first_name',
        'student_id__patronymic',
    )


    readonly_fields = ('student_id',)
    fields = ('student_id', 'course')  # лише ці два поля видно

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    @admin.display(description='ПІБ студента')
    def get_full_name(self, obj):
        return obj.student_id.get_full_name_with_patronymic()

    @admin.display(description='Курс')
    def get_course(self, obj):
        return obj.course

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
            'request_status': 'Статус',
        }

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
        'request_status',
    ]
    extra_list_display = ['display_grade']

    list_filter = (
        'request_status',
        'slot__stream_id',                     # фільтр за потоком
        'teacher_id__teacher_id__department',  # фільтр за кафедрою
        'academic_year',                       # фільтр за академічним роком
    )

    search_fields = (
        'student_id__last_name',
        'student_id__first_name',
        'student_id__patronymic',
        'teacher_id__teacher_id__last_name',
        'teacher_id__teacher_id__first_name',
        'teacher_id__teacher_id__patronymic',
    )

    export_fields = [
        'student_id',
        'teacher_id',
        'teacher_theme',
        'approved_student_theme',
        'request_status',
        'academic_year',
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
                'request_status',
            ]
        return super().get_fields(request, obj)

    @admin.display(description='Студент — Викладач')
    def get_student_teacher(self, obj):
        student_name = obj.student_id.get_full_name_with_patronymic()
        teacher_name = obj.teacher_id.teacher_id.get_full_name_with_patronymic()
        return f"{student_name} — {teacher_name}"

    @admin.display(description='Кафедра викладача',
                   ordering='teacher_id__teacher_id__department')
    def get_teacher_department(self, obj):
        return obj.teacher_id.teacher_id.department

    @admin.display(description='Група студента',
                   ordering='student_id__academic_group')
    def get_student_group(self, obj):
        return obj.student_id.academic_group

    @admin.display(description='Тема')
    def get_theme_display(self, obj):
        # pick the text you want to show
        text = (
            obj.approved_student_theme.theme
            if obj.approved_student_theme
            else (obj.teacher_theme.theme if obj.teacher_theme else '')
        )
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

# І нарешті реєструємо модель:
admin.site.register(Stream, StreamAdmin)

admin.site.register(OnlyTeacher, OnlyTeacherAdmin)
admin.site.register(OnlyStudent, OnlyStudentAdmin)
admin.site.register(Request, RequestAdmin)

# Реєструємо модель TeacherTheme в адмінці з новою конфігурацією
admin.site.register(TeacherTheme, TeacherThemeAdmin)

# Correctly register the model with the admin site:
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Slot, SlotAdmin)