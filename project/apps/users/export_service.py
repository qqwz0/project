from io import BytesIO
from urllib.parse import quote as urlquote
from django.http import FileResponse
from docxtpl import DocxTemplate
from collections import defaultdict
from django.utils.encoding import iri_to_uri

WORK_TYPE_MAP = {
    # нормалізовані ключі (lowercase, stripped) -> бажаний заголовок (нижній регістр, у потрібному відмінку)
    'курсова': 'курсових',
    'дипломна': 'дипломних',
    'магістерська': 'магістерських',
}

def export_requests_to_word(queryset):
    """
    Render requests queryset into a Word document using docxtpl.
    Returns a FileResponse ready for attachment.
    """

    from apps.catalog.models import Request
    from django.contrib import messages

    if not queryset:
        raise ValueError('Нічого не обрано.')

    # Collect year and specialty (derived from stream) – allow multiple, no hard failure
    years = set(q.academic_year for q in queryset)
    def _specialty_display(stream):
        if getattr(stream, 'specialty', None):
            sp = stream.specialty
            return sp.name or f"{sp.code}"
        return stream.specialty_name or ''

    def _safe_stream(req):
        try:
            return _specialty_display(req.slot.stream_id)
        except Exception:
            return ''

    streams = set(_safe_stream(q) for q in queryset)
    year = years.pop() if len(years) == 1 else ''
    specialty_display = streams.pop() if len(streams) == 1 else ''

    # Departments: якщо кілька кафедр — не вказуємо кафедру у заголовку
    depts = set(
        (q.teacher_id.teacher_id.get_department_name() if q.teacher_id and q.teacher_id.teacher_id else None)
        for q in queryset
    )
    depts = set(d for d in depts if d is not None)
    department = depts.pop().lower() if len(depts) == 1 else ''

    # helper для "людяного" level
    def humanize_work_type(raw):
        if not raw:
            return ''
        key = str(raw).strip().lower()
        return WORK_TYPE_MAP.get(key, raw)

    # Групуємо записи за (group, work_type)
    groups_map = defaultdict(list)
    for req in queryset:
        group = req.student_id.academic_group if req.student_id else None
        work_type = (req.work_type or '').strip()
        groups_map[(group, work_type)].append(req)

    # filename part
    groups_names = set(k[0] for k in groups_map.keys())
    if len(groups_names) == 1:
        only_group = next(iter(groups_names))
        group_fname = only_group or "no_group"
    else:
        group_fname = "multiple_groups"

    # Підготовка структури для шаблона
    groups_list = []
    def sort_key(item):
        (grp, wtype) = item
        return (str(wtype or ''), str(grp or ''))

    for (group_name, work_type) in sorted(groups_map.keys(), key=sort_key):
        rows = []
        for req in groups_map[(group_name, work_type)]:
            # student name (перші 2 слова)
            student = ''
            if req.student_id:
                student = " ".join(req.student_id.get_full_name_with_patronymic().split()[:2])

            theme = (
                (req.topic_name or '').strip()
                or (req.approved_student_theme.theme if getattr(req.approved_student_theme, 'theme', None) else '')
                or (req.teacher_theme.theme if getattr(req.teacher_theme, 'theme', None) else '')
                or (req.custom_student_theme or '')
            )

            # teacher string
            teacher_str = ''
            if req.teacher_id:
                ot = req.teacher_id
                lvl = (ot.academic_level or '').lower()
                u = ot.teacher_id
                if u:
                    teacher_str = f"{lvl}. {u.last_name} {u.first_name[:1]}. {(u.patronymic or '')[:1]}."
                else:
                    teacher_str = f"{lvl}."

            rows.append({'student': student, 'theme': theme, 'teacher': teacher_str})

        groups_list.append({
            'group_name': group_name,
            'group_display': f"групи {group_name}" if group_name else "без групи",
            'rows': rows,
            'level': humanize_work_type(work_type),
            'work_type_raw': work_type,
        })

    context = {
        'groups': groups_list,
        'stream': specialty_display,
        'department': department,
        'year': year,
    }

    tpl_path = 'templates/request_report_template.docx'
    doc = DocxTemplate(tpl_path)
    doc.render(context)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    # Build a safe filename even if fields are blank or mixed
    parts = ["Report", group_fname or "groups", specialty_display or "mixed", str(year or "all")]
    raw_name = "_".join(parts) + ".docx"
    ascii_fallback = "report.docx"  # safe ASCII fallback
    quoted_utf8 = urlquote(raw_name)

    response = FileResponse(
        buffer,
        as_attachment=True,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = (
        f"attachment; filename={ascii_fallback}; filename*=UTF-8''{quoted_utf8}"
    )

    return response