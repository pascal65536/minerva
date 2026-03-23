import subprocess
import json
import re


def parse_vulture_text(output: str):
    results = []
    for line in output.strip().split("\n"):
        if not line:
            continue
        match = re.match(r"^(.+?):(\d+):\s*(.*?)\s*(?:\(\d+% confidence\))?$", line)
        if match:
            file, line_no, message = match.groups()
            results.append(
                {"file": file, "line": int(line_no), "message": message.strip()}
            )
    return results


def parse_pycodestyle_text(raw_output):
    errors = []
    pattern = r"^(.+?):(\d+):(\d+):\s+([A-Z]\d{3})\s+(.+)$"
    for line in raw_output.strip().splitlines():
        match = re.match(pattern, line)
        if match:
            _, line_no, col_no, code, message = match.groups()
            errors.append(
                {
                    "line": int(line_no),
                    "column": int(col_no),
                    "code": code,
                    "message": message.strip(),
                }
            )
    return json.dumps({"errors": errors}, indent=2, ensure_ascii=False)


def run_bandit(filepath):
    task = ["bandit", "-f", "json", "-r", filepath]
    result = subprocess.run(task, capture_output=True, text=True)
    return result.stdout


def run_pylint(filepath):
    task = ["pylint", filepath, "--output-format=json"]
    result = subprocess.run(task, capture_output=True, text=True)
    return json.dumps({"errors": result.stdout}, indent=2, ensure_ascii=False)


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
    return result.stdout


def run_vulture(filepath):
    task = ["vulture", filepath]
    result = subprocess.run(task, capture_output=True, text=True)
    return parse_vulture_text(result.stdout) if result.stdout.strip() else []


def run_pycodestyle(filepath):
    task = ["pycodestyle", filepath]
    result = subprocess.run(task, capture_output=True, text=True)
    return parse_pycodestyle_text(result.stdout) if result.stdout.strip() else []


if __name__ == "__main__":
    filename = "fixtures/sample.py"

    res = run_flake8(filename)
    print(*res, sep='\n')
    exit()

    res = run_bandit(filename)
    print(res)

    res = run_pylint(filename)
    print(res)

    res = run_mypy(filename)
    print(res)

    res = run_vulture(filename)
    print(res)

    res = run_pycodestyle(filename)
    print(res)
