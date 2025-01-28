from .models import OnlyTeacher, Slot 
from django.views.generic import ListView
import re

class TeachersListView(ListView):
    model = OnlyTeacher
    template_name = 'teachers_catalog.html'
    context_object_name = 'data'
    # Using `select_related` to optimize queries by fetching the related 'teacher_id' object in the same query.
    # This prevents additional queries when accessing teacher attributes like `teacher.teacher_id.first_name`, `teacher.teacher_id.email`, etc.
    def get_queryset(self):
        teachers = OnlyTeacher.objects.select_related('teacher_id').all()     
        slots = Slot.filter_by_available_slots() # Get all slots with available quotas
        data = []
        
        if self.request.user.is_authenticated and self.request.user.role == 'Студент':
            user = self.request.user
            match = re.match(r'([А-ЯІЇЄҐ]+)-(\d)', user.academic_group)
            if match:
                user_stream = match.group(1) + '-' + match.group(2)
                slots = slots.filter(stream_id__stream_code__iexact=user_stream)  # Case-insensitive exact match 
        for teacher in teachers:
            free_slots = slots.filter(teacher_id=teacher)
            data.append({
                    'teacher': teacher,
                    'free_slots': free_slots,
                })
        return data    
                