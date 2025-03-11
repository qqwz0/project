from django.db import models
from django.contrib.auth.models import AbstractUser
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

    DEPARTMENT_CHOICES = [
        ('Сенсорної та напівпровідникової електроніки', 'Сенсорної та напівпровідникової електроніки'),
        ('Системного проектування', 'Системного проектування'),
        ('Фізичної та біомедичної електроніки', 'Фізичної та біомедичної електроніки'),
        ('Радіофізики та комп\'ютерних технологій', 'Радіофізики та комп\'ютерних технологій'),
        ('Радіоелектронних і комп\'ютерних систем', 'Радіоелектронних і комп\'ютерних систем'),
        ('Оптоелектроніки та інформаційних технологій', 'Оптоелектроніки та інформаційних технологій'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Студент')
    academic_group = models.CharField(max_length=6, blank=False, null=True)  # For students
    department = models.CharField(max_length=100, choices=DEPARTMENT_CHOICES, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='profile_pics/default-avatar.jpg', null=True, blank=True)
    patronymic = models.CharField("По-батькові", max_length=150, blank=True, null=True)

    username = None

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Specify any additional fields required when creating a superuser

    def __str__(self):
        return self.email

@receiver(pre_save, sender=CustomUser)
def auto_delete_old_file_on_change(sender, instance, **kwargs):
    """
    Deletes the old profile picture from the filesystem when a user uploads a new one.
    Ensures that the default avatar is not deleted.
    """
    if not instance.pk:
        return  # New user, no file to delete

    try:
        old_file = CustomUser.objects.get(pk=instance.pk).profile_picture
    except CustomUser.DoesNotExist:
        return

    new_file = instance.profile_picture
    # Compare files; if they differ and the old file isn't the default avatar, delete it
    if old_file and old_file != new_file and os.path.basename(old_file.name) != 'default-avatar.jpg':
        if os.path.exists(old_file.path):
            os.remove(old_file.path)
