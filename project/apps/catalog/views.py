from .utils import HtmxLoginRequiredMixin
from .models import OnlyTeacher, Slot, TeacherTheme, StudentTheme, Stream, Request
from django.core.exceptions import ValidationError 
from django.views.generic import ListView, DetailView, FormView
from .forms import RequestForm
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import F
from django.views import View
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.template.loader import render_to_string

import re

class TeachersListView(ListView):
    """
    Displays a list of teachers along with their available slots.
    """
    model = OnlyTeacher
    template_name = 'catalog/teachers_catalog.html'
    context_object_name = 'data'
    
    def get_queryset(self):
        """
        Returns a list of dictionaries that each contain:
        - Teacher instance
        - Free slots for that teacher
        """
        # Using `select_related` to optimize queries.
        teachers = OnlyTeacher.objects.select_related('teacher_id').all()
        
        # Get all slots with available quotas.
        slots = Slot.filter_by_available_slots()
        data = []
        is_matched = False
        
        # If user is a student, filter slots based on user's academic group.
        if self.request.user.is_authenticated and self.request.user.role == 'Студент':
            user = self.request.user
            match = re.match(r'([А-ЯІЇЄҐ]+)-(\d)', user.academic_group)
            if match:
                user_stream = match.group(1) + '-' + match.group(2)
                slots = slots.filter(stream_id__stream_code__iexact=user_stream)
                is_matched = True
        
        # Collect teacher and corresponding free slots in a list of dicts.
        for teacher in teachers:
            free_slots = slots.filter(teacher_id=teacher)
            data.append({
                'teacher': teacher,
                'free_slots': free_slots,
                'is_matched': is_matched
            })
        return data    

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
        print(f"All available slots for teacher {teacher}: {slots.count()}")
        is_matched = False
        
        # Filter slots by user's academic group if the user is a student.
        user = self.request.user
        match = re.match(r'([А-ЯІЇЄҐ]+)-(\d)', user.academic_group)
        if match:
            user_stream = match.group(1) + '-' + match.group(2)
            print(f"User stream: {user_stream}")
            slots = slots.filter(stream_id__stream_code__iexact=user_stream)
            print(f"Available slots for stream {user_stream}: {slots.count()}")
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
        try:
            # First try to assign the slot and save the request
            req = form.save(commit=False)
            self.assign_request_fields(form)
            
            # Get and validate the teacher theme if selected
            teacher_theme_text = form.cleaned_data.get('teacher_themes')
            if teacher_theme_text:
                try:
                    teacher_theme = TeacherTheme.objects.get(
                        theme=teacher_theme_text, 
                        teacher_id=self.get_object()
                    )
                    if not teacher_theme.is_occupied:
                        req.teacher_theme = teacher_theme
                        teacher_theme.is_occupied = True
                        teacher_theme.save()
                        print(f"Teacher theme assigned: {teacher_theme.theme}")
                    else:
                        raise ValidationError("Обрана тема вже зайнята")
                except TeacherTheme.DoesNotExist:
                    raise ValidationError("Обрана тема не існує")
            
            # Save the request after theme assignment
            req.save()
            print(f"Request created with ID: {req.id}")

            # Save student themes
            student_themes = form.cleaned_data.get('student_themes', [])
            if isinstance(student_themes, str):
                student_themes = [student_themes]
            
            for theme in student_themes:
                if theme and isinstance(theme, str):
                    student_theme = StudentTheme.objects.create(
                        student_id=self.request.user,
                        theme=theme.strip()
                    )
                    req.student_themes.add(student_theme)
                    print(f"Student theme added: {student_theme.theme}")
            
            # Update slot occupancy
            if req.slot:
                req.slot.occupied += 1
                req.slot.save()
                print(f"Slot {req.slot.id} occupancy updated to {req.slot.occupied}")
            
            messages.success(self.request, self.get_success_message(form.cleaned_data))
            
            if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
                response = JsonResponse({
                    'success': True,
                    'message': self.get_success_message(form.cleaned_data)
                })
                # Add HTMX redirect header to refresh the page
                response['HX-Redirect'] = reverse_lazy('profile')
                return response
            return super().form_valid(form)
        
        except ValidationError as e:
            print(f"Validation error: {str(e)}")
            messages.error(self.request, str(e))
            if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [str(e)]}
                }, status=400)
            return self.form_invalid(form)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            messages.error(self.request, f"Помилка при створенні запиту: {str(e)}")
            if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [f"Помилка при створенні запиту: {str(e)}"]}
                }, status=400)
            return self.form_invalid(form)
        
    def assign_request_fields(self, form):
        """
        Assigns current user, teacher, and request status to the form instance.
        Updates the proposed theme to occupied if provided.
        """
        form.instance.student_id = self.request.user
        form.instance.teacher_id = self.get_object()
        form.instance.request_status = 'Очікує'
        
        student_stream_code = form.instance.extract_stream_from_academic_group()
        if student_stream_code:
            try:
                stream = Stream.objects.get(stream_code=student_stream_code)
                # Get all slots for this teacher and stream
                available_slots = Slot.objects.filter(
                    teacher_id=form.instance.teacher_id,
                    stream_id=stream
                )
                
                # Find first slot that has space
                available_slot = None
                for slot in available_slots:
                    if slot.occupied < slot.quota:
                        available_slot = slot
                        break
                
                if available_slot:
                    form.instance.slot = available_slot
                else:
                    raise ValidationError(f"Немає вільних місць у викладача для потоку {stream.stream_code}")
            except Stream.DoesNotExist:
                raise ValidationError(f"Потік не знайдено: {student_stream_code}")

