from django import forms
from .models import Request, TeacherTheme, OnlyTeacher, Slot, RequestFile, FileComment
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
    label_suffix = ''

    departments = forms.MultipleChoiceField(
        label='Кафедра',
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-checkbox'}),
        required=False
    )
    slots = forms.IntegerField(
        label='Кількість місць',
        widget=forms.NumberInput(attrs={
            'type': 'range',
            'class': 'form-range',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Беремо кафедри з Department моделі
        from .models import Department
        departments = Department.objects.values_list('id', 'short_name', 'department_name')
        self.fields['departments'].choices = [
            (short, short or full) for dept_id, short, full in departments
        ]
        self.departments_fullnames = {
            short: full for dept_id, short, full in departments
        }
        slot_values = list(Slot.objects.values_list('quota', flat=True).distinct())
        min_slots = min(slot_values) if slot_values else 1
        max_slots = max(slot_values) if slot_values else 10
        self.fields['slots'].widget.attrs['min'] = min_slots
        self.fields['slots'].widget.attrs['max'] = max_slots
        self.fields['slots'].widget.attrs['step'] = 1
        self.fields['slots'].widget.attrs['value'] = min_slots

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
            'list': 'themes-list',
            'readonly': 'readonly',
        }),
        required=False
    )

    student_themes = forms.CharField(
        label="Введи свою тему",
        max_length=100, 
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Введи',
            'maxlength': 100,
        })
    )

    motivation_text = forms.CharField(
        required=False,       # необов’язкове
        max_length=500,       # макс. 500 символів
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'placeholder': 'Опиши свою мотивацію',
            'rows': 4,
            'maxlength': 500,   # обмеження на стороні клієнта
        }),
        label=''              # якщо хочеш забрати лейбл
    )

    def __init__(self, teacher_id, user=None, *args, **kwargs):
        """
        Initializes the form. 
        Fetches themes that are not occupied for the current teacher and match student's stream.
        Sets 'teacher_themes' and 'student_themes' as optional fields.
        """
        super(RequestForm, self).__init__(*args, **kwargs)
        # Query all unoccupied themes for this teacher
        themes = TeacherTheme.objects.filter(teacher_id=teacher_id, is_occupied=False, is_deleted=False, is_active=True)
        print(f"All unoccupied themes for teacher {teacher_id}: {themes.count()}")
        
        # Filter themes by student's stream if user is provided
        if user and hasattr(user, 'academic_group') and user.academic_group:
            import re
            from .models import Stream
            
            # Extract stream code from academic group (e.g., ФЕС-22 -> ФЕС-2)
            is_master = "М" in user.academic_group.upper()
            match = re.match(r"([А-ЯІЇЄҐ]+)-(\d)", user.academic_group)
            if match:
                user_stream_code = match.group(1) + "-" + match.group(2) + ("м" if is_master else "")
                print(f"Student academic group: {user.academic_group}, extracted stream: {user_stream_code}")
                try:
                    user_stream = Stream.objects.get(stream_code__iexact=user_stream_code)
                    print(f"Found stream: {user_stream}")
                    # Filter themes that are available for this stream
                    themes_before = themes.count()
                    themes = themes.filter(streams=user_stream)
                    themes_after = themes.count()
                    print(f"Themes before stream filter: {themes_before}, after: {themes_after}")
                except Stream.DoesNotExist:
                    print(f"Stream {user_stream_code} not found")
                    # If stream not found, show no themes
                    themes = themes.none()
            else:
                print(f"Could not extract stream from academic group: {user.academic_group}")
        else:
            print(f"No user or academic group provided. User: {user}, academic_group: {getattr(user, 'academic_group', 'N/A') if user else 'N/A'}")

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
            raise forms.ValidationError('Ви повинні обрати запропоновану тему або ввести власну.')
        
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
    
    def clean_student_themes(self):
        text = self.cleaned_data.get('student_themes', '').strip()
        if text and len(text) > 100:
            raise forms.ValidationError("Тема не може бути довшою за 100 символів.")
        return text

    class Meta:
        """
        Associates this form with the `Request` model and specifies common form settings.
        """
        model = Request
        fields = ['teacher_themes', 'student_themes', 'motivation_text']
        label_suffix = ''
        # labels = {
        #     'motivation_text': '',
        # }
        # widgets = {
        #     'motivation_text': forms.Textarea(attrs={
        #         'class': 'form-textarea',
        #         'placeholder': 'Опиши свою мотивацію'
        #     })
        # }
     
        

class RequestFileForm(forms.ModelForm):
    class Meta:
        model = RequestFile
        fields = ['file', 'description']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': 'Опис файлу (необов\'язково)'
            }),
        }

class FileCommentForm(forms.ModelForm):
    class Meta:
        model = FileComment
        fields = ['text', 'attachment']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Додайте коментар...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control-file'})
        }
