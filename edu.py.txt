import ast
import re
from string import ascii_lowercase as al, ascii_uppercase as au, digits as dg
from pprint import pprint
from collections import defaultdict
from behoof import load_json, save_json


KEYS = [
    "class_names",
    "declared_vars",
    "function_calls",
    "function_names",
    "import_asname",
    "import_from",
    "imports",
    "load_vars",
    "store_vars",
    "assigned_types",  # <-- добавлено
]

BUILTIN_NAMES = {
    "abs", "all", "any", "ascii", "bin", "bool", "breakpoint", "bytearray", "bytes",
    "callable", "chr", "classmethod", "compile", "complex", "delattr", "dict", "dir",
    "divmod", "enumerate", "eval", "exec", "filter", "float", "format", "frozenset",
    "getattr", "globals", "hasattr", "hash", "help", "hex", "id", "input", "int",
    "isinstance", "issubclass", "iter", "len", "list", "locals", "map", "max",
    "memoryview", "min", "next", "object", "oct", "open", "ord", "pow", "print",
    "property", "range", "repr", "reversed", "round", "set", "setattr", "slice",
    "sorted", "staticmethod", "str", "sum", "super", "tuple", "type", "vars", "zip",
    "__import__", "__str__",
}



def ast_to_serializable(node):
    """
    Рекурсивно преобразует AST в сериализуемую структуру с сохранением позиций
    """
    if isinstance(node, ast.AST):
        result = {"_type": type(node).__name__}
        if hasattr(node, "lineno"):
            result["lineno"] = node.lineno
        if hasattr(node, "col_offset"):
            result["col_offset"] = node.col_offset
        for field in node._fields:
            value = getattr(node, field)
            result[field] = ast_to_serializable(value)
        return result
    elif isinstance(node, list):
        return [ast_to_serializable(item) for item in node]
    else:
        return node


def serializable_to_ast(data):
    """
    Рекурсивно преобразует сериализуемую структуру обратно в AST
    """
    if isinstance(data, dict) and "_type" in data:
        node_type = data["_type"]
        node_class = getattr(ast, node_type)
        kwargs = {}
        for field in node_class._fields:
            if field in data:
                kwargs[field] = serializable_to_ast(data[field])
        node = node_class(**kwargs)
        if "lineno" in data:
            node.lineno = data["lineno"]
        if "col_offset" in data:
            node.col_offset = data["col_offset"]
        return node
    elif isinstance(data, list):
        return [serializable_to_ast(item) for item in data]
    else:
        return data


