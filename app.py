import os
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
)
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from behoof import load_json


settings_dct = load_json("settings", "app.json")

app = Flask(__name__)
app.secret_key = os.urandom(128)
app.root_dir = settings_dct.get("root_dir", "fixtures")


# class SettingsForm(FlaskForm):
#     checker_code = StringField(validators=[DataRequired()])
#     submit = SubmitField("Отправить")

#     # Метод для получения данных как JSON (если нужно)
#     def get_json_data(self):
#         return {"checker_code": self.checker_code.data}


class ProjectForm(FlaskForm):
    def validator_project_path(self, field):
        project_path = field.data
        if not project_path:
            raise ValidationError("Путь должен быть указан.")
        if not os.path.exists(project_path):
            raise ValidationError("Путь должен реально существовать.")
        if not os.path.isdir(project_path):
            raise ValidationError("Путь должен быть директорией.")
        return

    project_path = StringField(
        "Полный путь к папке с Python-файлами",
        validators=[DataRequired(), validator_project_path],
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
    if not len(files_lst):
        *_, selected_key = files_lst[0]

    selected_file_info = dict()
    for display_path, filename, key in files_lst:
        if selected_key != key:
            continue
        python_dct = raw_update_or_create(display_path)
        vulture_dct = group_line_update_or_create(display_path)
        selected_file_info = {
            "filename": filename,
            "display_path": display_path,
            "vulture_dct": vulture_dct,
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


# @app.route("/settings", methods=["POST"])
# def settings():
#     form = SettingsForm()
#     print(form.data)
#     if form.validate_on_submit():
#         settings_dct = form.get_json_data()
#         print(settings_dct)
#         flash("Настройки сохранены", "success")
#     return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
