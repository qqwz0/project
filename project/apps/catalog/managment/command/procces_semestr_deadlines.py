import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.catalog.models import Semestr, Request
from django.db.models import Q

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Команда для обробки семестрових дедлайнів.
    - Автоматично відхиляє запити студентів, що очікують, після настання дедлайну.
    - Автоматично блокує редагування тем в активних запитах після настання дедлайну.
    """
    help = 'Processes semester deadlines for student requests and theme editing.'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        self.stdout.write(f"[{now}] Starting semester deadline processing...")

        self.process_student_request_locks(now)
        self.process_theme_editing_locks(now)

        self.stdout.write(f"[{timezone.now()}] Finished semester deadline processing.")

    def process_student_request_locks(self, now):
        """Обробляє блокування створення нових запитів."""
        self.stdout.write("--> Checking for student request deadlines...")
        
        semesters_to_process = Semestr.objects.filter(
            lock_student_requests_date__lte=now.date(),
            student_requests_locked_at__isnull=True
        )
        
        if not semesters_to_process.exists():
            self.stdout.write(self.style.SUCCESS("No new student request deadlines to process."))
            return

        self.stdout.write(f"Found {semesters_to_process.count()} semester(s) to lock student requests.")
        total_rejected = 0
        
        for semestr in semesters_to_process:
            self.stdout.write(f"Processing student lock for: {semestr}...")
            try:
                rejected_count = semestr.apply_student_requests_lock()
                if rejected_count > 0:
                    self.stdout.write(self.style.SUCCESS(f"Rejected {rejected_count} pending requests for {semestr}."))
                    total_rejected += rejected_count
                else:
                    self.stdout.write(self.style.WARNING(f"No pending requests to reject for {semestr}."))
            except Exception as e:
                logger.error(f"Error processing student lock for semester {semestr.id}: {e}", exc_info=True)
                self.stderr.write(self.style.ERROR(f"An error occurred while processing {semestr}: {e}"))
        
        self.stdout.write(f"Total rejected requests: {total_rejected}.")

    def process_theme_editing_locks(self, now):
        """Обробляє блокування редагування тем."""
        self.stdout.write("--> Checking for theme editing deadlines...")

        semesters_to_process = Semestr.objects.filter(
            lock_teacher_editing_themes_date__lte=now.date(),
            teacher_editing_locked_at__isnull=True
        )

        if not semesters_to_process.exists():
            self.stdout.write(self.style.SUCCESS("No new theme editing deadlines to process."))
            return

        self.stdout.write(f"Found {semesters_to_process.count()} semester(s) to lock theme editing.")
        total_locked = 0

        for semestr in semesters_to_process:
            self.stdout.write(f"Processing theme lock for: {semestr}...")
            try:
                # Знаходимо всі активні запити, що відповідають семестру, і де тема ще не заблокована
                requests_to_lock = Request.objects.filter(
                    teacher_id__department=semestr.department,
                    academic_year=semestr.academic_year,
                    request_status='Активний',
                    is_topic_locked=False
                )
                
                updated_count = requests_to_lock.update(is_topic_locked=True)
                
                # Позначаємо семестр як оброблений
                semestr.teacher_editing_locked_at = now
                semestr.save(update_fields=['teacher_editing_locked_at'])

                if updated_count > 0:
                    self.stdout.write(self.style.SUCCESS(f"Locked themes for {updated_count} active requests in {semestr}."))
                    total_locked += updated_count
                else:
                    self.stdout.write(self.style.WARNING(f"No active requests found to lock themes in {semestr}."))
            except Exception as e:
                logger.error(f"Error processing theme lock for semester {semestr.id}: {e}", exc_info=True)
                self.stderr.write(self.style.ERROR(f"An error occurred while processing {semestr}: {e}"))

        self.stdout.write(f"Total themes locked: {total_locked}.")
