# Generated manually to fix master programs

from django.db import migrations


def remove_invalid_master_programs(apps, schema_editor):
    """Видаляє магістерські програми для спеціальностей, які не є ФЕІ та ФЕМ"""
    Specialty = apps.get_model('catalog', 'Specialty')
    
    # Видаляємо магістерські програми для спеціальностей, які не є ФЕІ (122) та ФЕМ (176)
    deleted_count = Specialty.objects.filter(
        education_level='master'
    ).exclude(
        code__in=['122', '176']
    ).delete()[0]
    
    print(f"Видалено {deleted_count} магістерських програм для спеціальностей, які не є ФЕІ та ФЕМ")


def reverse_remove_invalid_master_programs(apps, schema_editor):
    """Зворотна міграція - відновлює магістерські програми"""
    Specialty = apps.get_model('catalog', 'Specialty')
    Faculty = apps.get_model('catalog', 'Faculty')
    
    # Отримуємо факультет
    faculty = Faculty.objects.first()
    
    # Відновлюємо магістерські програми для всіх спеціальностей
    specialties_to_create = [
        {'code': '121', 'name': 'Інженерія програмного забезпечення', 'education_level': 'master'},
        {'code': '126', 'name': 'Інформаційні системи та технології', 'education_level': 'master'},
        {'code': '171', 'name': 'Електроніка', 'education_level': 'master'},
    ]
    
    for specialty_data in specialties_to_create:
        Specialty.objects.get_or_create(
            code=specialty_data['code'],
            faculty=faculty,
            education_level=specialty_data['education_level'],
            defaults={'name': specialty_data['name']}
        )


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0027_alter_onlystudent_options_remove_faculty_code'),
    ]

    operations = [
        migrations.RunPython(
            remove_invalid_master_programs,
            reverse_remove_invalid_master_programs
        ),
    ]
