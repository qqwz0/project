import logging
from django import forms
from django.core.exceptions import ValidationError
import re  # Regular expressions
from apps.catalog.models import (
    OnlyTeacher, 
    OnlyStudent,
    TeacherTheme
)
from .models import CustomUser

# Set up logging for debugging
logger = logging.getLogger(__name__)

class RegistrationForm(forms.Form):
    """
    RegistrationForm is a Django form for user registration with dynamic field requirements based on the user's role.
    Attributes:
        ROLE_CHOICES (list): List of tuples representing the role choices.
        DEPARTMENT_CHOICES (list): List of tuples representing the department choices.
        role (ChoiceField): Choice field for selecting the user's role with radio buttons.
        group (CharField): Char field for entering the academic group, required for students.
        department (ChoiceField): Choice field for selecting the department, required for lecturers.
    Methods:
        __init__(*args, **kwargs): Initializes the form and dynamically sets the 'required' attribute for fields based on the role.
        clean_group(): Validates the 'group' field, ensuring it is required and correctly formatted for students.
        clean_department(): Validates the 'department' field, ensuring it is required for lecturers.
    """
    ROLE_CHOICES = [
        ('Студент', 'Студент'),
        ('Викладач', 'Викладач'),
    ]

    DEPARTMENT_CHOICES = [
        ('Оптоелектроніки та інформаційних технологій', 'Оптоелектроніки та інформаційних технологій'),
        ('Радіоелектроніки і комп\'ютерних систем', 'Радіоелектроніки і комп\'ютерних систем'),
        ('Радіофізики та комп\'ютерних технологій', 'Радіофізики та комп\'ютерних технологій'),
        ('Сенсорної та напівпровідникової електроніки', 'Сенсорної та напівпровідникової електроніки'),
        ('Системного проектування', 'Системного проектування'),
        ('Фізичної та біомедичної електроніки', 'Фізичної та біомедичної електроніки'),
    ]

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'custom-radio-class'}),
        required=True,
        initial="Студент"
    )

    group = forms.CharField(
        label='Академічна група', 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Академічна група', 'class': 'form-input'})
    )

    department = forms.ChoiceField(
        label='Кафедра',
        choices=DEPARTMENT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Check if self.data is empty
        if not self.data:
            role = self.initial.get('role', 'Студент')  # Default to 'Студент' if no data
        else:
            role = self.data.get('role', 'Студент')  # Get the role from the submitted data, default to 'Студент'

        # Debugging log for the role selection
        logger.debug(f"Initializing form with role: {role}")

        # Dynamically set 'required' based on the role
        if role == 'Студент':
            self.fields['group'].required = True
            self.fields['department'].required = False
        elif role == 'Викладач':
            self.fields['department'].required = True
            self.fields['group'].required = False
        else:
            self.fields['group'].required = False
            self.fields['department'].required = False

        # Ensure that the correct 'required' attribute is reflected in the widget
        self.fields['group'].widget.attrs['required'] = self.fields['group'].required
        self.fields['department'].widget.attrs['required'] = self.fields['department'].required

    def clean_group(self):
        group = self.cleaned_data.get('group')
        role = self.cleaned_data.get('role')

        # Debugging log for group validation
        logger.debug(f"Cleaning 'group' field with value: {group} for role: {role}")

        if role == 'Студент':
            if not group:
                raise ValidationError("Це поле обов'язкове для студентів.")
            
            # Convert group to uppercase
            group = group.upper()
            self.cleaned_data['group'] = group  # Save the updated value back into cleaned_data
            
            # Regular expression to match the correct format
            pattern = r'^ФЕ[ЇСМЛ](?:-[1-4][1-9])?$|^ФЕП-[1-4][1-9](?:ВПК)?$'
            if not re.match(pattern, group):
                raise ValidationError("Академічна група повинна мати формат: ФЕЇ-14, ФЕС-21, ФЕП-23ВПК тощо.")
        
        # Debugging log after successful group validation
        logger.debug(f"Group cleaned successfully: {group}")
        
        return group
    
    def clean_department(self):
        department = self.cleaned_data.get('department')
        role = self.cleaned_data.get('role')

        # Debugging log for department validation
        logger.debug(f"Cleaning 'department' field with value: {department} for role: {role}")

        if role == 'Викладач':
            if not department:
                raise ValidationError("Це поле обов'язкове.")
        
        return department

class TeacherThemeForm(forms.ModelForm):
    theme = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': 'Введіть значення',
            'class': 'form-input'
        })
    )
    theme_description = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Опис теми',
            'class': 'form-input'
        }),
        required=False
    )

    class Meta:
        model = TeacherTheme
        fields = ['theme', 'theme_description']

class TeacherProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Ім'я",
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    last_name = forms.CharField(
        label="Прізвище",
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    patronymic = forms.CharField(
        label="По-батькові",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    department = forms.ChoiceField(
        label="Кафедра",
        choices=CustomUser.DEPARTMENT_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    class Meta:
        model = OnlyTeacher
        fields = ['academic_level', 'additional_email', 'phone_number']
        widgets = {
            'academic_level': forms.Select(attrs={'class': 'form-select'}),
            'additional_email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'пп.ivan.franko@lnu.edu.ua'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '68 450 65 46'
            })
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['department'].initial = user.department
            self.fields['patronymic'].initial = getattr(user, 'patronymic', '')

class StudentProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Ім'я")
    last_name = forms.CharField(label="Прізвище")
    patronymic = forms.CharField(label="По-батькові", required=False)
    academic_group = forms.CharField(label="Академічна група")  # Це поле тепер тільки для CustomUser

    class Meta:
        model = OnlyStudent
        fields = ['speciality', 'course', 'additional_email', 'phone_number']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['patronymic'].initial = user.patronymic
            self.fields['academic_group'].initial = user.academic_group

class ProfilePictureUploadForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['profile_picture']

class CropProfilePictureForm(forms.Form):
    x = forms.FloatField(widget=forms.HiddenInput())
    y = forms.FloatField(widget=forms.HiddenInput())
    width = forms.FloatField(widget=forms.HiddenInput())
    height = forms.FloatField(widget=forms.HiddenInput())