from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.http import JsonResponse, HttpResponseForbidden, FileResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseServerError
from django.contrib.auth.decorators import login_required
from .forms import RequestForm, FilteringSearchingForm, RequestFileForm, FileCommentForm
from .models import OnlyTeacher, Slot, TeacherTheme, StudentTheme, Stream, Request, RequestFile, FileComment
from django.core.exceptions import ValidationError 
from django.views.generic import ListView, DetailView, FormView, TemplateView
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.db.models import Max
from django.utils import timezone
from django.template.loader import render_to_string
from .utils import HtmxModalFormAccessMixin, FileAccessMixin

from django.shortcuts import render

import re
import logging

class TeachersCatalogView(TemplateView, FormView):
    """
    Displays the teachers catalog page with filtering and searching capabilities.
    
    This view combines TemplateView and FormView to render a catalog of teachers
    that can be filtered and searched by various criteria.
    
    Attributes:
        template_name (str): Path to the template that renders the catalog.
        form_class: Form class for filtering and searching teachers.
    
    Methods:
        get: Handles GET requests to display the teachers catalog with the filter form.
    """
    template_name = 'catalog/teachers_catalog.html'
    form_class = FilteringSearchingForm
    
    def get(self, request, *args, **kwargs):
        """
        Handles GET requests to display the teachers catalog.
        
        Args:
            request (HttpRequest): The HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
            
        Returns:
            HttpResponse: Rendered template with the filter form.
        """
        form = self.form_class()
        context = {'form': form}
        return render(request, self.template_name, context)
    