class ASTJSONAnalyzer:
    """
    Анализатор ошибок на основе сериализованного AST
    """

    def __init__(self):
        self.errors = []
        self.context = {
            "store_vars": defaultdict(set),
            "load_vars": defaultdict(set),
            "imports": defaultdict(set),
            "import_from": defaultdict(set),
            "import_asname": defaultdict(set),
            "function_calls": defaultdict(set),
            "declared_vars": defaultdict(set),
            "class_names": defaultdict(set),
            "function_names": defaultdict(set),
            "assigned_types": defaultdict(list),
            "current_scope": "global",
            "scope_stack": ["global"],
        }

    def collect_context(self, node):
        """
        Сбор контекстной информации для анализа
        """
        if isinstance(node, list):
            for item in node:
                self.collect_context(item)
        elif isinstance(node, dict):
            node_type = node.get("_type")
            lineno = node.get("lineno", 0)
            match node_type:
                case "ImportFrom":
                    module = node.get("module")
                    if module:
                        self.context["imports"][module].add(lineno)
                    for name in node.get("names", []):
                        module_name = name.get("name", "")
                        module_key = f"{module}.{module_name}" if module else module_name
                        module_lineno = name.get("lineno", 0)
                        module_asname = name.get("asname")
                        self.context["import_from"][module_key].add(module_lineno)
                        if module_asname:
                            mak = f"{module}.{module_name} as {module_asname}"
                            self.context["import_asname"][mak].add(module_lineno)
                case "Import":
                    for alias in node.get("names", []):
                        module = alias.get("name", "")
                        if module:
                            self.context["imports"][module].add(lineno)
                case "Name":
                    var_name = node.get("id", "")
                    ctx_node = node.get("ctx", {})
                    ctx_type = ctx_node.get("_type", "")
                    if ctx_type == "Store":
                        self.context["store_vars"][var_name].add(lineno)
                        self.context["declared_vars"][var_name].add(lineno)
                    elif ctx_type == "Load":
                        self.context["load_vars"][var_name].add(lineno)
                case "Call":
                    func_node = node.get("func", {})
                    func_name = ""
                    if func_node.get("_type") == "Name":
                        func_name = func_node.get("id", "")
                    elif func_node.get("_type") == "Attribute":
                        func_name = func_node.get("attr", "")
                    if func_name:
                        self.context["function_calls"][func_name].add(lineno)
                case "Assign":
                    targets = node.get("targets", [])
                    value_node = node.get("value", {})
                    value_info = {"type": None, "repr": None}
                    if value_node.get("_type") == "Constant":
                        val = value_node.get("value")
                        value_info["type"] = type(val).__name__
                        value_info["repr"] = repr(val)
                    elif value_node.get("_type") == "List":
                        value_info["type"] = "list"
                        value_info["repr"] = "[...]"
                    elif value_node.get("_type") == "Dict":
                        value_info["type"] = "dict"
                        value_info["repr"] = "{...}"
                    elif value_node.get("_type") == "Tuple":
                        value_info["type"] = "tuple"
                        value_info["repr"] = "(...)"
                    elif value_node.get("_type") == "Set":
                        value_info["type"] = "set"
                        value_info["repr"] = "{...}"
                    elif value_node.get("_type") == "Call":
                        value_info["type"] = "unknown"
                        value_info["repr"] = "<call>"
                    else:
                        value_info["type"] = "unknown"
                        value_info["repr"] = "<unknown>"

                    for target in targets:
                        if isinstance(target, dict) and target.get("_type") == "Name":
                            var_name = target.get("id", "")
                            self.context["store_vars"][var_name].add(lineno)
                            self.context["declared_vars"][var_name].add(lineno)
                            self.context["assigned_types"][var_name].append({
                                "type": value_info["type"],
                                "repr": value_info["repr"],
                                "lineno": lineno
                            })
                case "FunctionDef":
                    func_name = node.get("name", "<anonymous>")
                    self.context["function_names"][func_name].add(lineno)
                    self.context["scope_stack"].append(f"function:{func_name}")
                    self.context["current_scope"] = f"function:{func_name}"
                    for item in node.get("body", []):
                        self.collect_context(item)
                    self.context["scope_stack"].pop()
                    self.context["current_scope"] = self.context["scope_stack"][-1] if self.context["scope_stack"] else "global"
                case "ClassDef":
                    class_name = node.get("name", "<anonymous>")
                    self.context["class_names"][class_name].add(lineno)
                    self.context["scope_stack"].append(f"class:{class_name}")
                    self.context["current_scope"] = f"class:{class_name}"
                    for item in node.get("body", []):
                        self.collect_context(item)
                    self.context["scope_stack"].pop()
                    self.context["current_scope"] = self.context["scope_stack"][-1] if self.context["scope_stack"] else "global"

            for value in node.values():
                if isinstance(value, (dict, list)):
                    self.collect_context(value)

    def groupon(self):
        """
        Группировка собранных данных по именам с обогащением метаинформацией
        """
        group_dct = {}
        
        for key, values in self.context.items():
            if not isinstance(values, dict) or not values:
                continue
            for name, line_numbers in values.items():
                if name not in group_dct:
                    group_dct[name] = {"lines": []}
                group_dct[name].setdefault(key, []).extend(line_numbers)
                if key != "assigned_types":
                    group_dct[name]["lines"].extend(line_numbers)
        
        if "assigned_types" in self.context:
            for name, assignments in self.context["assigned_types"].items():
                if name not in group_dct:
                    group_dct[name] = {"lines": []}
                group_dct[name]["assigned_types"] = assignments
                first = assignments[0]
                group_dct[name]["value_type"] = first["type"]
                group_dct[name]["value_repr"] = first["repr"]
                group_dct[name]["lines"].append(first["lineno"])

        for name, data in group_dct.items():
            data["lineno"] = min(data["lines"]) if data["lines"] else 0
            data["keys"] = [ctx_key for ctx_key in KEYS if ctx_key in data]
            data["dunderscore"] = name.startswith("__") and name.endswith("__") and len(name) > 4
            data["startdigit"] = bool(name) and name[0].isdigit()
            data["snakecase"] = bool(name) and set(name).issubset(set("_" + al + dg)) and not name[0].isdigit()
            data["camelcase"] = bool(name) and name[0].isupper() and set(name).issubset(set(al + au + dg))
            data["lowercase"] = bool(name) and name.islower() and set(name).issubset(set(al + dg + "_"))
            
        return group_dct

    def apply_rule(self, group_dct, rule):
        """
        Безопасное применение правил с контролируемым окружением для условий
        """
        violations = []
        rule_keys = rule.get("keys", [])
        condition = rule["condition"]
        
        try:
            compiled_condition = compile(condition, "<rule>", "eval")
        except SyntaxError as e:
            print(f"Синтаксическая ошибка в правиле {rule.get('code', 'N/A')}: {e}")
            return violations

        def re_search(pattern, s):
            try:
                return re.search(pattern, str(s)) is not None
            except Exception:
                return False

        for name, value in group_dct.items():
            if rule_keys and not any(key in value for key in rule_keys):
                continue
            
            safe_context = {
                'name': name,
                'value': value,
                'keys': value.get('keys', []),
                'lineno': value.get('lineno', 0),
                'underscore': name.startswith("_") and not name.startswith("__"),
                'dunderscore': value.get('dunderscore', False),
                'startdigit': value.get('startdigit', False),
                'snakecase': value.get('snakecase', False),
                'camelcase': value.get('camelcase', False),
                'lowercase': value.get('lowercase', False),
                'len': len,
                'any': any,
                'all': all,
                'set': set,
                'tuple': tuple,
                're_search': re_search,
                'BUILTIN_NAMES': BUILTIN_NAMES,
            }
            
            try:
                if eval(compiled_condition, {"__builtins__": {}}, safe_context):
                    violations.append({
                        "code": rule["code"],
                        "message": rule["message"].format(
                            name=name,
                            lineno=value.get('lineno', 0),
                            value_type=value.get('value_type', 'unknown'),
                            value_repr=value.get('value_repr', '<unknown>')
                        ),
                        "severity": rule["severity"],
                        "lineno": value.get('lineno', 0),
                        "name": name,
                    })
            except Exception as e:
                continue
        
        return violations


