from urllib.parse import urlencode
from django.conf import settings
import requests
import logging
from django.contrib import messages
from django.shortcuts import redirect
from django.core.exceptions import ValidationError
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
        
        # Автоматично створюємо запити для студента, якщо він є в мапінгу
        create_automatic_requests_for_student(user, group_code)
        
    except Group.DoesNotExist:
        logger.warning(f"Group {group_code} not found for {email}, creating new group.")
        # Створюємо нову групу замість використання fallback
        try:
            # Знаходимо відповідний потік для групи
            from apps.catalog.models import Stream
            
            # Парсимо код групи щоб знайти потік
            # Наприклад: ФЕП-22ВПК -> потік ФЕП-2м
            if '-' in group_code:
                faculty_code = group_code.split('-')[0]  # ФЕП
                course_and_group = group_code.split('-')[1]  # 22ВПК
                
                # Витягуємо курс (перша цифра)
                course = course_and_group[0] if course_and_group and course_and_group[0].isdigit() else '1'
                stream_code = f"{faculty_code}-{course}м"
                
                # Знаходимо або створюємо потік
                stream, created = Stream.objects.get_or_create(
                    stream_code=stream_code,
                    defaults={
                        'faculty': faculty,
                        'course': int(course),
                        'education_level': 'master' if 'м' in stream_code.lower() else 'bachelor'
                    }
                )
                
                if created:
                    logger.info(f"Created new stream: {stream_code}")
                
                # Створюємо нову групу
                group_obj = Group.objects.create(
                    group_code=group_code,
                    stream=stream
                )
                logger.info(f"Created new group: {group_code}")
                
                OnlyStudent.objects.create(student_id=user, group=group_obj, faculty=faculty, department=department)
                logger.info(f"Created OnlyStudent for {email} with new group {group_code} and department {department}")
                
                # Автоматично створюємо запити для студента, якщо він є в мапінгу
                create_automatic_requests_for_student(user, group_code)
                
            else:
                logger.error(f"Invalid group code format: {group_code}")
                raise ValidationError(f"Неправильний формат групи: {group_code}. Використовуйте формат ФЕС-21, ФЕП-22ВПК тощо.")
                
        except Exception as e:
            logger.error(f"Failed to create new group {group_code}: {e}")
            # Не використовуємо fallback - викидаємо помилку
            raise ValidationError(f"Не вдалося створити групу {group_code}. Перевірте правильність написання.")


