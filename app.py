import os
import logging
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
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
    calculate_md5,
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
logger.setLevel(logging.INFO)
h = logging.FileHandler("log/app.log", encoding="utf-8")
h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
logger.addHandler(h)

data_dir = settings_dct.get("data_dir", "data")


def erase_file_cache(filename):
    md5_hash = calculate_md5(filename)
    group_line_file = f"{md5_hash}.json"
    raw_file = f"{md5_hash}_raw.json"
    group_line_path = os.path.join(data_dir, group_line_file)
    raw_path = os.path.join(data_dir, raw_file)
    deleted = False
    if os.path.exists(group_line_path):
        os.remove(group_line_path)
        logger.info(f"[CACHE] Удален кэш групп: {group_line_file}")
        deleted = True
    if os.path.exists(raw_path):
        os.remove(raw_path)
        logger.info(f"[CACHE] Удален кэш raw: {raw_file}")
        deleted = True
    return deleted


def extract_key_from_referer(referer):
    if not referer:
        return None
    parsed = urlparse(referer)
    params = parse_qs(parsed.query)
    return params.get("key", [None])[0]


def get_current_file_key():
    return request.args.get("key") or extract_key_from_referer(request.referrer)


def find_file_by_key(key):
    if not key:
        return None
    files_lst = scan_python_files(app.root_dir)
    for display_path, filename, file_key in files_lst:
        if file_key == key:
            return (display_path, filename, file_key)
    return None


def refresh_file_cache_by_key(key):
    file_info = find_file_by_key(key)
    if not file_info:
        logger.warning(f"[CACHE] Файл с ключом {key} не найден")
        return None
    display_path, filename, _ = file_info
    erase_file_cache(display_path)
    group_line_update_or_create(display_path)
    raw_update_or_create(display_path)
    logger.info(f"[CACHE] Обновлен кэш для файла: {display_path}")
    return (display_path, filename, True)


def load_groups_and_checkers():
    checker_code_dct = {}
    key_checker_code_dct = {}
    for checker_code in CheckerCode.query.all():
        key_cc = get_key_checker_code(checker_code.checker, checker_code.code)
        checker_code_dct[key_cc] = checker_code
        key_checker_code_dct[key_cc] = checker_code.group_key
    group_dct = {}
    for group in Group.query.all():
        group_dct[group.group_key] = group
    logger.info(
        f"[INDEX] Загружено групп: {len(group_dct)}, checker_codes: {len(checker_code_dct)}"
    )
    return checker_code_dct, key_checker_code_dct, group_dct


def process_file_analysis(display_path, filename, key, checker_code_dct, group_dct):
    python_dct = raw_update_or_create(display_path)
    vulture_dct = group_line_update_or_create(display_path)
    vulture_clean_dct = {}
    for line_num, checks in vulture_dct.items():
        group_map = {}
        for checker_data in checks:
            checker = checker_data["checker"]
            code = checker_data["code"]
            key_cc = get_key_checker_code(checker, code)
            checker_code_obj = checker_code_dct.get(key_cc)
            if not checker_code_obj:
                checker_code_obj = CheckerCode.query.filter_by(
                    checker=checker, code=code
                ).first()
            if not checker_code_obj:
                group_key = create_key(checker, code)
                checker_code_obj = CheckerCode.create(
                    checker=checker,
                    code=code,
                    group_key=group_key,
                    group_color=checker_data.get("color", "danger"),
                    group_name=checker_data.get("message", f"{checker}:{code}"),
                    group_translate=checker_data.get("code_name", ""),
                    group_descriptions=checker_data.get("type", ""),
                )
                checker_code_dct[key_cc] = checker_code_obj
            checker_code_obj.raw = checker_data
            group_key = checker_code_obj.group_key
            group_obj = group_dct.get(group_key)
            if not group_obj:
                group_obj = Group.query.filter_by(group_key=group_key).first()
                if group_obj:
                    group_dct[group_key] = group_obj
            if not group_obj:
                continue
            if not hasattr(group_obj, "checker_codes"):
                group_obj.checker_codes = []
            if checker_code_obj not in group_obj.checker_codes:
                group_obj.checker_codes.append(checker_code_obj)
            group_map.setdefault(group_key, group_obj)
        vulture_clean_dct[line_num] = list(group_map.values())
    db.session.expire_all()
    return {
        "filename": filename,
        "display_path": display_path,
        "vulture_dct": vulture_clean_dct,
        "python_dct": python_dct,
    }


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
    logger.info(f"[INDEX] Загрузка отчета для key={selected_key}")
    checker_code_dct, _, group_dct = load_groups_and_checkers()
    selected_file_info = {}
    for display_path, filename, key in files_lst:
        if selected_key != key:
            continue
        selected_file_info = process_file_analysis(
            display_path, filename, key, checker_code_dct, group_dct
        )
        break
    return render_template(
        "index.html",
        form=form,
        files_lst=files_lst,
        selected_key=selected_key,
        selected_file_info=selected_file_info,
    )


