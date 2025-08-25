from django.db import models
from django.urls import reverse  
from django.db.models import F
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
import logging
from django.utils import timezone
import os
import re

from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.users.models import CustomUser
from django.db import transaction

logger = logging.getLogger(__name__)
        
class OnlyTeacher(models.Model):
    teacher_id = models.OneToOneField('users.CustomUser', 
                                      on_delete=models.CASCADE, 
                                      primary_key=True, 
                                      limit_choices_to={'role': 'teacher'},
                                      related_name='catalog_teacher_profile')
    academic_level = models.CharField(max_length=50, default='Викладач')
    additional_email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_link = models.URLField(blank=True, null=True, verbose_name="Посилання на профіль",
                                  help_text="Посилання на профіль на сторінці факультету")
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name="Кафедра")
    
    def get_absolute_url(self):
        return reverse("modal", kwargs={"pk": self.pk})
    
    def __str__(self):
        return f"{self.teacher_id.first_name} {self.teacher_id.last_name}"

@receiver(post_save, sender=CustomUser)
def create_only_teacher(sender, instance, created, **kwargs):
    if instance.role == "Викладач":
        OnlyTeacher.objects.get_or_create(teacher_id=instance)

class Stream(models.Model):
    stream_code = models.CharField(max_length=100, unique=True)
    specialty = models.ForeignKey('Specialty', on_delete=models.CASCADE,
                                 related_name='streams',
                                 verbose_name="Спеціальність",
                                 null=True, blank=True)  # Тимчасово nullable для міграції
    year_of_entry = models.IntegerField(verbose_name="Рік вступу",
                                       help_text="Рік, коли потік почав навчання",
                                       default=2020)  # Тимчасовий default
    
    # Залишаємо specialty_name для зворотної сумісності під час міграції
    specialty_name = models.CharField(max_length=100, blank=True, null=True,
                                     help_text="Застаріле поле, буде видалено після міграції")
    
    def bachelors_or_masters(self):
        if self.stream_code.endswith('м'):
            return 'Магістри'
        return 'Бакалаври'
    
    def clean(self):
        """Validate stream codes with proper faculty prefix and course number"""
        super().clean()
        
        # Регулярний вираз для перевірки формату коду потоку
        # Допустимі коди: ФЕС-1, ФЕП-2, ФЕЛ-3, ФЕІ-4, ФЕМ-2, ФЕІ-2м, ФЕМ-1м
        pattern = r'^(ФЕ[СПЛІМ])-([1-4])(?:м)?$'
        
        match = re.match(pattern, self.stream_code)
        if not match:
            raise ValidationError({
                'stream_code': "Код потоку має бути у форматі 'ФЕС-1', 'ФЕП-2', 'ФЕЛ-3', 'ФЕІ-4', 'ФЕМ-2', 'ФЕІ-2м' або 'ФЕМ-1м'."
            })
        
        faculty = match.group(1)
        course_number = int(match.group(2))
        
        # Перевірка обмежень для магістерських програм
        if self.stream_code.endswith('м'):
            if faculty not in ['ФЕІ', 'ФЕМ']:
                raise ValidationError({
                    'stream_code': "Магістерські програми (з кодом, що закінчується на 'м') можуть бути лише для ФЕІ та ФЕМ."
                })
            if course_number > 2:
                raise ValidationError({
                    'stream_code': "Магістерські програми можуть бути лише для курсів 1 або 2."
                })
        else:
            if course_number > 4:
                raise ValidationError({
                    'stream_code': "Код потоку для бакалаврів не може бути більшим за 4 (наприклад, ФЕІ-4)."
                })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.stream_code} ({self.bachelors_or_masters()})"

