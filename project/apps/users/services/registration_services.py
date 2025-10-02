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
    # Отримуємо department з Microsoft Graph API
    params = {
        '$select': 'mail,userPrincipalName,givenName,surname,jobTitle,department'
    }
    response = requests.get(MICROSOFT_GRAPH_ME_ENDPOINT, headers=headers, params=params)
    return response.json()


def extract_user_data(user_info):
    email = user_info.get("mail") or user_info.get("userPrincipalName")
    return (
        email,
        user_info.get("givenName", ""),
        user_info.get("surname", ""),
        user_info.get("jobTitle", ""),
        user_info.get("department", "")
    )


def validate_faculty_from_microsoft(department):
    """
    Перевіряє чи факультет користувача з Microsoft підтримується системою
    """
    if not department:
        return False
    
    # Дозволені варіанти назв факультету
    allowed_faculties = [
        "Факультет електроніки та комп'ютерних технологій",
        "Факультет електроніки та КТ",
        "Факультет електроніки",
        "Faculty of Electronics and Computer Technologies",
        "Faculty of Electronics and CT"
    ]
    
    # Перевіряємо чи department містить один з дозволених факультетів
    department_lower = department.lower()
    for faculty in allowed_faculties:
        if faculty.lower() in department_lower:
            return True
    
    return False


def fail_and_redirect(request, msg, log_msg=None, level="error"):
    if log_msg:
        getattr(logger, level)(log_msg)
    messages.error(request, msg)
    return redirect("register")


def create_student_profile(user, group_code, email, faculty, department=None):
    from apps.catalog.models import Group, OnlyStudent
    try:
        group_obj = Group.objects.get(group_code=group_code)
        OnlyStudent.objects.create(student_id=user, group=group_obj, faculty=faculty, department=department)
        logger.info(f"Created OnlyStudent for {email} with group {group_code} and department {department}")
    except Group.DoesNotExist:
        logger.warning(f"Group {group_code} not found for {email}, using fallback group.")
        fallback = Group.objects.first()
        if fallback:
            OnlyStudent.objects.create(student_id=user, group=fallback, department=department, faculty=None)
            logger.warning(f"Fallback OnlyStudent created with group {fallback.group_code} and department {department}")
        else:
            logger.error("No groups available in DB for student creation.")


def create_teacher_profile(user, job_title, department_obj):
    """
    Створює профіль викладача з Department об'єктом
    """
    from apps.catalog.models import OnlyTeacher

    academic_level = job_title if job_title else "Викладач"
    faculty_short_name = department_obj.faculty.short_name if department_obj.faculty else "unknown"

    # Формуємо базовий profile_link
    last_name = user.email.split('.')[1]
    first_initial = user.email.split('.')[0][0]
    base_link = f"{last_name}-{first_initial}"

    # Формуємо повне посилання
    full_url = f"https://{faculty_short_name}.lnu.edu.ua/{base_link}"

    if url_exists(full_url):
        profile_link = full_url
    else:
        profile_link = None

    try:
        OnlyTeacher.objects.get_or_create(
            teacher_id=user,
            defaults={
                'academic_level': academic_level,
                'department': department_obj,
                'profile_link': profile_link
            }
        )
    except Exception as e:
        logger.error(f"Error creating OnlyTeacher for user {user.email}: {str(e)}", exc_info=True)
        raise  # Передаємо помилку далі
    logger.info(f"Created OnlyTeacher for {user.email} with department {department_obj.department_name} and profile link {profile_link}")

def url_exists(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False