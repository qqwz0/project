from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import pre_save
from django.dispatch import receiver
import os
import logging
from django.contrib.auth.base_user import BaseUserManager


logger = logging.getLogger(__name__)

class CustomUserManager(BaseUserManager):
    """
    Менеджер для CustomUser, який використовує email як унікальний ідентифікатор.
    """

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Електронна пошта є обов\'язковою для створення користувача.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Суперкористувач має мати is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Суперкористувач має мати is_superuser=True.')

        return self._create_user(email, password, **extra_fields)
        
from django.db.models.signals import pre_save
from django.dispatch import receiver
import os
import logging


logger = logging.getLogger(__name__)
        
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('Студент', 'Студент'),
        ('Викладач', 'Викладач'),
    ]


    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Студент')
    academic_group = models.CharField(max_length=9, blank=False, null=True)  # For students
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    patronymic = models.CharField("По-батькові", max_length=150, blank=True, null=True)

    username = None

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Specify any additional fields required when creating a superuser
    

    def __str__(self):
        return self.get_full_name_with_patronymic()
    
    def get_full_name_with_patronymic(self):
        parts = [self.last_name, self.first_name]
        if self.patronymic:
            parts.append(self.patronymic)
        return ' '.join(parts)
    
    def get_profile(self):
        """
        Повертає профіль користувача (OnlyTeacher або OnlyStudent), 
        залежно від ролі. Якщо профілю нема — None.
        """
        if self.role == 'Викладач':
            from apps.catalog.models import OnlyTeacher
            try:
                return self.catalog_teacher_profile  # OneToOneField
            except OnlyTeacher.DoesNotExist:
                return None

        if self.role == 'Студент':
            from apps.catalog.models import OnlyStudent
            try:
                return self.catalog_student_profile_new  # OneToOneField
            except OnlyStudent.DoesNotExist:
                return None

        return None


    def get_faculty(self):
        try:
            from apps.catalog.models import Group
            group = Group.objects.get(group_code=self.academic_group)
            return group.stream.specialty.faculty
        except Exception:
            return None  

    def get_department(self):
        """
        Повертає Department об'єкт через профіль (нова система)
        """
        profile = self.get_profile()
        if profile and hasattr(profile, 'department') and profile.department:
            return profile.department

        # Для студентів - через активний запит
        if self.role == 'Студент':
            active_request = self.users_student_requests.filter(
                request_status="Активний"
            ).select_related("teacher_id__department").first()

            if active_request and active_request.teacher_id and active_request.teacher_id.department:
                return active_request.teacher_id.department

        return None
    
    def get_department_name(self):
        """
        Повертає назву кафедри як строку (для зворотної сумісності)
        """
        department = self.get_department()
        return department.department_name if department else None


# @receiver(pre_save, sender=CustomUser)
# def auto_delete_old_file_on_change(sender, instance, **kwargs):
#     """
#     Deletes the old profile picture from the filesystem when a user uploads a new one.
#     Ensures that the default avatar is not deleted.
#     THIS IS INCOMPATIBLE WITH CLOUD STORAGE and will cause errors.
#     """
#     if not instance.pk:
#         return  # New user, no file to delete

#     try:
#         old_file = CustomUser.objects.get(pk=instance.pk).profile_picture
#     except CustomUser.DoesNotExist:
#         return

#     new_file = instance.profile_picture
#     # Compare files; if they differ and the old file isn't the default avatar, delete it
#     if old_file and old_file != new_file and os.path.basename(old_file.name) != 'default-avatar.jpg':
#         if os.path.exists(old_file.path):
#             os.remove(old_file.path)


class StudentExcelMapping(models.Model):
    """
    Мапінг студентів з Excel файлу для автоматичного призначення кафедр
    """
    last_name = models.CharField(max_length=100, verbose_name="Прізвище")
    first_name = models.CharField(max_length=100, verbose_name="Ім'я")
    patronymic = models.CharField(max_length=100, blank=True, verbose_name="По-батькові")
    department = models.CharField(max_length=200, verbose_name="Кафедра")
    group = models.CharField(max_length=50, verbose_name="Група")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Мапінг студентів Excel"
        verbose_name_plural = "Мапінги студентів Excel"
        unique_together = ['last_name', 'first_name', 'patronymic', 'group']

    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.patronymic} - {self.group}"

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name} {self.patronymic}".strip()


class StudentRequestMapping(models.Model):
    """
    Мапінг студентів з Excel файлу для автоматичного створення запитів
    """
    teacher_email = models.EmailField(verbose_name="Email викладача")
    stream = models.CharField(max_length=50, verbose_name="Потік")
    theme = models.CharField(max_length=500, verbose_name="Тема")
    theme_description = models.TextField(blank=True, verbose_name="Опис теми")
    student_name = models.CharField(max_length=200, verbose_name="Студент")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Мапінг запитів студентів"
        verbose_name_plural = "Мапінги запитів студентів"
        unique_together = ['teacher_email', 'stream', 'student_name']

    def __str__(self):
        return f"{self.student_name} - {self.theme[:50]}..."

    @property
    def teacher_name(self):
        try:
            teacher = CustomUser.objects.get(email=self.teacher_email)
            return teacher.get_full_name_with_patronymic()
        except CustomUser.DoesNotExist:
            return self.teacher_email

