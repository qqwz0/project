class FilteringSearchingForm(forms.Form):
    # ... existing code ...
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        departments = CustomUser.objects.values_list('department', flat=True).distinct()
        self.fields['department'].choices = [(d, d) for d in departments if d]
    
    # ... existing code ... 