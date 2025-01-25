from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('Студент', 'Студент'),
        ('Викладач', 'Викладач'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Студент')
    academic_group = models.CharField(max_length=6, blank=False, null=True)  # For students
    department = models.CharField(max_length=100, blank=False, null=True)   # For teachers
    is_active = models.BooleanField(default=False)

    username = None

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['role']  # Specify any additional fields required when creating a superuser

    def __str__(self):
        return self.email

