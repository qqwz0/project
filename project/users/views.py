import logging
import os
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.encoding import force_str
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from dotenv import load_dotenv

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
CSRF_STATE = "random_string_for_csrf_protection"

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
            
            # Redirect to Microsoft OAuth
            params = {
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "response_type": "code",
                "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
                "response_mode": "query",
                "scope": " ".join(settings.MICROSOFT_SCOPES),
                "state": CSRF_STATE,
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


def microsoft_callback(request):
    """
    Handle Microsoft's OAuth callback for registration.
    """
    code = request.GET.get("code")
    state = request.GET.get('state')
    if not code or not state:
        return JsonResponse({"error": "Authorization code or state not provided"}, status=400)

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
        token_response = requests.post(MICROSOFT_TOKEN_URL, data=data)
        token_response.raise_for_status()
        tokens = token_response.json()
        access_token = tokens.get("access_token")

        if not access_token:
            raise ValidationError("Failed to obtain access token")

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
            messages.error(request, "Please specify the correct role")
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
        return JsonResponse({"error": error_message}, status=400)
    except requests.exceptions.RequestException as e:
        logger.error("Error during Microsoft OAuth callback: %s", e)
        return JsonResponse({"error": "Failed to complete authentication"}, status=500)


def login(request):
    """
    Render the login page.
    """
    return render(request, 'login.html')