class Slot(models.Model):
    teacher_id = models.ForeignKey(OnlyTeacher, on_delete=models.CASCADE)
    stream_id = models.ForeignKey(Stream, on_delete=models.CASCADE)
    quota = models.IntegerField(validators=[MinValueValidator(0)])
    occupied = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['teacher_id', 'stream_id'], name='unique_teacher_stream')
        ]

    def __str__(self):
        available = self.quota - self.occupied
        return f"{self.stream_id.stream_code} ({available} доступно з {self.quota})"
    
    def get_available_slots(self):
        active_requests_count = Request.objects.filter(
            slot=self,
            request_status='Активний'
        ).count()
        
        self.occupied = active_requests_count
        self.save()
        return self.quota - self.occupied
    
    @classmethod
    def filter_by_available_slots(cls):
        slots = cls.objects.all()
        for slot in slots:
            slot.get_available_slots()  
        return cls.objects.filter(occupied__lt=F('quota'))
    
    def update_occupied_slots(self, increment):
        """
        Increment or decrement occupied slots but ensure it never exceeds quota.
        """
        logger.info(f"Before update: occupied = {self.occupied}, increment = {increment}")

        if increment > 0 and self.occupied + increment > self.quota:
            raise ValidationError("The number of occupied slots cannot exceed the quota.")

        self.occupied = Request.objects.filter(
            slot=self,
            request_status='Активний'
        ).count()
        
        self.save()

        logger.info(f"After update: occupied = {self.occupied}")

    def clean(self):
        """
        Custom validation to ensure occupied slots never exceed the quota.
        """
        if self.occupied > self.quota:
            raise ValidationError("The number of occupied slots cannot exceed the quota.")

    def save(self, *args, **kwargs):
        """
        Override save method to include the validation.
        """
        self.clean()  # Call the custom clean method before saving
        super().save(*args, **kwargs)

