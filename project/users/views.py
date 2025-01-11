from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password
from django.contrib.auth import login, authenticate
from .forms import RegistrationForm
from .models import CustomUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError

def login(request):
    return render(request, 'login.html')


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

