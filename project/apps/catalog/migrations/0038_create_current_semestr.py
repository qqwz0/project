from django.db import migrations
import datetime

def create_current_semestr(apps, schema_editor):
    Department = apps.get_model('catalog', 'Department')
    Semestr = apps.get_model('catalog', 'Semestr')
    today = datetime.date.today()
    year = today.year
    month = today.month

    # Визначаємо навчальний рік та семестр
    if 9 <= month <= 12:
        academic_year = f"{year}/{str(year + 1)[-2:]}"
        semestr_num = 1
    elif 1 <= month <= 2:
        academic_year = f"{year-1}/{str(year)[-2:]}"
        semestr_num = 1
    else:
        academic_year = f"{year-1}/{str(year)[-2:]}"
        semestr_num = 2

    for department in Department.objects.all():
        exists = Semestr.objects.filter(
            department=department,
            academic_year=academic_year,
            semestr=semestr_num
        ).exists()
        if not exists:
            Semestr.objects.create(
                department=department,
                academic_year=academic_year,
                semestr=semestr_num
            )

class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0037_merge_20250929_2313'),  
    ]

    operations = [
        migrations.RunPython(create_current_semestr),
    ]