@app.route("/refresh-all")
def refresh_all():
    logger.info("[REFRESH_ALL] Начало полного обновления")
    erase_data()
    files_lst = scan_python_files(app.root_dir)
    count = 0
    for display_path, filename, _ in files_lst:
        try:
            group_line_update_or_create(display_path)
            raw_update_or_create(display_path)
            count += 1
            logger.info(f"[REFRESH_ALL] Обновлен файл: {filename}")
        except Exception as e:
            logger.error(f"[REFRESH_ALL] Ошибка при обновлении {filename}: {e}")
    flash(f"Обновлено отчетов: {count} из {len(files_lst)}", "info")
    logger.info(f"[REFRESH_ALL] Завершено. Обновлено {count} файлов")
    return redirect(url_for("index"))


@app.route("/refresh/<key>")
def refresh(key):
    logger.info(f"[REFRESH] Обновление файла с ключом: {key}")
    result = refresh_file_cache_by_key(key)
    if result:
        display_path, filename, _ = result
        flash(f"Отчет о файле '{filename}' обновлен", "info")
        logger.info(f"[REFRESH] Файл обновлен: {filename}")
    else:
        flash(f"Файл с ключом {key} не найден", "warning")
        logger.warning(f"[REFRESH] Файл с ключом {key} не найден")
    return redirect(url_for("index", key=key))


@app.route("/api/file-info/<key>")
def api_file_info(key):
    file_info = find_file_by_key(key)
    if not file_info:
        return jsonify({"error": "File not found"}), 404
    display_path, filename, _ = file_info
    return jsonify(
        {
            "filename": filename,
            "display_path": display_path,
            "key": key,
        }
    )


@app.route("/api/analysis/<key>")
def api_analysis(key):
    file_info = find_file_by_key(key)
    if not file_info:
        return jsonify({"error": "File not found"}), 404
    display_path, filename, _ = file_info
    try:
        python_dct = raw_update_or_create(display_path)
        vulture_dct = group_line_update_or_create(display_path)
        checker_code_dct, _, group_dct = load_groups_and_checkers()
        result = {"filename": filename, "display_path": display_path, "lines": {}}
        for line_num, checks in vulture_dct.items():
            line_data = {"code": python_dct.get(line_num, ""), "errors": []}
            for checker_data in checks:
                checker = checker_data["checker"]
                code = checker_data["code"]
                key_cc = get_key_checker_code(checker, code)
                checker_code_obj = checker_code_dct.get(key_cc)
                if checker_code_obj:
                    group_obj = group_dct.get(checker_code_obj.group_key)
                    error_data = {
                        "checker": checker,
                        "code": code,
                        "message": checker_data.get("message", ""),
                        "severity": checker_data.get("issue_severity", "UNKNOWN"),
                        "group": {
                            "name": group_obj.name if group_obj else None,
                            "color": group_obj.color if group_obj else "secondary",
                            "is_hide": group_obj.is_hide if group_obj else False,
                        },
                        "raw_data": checker_data,
                    }
                    line_data["errors"].append(error_data)
            if line_data["errors"]:
                result["lines"][line_num] = line_data
        return jsonify(result)
    except Exception as e:
        logger.error(f"[API] Ошибка при получении анализа для {filename}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/group_action", methods=["POST"])
