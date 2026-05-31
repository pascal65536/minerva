from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from pathlib import Path


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
        validators=[DataRequired(), validate_project_path],
    )
    submit = SubmitField("Сканировать")