class Request(models.Model):
    # Додаємо нові поля
    topic_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Назва теми")
    topic_description = models.TextField(blank=True, null=True, verbose_name="Опис теми")
    is_topic_locked = models.BooleanField(default=False, verbose_name="Тема затверджена і заблокована")

    # Існуючі поля залишаються без змін
    teacher_theme = models.ForeignKey(
        'TeacherTheme',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requests',
        verbose_name="Тема викладача",
    )
    approved_student_theme = models.ForeignKey(
        'StudentTheme',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_requests',
        verbose_name="Затверджена тема студента",
    )
    custom_student_theme = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Довільна тема студента"
    )

    STATUS = [
        ('Очікує', 'Очікує'),
        ('Активний', 'Активний'),
        ('Відхилено', 'Відхилено'),
        ('Завершено', 'Завершено'),
    ]
    student_id = models.ForeignKey('users.CustomUser', 
                                   on_delete=models.SET_NULL, 
                                   null=True,
                                   limit_choices_to={'role': 'Студент'}, 
                                   unique=False,
                                   related_name='users_student_requests')
    teacher_id = models.ForeignKey(OnlyTeacher, on_delete=models.SET_NULL, null=True)
    slot = models.ForeignKey(Slot, on_delete=models.CASCADE, null=True, blank=True)
    motivation_text = models.TextField(
        blank=True,
        max_length=500,
    )
    request_date = models.DateTimeField(default=timezone.now)
    request_status = models.CharField(max_length=100, choices=STATUS, 
                                    default='Очікує')
    grade = models.IntegerField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True, null=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    academic_year = models.CharField(max_length=7, blank=True)  # Format: "2024/25"
    comment = models.TextField(blank=True, null=True, max_length=1000)
    send_contacts = models.BooleanField(default=False)
    work_type = models.CharField(max_length=50, choices=[
        ('Курсова', 'Курсова'),
        ('Дипломна', 'Дипломна'),
        ('Магістерська', 'Магістерська'),
    ], default='Курсова', help_text='Тип роботи, яку студент планує виконувати', blank=False)

    @property
    def is_active(self):
        """Перевіряє чи запит є активним (за останні 6 місяців)"""
        six_months_ago = timezone.now() - timezone.timedelta(days=180)
        return self.request_date >= six_months_ago

    @property
    def is_archived(self):
        """Перевіряє чи робота в архіві (завершена)"""
        return self.request_status == 'Завершено' and self.grade is not None

    def extract_stream_from_academic_group(self):
        """
        Extracts the stream code from the student's academic group using a regular expression.
        Example: 'ФЕС-23' -> 'ФЕС-2', 'ФЕІ-21м' -> 'ФЕІ-2'.
        """
        if not self.student_id or not self.student_id.academic_group:
            return None
        
        # Цей вираз знаходить префікс (напр. ФЕІ) та першу цифру курсу (напр. 2)
        match = re.match(r'([А-ЯІЇЄҐ]+)-(\d)', self.student_id.academic_group)
        if match:
            # Складаємо їх у код потоку (напр. ФЕІ-2)
            return f"{match.group(1)}-{match.group(2)}"
        
        return None
    
    def save(self, *args, **kwargs):
        # Перевіряємо чи змінюється статус і чи потрібно заблокувати тему
        if self.request_status in ['Активний', 'Завершено'] and not self.is_topic_locked:
            self.is_topic_locked = True
            
            # Зберігаємо тему в текстове поле при затвердженні
            if self.teacher_theme:
                self.topic_name = self.teacher_theme.theme
                self.topic_description = self.teacher_theme.theme_description
            elif self.approved_student_theme:
                self.topic_name = self.approved_student_theme.theme
            elif self.custom_student_theme:
                self.topic_name = self.custom_student_theme

        # Захист від зміни заблокованої теми - перевіряємо ТІЛЬКИ якщо тема вже заблокована
        if self.is_topic_locked and self.pk:  # Перевіряємо тільки для існуючих об'єктів
            try:
                original = Request.objects.get(pk=self.pk)
                if original.is_topic_locked and original.topic_name != self.topic_name:  # Додаємо перевірку is_topic_locked
                    raise ValidationError("Неможливо змінити затверджену тему")
            except Request.DoesNotExist:
                pass

        # Існуюча логіка для слотів
        if not self.slot:
            student_stream_code = self.extract_stream_from_academic_group()
            if not student_stream_code:
                raise ValidationError("Student academic group is missing or invalid.")

            try:
                stream = Stream.objects.get(stream_code=student_stream_code)
            except Stream.DoesNotExist:
                raise ValidationError(f"No stream found with code: {student_stream_code}")

            available_slot = Slot.objects.filter(
                teacher_id=self.teacher_id,
                stream_id=stream
            ).filter(occupied__lt=models.F('quota')).first()

            if not available_slot:
                raise ValidationError(f"Немає вільних місць у викладача {self.teacher_id} для потоку {stream.stream_code}")

            self.slot = available_slot

        # Встановлення навчального року
        if not self.academic_year:
            current_year = timezone.now().year
            month = timezone.now().month
            if month >= 9:
                self.academic_year = f"{current_year}/{str(current_year + 1)[-2:]}"
            else:
                self.academic_year = f"{current_year - 1}/{str(current_year)[-2:]}"

        # Обробка зміни статусу для слотів (переносимо після встановлення academic_year)
        status_changed = False
        if self.pk:
            try:
                old_request = Request.objects.get(pk=self.pk)
                if old_request.request_status != self.request_status:
                    status_changed = True
            except Request.DoesNotExist:
                pass

        # Завжди викликаємо super().save() в кінці
        super().save(*args, **kwargs)
        
        # Після збереження обробляємо зміни статусу
        if status_changed:
            if self.request_status == 'Активний':
                self.slot.update_occupied_slots(+1)
            elif old_request.request_status == 'Активний' and self.request_status != 'Активний':
                self.slot.update_occupied_slots(-1)
                
            # Free teacher theme when request is completed
            if self.request_status == 'Завершено' and self.teacher_theme:
                self.teacher_theme.is_occupied = False
                self.teacher_theme.save()
    
    def get_themes_display(self):
        """
        Returns a readable string of the selected themes.
        """
        student_themes_list = ", ".join([theme.theme for theme in self.student_themes.all()])
        teacher_theme_name = self.teacher_theme.theme if self.teacher_theme else "No teacher theme"
        return teacher_theme_name, student_themes_list
    
    def get_theme_display(self):
        # Якщо є topic_name (після підтвердження), показуємо його
        if self.topic_name:
            return self.topic_name
        
        # Інакше показуємо тему з ForeignKey
        if self.custom_student_theme:
            return f"{self.custom_student_theme} (довільна тема студента)"
        elif self.approved_student_theme:
            return f"{self.approved_student_theme.theme} (запропоновано студентом)"
        elif self.teacher_theme:
            return self.teacher_theme.theme
        
        return "Тема не вказана"
    
    @property
    def theme_display(self):
        return self.get_theme_display()

    def __str__(self):
        student_name = f"{self.student_id.first_name} {self.student_id.last_name}" if self.student_id else "Видалений студент"
        teacher_name = f"{self.teacher_id.teacher_id.first_name} {self.teacher_id.teacher_id.last_name}" if self.teacher_id and self.teacher_id.teacher_id else "Видалений викладач"
        return f"{student_name} - {teacher_name}"    
    
