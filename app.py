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
)


settings_dct = load_json("settings", "app.json")


app = Flask(__name__)
app.secret_key = os.urandom(128)
app.root_dir = Path(settings_dct.get("root_dir", "fixtures")).resolve().as_posix()

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///checker_colors.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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

    if files_lst and not selected_key:
        *_, selected_key = files_lst[0]

    teacher_lst = get_teacher_lst()
    selected_file_info = dict()
    checker_codes_list = []

    for display_path, filename, key in files_lst:
        if selected_key != key:
            continue

        python_dct = raw_update_or_create(display_path)
        vulture_dct = group_line_update_or_create(display_path)
        vulture_clean_dct = dict()
        for key_vulniture, checks in vulture_dct.items():
            vulture_clean_dct.setdefault(key_vulniture, [])
            for checker_code in checks:
                key_cc = get_key_checker_code(checker_code)
                if key_cc in teacher_lst:
                    continue
                vulture_clean_dct[key_vulniture].append(checker_code)
                checker_codes_list.append(f"{checker_code['checker']}:{checker_code['code']}")

        selected_file_info = {
            "filename": filename,
            "display_path": display_path,
            "vulture_dct": vulture_clean_dct,
            "python_dct": python_dct,
        }

    color_map = {}
    groups_info = []

    if selected_file_info:
        group_map = {}
        for checks in selected_file_info["vulture_dct"].values():
            for checker_code in checks:
                checker = checker_code['checker']
                code = checker_code['code']
                try:
                    dd = CheckerCode.query.filter_by(checker=checker, code=code).first()
                    group_key_cc = dd.group_key
                    group = Group.query.filter_by(group_key=group_key_cc).first()
                    checker_code['color'] = group.color

                    group_map.setdefault(group_key_cc, []).append((checker, code))
                except AttributeError:
                    checker_code['color'] = 'dark'

        for gk, pairs in group_map.items():
            group = Group.query.filter_by(group_key=gk).first()
            if group:
                groups_info.append({
                    "group_key": gk,
                    "group": group,
                    "pairs": pairs,
                    "checker_codes_str": ",".join(f"{c}:{co}" for c, co in pairs),
                })

    checker_codes_str = ",".join(set(checker_codes_list))

    return render_template(
        "index.html",
        form=form,
        files_lst=files_lst,
        selected_key=selected_key,
        selected_file_info=selected_file_info,
        color_map=color_map,
        checker_codes_str=checker_codes_str,
        groups_info=groups_info,
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


@app.route("/group-action", methods=["POST"])
def group_action():
    action = request.form.get("action")
    print(action)

    if action == 'group':
        for_group = list()
        for issue in request.form.getlist('issues'):
            for_group.append(issue.split('|'))
        with app.app_context():
            ids = CheckerCode.group_this(for_group)
            db.session.commit()
        print(ids)
        print(for_group)
    return redirect(url_for("index"))

    checker_codes_str = request.form.get("checker_codes", "")
    group_key = request.form.get("group_key", "")

    pairs = [p.strip() for p in checker_codes_str.split(",") if p.strip()]
    checker_code_lst = []
    for p in pairs:
        checker, code = p.split(":", 1)
        checker_code_lst.append((checker, code))

    if action == "group":
        if len(checker_code_lst) < 2:
            flash("Для группировки нужно минимум 2 объекта.", "warning")
            return redirect(url_for("index"))
        CheckerCode.group_this(checker_code_lst)
        flash("Объекты объединены в группу.", "success")

    elif action == "ungroup":
        if not group_key:
            flash("Не указан group_key для разгруппировки.", "danger")
            return redirect(url_for("index"))
        CheckerCode.ungroup_this(group_key)
        flash("Группа разгруппирована.", "success")

    elif action == "hide":
        if not group_key:
            flash("Не указан group_key для скрытия.", "danger")
            return redirect(url_for("index"))
        group = Group.query.filter_by(group_key=group_key).first()
        if group:
            group.is_hide = True
            db.session.commit()
            flash("Группа скрыта.", "success")
        else:
            flash("Группа не найдена.", "danger")

    elif action == "show":
        if not group_key:
            flash("Не указан group_key для показа.", "danger")
            return redirect(url_for("index"))
        group = Group.query.filter_by(group_key=group_key).first()
        if group:
            group.is_hide = False
            db.session.commit()
            flash("Группа показана.", "success")
        else:
            flash("Группа не найдена.", "danger")

    elif action == "edit":
        if not group_key:
            flash("Не указан group_key для редактирования.", "danger")
            return redirect(url_for("index"))
        group = Group.query.filter_by(group_key=group_key).first()
        if not group:
            flash("Группа не найдена.", "danger")
            return redirect(url_for("index"))

        name = request.form.get("name", "").strip()
        translate = request.form.get("translate", "").strip()
        descriptions = request.form.get("descriptions", "").strip()
        color = request.form.get("color", "").strip()

        group.name = name if name else None
        group.translate = translate if translate else None
        group.descriptions = descriptions if descriptions else None
        if color in ("info", "success", "warning", "danger", "dark", "primary", "secondary"):
            group.color = color

        db.session.commit()
        flash("Данные группы обновлены.", "success")

    else:
        flash("Неизвестное действие.", "danger")

    return redirect(url_for("index"))


if __name__ == "__main__":
    debug = True
    if debug:
        with app.app_context():
            db.create_all()
    app.run(debug=debug)