from django import forms
from .models import Request, TeacherTheme, OnlyTeacher, Slot
from apps.users.models import CustomUser

class FilteringForm(forms.Form):
    """        A Django Form class that provides filtering functionality for teacher listings.
    
    Technical Details:
    -----------------
    Form Fields:
        - departments (MultipleChoiceField): 
            - Dynamically populated from CustomUser.department
            - Uses CheckboxSelectMultiple widget
            - Allows multiple selections
            - CSS class: 'form-checkbox'
        
        - positions (MultipleChoiceField):
            - Dynamically populated from OnlyTeacher.position
            - Uses CheckboxSelectMultiple widget
            - Allows multiple selections
            - CSS class: 'form-checkbox'
        
        - slots (IntegerField):
            - Range input slider
            - Min/Max values from Slot.quota
            - Step size: 1
            - Default value: 1
            - CSS class: 'form-range'
    """
    DEPARTMENT_CHOICES = [
        (department, department) for department in CustomUser.objects.values_list('department', flat=True).distinct()
    ]
    POSITION_CHOICES = [
        (position, position) for position in OnlyTeacher.objects.values_list('position', flat=True).distinct()
    ]
    MIN_MAX_SLOTS = [
        (slots, slots) for slots in Slot.objects.values_list('quota', flat=True).distinct()
    ]
    
    departments = forms.MultipleChoiceField(
        label='Кафедри',
        choices=DEPARTMENT_CHOICES,
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'form-checkbox'}
        ),
        required=False
    )
    positions = forms.MultipleChoiceField(
        label='Посади',
        choices=POSITION_CHOICES,
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'form-checkbox'}
        ),
        required=False
    )
    slots = forms.IntegerField(
        label='Кількість місць',
        widget=forms.NumberInput(attrs={
            'type': 'range',
            'class': 'form-range',
            'min': MIN_MAX_SLOTS[0][0],
            'max': MIN_MAX_SLOTS[-1][0],
            'step': 1,
            'value': 1
        }),
        required=False
    )
     

class RequestForm(forms.ModelForm):
    """
    A form for creating or editing `Request` objects. 
    Allows the user to pick from suggested themes or enter their own.
    """

    # Proposed theme provided by the teacher.
    teacher_themes = forms.CharField(
        label="Обери запропоновану тему",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Обери',
            'list': 'themes-list',
            'readonly': 'readonly'
        }),
        required=False
    )

    # Custom theme entered by the student.
    student_themes = forms.CharField(
        label="Введи свою тему",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Введи',
        }),
        required=False
    )

    def __init__(self, teacher_id, *args, **kwargs):
        """
        Initializes the form. 
        Fetches themes that are not occupied for the current teacher.
        Sets 'proposed_themes' and 'student_themes' as optional fields.
        """
        super(RequestForm, self).__init__(*args, **kwargs)
        # Query all unoccupied themes for this teacher.
        themes = TeacherTheme.objects.filter(teacher_id=teacher_id, is_occupied=False)
        self.themes_list = [(theme.id, theme.theme) for theme in themes]

        # Mark these fields as optional, overriding global settings if necessary.
        self.fields['teacher_themes'].required = False
        self.fields['student_themes'].required = False
        
        if self.get_student_themes_count() >= 3:
            self.fields['student_themes'].widget.attrs['disabled'] = 'disabled'
    
    def get_student_themes_count(self):
        """
        Returns the number of student themes submitted via POST data.
        """
        return len(self.data.getlist('student_themes'))    

    def clean(self):
        """
        Validates `proposed_themes` and `student_themes`.
        Ensures at least one theme is chosen, and not more than three custom themes.
        """
        cleaned_data = super().clean()
        teacher_theme = cleaned_data.get('teacher_themes')
        student_themes = self.data.getlist('student_themes')

        # Check if either teacher theme or student theme is provided
        if not teacher_theme and not any(theme.strip() for theme in student_themes):
            raise forms.ValidationError('Ви повинні вибрати запропоновану тему або ввести власну.')
        
        # Limit the number of student themes to three.
        if self.get_student_themes_count() > 3:
            raise forms.ValidationError('Ви можете ввести не більше трьох тем.')
        

        # Clean up the student themes list to remove empty strings.
        cleaned_data['student_themes'] = [theme for theme in student_themes if theme.strip()]
        return cleaned_data

    def clean_motivation_text(self):
        """
        Validates the `motivation_text`, ensuring it stays within the length limit.
        """
        text = self.cleaned_data.get('motivation_text')
        # Check that the length does not exceed 2000 characters.
        if text and len(text) > 2000:
            raise forms.ValidationError("Мотиваційний текст занадто довгий.")
        return text

    class Meta:
        """
        Associates this form with the `Request` model and specifies common form settings.
        """
        model = Request
        fields = ['teacher_themes', 'student_themes', 'motivation_text', 'teacher_theme']
        label_suffix = ''
        labels = {
            'motivation_text': '',
        }
        widgets = {
            'motivation_text': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Опиши свою мотивацію'
            }),
            'teacher_theme': forms.HiddenInput(),
        }
     
        
