from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.catalog.models import Department, Faculty, OnlyTeacher
from apps.users.services.registration_services import create_teacher_profile
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Тестує реєстрацію викладачів та створення профілів з кафедрами'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Очистити тестові дані перед тестуванням',
        )
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Створити тестові дані (факультет та кафедри)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 ПОЧАТОК ТЕСТУВАННЯ РЕЄСТРАЦІЇ ВИКЛАДАЧІВ'))
        self.stdout.write('=' * 60)
        
        if options['cleanup']:
            self.cleanup_test_data()
        
        if options['create_test_data']:
            self.create_test_data()
        
        # Тестуємо різні сценарії
        self.test_teacher_registration_scenarios()
        
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('✅ ТЕСТУВАННЯ ЗАВЕРШЕНО'))

    def cleanup_test_data(self):
        """Очищає тестові дані"""
        self.stdout.write(self.style.WARNING('🧹 Очищення тестових даних...'))
        
        try:
            # Видаляємо тестових користувачів
            test_users = User.objects.filter(email__contains='test.teacher')
            deleted_users = test_users.count()
            test_users.delete()
            self.stdout.write(f'   Видалено тестових користувачів: {deleted_users}')
            
            # Видаляємо тестові кафедри
            test_departments = Department.objects.filter(department_name__contains='ТЕСТ')
            deleted_deps = test_departments.count()
            test_departments.delete()
            self.stdout.write(f'   Видалено тестових кафедр: {deleted_deps}')
            
            # Видаляємо тестовий факультет
            test_faculty = Faculty.objects.filter(name__contains='ТЕСТ')
            deleted_faculty = test_faculty.count()
            test_faculty.delete()
            self.stdout.write(f'   Видалено тестових факультетів: {deleted_faculty}')
            
            self.stdout.write(self.style.SUCCESS('✅ Очищення завершено'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Помилка очищення: {e}'))

    def create_test_data(self):
        """Створює тестові дані"""
        self.stdout.write(self.style.WARNING('📝 Створення тестових даних...'))
        
        try:
            # Створюємо тестовий факультет
            faculty, created = Faculty.objects.get_or_create(
                name="ТЕСТ Факультет електроніки та інформаційних технологій",
                defaults={'short_name': 'test_electronics'}
            )
            if created:
                self.stdout.write(f'   ✅ Створено факультет: {faculty.name}')
            else:
                self.stdout.write(f'   ℹ️  Факультет вже існує: {faculty.name}')
            
            # Створюємо тестові кафедри
            test_departments = [
                "ТЕСТ Кафедра радіокомп'ютерних систем",
                "ТЕСТ Кафедра радіофізики та комп'ютерних технологій",
                "ТЕСТ Кафедра системного проектування"
            ]
            
            created_deps = 0
            for dep_name in test_departments:
                dep, created = Department.objects.get_or_create(
                    department_name=dep_name,
                    defaults={'faculty': faculty}
                )
                if created:
                    created_deps += 1
                    self.stdout.write(f'   ✅ Створено кафедру: {dep_name}')
            
            self.stdout.write(f'   📊 Створено кафедр: {created_deps}')
            self.stdout.write(self.style.SUCCESS('✅ Тестові дані створено'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Помилка створення тестових даних: {e}'))

    def test_teacher_registration_scenarios(self):
        """Тестує різні сценарії реєстрації викладачів"""
        self.stdout.write(self.style.WARNING('🧪 Тестування сценаріїв реєстрації...'))
        
        # Сценарій 1: Успішна реєстрація з кафедрою
        self.test_successful_registration()
        
        # Сценарій 2: Спроба реєстрації без кафедри
        self.test_registration_without_department()
        
        # Сценарій 3: Реєстрація з неіснуючою кафедрою
        self.test_registration_with_invalid_department()
        
        # Сценарій 4: Перевірка існуючих викладачів без кафедри
        self.check_existing_teachers_without_department()

    def test_successful_registration(self):
        """Тестує успішну реєстрацію викладача з кафедрою"""
        self.stdout.write('\n📋 Сценарій 1: Успішна реєстрація з кафедрою')
        
        try:
            # Отримуємо тестову кафедру
            department = Department.objects.filter(department_name__contains='ТЕСТ').first()
            if not department:
                self.stdout.write(self.style.ERROR('   ❌ Немає тестових кафедр для тестування'))
                return
            
            # Створюємо тестового користувача
            test_email = 'test.teacher.success@lnu.edu.ua'
            
            # Видаляємо якщо існує
            User.objects.filter(email=test_email).delete()
            
            user = User.objects.create_user(
                email=test_email,
                first_name='Тестовий',
                last_name='Викладач',
                patronymic='Успішний',
                role='Викладач'
            )
            
            # Тестуємо створення профілю
            create_teacher_profile(user, 'Доцент', department)
            
            # Перевіряємо результат
            teacher_profile = user.get_profile()
            if teacher_profile:
                if teacher_profile.department:
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Профіль створено успішно'))
                    self.stdout.write(f'   📊 Кафедра: {teacher_profile.department.department_name}')
                    self.stdout.write(f'   📊 Посада: {teacher_profile.academic_level}')
                else:
                    self.stdout.write(self.style.ERROR('   ❌ Профіль створено, але кафедра не призначена'))
                    self.stdout.write(f'   📊 Посада: {teacher_profile.academic_level}')
            else:
                self.stdout.write(self.style.ERROR('   ❌ Профіль не створено'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Помилка: {e}'))

    def test_registration_without_department(self):
        """Тестує спробу реєстрації без кафедри"""
        self.stdout.write('\n📋 Сценарій 2: Спроба реєстрації без кафедри')
        
        try:
            test_email = 'test.teacher.no.department@lnu.edu.ua'
            
            # Видаляємо якщо існує
            User.objects.filter(email=test_email).delete()
            
            user = User.objects.create_user(
                email=test_email,
                first_name='Тестовий',
                last_name='Викладач',
                patronymic='БезКафедри',
                role='Викладач'
            )
            
            # Спроба створити профіль без кафедри
            try:
                create_teacher_profile(user, 'Доцент', None)
                self.stdout.write(self.style.ERROR('   ❌ Помилка: профіль створено без кафедри!'))
            except ValueError as e:
                self.stdout.write(self.style.SUCCESS(f'   ✅ Правильно відхилено: {e}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Неочікувана помилка: {e}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Помилка: {e}'))

    def test_registration_with_invalid_department(self):
        """Тестує реєстрацію з неіснуючою кафедрою"""
        self.stdout.write('\n📋 Сценарій 3: Реєстрація з неіснуючою кафедрою')
        
        try:
            test_email = 'test.teacher.invalid.department@lnu.edu.ua'
            
            # Видаляємо якщо існує
            User.objects.filter(email=test_email).delete()
            
            user = User.objects.create_user(
                email=test_email,
                first_name='Тестовий',
                last_name='Викладач',
                patronymic='НеіснуючаКафедра',
                role='Викладач'
            )
            
            # Створюємо фейкову кафедру
            fake_department = type('FakeDepartment', (), {'department_name': 'Неіснуюча кафедра'})()
            
            try:
                create_teacher_profile(user, 'Доцент', fake_department)
                self.stdout.write(self.style.ERROR('   ❌ Помилка: профіль створено з неіснуючою кафедрою!'))
            except Exception as e:
                self.stdout.write(self.style.SUCCESS(f'   ✅ Правильно відхилено: {str(e)[:100]}...'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Помилка: {e}'))

    def check_existing_teachers_without_department(self):
        """Перевіряє існуючих викладачів без кафедри"""
        self.stdout.write('\n📋 Сценарій 4: Перевірка існуючих викладачів без кафедри')
        
        try:
            # Знаходимо викладачів без кафедри
            teachers_without_department = OnlyTeacher.objects.filter(department__isnull=True)
            count = teachers_without_department.count()
            
            if count > 0:
                self.stdout.write(self.style.WARNING(f'   ⚠️  Знайдено {count} викладачів без кафедри:'))
                for teacher in teachers_without_department[:5]:  # Показуємо перших 5
                    self.stdout.write(f'      - {teacher.teacher_id.get_full_name_with_patronymic()} ({teacher.teacher_id.email})')
                if count > 5:
                    self.stdout.write(f'      ... та ще {count - 5} викладачів')
            else:
                self.stdout.write(self.style.SUCCESS('   ✅ Всі викладачі мають призначені кафедри'))
            
            # Показуємо загальну статистику
            total_teachers = OnlyTeacher.objects.count()
            self.stdout.write(f'   📊 Загалом викладачів: {total_teachers}')
            self.stdout.write(f'   📊 Без кафедри: {count}')
            self.stdout.write(f'   📊 З кафедрою: {total_teachers - count}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Помилка: {e}'))

    def show_department_statistics(self):
        """Показує статистику по кафедрах"""
        self.stdout.write('\n📊 СТАТИСТИКА ПО КАФЕДРАХ:')
        
        try:
            departments = Department.objects.all()
            for dep in departments:
                teacher_count = OnlyTeacher.objects.filter(department=dep).count()
                self.stdout.write(f'   {dep.department_name}: {teacher_count} викладачів')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Помилка отримання статистики: {e}'))
