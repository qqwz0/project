from django.db import models
from django.urls import reverse  
from django.db.models import F
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from apps.users.models import CustomUser
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)
        
class OnlyTeacher(models.Model):
    ACADEMIC_LEVELS = [
        ('Асистент', 'Асистент'),
        ('Доцент', 'Доцент'),
        ('Професор', 'Професор'),
    ]

    teacher_id = models.OneToOneField('users.CustomUser', 
                                    on_delete=models.CASCADE, 
                                    primary_key=True, 
                                    limit_choices_to={'role': 'teacher'}, 
                                    related_name='catalog_teacher_profile')
    academic_level = models.CharField(
        max_length=50,
        choices=ACADEMIC_LEVELS,
        default='Асистент'
    )
    additional_email = models.EmailField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"{self.teacher_id.first_name} {self.teacher_id.last_name}"

class Stream(models.Model):
    specialty_name = models.CharField(max_length=100)
    stream_code = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.stream_code
    
class Slot(models.Model):
    teacher_id = models.ForeignKey(OnlyTeacher, on_delete=models.CASCADE)
    stream_id = models.ForeignKey(Stream, on_delete=models.CASCADE)
    quota = models.IntegerField(validators=[MinValueValidator(0)])
    occupied = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    def get_available_slots(self):
        return self.quota - self.occupied
    
    @classmethod
    def filter_by_available_slots(cls):
        return cls.objects.filter(occupied__lt=F('quota'))
    
    def update_occupied_slots(self, increment):
        """
        Increment or decrement occupied slots but ensure it never exceeds quota.
        """
        logger.info(f"Before update: occupied = {self.occupied}, increment = {increment}")

        if increment > 0 and self.occupied + increment > self.quota:
            raise ValidationError("The number of occupied slots cannot exceed the quota.")

        self.occupied += increment
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
    STATUS = [
        ('Очікує', 'Очікує'),
        ('Активний', 'Активний'),
        ('Відхилено', 'Відхилено'),
        ('Завершено', 'Завершено'),
    ]
    student_id = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, 
                                 limit_choices_to={'role': 'student'}, 
                                 related_name='users_student_requests')
    teacher_id = models.ForeignKey(OnlyTeacher, on_delete=models.CASCADE)
    slot = models.ForeignKey(Slot, on_delete=models.CASCADE, null=True, blank=True)
    teacher_theme = models.ForeignKey('TeacherTheme', on_delete=models.CASCADE, 
                                    null=True, blank=True)
    student_themes = models.ManyToManyField('StudentTheme', blank=True)
    motivation_text = models.TextField()
    request_date = models.DateTimeField(auto_now_add=True)
    request_status = models.CharField(max_length=100, choices=STATUS, 
                                    default='Очікує')
    grade = models.IntegerField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True, null=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    academic_year = models.CharField(max_length=7, blank=True)  # Format: "2024/25"
    
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
        Extracts the stream code from the student's academic group.
        Example: ФЕС-23 → ФЕС-2
        """
        if self.student_id.academic_group:
            return self.student_id.academic_group[:-1]  # Remove the last digit
        return None

    def save(self, *args, **kwargs):
        """
        Assigns the correct Slot before saving.
        """
        if not self.slot:  # Only assign slot if not manually set
            student_stream_code = self.extract_stream_from_academic_group()
            print(f"Extracted stream code: {student_stream_code}")
            if not student_stream_code:
                raise ValidationError("Student academic group is missing or invalid.")

            # Find the corresponding Stream object
            try:
                stream = Stream.objects.get(stream_code=student_stream_code)
                print(f"Found stream: {stream}")
            except Stream.DoesNotExist:
                raise ValidationError(f"No stream found with code: {student_stream_code}")

            # Find an available slot for this teacher in this stream
            available_slot = Slot.objects.filter(
                teacher_id=self.teacher_id,
                stream_id=stream
            ).filter(occupied__lt=models.F('quota')).first()
            
            print(f"Available slot found: {available_slot}")

            if not available_slot:
                raise ValidationError(f"Немає вільних місць у викладача {self.teacher_id} для потоку {stream.stream_code}")

            # Assign the found slot
            self.slot = available_slot

        # Handle slot availability when request status changes
        if self.pk:  # Check if the request already exists
            old_request = Request.objects.get(pk=self.pk)
            if old_request.request_status != self.request_status:
                if self.request_status == 'Активний':
                    self.slot.update_occupied_slots(+1)
                elif old_request.request_status == 'Активний' and self.request_status != 'Активний':
                    self.slot.update_occupied_slots(-1)

        if not self.academic_year:
            current_year = timezone.now().year
            month = timezone.now().month
            if month >= 9:  # Якщо після вересня
                self.academic_year = f"{current_year}/{str(current_year + 1)[-2:]}"
            else:
                self.academic_year = f"{current_year - 1}/{str(current_year)[-2:]}"

        super().save(*args, **kwargs)
    
    def get_themes_display(self):
        """
        Returns a readable string of the selected themes.
        """
        student_themes_list = ", ".join([theme.theme for theme in self.student_themes.all()])
        teacher_theme_name = self.teacher_theme.theme if self.teacher_theme else "No teacher theme"
        return teacher_theme_name, student_themes_list

    def __str__(self):
        return self.student_id.first_name + ' ' + self.student_id.last_name + ' - ' + self.teacher_id.teacher_id.first_name + ' ' + self.teacher_id.teacher_id.last_name

class TeacherTheme(models.Model):
    teacher_id = models.ForeignKey(OnlyTeacher, on_delete=models.CASCADE)
    theme = models.CharField(max_length=100)
    theme_description = models.TextField()
    is_occupied = models.BooleanField(default=False)
    
    def __str__(self):
        return self.theme

class StudentTheme(models.Model):
    student_id = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, limit_choices_to={'role': 'student'}, related_name='users_student_themes')
    theme = models.CharField(max_length=100)
    
    def __str__(self):
        return self.theme 

class OnlyStudent(models.Model):
    student_id = models.OneToOneField('users.CustomUser', 
                                    on_delete=models.CASCADE, 
                                    primary_key=True,
                                    limit_choices_to={'role': 'student'},
                                    related_name='catalog_student_profile')
    speciality = models.CharField(max_length=100)
    course = models.IntegerField()
    additional_email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"Student: {self.student_id.get_full_name()}" 
