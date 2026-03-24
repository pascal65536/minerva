import os
import json
import subprocess
from flask import Flask, render_template, request, redirect, url_for, flash
from behoof import load_json, save_json, calculate_md5


app = Flask(__name__)
app.secret_key = os.urandom(128)
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
exclude_dirs = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "build",
    "dist",
}


def run_bandit(filepath):
    line = ["bandit", "-f", "json", "-r", filepath]
    result = subprocess.run(line, capture_output=True, text=True)
    return result.stdout


def run_pylint(filepath):
    line = ["pylint", filepath, "--output-format=json"]
    result = subprocess.run(line, capture_output=True, text=True)
    return result.stdout


def run_flake8(filepath):
    line = ["flake8", filepath, "--format=json"]
    result = subprocess.run(line, capture_output=True, text=True)
    return result.stdout


def run_filestr(filepath):
    with open(filepath) as f:
        content = f.readlines()

    result = []
    for line, raw in enumerate(content):
        result.append({"line": line + 1, "raw": raw.strip("\n")})
    return result


def update_reports_for_file(key, filepath):
    """
    Обновляем ошибки проекта
    """

    filecheck_dct = load_json("data", "filecheck.json", default={})
    filecheck_dct[key] = {
        "bandit": json.loads(run_bandit(filepath)).get("results"),
        "pylint": json.loads(run_pylint(filepath)),
        "flake8": json.loads(run_flake8(filepath)).get(filepath),
        "filestr": run_filestr(filepath),
    }
    for pyl in filecheck_dct[key]["pylint"]:
        pyl["message_id"] = pyl["message-id"]

    save_json("data", "filecheck.json", filecheck_dct)


def scan_python_files(root_dir):
    """
    Рекурсивно находит все .py файлы, игнорируя указанные директории
    """
    py_files = []
    if not os.path.exists(root_dir):
        return py_files

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Модифицируем список dirnames "на лету",
        # чтобы os.walk не заходил в исключённые папки
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        for f in filenames:
            if f.endswith(".py"):
                full_path = os.path.join(dirpath, f)
                py_files.append(full_path)

    return py_files


