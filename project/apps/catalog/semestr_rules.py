from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.catalog.models import Semestr, Request

def _resolve_academic_year(academic_year: str | None):
    if academic_year:
        return academic_year
    now = timezone.now()
    y = now.year
    return f"{y}/{str(y + 1)[-2:]}" if now.month >= 9 else f"{y - 1}/{str(y)[-2:]}"

def _current_semestr_num() -> int:
    m = timezone.now().month
    return 1 if m in (9, 10, 11, 12, 1, 2) else 2

def _get_semestr(department, academic_year: str):
    return Semestr.objects.filter(
        department=department,
        academic_year=academic_year,
        semestr=_current_semestr_num(),
    ).first()

def assert_can_create_request(teacher, academic_year: str | None = None):
    if not getattr(teacher, "department", None):
        raise ValidationError("У викладача не вказана кафедра.")
    ay = _resolve_academic_year(academic_year)
    sem = _get_semestr(teacher.department, ay)
    if not sem:
        raise ValidationError("Семестр не створений.")
    if not sem.can_student_create_request():
        raise ValidationError("Створення нових запитів заблоковано (дедлайн минув).")
    return sem

def assert_can_cancel_request(req: Request):
    sem = _get_semestr(req.teacher_id.department, req.academic_year)
    if sem and sem.should_lock_cancellations():
        raise ValidationError("Скасування заблоковано.")

def assert_can_complete_request(req: Request):
    sem = _get_semestr(req.teacher_id.department, req.academic_year)
    # Якщо семестр відсутній — забороняємо завершення
    if not sem:
        raise ValidationError("Семестр не створений.")
    if not sem.can_complete_requests():
        raise ValidationError("Завершення ще не дозволено.")

def assert_can_teacher_edit_themes(teacher, academic_year: str | None = None):
    ay = _resolve_academic_year(academic_year)
    sem = _get_semestr(teacher.department, ay)
    if not sem:
        raise ValidationError("Семестр не створений.")
    if sem.should_lock_teacher_editing_themes():
        raise ValidationError("Редагування тем викладачем заблоковано.")
    return sem


def assert_can_create(teacher, academic_year: str | None = None):
    return assert_can_create_request(teacher, academic_year)

def assert_can_complete(req: Request):
    return assert_can_complete_request(req)

def assert_can_cancel(req: Request):
    return assert_can_cancel_request(req)

def assert_can_edit(theme_obj, academic_year: str | None = None):
    return assert_can_teacher_edit_themes(theme_obj, academic_year)