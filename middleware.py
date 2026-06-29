import os
import json
import uuid
import time
from pathlib import Path
from copy import deepcopy
from sqlalchemy import create_engine, Column, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from behoof import load_json, save_json, calculate_md5, str_to_md5

Base = declarative_base()


class ErrorGroup(Base):
    __tablename__ = "error_groups"
    id = Column(String(32), primary_key=True, comment="UUID хэш группы или Epoch")
    code_name = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)
    more_info = Column(Text, nullable=True)
    issue_severity = Column(String(50), nullable=True)
    type = Column(String(50), nullable=True)
    physical = Column(Text, nullable=True)
    message_rus = Column(Text, nullable=True)
    descriptions_rus = Column(Text, nullable=True)
    best_practice = Column(Text, nullable=True)
    color = Column(String(50), default="primary")
    translate = Column(Text, nullable=True)
    is_hide = Column(Boolean, default=False)
    source_url = Column(Text, nullable=True)
    mappings = relationship(
        "GroupMapping", back_populates="error_group", cascade="all, delete-orphan"
    )


class GroupMapping(Base):
    __tablename__ = "group_mappings"
    raw_signature = Column(
        String(500), primary_key=True, comment="Ключ вида checker|code|code_name"
    )
    group_id = Column(String(32), ForeignKey("error_groups.id"), nullable=False)
    error_group = relationship("ErrorGroup", back_populates="mappings")


os.makedirs("instance", exist_ok=True)


basedir = Path(__file__).parent.resolve()
instance_dir = basedir / "instance"
os.makedirs(instance_dir, exist_ok=True)

DATABASE_URL = f"sqlite:///{(instance_dir / 'linter_cache.db').as_posix()}"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

settings_dct = load_json("settings", "app.json")
default_group_dct = settings_dct.get("group_dct", {})


def init_db():
    """Создает таблицы в базе данных, если они еще не созданы."""
    Base.metadata.create_all(bind=engine)


def process_combine_file(combine_filepath, default_group_dct):
    """
    Функция-прокладка: принимает путь к файлу *_combine.json,
    обрабатывает ошибки через БД ORM, имитируя логику оригинального __main__.
    Использует только входящий файл и базу данных.
    """
    if not os.path.exists(combine_filepath):
        print(f"Файл {combine_filepath} не найден.")
        return

    with open(combine_filepath, "r", encoding="utf-8") as f:
        rows_data = json.load(f)

    session = SessionLocal()
    try:
        for row in rows_data:
            for err in row.get("errors", []):
                checker = err.get("checker") or ""
                code = err.get("code") or ""
                code_name = err.get("code_name") or ""
                raw_signature = "|".join([checker, code, code_name])
                mapping = (
                    session.query(GroupMapping)
                    .filter_by(raw_signature=raw_signature)
                    .first()
                )
                if not mapping:
                    group_uuid = uuid.uuid4().hex
                    new_group = ErrorGroup(
                        id=group_uuid,
                        code_name=err.get("code_name"),
                        message=err.get("message"),
                        more_info=err.get("more_info"),
                        issue_severity=err.get("issue_severity"),
                        type=err.get("type"),
                        physical=err.get("physical"),
                        color=default_group_dct.get("color", "primary"),
                        is_hide=default_group_dct.get("is_hide", False),
                    )
                    session.add(new_group)
                    mapping = GroupMapping(
                        raw_signature=raw_signature, group_id=group_uuid
                    )
                    session.add(mapping)
                    session.flush()
                else:
                    group_uuid = mapping.group_id
                print(f"🔴 {code} | {checker} | {code_name}")
                print(f"🔴 {raw_signature} {err.get('message', '')[:80]}")

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def display_program_with_errors(combine_filepath):
    """
    Выводит текст программы построчно с наложением информации об ошибках
    и их метаданных из Базы Данных.
    """
    if not os.path.exists(combine_filepath):
        print(f"Файл {combine_filepath} не найден.")
        return

    with open(combine_filepath, "r", encoding="utf-8") as f:
        rows_data = json.load(f)

    session = SessionLocal()
    print("\n" + "=" * 40 + " ВЫВОД ПРОГРАММЫ С ОШИБКАМИ " + "=" * 40)
    for row in rows_data:
        line_num = row.get("line")
        raw_code = row.get("raw", "")
        print(f"{line_num}\t| {raw_code}")
        errors = row.get("errors", [])
        for err in errors:
            checker = err.get("checker") or ""
            code = err.get("code") or ""
            code_name = err.get("code_name") or ""
            raw_signature = "|".join([checker, code, code_name])
            mapping = (
                session.query(GroupMapping)
                .filter_by(raw_signature=raw_signature)
                .first()
            )
            severity = "UNKNOWN"
            group_id = "NOT_ASSIGNED"
            if mapping and mapping.error_group:
                severity = (
                    mapping.error_group.issue_severity
                    or mapping.error_group.type
                    or "WARNING"
                )
                group_id = mapping.error_group.id
            print(
                f"\t🔴 [{severity}] [Group: {group_id}] {code} ({checker}): {err.get('message')}"
            )

    print("=" * 108 + "\n")
    session.close()