@app.route("/", methods=["GET", "POST"])
def index():
    files_dct = load_json("data", "files.json", default={})
    report = None
    selected_key = request.args.get("key")
    selected_file_info = None
    table_data = []
    progress_dct = {}

    if request.method == "POST":
        project_path = request.form.get("project_path", "").strip()
        if (
            project_path
            and os.path.exists(project_path)
            and os.path.isdir(project_path)
        ):
            save_json("data", "files.json", {})
            save_json("data", "filecheck.json", {})
            files_dct = {}
            all_py_files = scan_python_files(project_path)
            if not all_py_files:
                msg = "В указанной директории не найдено .py файлов."
                flash(msg, "warning")
                return redirect(url_for("index"))

            for fp in all_py_files:
                key = calculate_md5(fp)
                try:
                    display_path = os.path.relpath(fp, project_path)
                except:
                    display_path = fp
                files_dct[key] = {
                    "filename": os.path.basename(fp),
                    "filepath": fp,
                    "display_path": display_path,
                    "project_root": project_path,
                }

            save_json("data", "files.json", files_dct)

            for fp in all_py_files:
                key = calculate_md5(fp)
                update_reports_for_file(key, fp)
            msg = f"Проект '{project_path}' загружен. Найдено и проанализировано {len(all_py_files)} Python-файлов."
            flash(msg, "success")
            return redirect(url_for("index"))
        msg = "Пожалуйста, укажите корректный путь к существующей директории."
        flash(msg, "error")

    # Загружаем отчет, если выбран файл
    if selected_key and selected_key in files_dct:
        selected_file_info = files_dct[selected_key]
        filecheck_dct = load_json("data", "filecheck.json", default={})
        report = filecheck_dct.get(selected_key)

        if report:
            # Группировка данных по номерам строк и анализаторам
            grouped = {}

            for analyzer, issues in report.items():
                for issue in issues:
                    line_num = issue.get("line_number") or issue.get("line") or ""
                    grouped.setdefault(line_num, {}).setdefault(analyzer, dict())
                    grouped[line_num][analyzer] = issue

            # Сортируем номера строк по возрастанию (числа)
            def line_sort_key(x):
                try:
                    return int(x)
                except:
                    return float("inf")  # нечисловые строки в конец

            sorted_lines = sorted(grouped.keys(), key=line_sort_key)

            # Формируем данные для таблицы
            table_data = []
            for line in sorted_lines:
                bandit = grouped[line].get("bandit", {}).get("issue_confidence", None)
                pylint = grouped[line].get("pylint", {}).get("type", None)

                match (bandit, pylint):
                    case (None, None):
                        border = "border-primary"
                        table = "table-light"
                    case (None, "convention"):
                        border = "border-warning"
                        table = "table-warning"
                    case (None, "warning"):
                        border = "border-warning"
                        table = "table-warning"
                    case (None, "error"):
                        border = "border-danger"
                        table = "table-danger"
                    case (None, "refactor"):
                        border = "border-success"
                        table = "table-success"
                    case ("LOW", "error"):
                        border = "border-danger"
                        table = "table-danger"
                    case ("LOW", "warning"):
                        border = "border-warning"
                        table = "table-warning"
                    case ("LOW", "convention"):
                        border = "border-warning"
                        table = "table-warning"
                    case ("HIGH", "convention"):
                        border = "border-danger"
                        table = "table-danger"
                    case ("HIGH", "warning"):
                        border = "border-danger"
                        table = "table-danger"
                    case ("MEDIUM", None):
                        border = "border-danger"
                        table = "table-danger"
                    case ("HIGH", None):
                        border = "border-danger"
                        table = "table-danger"
                    case ("LOW", None):
                        border = "border-success"
                        table = "table-success"
                    case _:
                        border = "border-secondary"
                        table = "table-secondary"

                row = {
                    "line": line,
                    "bandit": grouped[line].get("bandit"),
                    "pylint": grouped[line].get("pylint"),
                    "flake8": grouped[line].get("flake8"),
                    "filestr": grouped[line].get("filestr", {}).get("raw"),
                    "border": border,
                    "table": table,
                }
                table_data.append(row)
                progress_dct.setdefault("total", 0)
                progress_dct.setdefault(border.split("-")[-1], 0)
                progress_dct[border.split("-")[-1]] += 1
                progress_dct["total"] += 1

            progress_dct.update(
                {
                    "primary1": int(
                        progress_dct.get("primary", 0) / progress_dct["total"] * 100
                    ),
                    "warning1": int(
                        progress_dct.get("warning", 0) / progress_dct["total"] * 100
                    ),
                    "danger1": int(
                        progress_dct.get("danger", 0) / progress_dct["total"] * 100
                    ),
                    "secondary1": int(
                        progress_dct.get("secondary", 0) / progress_dct["total"] * 100
                    ),
                    "success1": int(
                        progress_dct.get("success", 0) / progress_dct["total"] * 100
                    ),
                }
            )

    else:
        table_data = []

    return render_template(
        "index.html",
        files=files_dct,
        selected_key=selected_key,
        selected_file_info=selected_file_info,
        table_data=table_data,
        progress_dct=progress_dct,
    )


@app.route("/refresh/<key>")
def refresh(key):
    files_dct = load_json("data", "files.json", default={})
    if key in files_dct:
        filepath = files_dct[key]["filepath"]
        update_reports_for_file(key, filepath)
        msg = f"Отчет для '{files_dct[key]['display_path']}' обновлен."
        flash(msg, "info")
    else:
        flash("Файл не найден.", "error")
    return redirect(url_for("index", key=key))


@app.route("/refresh-all")
def refresh_all():
    files_dct = load_json("data", "files.json", default={})
    count = 0
    for key, info in files_dct.items():
        update_reports_for_file(key, info["filepath"])
        count += 1
    flash(f"Обновлено отчетов: {count}", "info")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
