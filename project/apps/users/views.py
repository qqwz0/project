import json
import logging
from urllib.parse import urlencode, parse_qs
from functools import wraps

import requests
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import F
from django.db import transaction
from django.shortcuts import redirect, render, get_object_or_404
from django.utils.crypto import get_random_string
from dotenv import load_dotenv
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login
from django.contrib.auth.decorators import login_required

from .forms import RegistrationForm, TeacherProfileForm, StudentProfileForm
from .models import CustomUser
from apps.catalog.models import (
    OnlyTeacher,
    OnlyStudent,
    Stream,
    Slot,
    Request,
    TeacherTheme
)
from apps.catalog.models import (
    OnlyTeacher as CatalogTeacher,
)


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
        }
        authorization_url = f"{MICROSOFT_AUTH_URL}?{urlencode(params)}"
        logger.info("Authorization URL: %s", authorization_url)
        return redirect(authorization_url)

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
    code = request.GET.get("code")
    state = request.GET.get("state")

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
        
        teacher_profile = OnlyTeacher.objects.create(
            teacher_id=user,
            academic_level="Доцент",
            additional_email="teacher.test@lnu.edu.ua",
            phone_number="+380991234567"
        )

        stream = Stream.objects.create(
            specialty_name="Тестова спеціальність",
            stream_code="ФЕС-2"
        )
        
        Slot.objects.create(
            teacher_id=teacher_profile,
            stream_id=stream,
            quota=5,
            occupied=0
        )
        
    auth_login(request, user)
    return redirect("profile")

@login_required
def profile(request, user_id=None):
    if user_id:
        user_profile = get_object_or_404(CustomUser, id=user_id)
        is_own_profile = request.user.id == user_id
    else:
        user_profile = request.user
        is_own_profile = True

    context = {
        'user_profile': user_profile,
        'teacher_profile': teacher_profile,
        'is_own_profile': is_own_profile,
    }

    if user_profile.role == 'Викладач':
        teacher_profile = OnlyTeacher.objects.get(teacher_id=user_profile)
        themes = TeacherTheme.objects.filter(teacher_id=teacher_profile)
        slots = Slot.objects.filter(teacher_id=teacher_profile)
        
        if is_own_profile:
            received_requests = Request.objects.filter(
                teacher_id=teacher_profile,
                request_status='pending'
            )
            context['received_requests'] = received_requests

        context.update({
            'teacher_profile': teacher_profile,
            'themes': themes,
            'slots': slots,
        })

    elif user_profile.role == 'Студент':
        student_profile = OnlyStudent.objects.get(student_id=user_profile)
        
        if is_own_profile:
            sent_requests = Request.objects.filter(student_id=user_profile)
            context['sent_requests'] = sent_requests

        context['student_profile'] = student_profile

    return render(request, 'profile/profile.html', context)

import logging

logger = logging.getLogger('app')

@login_required
def approve_request(request, request_id):
    logger.info(f"Approving request ID: {request_id}, User: {request.user}")

    try:
        req = Request.objects.get(id=request_id)
    except Request.DoesNotExist:
        logger.info(f"Request ID {request_id} not found!")
        messages.info(request, "Запит не знайдено.")
        return redirect("profile")

    # Only allow the teacher or the student to act
    if req.teacher_id.teacher_id != request.user and req.student_id != request.user:
        logger.info(f"Unauthorized approval attempt by user {request.user}")
        messages.error(request, "Неможливо провести операцію.")
        return redirect("profile")

    if not req.slot:
        logger.info(f"Request {request_id} does not have a valid slot!")
        messages.error(request, "Запит не має дійсного слота.")
        return redirect("profile")

    available_slots = req.slot.get_available_slots()
    logger.info(f"Available slots: {available_slots}, Quota: {req.slot.quota}, Occupied: {req.slot.occupied}")

    if available_slots <= 0:
        logger.info(f"Auto-rejecting request {request_id} due to full capacity.")
        req.request_status = 'rejected'
        req.rejected_reason = "Усі місця зайняті."
        req.save()
        messages.error(request, "Запит автоматично відхилено: усі місця зайняті.")
        return redirect("profile")

    try:
        with transaction.atomic():
            logger.debug(f"Attempting to approve request {request_id}.")
            
            req.request_status = 'accepted'
            req.save()

            logger.info(f"Request {request_id} successfully approved.")
            messages.success(request, "Запит успішно підтверджено.")
    except ValidationError as e:
        logger.info(f"Validation error: {e}")
        messages.error(request, str(e))
    except Exception as e:
        logger.info(f"Unexpected error approving request {request_id}: {e}")
        messages.error(request, "Сталася помилка. Спробуйте ще раз.")

    return redirect("profile")


@login_required
def reject_request(request, request_id):
    req = get_object_or_404(Request, id=request_id)
    
    if req.teacher_id.teacher_id != request.user and req.student_id != request.user:
        messages.error(request, "Неможливо провести операцію.")
        return redirect("profile")
    
    if request.method == "POST":
        reason = request.POST.get("reason", "")
        req.request_status = "rejected"
        req.rejected_reason = reason  # Ensure your model has this field
        req.save()
        messages.success(request, "Запит відхилено.")
        return redirect("profile")
    
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
        
    teacher_profile, created = CatalogTeacher.objects.get_or_create(
        teacher_id=request.user,
        defaults={
            'position': 'Не вказано',
            'academic_level': 'Аспірант'
        }
    )
    
    if request.method == 'POST':
        form = TeacherProfileForm(request.POST, instance=teacher_profile, user=request.user)
        if form.is_valid():
            request.user.first_name = form.cleaned_data['first_name']
            request.user.last_name = form.cleaned_data['last_name']
            request.user.patronymic = form.cleaned_data['patronymic']
            request.user.department = form.cleaned_data['department']
            request.user.save()
            
            form.save()
            
            themes_data = form.cleaned_data.get('themes', '[]')
            if themes_data:
                themes = json.loads(themes_data)
                TeacherTheme.objects.filter(teacher_id=teacher_profile).delete()
                for theme_text in themes:
                    TeacherTheme.objects.create(
                        teacher_id=teacher_profile,
                        theme=theme_text,
                        theme_description="",
                        is_occupied=False
                    )
            
            messages.success(request, "Профіль успішно оновлено")
            return redirect('profile')
    else:
        form = TeacherProfileForm(instance=teacher_profile, user=request.user)
    
    existing_themes = TeacherTheme.objects.filter(teacher_id=teacher_profile)
    
    return render(request, 'profile/teacher_edit.html', {
        'form': form,
        'existing_themes': existing_themes
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
            'speciality': 'Не вказано',
            'course': 1 
        }
    )
    
    if request.method == 'POST':
        form = StudentProfileForm(request.POST, instance=student_profile, user=request.user)
        if form.is_valid():
            request.user.first_name = form.cleaned_data['first_name']
            request.user.last_name = form.cleaned_data['last_name']
            request.user.patronymic = form.cleaned_data['patronymic']
            request.user.academic_group = form.cleaned_data['academic_group']
            request.user.save()
            
            form.save()
            
            messages.success(request, "Профіль успішно оновлено")
            return redirect('profile')
    else:
        form = StudentProfileForm(instance=student_profile, user=request.user)
    
    return render(request, 'profile/student_edit.html', {
        'form': form
    })
