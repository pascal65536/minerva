import os
from flask import Flask, render_template, request, redirect, url_for, flash
from behoof import load_json, save_json, calculate_md5
from utils import (
    group_line_update_or_create,
    raw_update_or_create,
    scan_python_files,
    erase_data,
)

app = Flask(__name__)
app.secret_key = os.urandom(128)
settings_dct = load_json("settings", "app.json")
data_dir = settings_dct.get("data_dir", "data")
exclude_dirs = settings_dct.get("exclude_dirs", [])

root_dir = "fixtures"


@app.route("/", methods=["GET", "POST"])
def index():
    selected_key = request.args.get("key")
    files_lst = scan_python_files(root_dir)
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
        files_lst=files_lst,
        selected_key=selected_key,
        selected_file_info=selected_file_info,
    )


@app.route("/refresh-all")
def refresh_all():
    erase_data()
    files_lst = scan_python_files(root_dir)
    count = 0
    for filename, *_ in files_lst:
        group_line_update_or_create(filename)
        raw_update_or_create(filename)
        count += 1
    flash(f"Обновлено отчетов: {count}", "info")
    return redirect(url_for("index"))


@app.route("/refresh/<key>")
def refresh(key):
    # files_dct = load_json("data", "files.json", default={})
    # if key in files_dct:
    #     filepath = files_dct[key]["filepath"]
    #     update_reports_for_file(key, filepath)
    #     msg = f"Отчет для '{files_dct[key]['display_path']}' обновлен."
    #     flash(msg, "info")
    # else:
    #     flash("Файл не найден.", "error")
    return redirect(url_for("index", key=key))


if __name__ == "__main__":
    app.run(debug=True)
