from io import BytesIO
from urllib.parse import quote as urlquote
from django.http import FileResponse
from docxtpl import DocxTemplate
# from apps.catalog.models import Request
# from django.contrib import messages

def export_requests_to_word(queryset):
    """
    Render requests queryset into a Word document using docxtpl.
    Returns a FileResponse ready for attachment.
    """

    from apps.catalog.models import Request
    from django.contrib import messages

    # Validate uniformity
    years = set(q.academic_year for q in queryset)
    streams = set(q.slot.stream_id.specialty_name for q in queryset)
    if len(years) != 1 or len(streams) != 1:
        raise ValueError('Запити мають бути з одного року й одного потоку.')
    year = years.pop()
    stream = streams.pop()

    # Prepare context
    groups = set(q.student_id.academic_group for q in queryset)
    if len(groups) == 1:
        group = groups.pop()
        group_header = f"групи {group}"
        group_fname = group
    else:
        group_header = "різних груп"
        group_fname = "multiple_groups"

    items = []
    for req in queryset:
        student = req.student_id.get_full_name_with_patronymic().split()[:2]
        theme = (req.approved_student_theme or req.teacher_theme).theme
        ot = req.teacher_id
        lvl = ot.academic_level.lower()
        u = ot.teacher_id
        teacher_str = f"{lvl}. {u.last_name} {u.first_name[:1]}. {(u.patronymic or '')[:1]}."
        items.append({'student': ' '.join(student), 'theme': theme, 'teacher': teacher_str})

    context = {
        'group_display': group_header,
        'stream': stream,
        'department': queryset[0].teacher_id.teacher_id.department.lower(),
        'year': year,
        'items': items,
    }

    tpl_path = 'templates/request_report_template.docx'
    doc = DocxTemplate(tpl_path)
    doc.render(context)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    raw = f"Report_{group_fname}_{stream}_{year}.docx"
    quoted = urlquote(raw)
    response = FileResponse(
        buffer,
        as_attachment=True,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="{raw}"; filename*=UTF-8''{quoted}'
    )
    return response