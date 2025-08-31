FROM python:3.11-slim

WORKDIR /app

# Встановлення системних залежностей
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Копіювання requirements.txt спочатку для кращого кешування
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіювання проекту
COPY . .

# Встановлення робочої директорії
WORKDIR /app/project

# Створення користувача для безпеки
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Збірка статичних файлів
RUN python manage.py collectstatic --noinput

# Відкриття порту
EXPOSE 8000

# Запуск додатку
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]