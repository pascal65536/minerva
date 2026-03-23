"""
Файл my_script.py для исследования

Тестовый скрипт для лабораторной работы по статическому
анализу кода.
Содержит намеренно внесённые ошибки и уязвимости.
"""

import os
import sys
import pickle
import sqlite3
import subprocess
import json
import base64

# Обширный импорт
from behoof import *

# Обширный импорт
from ipdb import *

# Неиспользуемый импорт
import math

# Hardcoded секрет (уязвимость безопасности)
SECRET_KEY = "my_super_secret_password_123"


class UserManager:
    def __init__(self, db_path="users.db"):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        # Уязвимость: отсутствие проверки пути к БД
        self.conn = sqlite3.connect(self.db_path)

    def create_table(self):
        if not self.conn:
            self.connect()
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                email TEXT
            )
        """
        )

    def add_user(self, username, email):
        if not self.conn:
            self.connect()
        # Уязвимость: SQL-инъекция (небезопасная подстановка)
        query = f"INSERT INTO users (username, email) VALUES ('{username}', '{email}')"
        self.conn.execute(query)
        self.conn.commit()

    def get_user(self, user_id):
        if not self.conn:
            self.connect()
        # Уязвимость: отсутствие валидации user_id
        cursor = self.conn.execute(f"SELECT * FROM users WHERE id = {user_id}")
        return cursor.fetchone()

    def close(self):
        if self.conn:
            self.conn.close()


# Небезопасная функция: eval
def run_user_code(code_str):
    # Уязвимость: использование eval с пользовательским вводом
    return eval(code_str)


# Небезопасная десериализация
def load_user_data(data_file):
    with open(data_file, "rb") as f:
        # Уязвимость: небезопасный pickle
        return pickle.load(f)


# Функция с неинициализированной переменной
def buggy_function(x):
    if x > 0:
        result = x * 2
    # ОШИБКА: result может быть не определён
    print(result)


# Функция с утечкой файла
def read_config(filename):
    f = open(filename, "r")  # Утечка: файл не закрывается
    return f.read()


# Функция без аннотаций типов (для mypy)
def calculate_area(width, height):
    return width * height


# Неиспользуемая функция
def unused_function():
    return "This function is never called"


# Нарушение PEP 8: длинная строка
def long_line_function():
    return "This is a very long line that exceeds the recommended 79 or even 88 character limit and should be wrapped properly but it is not"


# Функция с потенциальным IndexError
def get_item(lst, index):
    return lst[index]  # Нет проверки границ


# Функция с потенциальным KeyError
def get_user_email(user_dict):
    return user_dict["email"]  # Нет проверки ключа


# Уязвимость: выполнение команды через subprocess без валидации
def run_system_command(cmd):
    # Уязвимость: shell=True + пользовательский ввод
    return subprocess.check_output(cmd, shell=True)


# Функция с небезопасным base64 decode
def decode_token(token):
    try:
        decoded = base64.b64decode(token)
        return json.loads(decoded)
    except Exception as e:
        print("Error:", e)
        return None


# Главная функция
def main():
    print("=== Старт тестового скрипта ===")

    # 1. Работа с пользователем
    user_input = input("Введите выражение для вычисления: ")
    try:
        result = run_user_code(user_input)  # Опасно!
        print("Результат:", result)
    except Exception as e:
        print("Ошибка при вычислении:", e)

    # 2. Работа с БД
    db = UserManager()
    db.create_table()
    username = input("Введите имя пользователя: ")
    email = input("Введите email: ")
    db.add_user(username, email)  # SQL-инъекция!

    user_id_input = input("Введите ID пользователя для поиска: ")
    user = db.get_user(user_id_input)  # SQL-инъекция!
    print("Найден пользователь:", user)

    db.close()

    # 3. Неинициализированная переменная
    try:
        buggy_function(-5)  # Вызовет NameError
    except NameError as e:
        print("Ошибка неинициализированной переменной:", e)

    # 4. Чтение конфига (утечка файла)
    try:
        config = read_config("config.txt")
        print("Конфиг:", config[:50])
    except FileNotFoundError:
        print("Файл config.txt не найден")

    # 5. Небезопасная десериализация
    try:
        data = load_user_data("user_data.pkl")  # Опасно!
        print("Загружены данные:", data)
    except FileNotFoundError:
        print("Файл user_data.pkl не найден")

    # 6. Пример работы с индексом
    my_list = [1, 2, 3]
    idx = int(input("Введите индекс списка: "))
    try:
        print("Элемент:", get_item(my_list, idx))  # Может вызвать IndexError
    except IndexError:
        print("Индекс вне диапазона")

    # 7. Пример с словарём
    user_info = {"name": "Alice"}
    try:
        print("Email:", get_user_email(user_info))  # KeyError
    except KeyError:
        print("Ключ 'email' отсутствует")

    # 8. Выполнение системной команды
    cmd = input("Введите команду для выполнения: ")
    try:
        output = run_system_command(cmd)  # RCE-уязвимость!
        print("Вывод команды:", output.decode())
    except Exception as e:
        print("Ошибка выполнения команды:", e)

    # 9. Декодирование токена
    token = input("Введите base64-токен: ")
    payload = decode_token(token)
    if payload:
        print("Декодированный payload:", payload)

    print("=== Конец скрипта ===")


# Глобальный вызов без проверки __name__
main()
