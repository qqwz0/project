from django import forms
from .models import Request, TeacherTheme, OnlyTeacher, Slot
from apps.users.models import CustomUser


DEFAULT_DEPARTMENT_CHOICES = [
    ('Кафедра математики', 'Кафедра математики'),
    ('Кафедра інформатики', 'Кафедра інформатики'),
    ('Кафедра фізики', 'Кафедра фізики')
]

DEFAULT_ACADEMIC_LEVELS = [
    ('Асистент', 'Асистент'),
    ('Доцент', 'Доцент'),
    ('Професор', 'Професор')
]

class FilteringSearchingForm(forms.Form):
    """A Django Form class that provides filtering and searching functionality for teacher listings."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Try to get dynamic values only when the form is actually initialized
        try:
            # Get department choices if the field exists
            if hasattr(CustomUser, 'department'):
                departments = CustomUser.objects.values_list('department', flat=True).distinct()
                department_choices = [
                    (department, (department[:25] + '...' if len(department) > 25 else department))
                    for department in filter(None, departments)
                ]
                if department_choices:
                    self.fields['departments'].choices = department_choices
            
            # Get academic levels
            if hasattr(OnlyTeacher, 'academic_level'):
                academic_levels = OnlyTeacher.objects.values_list('academic_level', flat=True).distinct()
                academic_level_choices = [(level, level) for level in filter(None, academic_levels)]
                if academic_level_choices:
                    self.fields['academic_levels'].choices = academic_level_choices
            
            # Get slot values
            slot_values = list(Slot.objects.values_list('quota', flat=True).distinct())
            if slot_values:
                min_slots = min(slot_values)
                max_slots = max(slot_values)
                self.fields['slots'].widget.attrs.update({
                    'min': min_slots,
                    'max': max_slots,
                    'value': min_slots
                })
        except Exception as e:
            # Use default values if database access fails
            pass
    
    label_suffix = ''
    
    departments = forms.MultipleChoiceField(
        label='Кафедра',
        choices=DEFAULT_DEPARTMENT_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-checkbox'}),
        required=False
    )
    
    academic_levels = forms.MultipleChoiceField(
        label='Науковий ступінь',
        choices=DEFAULT_ACADEMIC_LEVELS,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-checkbox'}),
        required=False
    )
    
    slots = forms.IntegerField(
        label='Кількість місць',
        widget=forms.NumberInput(attrs={
            'type': 'range',
            'class': 'form-range',
            'min': 1,
            'max': 10,
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
        
