import ast
import re
import os
import json


def load_json(folder_name_lst, file_name, default=None):
    if default is None:
        default = {}
    if isinstance(folder_name_lst, str):
        folder_name = folder_name_lst
    elif isinstance(folder_name_lst, list):
        folder_name = os.path.join(*folder_name_lst)
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    filename = os.path.join(folder_name, file_name)
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=True)
    with open(filename, encoding="utf-8") as f:
        load_dct = json.load(f)
    return load_dct


def save_json(folder_name_lst, file_name, save_dct):
    if isinstance(folder_name_lst, str):
        folder_name = folder_name_lst
    elif isinstance(folder_name_lst, list):
        folder_name = os.path.join(*folder_name_lst)
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    filename = os.path.join(folder_name, file_name)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(save_dct, f, ensure_ascii=False, indent=4)


class Minerva:
    """
    Основной класс плагина Minerva.
    """

    name = "minerva"
    version = "1.3.0"
    directory = "settings"
    filename = "plugin.json"

    def __init__(self, tree: ast.AST, filename: str):
        self.tree = tree
        self.filename = filename

    @classmethod
    def add_options(cls, parser):
        """
        Регистрация настроек в flake8
        """
        settings = cls.load_settings()

        parser.add_option(
            "--min-var-length",
            action="store",
            type=int,
            default=settings.get("min_length", 2),
            parse_from_config=True,
            help="Минимальная длина имени переменной",
        )
        parser.add_option(
            "--max-var-length",
            action="store",
            type=int,
            default=settings.get("max_length", 40),
            parse_from_config=True,
            help="Максимальная длина имени переменной",
        )
        parser.add_option(
            "--allowed-single-letters",
            action="store",
            type=str,
            default=settings.get("allowed_single_letters", "i,j,x,y,e"),
            parse_from_config=True,
            help="Разрешенные однобуквенные имена через запятую",
        )
        parser.add_option(
            "--enforce-snake-case",
            action="store_true",
            default=settings.get("enforce_snake_case", True),
            parse_from_config=True,
            help="Требовать snake_case для имен переменных",
        )
        parser.add_option(
            "--prohibited-modules",
            action="store",
            type=str,
            default=settings.get("prohibited_modules", "math,re"),
            parse_from_config=True,
            help="Запрещенные модули для импорта через запятую",
        )

    @classmethod
    def parse_options(cls, options):
        """
        Парсинг полученных опций
        """
        cls.min_length = options.min_var_length
        cls.max_length = options.max_var_length
        cls.allowed_single_letters = set(
            letter.strip() for letter in options.allowed_single_letters.split(",")
        )
        cls.enforce_snake_case = options.enforce_snake_case
        cls.prohibited_modules = set(
            mod.strip() for mod in options.prohibited_modules.split(",") if mod.strip()
        )

    def run(self):
        """
        Генератор нарушений
        """
        settings = self.load_settings()
        visitor = MinervaVisitor(**settings)
        visitor.visit(self.tree)
        for violation in visitor.violations:
            yield violation

    @classmethod
    def load_settings(cls):
        """
        Загрузка настроек из файла
        """
        settings = load_json(cls.directory, cls.filename)
        if settings == {}:
            settings["min_length"] = 2
            settings["max_length"] = 40
            settings["allowed_single_letters"] = "i,j,x,y,e"
            settings["enforce_snake_case"] = True
            settings["prohibited_modules"] = "math,re"
            save_json(cls.directory, cls.filename, settings)
        return settings


class MinervaVisitor(ast.NodeVisitor):
    """
    Визитор AST дерева для проверки имен и импортов
    """

    def __init__(
        self,
        min_length,
        max_length,
        allowed_single_letters,
        enforce_snake_case,
        prohibited_modules,
    ):
        self.violations = list()
        self.min_length = min_length
        self.max_length = max_length
        
        self.allowed_single_letters = (
            set(letter.strip() for letter in allowed_single_letters.split(","))
            if isinstance(allowed_single_letters, str)
            else allowed_single_letters
        )

        self.enforce_snake_case = enforce_snake_case
        
        self.prohibited_modules = (
            set(mod.strip() for mod in prohibited_modules.split(",") if mod.strip())
            if isinstance(prohibited_modules, str)
            else prohibited_modules
        )

        self.snake_case_pattern = re.compile(r"^_?[a-z][a-z0-9_]*$")

    def _check_name(self, name, lineno, col_offset):
        if not name:
            return

        if name.startswith("__") and name.endswith("__"):
            return

        if len(name) < self.min_length:
            if name not in self.allowed_single_letters:
                msg = f"MN001 variable name too short (min {self.min_length} chars)"
                candidate = (lineno, col_offset, msg, Minerva)
                if candidate not in self.violations:
                    self.violations.append(candidate)
                return

        if len(name) > self.max_length:
            msg = f"MN002 variable name too long (max {self.max_length} chars)"
            candidate = (lineno, col_offset, msg, Minerva)
            if candidate not in self.violations:
                self.violations.append(candidate)
            return

        if name.isupper():
            return

        if self.enforce_snake_case:
            if not self.snake_case_pattern.match(name):
                msg = "MN003 variable name must be in snake_case"
                candidate = (lineno, col_offset, msg, Minerva)
                if candidate not in self.violations:
                    self.violations.append(candidate)

    def _check_import(self, module_name, lineno, col_offset):
        """
        Проверка модуля на наличие в списке ЗАПРЕЩЕННЫХ (Black List)
        """
        if not self.prohibited_modules:
            return

        base_module = module_name.split(".")[0]

        if base_module in self.prohibited_modules:
            msg = f"MN004 import of '{base_module}' is prohibited"
            candidate = (lineno, col_offset, msg, Minerva)
            if candidate not in self.violations:
                self.violations.append(candidate)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self._check_import(alias.name, node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self._check_import(node.module, node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self._check_name(node.id, node.lineno, node.col_offset)
        else:
            self.generic_visit(node)

    def visit_arg(self, node: ast.arg):
        self._check_name(node.arg, node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        self._visit_target(node.target)
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor):
        self._visit_target(node.target)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            self._visit_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            self._check_name(node.target.id, node.target.lineno, node.target.col_offset)
        else:
            self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr):
        if isinstance(node.target, ast.Name):
            self._check_name(node.target.id, node.target.lineno, node.target.col_offset)
        else:
            self.generic_visit(node)

    def _visit_target(self, target: ast.expr):
        """
        Рекурсивный обход целей присваивания
        """
        if isinstance(target, ast.Name):
            self._check_name(target.id, target.lineno, target.col_offset)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._visit_target(elt)