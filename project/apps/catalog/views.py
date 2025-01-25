from .models import Only_teacher, Request 
from django.db.models import Avg
from django.views.generic import ListView, DetailView

class TeachersListView(ListView):
    model = Only_teacher
    template_name = 'teachers_catalog.html'
    context_object_name = 'data'
    # Using `select_related` to optimize queries by fetching the related 'teacher_id' object in the same query.
    # This prevents additional queries when accessing teacher attributes like `teacher.teacher_id.first_name`, `teacher.teacher_id.email`, etc.
    def get_queryset(self):
        teachers = Only_teacher.objects.select_related('teacher_id').all()
        data = []
        for teacher in teachers:

                free_slots = slots_left(teacher.teacher_id.id)
                data.append({
                    'teacher': teacher,
                    'free_slots': free_slots,
                })
        return data        
                


def slots_left(teacher_id):
    try:
        places = Only_teacher.objects.get(teacher_id=teacher_id).slots  
        requests = Request.objects.filter(teacher_id=teacher_id, request_status='accepted').count()
        return places - requests
    except Only_teacher.DoesNotExist:
        return 0

class TeacherDetailView(DetailView):
    model = Only_teacher
    template_name = 'teacher_detail.html'
    context_object_name = 'teacher'
    # `get` is used to retrieve a single teacher by their `teacher_id`. This will return one unique object or raise an exception if no teacher is found.
    # It is more efficient when you are sure you only need one object.
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.get_object()
        context['free_slots'] = slots_left(teacher.teacher_id.id)
        return context