class TeacherTheme(models.Model):
    teacher_id = models.ForeignKey(OnlyTeacher, on_delete=models.SET_NULL, null=True, related_name='themes')
    theme = models.CharField(max_length=100)
    theme_description = models.TextField(blank=True, null=True)
    is_occupied = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False, help_text='Позначає, чи тема була видалена (неактивна)')
    streams = models.ManyToManyField(Stream, blank=True, related_name='teacher_themes')
    
    def __str__(self):
        status = "🟢" if self.is_active else "🔴"
        return f"{status} {self.theme}"
    
    def can_be_deleted(self):
        """Перевіряє чи можна фізично видалити тему"""
        # Перевіряємо чи тема використовується тільки в завершених запитах
        active_requests = Request.objects.filter(
            teacher_theme=self,
            request_status__in=['Очікує', 'Активний']
        ).exists()
        
        # Можна видалити якщо немає активних запитів
        return not active_requests
    
    def force_delete(self):
        """Фізично видаляє тему незалежно від статусу"""
        super().delete()

    def delete(self, force=False, *args, **kwargs):
        """
        Видаляє тему з перевіркою можливості видалення
        Args:
            force (bool): Якщо True, видаляє тему незалежно від статусу
        """
        if force or self.can_be_deleted():
            return super().delete(*args, **kwargs)
        self.soft_delete()
        return False

    def soft_delete(self):
        """Логічне видалення теми"""
        self.is_deleted = True
        self.is_active = False
        self.save()

    def activate(self):
        """Активація теми"""
        self.is_active = True
        self.is_deleted = False
        self.save()

    def deactivate(self):
        """Деактивація теми"""
        print(f"Before deactivate: is_active={self.is_active}, is_deleted={self.is_deleted}")
        self.is_active = False
        self.is_deleted = False
        print(f"After setting values: is_active={self.is_active}, is_deleted={self.is_deleted}")
        self.save()
        self.refresh_from_db()  # Перечитуємо з бази
        print(f"After save: is_active={self.is_active}, is_deleted={self.is_deleted}")
    
    def get_active_requests_count(self):
        """Повертає кількість активних запитів для цієї теми"""
        return Request.objects.filter(
            teacher_theme=self,
            request_status__in=['Очікує', 'Активний']
        ).count()
    
    def get_streams_display(self):
        """Повертає список потоків у вигляді рядка"""
        streams = self.streams.all()
        if streams:
            return ', '.join([stream.stream_code for stream in streams])
        return 'Без потоку'
    
    @classmethod
    def get_active_themes(cls):
        """Повертає лише активні теми"""
        return cls.objects.filter(is_active=True)
    
    class Meta:
        ordering = ['teacher_id__teacher_id__last_name', 'theme']

class StudentTheme(models.Model):
    student_id = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, limit_choices_to={'role': 'student'}, related_name='users_student_themes')
    request = models.ForeignKey('Request', on_delete=models.CASCADE, related_name='student_themes')
    theme = models.CharField(max_length=100)
    
    def __str__(self):
        return self.theme 

 

class OnlyStudent(models.Model):
    """
    Нова модель студента з нормалізованою структурою
    Студент належить до групи, а група - до потоку
    """
    student_id = models.OneToOneField('users.CustomUser', 
                                    on_delete=models.CASCADE, 
                                    primary_key=True,
                                    limit_choices_to={'role': 'student'},
                                    related_name='catalog_student_profile_new')
    group = models.ForeignKey('Group', on_delete=models.CASCADE,
                             related_name='students',
                             verbose_name="Група")
    additional_email = models.EmailField(blank=True, null=True, verbose_name="Додатковий email")
    phone_number = models.CharField(max_length=15, blank=True, null=True, verbose_name="Телефон")
    
    class Meta:
        verbose_name = "Студент"
        verbose_name_plural = "Студенти"
    
    @property
    def specialty(self):
        """Повертає спеціальність через групу -> потік -> спеціальність"""
        return self.group.stream.specialty
    
    @property
    def faculty(self):
        """Повертає факультет через групу -> потік -> спеціальність -> факультет"""
        return self.group.stream.specialty.faculty
    
    @property
    def education_level(self):
        """Повертає рівень освіти зі спеціальності"""
        return self.group.stream.specialty.education_level
    
    @property
    def course(self):
        """Вираховує курс на основі року вступу потоку"""
        from datetime import datetime
        current_year = datetime.now().year
        return current_year - self.group.stream.year_of_entry + 1
    
    def __str__(self):
        return f"Student: {self.student_id.get_full_name()} ({self.group.group_code})"

