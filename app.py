import sys
import os
import ast
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QTableWidget, QTableWidgetItem, QFileDialog, QSplitter,
    QHeaderView, QMessageBox, QLabel, QTabWidget, QDialog, QDialogButtonBox,
    QFormLayout, QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush
from collections import defaultdict
from edu import ast_to_serializable, ASTJSONAnalyzer
from behoof import load_json, save_json


class RuleEditorWidget(QWidget):
    """
    Виджет редактора правил для интеграции в основное окно
    """
    rule_saved = pyqtSignal(dict, int)
    rule_deleted = pyqtSignal(int)
    rule_cancelled = pyqtSignal()

    def __init__(self, rule=None, rule_index=-1, context_keys=None, parent=None):
        super().__init__(parent)
        self.rule = rule or {}
        self.rule_index = rule_index
        self.context_keys = context_keys or [
            "store_vars", "load_vars", "imports", "import_from",
            "import_asname", "function_calls", "declared_vars",
            "class_names", "function_names"
        ]
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Заголовок
        title = QLabel(f"{'Редактирование правила' if self.rule else 'Создание нового правила'}")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Форма правила
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Код правила
        self.code_edit = QLineEdit(self.rule.get("code", "").strip())
        self.code_edit.setPlaceholderText("Например: STYLE-001")
        self.code_edit.setFont(QFont("Consolas", 11))
        form_layout.addRow("Код правила:", self.code_edit)

        # Ключи (мультивыбор)
        self.keys_list = QListWidget()
        self.keys_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.keys_list.setMinimumHeight(100)
        self.keys_list.setFont(QFont("Segoe UI", 10))
        
        selected_keys = self.rule.get("keys", [])
        if isinstance(selected_keys, str):
            selected_keys = [k.strip() for k in selected_keys.split(",") if k.strip()]
        
        for key in self.context_keys:
            item = QListWidgetItem(key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if key in selected_keys else Qt.CheckState.Unchecked
            )
            self.keys_list.addItem(item)
        
        form_layout.addRow("Контекстные ключи (keys):", self.keys_list)

        # Условие
        self.condition_edit = QTextEdit(self.rule.get("condition", "").strip())
        self.condition_edit.setMaximumHeight(100)
        self.condition_edit.setFont(QFont("Consolas", 10))
        self.condition_edit.setPlaceholderText(
            "Доступные переменные:\n"
            "  - name, keys, lineno\n"
            "  - snakecase, camelcase, startdigit, dunderscore\n"
            "  - BUILTIN_NAMES\n"
            "  - len(), any(), all()\n\n"
            "Примеры:\n"
            "  name in ['eval', 'exec']\n"
            "  not snakecase and not dunderscore\n"
            "  startdigit"
        )
        form_layout.addRow("Условие (Python):", self.condition_edit)

        # Сообщение
        self.message_edit = QTextEdit(self.rule.get("message", "").strip())
        self.message_edit.setMaximumHeight(80)
        self.message_edit.setFont(QFont("Consolas", 10))
        self.message_edit.setPlaceholderText(
            "Поддерживает подстановку: {name}, {lineno}\n"
            "Пример: Имя переменной '{name}' должно быть в snake_case (строка {lineno})"
        )
        form_layout.addRow("Сообщение:", self.message_edit)

        # Уровень серьёзности
        self.severity_combo = QComboBox()
        self.severity_combo.addItems(["info", "low", "medium", "warning", "high", "error", "critical"])
        severity = self.rule.get("severity", "warning").strip().lower()
        idx = self.severity_combo.findText(severity, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.severity_combo.setCurrentIndex(idx)
        form_layout.addRow("Уровень серьёзности:", self.severity_combo)

        layout.addLayout(form_layout)

        # Кнопки управления
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.save_btn = QPushButton("✅ Сохранить правило")
        self.save_btn.clicked.connect(self.save_rule)
        self.save_btn.setStyleSheet("padding: 8px 16px; background-color: #2ecc71; color: white; font-weight: bold;")

        self.cancel_btn = QPushButton("❌ Отмена")
        self.cancel_btn.clicked.connect(self.rule_cancelled.emit)
        self.cancel_btn.setStyleSheet("padding: 8px 16px;")

        btn_layout.addWidget(self.save_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def get_selected_keys(self):
        """
        Получает список выбранных ключей
        """
        return [
            self.keys_list.item(i).text()
            for i in range(self.keys_list.count())
            if self.keys_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def save_rule(self):
        """
        Сохраняет правило и генерирует сигнал
        """
        code = self.code_edit.text().strip()
        if not code:
            QMessageBox.warning(self, "Ошибка", "Код правила не может быть пустым!")
            return

        keys = self.get_selected_keys()
        if not keys:
            reply = QMessageBox.question(
                self, "Подтверждение",
                "Правило без контекстных ключей может не сработать.\nПродолжить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        rule = {
            "code": code,
            "keys": keys,
            "condition": self.condition_edit.toPlainText().strip(),
            "message": self.message_edit.toPlainText().strip(),
            "severity": self.severity_combo.currentText().strip().lower()
        }

        self.rule_saved.emit(rule, self.rule_index)


class CodeCheckerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AST Educational Code Checker")
        self.resize(1600, 950)
        self.code_lines = []
        self.current_file = None
        self.analyzer = None
        self.errors_by_line = defaultdict(list)
        self.all_errors = []
        self.current_rules = []
        self.selected_line = 0
        self.selected_rule_index = -1
        self.context_keys = [
            "store_vars", "load_vars", "imports", "import_from",
            "import_asname", "function_calls", "declared_vars",
            "class_names", "function_names"
        ]
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        self.load_btn = QPushButton("📂 Открыть файл (Ctrl+O)")
        self.load_btn.setShortcut("Ctrl+O")
        self.load_btn.clicked.connect(self.load_file)
        self.load_btn.setStyleSheet("padding: 8px 16px; font-weight: bold;")

        self.analyze_btn = QPushButton("🔍 Анализировать (F5)")
        self.analyze_btn.setShortcut("F5")
        self.analyze_btn.clicked.connect(self.run_analysis)
        self.analyze_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px;"
        )

        self.clear_btn = QPushButton("🗑️ Очистить")
        self.clear_btn.clicked.connect(self.clear_all)
        self.clear_btn.setStyleSheet("padding: 8px 16px;")

        self.add_rule_btn = QPushButton("➕ Добавить правило")
        self.add_rule_btn.clicked.connect(self.show_rule_editor)
        self.add_rule_btn.setStyleSheet("background-color: #3498db; color: white; padding: 8px 16px;")

        self.save_rules_btn = QPushButton("💾 Сохранить правила")
        self.save_rules_btn.clicked.connect(self.save_rules_to_file)
        self.save_rules_btn.setStyleSheet("background-color: #2ecc71; color: white; padding: 8px 16px;")

        buttons_layout.addWidget(self.load_btn)
        buttons_layout.addWidget(self.analyze_btn)
        buttons_layout.addWidget(self.clear_btn)
        buttons_layout.addWidget(self.add_rule_btn)
        buttons_layout.addWidget(self.save_rules_btn)
        buttons_layout.addStretch()
        main_layout.addLayout(buttons_layout)

        # Основной горизонтальный сплиттер: код | результаты + правила
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая панель: редактор кода
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Исходный код Python:"))
        self.code_editor = QTextEdit()
        self.code_editor.setFont(QFont("Consolas", 11))
        self.code_editor.setPlaceholderText(
            "Введите или загрузите Python-код для анализа\n\n"
            "Пример:\nimport subprocess\n\neval('2 + 2')\n\nx = 5\nMyClass = type('MyClass', (), {})"
        )
        left_layout.addWidget(self.code_editor)
        main_splitter.addWidget(left_widget)

        # Правая вертикальная панель: результаты + правила
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Верхняя панель: результаты анализа (ВСЕ строки)
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.addWidget(QLabel("Результаты анализа (все строки кода):"))

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["№", "Код ошибки", "Строка кода", "Описание ошибки"])
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.results_table.setColumnWidth(0, 50)
        self.results_table.setColumnWidth(1, 120)
        self.results_table.setFont(QFont("Consolas", 10))
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QTableWidget::item {
                padding: 4px;
            }
        """)
        self.results_table.itemClicked.connect(self.on_line_selected)
        results_layout.addWidget(self.results_table)
        right_splitter.addWidget(results_widget)
        right_splitter.setStretchFactor(0, 2)

        # Нижняя панель: правила + редактор
        rules_editor_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Таблица правил
        rules_widget = QWidget()
        rules_layout = QVBoxLayout(rules_widget)
        rules_layout.addWidget(QLabel("Правила для выбранной строки / Все правила:"))

        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(4)
        self.rules_table.setHorizontalHeaderLabels(["Код", "Ключи", "Уровень", "Условие (кратко)"])
        rule_header = self.rules_table.horizontalHeader()
        rule_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        rule_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        rule_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        rule_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.rules_table.setColumnWidth(1, 180)
        self.rules_table.setFont(QFont("Consolas", 9))
        self.rules_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rules_table.itemClicked.connect(self.on_rule_selected)
        rules_layout.addWidget(self.rules_table)
        rules_editor_splitter.addWidget(rules_widget)

        # Редактор правил (изначально скрыт)
        self.rule_editor_container = QWidget()
        self.rule_editor_container.hide()
        rules_editor_splitter.addWidget(self.rule_editor_container)
        rules_editor_splitter.setStretchFactor(0, 1)
        rules_editor_splitter.setStretchFactor(1, 1)

        right_splitter.addWidget(rules_editor_splitter)
        right_splitter.setStretchFactor(1, 1)

        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)

        main_layout.addWidget(main_splitter)

        # Загрузка правил при старте
        self.load_rules()
        self.statusBar().showMessage("Готов к анализу кода — загрузите файл или введите код")

    def clear_all(self):
        """
        Очистка всех полей
        """
        self.code_editor.clear()
        self.clear_results()
        self.hide_rule_editor()
        self.current_file = None
        self.analyzer = None
        self.errors_by_line.clear()
        self.all_errors = []
        self.selected_line = 0
        self.statusBar().showMessage("Очищено")

    def clear_results(self):
        """
        Очистка таблицы результатов
        """
        self.results_table.setRowCount(0)
        self.results_table.clearContents()
        self.rules_table.setRowCount(0)
        self.rules_table.clearContents()

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Открыть Python файл", "", "Python файлы (*.py);;Все файлы (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            self.code_editor.setPlainText(code)
            self.current_file = file_path
            self.code_lines = code.splitlines()
            self.statusBar().showMessage(f"Загружен: {os.path.basename(file_path)}")
            self.clear_results()
            self.hide_rule_editor()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл:\n{str(e)}")

    def clean_rule(self, rule):
        """
        Очищает правило от пробелов в ключах и исправляет ошибки в условиях
        """
        clean = {}
        for key, value in rule.items():
            clean_key = key.strip()
            
            if isinstance(value, str):
                clean_value = value.strip()
                # Исправление известных ошибок
                if clean_key == "condition":
                    clean_value = clean_value.replace("' import '", "'__import__'")
                    clean_value = clean_value.replace("' import'", "'__import__'")
                    clean_value = clean_value.replace(" 'import'", "'__import__'")
                    clean_value = clean_value.replace("name.startswith(' ')", "name.startswith('_')")
            elif isinstance(value, list):
                clean_value = [v.strip() if isinstance(v, str) else v for v in value if v is not None]
            else:
                clean_value = value
            
            if clean_value is not None and (clean_value or clean_key in ("keys", "condition", "message")):
                clean[clean_key] = clean_value
        return clean

    def load_rules(self):
        """
        Загружает правила из JSON с автоматической очисткой
        """
        try:
            raw_rules = load_json('data', 'rules.json')
            if not isinstance(raw_rules, list):
                raise ValueError("Некорректный формат правил")
            
            rules = []
            for rule in raw_rules:
                try:
                    clean = self.clean_rule(rule)
                    # Проверка обязательных полей
                    if all(k in clean for k in ["code", "keys", "condition", "message", "severity"]):
                        rules.append(clean)
                except:
                    continue
            
            self.current_rules = rules
            self.display_rules_table()
            self.statusBar().showMessage(f"Загружено правил: {len(rules)}")
            
        except FileNotFoundError:
            self.current_rules = self.get_default_rules()
            self.display_rules_table()
            self.statusBar().showMessage("Файл правил не найден — использованы правила по умолчанию")
        except Exception as e:
            QMessageBox.warning(self, "Предупреждение", f"Ошибка загрузки правил:\n{str(e)}")
            self.current_rules = self.get_default_rules()
            self.display_rules_table()

    def get_default_rules(self):
        """
        Правила по умолчанию
        """
        return [
            {
                "code": "SEC-001",
                "keys": ["function_calls"],
                "condition": "name in ['eval', 'exec', 'compile', '__import__']",
                "message": "Запрещено использование опасной функции '{name}' (строка {lineno})",
                "severity": "error"
            },
            {
                "code": "SEC-002",
                "keys": ["imports", "import_from"],
                "condition": "name in ['os', 'sys', 'subprocess', 'pickle', 'socket', 'ctypes']",
                "message": "Запрещён импорт модуля '{name}' (строка {lineno})",
                "severity": "error"
            },
            {
                "code": "STYLE-001",
                "keys": ["store_vars", "declared_vars"],
                "condition": "not snakecase and not dunderscore and not name.startswith('_') and name not in BUILTIN_NAMES and len(name) > 1",
                "message": "Имя переменной '{name}' должно быть в snake_case (строка {lineno})",
                "severity": "warning"
            }
        ]

    def display_rules_table(self, filtered_rules=None):
        """
        Отображает правила в таблице
        """
        rules = filtered_rules if filtered_rules is not None else self.current_rules
        self.rules_table.setRowCount(len(rules))
        
        severity_colors = {
            "critical": QColor(255, 150, 150),
            "error": QColor(255, 180, 180),
            "high": QColor(255, 200, 180),
            "warning": QColor(255, 255, 200),
            "medium": QColor(230, 255, 230),
            "low": QColor(220, 240, 255),
            "info": QColor(240, 240, 240),
        }
        
        for i, rule in enumerate(rules):
            code = rule.get("code", "N/A")
            severity = rule.get("severity", "info").lower()
            bg_color = severity_colors.get(severity, QColor(240, 240, 240))
            
            # Код
            item = QTableWidgetItem(code)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(QBrush(bg_color))
            self.rules_table.setItem(i, 0, item)
            
            # Ключи
            keys = ", ".join(rule.get("keys", []))
            item = QTableWidgetItem(keys)
            item.setBackground(QBrush(bg_color))
            self.rules_table.setItem(i, 1, item)
            
            # Уровень
            item = QTableWidgetItem(severity.upper())
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(QBrush(bg_color))
            self.rules_table.setItem(i, 2, item)
            
            # Условие
            cond = rule.get("condition", "")[:60] + "..." if len(rule.get("condition", "")) > 60 else rule.get("condition", "")
            item = QTableWidgetItem(cond)
            item.setBackground(QBrush(bg_color))
            self.rules_table.setItem(i, 3, item)
        
        self.rules_table.resizeRowsToContents()

    def run_analysis(self):
        code = self.code_editor.toPlainText()
        if not code.strip():
            QMessageBox.warning(self, "Предупреждение", "Введите код для анализа!")
            return

        if not self.current_rules:
            QMessageBox.warning(self, "Предупреждение", "Нет правил для анализа!")
            return

        try:
            self.statusBar().showMessage("Анализируем код...")
            self.analyze_btn.setEnabled(False)
            QApplication.processEvents()

            # Парсинг и сериализация AST
            tree = ast.parse(code)
            serialized = ast_to_serializable(tree)
            save_json("data", "ast.json", serialized)

            # Анализ контекста — ИСПРАВЛЕНО: нет метода analyze()
            self.analyzer = ASTJSONAnalyzer()
            ast_json = load_json("data", "ast.json")
            self.analyzer.collect_context(ast_json)
            
            # Группировка
            group_dct = self.analyzer.groupon()

            # Применение правил — ИСПРАВЛЕНО: метод экземпляра
            self.all_errors = []
            for rule in self.current_rules:
                rule_errors = self.analyzer.apply_rule(group_dct, rule)
                self.all_errors.extend(rule_errors)

            # Группировка по строкам
            self.errors_by_line = defaultdict(list)
            for error in self.all_errors:
                lineno = error.get("lineno", 0)
                if lineno > 0:
                    self.errors_by_line[lineno].append(error)

            self.display_all_lines()
            
            # Статистика
            total = len(self.all_errors)
            errors = len([e for e in self.all_errors if e.get('severity') == 'error'])
            warnings = len([e for e in self.all_errors if e.get('severity') == 'warning'])
            
            if total == 0:
                msg = "✅ Анализ завершён: ошибок не обнаружено"
            else:
                msg = f"✅ Анализ завершён: {total} нарушений"
                if errors:
                    msg += f" (ошибок: {errors})"
                if warnings:
                    msg += f" (предупреждений: {warnings})"
            
            self.statusBar().showMessage(msg, 5000)

        except SyntaxError as e:
            QMessageBox.critical(
                self, "Синтаксическая ошибка",
                f"Строка {e.lineno}, позиция {e.offset}:\n{e.msg}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка анализа", f"{type(e).__name__}: {str(e)}")
        finally:
            self.analyze_btn.setEnabled(True)

    def display_all_lines(self):
        """
        Отображает все строки кода
        """
        self.clear_results()
        self.code_lines = self.code_editor.toPlainText().splitlines()
        
        severity_colors = {
            "critical": (QColor(255, 150, 150), QColor(128, 0, 0)),
            "error": (QColor(255, 180, 180), QColor(139, 0, 0)),
            "high": (QColor(255, 200, 180), QColor(165, 42, 42)),
            "warning": (QColor(255, 255, 200), QColor(139, 69, 19)),
            "medium": (QColor(230, 255, 230), QColor(46, 139, 87)),
            "low": (QColor(220, 240, 255), QColor(25, 25, 112)),
            "info": (QColor(240, 240, 240), QColor(40, 40, 40)),
        }

        if not self.code_lines:
            return

        self.results_table.setRowCount(len(self.code_lines))
        
        for row, line_text in enumerate(self.code_lines):
            line_num = row + 1
            
            # № строки
            item = QTableWidgetItem(str(line_num))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            self.results_table.setItem(row, 0, item)
            
            # Код ошибки (пока пустой)
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_table.setItem(row, 1, item)
            
            # Строка кода
            item = QTableWidgetItem(line_text.rstrip() or " ")
            item.setFont(QFont("Consolas", 10))
            self.results_table.setItem(row, 2, item)
            
            # Описание ошибки
            self.results_table.setItem(row, 3, QTableWidgetItem(""))

            # Обработка ошибок для строки
            errors = self.errors_by_line.get(line_num, [])
            if errors:
                max_sev = max(
                    (e.get("severity", "info").lower() for e in errors),
                    key=lambda s: list(severity_colors.keys()).index(s) if s in severity_colors else -1
                )
                bg_color, fg_color = severity_colors.get(max_sev, (QColor(240, 240, 240), QColor(40, 40, 40)))
                
                # Коды ошибок
                codes = sorted(set(e.get("code", "N/A") for e in errors))
                code_item = self.results_table.item(row, 1)
                code_item.setText(", ".join(codes))
                code_item.setBackground(QBrush(bg_color))
                code_item.setForeground(QBrush(fg_color))
                
                # Описание
                msgs = [f"[{e.get('code', 'N/A')}] {e.get('severity', 'info').upper()}: {e.get('message', '')}" for e in errors]
                msg_item = QTableWidgetItem("\n".join(msgs))
                msg_item.setBackground(QBrush(bg_color))
                msg_item.setForeground(QBrush(fg_color))
                self.results_table.setItem(row, 3, msg_item)
                
                # Подсветка строки кода и номера
                code_item = self.results_table.item(row, 2)
                code_item.setBackground(QBrush(bg_color.lighter(110)))
                code_item.setForeground(QBrush(fg_color))
                
                num_item = self.results_table.item(row, 0)
                num_item.setBackground(QBrush(bg_color))
                num_item.setForeground(QBrush(fg_color))
            else:
                # Строки без ошибок — серый номер
                num_item = self.results_table.item(row, 0)
                num_item.setForeground(QBrush(QColor(120, 120, 120)))

        self.results_table.resizeRowsToContents()
        self.results_table.scrollToTop()

    def on_line_selected(self, item):
        """
        Обработчик клика по строке кода
        """
        if not item:
            return
        
        row = item.row()
        self.selected_line = row + 1
        self.hide_rule_editor()
        
        errors = self.errors_by_line.get(self.selected_line, [])
        if errors:
            # Фильтрация правил по кодам ошибок
            error_codes = {e.get("code", "").strip() for e in errors}
            matched = [r for r in self.current_rules if r.get("code", "").strip() in error_codes]
            self.display_rules_table(matched)
        else:
            # Показываем все правила
            self.display_rules_table()
            self.statusBar().showMessage(f"Строка {self.selected_line} не содержит ошибок")

    def on_rule_selected(self, item):
        """
        Обработчик клика по правилу — открывает редактор
        """
        if not item:
            return
        
        row = item.row()
        errors = self.errors_by_line.get(self.selected_line, [])
        
        if errors:
            # Правила для конкретной строки
            error_codes = {e.get("code", "").strip() for e in errors}
            matched = [r for r in self.current_rules if r.get("code", "").strip() in error_codes]
            if row < len(matched):
                rule = matched[row]
                self.selected_rule_index = self.current_rules.index(rule)
                self.show_rule_editor(rule, self.selected_rule_index)
        else:
            # Все правила
            if row < len(self.current_rules):
                rule = self.current_rules[row]
                self.selected_rule_index = row
                self.show_rule_editor(rule, self.selected_rule_index)

    def show_rule_editor(self, rule=None, rule_index=-1):
        """
        Открывает редактор правил как виджет справа
        """
        # Очистка контейнера
        layout = self.rule_editor_container.layout()
        if layout:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            QWidget().setLayout(layout)
        
        # Создание редактора
        editor = RuleEditorWidget(rule, rule_index, self.context_keys, self)
        editor.rule_saved.connect(self.on_rule_saved)
        editor.rule_cancelled.connect(self.hide_rule_editor)
        
        # Размещение в контейнере
        layout = QVBoxLayout(self.rule_editor_container)
        layout.addWidget(editor)
        self.rule_editor_container.show()

    def hide_rule_editor(self):
        """
        Скрывает редактор правил
        """
        self.rule_editor_container.hide()

    def on_rule_saved(self, rule, rule_index):
        """
        Обработчик сохранения правила
        """
        if rule_index >= 0 and rule_index < len(self.current_rules):
            # Редактирование существующего
            self.current_rules[rule_index] = rule
            msg = f"Правило '{rule['code']}' обновлено"
        else:
            # Добавление нового
            self.current_rules.append(rule)
            msg = f"Добавлено правило '{rule['code']}'"
        
        self.hide_rule_editor()
        self.display_rules_table()
        
        # Авто-анализ если есть код
        if self.code_editor.toPlainText().strip():
            self.run_analysis()
        
        self.statusBar().showMessage(msg, 3000)

    def save_rules_to_file(self):
        """
        Сохраняет правила в файл
        """
        if not self.current_rules:
            QMessageBox.warning(self, "Предупреждение", "Нет правил для сохранения!")
            return
        
        os.makedirs("data", exist_ok=True)
        filepath = os.path.join("data", "rules.json")
        
        # Резервная копия
        if os.path.exists(filepath):
            backup = filepath + ".bak"
            import shutil
            shutil.copy2(filepath, backup)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.current_rules, f, ensure_ascii=False, indent=2)
            
            msg = f"Сохранено {len(self.current_rules)} правил в data/rules.json"
            if os.path.exists(filepath + ".bak"):
                msg += "\nСоздана резервная копия: rules.json.bak"
            
            QMessageBox.information(self, "Успех", msg)
            self.statusBar().showMessage("Правила сохранены", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить правила:\n{str(e)}")

    def closeEvent(self, event):
        """
        Подтверждение закрытия
        """
        if self.code_editor.toPlainText().strip() and not self.current_file:
            reply = QMessageBox.question(
                self, "Подтверждение",
                "Есть несохранённый код. Закрыть приложение?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Цветовая схема
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor(245, 247, 249))
    palette.setColor(palette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(palette.ColorRole.AlternateBase, QColor(240, 245, 250))
    palette.setColor(palette.ColorRole.Text, QColor(40, 40, 40))
    app.setPalette(palette)
    
    window = CodeCheckerApp()
    window.show()
    sys.exit(app.exec())
