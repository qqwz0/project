from django.core.mail import send_mail
import threading
import datetime
import logging

logger = logging.getLogger(__name__)

def send_email_async(subject, message, from_email, recipient_list, html_message):
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=True,
        )
        logger.info(f"Email sent to {recipient_list}")
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")

def send_email_in_thread(subject, body, from_email, recipient_list, html_message):
    def _send():
        try:
            send_email_async(subject, body, from_email, recipient_list, html_message)
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()
    
def get_short_file_name(file_name):
    name_parts = file_name.rsplit('.', 1)
    base = name_parts[0]
    ext = name_parts[1] if len(name_parts) > 1 else ''
    if '_' in base:
        short_base = base.rsplit('_', 1)[0]
    else:
        short_base = base
    return f"{short_base}.{ext}" if ext else short_base

def get_group_name(user_id):
    return f'user_{user_id}'

def get_now_str():
    return datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
