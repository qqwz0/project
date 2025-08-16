import json
import logging
from functools import wraps
from io import BytesIO
from urllib.parse import urlencode, parse_qs
from dotenv import load_dotenv
import os
import re

import requests
from PIL import Image
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpRequest, JsonResponse, HttpResponseNotAllowed, HttpResponseNotFound, HttpResponseServerError
from django.shortcuts import redirect, render, get_object_or_404
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.urls import reverse
from django.template.loader import render_to_string
from django.views import View
from django.db.models import F
from django.db.models import Q


from cloudinary_storage.storage import MediaCloudinaryStorage

from .forms import RegistrationForm, TeacherProfileForm, StudentProfileForm, ProfilePictureUploadForm, CropProfilePictureForm
from .models import CustomUser
from apps.catalog.models import (
    OnlyTeacher,
    OnlyStudent,
    Stream,
    Slot,
    Request,
    TeacherTheme,
    RequestFile,
    FileComment,
    StudentTheme
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Constants
MICROSOFT_AUTH_URL = f"{settings.MICROSOFT_AUTHORITY}/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = f"{settings.MICROSOFT_AUTHORITY}/oauth2/v2.0/token"
MICROSOFT_GRAPH_ME_ENDPOINT = f"{settings.MICROSOFT_GRAPH_ENDPOINT}/me"

def own_profile_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        profile_id = kwargs.get('profile_id') or request.user.id
        if request.user.id != profile_id:
            messages.error(request, "Ви можете редагувати тільки власний профіль")
            return redirect('profile')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def microsoft_register(request):
    """
    Description:
        Handle the registration process using Microsoft OAuth.
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: The HTTP response object. Redirects to Microsoft OAuth if the form is valid, 
                      otherwise renders the registration form with errors.
    """
    logger.debug("Request method: %s", request.method)
    if request.method == "POST":
        logger.debug("POST request received")
        form = RegistrationForm(request.POST)
        if form.is_valid():
            logger.debug("Form is valid")
            # Store form data in session
            request.session["role"] = form.cleaned_data["role"]
            request.session["group"] = form.cleaned_data.get("group")
            request.session["department"] = form.cleaned_data.get("department")

            CSRF_STATE = get_random_string(32)
            request.session['csrf_state'] = CSRF_STATE
            
            # Redirect to Microsoft OAuth
            params = {
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "response_type": "code",
                "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
                "response_mode": "query",
                "scope": " ".join(settings.MICROSOFT_SCOPES),
                "state": urlencode({"action": 'register', "csrf": CSRF_STATE}),
            }
            authorization_url = f"{MICROSOFT_AUTH_URL}?{urlencode(params)}"
            logger.info("Redirecting to Microsoft OAuth: %s", authorization_url)
            return redirect(authorization_url)
        else:
            logger.error("Form errors: %s", form.errors)
            return render(request, "auth/register.html", {"form": form, "errors": form.errors})
    else:
        logger.debug("GET request received")
        form = RegistrationForm()

    return render(request, "auth/register.html", {"form": form})

def microsoft_login(request):
    """
    This view handles the GET request to initiate the Microsoft OAuth login process.
    If the "redirect" query parameter is not present, it renders a login page.
    Otherwise, it generates a CSRF state token, stores it in the session, and redirects
    the user to Microsoft's OAuth authorization URL.
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Renders the login page if "redirect" is not in the query parameters.
                      Redirects to Microsoft's OAuth authorization URL if "redirect" is present.
    """
    logger.debug("Starting Microsoft login process.")

    if request.method == "GET":
        logger.debug("GET request received for Microsoft login.")

        # If the request is to render the login page
        if not request.GET.get("redirect"):
            logger.debug("Rendering login page before redirecting to Microsoft.")
            return render(request, 'auth/login.html')  # Update with the correct template path
        
        CSRF_STATE = get_random_string(32)
        request.session['csrf_state'] = CSRF_STATE

        # Redirect to Microsoft's OAuth page if "redirect" is set in the query params
        logger.info("Redirecting to Microsoft login page.")
        params = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
            "response_mode": "query",
            "scope": " ".join(settings.MICROSOFT_SCOPES),
            "state": urlencode({"action": 'login', "csrf": CSRF_STATE}),
            "redirect": request.GET.get("redirect", "")  # Preserve the redirect URL if provided
        }
        authorization_url = f"{MICROSOFT_AUTH_URL}?{urlencode(params)}"
        logger.info("Authorization URL: %s", authorization_url)
        return redirect(authorization_url)
    return HttpResponseNotAllowed(['GET'])

