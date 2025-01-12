from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
import logging
from .forms import RegistrationForm
from .models import CustomUser

logger = logging.getLogger(__name__)

def login(request):
    return render(request, 'login.html')

def send_confirmation_email(user):
    try:
        # Generate confirmation token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(str(user.pk).encode())

        email_body = (
            f"Шановний(а) {user.first_name} {user.last_name},\n\n"
            f"Дякуємо за реєстрацію! Щоб підтвердити ваш обліковий запис, "
            f"перейдіть за посиланням нижче:\n\n"
            f"http://localhost:8000/users/confirm/{uid}/{token}/\n\n"
            f"Якщо ви не реєструвалися на нашому сайті, проігноруйте цей лист.\n\n"
            f"З повагою,\nКоманда підтримки."
        )

        send_mail(
            subject='Підтвердження реєстрації',
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Лист підтвердження надіслано {user.email}")
    except Exception as e:
        logger.error(f"Не вийшло надіслати лист до {user.email}. Помилка: {e}")

def confirm_registration(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = get_object_or_404(CustomUser, pk=uid)

        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save()
            return render(request, 'success.html')
        else:
            return render(request, 'fail.html')
    except Exception as e:
        logger.error(f"Помилка підтвердження: {e}")
        return HttpResponse("Виникла помилка під час підтвердження.")

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                email = form.cleaned_data['email'].lower()
                password = form.cleaned_data['password1']
                role = form.cleaned_data['role']

                # Extract names from the email
                name_part = email.split('@')[0]
                name_parts = name_part.split('.')
                if len(name_parts) != 2:
                    form.add_error('email', "Корпоративна пошта має мати вигляд: ivan.franko@lnu.edu.ua")
                first_name = name_parts[0].capitalize()
                last_name = name_parts[1].capitalize()

                if role == 'Студент':
                    academic_group = form.cleaned_data.get('group')
                    user = CustomUser(
                        email=email,
                        password=make_password(password),
                        role=role,
                        academic_group=academic_group,
                        first_name=first_name,
                        last_name=last_name,
                        is_active=False
                    )
                elif role == 'Викладач':
                    department = form.cleaned_data.get('department')
                    user = CustomUser(
                        email=email,
                        password=make_password(password),
                        role=role,
                        department=department,
                        first_name=first_name,
                        last_name=last_name,
                        is_active=False
                    )

                user.save()
                send_confirmation_email(user)

                return redirect('login')
            except IntegrityError as e:
                if 'Duplicate entry' in str(e):
                    form.add_error('email', "Цей email вже зареєстрований.")
                else:
                    form.add_error(None, f"Трапилася неочікувана помилка: {str(e)}")
            except Exception as e:
                logger.error(f"Помилка реєстрації: {e}")
                form.add_error(None, "Виникла помилка при обробці даних.")
    else:
        form = RegistrationForm()

    return render(request, 'register.html', {'form': form})
