import os
from pathlib import Path
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from flask_wtf import FlaskForm
from utils import (
    group_line_update_or_create,
    raw_update_or_create,
    scan_python_files,
    erase_data,
    get_key_checker_code,
    get_teacher_lst,
)
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from behoof import load_json

settings_dct = load_json("settings", "app.json")

app = Flask(__name__)
app.secret_key = os.urandom(128)
app.root_dir = Path(settings_dct.get("root_dir", "fixtures")).resolve().as_posix()


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


@app.route("/", methods=["GET", "POST"])
def index():
    form = ProjectForm()
    if form.validate_on_submit():
        app.root_dir = form.project_path.data
        files_lst = scan_python_files(app.root_dir)
        msg = f"Проект '{app.root_dir}' загружен. Найдено и проанализировано {len(files_lst)} Python-файлов."
        flash(msg, "success")
        return redirect(url_for("index"))

    files_lst = scan_python_files(app.root_dir)
    selected_key = request.args.get("key")

    if files_lst and not selected_key:
        *_, selected_key = files_lst[0]

    teacher_lst = get_teacher_lst()
    selected_file_info = dict()
    for display_path, filename, key in files_lst:
        if selected_key != key:
            continue

        python_dct = raw_update_or_create(display_path)
        vulture_dct = group_line_update_or_create(display_path)
        vulture_clean_dct = dict()
        for key_vulniture, checks in vulture_dct.items():
            vulture_clean_dct.setdefault(key_vulniture, [])
            for checker_code in checks:
                key = get_key_checker_code(checker_code)
                if key in teacher_lst:
                    continue
                vulture_clean_dct[key_vulniture].append(checker_code)

        selected_file_info = {
            "filename": filename,
            "display_path": display_path,
            "vulture_dct": vulture_clean_dct,
            "python_dct": python_dct,
        }

    return render_template(
        "index.html",
        form=form,
        files_lst=files_lst,
        selected_key=selected_key,
        selected_file_info=selected_file_info,
    )


@app.route("/refresh-all")
def refresh_all():
    erase_data()
    files_lst = scan_python_files(app.root_dir)
    count = 0
    for filename, *_ in files_lst:
        group_line_update_or_create(filename)
        raw_update_or_create(filename)
        count += 1
    flash(f"Обновлено отчетов: {count}", "info")
    return redirect(url_for("index"))


@app.route("/refresh/<key>")
def refresh(key):
    erase_data(key)
    flash(f"Отчет о файле обновлен", "info")
    return redirect(url_for("index", key=key))


if __name__ == "__main__":
    app.run(debug=True)