# Нові моделі для нормалізації структури
class Faculty(models.Model):
    """
    Факультети - найвищий рівень в ієрархії
    """
    name = models.CharField(max_length=150, unique=True, verbose_name="Назва факультету")
    short_name = models.CharField(max_length=50, unique=True, verbose_name="Коротка назва англійською",
                                 help_text="Наприклад: electronics, philosophy, mechanics")
    
    class Meta:
        verbose_name = "Факультет"
        verbose_name_plural = "Факультети"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Specialty(models.Model):
    """
    Спеціальності - належать факультету
    """
    EDUCATION_LEVELS = [
        ('bachelor', 'Бакалавр'),
        ('master', 'Магістр'),
        ('phd', 'Доктор філософії'),
    ]
    
    name = models.CharField(max_length=150, verbose_name="Назва спеціальності")
    code = models.CharField(max_length=20, verbose_name="Код спеціальності",
                           help_text="Наприклад: 121, 122, 123")
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, 
                               related_name='specialties',
                               verbose_name="Факультет")
    education_level = models.CharField(max_length=50, choices=EDUCATION_LEVELS,
                                     verbose_name="Рівень освіти")
    
    class Meta:
        verbose_name = "Спеціальність"
        verbose_name_plural = "Спеціальності"
        unique_together = ['code', 'faculty', 'education_level']
        ordering = ['faculty', 'name']
    
    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_education_level_display()})"

class Group(models.Model):
    """
    Групи - належать потоку
    """
    group_code = models.CharField(max_length=50, unique=True, 
                                 verbose_name="Код групи",
                                 help_text="Наприклад: ІМ-21, ПМ-31")
    stream = models.ForeignKey('Stream', on_delete=models.CASCADE,
                              related_name='groups',
                              verbose_name="Потік")
    
    class Meta:
        verbose_name = "Група"
        verbose_name_plural = "Групи"
        ordering = ['group_code']

    def __str__(self):
        return self.group_code
    
class Department(models.Model):
    """
    Кафедри - належать факультету
    """
    department_name = models.CharField(max_length=200, unique=True, 
                                 verbose_name="Назва кафедри",
                                 help_text="Наприклад: Кафедра комп'ютерних наук")
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, 
                               related_name='departments',
                               verbose_name="Факультет")
    
    
    class Meta:
        verbose_name = "Кафедра"
        verbose_name_plural = "Кафедри"
        ordering = ['department_name']

    def __str__(self):
        return self.department_name

class RequestFile(models.Model):
    """
    Model for storing files attached to requests.
    """
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='request_files/%Y/%m/%d/')
    uploaded_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    version = models.IntegerField(default=1)  
    description = models.TextField(blank=True)  
    is_archived = models.BooleanField(default=False, verbose_name="Збережено в архіві")

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"File for request {self.request.id} (v{self.version})"

    def get_filename(self):
        return os.path.basename(self.file.name)




class FileComment(models.Model):
    """
    Model for storing comments on request files.
    """
    file = models.ForeignKey(RequestFile, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    attachment = models.FileField(upload_to='comment_attachments/%Y/%m/%d/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author.get_full_name()} on {self.file}"
        
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            print(f"[DEBUG] Creating new FileComment: {self.text[:50]}...")
        super().save(*args, **kwargs)
        if is_new:
            print(f"[DEBUG] FileComment created with ID: {self.pk}")

    def get_attachment_filename(self):
        """Повертає ім'я прикріпленого файлу без шляху"""
        if self.attachment:
            return self.attachment.name.split('/')[-1]
        return None
