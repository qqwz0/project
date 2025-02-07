from django import forms
from .models import Request, TeacherTheme

class RequestForm(forms.ModelForm):
    """
    A form for creating or editing `Request` objects. 
    Allows the user to pick from suggested themes or enter their own.
    """

    # Proposed theme provided by the teacher.
    proposed_themes = forms.CharField(
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
        themes = TeacherTheme.objects.filter(teacher_id=teacher_id, is_ocupied=False)
        self.themes_list = [(theme.id, theme.theme) for theme in themes]

        # Mark these fields as optional, overriding global settings if necessary.
        self.fields['proposed_themes'].required = False
        self.fields['student_themes'].required = False
    
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
        proposed_theme = cleaned_data.get('proposed_themes')
        student_themes = self.data.getlist('student_themes')

        # Require the user to pick or enter a theme.
        if not proposed_theme and not any(student_themes):
            raise forms.ValidationError('Ви повинні вибрати запропоновану тему або ввести власну.')
        
        # Limit the number of student themes to three.
        if self.get_student_themes_count() > 4:
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
        fields = ['proposed_themes', 'student_themes', 'motivation_text', 'proposed_theme_id']
        label_suffix = ''
        labels = {
            'motivation_text': '',
        }
        widgets = {
            'motivation_text': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Опиши свою мотивацію'
            }),
            'proposed_theme_id': forms.HiddenInput(),
        }
     
        
