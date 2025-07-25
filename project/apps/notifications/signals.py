from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.catalog.models import Request, RequestFile, FileComment
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db import transaction
from .models import Message
from django.template.loader import render_to_string
from .utils import send_email_in_thread, get_group_name, get_now_str
from django.urls import reverse
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

ROLE_TEACHER = 'Викладач'
ROLE_STUDENT = 'Студент'

@receiver(post_save, sender=Request)
def send_notification_on_request(sender, instance, created, **kwargs):
    """
    Handles notification when a student creates a new request.

    Args:
        sender: The model class.
        instance: The actual instance being saved.
        created: Boolean; True if a new record was created.
        **kwargs: Additional keyword arguments.
    """
    logger.info(f"Checking if new request was created: {instance.pk}")
    channel_layer = get_channel_layer()
    if created:
        try:
            teacher_user = instance.teacher_id.teacher_id
            student = instance.student_id
            student_name = f"{student.first_name} {student.last_name}"
            message = f"Ви отримали запит від студента {student_name}! 📩"
            time = get_now_str()
            notification = f"Новий запит від {student_name}"
            profile_url = f"{settings.BASE_URL}{reverse('profile')}"
            student_profile_url = f"{settings.BASE_URL}{reverse('profile_detail', args=[student.pk])}"
            context = {
                'student_name': student_name,
                'profile_url': profile_url,
                'student_profile_url': student_profile_url,
                'time': time
            }
            html_message = render_to_string('notifications/new_request.html', context)

            def create_message():
                """
                Creates a message, sends email and websocket notification to the teacher.
                """
                Message.objects.create(
                    message_text=message,
                    recipient=teacher_user,
                    sender=student,
                    created_at=time,
                    related_request=instance
                )
                event = {
                    "type": "send_notification",
                    "notification": notification,
                    'time': time,
                }
                send_email_in_thread(
                    f'Новий запит від студента {student_name}',
                    '',
                    'vasylhlova24@gmail.com',
                    [teacher_user.email],
                    html_message
                )
                group_name = get_group_name(teacher_user.pk)
                logger.info(f"Sending notification to teacher group: {group_name}")
                async_to_sync(channel_layer.group_send)(group_name, event)

            transaction.on_commit(create_message)
        except Exception as e:
            logger.error(f"Failed to send teacher notification: {str(e)}")

@receiver(post_save, sender=RequestFile)
def send_notification_on_file_upload(sender, instance, created, **kwargs):
    """
    Handles notification when a file is uploaded to a request.

    Args:
        sender: The model class.
        instance: The actual instance being saved.
        created: Boolean; True if a new record was created.
        **kwargs: Additional keyword arguments.
    """
    logger.info(f"Checking if new file was uploaded: {instance.pk}")
    channel_layer = get_channel_layer()
    if created:
        try:
            uploader = instance.uploaded_by
            if uploader.role == ROLE_TEACHER:
                another_user = instance.request.student_id
            elif uploader.role == ROLE_STUDENT:
                another_user = instance.request.teacher_id.teacher_id
            else:
                logger.warning("Unknown uploader role")
                return

            request_id = instance.request
            uploader_name = f"{uploader.first_name} {uploader.last_name}"
            short_file_name = instance.get_filename()
            message = f"{uploader_name} завантажив файл {short_file_name} до вашої роботи! 📎"
            time = get_now_str()
            download_url = f"{settings.BASE_URL}{reverse('download_file', args=[instance.pk])}"
            notification = f"Новий файл в вашій роботі"
            profile_url = f"{settings.BASE_URL}{reverse('profile')}"
            context = {
                'uploader_name': uploader_name,
                'profile_url': profile_url,
                'file_name': short_file_name,
                'download_url': download_url,
                'time': time
            }
            html_message = render_to_string('notifications/new_file.html', context)

            def create_message():
                """
                Creates a message, sends email and websocket notification to the other user.
                """
                Message.objects.create(
                    message_text=message,
                    recipient=another_user,
                    sender=uploader,
                    created_at=time,
                    related_request=request_id
                )
                event = {
                    "type": "send_notification",
                    "notification": notification,
                    'time': time,
                }
                send_email_in_thread(
                    f'{uploader_name} завантажив новий файл до роботи!',
                    '',
                    'vasylhlova24@gmail.com',
                    [another_user.email],
                    html_message
                )
                group_name = get_group_name(another_user.pk)
                logger.info(f"Sending notification to group: {group_name}")
                async_to_sync(channel_layer.group_send)(group_name, event)

            transaction.on_commit(create_message)
        except Exception as e:
            logger.error(f"Failed to send file upload notification: {str(e)}")