def microsoft_callback(request):
    """
    Handles the callback from Microsoft's OAuth2 authentication.
    This view function processes the authorization code and state parameters
    returned by Microsoft's OAuth2 authentication flow. It validates the state
    parameter to prevent CSRF attacks and then delegates the handling to either
    the registration or login callback based on the action specified in the state.
    Args:
        request (HttpRequest): The HTTP request object containing the authorization
                               code and state parameters.
    Returns:
        HttpResponse: A redirect to the appropriate page based on the outcome of
                      the callback handling.
    Raises:
        Exception: If an unexpected error occurs during the processing of the callback.
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(['GET'])
    code = request.GET.get("code")
    state = request.GET.get("state")

    logger.error(f"[CSRF DEBUG] session.csrf_state={request.session.get('csrf_state')}, state={state}")

    if not code or not state:
        logger.error("Authorization code or state parameter is missing.")
        messages.error(request, "Відсутній код авторизації або параметр стану.")
        return redirect("login")

    try:
        logger.debug("Incoming state: %s", state)
        logger.debug("Session CSRF state: %s", request.session.get('csrf_state'))

        # Parse state
        state_data = parse_qs(state)
        logger.debug("Parsed state data: %s", state_data)

        action = state_data.get("action", [None])[0]
        received_csrf = state_data.get("csrf", [None])[0]

        # Check CSRF state
        if received_csrf != request.session.get('csrf_state'):
            logger.error("CSRF check failed. Received: %s, Expected: %s",
                         received_csrf, request.session.get('csrf_state'))
            messages.error(request, "Недійсний параметр стану.")
            return redirect("login")

        # Handle actions
        if action == "register":
            return handle_registration_callback(request, code)
        elif action == "login":
            return handle_login_callback(request, code)
        else:
            logger.error("Invalid action in state parameter: %s", action)
            messages.error(request, "Недійсна дія в параметрі стану.")
            return redirect("login")

    except Exception as e:
        logger.error("Unexpected error in microsoft_callback: %s", e, exc_info=True)
        messages.error(request, "Сталася несподівана помилка.")
        return redirect("login")

def handle_registration_callback(request, code):
    """
    This function processes the OAuth callback from Microsoft during user registration.
    It exchanges the authorization code for an access token, fetches user information
    from Microsoft Graph, and registers the user in the system.
    Args:
        request (HttpRequest): The HTTP request object.
        code (str): The authorization code received from Microsoft.
    Returns:
        HttpResponse: A redirect response to the appropriate page based on the outcome.
    Raises:
        ValidationError: If there is a validation error during user registration.
        requests.exceptions.RequestException: If there is an error during the OAuth callback process.
    """
    logger.debug("Handling registration callback.")

    data = {
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "scope": " ".join(settings.MICROSOFT_SCOPES),
        "code": code,
        "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
        "grant_type": "authorization_code",
        "client_secret": settings.MICROSOFT_CLIENT_SECRET,
        "state": urlencode({"action": 'login', "csrf": request.session.get('csrf_state')}),
    }

    try:
        # Request access token
        logger.debug("Requesting access token from Microsoft.")
        token_response = requests.post(MICROSOFT_TOKEN_URL, data=data)
        token_response.raise_for_status()
        tokens = token_response.json()
        access_token = tokens.get("access_token")

        if not access_token:
            logger.error("Failed to obtain access token.")
            messages.error(request, "Не вдалося отримати токен доступу.")
            return redirect('register')

        logger.debug("Access token obtained.")

        # Fetch user info
        headers = {"Authorization": f"Bearer {access_token}"}
        logger.debug("Fetching user info from Microsoft Graph.")
        user_info = requests.get(MICROSOFT_GRAPH_ME_ENDPOINT, headers=headers).json()

        # Extract user details
        email = user_info.get("mail") or user_info.get("userPrincipalName")
        first_name = user_info.get("givenName", "")
        last_name = user_info.get("surname", "")
        job_title = user_info.get("jobTitle", "Not specified")

        derived_role = "Студент" if "Student" in job_title else "Викладач"

        submitted_role = request.session.get("role")
        group = request.session.get("group")
        department = request.session.get("department")

        if submitted_role != derived_role:
            logger.error("Role mismatch. Submitted: %s, Derived: %s", submitted_role, derived_role)
            messages.error(request, "Будь ласка, вкажіть правильну роль.")
            return redirect('register')

        # Check if user already exists
        user, created = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "password": make_password(None),
                "is_active": True,
                "role": derived_role,
                "academic_group": group if derived_role == "Студент" else None,
                "department": department if derived_role == "Викладач" else None,
            },
        )

        if not created:
            logger.error("User already registered: %s", email)
            messages.error(request, "Користувач вже зареєстрований.")
            return redirect('register')

        if created:
            logger.info("New user registered: %s", email)
            # Створюємо профіль в залежності від ролі
            if derived_role == "Студент":
                # Визначаємо курс з номера групи
                course = 1  # Значення за замовчуванням
                if group:
                    match = re.match(r'^ФЕ[ЇСМЛП]-(\d)', group)
                    if match:
                        course = int(match.group(1))
                
                OnlyStudent.objects.create(
                    student_id=user,
                    course=course,  # Використовуємо визначений курс
                    speciality="Не вказано"  # Значення за замовчуванням
                )
            elif derived_role == "Викладач":
                OnlyTeacher.objects.create(
                    teacher_id=user,
                    academic_level="Асистент"  # Значення за замовчуванням
                )

        # Redirect user to the desired page after registration
        messages.success(request, "Успішно зареєстровано! Будь ласка, увійдіть.")
        return redirect("login") 

    except ValidationError as e:
        error_message = str(e)
        logger.error("Validation error during registration: %s", error_message)
        messages.error(request, error_message)
        return redirect('register')
    except requests.exceptions.RequestException as e:
        logger.error("Error during Microsoft OAuth callback: %s", e)
        messages.error(request, "Не вдалося завершити автентифікацію.")
        return redirect('register')

def handle_login_callback(request, code):

    """
    This function processes the OAuth callback from Microsoft, retrieves the access token,
    fetches user information from Microsoft Graph, and logs in the user if they exist in the database.
    Args:
        request (HttpRequest): The HTTP request object containing the callback data.
        code (str): The authorization code provided by Microsoft.
    Returns:
        HttpResponse: A redirect response to the appropriate page based on the outcome of the login process.
    Raises:
        ValidationError: If there is a validation error during the login process.
        requests.exceptions.RequestException: If there is an error during the HTTP requests to Microsoft.
    Handle Microsoft's OAuth login callback.
    """
    logger.debug("Handling callback for Microsoft login.")
    state = request.GET.get("state")

    if not code or not state:
        logger.error("Authorization code or state not provided.")
        messages.error(request, "Код авторизації або стан не надано.")
        return redirect("login")

    logger.debug("Authorization code: %s", code)
    logger.debug("State: %s", state)

    data = {
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "scope": " ".join(settings.MICROSOFT_SCOPES),
        "code": code,
        "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
        "grant_type": "authorization_code",
        "client_secret": settings.MICROSOFT_CLIENT_SECRET,
    }

    try:
        # Request access token
        logger.debug("Requesting access token from Microsoft.")
        token_response = requests.post(MICROSOFT_TOKEN_URL, data=data)
        token_response.raise_for_status()
        tokens = token_response.json()
        access_token = tokens.get("access_token")

        if not access_token:
            logger.error("Failed to obtain access token.")
            messages.error(request, "Не вдалося отримати токен доступу.")
            return redirect("login")

        logger.debug("Access token obtained.")

        # Fetch user info
        headers = {"Authorization": f"Bearer {access_token}"}
        logger.debug("Fetching user info from Microsoft Graph.")
        user_info = requests.get(MICROSOFT_GRAPH_ME_ENDPOINT, headers=headers).json()

        # Extract user details
        email = user_info.get("mail") or user_info.get("userPrincipalName")
        if not email:
            logger.error("Email not found in Microsoft account.")
            messages.error(request, "Електронна пошта не знайдена в обліковому записі Microsoft.")
            return redirect("login")

        logger.debug("User email: %s", email)

        # Check if the user exists
        try:
            logger.debug("Checking if user exists in the database.")
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            logger.error("User with email %s not found.", email)
            messages.error(request, "Користувача з цією електронною поштою не знайдено.")
            return redirect("login")

        # Log in the user
        logger.debug("Logging in the user: %s", email)
        auth_login(request, user)
        update_last_login(None, user)  # Update the last login timestamp

        logger.info("User logged in: %s", email)

        # Redirect to the desired page after login
        return redirect("profile")  # Change 'profile' to your desired default page

    except ValidationError as e:
        error_message = str(e)
        logger.error("Validation error during login: %s", error_message)
        messages.error(request, error_message)
        return redirect("login")
    except requests.exceptions.RequestException as e:
        logger.error("Error during Microsoft OAuth login: %s", e)
        messages.error(request, "Не вдалося завершити автентифікацію.")
        return redirect("login")
    
def fake_login(request):
    email = "VYKLADACH.VYKLADACH@lnu.edu.ua"
    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        user = CustomUser.objects.create(
            email=email,
            first_name="Викладач",
            last_name="Тестовий",
            patronymic="Петрович",
            role="Викладач",
            department="Системного проектування",
            is_active=True,
            password=make_password("fake_password")
        )
    # Використовуємо get_or_create для OnlyTeacher
    OnlyTeacher.objects.get_or_create(
            teacher_id=user,
        defaults={
            "academic_level": "Доцент",
            "additional_email": "teacher.test@lnu.edu.ua",
            "phone_number": "+380991234567"
        }
    )
    auth_login(request, user)
    return redirect("profile")

def fake_student_login(request):
    email = "STUDENT.STUDENT@lnu.edu.ua"
    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        user = CustomUser.objects.create(
            email=email,
            first_name="Студент",
            last_name="Тестовий",
            patronymic="Іванович",
            role="Студент",
            academic_group="ФЕС-21",
            is_active=True,
            password=make_password("fake_password")
        )
    OnlyStudent.objects.get_or_create(
        student_id=user,
        defaults={
            "speciality": "Не вказано",
            "course": 2,
            "additional_email": "student.test@lnu.edu.ua",
            "phone_number": "+380991234568"
        }
    )
    auth_login(request, user)
    return redirect("profile")

def fake_student_login_2(request):
    email = "STUDENT2.STUDENT2@lnu.edu.ua"
    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        user = CustomUser.objects.create(
            email=email,
            first_name="Студент",
            last_name="Тестовий",
            patronymic="Петрович",
            role="Студент",
            academic_group="ФЕС-22",
            is_active=True,
            password=make_password("fake_password")
        )
    OnlyStudent.objects.get_or_create(
        student_id=user,
        defaults={
            "speciality": "Не вказано",
            "course": 3,
            "additional_email": "student2.test@lnu.edu.ua",
            "phone_number": "+380991234569"
        }
    )
    auth_login(request, user)
    return redirect("profile")

@login_required
def profile(request: HttpRequest, user_id=None):
    """
    Display user profile with their requests and themes.
    If user_id is provided, display that user's profile, otherwise display the logged-in user's profile.
    """
    if user_id:
        user_profile = get_object_or_404(CustomUser, id=user_id)
        is_own_profile = request.user.id == user_id
    else:
        user_profile = request.user
        is_own_profile = True

    context = {
        'user_profile': user_profile,
        'is_own_profile': is_own_profile,
    }

    # Add role-specific data
    if user_profile.role == 'Викладач':
        teacher_profile = get_object_or_404(OnlyTeacher, teacher_id=user_profile)
        active_requests = Request.objects.select_related(
            'student_id', 'teacher_id', 'teacher_theme', 'slot'
        ).prefetch_related('student_themes', 'files').filter(
            teacher_id__teacher_id=user_profile,
            request_status='Активний'
        )
        
        # Get files for active requests
        active_request_files = {}
        for req in active_requests:
            files = RequestFile.objects.filter(request=req).select_related('uploaded_by')
            active_request_files[str(req.id)] = list(files)
        
        # Додаю accepted_requests
        accepted_requests = Request.objects.select_related(
            'student_id', 'teacher_id', 'teacher_theme', 'slot'
        ).prefetch_related('student_themes', 'files').filter(
            teacher_id__teacher_id=user_profile,
            request_status__in=['Активний', 'Завершено']
        )
        
        # Додаю rejected_requests
        rejected_requests = Request.objects.select_related(
            'student_id', 'teacher_id', 'teacher_theme', 'slot'
        ).prefetch_related('student_themes', 'files').filter(
            teacher_id__teacher_id=user_profile,
            request_status='Відхилено'
        )
        
        context.update({
            'teacher_profile': teacher_profile,

            # Групуємо теми викладача за потоками
            'themes_by_stream': _group_teacher_themes_by_stream(teacher_profile),

            'slots': Slot.objects.filter(teacher_id=teacher_profile).annotate(
                available=F('quota') - F('occupied')
            ),
            'pending_requests': Request.objects.select_related(
                'student_id', 'teacher_id', 'teacher_theme', 'slot'
            ).prefetch_related('student_themes', 'files').filter(
                teacher_id__teacher_id=user_profile,
                request_status='Очікує'
            ),
            'active_requests': active_requests,
            'active_request_files': active_request_files,
            'archived_requests': Request.objects.select_related(
                'student_id', 'teacher_id', 'teacher_theme', 'slot'
            ).prefetch_related('student_themes', 'files').filter(
                teacher_id__teacher_id=user_profile,
                request_status='Завершено'
            ),
            'accepted_requests': accepted_requests,
            'rejected_requests': rejected_requests,
        })
    else:  # Student
        # Get or create student profile
        student_profile = get_object_or_404(OnlyStudent, student_id=user_profile)
        
        # Get all requests for the student
        all_requests = Request.objects.select_related(
            'student_id', 'teacher_id', 'teacher_theme', 'slot'
        ).prefetch_related('student_themes').filter(
            student_id=user_profile
        )
        
        # Активні та архівні запити для вкладок
        active_requests = all_requests.filter(request_status='Активний')
        archived_requests = all_requests.filter(request_status='Завершено')
        
        # Get all active requests with files
        active_request_files = {}
        for req in active_requests:
            files = RequestFile.objects.filter(request=req).select_related('uploaded_by')
            active_request_files[str(req.id)] = list(files)
        
        context.update({
            'student_profile': student_profile,
            'all_requests': all_requests,
            'has_rejected': all_requests.filter(request_status='Відхилено').exists(),
            'has_pending': all_requests.filter(request_status='Очікує').exists(),
            'active_requests': active_requests,
            'archived_requests': archived_requests,
            'active_request_files': active_request_files,
        })
        # Додаємо номер курсу для шаблону
        student_course = None
        if user_profile.academic_group:
            import re
            match = re.match(r'^ФЕ[ЇСМЛП]-(\d)', user_profile.academic_group)
            if match:
                student_course = int(match.group(1))
        context['student_course'] = student_course

    return render(request, 'profile/profile.html', context)

@login_required
@transaction.atomic
def approve_request(request, request_id):
    """
    Approve a request and update its status to 'Активний'.
    Automatically cancel all other pending requests from the same student.
    """
    if request.method == 'POST':
        try:
            # Use select_for_update to prevent race conditions
            req = Request.objects.select_for_update().get(id=request_id)
            
            # Add debugging logs
            logger.debug(f"Request ID: {req.id}, Student: {req.student_id}, Teacher: {req.teacher_id}")
            logger.debug(f"Current user: {request.user.id} - {request.user}")
            logger.debug(f"Teacher user: {req.teacher_id.teacher_id.id} - {req.teacher_id.teacher_id}")
            
            # Check if the user is the teacher who received the request - use more reliable comparison
            if req.teacher_id.teacher_id == request.user:
                student_id = req.student_id
                
                # Cancel all other pending requests from this student
                other_pending_requests = Request.objects.filter(
                    student_id=student_id,
                    request_status='Очікує'
                ).exclude(id=req.id)
                
                cancelled_count = other_pending_requests.update(
                    request_status='Відхилено', 
                    rejected_reason='Автоматично скасовано через прийняття іншого запиту'
                )
                
                # Accept the chosen request
                req.request_status = 'Активний'
                req.save()
                
                logger.info(f"Request {req.id} approved. {cancelled_count} other pending requests cancelled for student {student_id.id}")
                
                success_message = f'Запит успішно підтверджено. {cancelled_count} інших очікуючих запитів автоматично скасовано.' if cancelled_count > 0 else 'Запит успішно підтверджено.'
                messages.success(request, success_message)
                
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True})
                return redirect('profile')
            else:
                logger.warning(f"User {request.user.id} attempted to approve request {request_id} belonging to teacher {req.teacher_id.teacher_id.id}")
                messages.error(request, 'У вас немає прав для підтвердження цього запиту')
        except Request.DoesNotExist:
            messages.error(request, 'Запит не знайдено')
        except Exception as e:
            logger.exception(f"Error approving request {request_id}: {str(e)}")
            messages.error(request, f'Помилка при підтвердженні запиту: {str(e)}')
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Помилка при обробці запиту'})
    return redirect('profile')

@login_required
def reject_request(request, request_id):
    """
    Reject a request and update its status to 'Відхилено'.
    """
    if request.method == 'POST':
        try:
            req = Request.objects.get(id=request_id)
            logger.debug(f"Reject Request ID: {req.id}, Student: {req.student_id}, Teacher: {req.teacher_id}")
            logger.debug(f"Current user: {request.user.id} - {request.user}")
            logger.debug(f"Teacher user: {req.teacher_id.teacher_id.id} - {req.teacher_id.teacher_id}")

            # Check if the user is the teacher who received the request
            if req.teacher_id.teacher_id == request.user:
                # --- FIX: Read reason from JSON if POST is empty ---
                reason = request.POST.get('rejectReason')
                if reason is None and request.content_type == 'application/json':
                    try:
                        data = json.loads(request.body.decode('utf-8'))
                        reason = data.get('rejectReason')
                    except Exception as e:
                        logger.error(f"Error parsing JSON body: {e}")
                        reason = None
                        
                req.request_status = 'Відхилено'
                req.rejected_reason = reason if reason else 'Викладач не вказав причину відмови'
                req.save()

                if req.teacher_theme:
                    req.teacher_theme.is_occupied = False
                    req.teacher_theme.save()

                messages.success(request, 'Запит успішно відхилено')

                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True})
                return redirect('profile')
            else:
                logger.warning(f"User {request.user.id} attempted to reject request {request_id} belonging to teacher {req.teacher_id.teacher_id.id}")
                messages.error(request, 'У вас немає прав для відхилення цього запиту')
        except Request.DoesNotExist:
            messages.error(request, 'Запит не знайдено')
        except Exception as e:
            logger.exception(f"Error rejecting request {request_id}: {str(e)}")
            messages.error(request, f'Помилка при відхиленні запиту: {str(e)}')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Помилка при обробці запиту'})
    return redirect('profile')

@login_required
def update_profile_picture(request):
    if request.method == 'POST':
        form = ProfilePictureUploadForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            logger.debug("Profile picture form is valid.")
            try:
                form.save()
                return redirect('crop_profile_picture')  # Redirect to crop profile picture view
            except Exception as e:
                logger.error(f"Error saving profile picture for user {request.user.id}: {str(e)}")
                messages.error(request, "Error saving profile picture.")
                return redirect('profile')
        else:
            logger.warning(f"Profile picture form is invalid: {form.errors}")
            messages.error(request, "Form is invalid.")
            return redirect('profile')
    else:
        form = ProfilePictureUploadForm(instance=request.user)
    
    context = {
        'form': form,
        'user_profile': request.user,
        'is_own_profile': True,
    }
    return render(request, 'profile/profile.html', context)

@login_required
def crop_profile_picture(request):
    if request.method == 'POST':
        crop_form = CropProfilePictureForm(request.POST)
        if crop_form.is_valid():
            x = crop_form.cleaned_data['x']
            y = crop_form.cleaned_data['y']
            width = crop_form.cleaned_data['width']
            height = crop_form.cleaned_data['height']
            try:
                # Use the uploaded file if available
                if 'profile_picture' in request.FILES:
                    image_file = request.FILES['profile_picture']
                    image = Image.open(image_file).convert('RGB')
                else:
                    return JsonResponse({'success': False, 'error': 'No image file provided.'})

                # Crop and resize the image
                cropped_image = image.crop((x, y, x + width, y + height))
                cropped_image = cropped_image.resize((240, 240), Image.LANCZOS)

                # Save the cropped image to an in-memory file
                img_io = BytesIO()
                cropped_image.save(img_io, format='JPEG', quality=90)
                img_content = ContentFile(img_io.getvalue())

                # --- FORCE CLOUDINARY UPLOAD (DIAGNOSTIC STEP) ---
                user = request.user
                storage = MediaCloudinaryStorage()
                file_name = f"profile_pics/profile_{user.id}.jpg"
                
                # Delete the old file from Cloudinary if it exists, to prevent duplicates
                if storage.exists(file_name):
                    storage.delete(file_name)
                
                # Save the new file directly to Cloudinary
                saved_file_name = storage.save(file_name, img_content)
                
                # Manually update the user's model field with the path returned by Cloudinary
                user.profile_picture.name = saved_file_name
                user.save(update_fields=['profile_picture'])
                
                # Get the final URL directly from the storage
                new_url = storage.url(saved_file_name)
                # --- END OF DIAGNOSTIC STEP ---

                logger.debug(f"Forced Cloudinary upload successful for user {user.id}. URL: {new_url}")
                return JsonResponse({
                    'success': True, 
                    'new_profile_picture_url': new_url,
                })
            except Exception as e:
                logger.exception(f"Error during forced Cloudinary upload for user {request.user.id}: {str(e)}")
                return JsonResponse({'success': False, 'error': 'Error processing the image.'})
        else:
            logger.warning(f"Crop form is invalid for user {request.user.id}: {crop_form.errors}")
            return JsonResponse({'success': False, 'error': 'Crop form is invalid.'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

def logout_view(request):
    logout(request)
    logger.info("User logged out.")
    return redirect('login')

@login_required
@own_profile_required
def teacher_profile_edit(request):
    if request.user.role != 'Викладач':
        messages.error(request, "Доступ заборонено")
        return redirect('profile')
        
    teacher_profile, created = OnlyTeacher.objects.get_or_create(
        teacher_id=request.user,
        defaults={
            'position': 'Не вказано',
            'academic_level': 'Аспірант'
        }
    )
    
    if request.method == 'POST':
        form = TeacherProfileForm(request.POST, instance=teacher_profile, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Update user fields
                    request.user.first_name = form.cleaned_data['first_name']
                    request.user.last_name = form.cleaned_data['last_name']
                    request.user.patronymic = form.cleaned_data['patronymic']
                    request.user.department = form.cleaned_data['department']
                    request.user.save()
                    
                    form.save()
                    
                    messages.success(request, "Профіль успішно оновлено")
                    
                    # Handle themes
                    new_themes_data = request.POST.get('themes_data', '[]')
                    logger.debug(f"Themes data received: {new_themes_data}")
                    
                    # Тільки обробляємо теми якщо дані дійсно передані і не порожні
                    if new_themes_data and new_themes_data != '[]':
                        try:
                            new_themes = json.loads(new_themes_data)
                            new_theme_texts = {item['theme'] for item in new_themes}
                            
                            existing_themes = TeacherTheme.objects.filter(teacher_id=teacher_profile)
                            
                            # Find themes to remove
                            for theme in existing_themes:
                                if theme.theme not in new_theme_texts:
                                    # Check if theme is in an active or pending request
                                    is_in_use = Request.objects.filter(
                                        Q(teacher_theme=theme) | Q(approved_student_theme__theme=theme.theme),
                                        request_status__in=['Активний', 'Очікує']
                                    ).exists()

                                    if is_in_use:
                                        error_message = f"Неможливо видалити тему '{theme.theme}', оскільки вона використовується в активному або очікуючому запиті."
                                        logger.warning(f"User {request.user.id} failed to delete theme '{theme.theme}' as it is in use.")
                                        return JsonResponse({'success': False, 'message': error_message}, status=409)
                                    
                                    # Soft delete if not in use
                                    theme.is_deleted = True
                                    theme.save()

                            # Add or update themes
                            for theme_data in new_themes:
                                theme_text = theme_data.get('theme', '').strip()
                                if theme_text:
                                    theme_obj, created = TeacherTheme.objects.update_or_create(
                                        teacher_id=teacher_profile,
                                        theme=theme_text,
                                        defaults={
                                            'theme_description': theme_data.get('description', ''),
                                            'is_deleted': False # Ensure it's active
                                        }
                                    )
                        
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON Decode Error: {str(e)} - Data: {new_themes_data}")
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({
                                    'success': False,
                                    'message': 'Помилка при збереженні тем'
                                }, status=400)
                            messages.error(request, "Помилка при збереженні тем")
                    
                    messages.success(request, "Профіль успішно оновлено")
                    
                    # Return JSON response for AJAX requests without redirect
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Профіль успішно оновлено'
                        })
                    
                    # For regular requests, stay on the same page
                    return render(request, 'profile/teacher_edit.html', {
                        'form': form,
                        'existing_themes': TeacherTheme.objects.filter(teacher_id=teacher_profile, is_deleted=False),
                        'slots': Slot.objects.filter(teacher_id=teacher_profile),
                        'available_streams': Stream.objects.exclude(
                            id__in=Slot.objects.filter(teacher_id=teacher_profile).values_list('stream_id_id', flat=True)
                        ),
                        'all_streams': Stream.objects.all(),
                        'user': request.user,
                        'user_profile': request.user
                    })
            except Exception as e:
                logger.error(f"Error processing profile: {str(e)}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f"Помилка при збереженні профілю: {str(e)}"
                    }, status=400)
                messages.error(request, f"Помилка при збереженні профілю: {str(e)}")
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': dict(form.errors.items())
                }, status=400)
            messages.error(request, "Помилка при збереженні профілю")

    else:
        form = TeacherProfileForm(instance=teacher_profile, user=request.user)
    
    existing_themes = TeacherTheme.objects.filter(teacher_id=teacher_profile, is_deleted=False)
    slots = Slot.objects.filter(teacher_id=teacher_profile)
    existing_stream_ids = slots.values_list('stream_id_id', flat=True)
    available_streams = Stream.objects.exclude(id__in=existing_stream_ids)

    return render(request, 'profile/teacher_edit.html', {
        'form': form,
        'existing_themes': existing_themes,
        'slots': slots,
        'available_streams': available_streams,
        'all_streams': Stream.objects.all(),  # Всі потоки для селектора в темах
        'user': request.user,
        'user_profile': request.user
    })

def teacher_requests(request):
    return render(request, 'profile/requests.html', {
        'message': 'У вас немає нових запитів.'
    })

@login_required
@own_profile_required
def student_profile_edit(request):
    if request.user.role != 'Студент':
        messages.error(request, "Доступ заборонено")
        return redirect('profile')
        
    student_profile, created = OnlyStudent.objects.get_or_create(
        student_id=request.user,
        defaults={
            'course': 1,
            'speciality': 'Не вказано'
        }
    )
    
    if request.method == 'POST':
        form = StudentProfileForm(request.POST, instance=student_profile, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Update user fields
                    request.user.first_name = form.cleaned_data['first_name']
                    request.user.last_name = form.cleaned_data['last_name']
                    request.user.patronymic = form.cleaned_data['patronymic']
                    request.user.academic_group = form.cleaned_data['academic_group']
                    request.user.save()
                    
                    # Update student profile fields
                    student_profile.course = form.cleaned_data['course']
                    student_profile.education_level = form.cleaned_data.get('education_level')
                    student_profile.additional_email = form.cleaned_data['additional_email']
                    student_profile.phone_number = form.cleaned_data['phone_number']
                    student_profile.save()
                    
                    messages.success(request, "Профіль успішно оновлено")
                    
                    # If it's an AJAX request, return JSON response
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Профіль успішно оновлено'
                        })
                    
                    # For regular requests, stay on the same page like teacher profile
                    return render(request, 'profile/student_edit.html', {
                        'form': form,
                        'user': request.user,
                        'user_profile': request.user
                    })
            except Exception as e:
                logger.error(f"Error saving student profile: {str(e)}")
                messages.error(request, f"Помилка при збереженні профілю: {str(e)}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f"Помилка при збереженні профілю: {str(e)}"
                    }, status=400)
        else:
            # Improved error handling - ensure all validation errors are captured
            logger.warning(f"Student profile form validation failed: {form.errors}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': dict(form.errors.items())
                }, status=400)
            else:
                # For non-AJAX requests, add form errors to messages
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
    else:
        form = StudentProfileForm(instance=student_profile, user=request.user)
    
    # Get the user profile from the database to ensure we have the latest data
    user_profile = get_object_or_404(CustomUser, id=request.user.id)
    
    return render(request, 'profile/student_edit.html', {
        'form': form,
        'user': request.user,
        'user_profile': user_profile
    })

@login_required
def complete_request(request, request_id):
    """
    Complete a request and assign a grade.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"})

    try:
        req = Request.objects.get(id=request_id)
        
        # Only allow the teacher to complete the request
        if req.teacher_id.teacher_id != request.user:
            return JsonResponse({"success": False, "error": "У вас немає прав для завершення цього запиту"})
            
        # Get the grade from POST data
        grade = request.POST.get("grade")
        if not grade or not grade.isdigit() or int(grade) < 0 or int(grade) > 100:
            return JsonResponse({"success": False, "error": "Будь ласка, введіть оцінку від 0 до 100"})
            
        # Update request status
        req.request_status = "Завершено"
        req.grade = int(grade)
        req.completion_date = timezone.now()
        req.save()
        
        messages.success(request, "Роботу успішно завершено")
        return JsonResponse({"success": True})
        
    except Request.DoesNotExist:
        return JsonResponse({"success": False, "error": "Запит не знайдено"})
    except Exception as e:
        logger.error(f"Error completing request {request_id}: {str(e)}")
        return JsonResponse({"success": False, "error": "Сталася помилка при обробці запиту"})

