from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from pathlib import Path
from models import CheckerCode


class ProjectForm(FlaskForm):
    def validate_project_path(self, field):
        raw_path = field.data.strip()
        if not raw_path:
            raise ValidationError("Путь должен быть указан.")

        try:
            path_obj = Path(raw_path).resolve()
        except Exception as e:
            raise ValidationError(f"Некорректный формат пути: {e}")

        if not path_obj.is_dir():
            raise ValidationError("Путь должен быть существующей директорией.")

        field.data = str(path_obj)

    project_path = StringField(
        "Полный путь к папке с Python-файлами",
        validators=[DataRequired()],
    )
    submit = SubmitField("Сканировать")


def validate_checker_codes(form, field):
    """Проверяет, что строка checker_codes — это список 'checker:code' через запятую."""
    if not field.data:
        # разрешаем пустой, если action не group/ungroup
        action = getattr(form, "action", None)
        if action and action.data in ("group", "ungroup", "hide", "show", "edit"):
            raise ValidationError("Список checker:code не указан.")
        return

    pairs = [p.strip() for p in field.data.split(",") if p.strip()]
    if not pairs:
        action = getattr(form, "action", None)
        if action and action.data in ("group", "ungroup", "hide", "show", "edit"):
            raise ValidationError("Список checker:code пуст.")
        return

    for p in pairs:
        if ":" not in p:
            raise ValidationError(f"Некорректный формат: {p} (должен быть checker:code)")

    # опционально: проверить существование в БД для action group
    action = getattr(form, "action", None)
    if action and action.data == "group":
        for p in pairs:
            checker, code = p.split(":", 1)
            obj = CheckerCode.query.filter_by(checker=checker, code=code).first()
            if not obj:
                raise ValidationError(f"Не найден CheckerCode: {checker}:{code}")

