from django.core.mail import send_mail
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