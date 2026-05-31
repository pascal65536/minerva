"""
Скрипт инициализации БД с тестовыми данными.
Запуск: python init_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from app import app, db
from models import CheckerCode, Group


def init_db():
    """Создаёт таблицы и добавляет стартовые данные."""
    with app.app_context():
        db.create_all()

        if Group.query.first():
            print("База данных уже инициализирована.")
            return

        groups = [
            Group(group_key="vulture_unused", color="#ff6b6b", name="Unused", descriptions="Неиспользуемый код"),
            Group(group_key="flake8_style", color="#5f27cd", name="Style", descriptions="Стилевые предупреждения"),
            Group(group_key="pylint_convention", color="#10ac84", name="Convention", descriptions="Соглашения"),
        ]
        db.session.add_all(groups)
        db.session.commit()

        codes = [
            ("vulture", "V101", "vulture_unused"),
            ("vulture", "V102", "vulture_unused"), 
            ("flake8", "E302", "flake8_style"),
            ("flake8", "E501", "flake8_style"),   
            ("pylint", "C0103", "pylint_convention"),
        ]
        for checker, code, group_key in codes:
            CheckerCode.get_or_create(checker, code, group_key=group_key)
        
        db.session.commit()
        print(f"Добавлено {len(groups)} групп и {len(codes)} записей в БД.")


if __name__ == "__main__":
    init_db()

    # # Получить или создать запись
    # cc1 = CheckerCode.get_or_create("Vulture", "V101")
    # cc2 = CheckerCode.get_or_create("Vulture", "V102")

    # # Группировка: объединить две записи в одну группу
    # cc2.group_with(cc1)  # теперь у cc1 и cc2 одинаковый group_key и цвет
    # db.session.commit()

    # # Разгруппировка: сделать запись независимой
    # cc2.ungroup()  # у cc2 теперь уникальный group_key
    # db.session.commit()

    # # Группировка по произвольному ключу
    # cc1.group_by_key("my_custom_group")
    # db.session.commit()

    # # Получить цвет для множества пар ОДНИМ запросом (для рендеринга)
    # pairs = [("Vulture", "V101"), ("Flake8", "E501"), ("Pylint", "C0103")]
    # colors = CheckerCode.bulk_get_colors(pairs)
    # # Результат: {("Vulture", "V101"): "#ff6b6b", ...}