# Dockerfile
FROM python:3.12-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# 1. Обновляем pip
RUN pip install --no-cache-dir --upgrade pip

# 2. Устанавливаем основные зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Устанавливаем плагин напрямую из репозитория GitHub
RUN pip install --no-cache-dir "git+https://github.com/pascal65536/minerva-plugin.git@main"

# 4. Копируем исходный код приложения
COPY . .

# Переменные окружения для Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Порт
EXPOSE 5000

# Запуск приложения
CMD ["flask", "run"]