from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password
from django.contrib.auth import login, authenticate, get_user_model
from .forms import RegistrationForm
from .models import CustomUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.core.mail import send_mail
from django.conf import settings
import logging
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

def login(request):
    return render(request, 'login.html')

def send_confirmation_email(first_name, last_name, email):
    try:
        # Log the email details for debugging
        logger.debug(f"Надсилаю лист підтвердження на пошту {email}...")
        
        # Send the email
        send_mail(
            'Підтвердження реєстрації',
            f'Вітаю {first_name} {last_name},\n\nДякуємо за реєстрацію на нашій платформі.',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        logger.info(f"Лист успішно надіслано на пошту {email}")
    
    except Exception as e:
        # Log the error
        logger.error(f"Не вийшло надіслати лист на {email}. Помилка: {str(e)}")
        # Optionally, print the error for immediate feedback during development
        print(f"Виникла помилка з надсиланням листа: {e}")


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Get form data and process it
                email = form.cleaned_data['email']
                password = form.cleaned_data['password1']
                role = form.cleaned_data['role']

                # Extract names from the email
                name_part = email.split('@')[0]
                name_parts = name_part.split('.')
                if len(name_parts) != 2:
                    form.add_error('email', "Корпоративна пошта має мати вигляд: ivan.franko@lnu.edu.ua")

                first_name = name_parts[0].capitalize()
                last_name = name_parts[1].capitalize()

                # Handle roles
                if role == 'Студент':
                    academic_group = form.cleaned_data['group']
                    user = CustomUser(
                        email=email,
                        password=make_password(password),
                        role=role,
                        academic_group=academic_group,
                        first_name=first_name,
                        last_name=last_name
                    )
                elif role == 'Викладач':
                    department = form.cleaned_data['department']
                    user = CustomUser(
                        email=email,
                        password=make_password(password),
                        role=role,
                        department=department,
                        first_name=first_name,
                        last_name=last_name
                    )

                user.save()

                send_confirmation_email(first_name, last_name, email)

                return redirect('login')
            except IntegrityError as e:
                # Catch IntegrityError (duplicate email in this case)
                if 'Duplicate entry' in str(e):
                    form.add_error('email', "Цей email вже зареєстрований. Використайте інший email.")
                else:
                    form.add_error(None, f"Трапилася неочікувана помилка: {str(e)}")
            except Exception as e:
                form.add_error(None, f"An error occurred: {str(e)}")
        # If form is not valid, fall through to render form with errors
    else:
        form = RegistrationForm()

    return render(request, 'register.html', {'form': form})

