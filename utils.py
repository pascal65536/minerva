from copy import deepcopy
import subprocess
import json
import re
from collections import defaultdict
import pprint
from behoof import save_json


transform_dct = {
    "code": None,
    "file": None,
    "line": None,
    "column": None,
    "message": None,
    "physical": None,
    "checker": None,
    "code_name": None,
    "column_end": None,
    "issue_confidence": None,
    "issue_cwe_id": None,
    "issue_cwe_link": None,
    "issue_severity": None,
}


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


def transform_flake8_to_vulture(flake8_output):
    local_dct = deepcopy(transform_dct)
    local_dct.update(
        {
            "code": flake8_output["code"],
            "file": flake8_output["filename"],
            "line": int(flake8_output["line_number"]),
            "column": int(flake8_output["column_number"]),
            "message": flake8_output["text"],
            "physical": flake8_output["physical_line"].rstrip(),
            "checker": "flake8",
        }
    )
    return local_dct


def transform_bandit_to_vulture(bandit_output):
    local_dct = deepcopy(transform_dct)
    local_dct.update(
        {
            "code": bandit_output["test_id"],
            "code_name": bandit_output["test_name"],
            "file": bandit_output["filename"].strip('.'),
            "line": int(bandit_output["line_number"]),
            "column": int(bandit_output["col_offset"]),
            "column_end": int(bandit_output["end_col_offset"]),
            "message": bandit_output["issue_text"],
            "physical": bandit_output["code"].rstrip(),
            "more_info": bandit_output["more_info"],
            "issue_confidence": bandit_output["issue_confidence"],
            "issue_cwe_id": bandit_output["issue_cwe"]["id"],
            "issue_cwe_link": bandit_output["issue_cwe"]["link"],
            "issue_severity": bandit_output["issue_severity"],
            "checker": "bandit",
        }
    )
    return local_dct


def transform_pylint_to_vulture(pylint_output):
    local_dct = deepcopy(transform_dct)
    local_dct.update(
        {
            "checker": "pylint",
            "code": pylint_output["message-id"],
            "code_name": pylint_output["symbol"],
            "issue_confidence": pylint_output["type"].upper(),
            "file": pylint_output["path"],
            "line": pylint_output["line"],
            "column": pylint_output["column"],
            "column_end": pylint_output["endColumn"],
            "message": pylint_output["message"],
            "physical": pylint_output["obj"].rstrip(),
        }
    )
    return local_dct


def transform_mypy_to_vulture(mypy_output):
    local_dct = deepcopy(transform_dct)
    code_str = mypy_output["code"]
    code = f"MY{sum(map(ord, code_str))}"    
    local_dct.update(
        {
            "code": code,
            "checker": "mypy",
            "code_name": mypy_output["code"],
            "issue_confidence": mypy_output["severity"].upper(),
            "file": mypy_output["file"],
            "line": mypy_output["line"],
            "column": mypy_output["column"],
            "message": mypy_output["message"],
            "physical": mypy_output["hint"],
        }
    )
    return local_dct


def transform_vulture_to_vulture(vulture_output):
    local_dct = deepcopy(transform_dct)
    code_str = "".join(vulture_output["message"].split()[:2])
    code = f"VU{sum(map(ord, code_str))}"
    local_dct.update(
        {
            "code": code,
            "checker": "vulture",
            "file": vulture_output["file"],
            "line": vulture_output["line"],
            "message": vulture_output["message"],
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
            "message": pycodestyle_output["message"],
        }
    )
    return local_dct


if __name__ == "__main__":
    filename = "fixtures/script_clean.py"

    group_line = defaultdict(list)
    group_code = defaultdict(list)

    res = run_flake8(filename)
    for flake8_output in res:
        r = transform_flake8_to_vulture(flake8_output)
        group_line[r["line"]].append(r)
        group_code[r["code"]].append(r)

    res = run_bandit(filename)
    for bandit_output in res:
        r = transform_bandit_to_vulture(bandit_output)
        group_line[r["line"]].append(r)
        group_code[r["code"]].append(r)

    res = run_pylint(filename)
    for pylint_output in res:
        r = transform_pylint_to_vulture(pylint_output)
        group_line[r["line"]].append(r)
        group_code[r["code"]].append(r)

    res = run_mypy(filename)
    for mypy_output in res:
        r = transform_mypy_to_vulture(mypy_output)
        group_line[r["line"]].append(r)
        group_code[r["code"]].append(r)

    res = run_vulture(filename)
    for vulture_output in res:
        r = transform_vulture_to_vulture(vulture_output)
        group_line[r["line"]].append(r)
        group_code[r["code"]].append(r)

    res = run_pycodestyle(filename)
    for pycodestyle_output in res:
        r = transform_pycodestyle_to_vulture(pycodestyle_output)
        group_line[r["line"]].append(r)
        group_code[r["code"]].append(r)

    print(group_line)
    print(group_code)

    save_json("data", "group_line.json", group_line)
    save_json("data", "group_code.json", group_code)
