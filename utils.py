import os
from copy import deepcopy
import subprocess
import json
import re
from collections import defaultdict
from behoof import load_json, save_json, calculate_md5, str_to_md5

settings_dct = load_json("settings", "app.json")
data_dir = settings_dct.get("data_dir", "data")
exclude_dirs = settings_dct.get("exclude_dirs", [])
transform_dct = settings_dct.get("transform_dct", {})

os.makedirs(data_dir, exist_ok=True)


def create_key(checker, code):
    return str_to_md5(get_key_checker_code(checker, code))

def get_key_checker_code(checker, code):
    key = f"{checker}|{code}"
    return key

def parse_vulture_text(output):
    results = []
    for line in output.strip().split("\n"):
        if not line:
            continue
        match = re.match(r"^(.+?):(\d+):\s*(.*?)\s*(?:\(\d+% confidence\))?$", line)
        if not match:
            continue
        file, line_no, message = match.groups()
        item = {"file": file, "line": int(line_no), "message": message.strip()}
        results.append(item)
    return results


def parse_pycodestyle_text(raw_output):
    errors = []
    pattern = r"^(.+?):(\d+):(\d+):\s+([A-Z]\d{3})\s+(.+)$"
    for line in raw_output.strip().splitlines():
        match = re.match(pattern, line)
        if not match:
            continue
        _, line_no, col_no, code, message = match.groups()
        line_no = int(line_no)
        col_no = int(col_no)
        message = message.strip()
        item = {"line": line_no, "column": col_no, "code": code, "message": message}
        errors.append(item)
    return errors


def run_bandit(filepath):
    task = ["bandit", "-f", "json", "-r", filepath]
    result = subprocess.run(task, capture_output=True, text=True)
    return json.loads(result.stdout).get("results", [])


def run_pylint(filepath):
    task = ["pylint", filepath, "--output-format=json"]
    result = subprocess.run(task, capture_output=True, text=True)
    return json.loads(result.stdout)


def run_flake8(filepath):
    task = ["flake8", filepath, "--format=json"]
    result = subprocess.run(task, capture_output=True, text=True)
    res = []
    for _, value in json.loads(result.stdout).items():
        res.extend(value)
    return res


def run_mypy(filepath):
    task = ["mypy", filepath, "--output=json"]
    result = subprocess.run(task, capture_output=True, text=True)
    res = []
    for row in result.stdout.splitlines():
        if not row:
            continue
        res.append(json.loads(row))
    return res


def run_vulture(filepath):
    task = ["vulture", filepath]
    result = subprocess.run(task, capture_output=True, text=True)
    return parse_vulture_text(result.stdout) if result.stdout.strip() else []


def run_pycodestyle(filepath):
    task = ["pycodestyle", filepath]
    result = subprocess.run(task, capture_output=True, text=True)
    return parse_pycodestyle_text(result.stdout) if result.stdout.strip() else []