class AcceptRequestView(View):
    def post(self, request, pk):
        req = get_object_or_404(Request, pk=pk)
        if request.user.role == 'Викладач' and req.teacher_id.teacher_id == request.user:
            req.request_status = 'Активний'
            req.save()
            messages.success(request, 'Запит прийнято')
            return JsonResponse({'success': True})
        return JsonResponse({'success': False}, status=403)

class CompleteRequestView(View):
    def post(self, request, pk):
        req = get_object_or_404(Request, pk=pk)
        if request.user.role == 'Викладач' and req.teacher_id.teacher_id == request.user:
            req.request_status = 'Завершено'
            req.completion_date = timezone.now()
            req.grade = request.POST.get('grade')
            req.save()
            messages.success(request, 'Роботу завершено')
            return JsonResponse({'success': True})
        return JsonResponse({'success': False}, status=403)

def get_requests_data(request):
    if request.user.role == 'Викладач':
        pending_requests = Request.objects.select_related(
            'student_id', 'teacher_id', 'teacher_theme', 'slot'
        ).prefetch_related('student_themes').filter(
            teacher_id__teacher_id=request.user,
             request_status='Очікує'
        )
        active_requests = Request.objects.select_related(
            'student_id', 'teacher_id', 'teacher_theme', 'slot'
        ).prefetch_related('student_themes').filter(
            teacher_id__teacher_id=request.user,
            request_status='Активний'
        )
        archived_requests = Request.objects.select_related(
            'student_id', 'teacher_id', 'teacher_theme', 'slot'
        ).prefetch_related('student_themes').filter(
            teacher_id__teacher_id=request.user,
            request_status='Завершено'
        )
    else:  # Student
        pending_requests = Request.objects.select_related(
            'student_id', 'teacher_id', 'teacher_theme', 'slot'
        ).prefetch_related('student_themes').filter(
            student_id=request.user,
            request_status='Очікує'
        )
        active_requests = Request.objects.select_related(
            'student_id', 'teacher_id', 'teacher_theme', 'slot'
        ).prefetch_related('student_themes').filter(
            student_id=request.user,
            request_status='Активний'
        )
        archived_requests = Request.objects.select_related(
            'student_id', 'teacher_id', 'teacher_theme', 'slot'
        ).prefetch_related('student_themes').filter(
            student_id=request.user,
            request_status='Завершено'
        )
    
    print(f"Found pending requests: {pending_requests.count()}")
    print(f"Found active requests: {active_requests.count()}")
    print(f"Found archived requests: {archived_requests.count()}")
    
    return {
        'pending_requests': pending_requests,
        'active_requests': active_requests,
        'archived_requests': archived_requests
    }

def load_tab_content(request, tab_name):
    data = get_requests_data(request)
    template_name = f'profile/{tab_name}.html'
    html = render_to_string(template_name, data, request=request)
    return JsonResponse({'html': html})

def reject_request(request, request_id):
    """
    Reject a request and update its status to 'rejected'.
    """
    if request.method == 'POST':
        try:
            req = Request.objects.get(id=request_id)
            
            # Check if the user is the teacher who received the request
            if request.user == req.teacher_id.teacher_id:
                # Update request status
                req.request_status = 'Відхилено'
                req.save()
                
                # If there was a teacher theme, mark it as unoccupied
                if req.teacher_theme:
                    req.teacher_theme.is_occupied = False
                    req.teacher_theme.save()
                
                messages.success(request, 'Запит успішно відхилено')
                
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True})
                return redirect('profile')
            else:
                messages.error(request, 'У вас немає прав для відхилення цього запиту')
        except Request.DoesNotExist:
            messages.error(request, 'Запит не знайдено')
        except Exception as e:
            messages.error(request, f'Помилка при відхиленні запиту: {str(e)}')
    
    return redirect('profile')
    
    