@login_required
def load_profile_tab(request, tab_name):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        context = {'user_profile': request.user}
        
        if tab_name == 'active':
            if request.user.role == 'Студент':
                active_requests = Request.objects.filter(
                    student_id=request.user,
                    request_status='Активний'
                ).select_related('teacher_id__teacher_id', 'teacher_theme', 'slot')
            
                # Створюємо словник для файлів
                active_request_files = {}
                for req in active_requests:
                    files = RequestFile.objects.filter(request=req).order_by('-uploaded_at')
                    active_request_files[req.id] = files
                
                context.update({
                    'active_requests': active_requests,
                    'active_request_files': active_request_files
                })
            else:  # Викладач
                active_requests = Request.objects.filter(
                    teacher_id__teacher_id=request.user,
                    request_status='Активний'
                )
                
                active_request_files = {}
                for req in active_requests:
                    files = RequestFile.objects.filter(request=req).order_by('-uploaded_at')
                    active_request_files[req.id] = files
                
                context.update({
                    'active_requests': active_requests,
                    'active_request_files': active_request_files
                })
            
            html = render_to_string('profile/active.html', context, request=request)
            return JsonResponse({'html': html})
            
        elif tab_name == 'requests':
            if request.user.role == 'Викладач':
                # Отримати запити, що очікують на підтвердження та відхилені запити
                pending_requests = Request.objects.filter(
                    teacher_id__teacher_id=request.user,
                    request_status__in=['Очікує', 'Відхилено']
                ).select_related('student_id', 'teacher_id', 'teacher_theme', 'slot')
                
                # Отримати запити, які були прийняті (Активний) або завершені
                accepted_requests = Request.objects.filter(
                    teacher_id__teacher_id=request.user,
                    request_status__in=['Активний', 'Завершено']
                ).select_related('student_id', 'teacher_id', 'teacher_theme', 'slot')
                
                context.update({
                    'pending_requests': pending_requests,
                    'accepted_requests': accepted_requests
                })
            else:
                # Для студента отримуємо всі запити
                sent_requests = Request.objects.filter(
                    student_id=request.user
                ).select_related('teacher_id__teacher_id', 'teacher_theme', 'slot')
                context['sent_requests'] = sent_requests
            
            html = render_to_string('profile/requests.html', context, request=request)
            return JsonResponse({'html': html})
            
        elif tab_name == 'archive':
            if request.user.role == 'Викладач':
                archive_requests = Request.objects.filter(
                    teacher_id__teacher_id=request.user,
                    request_status='Завершено'
                ).select_related('student_id', 'teacher_id', 'teacher_theme', 'slot')
            else:
                archive_requests = Request.objects.filter(
                    student_id=request.user,
                    request_status='Завершено'
                ).select_related('teacher_id__teacher_id', 'teacher_theme', 'slot')
            
            context['archived_requests'] = archive_requests
            html = render_to_string('profile/archive.html', context, request=request)
        return JsonResponse({'html': html})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def restore_request(request, request_id):
    """
    Restore a rejected request and update its status back to 'Очікує'.
    """
    if request.method == 'POST':
        try:
            req = Request.objects.get(id=request_id)
            
            # Add debugging logs
            logger.debug(f"Restore Request ID: {req.id}, Student: {req.student_id}, Teacher: {req.teacher_id}")
            logger.debug(f"Current user: {request.user.id} - {request.user}")
            logger.debug(f"Teacher user: {req.teacher_id.teacher_id.id} - {req.teacher_id.teacher_id}")
            
            # Check if the user is the teacher who rejected the request
            if req.teacher_id.teacher_id == request.user:
                # Check if request is in rejected status
                if req.request_status == 'Відхилено':
                    # Update request status back to pending
                    req.request_status = 'Очікує'
                    req.save()
                    
                    messages.success(request, 'Запит успішно відновлено')
                    
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'success': True})
                    return redirect('profile')
                else:
                    messages.error(request, 'Відновити можна лише відхилені запити')
            else:
                logger.warning(f"User {request.user.id} attempted to restore request {request_id} belonging to teacher {req.teacher_id.teacher_id.id}")
                messages.error(request, 'У вас немає прав для відновлення цього запиту')
        except Request.DoesNotExist:
            messages.error(request, 'Запит не знайдено')
        except Exception as e:
            logger.exception(f"Error restoring request {request_id}: {str(e)}")
            messages.error(request, f'Помилка при відновленні запиту: {str(e)}')
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Помилка при обробці запиту'})
    return redirect('profile')

