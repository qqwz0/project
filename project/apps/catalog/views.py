from .utils import HtmxLoginRequiredMixin
from .models import OnlyTeacher, Slot, TeacherTheme, StudentTheme, Stream
from django.core.exceptions import ValidationError 
from django.views.generic import ListView, DetailView, FormView, TemplateView
from .forms import RequestForm, FilteringForm
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import F
from django.shortcuts import render

import re

class TeachersCatalogView(TemplateView, FormView):
    """
    Displays the teachers catalog page.
    """
    template_name = 'catalog/teachers_catalog.html'
    form_class = FilteringForm
    
    def get(self, request, *args, **kwargs):
        """
        Handles GET requests to display the teachers catalog.
        """
        form = self.form_class()
        context = {'form': form}
        return render(request, self.template_name, context)
    
class TeachersListView(ListView):
    """
    Displays a list of teachers along with their available slots.
    """
    model = OnlyTeacher
    context_object_name = 'data'
    
    def get(self, request, *args, **kwargs):
        """
        Returns a list of dictionaries that each contain:
        - Teacher instance (converted to dictionary)
        - Free slots for that teacher (converted to list of dictionaries)
        """
        teachers = OnlyTeacher.objects.select_related('teacher_id').all()
        slots = Slot.filter_by_available_slots()
        data = []
        is_matched = False

        if request.user.is_authenticated and request.user.role == 'Студент':
            user = request.user
            match = re.match(r'([А-ЯІЇЄҐ]+)-(\d)', user.academic_group)
            if match:
                user_stream = match.group(1) + '-' + match.group(2)
                slots = slots.filter(stream_id__stream_code__iexact=user_stream)
                is_matched = True

        for teacher in teachers:
            free_slots = slots.filter(teacher_id=teacher)
        
            data.append({
                'teacher': {
                    'id': teacher.pk,
                    'position': teacher.position,
                    'photo':teacher.photo.url if teacher.photo else None,
                    'teacher_id': {
                        'first_name': teacher.teacher_id.first_name,
                        'last_name': teacher.teacher_id.last_name,
                        'department': teacher.teacher_id.department,
                    }
                    
                },
                'free_slots': [
                    {
                        'stream_id': {
                            'stream_code': slot.stream_id.stream_code
                        },
                        'get_available_slots': slot.get_available_slots()
                    }
                    for slot in free_slots
                ],
                'is_matched': is_matched
            })

        return JsonResponse(data, safe=False)  

class TeacherModalView(HtmxLoginRequiredMixin, SuccessMessageMixin, DetailView, FormView):
    """
    Manages the teacher detail view, form submission, and saves student requests.
    """
    model = OnlyTeacher
    template_name = 'catalog/teacher_modal.html'
    context_object_name = 'teacher'
    form_class = RequestForm
    success_url = reverse_lazy('teachers_catalog')
    success_message = "Запит успішно відправлено. Очікуйте підтвердження від викладача."
    
    def get(self, request, *args, **kwargs):
        """
        Handles GET requests to display the teacher modal.
        """
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """
        Handles POST requests to process the form data.
        """
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)
    
    def get_success_message(self, cleaned_data):
        """
        Returns the success message defined in the class.
        """
        return super().get_success_message(cleaned_data)
    
    def get_form_kwargs(self):
        """
        Passes the teacher instance to the form via 'teacher_id'.
        """
        kwargs = super().get_form_kwargs()
        kwargs['teacher_id'] = self.get_object()
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Adds a list of free slots to the template context, filtered by user group if applicable.
        """
        context = super().get_context_data(**kwargs)
        teacher = self.get_object()
        
        # Fetch available slots for this teacher.
        slots = Slot.filter_by_available_slots().filter(teacher_id=teacher)
        is_matched = False
        
        # Filter slots by user's academic group if the user is a student.
        user = self.request.user
        match = re.match(r'([А-ЯІЇЄҐ]+)-(\d)', user.academic_group)
        if match:
            user_stream = match.group(1) + '-' + match.group(2)
            slots = slots.filter(stream_id__stream_code__iexact=user_stream)
            is_matched = True
        
        context['free_slots'] = slots
        context['is_matched'] = is_matched
        return context
    
    def form_invalid(self, form):
        """
        Handles invalid form submissions. Returns JSON for XMLHttpRequests.
        """
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)
    
    def form_valid(self, form):
        """
        Processes valid form data. Creates a request, saves themes, and returns JSON for XMLHttpRequests.
        """
        req = form.save(commit=False)
        self.assign_request_fields(form)
        req.save()

        # Save each student theme from cleaned data.
        student_themes_data = form.cleaned_data['student_themes']
        for theme in student_themes_data:
            if theme:
                student_theme = StudentTheme.objects.create(student_id=self.request.user, theme=theme)
                req.student_themes.add(student_theme)
        
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            messages.success(self.request, self.get_success_message(form.cleaned_data))
            return JsonResponse({'success': True})
        return super().form_valid(form)
        
    def assign_request_fields(self, form):
        """
        Assigns current user, teacher, and request status to the form instance.
        Updates the proposed theme to occupied if provided.
        """
        form.instance.student_id = self.request.user
        form.instance.teacher_id = self.get_object()
        form.instance.request_status = 'pending'
        
        student_stream_code = form.instance.extract_stream_from_academic_group()
        if student_stream_code:
            try:
                stream = Stream.objects.get(stream_code=student_stream_code)
                available_slot = Slot.objects.filter(
                    teacher_id=form.instance.teacher_id,
                    stream_id=stream,
                    occupied__lt=F('quota')
                ).first()
                
                if available_slot:
                    form.instance.slot = available_slot
                else:
                    raise ValidationError(f"No available slots for teacher {form.instance.teacher_id} in stream {stream.stream_code}")
            except Stream.DoesNotExist:
                raise ValidationError(f"No stream found with code: {student_stream_code}")

        teacher_theme = form.cleaned_data.get('teacher_themes')
        if teacher_theme:
            # Mark the chosen teacher theme as occupied.
            theme = TeacherTheme.objects.get(theme=teacher_theme, teacher_id=form.instance.teacher_id)
            form.instance.teacher_theme = theme
            theme.is_occupied = True
            theme.save()




            
        

    
    