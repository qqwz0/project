# Generated manually on 2025-01-18

from django.db import migrations


def fix_department_names_final(apps, schema_editor):
    """
    Виправляє назви кафедр відповідно до правильного шаблону
    """
    Department = apps.get_model('catalog', 'Department')
    OnlyTeacher = apps.get_model('catalog', 'OnlyTeacher')
    OnlyStudent = apps.get_model('catalog', 'OnlyStudent')
    
    print("🔄 Виправлення назв кафедр відповідно до шаблону...")
    
    # Мапінг старих назв на нові правильні назви
    department_fixes = {
        'Сенсорної та напівпровідникової електроніки': 'Сенсорної та напівпровідникової електроніки',
        'Системного проектування': 'Системного проектування',
        'Фізичної та біомедичної електроніки': 'Фізичної та біомедичної електроніки',
        'Радіофізики та комп\'ютерних технологій': 'Радіофізики та комп\'ютерних технологій',
        'Радіоелектронних і комп\'ютерних систем': 'Радіоелектронних і комп\'ютерних систем',
        'Оптоелектроніки та інформаційних технологій': 'Оптоелектроніки та інформаційних технологій',
    }
    
    # Видаляємо тестові кафедри
    test_departments = Department.objects.filter(department_name__startswith='ТЕСТ')
    for test_dept in test_departments:
        print(f"🗑️  Видаляємо тестову кафедру: {test_dept.department_name}")
        test_dept.delete()
    
    # Обробляємо дублікати та виправляємо назви
    updated_count = 0
    created_count = 0
    
    for old_name, new_name in department_fixes.items():
        try:
            # Знаходимо кафедру зі старою назвою
            old_department = Department.objects.filter(department_name=old_name).first()
            
            if old_department:
                # Перевіряємо, чи не існує вже кафедра з новою назвою
                existing_new = Department.objects.filter(department_name=new_name).first()
                
                if existing_new and old_department.id != existing_new.id:
                    # Якщо нова кафедра вже існує, оновлюємо всі посилання на стару
                    print(f"📌 Кафедра '{new_name}' вже існує, оновлюємо посилання...")
                    
                    # Оновлюємо всі посилання на стару кафедру
                    OnlyTeacher.objects.filter(department=old_department).update(department=existing_new)
                    OnlyStudent.objects.filter(department=old_department).update(department=existing_new)
                    
                    # Видаляємо стару кафедру
                    old_department.delete()
                    print(f"✅ Видалено стару кафедру '{old_name}' та оновлено посилання на '{new_name}'")
                    updated_count += 1
                else:
                    # Просто перейменовуємо кафедру
                    old_department.department_name = new_name
                    old_department.save()
                    print(f"✅ Перейменовано кафедру: '{old_name}' → '{new_name}'")
                    updated_count += 1
            else:
                # Якщо старої кафедри немає, створюємо нову
                faculty = Department.objects.first().faculty if Department.objects.exists() else None
                if faculty:
                    Department.objects.get_or_create(
                        department_name=new_name,
                        defaults={'faculty': faculty}
                    )
                    print(f"✅ Створено нову кафедру: '{new_name}'")
                    created_count += 1
                else:
                    print(f"⚠️  Не вдалося створити кафедру '{new_name}' - немає факультету")
                    
        except Exception as e:
            print(f"❌ Помилка при обробці кафедри '{old_name}': {str(e)}")
            continue
    
    print(f"✅ Виправлення завершено! Оновлено: {updated_count}, створено: {created_count}")
    
    # Виводимо поточний список кафедр
    print("\n📋 Фінальний список кафедр:")
    for dept in Department.objects.all().order_by('department_name'):
        print(f"   • {dept.department_name}")


def reverse_fix_department_names_final(apps, schema_editor):
    """
    Відкат змін - повертає старі назви кафедр
    """
    Department = apps.get_model('catalog', 'Department')
    
    print("🔄 Відкат назв кафедр...")
    
    # Зворотний мапінг
    reverse_fixes = {
        'Сенсорної та напівпровідникової електроніки': 'Сенсорної та напівпровідникової електроніки',
        'Системного проектування': 'Системного проектування',
        'Фізичної та біомедичної електроніки': 'Фізичної та біомедичної електроніки',
        'Радіофізики та комп\'ютерних технологій': 'Радіофізики та комп\'ютерних технологій',
        'Радіоелектронних і комп\'ютерних систем': 'Радіоелектронних і комп\'ютерних систем',
        'Оптоелектроніки та інформаційних технологій': 'Оптоелектроніки та інформаційних технологій',
    }
    
    for new_name, old_name in reverse_fixes.items():
        try:
            dept = Department.objects.filter(department_name=new_name).first()
            if dept:
                dept.department_name = old_name
                dept.save()
                print(f"✅ Відкат: '{new_name}' → '{old_name}'")
        except Exception as e:
            print(f"❌ Помилка відкату для '{new_name}': {str(e)}")


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0039_merge_20251001_1011'),
    ]

    operations = [
        migrations.RunPython(fix_department_names_final, reverse_fix_department_names_final),
    ]
