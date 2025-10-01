# Generated manually on 2025-01-18

from django.db import migrations


def clean_and_set_departments(apps, schema_editor):
    """
    Очищає всі кафедри та встановлює тільки правильні
    """
    Department = apps.get_model('catalog', 'Department')
    OnlyTeacher = apps.get_model('catalog', 'OnlyTeacher')
    OnlyStudent = apps.get_model('catalog', 'OnlyStudent')
    Faculty = apps.get_model('catalog', 'Faculty')
    
    print("🔄 Очищення та встановлення правильних кафедр...")
    
    # Отримуємо факультет
    faculty = Faculty.objects.first()
    if not faculty:
        print("❌ Помилка: Не знайдено жодного факультету!")
        return
    
    # Правильні назви кафедр
    correct_departments = [
        'Системного проектування',
        'Оптоелектроніки та інформаційних технологій',
        'Радіофізики та комп\'ютерних технологій',
        'Радіоелектронних і комп\'ютерних систем',
        'Фізичної та біомедичної електроніки',
        'Сенсорної та напівпровідникової електроніки',
    ]
    
    # Отримуємо всі поточні кафедри
    current_departments = list(Department.objects.all())
    print(f"📋 Поточні кафедри ({len(current_departments)}):")
    for dept in current_departments:
        print(f"   • {dept.department_name}")
    
    # Створюємо правильні кафедри
    created_departments = {}
    for dept_name in correct_departments:
        dept, created = Department.objects.get_or_create(
            department_name=dept_name,
            defaults={'faculty': faculty}
        )
        created_departments[dept_name] = dept
        if created:
            print(f"✅ Створено кафедру: {dept_name}")
        else:
            print(f"📌 Кафедра вже існує: {dept_name}")
    
    # Оновлюємо посилання на правильні кафедри
    # Для викладачів
    teachers_updated = 0
    for teacher in OnlyTeacher.objects.all():
        if teacher.department:
            old_dept_name = teacher.department.department_name
            # Шукаємо відповідну правильну кафедру
            for correct_name, correct_dept in created_departments.items():
                if (old_dept_name.lower() in correct_name.lower() or 
                    correct_name.lower() in old_dept_name.lower() or
                    any(word in correct_name.lower() for word in old_dept_name.lower().split() if len(word) > 3)):
                    teacher.department = correct_dept
                    teacher.save()
                    teachers_updated += 1
                    print(f"🔄 Оновлено викладача: {old_dept_name} → {correct_name}")
                    break
    
    # Для студентів
    students_updated = 0
    for student in OnlyStudent.objects.all():
        if student.department:
            old_dept_name = student.department.department_name
            # Шукаємо відповідну правильну кафедру
            for correct_name, correct_dept in created_departments.items():
                if (old_dept_name.lower() in correct_name.lower() or 
                    correct_name.lower() in old_dept_name.lower() or
                    any(word in correct_name.lower() for word in old_dept_name.lower().split() if len(word) > 3)):
                    student.department = correct_dept
                    student.save()
                    students_updated += 1
                    print(f"🔄 Оновлено студента: {old_dept_name} → {correct_name}")
                    break
    
    # Видаляємо неправильні кафедри
    deleted_count = 0
    for dept in current_departments:
        if dept.department_name not in correct_departments:
            # Перевіряємо, чи немає посилань на цю кафедру
            if not OnlyTeacher.objects.filter(department=dept).exists() and not OnlyStudent.objects.filter(department=dept).exists():
                print(f"🗑️  Видаляємо неправильну кафедру: {dept.department_name}")
                dept.delete()
                deleted_count += 1
            else:
                print(f"⚠️  Кафедра {dept.department_name} має посилання, залишаємо")
    
    print(f"\n✅ Очищення завершено!")
    print(f"   Оновлено викладачів: {teachers_updated}")
    print(f"   Оновлено студентів: {students_updated}")
    print(f"   Видалено кафедр: {deleted_count}")
    
    # Виводимо фінальний список кафедр
    print("\n📋 Фінальний список кафедр:")
    for dept in Department.objects.all().order_by('department_name'):
        print(f"   • {dept.department_name}")


def reverse_clean_and_set_departments(apps, schema_editor):
    """
    Відкат - не потрібно, оскільки ми просто очищаємо та встановлюємо правильні
    """
    print("ℹ️  Відкат не потрібен - просто очищали та встановлювали правильні кафедри")


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0040_fix_department_names_final'),
    ]

    operations = [
        migrations.RunPython(clean_and_set_departments, reverse_clean_and_set_departments),
    ]
