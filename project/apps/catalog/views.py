import logging
import re
import json
from urllib import request

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.http import (
    FileResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, ListView, TemplateView

from .forms import FileCommentForm, FilteringSearchingForm, RequestFileForm, RequestForm
from .models import (
    FileComment,
    OnlyTeacher,
    Request,
    RequestFile,
    Slot,
    Stream,
    StudentTheme,
    TeacherTheme,
    Announcement
)
from .templatetags.catalog_extras import get_profile_picture_url
from .utils import FileAccessMixin, HtmxModalFormAccessMixin


class TeachersCatalogView(LoginRequiredMixin, TemplateView, FormView):
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

    template_name = "catalog/teachers_catalog.html"
    form_class = FilteringSearchingForm
        
    def dispatch(self, request, *args, **kwargs):
        # Дозволяємо доступ лише студентам
        if (
            not request.user.is_authenticated
            or getattr(request.user, "role", None) != "Студент"
        ):
            from django.shortcuts import redirect
            from django.urls import reverse

            return redirect("profile")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = self.get_form()
        context["user_profile"] = self.request.user
        return context
    
    def get(self, request, *args, **kwargs):
        """
        Handles GET requests to display the teachers catalog.
        """
        return self.render_to_response(self.get_context_data())
    

class TeachersListView(LoginRequiredMixin, ListView):
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
    context_object_name = "data"
    
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
        try:
            teachers = OnlyTeacher.objects.select_related("teacher_id").all()
            slots = Slot.filter_by_available_slots()
            data = []
            is_matched = False
            has_active = False
            already_requested_set = set()

            if request.user.is_authenticated and request.user.role == "Студент":
                user = request.user
                has_active = (
                    True
                    if Request.objects.filter(
                        student_id=user, request_status="Активний"
                    ).exists()
                    else False
                )
                
                # --- Фільтрація за кафедрою для 3+ курсу ---
                # Витягуємо курс з academic_group (наприклад, ФЕС-33 -> 3)
                course = None
                is_master = "М" in user.academic_group.upper()
                if user.academic_group:
                    match = re.match(r"^ФЕ[СМЛПІ]-(\d)", user.academic_group)
                    if match:
                        course = int(match.group(1))
                
                # Оновлена, більш точна умова фільтрації
                if user.department and ((course and course >= 3) or is_master):
                    teachers = teachers.filter(
                        teacher_id__department__iexact=user.department.strip()
                    )
                
                teacher_ids = [t.pk for t in teachers]
                # ---

                teacher_ids = [t.pk for t in teachers]
                already_requested_qs = Request.objects.filter(
                    student_id=user, teacher_id__in=teacher_ids, request_status="Очікує"
                ).values_list("teacher_id", flat=True)
                already_requested_set = set(already_requested_qs)
                match = re.match(r"([А-ЯІЇЄҐ]+)-(\d)", user.academic_group)
                if match:
                    user_stream = (
                        match.group(1)
                        + "-"
                        + match.group(2)
                        + ("м" if is_master else "")
                    )

                    # Фільтруємо по коду потоку та освітньому ступеню, але дозволяємо None значення
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

                # Handle profile picture URL safely
                try:
                    photo_url = get_profile_picture_url(teacher.teacher_id)
                except Exception as e:
                    print(f"Error getting profile picture URL: {str(e)}")
                    photo_url = static("images/default-avatar.jpg")

                data.append(
                    {
                        "has_active": has_active,
                        "teacher": {
                            "id": teacher.pk,
                            "academic_level": teacher.academic_level,
                            "photo": photo_url,
                            "url": teacher.get_absolute_url(),
                            "already_requested": already_requested,
                            "teacher_id": {
                                "id": teacher.teacher_id.id,
                                "first_name": teacher.teacher_id.first_name,
                                "last_name": teacher.teacher_id.last_name,
                                "department": teacher.teacher_id.department,
                                "full_name": full_name,
                            },
                        },
                        "free_slots": [
                            {
                                "stream_id": {
                                    "stream_code": slot.stream_id.stream_code
                                },
                                "get_available_slots": slot.get_available_slots(),
                        }
                        for slot in free_slots
                    ],
                        "is_matched": is_matched,
                    }
                )

            return JsonResponse(data, safe=False)
        except Exception as e:
            import traceback

            print("Error in TeachersListView:", str(e))
            print(traceback.format_exc())
            return JsonResponse({"error": str(e)}, status=500)


class TeacherModalView(
    HtmxModalFormAccessMixin, SuccessMessageMixin, DetailView, FormView
):
    """
    Manages the teacher detail view, form submission, and saves student requests.
    """

    model = OnlyTeacher
    template_name = "catalog/teacher_modal.html"
    context_object_name = "teacher"
    form_class = RequestForm
    success_url = reverse_lazy("teachers_catalog")
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
        Passes the teacher instance and current user to the form.
        """
        kwargs = super().get_form_kwargs()
        kwargs["teacher_id"] = self.get_object()
        kwargs["user"] = self.request.user
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
        is_master = "М" in user.academic_group.upper()
        match = re.match(r"([А-ЯІЇЄҐ]+)-(\d)", user.academic_group)
        if match:
            user_stream = (
                match.group(1) + "-" + match.group(2) + ("м" if is_master else "")
            )
            print(f"User stream: {user_stream}")
            # Фільтруємо по коду потоку та освітньому ступеню, але дозволяємо None значення
            
            slots = slots.filter(stream_id__stream_code__iexact=user_stream)
            print(f"Available slots for stream {user_stream}: {slots.count()}")
            is_matched = True
        
        context["free_slots"] = slots
        context["is_matched"] = is_matched
        
        # Use the template tag to get profile picture URL
        context["photo"] = get_profile_picture_url(teacher.teacher_id)
            
        return context
    
    def form_invalid(self, form):
        """
        Handles invalid form submissions. Returns JSON for XMLHttpRequests.
        """
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
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
            teacher_theme_text = form.cleaned_data.get("teacher_themes")
            if teacher_theme_text:
                try:
                    teacher_theme = TeacherTheme.objects.get(
                        theme=teacher_theme_text, teacher_id=self.get_object()
                    )
                    if not teacher_theme.is_occupied and not teacher_theme.is_deleted:
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
            student_themes = form.cleaned_data.get("student_themes", [])
            if isinstance(student_themes, str):
                student_themes = [student_themes]
            
            for theme in student_themes:
                if theme and isinstance(theme, str):
                    student_theme = StudentTheme.objects.create(
                        student_id=self.request.user, request=req, theme=theme.strip()
                    )
                    print(f"Student theme added: {student_theme.theme}")
                        
            messages.success(self.request, self.get_success_message(form.cleaned_data))
            
            if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
                response = JsonResponse(
                    {
                        "success": True,
                        "message": self.get_success_message(form.cleaned_data),
                    }
                )
                # Add HTMX redirect header to refresh the page
                response["HX-Redirect"] = reverse_lazy("profile")
                return response
            return super().form_valid(form)
        
        except ValidationError as e:
            print(f"Validation error: {str(e)}")
            messages.error(self.request, str(e))
            if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "errors": {"__all__": e.messages}}, status=400
                )
            return self.form_invalid(form)

    def assign_request_fields(self, form):
        """
        Assigns current user, teacher, and request status to the form instance.
        Updates the proposed theme to occupied if provided.
        """
        form.instance.student_id = self.request.user
        form.instance.teacher_id = self.get_object()
        form.instance.request_status = "Очікує"
        
        is_master = "М" in self.request.user.academic_group.upper()
        student_stream_code = form.instance.extract_stream_from_academic_group() + (
            "м" if is_master else ""
        )
        curse = student_stream_code.split("-")[1] if student_stream_code else None

        if curse and curse == "4":
            form.instance.work_type = "Дипломна"
        elif is_master:
            form.instance.work_type = "Магістерська"
        else:
            form.instance.work_type = "Курсова"
        
        if student_stream_code:
            try:
                # Get a single Stream object instead of a QuerySet
                stream = Stream.objects.get(stream_code=student_stream_code)
                    
                # Get all slots for this teacher and stream
                available_slots = Slot.objects.filter(
                    teacher_id=form.instance.teacher_id, stream_id=stream
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
                    raise ValidationError(
                        f"На жаль, вільних місць для {stream.stream_code} нема :("
                    )
            except Stream.DoesNotExist:
                raise ValidationError(f"Потік не знайдено: {student_stream_code}")


# AcceptRequestView видалено - використовується approve_request_with_theme з users/views.py


class CompleteRequestView(View):
    def post(self, request, pk):
        req = get_object_or_404(Request, pk=pk)
        if (
            request.user.role == "Викладач"
            and req.teacher_id.teacher_id == request.user
        ):
            # Отримуємо обрані файли
            selected_files_json = request.POST.get("selected_files", "[]")
            logger.error(f"[COMPLETE DEBUG] selected_files_json: {selected_files_json}")
            try:
                selected_file_ids = json.loads(selected_files_json)
                logger.error(f"[COMPLETE DEBUG] selected_file_ids: {selected_file_ids}")
            except json.JSONDecodeError as e:
                logger.error(f"[COMPLETE DEBUG] JSON decode error: {e}")
                selected_file_ids = []
            
            # Позначаємо файли як архівні
            if selected_file_ids:
                updated_files = RequestFile.objects.filter(
                    request=req,
                    id__in=selected_file_ids
                ).update(is_archived=True)
                logger.error(f"[COMPLETE DEBUG] Updated {updated_files} files as archived")
                
                # Позначаємо необрані файли як неархівні
                unarchived_files = RequestFile.objects.filter(
                    request=req
                ).exclude(
                    id__in=selected_file_ids
                ).update(is_archived=False)
                logger.error(f"[COMPLETE DEBUG] Updated {unarchived_files} files as not archived")
                
                req.request_status = "Завершено"
                req.completion_date = timezone.now()
                req.grade = request.POST.get("grade")
                req.save()
            else:
                logger.error("[COMPLETE DEBUG] No files selected")
                return JsonResponse({
                    "success": False, 
                    "error": "Необхідно обрати хоча б один файл для збереження в архіві"
                })

            # Theme will be freed automatically in the model when status changes to 'Завершено'

            if req.slot:
                req.slot.get_available_slots()
            messages.success(request, "Роботу завершено")
            return JsonResponse({"success": True})
        return JsonResponse({"success": False}, status=403)


@login_required
def request_files_for_completion(request, request_id):
    """Отримати файли запиту для вибору при завершенні"""
    try:
        req = get_object_or_404(Request, pk=request_id)
        
        # Перевіряємо права доступу
        if request.user.role == "Викладач" and req.teacher_id.teacher_id != request.user:
            return JsonResponse({"error": "Forbidden"}, status=403)
        
        files_data = []
        for file in req.files.all():
            files_data.append({
                "id": file.id,
                "file_name": file.get_filename(),
                "uploaded_at": file.uploaded_at.strftime("%d.%m.%Y %H:%M"),
                "uploaded_by": file.uploaded_by.get_full_name() if file.uploaded_by else "Невідомий",
                "description": file.description or "",
            })
        
        return JsonResponse({"files": files_data})
        
    except Request.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": "An unexpected error occurred"}, status=500)


@login_required
def archived_request_details(request, request_id):
    logger = logging.getLogger("django")
    logger.error(
        f'[ARCHIVE DEBUG] request.user.id={request.user.id}, request.user.role={getattr(request.user, "role", None)}'
    )
    try:
        req = (
            Request.objects.select_related(
                "student_id", "teacher_id__teacher_id", "teacher_theme"
            )
            .prefetch_related("files__comments__author")
            .get(id=request_id, request_status="Завершено")
        )
        logger.error(
            f'[ARCHIVE DEBUG] req.student_id.id={getattr(req.student_id, "id", None)}, req.teacher_id.teacher_id.id={getattr(req.teacher_id.teacher_id, "id", None)}'
        )
        # Check access permissions
        if request.user.role == "Студент" and req.student_id != request.user:
            logger.error(
                f"[ARCHIVE DEBUG] 403: student_id mismatch (req.student_id={req.student_id.id}, user={request.user.id})"
            )
            return JsonResponse({"error": "Forbidden"}, status=403)
        if (
            request.user.role == "Викладач"
            and req.teacher_id.teacher_id != request.user
        ):
            logger.error(
                f"[ARCHIVE DEBUG] 403: teacher_id mismatch (req.teacher_id.teacher_id={req.teacher_id.teacher_id.id}, user={request.user.id})"
            )
            return JsonResponse({"error": "Forbidden"}, status=403)
        files_data = []
        all_files = req.files.all()
        archived_files = req.files.filter(is_archived=True)
        logger.error(f"[ARCHIVE DEBUG] Request ID: {req.id}")
        logger.error(f"[ARCHIVE DEBUG] Total files: {all_files.count()}, Archived files: {archived_files.count()}")
        logger.error(f"[ARCHIVE DEBUG] All files: {[f.id for f in all_files]}")
        logger.error(f"[ARCHIVE DEBUG] Archived files: {[f.id for f in archived_files]}")
        
        for file in archived_files:
            logger.error(f"[ARCHIVE DEBUG] Processing archived file: ID {file.id}, name {file.get_filename()}")
            comments_data = []
            for comment in file.comments.all():
                comments_data.append(
                    {
                        "author": comment.author.get_full_name(),
                        "text": comment.text,
                        "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M"),
                    }
                )

            files_data.append(
                {
                    "id": file.id,
                    "file_url": file.file.url,
                    "file_name": file.get_filename(),
                    "description": file.description,
                    "uploaded_at": file.uploaded_at.strftime("%d.%m.%Y %H:%M"),
                    "uploaded_by": file.uploaded_by.get_full_name(),
                    "comments": comments_data,
                }
            )
        
        logger.error(f"[ARCHIVE DEBUG] Final files_data length: {len(files_data)}")
        
        response_data = {
            "student": {
                "name": req.student_id.get_full_name(),
                "group": req.student_id.academic_group,
            },
            "teacher": {
                "name": req.teacher_id.teacher_id.get_full_name(),
            },
            "theme": (
                req.teacher_theme.theme if req.teacher_theme else "Тема не вказана"
            ),
            "grade": req.grade,
            "completion_date": req.completion_date.strftime("%d.%m.%Y"),
            "files": files_data,
        }
        
        return JsonResponse(response_data)

    except Request.DoesNotExist:
        logger.error(f"[ARCHIVE DEBUG] 404: Request.DoesNotExist for id={request_id}")
        return JsonResponse({"error": "Request not found"}, status=404)
    except Exception as e:
        logger.error(f"[ARCHIVE DEBUG] 500: {str(e)}")
        return JsonResponse({"error": "An unexpected error occurred"}, status=500)


def get_requests_data(request):
    if request.user.role == "Викладач":
        pending_requests = (
            Request.objects.select_related(
                "student_id", "teacher_id", "teacher_theme", "slot"
            )
            .prefetch_related("student_themes")
            .filter(teacher_id__teacher_id=request.user, request_status="Очікує")
        )
        active_requests = (
            Request.objects.select_related(
                "student_id", "teacher_id", "teacher_theme", "slot"
            )
            .prefetch_related("student_themes")
            .filter(teacher_id__teacher_id=request.user, request_status="Активний")
        )
        archived_requests = (
            Request.objects.select_related(
                "student_id", "teacher_id", "teacher_theme", "slot"
            )
            .prefetch_related("student_themes")
            .filter(
            teacher_id__teacher_id=request.user,
                request_status="Завершено",
                files__is_archived=True
            ).distinct()
        )
    else:  # Student
        pending_requests = (
            Request.objects.select_related(
                "student_id", "teacher_id", "teacher_theme", "slot"
            )
            .prefetch_related("student_themes")
            .filter(student_id=request.user, request_status="Очікує")
        )
        active_requests = (
            Request.objects.select_related(
                "student_id", "teacher_id", "teacher_theme", "slot"
            )
            .prefetch_related("student_themes")
            .filter(student_id=request.user, request_status="Активний")
        )
        archived_requests = (
            Request.objects.select_related(
                "student_id", "teacher_id", "teacher_theme", "slot"
            )
            .prefetch_related("student_themes")
            .filter(
            student_id=request.user,
                request_status="Завершено",
                files__is_archived=True
            ).distinct()
        )
    
    print(f"Found pending requests: {pending_requests.count()}")
    print(f"Found active requests: {active_requests.count()}")
    print(f"Found archived requests: {archived_requests.count()}")
    
    # Get files for active requests
    active_request_files = {}
    for request_obj in active_requests:
        files = RequestFile.objects.filter(request=request_obj).select_related(
            "uploaded_by"
        )
        active_request_files[str(request_obj.id)] = list(
            files
        )  # Convert QuerySet to list and use string key
    
    return {
        "pending_requests": pending_requests,
        "active_requests": active_requests,
        "archived_requests": archived_requests,
        "active_request_files": active_request_files,
    }


def load_tab_content(request, tab_name):
    try:
        data = get_requests_data(request)
        
        data.update(
            {
                "user": request.user,
                "request": request,
            }
        )

        template_name = f"profile/{tab_name}.html"
        html = render_to_string(template_name, data, request=request)
        return JsonResponse({"html": html})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def reject_request(request, request_id):
    if request.method == "POST":
        try:
            req = Request.objects.get(id=request_id)
            if request.user == req.teacher_id.teacher_id:
                # Змінюємо статус (тема звільниться автоматично в моделі)
                req.request_status = "Відхилено"
                req.save()
                messages.success(request, "Запит успішно відхилено")
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"success": True})
                return redirect("profile")
        except Request.DoesNotExist:
            messages.error(request, "Запит не знайдено")
        except Exception as e:
            messages.error(request, f"Помилка при відхиленні запиту: {str(e)}")
    
    return redirect("profile")


class UploadFileView(View):
    def post(self, request, request_id):
        try:
            course_request = Request.objects.get(pk=request_id)
            
            if (
                request.user != course_request.student_id
                and request.user != course_request.teacher_id.teacher_id
            ):
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {"status": "error", "message": "Немає прав доступу"}, status=403
                    )
                return HttpResponseForbidden("Немає прав доступу")

            if course_request.request_status != "Активний":
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "status": "error",
                            "message": "Файли можна додавати тільки до активних запитів",
                        },
                        status=400,
                    )
                return HttpResponseBadRequest(
                    "Файли можна додавати тільки до активних запитів"
                )
            
            form = RequestFileForm(request.POST, request.FILES)
            if form.is_valid():
                file = form.save(commit=False)
                file.request = course_request
                file.uploaded_by = request.user
                
                latest_version = RequestFile.objects.filter(
                    request=course_request
                ).aggregate(Max("version"))["version__max"]
                file.version = (latest_version or 0) + 1
                
                file.save()
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"status": "success"})
                return redirect("profile")
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"status": "error", "message": "Помилка у формі"}, status=400
                )
            return HttpResponseBadRequest("Помилка у формі")
        except Request.DoesNotExist:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"status": "error", "message": "Запит не знайдено"}, status=404
                )
            return HttpResponseNotFound("Запит не знайдено")
        except Exception as e:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"status": "error", "message": str(e)}, status=500)
            return HttpResponseServerError(str(e))


class DeleteFileView(FileAccessMixin, View):
    def post(self, request, pk):
        try:
            file = RequestFile.objects.get(pk=pk)
            
            if not (
                request.user == file.uploaded_by
                or request.user == file.request.teacher_id.teacher_id
            ):
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "У вас немає прав для видалення цього файлу",
                    }
                )
            
            file.delete()
            return JsonResponse({"success": True, "message": "Файл успішно видалено"})
        except RequestFile.DoesNotExist:
            return JsonResponse({"success": False, "error": "Файл не знайдено"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})


class DownloadFileView(FileAccessMixin, View):
    def get(self, request, pk):
        try:
            file = RequestFile.objects.get(pk=pk)
            course_request = file.request
            
            if not (
                request.user == file.uploaded_by
                or request.user == course_request.student_id
                or request.user == course_request.teacher_id.teacher_id
            ):
                return HttpResponseForbidden("Немає прав доступу")
            
            response = FileResponse(file.file)
            response["Content-Disposition"] = (
                f'attachment; filename="{file.get_filename()}"'
            )
            return response
            
        except RequestFile.DoesNotExist:
            return HttpResponseNotFound("Файл не знайдено")


class AddCommentView(FileAccessMixin, View):
    def post(self, request, file_id):
        """Обробляє POST-запит для додавання коментаря до файлу"""
        try:
            file = RequestFile.objects.get(pk=file_id)
            course_request = file.request
            
            if (
                request.user != course_request.student_id
                and request.user != course_request.teacher_id.teacher_id
            ):
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {"success": False, "error": "Немає прав доступу"}, status=403
                    )
                else:
                    messages.error(
                        request, "Немає прав доступу для додавання коментаря"
                    )
                    return redirect("profile")

            text = request.POST.get("text")
            if not text and not request.FILES.get("attachment"):
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "Коментар не може бути порожнім, додайте текст або прикріпіть файл",
                        },
                        status=400,
                    )
                else:
                    messages.error(
                        request,
                        "Коментар не може бути порожнім, додайте текст або прикріпіть файл",
                    )
                    return redirect("profile")

            comment = FileComment(file=file, author=request.user, text=text or "")

            attachment = request.FILES.get("attachment")
            if attachment:
                comment.attachment = attachment
        
            comment.save()
                
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                response_data = {
                    "success": True,
                    "comment_id": comment.id,
                    "text": comment.text,
                    "author": comment.author.get_full_name(),
                    "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M"),
                }
                
                if comment.attachment:
                    response_data["attachment"] = {
                        "name": comment.get_attachment_filename(),
                        "url": comment.attachment.url,
                    }
                
                return JsonResponse(response_data)
            else:
                messages.success(request, "Коментар успішно додано")
                return redirect("profile")
            
        except RequestFile.DoesNotExist:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "error": "Файл не знайдено"}, status=404
                )
            else:
                messages.error(request, "Файл не знайдено")
                return redirect("profile")
                
        except Exception as e:
            import traceback

            traceback.print_exc()
            
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)}, status=500)
            else:
                messages.error(request, f"Помилка при додаванні коментаря: {str(e)}")
                return redirect("profile")


class DeleteCommentView(FileAccessMixin, View):
    def post(self, request, pk):
        try:
            comment = FileComment.objects.get(pk=pk)
            
            if request.user != comment.author:
                return JsonResponse(
                    {"success": False, "error": "Немає прав доступу"}, status=403
                )
            
            comment.delete()
            return JsonResponse({"success": True})
            
        except FileComment.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Коментар не знайдено"}, status=404
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
def add_comment(request, file_id):
    """Обробляє POST-запит для додавання коментаря до файлу"""
    try:
        file = RequestFile.objects.get(pk=file_id)
        course_request = file.request

        if (
            request.user != course_request.student_id
            and request.user != course_request.teacher_id.teacher_id
        ):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "error": "Немає прав доступу"}, status=403
                )
            else:
                messages.error(request, "Немає прав доступу для додавання коментаря")
                return redirect("profile")

        text = request.POST.get("text")
        if not text and not request.FILES.get("attachment"):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Коментар не може бути порожнім, додайте текст або прикріпіть файл",
                    },
                    status=400,
                )
            else:
                messages.error(
                    request,
                    "Коментар не може бути порожнім, додайте текст або прикріпіть файл",
                )
                return redirect("profile")

        comment = FileComment(file=file, author=request.user, text=text or "")

        attachment = request.FILES.get("attachment")
        if attachment:
            comment.attachment = attachment

        comment.save()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            response_data = {
                "success": True,
                "comment_id": comment.id,
                "text": comment.text,
                "author": comment.author.get_full_name(),
                "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M"),
            }

            if comment.attachment:
                response_data["attachment"] = {
                    "name": comment.get_attachment_filename(),
                    "url": comment.attachment.url,
                }

            return JsonResponse(response_data)
        else:
            messages.success(request, "Коментар успішно додано")
            return redirect("profile")

    except RequestFile.DoesNotExist:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "error": "Файл не знайдено"}, status=404
            )
        else:
            messages.error(request, "Файл не знайдено")
            return redirect("profile")

    except Exception as e:
        import traceback

        traceback.print_exc()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": str(e)}, status=500)
        else:
            messages.error(request, f"Помилка при додаванні коментаря: {str(e)}")
            return redirect("profile")


@login_required
def delete_comment(request, pk):
    comment = get_object_or_404(FileComment, pk=pk)
    if comment.author == request.user or request.user.is_staff:
        comment.delete()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error", "message": "Unauthorized"}, status=403)


@login_required
@require_POST
def delete_theme(request, theme_id):
    """
    Видаляє тему викладача з перевіркою можливості видалення
    """
    theme = get_object_or_404(
        TeacherTheme, id=theme_id, teacher_id__teacher_id=request.user
    )
    try:
        if not theme.can_be_deleted():
            return JsonResponse(
                {
                    "error": "Неможливо видалити тему, яка використовується в активних або очікуючих запитах"
                },
                status=400,
            )

        theme.delete(force=True)
        return JsonResponse({"success": True})

    except Exception as e:
        logger.error(f"Error deleting theme {theme_id}: {str(e)}")
        return JsonResponse(
            {"error": f"Помилка при видаленні теми: {str(e)}"}, status=500
        )

def home(request):
    faculty_announcements = []
    department_announcements = []

    if request.user.is_authenticated:
        faculty = request.user.get_faculty()
        department = request.user.get_department()

        # Факультетські оголошення
        if faculty:
            faculty_announcements = Announcement.objects.filter(
                author_type="faculty",
                author_faculty=faculty,
                is_active=True
            )

        # Кафедральні оголошення
        if department:
            department_announcements = Announcement.objects.filter(
                author_type="department",
                author_department=department,
                is_active=True
            )

    context = {
        "faculty_announcements": faculty_announcements,
        "department_announcements": department_announcements,
    }
    return render(request, "home.html", context)



class AutocompleteView(LoginRequiredMixin, View):
    """
    Універсальний автокомпліт для пошуку викладачів та тем
    """
    
    def get(self, request):
        query = request.GET.get("q", "").strip()
        results = []
        
        if not query or len(query) < 2:
            return JsonResponse(results, safe=False)
        
        try:
            # Пошук викладачів (тільки по іменах, без кафедр)
            teachers = OnlyTeacher.objects.select_related("teacher_id").filter(
                Q(teacher_id__first_name__icontains=query) |
                Q(teacher_id__last_name__icontains=query) |
                Q(teacher_id__patronymic__icontains=query)
            )[:5]
            
            for teacher in teachers:
                results.append({
                    "type": "teacher",
                    "id": teacher.pk,
                    "label": f"👨‍🏫 {teacher.teacher_id.first_name} {teacher.teacher_id.last_name}",
                    "description": f"{teacher.academic_level} • {teacher.teacher_id.department}",
                    "url": "#"  # Не потрібен URL, фільтрування буде на тій же сторінці
                })
            
            # Пошук тем
            themes = TeacherTheme.objects.select_related("teacher_id__teacher_id").filter(
                Q(theme__icontains=query) | Q(theme_description__icontains=query),
                is_active=True,
                is_deleted=False
            )[:5]
            
            for theme in themes:
                results.append({
                    "type": "theme", 
                    "id": theme.pk,
                    "label": f"📚 {theme.theme}",
                    "description": f"Викладач: {theme.teacher_id.teacher_id.first_name} {theme.teacher_id.teacher_id.last_name}",
                    "url": "#"  # Не потрібен URL, фільтрування буде на тій же сторінці
                })
                
        except Exception as e:
            logger.error(f"Error in autocomplete search: {str(e)}")
            return JsonResponse({"error": "Помилка пошуку"}, status=500)
        
        return JsonResponse(results, safe=False)


class ThemesAPIView(LoginRequiredMixin, View):
    """
    API view для отримання списку тем у JSON форматі
    """
    
    def get(self, request):
        try:
            query = request.GET.get('q', '').strip()
            user = request.user
            
            # Базовий набір тем (активні, не видалені, не зайняті)
            themes_qs = TeacherTheme.objects.select_related('teacher_id__teacher_id').filter(
                is_active=True,
                is_deleted=False,
                teacher_id__isnull=False,
                teacher_id__teacher_id__isnull=False,
            )
            
            # Показуємо лише доступні теми (не зайняті)
            if hasattr(TeacherTheme, 'is_occupied'):
                themes_qs = themes_qs.filter(is_occupied=False)
            
            # Обмеження доступу для студента: показувати лише теми викладачів,
            # у яких є вільні слоти для потоку студента
            if user.is_authenticated and getattr(user, 'role', None) == 'Студент':
                teachers = OnlyTeacher.objects.select_related('teacher_id').all()
                
                # Фільтр кафедри для 3+ курсу або магістрів (аналогічно TeachersListView)
                course = None
                is_master = 'М' in user.academic_group.upper() if getattr(user, 'academic_group', '') else False
                if getattr(user, 'academic_group', None):
                    match = re.match(r"^ФЕ[СМЛПІ]-(\d)", user.academic_group)
                    if match:
                        course = int(match.group(1))
                if getattr(user, 'department', None) and ((course and course >= 3) or is_master):
                    teachers = teachers.filter(teacher_id__department__iexact=user.department.strip())
                
                # Витягуємо потік студента
                slots = Slot.filter_by_available_slots()
                is_matched = False
                match = re.match(r"([А-ЯІЇЄҐ]+)-(\d)", getattr(user, 'academic_group', '') )
                if match:
                    user_stream = match.group(1) + '-' + match.group(2) + ('м' if is_master else '')
                    slots = slots.filter(stream_id__stream_code__iexact=user_stream)
                    is_matched = True
                
                # Залишаємо лише викладачів з вільними слотами у відповідному потоці
                teacher_ids_with_slots = slots.values_list('teacher_id', flat=True).distinct()
                allowed_teacher_ids = teachers.filter(pk__in=teacher_ids_with_slots).values_list('pk', flat=True)
                themes_qs = themes_qs.filter(teacher_id__in=allowed_teacher_ids)
            
            # Пошуковий запит
            if query:
                themes_qs = themes_qs.filter(
                    Q(theme__icontains=query) |
                    Q(theme_description__icontains=query) |
                    Q(teacher_id__teacher_id__first_name__icontains=query) |
                    Q(teacher_id__teacher_id__last_name__icontains=query)
                )
            
            themes_qs = themes_qs.order_by('theme')
            
            themes_data = []
            for theme in themes_qs:
                themes_data.append({
                    'id': theme.id,
                    'theme': theme.theme,
                    'theme_description': theme.theme_description or '',
                    'teacher_name': theme.teacher_id.teacher_id.get_full_name(),
                    'teacher_id': theme.teacher_id.teacher_id.id,
                    'department': theme.teacher_id.teacher_id.department or '',
                })
            
            return JsonResponse(themes_data, safe=False)
            
        except Exception as e:
            logger.error(f"Error in ThemesAPIView: {str(e)}")
            return JsonResponse({"error": "Помилка завантаження тем"}, status=500)


class ThemesListView(LoginRequiredMixin, ListView):
    """
    Відображає список всіх доступних тем
    """
    model = TeacherTheme
    template_name = "catalog/themes_list.html"
    context_object_name = "themes"
    paginate_by = 20
    
    def get_queryset(self):
        return TeacherTheme.objects.select_related('teacher_id__teacher_id').filter(
            is_active=True,
            is_deleted=False,
            teacher_id__isnull=False,
            teacher_id__teacher_id__isnull=False
        ).order_by('theme')


class ThemeTeachersView(LoginRequiredMixin, View):
    """
    Повертає список викладачів, які ведуть конкретну тему
    """
    
    def get(self, request, theme_id):
        try:
            # Знаходимо тему
            theme = get_object_or_404(
                TeacherTheme.objects.select_related('teacher_id'),
                id=theme_id,
                is_active=True,
                is_deleted=False
            )
            
            # Знаходимо всіх викладачів з такою ж темою
            similar_themes = TeacherTheme.objects.select_related('teacher_id').filter(
                theme__iexact=theme.theme,
                is_active=True,
                is_deleted=False
            )
            
            # Повертаємо список ID викладачів
            teacher_ids = [t.teacher_id.pk for t in similar_themes]
            
            return JsonResponse(teacher_ids, safe=False)
            
        except Exception as e:
            logger.error(f"Error getting teachers for theme {theme_id}: {str(e)}")
            return JsonResponse({"error": "Помилка отримання викладачів"}, status=500)
