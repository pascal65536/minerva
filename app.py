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
# from flask import render_template, request, redirect, url_for, flash, app
from behoof import load_json
from extensions import db
from models import CheckerCode, Group
from forms import ProjectForm
from utils import (
    group_line_update_or_create,
    raw_update_or_create,
    scan_python_files,
    erase_data,
    get_key_checker_code,
    get_teacher_lst,
    create_key,
    scan_python_files,
    raw_update_or_create,
    group_line_update_or_create,
    create_key,
    get_key_checker_code,
)


settings_dct = load_json("settings", "app.json")


app = Flask(__name__)
app.secret_key = os.urandom(128)
app.root_dir = Path(settings_dct.get("root_dir", "fixtures")).resolve().as_posix()

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///checker_colors.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)



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

    # Если файлы есть, но файл не выбран — берём первый
    if files_lst and not selected_key:
        *_, selected_key = files_lst[0]

    teacher_lst = get_teacher_lst()
    selected_file_info = {}

    # Кэшируем CheckerCode и группы из БД
    key_checker_code_dct = {}
    checker_code_dct = {}
    for checker_code in CheckerCode.query.all():
        key_cc = get_key_checker_code(checker_code.checker, checker_code.code)
        checker_code_dct[key_cc] = checker_code
        key_checker_code_dct[key_cc] = checker_code.group_key

    group_dct = {}
    for group in Group.query.all():
        group_dct[group.group_key] = group

    selected_file_info = {}

    for display_path, filename, key in files_lst:
        if selected_key != key:
            continue

        python_dct = raw_update_or_create(display_path)
        vulture_dct = group_line_update_or_create(display_path)
        vulture_clean_dct = {}
        for key_vulniture, checks in vulture_dct.items():
            group_map = {}

            for checker_code in checks:
                checker = checker_code["checker"]
                code = checker_code["code"]
                key_cc = get_key_checker_code(checker, code)

                # Получаем/создаём CheckerCode
                checker_code_obj = checker_code_dct.get(key_cc)
                if not checker_code_obj:
                    checker_code_obj = CheckerCode.query.filter_by(
                        checker=checker,
                        code=code
                    ).first()

                if not checker_code_obj:
                    group_key = create_key(checker, code)
                    checker_code_obj = CheckerCode.create(
                        checker=checker,
                        code=code,
                        group_key=group_key,
                        group_color=checker_code.get("color", "danger"),
                        group_name=checker_code.get("message"),
                        group_translate=checker_code.get("code_name"),
                        group_descriptions=checker_code.get("type"),
                    )
                    checker_code_dct[key_cc] = checker_code_obj
                    key_checker_code_dct[key_cc] = checker_code_obj.group_key

                # Добавляем raw: описание ошибки из анализатора
                checker_code_obj.raw = checker_code

                # Получаем группу
                group_key = checker_code_obj.group_key
                group_obj = group_dct.get(group_key)
                if not group_obj:
                    group_obj = Group.query.filter_by(group_key=group_key).first()
                    if group_obj:
                        group_dct[group_key] = group_obj

                if not group_obj:
                    continue

                # Создаём список checker_codes у группы, если его нет
                if not hasattr(group_obj, "checker_codes"):
                    group_obj.checker_codes = []

                group_obj.checker_codes.append(checker_code_obj)
                group_map.setdefault(group_key, group_obj)

            vulture_clean_dct[key_vulniture] = list(group_map.values())

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


@app.route("/group_action", methods=["POST"])
def group_action():
    action = request.form.get("action")
    group_keys = request.form.getlist("group_keys")
    group_key = request.form.get("group_key", "")

    if action == "group" and group_keys:
        if len(group_keys) < 2:
            flash("Для группировки нужно выбрать минимум 2 группы.", "warning")
            return redirect(request.referrer or url_for("index"))
        try:
            main_group = Group.union(group_keys)
            flash(f"Группы объединены в '{main_group.group_key}'.", "success")
        except Exception as e:
            flash(f"Ошибка при группировке: {e}", "danger")
        return redirect(request.referrer or url_for("index"))

    elif action == "split":
        if not group_key:
            flash("Не указан group_key для разгруппировки.", "danger")
            return redirect(request.referrer or url_for("index"))
        try:
            new_groups = Group.split(group_key)
            flash(f"Группа '{group_key}' разгруппирована на {len(new_groups)} новых групп.\n\n{new_groups}", "success")
        except Exception as e:
            flash(f"Ошибка при разгруппировке: {e}", "danger")
        return redirect(request.referrer or url_for("index"))

    elif action == "toggle_hide":
        if not group_key:
            flash("Не указан group_key для скрытия/показа.", "danger")
            return redirect(request.referrer or url_for("index"))
        group = Group.query.filter_by(group_key=group_key).first()
        if not group:
            flash("Группа не найдена.", "danger")
            return redirect(request.referrer or url_for("index"))
        group.is_hide = not group.is_hide
        db.session.commit()
        if group.is_hide:
            flash("Группа скрыта.", "success")
        else:
            flash("Группа показана.", "success")
        return redirect(request.referrer or url_for("index"))

    elif action == "hide":
        if not group_key:
            flash("Не указан group_key для скрытия.", "danger")
            return redirect(request.referrer or url_for("index"))
        group = Group.query.filter_by(group_key=group_key).first()
        if not group:
            flash("Группа не найдена.", "danger")
            return redirect(request.referrer or url_for("index"))
        group.is_hide = True
        db.session.commit()
        flash("Группа скрыта.", "success")
        return redirect(request.referrer or url_for("index"))

    elif action == "show":
        if not group_key:
            flash("Не указан group_key для показа.", "danger")
            return redirect(request.referrer or url_for("index"))

        group = Group.query.filter_by(group_key=group_key).first()
        if not group:
            flash("Группа не найдена.", "danger")
            return redirect(request.referrer or url_for("index"))
        group.is_hide = False
        db.session.commit()
        flash("Группа показана.", "success")

        return redirect(request.referrer or url_for("index"))

    elif action == "edit":
        if not group_key:
            flash("Не указан group_key для редактирования.", "danger")
            return redirect(request.referrer or url_for("index"))
        group = Group.query.filter_by(group_key=group_key).first()
        if not group:
            flash("Группа не найдена.", "danger")
            return redirect(request.referrer or url_for("index"))
        name = request.form.get("name", "").strip()
        translate = request.form.get("translate", "").strip()
        descriptions = request.form.get("descriptions", "").strip()
        color = request.form.get("color", "").strip()
        group.name = name if name else None
        group.translate = translate if translate else None
        group.descriptions = descriptions if descriptions else None
        valid_colors = (
            "info", "success", "warning", "danger",
            "dark", "primary", "secondary"
        )
        if color in valid_colors:
            group.color = color
        db.session.commit()
        flash("Данные группы обновлены.", "success")
        return redirect(request.referrer or url_for("index"))

    else:
        flash("Неизвестное действие.", "danger")
        return redirect(request.referrer or url_for("index"))

if __name__ == "__main__":
    debug = True
    if debug:
        with app.app_context():
            db.create_all()
    app.run(debug=debug)
