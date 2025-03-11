from django.db import models
from django.contrib.auth.models import AbstractUser
from image_cropping import ImageRatioField

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

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Студент')
    academic_group = models.CharField(max_length=6, null=True)
    department = models.CharField(max_length=100, choices=DEPARTMENT_CHOICES, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    patronymic = models.CharField("По-батькові", max_length=150, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email