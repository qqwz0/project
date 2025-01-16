import logging
from urllib.parse import urlencode, parse_qs

import requests
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.crypto import get_random_string
from dotenv import load_dotenv
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login

from .forms import RegistrationForm
from .models import CustomUser

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Constants
MICROSOFT_AUTH_URL = f"{settings.MICROSOFT_AUTHORITY}/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = f"{settings.MICROSOFT_AUTHORITY}/oauth2/v2.0/token"
MICROSOFT_GRAPH_ME_ENDPOINT = f"{settings.MICROSOFT_GRAPH_ENDPOINT}/me"

def microsoft_register(request):
    """
    Handle the registration process using Microsoft OAuth.
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
            logger.debug("Redirecting to: %s", authorization_url)
            return redirect(authorization_url)
        else:
            logger.debug("Form errors: %s", form.errors)
            return render(request, "register.html", {"form": form, "errors": form.errors})
    else:
        logger.debug("GET request received")
        form = RegistrationForm()

    return render(request, "register.html", {"form": form})

def microsoft_login(request):
    """
    Handle Microsoft's OAuth login initiation and optionally show a login page.
    """
    logger.debug("Starting Microsoft login process.")

    if request.method == "GET":
        logger.debug("GET request received for Microsoft login.")

        # If the request is to render the login page
        if not request.GET.get("redirect"):
            logger.debug("Rendering login page before redirecting to Microsoft.")
            return render(request, 'login.html')  # Update with the correct template path
        
        CSRF_STATE = get_random_string(32)
        request.session['csrf_state'] = CSRF_STATE

        # Redirect to Microsoft's OAuth page if "redirect" is set in the query params
        logger.debug("Redirecting to Microsoft login page.")
        params = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
            "response_mode": "query",
            "scope": " ".join(settings.MICROSOFT_SCOPES),
            "state": urlencode({"action": 'login', "csrf": CSRF_STATE}),
        }
        authorization_url = f"{MICROSOFT_AUTH_URL}?{urlencode(params)}"
        logger.debug("Authorization URL: %s", authorization_url)
        return redirect(authorization_url)

def microsoft_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")

    if not code or not state:
        logger.error("Відсутній авторизаційний код або параметр стану.")
        messages.error(request, "Авторизаційний код або параметр стану не надано")
        return redirect("login")

    try:
        logger.debug("Вхідний стан: %s", state)
        logger.debug("CSRF стан сесії: %s", request.session.get('csrf_state'))

        # Розбір стану
        state_data = parse_qs(state)
        logger.debug("Розібрані дані стану: %s", state_data)

        action = state_data.get("action", [None])[0]
        received_csrf = state_data.get("csrf", [None])[0]

        # Перевірка CSRF стану
        if received_csrf != request.session.get('csrf_state'):
            logger.error("Перевірка CSRF не вдалася. Отримано: %s, Очікувано: %s",
                         received_csrf, request.session.get('csrf_state'))
            messages.error(request, "Недійсний параметр стану")
            return redirect("login")

        # Обробка дій
        if action == "register":
            return handle_registration_callback(request, code)
        elif action == "login":
            return handle_login_callback(request, code)
        else:
            logger.error("Недійсна дія в параметрі стану: %s", action)
            messages.error(request, "Недійсна дія в параметрі стану")
            return redirect("login")

    except Exception as e:
        logger.error("Неочікувана помилка в microsoft_callback: %s", e, exc_info=True)
        messages.error(request, "Сталася неочікувана помилка")
        return redirect("login")

def handle_registration_callback(request, code):
    """
    Handle Microsoft's OAuth callback for registration.
    """

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
        token_response = requests.post(MICROSOFT_TOKEN_URL, data=data)
        token_response.raise_for_status()
        tokens = token_response.json()
        access_token = tokens.get("access_token")

        if not access_token:
            messages.error(request, "Не вдалося отримати токен доступу.")
            return redirect('register')

        # Fetch user info
        headers = {"Authorization": f"Bearer {access_token}"}
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
            messages.error(request, "Такий користувач вже зареєстрований.")
            return redirect('register')

        if created:
            logger.info("New user: %s", email)

        # Redirect user to the desired page after registration
        return redirect("login") 

    except ValidationError as e:
        error_message = str(e)
        messages.error(request, error_message)
        return redirect('register')
    except requests.exceptions.RequestException as e:
        logger.error("Error during Microsoft OAuth callback: %s", e)
        messages.error(request, "Не вдалося завершити автентифікацію.")
        return redirect('register')

def handle_login_callback(request, code):
    """
    Handle Microsoft's OAuth login callback.
    """
    logger.debug("Handling callback for Microsoft login.")
    state = request.GET.get("state")

    if not code or not state:
        logger.error("Authorization code or state not provided.")
        messages.error(request, "Авторизаційний код або параметр стану не надано.")
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
            messages.error(request, "Електронну пошту не знайдено в обліковому записі Microsoft.")
            return redirect("login")

        logger.debug("User email: %s", email)

        # Check if the user exists
        try:
            logger.debug("Checking if user exists in the database.")
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            logger.error("User with email %s not found.", email)
            messages.error(request, "Користувача з такою електронною поштою не знайдено.")
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

def profile(request):
    return render(request, "profile.html")

def logout_view(request):
    logout(request)
    return redirect('login')