@login_required
def archived_request_details(request, request_id):
    """
    Get details for an archived request.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    try:
        req = Request.objects.select_related(
            'student_id', 'teacher_id__teacher_id', 'teacher_theme'
        ).prefetch_related(
            'files__comments__author'
        ).get(id=request_id, request_status='Завершено')

        # Check access permissions
        if request.user.role == 'Студент' and req.student_id != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)
        if request.user.role == 'Викладач' and req.teacher_id.teacher_id != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)

        files_data = []
        for file in req.files.all():
            comments_data = []
            for comment in file.comments.all():
                comments_data.append({
                    'author': comment.author.get_full_name(),
                    'text': comment.text,
                    'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M')
                })
            
            files_data.append({
                'id': file.id,
                'file_url': file.file.url,
                'file_name': file.get_filename(),
                'description': file.description,
                'uploaded_at': file.uploaded_at.strftime('%d.%m.%Y %H:%M'),
                'uploaded_by': file.uploaded_by.get_full_name(),
                'comments': comments_data,
            })
        
        # Determine theme with proper priority
        theme = 'Тема не вказана'
        if req.custom_student_theme:
            theme = f"{req.custom_student_theme} (довільна тема студента)"
        elif req.approved_student_theme:
            theme = f"{req.approved_student_theme.theme} (запропоновано студентом)"
        elif req.teacher_theme:
            theme = req.teacher_theme.theme

        response_data = {
            'student': {
                'name': req.student_id.get_full_name(),
                'group': req.student_id.academic_group,
            },
            'teacher': {
                'name': req.teacher_id.teacher_id.get_full_name(),
            },
            'theme': theme,
            'grade': req.grade,
            'completion_date': req.completion_date.strftime('%d.%m.%Y'),
            'files': files_data
        }
        
        return JsonResponse(response_data)

    except Request.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)

def custom_404(request, exception):
    """
    Custom handler for 404 errors that renders a standalone error page
    """
    try:
        html = render_to_string('404.html', {}, request=request)
        return HttpResponseNotFound(html, content_type='text/html')
    except Exception as e:
        logger.error(f"Error rendering 404 page: {str(e)}")
        return HttpResponseNotFound('<h1>404 - Сторінку не знайдено</h1>')

def custom_500(request):
    """
    Custom handler for 500 errors that renders a standalone error page
    """
    try:
        html = render_to_string('500.html', {}, request=request)
        return HttpResponseServerError(html, content_type='text/html')
    except Exception as e:
        logger.error(f"Error rendering 500 page: {str(e)}")
        return HttpResponseServerError('<h1>500 - Внутрішня помилка сервера</h1>')

@require_GET
def request_details_for_approve(request, request_id):
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        req = Request.objects.select_related('student_id', 'teacher_id').prefetch_related('student_themes').get(id=request_id, request_status='Очікує')
        if request.user.role != 'Викладач' or req.teacher_id.teacher_id != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)
        
        selected_theme_id = req.teacher_theme.id if req.teacher_theme else None
        
        # Теми викладача
        teacher_themes = TeacherTheme.objects.filter(
            Q(teacher_id=req.teacher_id) & 
            (Q(is_occupied=False, is_active=True) | Q(id=selected_theme_id))
        )

        # Теми студента
        student_themes = req.student_themes.all()
        # Формуємо список тем для вибору
        themes = [
            {'id': f'teacher_{t.id}', 'title': f'Тема викладача: {t.theme}'} for t in teacher_themes
        ] + [
            {'id': f'student_{t.id}', 'title': f'Тема студента: {t.theme}'} for t in student_themes
        ]
        
        # Додаємо довільну тему студента, якщо вона є
        if req.custom_student_theme:
            themes.append({
                'id': 'custom_student_theme',
                'title': f'Довільна тема студента: {req.custom_student_theme}'
            })
        
        data = {
            'student_name': req.student_id.get_full_name(),
            'student_group': req.student_id.academic_group,
            'motivation': req.motivation_text,
            'request_date': req.request_date.strftime('%d.%m.%Y'),
            'themes': themes,
        }
        return JsonResponse(data)
    except Request.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)

@csrf_exempt
@require_POST
@transaction.atomic
def approve_request_with_theme(request, request_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        req = Request.objects.select_for_update().select_related('teacher_id', 'teacher_theme').get(
            id=request_id,
            request_status='Очікує'
        )

        if request.user.role != 'Викладач' or req.teacher_id.teacher_id != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)

        data = json.loads(request.body.decode('utf-8'))
        theme_id = data.get('theme_id')
        if not theme_id:
            return JsonResponse({'error': 'Тему не обрано'}, status=400)

        # Зберігаємо початкову тему викладача, щоб звільнити її, якщо буде обрано іншу
        original_teacher_theme = req.teacher_theme
        new_teacher_theme = None

        # Extract new fields
        comment = data.get('comment', '').strip()
        send_contacts = data.get('send_contacts', False)

        # Store student_id before making changes
        student_id = req.student_id

        # Cancel all other pending requests from this student
        other_pending_requests = Request.objects.filter(
            student_id=student_id,
            request_status='Очікує'
        ).exclude(id=req.id)
        
        cancelled_count = other_pending_requests.update(
            request_status='Відхилено', 
            rejected_reason='Автоматично скасовано через прийняття іншого запиту'
        )

        # Assign comment and send_contacts
        req.comment = comment
        req.send_contacts = send_contacts  # Використовуємо правильне ім'я поля

        # Assign theme
        if str(theme_id).startswith('teacher_'):
            theme_pk = int(str(theme_id).replace('teacher_', ''))
            theme = TeacherTheme.objects.get(id=theme_pk, teacher_id=req.teacher_id)
            
            if theme.is_occupied and theme != original_teacher_theme:
                return JsonResponse({'error': 'Ця тема вже зайнята іншим студентом.'}, status=400)
            new_teacher_theme = theme

            req.teacher_theme = theme
            req.approved_student_theme = None  # Явно очищаємо, якщо раніше була студентська
            req.custom_student_theme = None  # Очищаємо довільну тему, якщо вона була
        elif str(theme_id).startswith('student_'):
            theme_pk = int(str(theme_id).replace('student_', ''))
            theme = StudentTheme.objects.get(id=theme_pk, request=req)
            req.teacher_theme = None  # Явно очищаємо, якщо раніше була викладацька
            req.approved_student_theme = theme  # Зберігаємо посилання на студентську тему
            req.custom_student_theme = None  # Очищаємо довільну тему
        elif str(theme_id) == 'custom_student_theme':
            # Вибрана довільна тема студента
            req.teacher_theme = None  # Очищаємо тему викладача
            req.approved_student_theme = None  # Очищаємо затверджену тему студента
        else:
            return JsonResponse({'error': 'Некоректна тема'}, status=400)

        if original_teacher_theme and original_teacher_theme != new_teacher_theme:
            original_teacher_theme.is_occupied = False
            original_teacher_theme.save()
        
        if new_teacher_theme and not new_teacher_theme.is_occupied:
            new_teacher_theme.is_occupied = True
            new_teacher_theme.save()

        req.request_status = 'Активний'
        print(f"Saving Request ID {req.id}")
        print(f"Comment: {req.comment}")
        print(f"Send contacts to student: {req.send_contacts}")
        
        logger.info(f"Request {req.id} approved with theme. {cancelled_count} other pending requests cancelled for student {student_id.id}")
        
        req.save()
        return JsonResponse({
            'success': True,
            'cancelled_count': cancelled_count
        })

    except Request.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)
    except TeacherTheme.DoesNotExist:
        return JsonResponse({'error': 'Тема викладача не знайдена'}, status=404)
    except StudentTheme.DoesNotExist:
        return JsonResponse({'error': 'Тема студента не знайдена'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
@transaction.atomic
def student_refuse_request(request, request_id):
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    try:
        req = Request.objects.select_related('teacher_theme').get(id=request_id)
        if request.user.role != 'Студент' or req.student_id != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)
        if req.request_status not in ['Очікує', 'Активний']:
            return JsonResponse({'error': 'Відмовитися можна лише від запиту зі статусом "Очікує" або "Активний"'}, status=400)
        
        if req.teacher_theme:
            req.teacher_theme.is_occupied = False
            req.teacher_theme.save()

        data = json.loads(request.body.decode('utf-8'))
        reason = data.get('reason', '').strip()
        req.request_status = 'Відхилено студентом'
        req.rejected_reason = reason or 'Студент не вказав причину відмови'
        req.save()
        return JsonResponse({'success': True})
    except Request.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def edit_request_theme(request, request_id):
    """
    Edit the theme of an active request.
    Only teachers can edit themes of their active requests.
    """
    logger.info(f"edit_request_theme called with request_id: {request_id}")
    
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        logger.warning("Invalid request - not AJAX")
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        # Get the request
        req = Request.objects.get(id=request_id, request_status='Активний')
        logger.info(f"Found request: {req.id}, teacher: {req.teacher_id.teacher_id}, current user: {request.user}")
        
        # Check if user is the teacher of this request
        if request.user.role != 'Викладач' or req.teacher_id.teacher_id != request.user:
            logger.warning(f"Permission denied: user {request.user.id} trying to edit theme for request {request_id}")
            return JsonResponse({'error': 'У вас немає прав для редагування цієї теми'}, status=403)
        
        # Parse JSON data
        data = json.loads(request.body.decode('utf-8'))
        new_theme = data.get('new_theme', '').strip()
        logger.info(f"New theme: '{new_theme}'")
        
        if not new_theme:
            logger.warning("Empty theme provided")
            return JsonResponse({'error': 'Тема не може бути порожньою'}, status=400)
        
        # Update the theme based on what type it currently is, preserving the type
        if req.custom_student_theme:
            # If it's a custom student theme, update it directly
            logger.info(f"Updating custom student theme: {req.custom_student_theme} -> {new_theme}")
            req.custom_student_theme = new_theme
            req.save()
        elif req.approved_student_theme:
            # If it's an approved student theme, update the theme text
            logger.info(f"Updating approved student theme: {req.approved_student_theme.theme} -> {new_theme}")
            req.approved_student_theme.theme = new_theme
            req.approved_student_theme.save()
        elif req.teacher_theme:
            logger.info(f"Updating existing teacher theme: {req.teacher_theme.theme} -> {new_theme}")
            req.teacher_theme.theme = new_theme
            req.teacher_theme.save()
        else:
            logger.info("Creating new teacher theme")
            # If no theme exists, create a new teacher theme
            teacher_profile = OnlyTeacher.objects.get(teacher_id=request.user)
            new_teacher_theme = TeacherTheme.objects.create(
                teacher_id=teacher_profile,
                theme=new_theme,
                theme_description='Тема, створена під час редагування'
            )
            req.teacher_theme = new_teacher_theme
            req.save()
        
        logger.info("Theme updated successfully")
        return JsonResponse({'success': True, 'message': 'Тему успішно оновлено'})
        
    except Request.DoesNotExist:
        logger.error(f"Request {request_id} not found or not active")
        return JsonResponse({'error': 'Запит не знайдено або не є активним'}, status=404)
    except OnlyTeacher.DoesNotExist:
        logger.error(f"Teacher profile not found for user {request.user.id}")
        return JsonResponse({'error': 'Профіль викладача не знайдено'}, status=404)
    except Exception as e:
        logger.error(f"Error editing request theme {request_id}: {str(e)}")
        return JsonResponse({'error': 'Сталася помилка при оновленні теми'}, status=500)
    
    
@login_required
@require_GET
def get_student_request_details(request, request_id):
    """
    Get details for a student's request.
    """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    req = get_object_or_404(Request.objects.select_related('teacher_theme', 'teacher_id'), id=request_id)

    if req.student_id != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    student_themes = list(req.student_themes.all().values('id', 'theme'))
    
    selected_teacher_theme_id = req.teacher_theme.id if req.teacher_theme else None

    available_teacher_themes_query = TeacherTheme.objects.filter(
        teacher_id=req.teacher_id, is_active=True
    ).filter(
        Q(is_occupied=False) | Q(id=selected_teacher_theme_id)
    )
    available_teacher_themes = list(available_teacher_themes_query.values('id', 'theme'))
    
    data = {
        'motivation': req.motivation_text,
        'student_themes': student_themes,
        'selected_teacher_theme_id': selected_teacher_theme_id,
        'available_teacher_themes': available_teacher_themes,
    }
    return JsonResponse(data)

@login_required
@require_POST
@transaction.atomic
def edit_student_request(request, request_id):
    """
    Edit a student's request, including motivation and themes.
    """
    req = get_object_or_404(Request, id=request_id)

    if req.student_id != request.user:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    
    motivation = request.POST.get('motivation', '').strip()

    current_student_theme_ids = {int(tid) for tid in request.POST.getlist('themes') if tid.isdigit()}
    
    new_themes = [t.strip() for t in request.POST.getlist('new_themes') if t.strip()]
    
    total_student_themes = len(current_student_theme_ids) + len(new_themes)
    
    if total_student_themes > 3:
        return JsonResponse({'success': False, 'error': 'Ви можете запропонувати не більше 3 власних тем.'}, status=400)
    
    new_teacher_theme_id = request.POST.get('teacher_theme_id')
    
    if total_student_themes == 0 and not new_teacher_theme_id:
        return JsonResponse({'success': False, 'error': 'Необхідно обрати тему викладача або запропонувати власну.'}, status=400)

    req.motivation_text = motivation

    StudentTheme.objects.filter(request=req).exclude(id__in=current_student_theme_ids).delete()

    for theme_text in new_themes:
        StudentTheme.objects.create(
            request=req,
            student_id=request.user,
            theme=theme_text
        )
        
    old_teacher_theme = req.teacher_theme
    new_teacher_theme = None
    if new_teacher_theme_id and new_teacher_theme_id.isdigit():
        try:
            new_teacher_theme = TeacherTheme.objects.get(id=int(new_teacher_theme_id))
        except TeacherTheme.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Обрану тему викладача не знайдено.'}, status=400)

    if old_teacher_theme != new_teacher_theme:
        if old_teacher_theme:
            old_teacher_theme.is_occupied = False
            old_teacher_theme.save()

        if new_teacher_theme:
            if new_teacher_theme.is_occupied:
                 return JsonResponse({'success': False, 'error': 'Ця тема вже зайнята іншим студентом.'}, status=400)
            new_teacher_theme.is_occupied = True
            new_teacher_theme.save()

    req.teacher_theme = new_teacher_theme
            
    req.save()
    return JsonResponse({'success': True, 'message': 'Запит успішно оновлено'})

@login_required
@require_POST
def activate_teacher_theme(request, theme_id):
    """
    Активує тему викладача
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        theme = TeacherTheme.objects.get(id=theme_id)
        
        # Перевіряємо права доступу
        if request.user.role != 'Викладач' or theme.teacher_id.teacher_id != request.user:
            return JsonResponse({'error': 'У вас немає прав для активації цієї теми'}, status=403)
        
        # Активуємо тему (синхронізуємо обидва поля)
        theme.is_active = True
        theme.is_deleted = False  # ✅ Важливо!
        theme.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Тему успішно активовано'
        })
        
    except TeacherTheme.DoesNotExist:
        return JsonResponse({'error': 'Тему не знайдено'}, status=404)
    except Exception as e:
        logger.error(f"Error activating theme {theme_id}: {str(e)}")
        return JsonResponse({'error': 'Сталася помилка при активації теми'}, status=500)

