import os
import sys
import pickle
import sqlite3
import subprocess
import json
import base64
from behoof import *
from ipdb import *
import math


SECRET_KEY = "my_super_secret_password_123"


class UserManager:
    def __init__(self, db_path="users.db"):
        self.db_path = db_path
        self.conn = None

    def connect(self):
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
        query = f"INSERT INTO users (username, email) VALUES ('{username}', '{email}')"
        self.conn.execute(query)
        self.conn.commit()

    def get_user(self, user_id):
        if not self.conn:
            self.connect()
        cursor = self.conn.execute(f"SELECT * FROM users WHERE id = {user_id}")
        return cursor.fetchone()

    def close(self):
        if self.conn:
            self.conn.close()


def run_user_code(code_str):
    return eval(code_str)


def load_user_data(data_file):
    with open(data_file, "rb") as f:
        return pickle.load(f)


def buggy_function(x):
    if x > 0:
        result = x * 2
    print(result)


def read_config(filename):
    f = open(filename, "r")
    return f.read()


def calculate_area(width, height):
    return width * height


def unused_function():
    return "This function is never called"


def long_line_function():
    return "This is a very long line that exceeds the recommended 79 or even 88 character limit and should be wrapped properly but it is not"


def get_item(lst, index):
    return lst[index]


def get_user_email(user_dict):
    return user_dict["email"]


def run_system_command(cmd):
    return subprocess.check_output(cmd, shell=True)


def decode_token(token):
    try:
        decoded = base64.b64decode(token)
        return json.loads(decoded)
    except Exception as e:
        print("Error:", e)
        return None


def main():
    print("=== Старт тестового скрипта ===")

    user_input = input("Введите выражение для вычисления: ")
    try:
        result = run_user_code(user_input)
        print("Результат:", result)
    except Exception as e:
        print("Ошибка при вычислении:", e)

    db = UserManager()
    db.create_table()
    username = input("Введите имя пользователя: ")
    email = input("Введите email: ")
    db.add_user(username, email)

    user_id_input = input("Введите ID пользователя для поиска: ")
    user = db.get_user(user_id_input)
    print("Найден пользователь:", user)

    db.close()

    try:
        buggy_function(-5)
    except NameError as e:
        print("Ошибка неинициализированной переменной:", e)

    try:
        config = read_config("config.txt")
        print("Конфиг:", config[:50])
    except FileNotFoundError:
        print("Файл config.txt не найден")

    try:
        data = load_user_data("user_data.pkl")
        print("Загружены данные:", data)
    except FileNotFoundError:
        print("Файл user_data.pkl не найден")

    my_list = [1, 2, 3]
    idx = int(input("Введите индекс списка: "))
    try:
        print("Элемент:", get_item(my_list, idx))
    except IndexError:
        print("Индекс вне диапазона")

    user_info = {"name": "Alice"}
    try:
        print("Email:", get_user_email(user_info))  # KeyError
    except KeyError:
        print("Ключ 'email' отсутствует")

    cmd = input("Введите команду для выполнения: ")
    try:
        output = run_system_command(cmd)
        print("Вывод команды:", output.decode())
    except Exception as e:
        print("Ошибка выполнения команды:", e)

    token = input("Введите base64-токен: ")
    payload = decode_token(token)
    if payload:
        print("Декодированный payload:", payload)

    print("=== Конец скрипта ===")


main()
