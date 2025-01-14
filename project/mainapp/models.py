from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class User(models.Model):
    ROLES= [
        ('student', 'студент'),
        ('teacher', 'викладач'),
    ]
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    password = models.CharField(max_length=100)
    role = models.CharField(max_length=100, choices=ROLES)
    faculty = models.CharField(max_length=100, blank=True, null=True, )
    group = models.CharField(max_length=100, blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if self.role == 'student':
            self.faculty = None
        elif self.role == 'teacher':
            self.group = None
        super(User, self).save(*args, **kwargs)
    
     
class Only_teacher(models.Model):
    teacher_id = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, limit_choices_to={'role': 'teacher'})
    phone_num = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='teacher_photos/', blank=True, null=True)
    position = models.CharField(max_length=100)
    slots = models.IntegerField()
    sci_interests = models.TextField(blank=True)
    
    def __str__(self):
        return self.teacher_id.first_name + ' ' + self.teacher_id.last_name


class Review(models.Model):
    student_id = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    teacher_id = models.ForeignKey(Only_teacher, on_delete=models.CASCADE)
    rating = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(5)])
    rating_date = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return self.student_id.first_name + ' ' + self.student_id.last_name + ' - ' + self.teacher_id.teacher_id.first_name + ' ' + self.teacher_id.teacher_id.last_name    

    
class Request(models.Model):
    STATUS= [
        ('pending', 'очікується'),
        ('accepted', 'прийнятий'),
        ('rejected', 'відхилений'),
    ]
    student_id = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    teacher_id = models.ForeignKey(Only_teacher, on_delete=models.CASCADE)
    request_text = models.TextField()
    request_date = models.DateField(auto_now_add=True)
    request_status = models.CharField(max_length=100, choices=STATUS)
    theme = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return self.student_id.first_name + ' ' + self.student_id.last_name + ' - ' + self.teacher_id.teacher_id.first_name + ' ' + self.teacher_id.teacher_id.last_name