def group_action():
    action = request.form.get("action")
    group_keys = request.form.getlist("group_keys")
    group_key = request.form.get("group_key", "")
    logger.info(
        f"[GROUP_ACTION] Действие: {action}, group_keys: {group_keys}, group_key: {group_key}"
    )
    current_key = get_current_file_key()
    if action == "group" and group_keys:
        if len(group_keys) < 2:
            flash("Для группировки нужно выбрать минимум 2 группы.", "warning")
            return redirect(request.referrer or url_for("index"))
        try:
            logger.info(f"[GROUP_ACTION] Объединение групп: {group_keys}")
            main_group = Group.union(group_keys)
            logger.info(f"[GROUP_ACTION] Группы объединены в '{main_group.group_key}'")
            if current_key:
                refresh_file_cache_by_key(current_key)
            flash(f"Группы объединены в '{main_group.group_key}'.", "success")
        except Exception as e:
            logger.error(f"[GROUP_ACTION] Ошибка при группировке: {e}", exc_info=True)
            flash(f"Ошибка при группировке: {e}", "danger")
        return redirect(request.referrer or url_for("index"))
    elif action == "split":
        if not group_key:
            flash("Не указан group_key для разгруппировки.", "danger")
            return redirect(request.referrer or url_for("index"))
        try:
            logger.info(f"[GROUP_ACTION] Разделение группы: {group_key}")
            new_groups = Group.split(group_key)
            logger.info(f"[GROUP_ACTION] Группа разделена на {len(new_groups)} групп")
            db.session.expire_all()
            if current_key:
                refresh_file_cache_by_key(current_key)
            flash(
                f"Группа '{group_key}' разгруппирована на {len(new_groups)} новых групп.",
                "success",
            )
        except Exception as e:
            logger.error(f"[GROUP_ACTION] Ошибка при разделении: {e}", exc_info=True)
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
        new_state = not group.is_hide
        logger.info(
            f"[GROUP_ACTION] Изменение видимости группы '{group_key}': {group.is_hide} -> {new_state}"
        )
        group.is_hide = new_state
        db.session.commit()
        if current_key:
            refresh_file_cache_by_key(current_key)
        if group.is_hide:
            flash(f"Группа '{group.name or group_key}' скрыта.", "success")
        else:
            flash(f"Группа '{group.name or group_key}' показана.", "success")
        return redirect(request.referrer or url_for("index"))
    elif action == "edit":
        edit_group_key = request.form.get("edit_group_key")
        if not edit_group_key:
            flash("Не указан group_key для редактирования.", "danger")
            return redirect(request.referrer or url_for("index"))
        group = Group.query.filter_by(group_key=edit_group_key).first()
        if not group:
            flash("Группа не найдена.", "danger")
            return redirect(request.referrer or url_for("index"))
        old_values = {
            "name": group.name,
            "translate": group.translate,
            "descriptions": group.descriptions,
            "color": group.color,
        }
        name = request.form.get("edit_name", "").strip()
        translate = request.form.get("edit_translate", "").strip()
        descriptions = request.form.get("edit_descriptions", "").strip()
        color = request.form.get("edit_color", "").strip()
        logger.info(
            f"[EDIT] Старые значения: name='{old_values['name']}', translate='{old_values['translate']}', color='{old_values['color']}'"
        )
        logger.info(
            f"[EDIT] Новые значения: name='{name}', translate='{translate}', color='{color}'"
        )
        changed = False
        if name != (group.name or ""):
            group.name = name if name else None
            logger.info(f"[EDIT] Обновлено name: '{old_values['name']}' -> '{name}'")
            changed = True
        if translate != (group.translate or ""):
            group.translate = translate if translate else None
            logger.info(
                f"[EDIT] Обновлено translate: '{old_values['translate']}' -> '{translate}'"
            )
            changed = True
        if descriptions != (group.descriptions or ""):
            group.descriptions = descriptions if descriptions else None
            logger.info(
                f"[EDIT] Обновлено descriptions: было {len(old_values['descriptions'] or '')} символов, стало {len(descriptions)}"
            )
            changed = True
        valid_colors = (
            "primary",
            "secondary",
            "success",
            "danger",
            "warning",
            "info",
            "dark",
        )
        if color in valid_colors and color != group.color:
            logger.info(f"[EDIT] Обновлено color: '{old_values['color']}' -> '{color}'")
            group.color = color
            changed = True
        if changed:
            db.session.commit()
            if current_key:
                refresh_file_cache_by_key(current_key)
            logger.info(f"[EDIT] Группа '{edit_group_key}' успешно обновлена")
            flash("Данные группы обновлены.", "success")
        else:
            logger.info(f"[EDIT] Изменений не обнаружено")
            flash("Нет изменений для сохранения.", "warning")
        return redirect(
            url_for("index", key=current_key)
            if current_key
            else request.referrer or url_for("index")
        )
    else:
        flash(f"Неизвестное действие: {action}", "danger")
        return redirect(request.referrer or url_for("index"))


@app.errorhandler(404)
def page_not_found(e):
    logger.warning(f"[404] Страница не найдена: {request.url}")
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"[500] Внутренняя ошибка сервера: {e}", exc_info=True)
    return render_template("500.html"), 500


if __name__ == "__main__":
    debug = settings_dct.get("debug", True)
    with app.app_context():
        db.create_all()
        logger.info("База данных инициализирована")
    logger.info(f"Запуск приложения в режиме {'DEBUG' if debug else 'PRODUCTION'}")
    app.run(debug=debug, host="0.0.0.0", port=5000)
