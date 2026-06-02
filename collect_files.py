import os
import fnmatch


def should_ignore_dir(dirname):
    """Проверяет, нужно ли игнорировать директорию"""
    ignore_patterns = [
        ".cache",
        ".env",
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "data",
        "dist",
        "egg-info",
        "env",
        "fixtures",
        "instance",
        "log",
        "minerva-plugin",
        "node_modules",
        "settings",
        "venv",
    ]

    return any(fnmatch.fnmatch(dirname, pattern) for pattern in ignore_patterns)


def collect_files(root_dir, extensions):
    """Собирает файлы с заданными расширениями, игнорируя системные папки"""
    matched_files = []
    for foldername, subfolders, filenames in os.walk(root_dir):
        for subfolder in list(subfolders):
            if should_ignore_dir(subfolder):
                subfolders.remove(subfolder)
        for filename in filenames:
            if any(filename.endswith(ext) for ext in extensions):
                full_path = os.path.join(foldername, filename)
                relative_path = os.path.relpath(full_path, root_dir)
                matched_files.append((full_path, relative_path))
    return matched_files


def merge_files_to_txt(output_file, root_dir, extensions):
    """Объединяет содержимое всех найденных файлов в один txt файл"""
    files = collect_files(root_dir, extensions)
    if not files:
        print("Не найдено ни одного .py или .html файла.")
        return
    with open(output_file, "w", encoding="utf-8") as outfile:
        for full_path, rel_path in sorted(files):  # сортируем для удобства
            try:
                with open(full_path, "r", encoding="utf-8") as infile:
                    content = infile.read()
                outfile.write(f"{'='*80}\n")
                outfile.write(f"Путь: {rel_path}\n")
                outfile.write(f"{'='*80}\n")
                outfile.write(content)
                outfile.write(f"\n\n{'#'*80}\n\n")
                print(f"Добавлен: {rel_path}")
            except Exception as e:
                print(f"Ошибка при чтении {rel_path}: {e}")
                outfile.write(f"ОШИБКА ЧТЕНИЯ: {e}\n\n")

    print(f"\nГотово! Все файлы собраны в {output_file}")
    print(f"Всего обработано файлов: {len(files)}")


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    extensions = [".py", ".html"]
    output_filename = "collected_files.txt"
    output_path = os.path.join(current_dir, output_filename)
    print(f"Поиск .py и .html файлов в: {current_dir}")
    print(f"Игнорируются папки: venv, env, __pycache__, .git, и т.д.\n")
    merge_files_to_txt(output_path, current_dir, extensions)