class TeachersListView(ListView):    
    """
    API view that provides a list of teachers with their available slots.
    
    This view extends Django's ListView to return JSON data containing
    teacher information and availability slots. It handles filtering based on
    the authenticated student's academic group.
    
    Attributes:
        model (Model): The OnlyTeacher model class.
        context_object_name (str): Name for the context variable containing the data.
    
    Methods:
        get: Returns JSON data with teacher information and available slots.
    """
    model = OnlyTeacher
    context_object_name = 'data'
    
    def get(self, request, *args, **kwargs):
        """
        Returns a JSON response with teacher data and their available slots.
        
        For authenticated students, slots are filtered by the student's academic group.
        Each teacher entry includes personal information and availability data.
        
        Args:
            request (HttpRequest): The HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
            
        Returns:
            JsonResponse: JSON data containing teachers and their available slots.
                Format:
                [
                    {
                        'teacher': {
                            'id': int,
                            'position': str,
                            'photo': str (url),
                            'teacher_id': {
                                'first_name': str,
                                'last_name': str,
                                'department': str,
                            }
                        },
                        'free_slots': [
                            {
                                'stream_id': {
                                    'stream_code': str
                                },
                                'get_available_slots': int
                            }
                        ],
                        'is_matched': bool
                    }
                ]
        """
        teachers = OnlyTeacher.objects.select_related('teacher_id').all()
        slots = Slot.filter_by_available_slots()
        data = []
        is_matched = False
        has_active = False
        already_requested_set = set()

        if request.user.is_authenticated and request.user.role == 'Студент':
            user = request.user
            has_active = True if Request.objects.filter(
                student_id=user,
                request_status='Активний'
            ).exists() else False
            
            teacher_ids = [t.pk for t in teachers]
            already_requested_qs = Request.objects.filter(
                student_id=user,
                teacher_id__in=teacher_ids,
                request_status='Очікує'
            ).values_list('teacher_id', flat=True)
            already_requested_set = set(already_requested_qs)
            match = re.match(r'([А-ЯІЇЄҐ]+)-(\d)', user.academic_group)
            if match:
                user_stream = match.group(1) + '-' + match.group(2)
                slots = slots.filter(stream_id__stream_code__iexact=user_stream)
                is_matched = True
                
    

        for teacher in teachers:
            free_slots = slots.filter(teacher_id=teacher)
            already_requested = teacher.pk in already_requested_set
            if teacher.teacher_id.patronymic:
                patronymic = teacher.teacher_id.patronymic
                full_name = f"{teacher.teacher_id.last_name} {teacher.teacher_id.first_name} {patronymic}"
            else:
                full_name = f"{teacher.teacher_id.last_name} {teacher.teacher_id.first_name}"

            data.append({
                'has_active': has_active,
                'teacher': {
                    'id': teacher.pk,
                    'academic_level': teacher.academic_level,
                    'photo': teacher.teacher_id.profile_picture.url,
                    'url': teacher.get_absolute_url(),
                    'already_requested': already_requested,
                    'teacher_id': {
                        'first_name': teacher.teacher_id.first_name,
                        'last_name': teacher.teacher_id.last_name,
                        'department': teacher.teacher_id.department,
                        'full_name': full_name
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

class TeacherModalView(HtmxModalFormAccessMixin, SuccessMessageMixin, DetailView, FormView):
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
        context['photo'] = teacher.teacher_id.profile_picture.url 
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
            if req.slot:
                req.slot.get_available_slots()
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
            if req.slot:
                req.slot.get_available_slots()
            messages.success(request, 'Роботу завершено')
            return JsonResponse({'success': True})
        return JsonResponse({'success': False}, status=403)

@login_required
def archived_request_details(request, pk):
    import logging
    logger = logging.getLogger('django')
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        logger.error(f'[ARCHIVE MODAL] Not AJAX request for pk={pk}')
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        req = Request.objects.select_related(
            'student_id', 'teacher_id__teacher_id', 'teacher_theme'
        ).prefetch_related(
            'files__comments__author'
        ).get(pk=pk, request_status='Завершено')
        # Check access permissions
        if request.user.role == 'Студент' and req.student_id != request.user:
            logger.error(f'[ARCHIVE MODAL] Forbidden: student_id mismatch (req.student_id={req.student_id.id}, user={request.user.id})')
            return JsonResponse({'error': 'Forbidden'}, status=403)
        if request.user.role == 'Викладач' and req.teacher_id.teacher_id != request.user:
            logger.error(f'[ARCHIVE MODAL] Forbidden: teacher_id mismatch (req.teacher_id.teacher_id={req.teacher_id.teacher_id.id}, user={request.user.id})')
            return JsonResponse({'error': 'Forbidden'}, status=403)
        files_data = []
        for file in req.files.all():
            file_data = {
                'file_name': file.get_filename(),
                'file_url': file.file.url,
                'description': file.description,
                'uploaded_by': file.uploaded_by.get_full_name(),
                'uploaded_at': file.uploaded_at.strftime('%d.%m.%Y %H:%M'),
                'comments': [
                    {
                        'author': comment.author.get_full_name(),
                        'text': comment.text,
                        'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M')
                    }
                    for comment in file.comments.all()
                ]
            }
            files_data.append(file_data)
        data = {
            'student': {
                'name': req.student_id.get_full_name(),
                'group': req.student_id.academic_group
            },
            'teacher': {
                'name': req.teacher_id.teacher_id.get_full_name()
            },
            'theme': req.teacher_theme.theme if req.teacher_theme else "Без теми",
            'grade': req.grade,
            'completion_date': req.completion_date.strftime("%d.%m.%Y"),
            'files': files_data
        }
        return JsonResponse(data)
    except Request.DoesNotExist:
        logger.error(f'[ARCHIVE MODAL] Request not found for pk={pk}')
        return JsonResponse({'error': 'Request not found'}, status=404)
    except Exception as e:
        logger.error(f'[ARCHIVE MODAL] Unexpected error for pk={pk}: {str(e)}')
        return JsonResponse({'error': 'An unexpected error occurred', 'details': str(e)}, status=500)

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
    
    # Get files for active requests
    active_request_files = {}
    for request_obj in active_requests:
        files = RequestFile.objects.filter(request=request_obj).select_related('uploaded_by')
        active_request_files[str(request_obj.id)] = list(files)  # Convert QuerySet to list and use string key
    
    return {
        'pending_requests': pending_requests,
        'active_requests': active_requests,
        'archived_requests': archived_requests,
        'active_request_files': active_request_files,
    }

def load_tab_content(request, tab_name):
    try:
        data = get_requests_data(request)
        
        data.update({
            'user': request.user,
            'request': request, 
        })
        
        template_name = f'profile/{tab_name}.html'
        html = render_to_string(template_name, data, request=request)
        return JsonResponse({'html': html})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def reject_request(request, request_id):
    if request.method == 'POST':
        try:
            req = Request.objects.get(id=request_id)
            if request.user == req.teacher_id.teacher_id:
                req.request_status = 'Відхилено'
                req.save()
                messages.success(request, 'Запит успішно відхилено')
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True})
                return redirect('profile')
        except Request.DoesNotExist:
            messages.error(request, 'Запит не знайдено')
        except Exception as e:
            messages.error(request, f'Помилка при відхиленні запиту: {str(e)}')
    
    return redirect('profile')

class UploadFileView(View):
    def post(self, request, request_id):
        try:
            course_request = Request.objects.get(pk=request_id)
            
            if request.user != course_request.student_id and request.user != course_request.teacher_id.teacher_id:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': 'Немає прав доступу'}, status=403)
                return HttpResponseForbidden('Немає прав доступу')
            
            if course_request.request_status != 'Активний':
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': 'Файли можна додавати тільки до активних запитів'}, status=400)
                return HttpResponseBadRequest('Файли можна додавати тільки до активних запитів')
            
            form = RequestFileForm(request.POST, request.FILES)
            if form.is_valid():
                file = form.save(commit=False)
                file.request = course_request
                file.uploaded_by = request.user
                
                latest_version = RequestFile.objects.filter(request=course_request).aggregate(Max('version'))['version__max']
                file.version = (latest_version or 0) + 1
                
                file.save()
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success'})
                return redirect('profile')
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Помилка у формі'}, status=400)
            return HttpResponseBadRequest('Помилка у формі')
        except Request.DoesNotExist:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Запит не знайдено'}, status=404)
            return HttpResponseNotFound('Запит не знайдено')
        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            return HttpResponseServerError(str(e))


class DeleteFileView(FileAccessMixin, View):
    def post(self, request, pk):
        try:
            file = RequestFile.objects.get(pk=pk)
            
            if not (request.user == file.uploaded_by or request.user == file.request.teacher_id.teacher_id):
                return JsonResponse({
                    'status': 'error',
                    'message': 'У вас немає прав для видалення цього файлу'
                })
            
            file.delete()
            return JsonResponse({
                'success': True,
                'message': 'Файл успішно видалено'
            })
        except RequestFile.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Файл не знайдено'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


class DownloadFileView(FileAccessMixin, View):
    def get(self, request, pk):
        try:
            file = RequestFile.objects.get(pk=pk)
            course_request = file.request
            
            if not (request.user == file.uploaded_by or request.user == course_request.student_id or request.user == course_request.teacher_id.teacher_id):
                return HttpResponseForbidden('Немає прав доступу')
            
            response = FileResponse(file.file)
            response['Content-Disposition'] = f'attachment; filename="{file.get_filename()}"'
            return response
            
        except RequestFile.DoesNotExist:
            return HttpResponseNotFound('Файл не знайдено')


class AddCommentView(FileAccessMixin, View):
    def post(self, request, file_id):
        """Обробляє POST-запит для додавання коментаря до файлу"""
        try:
            file = RequestFile.objects.get(pk=file_id)
            course_request = file.request
            
            if request.user != course_request.student_id and request.user != course_request.teacher_id.teacher_id:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Немає прав доступу'}, status=403)
                else:
                    messages.error(request, 'Немає прав доступу для додавання коментаря')
                    return redirect('profile')
            
            text = request.POST.get('text')
            if not text and not request.FILES.get('attachment'):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Коментар не може бути порожнім, додайте текст або прикріпіть файл'}, status=400)
                else:
                    messages.error(request, 'Коментар не може бути порожнім, додайте текст або прикріпіть файл')
                    return redirect('profile')
            
            comment = FileComment(
                file=file,
                author=request.user,
                text=text or ''  
            )
            
            attachment = request.FILES.get('attachment')
            if attachment:
                comment.attachment = attachment
            
            comment.save()
                
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                response_data = {
                    'success': True,
                    'comment_id': comment.id,
                    'text': comment.text,
                    'author': comment.author.get_full_name(),
                    'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M')
                }
                
                if comment.attachment:
                    response_data['attachment'] = {
                        'name': comment.get_attachment_filename(),
                        'url': comment.attachment.url
                    }
                
                return JsonResponse(response_data)
            else:
                messages.success(request, 'Коментар успішно додано')
                return redirect('profile')
            
        except RequestFile.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Файл не знайдено'}, status=404)
            else:
                messages.error(request, 'Файл не знайдено')
                return redirect('profile')
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)}, status=500)
            else:
                messages.error(request, f'Помилка при додаванні коментаря: {str(e)}')
                return redirect('profile')


class DeleteCommentView(FileAccessMixin, View):
    def post(self, request, pk):
        try:
            comment = FileComment.objects.get(pk=pk)
            
            if request.user != comment.author:
                return JsonResponse({'success': False, 'error': 'Немає прав доступу'}, status=403)
            
            comment.delete()
            return JsonResponse({'success': True})
            
        except FileComment.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Коментар не знайдено'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

@login_required
def add_comment(request, file_id):
    file = get_object_or_404(RequestFile, id=file_id)
    if request.method == 'POST':
        form = FileCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.file = file
            comment.author = request.user
            comment.save()
            return JsonResponse({
                'status': 'success',
                'comment': {
                    'id': comment.id,
                    'text': comment.text,
                    'author': comment.author.get_full_name(),
                    'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                }
            })
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def delete_comment(request, pk):
    comment = get_object_or_404(FileComment, pk=pk)
    if comment.author == request.user or request.user.is_staff:
        comment.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)