def run_filestr(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.readlines()

    result = []
    for line, raw in enumerate(content):
        result.append({"line": line + 1, "raw": raw.strip("\n")})
    return result


def transform_flake8_to_vulture(flake8_output):
    local_dct = deepcopy(transform_dct)
    color = "danger"
    local_dct.update(
        {
            "code": flake8_output["code"],
            "file": flake8_output["filename"].replace("\\", "/"),
            "line": int(flake8_output["line_number"]),
            "column": int(flake8_output["column_number"]),
            "message": flake8_output["text"].replace('"', "'"),
            "physical": flake8_output["physical_line"].rstrip(),
            "checker": "flake8",
            "color": color,
        }
    )
    return local_dct


def transform_bandit_to_vulture(bandit_output):
    local_dct = deepcopy(transform_dct)
    color_dct = {
        "HIGH": "danger",
        "CRITICAL": "warning",
        "MEDIUM": "primary",
        "LOW": "success",
    }
    color = color_dct.get(bandit_output["issue_severity"], "dark")
    local_dct.update(
        {
            "code": bandit_output["test_id"],
            "code_name": bandit_output["test_name"],
            "file": bandit_output["filename"].strip(".").replace("\\", "/"),
            "line": int(bandit_output["line_number"]),
            "column": int(bandit_output["col_offset"]),
            "column_end": int(bandit_output["end_col_offset"]),
            "message": bandit_output["issue_text"].replace('"', "'"),
            "physical": bandit_output["code"].rstrip(),
            "more_info": bandit_output["more_info"],
            "issue_confidence": bandit_output["issue_confidence"],
            "issue_cwe_id": bandit_output["issue_cwe"]["id"],
            "issue_cwe_link": bandit_output["issue_cwe"]["link"],
            "issue_severity": bandit_output["issue_severity"],
            "checker": "bandit",
            "color": color,
        }
    )
    return local_dct


def transform_pylint_to_vulture(pylint_output):
    local_dct = deepcopy(transform_dct)

    if "type" not in pylint_output and "symbol" in pylint_output:
        if pylint_output["symbol"] in ["possibly-used-before-assignment"]:
            pylint_output["type"] = "error"
        elif pylint_output["symbol"] in ["invalid-name", "missing-module-docstring"]:
            pylint_output["type"] = "convention"
        elif pylint_output["symbol"] in ["unused-import"]:
            pylint_output["type"] = "warning"
    color_dct = {
        "warning": "info",
        "error": "primary",
        "convention": "success",
    }
    color = color_dct.get(pylint_output["type"], "dark")
    local_dct.update(
        {
            "checker": "pylint",
            "code": pylint_output["message-id"],
            "code_name": pylint_output["symbol"],
            "type": pylint_output["type"],
            "file": pylint_output["path"].replace("\\", "/"),
            "line": pylint_output["line"],
            "column": pylint_output["column"],
            "column_end": pylint_output["endColumn"],
            "message": pylint_output["message"].replace('"', "'"),
            "physical": pylint_output["obj"].rstrip(),
            "color": color,
        }
    )
    return local_dct


def transform_mypy_to_vulture(mypy_output):
    local_dct = deepcopy(transform_dct)
    code_str = mypy_output["code"]
    code = f"MY{sum(map(ord, code_str))}"
    color_dct = {"ERROR": "danger"}
    color = color_dct.get(mypy_output["severity"].upper(), "dark")
    local_dct.update(
        {
            "code": code,
            "checker": "mypy",
            "code_name": mypy_output["code"],
            "issue_severity": mypy_output["severity"].upper(),
            "file": mypy_output["file"].replace("\\", "/"),
            "line": mypy_output["line"],
            "column": mypy_output["column"],
            "message": mypy_output["message"].replace('"', "'"),
            "physical": mypy_output["hint"],
            "color": color,
        }
    )
    return local_dct


def transform_vulture_to_vulture(vulture_output):
    local_dct = deepcopy(transform_dct)
    code_str = "".join(vulture_output["message"].split()[:2])
    code = f"VU{sum(map(ord, code_str))}"
    color = "danger"
    local_dct.update(
        {
            "code": code,
            "checker": "vulture",
            "file": vulture_output["file"].replace("\\", "/"),
            "line": vulture_output["line"],
            "message": vulture_output["message"].replace('"', "'"),
            "color": color,
        }
    )
    return local_dct


def transform_pycodestyle_to_vulture(pycodestyle_output):
    local_dct = deepcopy(transform_dct)
    local_dct.update(
        {
            "checker": "vulture",
            "code": pycodestyle_output["code"],
            "column": pycodestyle_output["column"],
            "line": pycodestyle_output["line"],
            "message": pycodestyle_output["message"].replace('"', "'"),
        }
    )
    return local_dct


def transform_filestr_to_vulture(filestr_output):
    local_dct = dict()
    local_dct.update(
        {
            "checker": "filestr",
            "raw": filestr_output["raw"],
            "line": filestr_output["line"],
        }
    )
    return local_dct


def group_line_update_or_create(filename):
    md5_hash = calculate_md5(filename)
    group_line_file = f"{md5_hash}.json"
    group_line = load_json(data_dir, group_line_file)
    if group_line == {}:
        group_line = calc_group_line(filename)
        save_json(data_dir, group_line_file, group_line)
    return group_line


def raw_update_or_create(filename):
    md5_hash = calculate_md5(filename)
    raw_file = f"{md5_hash}_raw.json"
    raw_dct = load_json(data_dir, raw_file)
    if raw_dct == {}:
        with open(filename, "r", encoding="utf-8", errors="replace") as f:
            content = f.readlines()
        for line, raw in enumerate(content):
            raw_dct[line + 1] = raw.rstrip("\n")
        save_json(data_dir, raw_file, raw_dct)
    return raw_dct


def calc_group_line(filename):
    group_line = defaultdict(list)

    res = run_flake8(filename)
    for flake8_output in res:
        r = transform_flake8_to_vulture(flake8_output)
        group_line[r["line"]].append(r)

    res = run_bandit(filename)
    for bandit_output in res:
        r = transform_bandit_to_vulture(bandit_output)
        group_line[r["line"]].append(r)

    res = run_pylint(filename)
    for pylint_output in res:
        r = transform_pylint_to_vulture(pylint_output)
        group_line[r["line"]].append(r)

    res = run_mypy(filename)
    for mypy_output in res:
        r = transform_mypy_to_vulture(mypy_output)
        group_line[r["line"]].append(r)

    res = run_vulture(filename)
    for vulture_output in res:
        r = transform_vulture_to_vulture(vulture_output)
        group_line[r["line"]].append(r)

    res = run_pycodestyle(filename)
    for pycodestyle_output in res:
        r = transform_pycodestyle_to_vulture(pycodestyle_output)
        group_line[r["line"]].append(r)

    return group_line


def scan_python_files(root_dir):
    py_files = []
    if not os.path.exists(root_dir):
        return py_files

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for f in filenames:
            if not f.endswith(".py"):
                continue
            full_path = os.path.join(dirpath, f)
            py_files.append((full_path, f, calculate_md5(full_path)))
    return sorted(py_files)


# def scan_python_files(root_dir):
#     """
#     Сканировать директории на наличие Python-файлов.
#     Возвращает список кортежей: (display_path, filename, key)
#     """
#     from pathlib import Path

#     py_files = []
#     root_path = Path(root_dir).resolve()

#     if not root_path.exists() or not root_path.is_dir():
#         return py_files

#     for path in root_path.rglob("*.py"):
#         # Пропускаем файлы, которых нет в текущей ФС (например, из контейнеров)
#         if not path.exists() or not path.is_file():
#             continue

#         try:
#             full_path = str(path)
#             display_path = str(path.relative_to(root_path))
#             filename = path.name
#             key = calculate_md5(full_path)

#             py_files.append((display_path, filename, key))
#         except (OSError, ValueError):
#             # Пропускаем файлы, которые не удалось обработать
#             continue

#     # Сортируем по имени файла
#     py_files.sort(key=lambda x: x[1])

#     return py_files

def erase_data(key=None):
    for file in os.listdir(data_dir):
        if not file.endswith(".json"):
            continue
        if key:
            if file.startswith(key):
                os.remove(os.path.join(data_dir, file))
        else:
            os.remove(os.path.join(data_dir, file))


def get_checker_code(filename):
    accumulator = set()
    checker_code_dct = load_json("settings", "checker_code.json", default=[])
    ret = group_line_update_or_create(filename)
    for _, checks in ret.items():
        for test in checks:
            key = test["checker"], test["code"]
            if key in accumulator:
                continue
            accumulator.add(key)

            test.pop("file")
            test.pop("line")
            test.pop("column")
            test.pop("column_end")
            test.pop("physical")
            test.pop("issue_confidence")
            test.pop("issue_cwe_id")
            test.pop("issue_cwe_link")
            test.pop("issue_severity")
            test.pop("message")
            if "more_info" in test:
                test.pop("more_info")
            checker_code_dct.append(test)
    save_json("settings", "checker_code.json", checker_code_dct)
    return checker_code_dct


def get_teacher_lst():
    teacher_lst = load_json("settings", "teacher.json", default=[])
    return teacher_lst


def get_teacher(filename):
    teacher_lst = load_json("settings", "teacher.json", default=[])
    ret = group_line_update_or_create(filename)
    for _, checks in ret.items():
        for checker_code in checks:
            key = get_key_checker_code(checker_code['checker'], checker_code['code'])
            teacher_lst.append(key)
    teacher_sorted_lst = sorted(set(teacher_lst))
    save_json("settings", "teacher.json", teacher_sorted_lst)
    return teacher_sorted_lst


if __name__ == "__main__":
    teacher_lst = load_json("settings", "teacher.json", default=[])
    for teacher in teacher_lst:
        print(teacher)
