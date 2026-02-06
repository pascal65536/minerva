# ::python3
# ::header

user_code = """
::code

if 3:
    print(111)

::footer
"""

import ast
import re
from collections import defaultdict


RULE = {
    "code": "RE-001",
    "keys": ["imports"],
    "condition": "name == 're'",
    "message": "Импорт модуля 're' запрещён в учебных заданиях (строка {lineno})",
    "severity": "warning",
}

def ast_to_serializable(node):
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


class ASTJSONAnalyzer:
    def __init__(self):
        self.context = {
            "imports": defaultdict(set),
        }

    def collect_context(self, node):
        if isinstance(node, list):
            for item in node:
                self.collect_context(item)
        elif isinstance(node, dict):
            node_type = node.get("_type")
            lineno = node.get("lineno", 0)
            if node_type == "Import":
                for alias in node.get("names", []):
                    module = alias.get("name", "")
                    if module:
                        self.context["imports"][module].add(lineno)
            elif node_type == "ImportFrom":
                module = node.get("module")
                if module:
                    self.context["imports"][module].add(lineno)
                for name in node.get("names", []):
                    mod_name = name.get("name", "")
                    full = f"{module}.{mod_name}" if module else mod_name
                    self.context["imports"][full].add(lineno)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    self.collect_context(value)

    def groupon(self):
        group_dct = {}
        for key, values in self.context.items():
            if not isinstance(values, dict):
                continue
            for name, line_numbers in values.items():
                if name not in group_dct:
                    group_dct[name] = {"lines": []}
                group_dct[name].setdefault(key, []).extend(line_numbers)
                group_dct[name]["lines"].extend(line_numbers)
                group_dct[name]["lineno"] = min(group_dct[name]["lines"])
                group_dct[name]["keys"] = [k for k in ["imports"] if k in group_dct[name]]
        return group_dct

    def apply_rule(self, group_dct, rule):
        violations = []
        rule_keys = rule.get("keys", [])
        try:
            compiled_condition = compile(rule["condition"], "<rule>", "eval")
        except SyntaxError:
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
                "name": name,
                "value": value,
                "keys": value.get("keys", []),
                "lineno": value.get("lineno", 0),
                "len": len,
                "any": any,
                "all": all,
                "set": set,
                "tuple": tuple,
                "re_search": re_search,
            }
            try:
                if eval(compiled_condition, {"__builtins__": {}}, safe_context):
                    violations.append(
                        {
                            "message": rule["message"].format(
                                name=name,
                                lineno=value.get("lineno", 0),
                                value_type=value.get("value_type", "unknown"),
                                value_repr=value.get("value_repr", "<unknown>"),
                            )
                        }
                    )
            except Exception:
                continue
        return violations


# stepik_input = """::python3
# ::header
# class Ticket:
#     def __init__(self):
#         self.price_list = list()

#     def get_data(self, text):
#         head = True
#         self.price_list.clear()
#         for row in text.split("\\n"):
#             if head:
#                 head = False
#                 continue
#             if not row:
#                 continue
#             name, cost = row.split(";")
#             self.price_list.append(
#                 {"Название товара": name, "Цена": int(cost), "Количество": 0}
#             )
#         return self.price_list
        
# ::code
# class Ticket:

#     def get_data(self, text):
#         pass

# ::footer
# import sys
# text = sys.stdin.read()
        
# ticket = Ticket()
# ret = ticket.get_data(text)
# print(ret)
# """

# Извлекаем только часть между ::code и ::footer
# lines = stepik_input.splitlines()
# inside_code = False
# user_lines = []
# for line in lines:
#     if line.strip() == "::code":
#         inside_code = True
#         continue
#     elif line.strip() == "::footer":
#         break
#     if inside_code:
#         user_lines.append(line)

# user_code = "\n".join(user_lines)

try:
    tree = ast.parse(user_code)
except SyntaxError as e:
    print(f"Синтаксическая ошибка: {e}")
    exit(1)

serialized = ast_to_serializable(tree)
analyzer = ASTJSONAnalyzer()
analyzer.collect_context(serialized)
group_dct = analyzer.groupon()
violations = analyzer.apply_rule(group_dct, RULE)

for v in violations:
    print(v["message"])