if __name__ == "__main__":
    filepath = "ast_checker_sample.py"
    with open(filepath, "r", encoding="utf-8") as f:
        test_code = f.read()

    # Парсинг и сериализация AST
    tree = ast.parse(test_code)
    serialized = ast_to_serializable(tree)
    save_json("data", "ast.json", serialized)

    # Загрузка и анализ
    loaded = load_json("data", "ast.json")
    analyzer = ASTJSONAnalyzer()
    analyzer.collect_context(loaded)
    group_dct = analyzer.groupon()
    pprint(group_dct)
    
    # Применение правил
    all_violations = []
    print("=" * 70)

    rules = load_json("data", "rules.json")
    for rule in rules:
        violations = analyzer.apply_rule(group_dct, rule)
        if violations:
            print(f"Правило {rule['code']} ({rule['severity']}):")
            for v in violations:
                print(f"{v['message']}")
            all_violations.extend(violations)
            print("-" * 70)
    
    if not all_violations:
        print("Ошибок нет!")
    else:
        print(f"Нарушений {len(all_violations)} из них:")
        print(f"- Ошибок {len([v for v in all_violations if v['severity'] == 'error'])}")
        print(f"- Предупреждений {len([v for v in all_violations if v['severity'] == 'warning'])}")
    
    print("=" * 70)