@login_required
@require_POST
def deactivate_teacher_theme(request, theme_id):
    """
    Деактивує тему викладача
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        theme = TeacherTheme.objects.get(id=theme_id)
        
        # Перевіряємо права доступу
        if request.user.role != 'Викладач' or theme.teacher_id.teacher_id != request.user:
            return JsonResponse({'error': 'У вас немає прав для деактивації цієї теми'}, status=403)
        
        # Деактивуємо тему (тільки is_active)
        theme.is_active = False
        theme.is_deleted = False  # ✅ Змінюємо на False
        theme.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Тему успішно деактивовано'
        })
        
    except TeacherTheme.DoesNotExist:
        return JsonResponse({'error': 'Тему не знайдено'}, status=404)
    except Exception as e:
        logger.error(f"Error deactivating theme {theme_id}: {str(e)}")
        return JsonResponse({'error': 'Сталася помилка при деактивації теми'}, status=500)

@login_required
@require_POST
def delete_teacher_theme(request, theme_id):
    """
    Фізично видаляє тему викладача (з перевірками залежностей)
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        theme = TeacherTheme.objects.get(id=theme_id)
        
        # Перевіряємо права доступу
        if request.user.role != 'Викладач' or theme.teacher_id.teacher_id != request.user:
            return JsonResponse({'error': 'У вас немає прав для видалення цієї теми'}, status=403)
        
        # Перевіряємо чи можна видалити
        if not theme.can_be_deleted():
            active_count = theme.get_active_requests_count()
            return JsonResponse({
                'error': f'Неможливо видалити тему. Вона використовується в {active_count} активних запитах.'
            }, status=400)
        
        # Видаляємо тему
        theme_name = theme.theme
        theme.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Тему "{theme_name}" успішно видалено'
        })
        
    except TeacherTheme.DoesNotExist:
        return JsonResponse({'error': 'Тему не знайдено'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting theme {theme_id}: {str(e)}")
        return JsonResponse({'error': 'Сталася помилка при видаленні теми'}, status=500)

@login_required
@require_POST
def attach_theme_to_streams(request, theme_id):
    """
    Прикріплює тему до потоків
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        theme = TeacherTheme.objects.get(id=theme_id)
        
        # Перевіряємо права доступу
        if request.user.role != 'Викладач' or theme.teacher_id.teacher_id != request.user:
            return JsonResponse({'error': 'У вас немає прав для редагування цієї теми'}, status=403)
        
        # Отримуємо список ID потоків
        data = json.loads(request.body.decode('utf-8'))
        stream_ids = data.get('stream_ids', [])
        
        if stream_ids:
            streams = Stream.objects.filter(id__in=stream_ids)
            theme.streams.set(streams)
            stream_names = ', '.join([stream.stream_code for stream in streams])
            message = f'Тему прикріплено до потоків: {stream_names}'
        else:
            theme.streams.clear()
            message = 'Тему відкріплено від усіх потоків'
        
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except TeacherTheme.DoesNotExist:
        return JsonResponse({'error': 'Тему не знайдено'}, status=404)
    except Exception as e:
        logger.error(f"Error attaching theme {theme_id} to streams: {str(e)}")
        return JsonResponse({'error': 'Сталася помилка при прикріпленні теми до потоків'}, status=500)

@login_required
@require_http_methods(["POST"])
def create_teacher_theme(request):
    """
    Створює нову тему викладача
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    if request.user.role != 'Викладач':
        return JsonResponse({'error': 'У вас немає прав для створення тем'}, status=403)
    
    try:
        data = json.loads(request.body)
        theme_name = data.get('theme', '').strip()
        theme_description = data.get('description', '').strip()
        # Приймаємо stream_ids замість streams
        stream_ids = data.get('stream_ids', [])
        
        if not theme_name:
            return JsonResponse({'error': 'Назва теми не може бути порожньою'}, status=400)
        
        # Отримати профіль викладача
        teacher_profile = OnlyTeacher.objects.get(teacher_id=request.user)
        
        # Створити тему з правильними полями
        theme = TeacherTheme.objects.create(
            teacher_id=teacher_profile,
            theme=theme_name,
            theme_description=theme_description,
            is_occupied=False,
            is_active=True,
            is_deleted=False
        )
        
        # Прикріпити до потоків
        if stream_ids:
            streams = Stream.objects.filter(id__in=stream_ids)
            theme.streams.set(streams)
        
        return JsonResponse({
            'success': True,
            'message': 'Тему успішно створено',
            'theme': {
                'id': theme.id,
                'theme': theme.theme,
                'description': theme.theme_description,
                'is_active': theme.is_active,
                'streams': list(theme.streams.values_list('id', flat=True))
            }
        })
        
    except OnlyTeacher.DoesNotExist:
        return JsonResponse({'error': 'Профіль викладача не знайдено'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некоректний формат даних'}, status=400)
    except Exception as e:
        logger.error(f"Error creating teacher theme: {str(e)}")
        return JsonResponse({'error': f'Помилка при створенні теми: {str(e)}'}, status=500)

@login_required
@require_POST
def update_teacher_theme(request, theme_id):
    """
    Оновлює тему викладача
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        theme = TeacherTheme.objects.get(id=theme_id)
        
        # Перевіряємо права доступу
        if request.user.role != 'Викладач' or theme.teacher_id.teacher_id != request.user:
            return JsonResponse({'error': 'У вас немає прав для редагування цієї теми'}, status=403)
        
        # Отримуємо дані з запиту
        data = json.loads(request.body)
        theme_name = data.get('theme', '').strip()
        theme_description = data.get('description', '').strip()
        
        # Валідація
        if not theme_name:
            return JsonResponse({'error': 'Назва теми не може бути порожньою'}, status=400)
        
        if len(theme_name) > 100:
            return JsonResponse({'error': 'Назва теми занадто довга (максимум 100 символів)'}, status=400)
        
        # Перевіряємо чи тема з такою назвою вже існує у цього викладача
        existing_theme = TeacherTheme.objects.filter(
            teacher_id=theme.teacher_id,
            theme=theme_name
        ).exclude(id=theme_id).first()
        
        if existing_theme:
            return JsonResponse({'error': 'У вас вже є тема з такою назвою'}, status=400)
        
        # Оновлюємо тему
        theme.theme = theme_name
        theme.theme_description = theme_description
        theme.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Тему успішно оновлено',
            'theme': {
                'id': theme.id,
                'name': theme.theme,
                'description': theme.theme_description
            }
        })
        
    except TeacherTheme.DoesNotExist:
        return JsonResponse({'error': 'Тему не знайдено'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некоректні дані'}, status=400)
    except Exception as e:
        logger.error(f"Error updating theme {theme_id}: {str(e)}")
        return JsonResponse({'error': 'Сталася помилка при оновленні теми'}, status=500)

@login_required
def delete_theme(request, theme_id):
    """
    Видаляє тему викладача з перевіркою можливості видалення
    """
    theme = get_object_or_404(TeacherTheme, id=theme_id, teacher_id__teacher_id=request.user)
    try:
        active_requests = Request.objects.filter(
            teacher_theme=theme,
            request_status__in=['Очікує', 'Активний']
        ).exists()

        if active_requests:
            return JsonResponse({
                'error': 'Неможливо видалити тему, яка використовується в активних або очікуючих запитах'
            }, status=400)
        
        theme.delete() 
        return JsonResponse({'success': True})

    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Помилка при видаленні теми: {str(e)}'}, status=500)

def _group_teacher_themes_by_stream(teacher_profile):
    """
    Групує теми викладача за потоками
    """
    themes = TeacherTheme.objects.filter(
        teacher_id=teacher_profile, 
        is_deleted=False, 
        is_active=True
    ).exclude(
        theme_description='(Запропоновано студентом)'
    ).prefetch_related('streams')
    
    themes_by_stream = {}
    
    for theme in themes:
        if not theme.streams.exists():
            if 'Без потоку' not in themes_by_stream:
                themes_by_stream['Без потоку'] = []
            themes_by_stream['Без потоку'].append(theme)
        else:
            for stream in theme.streams.all():
                stream_name = stream.stream_code.replace(' (Бакалаври)', '')
                if stream_name not in themes_by_stream:
                    themes_by_stream[stream_name] = []
                themes_by_stream[stream_name].append(theme)
    
    sorted_themes_by_stream = {}
    if 'Без потоку' in themes_by_stream:
        sorted_themes_by_stream['Без потоку'] = themes_by_stream['Без потоку']
    
    for stream_name in sorted([k for k in themes_by_stream.keys() if k != 'Без потоку']):
        sorted_themes_by_stream[stream_name] = themes_by_stream[stream_name]
    
    return sorted_themes_by_stream