def create_automatic_requests_for_student(user, group_code):
    """
    Автоматично створює запити для студента на основі StudentRequestMapping
    """
    from apps.users.models import StudentExcelMapping, StudentRequestMapping
    from apps.catalog.models import Request, TeacherTheme, Slot, Stream
    from apps.users.models import CustomUser
    
    try:
        # Шукаємо студента в мапінгу
        logger.info(f"Looking for mapping for student: {user.get_full_name_with_patronymic()}, group: {group_code}")
        
        # Спочатку шукаємо без групи, щоб перевірити чи є студент в мапінгу взагалі
        student_mapping = StudentExcelMapping.objects.filter(
            last_name__icontains=user.last_name,
            first_name__icontains=user.first_name
        ).first()
        
        if not student_mapping and user.patronymic:
            logger.info(f"Trying with patronymic: {user.patronymic}")
            student_mapping = StudentExcelMapping.objects.filter(
                last_name__icontains=user.last_name,
                first_name__icontains=user.first_name,
                patronymic__icontains=user.patronymic
            ).first()
        
        # Якщо знайшли студента, перевіряємо групу
        if student_mapping:
            if student_mapping.group != group_code:
                logger.warning(f"Student {student_mapping.full_name} found but group mismatch: mapping has '{student_mapping.group}', registration has '{group_code}'")
                # Спробуємо знайти з правильною групою
                student_mapping = StudentExcelMapping.objects.filter(
                    last_name__icontains=user.last_name,
                    first_name__icontains=user.first_name,
                    group=group_code
                ).first()
                
                if not student_mapping and user.patronymic:
                    student_mapping = StudentExcelMapping.objects.filter(
                        last_name__icontains=user.last_name,
                        first_name__icontains=user.first_name,
                        patronymic__icontains=user.patronymic,
                        group=group_code
                    ).first()
        
        if not student_mapping:
            logger.info(f"No mapping found for student {user.get_full_name_with_patronymic()}")
            # Логуємо всі доступні мапінги для діагностики
            all_mappings = StudentExcelMapping.objects.filter(group=group_code)
            logger.info(f"Available mappings for group {group_code}: {list(all_mappings.values('last_name', 'first_name', 'patronymic', 'department'))}")
            return None
        
        logger.info(f"Found mapping for student: {student_mapping.full_name}, department: {student_mapping.department}")
        
        # Автоматично призначаємо кафедру студенту
        if student_mapping.department:
            from apps.catalog.models import Department
            
            # Мапінг скорочень кафедр до повних назв
            DEPARTMENT_MAPPING = {
                'РКС': 'Радіоелектронних і комп\'ютерних систем',
                'РКТ': 'Радіофізики та комп\'ютерних технологій', 
                'СП': 'Системного проектування',
                'КОІТ': 'Оптоелектроніки та інформаційних технологій',
                'СНПЕ': 'Сенсорної та напівпровідникової електроніки',
                'ФБМЕ': 'Фізичної та біомедичної електроніки',
            }
            
            department_name = DEPARTMENT_MAPPING.get(student_mapping.department, student_mapping.department)
            try:
                department = Department.objects.get(department_name__iexact=department_name)
                student_profile = user.get_profile()
                if student_profile:
                    # Перевіряємо, чи кафедра ще не призначена
                    if not student_profile.department:
                        student_profile.department = department
                        student_profile.save()
                        logger.info(f"Assigned department {department.department_name} to student {user.get_full_name_with_patronymic()}")
                    else:
                        logger.info(f"Student {user.get_full_name_with_patronymic()} already has department {student_profile.department.department_name}")
            except Department.DoesNotExist:
                logger.warning(f"Department {department_name} (mapped from {student_mapping.department}) not found")
        
        # Шукаємо запити для створення
        student_requests = StudentRequestMapping.objects.filter(
            student_name__icontains=user.get_full_name_with_patronymic()
        )
        
        logger.info(f"Found {student_requests.count()} request mappings for student {user.get_full_name_with_patronymic()}")
        
        for request_mapping in student_requests:
            try:
                # Знаходимо викладача
                teacher_user = CustomUser.objects.get(email=request_mapping.teacher_email, role='Викладач')
                teacher_profile = teacher_user.catalog_teacher_profile
                
                # Знаходимо потік
                stream = Stream.objects.get(stream_code=request_mapping.stream)
                
                # Знаходимо тему викладача
                teacher_theme = TeacherTheme.objects.filter(
                    teacher_id=teacher_profile,
                    theme__icontains=request_mapping.theme
                ).first()
                
                if not teacher_theme:
                    # Створюємо тему, якщо її немає
                    teacher_theme = TeacherTheme.objects.create(
                        teacher_id=teacher_profile,
                        theme=request_mapping.theme,
                        theme_description=request_mapping.theme_description,
                        is_active=True,
                        is_occupied=True
                    )
                    # Додаємо тему до потоку
                    teacher_theme.streams.add(stream)
                
                # Знаходимо слот
                slot = Slot.objects.filter(
                    teacher_id=teacher_profile,
                    stream_id=stream
                ).first()
                
                if not slot:
                    logger.warning(f"No slot found for teacher {teacher_profile} and stream {stream}")
                    continue
                
                # Перевіряємо чи є вільні місця
                if slot.occupied >= slot.quota:
                    logger.warning(f"Slot for teacher {teacher_profile} and stream {stream} is full")
                    continue
                
                # Створюємо запит
                request_obj, created = Request.objects.get_or_create(
                    teacher_id=teacher_profile,
                    student_id=user,
                    teacher_theme=teacher_theme,
                    defaults={
                        'request_status': 'Активний',
                        'motivation_text': f'Автоматично створений запит для теми: {request_mapping.theme}',
                        'slot': slot,
                        'topic_name': request_mapping.theme,
                        'topic_description': request_mapping.theme_description
                    }
                )
                
                if created:
                    # Оновлюємо зайнятість слота
                    slot.occupied += 1
                    slot.save()
                    
                    # Позначаємо тему як зайняту
                    teacher_theme.is_occupied = True
                    teacher_theme.save()
                    
                    logger.info(f"Created automatic request for student {user.get_full_name_with_patronymic()} with theme {request_mapping.theme}")
                    return request_obj  # Повертаємо створений запит
                
            except Exception as e:
                logger.error(f"Error creating automatic request for student {user.get_full_name_with_patronymic()}: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error in create_automatic_requests_for_student: {str(e)}")
    
    return None  # Повертаємо None, якщо запит не було створено


def create_teacher_profile(user, job_title, department_obj):
    """
    Створює профіль викладача з Department об'єктом
    """
    from apps.catalog.models import OnlyTeacher

    # Перевіряємо, що кафедра передана
    if not department_obj:
        logger.error(f"Cannot create teacher profile for {user.email}: department is None")
        raise ValueError("Department is required for teacher profile creation")

    academic_level = job_title if job_title else "Викладач"
    faculty_short_name = department_obj.faculty.short_name if department_obj.faculty else "unknown"
    
    logger.info(f"Creating teacher profile for {user.email} with department: {department_obj.department_name}")

    # Формуємо базовий profile_link
    email = user.email.split('@')[0]  # take only the "first.last" part
    first_name, last_name = email.split('.')  # split into first and last
    first_initial = first_name[0]  # take first letter of first name
    base_link = f"{last_name}-{first_initial}"


    # Формуємо повне посилання
    full_url = f"https://{faculty_short_name}.lnu.edu.ua/employee/{base_link}"

    if url_exists(full_url):
        profile_link = full_url
    else:
        profile_link = None

    try:
        teacher_profile, created = OnlyTeacher.objects.get_or_create(
            teacher_id=user,
            defaults={
                'academic_level': academic_level,
                'department': department_obj,
                'profile_link': profile_link
            }
        )
        
        # Якщо профіль вже існує, оновлюємо його
        if not created:
            teacher_profile.academic_level = academic_level
            teacher_profile.department = department_obj
            teacher_profile.profile_link = profile_link
            teacher_profile.save()
            logger.info(f"Updated OnlyTeacher for {user.email} with department {department_obj.department_name}")
        else:
            logger.info(f"Created OnlyTeacher for {user.email} with department {department_obj.department_name}")
        return teacher_profile
    except Exception as e:
        logger.error(f"Error creating OnlyTeacher for user {user.email}: {str(e)}", exc_info=True)
        raise  # Передаємо помилку далі

def url_exists(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        print(f"Checked URL: {url} - Status Code: {response.status_code}")
        return response.status_code == 200
    except requests.RequestException:
        return False