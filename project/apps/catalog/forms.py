from django import forms
from .models import Request, TeacherTheme, OnlyTeacher, Slot
from apps.users.models import CustomUser


class FilteringSearchingForm(forms.Form):
    """A Django Form class that provides filtering and searching functionality for teacher listings.
    
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
            
        - show_occupied (BooleanField):
            - Checkbox to toggle display of fully occupied teacher slots
            - CSS class: 'form-boolean'
            
        - searching (CharField):
            - Text input for searching teachers by name
            - Placeholder: 'Пошук викладача...'
            - CSS class: 'form-searching'
    """
    DEPARTMENT_CHOICES = [
        (department, (department[:25] + '...' if len(department) > 25 else department))
        for department in filter(None, CustomUser.objects.values_list('department', flat=True).distinct())
    ]
    ACADEMIC_LEVELS = [
        (level, level) for level in filter(None, OnlyTeacher.objects.values_list('academic_level', flat=True).distinct())
    ]
    
    slot_values = list(Slot.objects.values_list('quota', flat=True).distinct())
    min_slots = min(slot_values) if slot_values else 1
    max_slots = max(slot_values) if slot_values else 10
    
    label_suffix = ''
    
    departments = forms.MultipleChoiceField(
        label='Кафедра',
        choices=DEPARTMENT_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-checkbox'}),
        required=False
    )
    academic_levels = forms.MultipleChoiceField(
        label='Науковий ступінь',
        choices=ACADEMIC_LEVELS,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-checkbox'}),
        required=False
    )
    slots = forms.IntegerField(
        label='Кількість місць',
        widget=forms.NumberInput(attrs={
            'type': 'range',
            'class': 'form-range',
            'min': min_slots,
            'max': max_slots,
            'step': 1,
            'value': min_slots
        }),
        required=False
    )
    show_occupied = forms.BooleanField(
        label='',
        widget=forms.CheckboxInput(attrs={'class': 'form-boolean'}),
        required=False
    )
    searching = forms.CharField(
        label='',
        widget=forms.TextInput(attrs={'class': 'form-searching', 'placeholder': 'Пошук викладача...'}),
        required=False
    )
    

class RequestForm(forms.ModelForm):
    """
    A form for creating or editing `Request` objects. 
    Allows the user to pick from suggested themes or enter their own.
    """

    teacher_themes = forms.CharField(
        label="Обери запропоновану тему",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Обери',
            'list': 'themes-list'
        }),
        required=False
    )

    student_themes = forms.CharField(
        label="Введи свою тему",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Введи'
        }),
        required=False
    )

    def __init__(self, teacher_id, *args, **kwargs):
        """
        Initializes the form. 
        Fetches themes that are not occupied for the current teacher.
        Sets 'teacher_themes' and 'student_themes' as optional fields.
        """
        super(RequestForm, self).__init__(*args, **kwargs)
        # Query all unoccupied themes for this teacher
        themes = TeacherTheme.objects.filter(teacher_id=teacher_id, is_occupied=False)
        self.themes_list = [(theme.theme, theme.theme) for theme in themes]
        
        # Mark these fields as optional
        self.fields['teacher_themes'].required = False
        self.fields['student_themes'].required = False
        
        # Disable student themes input if limit reached
        if self.get_student_themes_count() >= 3:
            self.fields['student_themes'].widget.attrs['disabled'] = 'disabled'
    
    def get_student_themes_count(self):
        """
        Returns the number of student themes submitted via POST data.
        """
        if self.data:
            themes = self.data.getlist('student_themes')
            return len([t for t in themes if t.strip()])
        return 0

    def clean(self):
        """
        Validates `teacher_themes` and `student_themes`.
        Ensures at least one theme is chosen, and not more than three custom themes.
        """
        cleaned_data = super().clean()
        teacher_theme = cleaned_data.get('teacher_themes')
        student_themes = self.data.getlist('student_themes')
        
        # Filter out empty themes
        student_themes = [theme.strip() for theme in student_themes if theme.strip()]
        
        # Check if either teacher theme or student theme is provided
        if not teacher_theme and not student_themes:
            raise forms.ValidationError('Ви повинні вибрати запропоновану тему або ввести власну.')
        
        # Limit the number of student themes to three
        if len(student_themes) > 3:
            raise forms.ValidationError('Ви можете ввести не більше трьох тем.')
        
        # Save cleaned student themes
        cleaned_data['student_themes'] = student_themes
        return cleaned_data

    def clean_motivation_text(self):
        """
        Validates the `motivation_text`, ensuring it stays within the length limit.
        """
        text = self.cleaned_data.get('motivation_text', '')
        if text and len(text) > 2000:
            raise forms.ValidationError("Мотиваційний текст занадто довгий.")
        return text

    class Meta:
        """
        Associates this form with the `Request` model and specifies common form settings.
        """
        model = Request
        fields = ['teacher_themes', 'student_themes', 'motivation_text']
        label_suffix = ''
        labels = {
            'motivation_text': '',
        }
        widgets = {
            'motivation_text': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Опиши свою мотивацію'
            })
        }
     
        
