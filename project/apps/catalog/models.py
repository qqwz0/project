from django.db import models
from django.urls import reverse  
from django.db.models import F
from time import time
        
class OnlyTeacher(models.Model):
    teacher_id = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE, primary_key=True, limit_choices_to={'role': 'teacher'})
    photo = models.ImageField(upload_to='teacher_photos/', blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)

    def get_absolute_url(self):
        return reverse("detail_request_modal", kwargs={"pk": self.pk})
    
    def __str__(self):
        return self.teacher_id.first_name + ' ' + self.teacher_id.last_name

class Stream(models.Model):
    specialty_name = models.CharField(max_length=100)
    stream_code = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.stream_code
    
class Slot(models.Model):
    teacher_id = models.ForeignKey(OnlyTeacher, on_delete=models.CASCADE)
    stream_id = models.ForeignKey(Stream, on_delete=models.CASCADE)
    quota = models.IntegerField()
    occupied = models.IntegerField(default=0)
    
    def get_available_slots(self):
        return self.quota - self.occupied
    
    @classmethod
    def filter_by_available_slots(cls):
        return cls.objects.filter(occupied__lt=F('quota'))
       
class Request(models.Model):
    STATUS= [
        ('pending', 'очікується'),
        ('accepted', 'прийнятий'),
        ('rejected', 'відхилений'),
    ]
    student_id = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, limit_choices_to={'role': 'student'}, unique=False)
    teacher_id = models.ForeignKey(OnlyTeacher, on_delete=models.CASCADE)
    proposed_theme_id = models.ForeignKey('TeacherTheme', on_delete=models.CASCADE, blank=True, null=True)
    motivation_text = models.TextField()
    request_date_time = models.DateTimeField(auto_now_add=True)
    request_status = models.CharField(max_length=100, choices=STATUS)
    
    def __str__(self):
        return self.student_id.first_name + ' ' + self.student_id.last_name + ' - ' + self.teacher_id.teacher_id.first_name + ' ' + self.teacher_id.teacher_id.last_name
    
class TeacherTheme(models.Model):
    teacher_id = models.ForeignKey(OnlyTeacher, on_delete=models.CASCADE)
    theme = models.CharField(max_length=100)
    theme_description = models.TextField()
    is_ocupied = models.BooleanField(default=False)
    
    def __str__(self):
        return self.theme

class StudentTheme(models.Model):
    student_id = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    theme = models.CharField(max_length=100)
    request_id = models.ForeignKey(Request, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.theme        