@receiver(pre_save, sender=Request)
def send_notification_on_request_status_changed(sender, instance, **kwargs):
    """
    Handles notification when the status of a request changes (except 'Завершено').

    Args:
        sender: The model class.
        instance: The actual instance being saved.
        **kwargs: Additional keyword arguments.
    """
    logger.info(f"Checking if request status was changed: {instance.pk}")
    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old_instance.request_status != instance.request_status and instance.request_status != 'Завершено':
        try:
            channel_layer = get_channel_layer()
            student_user = instance.student_id
            teacher_user = instance.teacher_id.teacher_id
            status_text = "відхилив" if instance.request_status == "Відхилено" else "прийняв"
            teacher_name = f"{teacher_user.first_name} {teacher_user.last_name}"
            emoji = "✅" if status_text == "прийняв" else "❌"
            message = f"{teacher_name} {status_text} ваш запит! {emoji}"
            rejected_reason = instance.rejected_reason if status_text == "відхилив" else None
            time = get_now_str()
            notification = f"{teacher_name} відповів на ваш запит"
            profile_url = f"{settings.BASE_URL}{reverse('profile')}"
            catalog_url = f"{settings.BASE_URL}{reverse('teachers_catalog')}"
            context = {
                'teacher_name': teacher_name,
                'status_text': status_text,
                'rejected_reason': rejected_reason,
                'profile_url': profile_url,
                'catalog_url': catalog_url,
                'time': time
            }
            html_message = render_to_string('notifications/request_status_changed.html', context)
            send_email_in_thread(
                f'Увага! Нове повідомлення від викладача {teacher_name}',
                '',
                'vasylhlova24@gmail.com',
                [student_user.email],
                html_message
            )
            Message.objects.create(
                message_text=message,
                recipient=student_user,
                sender=teacher_user,
                created_at=time,
                status=status_text,
                related_request=instance
            )
            event = {
                "type": "send_notification",
                "notification": notification,
                'time': time
            }
            group_name = get_group_name(student_user.pk)
            logger.info(f"Sending notification to student group: {group_name}")
            async_to_sync(channel_layer.group_send)(group_name, event)
        except Exception as e:
            logger.error(f"Failed to send student notification: {str(e)}")

@receiver(pre_save, sender=Request)
def send_notification_on_work_status_changed(sender, instance, **kwargs):
    """
    Handles notification when the grade of a request changes.

    Args:
        sender: The model class.
        instance: The actual instance being saved.
        **kwargs: Additional keyword arguments.
    """
    logger.info(f"Checking if work status was changed: {instance.pk}")
    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old_instance.grade != instance.grade:
        try:
            channel_layer = get_channel_layer()
            student_user = instance.student_id
            teacher_user = instance.teacher_id.teacher_id
            grade = instance.grade
            teacher_name = f"{teacher_user.first_name} {teacher_user.last_name}"
            message = f"Викладач {teacher_name} завершив перевірку вашої роботи та виставив оцінку: {grade}.🎓"
            time = get_now_str()
            notification = "Ваша робота завершена та оцінена!"
            profile_url = f"{settings.BASE_URL}{reverse('profile')}"
            context = {
                'teacher_name': teacher_name,
                'grade': grade,
                'profile_url': profile_url,
                'time': time
            }
            html_message = render_to_string('notifications/work_status_changed.html', context)
            send_email_in_thread(
                f'Увага! Нове повідомлення від викладача {teacher_name}',
                '',
                'vasylhlova24@gmail.com',
                [student_user.email],
                html_message
            )
            Message.objects.create(
                message_text=message,
                recipient=student_user,
                sender=teacher_user,
                created_at=time,
                related_request=instance,
            )
            event = {
                "type": "send_notification",
                "notification": notification,
                'time': time
            }
            group_name = get_group_name(student_user.pk)
            logger.info(f"Sending notification to student group: {group_name}")
            async_to_sync(channel_layer.group_send)(group_name, event)
        except Exception as e:
            logger.error(f"Failed to send student notification: {str(e)}")

@receiver(post_save, sender=FileComment)
def send_notification_on_comment(sender, instance, created, **kwargs):
    """
    Handles notification when a comment is added to a file.

    Args:
        sender: The model class.
        instance: The actual instance being saved.
        created: Boolean; True if a new record was created.
        **kwargs: Additional keyword arguments.
    """
    logger.info(f"Checking if new comment was added: {instance.pk}")
    channel_layer = get_channel_layer()
    if created:
        try:
            request_id = instance.file.request
            author = instance.author
            if author.role == ROLE_TEACHER:
                another_user = instance.file.request.student_id
            elif author.role == ROLE_STUDENT:
                another_user = instance.file.request.teacher_id.teacher_id
            else:
                logger.warning("Unknown author role")
                return

            short_file_name = instance.file.get_filename()
            author_name = f"{author.first_name} {author.last_name}"
            message = f"{author_name} залишив коментар до файлу {short_file_name}! 💬"
            time = get_now_str()
            notification = f"Новий коментар до вашого файлу!"

            def create_message():
                """
                Creates a message and sends websocket notification to the other user.
                """
                Message.objects.create(
                    message_text=message,
                    recipient=another_user,
                    sender=author,
                    created_at=time,
                    related_request=request_id
                )
                event = {
                    "type": "send_notification",
                    "notification": notification,
                    'time': time,
                }
                group_name = get_group_name(another_user.pk)
                logger.info(f"Sending notification to group: {group_name}")
                async_to_sync(channel_layer.group_send)(group_name, event)

            transaction.on_commit(create_message)
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")