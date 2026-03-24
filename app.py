import os
import json
import subprocess
from flask import Flask, render_template, request, redirect, url_for, flash
from behoof import load_json, save_json, calculate_md5


app = Flask(__name__)
app.secret_key = os.urandom(128)
settings_dct = load_json("settings", "app.json")
data_dir = settings_dct.get("data_dir", "data")
exclude_dirs = settings_dct.get("exclude_dirs", [])


@app.route("/", methods=["GET", "POST"])
def index():
    files_dct = load_json(data_dir, "group_line.json")

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
