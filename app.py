import os
import logging
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
    create_key,
)

settings_dct = load_json("settings", "app.json")

app = Flask(__name__)
app.secret_key = os.urandom(128)
app.root_dir = Path(settings_dct.get("root_dir", "fixtures")).resolve().as_posix()

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///checker_colors.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

os.makedirs("log", exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
h = logging.FileHandler("log/app.log", encoding="utf-8")
h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
logger.addHandler(h)

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

    logger.info(f"[INDEX] START selected_key={selected_key}")

    selected_file_info = {}
    key_checker_code_dct = {}
    checker_code_dct = {}
    for checker_code in CheckerCode.query.all():
        key_cc = get_key_checker_code(checker_code.checker, checker_code.code)
        checker_code_dct[key_cc] = checker_code
        key_checker_code_dct[key_cc] = checker_code.group_key
        logger.debug(f"[INDEX] CheckerCode key_cc={key_cc} group_key={checker_code.group_key}")

    group_dct = {}
    for group in Group.query.all():
        group_dct[group.group_key] = group
        logger.debug(f"[INDEX] Loaded group: group_key={group.group_key} is_hide={group.is_hide}")

    logger.info(f"[INDEX] Всего загружено групп: {len(group_dct)}")

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

                checker_code_obj.raw = checker_code

                group_key = checker_code_obj.group_key
                logger.debug(f"[INDEX] line={key_vulniture} checker={checker} code={code} group_key={group_key}")
                group_obj = group_dct.get(group_key)
                if not group_obj:
                    group_obj = Group.query.filter_by(group_key=group_key).first()
                    if group_obj:
                        group_dct[group_key] = group_obj

                if not group_obj:
                    continue

                if not hasattr(group_obj, "checker_codes"):
                    group_obj.checker_codes = []

                group_obj.checker_codes.append(checker_code_obj)
                group_map.setdefault(group_key, group_obj)

            vulture_clean_dct[key_vulniture] = list(group_map.values())

        logger.info("[INDEX] GROUPS IN vulture_clean_dct:")
        for line_num, groups in vulture_clean_dct.items():
            for group in groups:
                logger.debug(
                    f"[INDEX] line={line_num} "
                    f"group_key={group.group_key} "
                    f"is_hide={group.is_hide}"
                )

        db.session.expire_all()

        selected_file_info = {
            "filename": filename,
            "display_path": display_path,
            "vulture_dct": vulture_clean_dct,
            "python_dct": python_dct,
        }

    logger.info("[INDEX] RENDERING TEMPLATE")
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

    logger.debug(f"[GROUP_ACTION] START action={action} group_key={group_key}")

    if action == "group" and group_keys:
        if len(group_keys) < 2:
            flash("Для группировки нужно выбрать минимум 2 группы.", "warning")
            return redirect(request.referrer or url_for("index"))
        try:
            main_group = Group.union(group_keys)
            flash(f"Группы объединены в '{main_group.group_key}'.", "success")
        except Exception as e:
            logger.error(f"[GROUP_ACTION] ERROR in Group.union: {e}")
            flash(f"Ошибка при группировке: {e}", "danger")
        return redirect(request.referrer or url_for("index"))

    elif action == "split":
        if not group_key:
            flash("Не указан group_key для разгруппировки.", "danger")
            return redirect(request.referrer or url_for("index"))
        try:
            logger.info(f"[GROUP_ACTION] BEFORE split: group_key={group_key}")
            new_groups = Group.split(group_key)
            logger.info(f"[GROUP_ACTION] AFTER split: group_key={group_key} len(new_groups)={len(new_groups)}")
            db.session.expire_all()
            flash(f"Группа '{group_key}' разгруппирована на {len(new_groups)} новых групп.", "success")
        except Exception as e:
            logger.error(f"[GROUP_ACTION] ERROR in Group.split: {e}")
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

        old_is_hide = group.is_hide
        logger.info(f"[GROUP_ACTION] toggle_hide BEFORE: group_key={group_key} is_hide={old_is_hide}")
        group.is_hide = not group.is_hide
        db.session.commit()
        logger.info(f"[GROUP_ACTION] toggle_hide AFTER: group_key={group_key} is_hide={group.is_hide}")

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
        logger.info(f"[GROUP_ACTION] hide BEFORE: group_key={group_key} is_hide={group.is_hide}")
        group.is_hide = True
        db.session.commit()
        logger.info(f"[GROUP_ACTION] hide AFTER: group_key={group_key} is_hide={group.is_hide}")
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
        logger.info(f"[GROUP_ACTION] show BEFORE: group_key={group_key} is_hide={group.is_hide}")
        group.is_hide = False
        db.session.commit()
        logger.info(f"[GROUP_ACTION] show AFTER: group_key={group_key} is_hide={group.is_hide}")
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
        logger.info(f"[GROUP_ACTION] edit BEFORE: group_key={group_key} is_hide={group.is_hide}")
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
        logger.info(f"[GROUP_ACTION] edit AFTER: group_key={group_key} is_hide={group.is_hide}")
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