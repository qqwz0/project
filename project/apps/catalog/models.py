from django.db import models
from django.urls import reverse  
from django.db.models import F
        
class OnlyTeacher(models.Model):
    teacher_id = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE, primary_key=True, limit_choices_to={'role': 'teacher'})
    photo = models.ImageField(upload_to='teacher_photos/', blank=True, null=True)
    position = models.CharField(max_length=100)

    def get_absolute_url(self):
        return reverse("teacher_detail", kwargs={"pk": self.pk})
    
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
    student_id = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    teacher_id = models.ForeignKey(OnlyTeacher, on_delete=models.CASCADE)
    request_text = models.TextField()
    request_date = models.DateField(auto_now_add=True)
    request_status = models.CharField(max_length=100, choices=STATUS)
    theme = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return self.student_id.first_name + ' ' + self.student_id.last_name + ' - ' + self.teacher_id.teacher_id.first_name + ' ' + self.teacher_id.teacher_id.last_name