def group_signatures_together(signatures_list, group_meta_dct=None):
    """
    ГРУППИРОВКА: объединяет переданный список сигнатур в одну общую группу.
    Идентификатором группы (group_id) становится текущее время в формате Epoch (str).
    """
    if not signatures_list:
        return

    session = SessionLocal()
    try:
        epoch_group_id = str(int(time.time()))

        # Создаем или перезаписываем метаданные общей группы
        meta = group_meta_dct or {}
        error_group = session.query(ErrorGroup).filter_by(id=epoch_group_id).first()
        if not error_group:
            error_group = ErrorGroup(
                id=epoch_group_id,
                code_name=meta.get("code_name"),
                message=meta.get("message", "Объединенная группа линтера"),
                issue_severity=meta.get("issue_severity"),
                type=meta.get("type"),
                color=meta.get("color", "primary"),
                is_hide=meta.get("is_hide", False),
            )
            session.add(error_group)

        for sig in signatures_list:
            mapping = session.query(GroupMapping).filter_by(raw_signature=sig).first()
            if mapping:
                old_group_id = mapping.group_id
                mapping.group_id = epoch_group_id
                session.flush()

                # Если у старой группы больше нет привязанных сигнатур — удаляем её
                siblings = (
                    session.query(GroupMapping).filter_by(group_id=old_group_id).count()
                )
                if siblings == 0:
                    session.query(ErrorGroup).filter_by(id=old_group_id).delete()

        session.commit()
        print(
            f"Успешно сгруппировано {len(signatures_list)} сигнатур под ID: {epoch_group_id}"
        )
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def ungroup_signatures(signatures_list):
    """
    РАЗГРУППИРОВКА: разъединяет ошибки. Для каждой переданной сигнатуры
    генерируется свой собственный новый UUID в качестве group_id.
    """
    if not signatures_list:
        return

    session = SessionLocal()
    try:
        for sig in signatures_list:
            mapping = session.query(GroupMapping).filter_by(raw_signature=sig).first()
            if mapping:
                old_group_id = mapping.group_id
                new_group_uuid = uuid.uuid4().hex

                # Копируем метаданные старой группы или создаем дефолтные для новой индивидуальной группы
                old_group = session.query(ErrorGroup).filter_by(id=old_group_id).first()
                new_group = ErrorGroup(
                    id=new_group_uuid,
                    code_name=old_group.code_name if old_group else None,
                    message=(
                        old_group.message
                        if old_group
                        else f"Разгруппированная ошибка {sig}"
                    ),
                    more_info=old_group.more_info if old_group else None,
                    issue_severity=old_group.issue_severity if old_group else None,
                    type=old_group.type if old_group else None,
                    physical=old_group.physical if old_group else None,
                    color=old_group.color if old_group else "primary",
                    is_hide=old_group.is_hide if old_group else False,
                )
                session.add(new_group)

                # Присваиваем сигнатуре новый id
                mapping.group_id = new_group_uuid
                session.flush()

                # Очищаем старую группу, если она опустела
                siblings = (
                    session.query(GroupMapping).filter_by(group_id=old_group_id).count()
                )
                if siblings == 0:
                    session.query(ErrorGroup).filter_by(id=old_group_id).delete()

        session.commit()
        print(
            f"Успешно разгруппировано {len(signatures_list)} сигнатур. Каждой присвоен новый UUID."
        )
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


if __name__ == "__main__":
    init_db()
    mock_combine_filename = "data/2d29e7047f95703c96492235d1eb6cd3_combine.json"
    if not os.path.exists(mock_combine_filename):
        # Если оригинального файла нет, создаем структуру в памяти для теста функционала
        os.makedirs("data", exist_ok=True)
        mock_data = [
            {
                "line": 5,
                "raw": "def process_data(x, y):",
                "errors": [
                    {
                        "checker": "pylint",
                        "code": "W0613",
                        "code_name": "unused-argument",
                        "message": "Unused argument 'y'",
                        "type": "warning",
                    },
                    {
                        "checker": "vulture",
                        "code": "VU12A34",
                        "code_name": None,
                        "message": "unused argument 'y'",
                        "type": "warning",
                    },
                ],
            }
        ]
        with open(mock_combine_filename, "w", encoding="utf-8") as f:
            json.dump(mock_data, f, indent=4)

    print("Шаг 1: Запуск прокладки и обработка файла через ORM...")
    process_combine_file(mock_combine_filename, default_group_dct)

    print("\nШаг 2: Тестирование вывода текста программы с наложенными ошибками:")
    display_program_with_errors(mock_combine_filename)

    # Тестируемые сигнатуры
    test_sigs = [
        "flake8|F401|",
        "pylint|W0613|unused-argument",
        "vulture|VU12A34|",
        "pylint|C0114|missing-module-docstring",
        "pycodestyle|E501|",
    ]

    print("Шаг 3: Тестирование ГРУППИРОВКИ в формат Epoch:")
    group_signatures_together(
        test_sigs, {"message": "Сгруппированные неиспользуемые аргументы"}
    )
    display_program_with_errors(mock_combine_filename)

    print("Шаг 4: Тестирование РАЗГРУППИРОВКИ обратно в новые уникальные UUID:")
    ungroup_signatures(test_sigs)
    display_program_with_errors(mock_combine_filename)
