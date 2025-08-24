from urllib.parse import urlencode
from django.conf import settings
import requests
import logging
from django.contrib import messages
from django.shortcuts import redirect
from apps.catalog.models import (OnlyStudent, OnlyTeacher)

MICROSOFT_AUTH_URL = f"{settings.MICROSOFT_AUTHORITY}/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = f"{settings.MICROSOFT_AUTHORITY}/oauth2/v2.0/token"
MICROSOFT_GRAPH_ME_ENDPOINT = f"{settings.MICROSOFT_GRAPH_ENDPOINT}/me"

logger = logging.getLogger(__name__)

def get_access_token(code, request):
    data = {
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "scope": " ".join(settings.MICROSOFT_SCOPES),
        "code": code,
        "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
        "grant_type": "authorization_code",
        "client_secret": settings.MICROSOFT_CLIENT_SECRET,
        "state": urlencode({"action": "login", "csrf": request.session.get("csrf_state")}),
    }
    token_response = requests.post(MICROSOFT_TOKEN_URL, data=data)
    token_response.raise_for_status()
    return token_response.json().get("access_token")


def get_user_info(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    return requests.get(MICROSOFT_GRAPH_ME_ENDPOINT, headers=headers).json()


def extract_user_data(user_info):
    email = user_info.get("mail") or user_info.get("userPrincipalName")
    return (
        email,
        user_info.get("givenName", ""),
        user_info.get("surname", ""),
        user_info.get("jobTitle", "")
    )


def fail_and_redirect(request, msg, log_msg=None, level="error"):
    if log_msg:
        getattr(logger, level)(log_msg)
    messages.error(request, msg)
    return redirect("register")


def create_student_profile(user, group_code, email):
    from apps.catalog.models import Group
    try:
        group_obj = Group.objects.get(group_code=group_code)
        OnlyStudent.objects.create(student_id=user, group=group_obj)
        logger.info(f"Created OnlyStudent for {email} with group {group_code}")
    except Group.DoesNotExist:
        logger.warning(f"Group {group_code} not found for {email}, using fallback group.")
        fallback = Group.objects.first()
        if fallback:
            OnlyStudent.objects.create(student_id=user, group=fallback)
            logger.warning(f"Fallback OnlyStudent created with group {fallback.group_code}")
        else:
            logger.error("No groups available in DB for student creation.")


def create_teacher_profile(user, job_title, department_name):
    from apps.catalog.models import Department, OnlyTeacher

    try:
        department_obj = Department.objects.get(department_name=department_name)
    except Department.DoesNotExist:
        logger.warning(f"Department {department_name} not found for {user.email}, using fallback.")
        department_obj = Department.objects.first()
        if not department_obj:
            logger.error("No departments available in DB for teacher creation.")
            return

    academic_level = job_title if job_title else "Викладач"
    faculty_short_name = department_obj.faculty.short_name if department_obj.faculty else "unknown"

    # Формуємо базовий profile_link
    last_name = user.last_name.lower() if user.last_name else user.email.split('.')[1]
    first_initial = user.first_name[0].lower() if user.first_name else user.email.split('.')[0][0]
    base_link = f"{last_name}-{first_initial}"

    # Формуємо повне посилання
    full_url = f"https://{faculty_short_name}.lnu.edu.ua/{base_link}"

    if url_exists(full_url):
        profile_link = full_url
    else:
        profile_link = None

    OnlyTeacher.objects.create(
        teacher_id=user,
        academic_level=academic_level,
        department=department_obj,
        profile_link=profile_link
    )
    logger.info(f"Created OnlyTeacher for {user.email} with department {department_obj.department_name} and profile link {profile_link}")

def url_exists(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False