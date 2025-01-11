from django import forms
from .models import CustomUser
from django.core.exceptions import ValidationError
import re  # Regular expressions

class RegistrationForm(forms.Form):
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
        widget=forms.RadioSelect,
        required=True,
        initial="Студент"
    )

    email = forms.EmailField(
        label='Корпоративна скринька',
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Корпоративна скринька'})
    )

    password1 = forms.CharField(
        label='Пароль', 
        widget=forms.PasswordInput(attrs={'placeholder': 'Введіть пароль'}), 
        required=True
    )

    password2 = forms.CharField(
        label='Підтвердити пароль',
        widget=forms.PasswordInput(attrs={'placeholder': 'Підтвердьте пароль'}),
        required=True
    )

    group = forms.CharField(
        label='Академічна група', 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Академічна група'})
    )

    department = forms.ChoiceField(
        label='Кафедра',
        choices=DEPARTMENT_CHOICES,
        required=False,
        widget=forms.Select,
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email.endswith('@lnu.edu.ua'):
            raise ValidationError("Email повинен закінчуватися на '@lnu.edu.ua'")
        return email

    def clean_group(self):
        group = self.cleaned_data.get('group')
        role = self.cleaned_data.get('role')

        # If the role is "Студент", check if the group matches the required pattern
        if role == 'Студент':
            if not group:
                raise ValidationError("Це поле обов'язкове для студентів.")
            
            # Convert group to uppercase
            group = group.upper()
            self.cleaned_data['group'] = group  # Save the updated value back into cleaned_data
            
            # Regular expression to match the correct format
            pattern = r'^ФЕ[ЇСМЛП]-[1-4][1-9]$'
            if not re.match(pattern, group):
                raise ValidationError("Академічна група повинна мати формат: ФЕЇ-14, ФЕС-21, ФЕМ-33 тощо.")
        return group
    
    def clean_password1(self):
        password = self.cleaned_data.get('password1')

        # Check password length
        if len(password) < 8:
            raise ValidationError("Пароль має бути довжиною не менше 8 символів.")
        if len(password) > 25:
            raise ValidationError("Довжина паролю не має перевищувати 25 символів.")
        
        # Return the password as-is to retain the value
        return password

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError("Паролі не співпадають")
        
        # Return the second password as-is to retain the value
        return password2

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Паролі не співпадають")

        return cleaned_data
