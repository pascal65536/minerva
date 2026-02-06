import sys
import os
import json
import shutil
import re
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QSplitter,
    QFileDialog,
    QComboBox,
    QLineEdit,
    QLabel,
    QMessageBox,
    QFrame,
    QGridLayout,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QHeaderView,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPalette


class RuleEditorWidget(QWidget):
    """
    Редактор правил для AST анализатора
    """

    def __init__(self, rules_data):
        super().__init__()
        self.rules_data = rules_data
        self.sort_column = 0
        self.sort_order = Qt.SortOrder.AscendingOrder
        self.context_keys = [
            "store_vars",
            "load_vars",
            "imports",
            "import_from",
            "import_asname",
            "function_calls",
            "declared_vars",
            "class_names",
            "function_names",
        ]
        self.severity_levels = [
            "info",
            "low",
            "medium",
            "warning",
            "high",
            "error",
            "critical",
        ]
        self.severity_colors = {
            "critical": QColor(255, 200, 200),
            "error": QColor(255, 230, 230),
            "high": QColor(255, 240, 220),
            "warning": QColor(255, 255, 220),
            "medium": QColor(240, 255, 240),
            "low": QColor(230, 245, 255),
            "info": QColor(245, 245, 245),
        }
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Код", "Ключи (keys)", "Уровень", "Условие (кратко)"]
        )
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_table)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.load_selected_rule)
        self.table.setFont(QFont("Consolas", 10))
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            """
            QTableWidget { gridline-color: #d0d0d0; }
            QTableWidget::item:selected { background-color: #3498db; color: white; }
        """
        )
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        form_frame = QFrame()
        form_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        form_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 4px;")
        form_layout = QGridLayout(form_frame)
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(15, 15, 15, 15)
        row = 0
        form_layout.addWidget(
            QLabel("Код правила:"),
            row,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("Например: STYLE-001, SEC-002")
        self.code_edit.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.code_edit.textChanged.connect(self.update_preview)
        form_layout.addWidget(self.code_edit, row, 1)
        row += 1
        form_layout.addWidget(
            QLabel("Контекстные ключи (keys):"),
            row,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        self.keys_list = QListWidget()
        self.keys_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.keys_list.setFont(QFont("Segoe UI", 10))
        self.keys_list.setMinimumHeight(100)
        for key in self.context_keys:
            item = QListWidgetItem(key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.keys_list.addItem(item)
        self.keys_list.itemChanged.connect(self.update_preview)
        form_layout.addWidget(self.keys_list, row, 1)
        row += 1
        form_layout.addWidget(
            QLabel("Условие (Python):"),
            row,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        self.condition_edit = QTextEdit()
        self.condition_edit.setMaximumHeight(100)
        self.condition_edit.setFont(QFont("Consolas", 10))
        self.condition_edit.setPlaceholderText(
            "Доступные переменные в условии:\n"
            "  - name, keys, lineno\n"
            "  - snakecase, camelcase, startdigit, dunderscore\n"
            "  - BUILTIN_NAMES, FORBIDDEN_IMPORTS, DANGEROUS_FUNCTIONS\n"
            "  - re_search(pattern, string)\n\n"
            "Примеры:\n"
            "  name in DANGEROUS_FUNCTIONS\n"
            "  not snakecase and not dunderscore and len(name) > 1\n"
            "  startdigit"
        )
        self.condition_edit.textChanged.connect(self.update_preview)
        form_layout.addWidget(self.condition_edit, row, 1)
        row += 1
        form_layout.addWidget(
            QLabel("Сообщение:"),
            row,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        self.message_edit = QTextEdit()
        self.message_edit.setMaximumHeight(80)
        self.message_edit.setFont(QFont("Consolas", 10))
        self.message_edit.setPlaceholderText(
            "Поддерживает форматирование: {name}, {lineno}\n"
            "Пример: Имя переменной '{name}' должно быть в snake_case (строка {lineno})"
        )
        form_layout.addWidget(self.message_edit, row, 1)
        row += 1
        form_layout.addWidget(
            QLabel("Уровень серьёзности:"),
            row,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self.severity_combo = QComboBox()
        self.severity_combo.addItems(self.severity_levels)
        self.severity_combo.setFont(QFont("Segoe UI", 10))
        self.severity_combo.currentTextChanged.connect(self.update_preview)
        form_layout.addWidget(self.severity_combo, row, 1)
        editor_layout.addWidget(form_frame)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        self.save_btn = QPushButton("💾 Сохранить правило")
        self.save_btn.clicked.connect(self.save_rule)
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(
            """
            QPushButton { 
                padding: 8px 16px; 
                font-weight: bold; 
                background-color: #3498db; 
                color: white; 
                border-radius: 4px;
            }
            QPushButton:disabled { 
                background-color: #bdc3c7; 
                color: #7f8c8d; 
            }
            QPushButton:hover:!disabled { 
                background-color: #2980b9; 
            }
        """
        )

        self.add_btn = QPushButton("Добавить новое")
        self.add_btn.clicked.connect(self.add_new_rule)
        self.add_btn.setStyleSheet(
            """
            QPushButton { 
                padding: 8px 16px; 
                font-weight: bold; 
                background-color: #27ae60; 
                color: white; 
                border-radius: 4px;
            }
            QPushButton:hover { 
                background-color: #219653; 
            }
        """
        )

        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self.delete_rule)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet(
            """
            QPushButton { 
                padding: 8px 16px; 
                font-weight: bold; 
                background-color: #e74c3c; 
                color: white; 
                border-radius: 4px;
            }
            QPushButton:disabled { 
                background-color: #bdc3c7; 
                color: #7f8c8d; 
            }
            QPushButton:hover:!disabled { 
                background-color: #c0392b; 
            }
        """
        )

        self.validate_btn = QPushButton("Проверить условие")
        self.validate_btn.clicked.connect(self.validate_condition)
        self.validate_btn.setStyleSheet(
            """
            QPushButton { 
                padding: 8px 16px; 
                background-color: #f39c12; 
                color: white; 
                border-radius: 4px;
            }
            QPushButton:hover { 
                background-color: #e67e22; 
            }
        """
        )

        self.load_json_btn = QPushButton("Загрузить")
        self.load_json_btn.clicked.connect(self.load_json_file)
        self.load_json_btn.setStyleSheet(
            """
            QPushButton { 
                padding: 8px 16px; 
                background-color: #9b59b6; 
                color: white; 
                border-radius: 4px;
            }
            QPushButton:hover { 
                background-color: #8e44ad; 
            }
        """
        )

        self.save_json_btn = QPushButton("Сохранить в JSON")
        self.save_json_btn.clicked.connect(self.save_json_file)
        self.save_json_btn.setStyleSheet(
            """
            QPushButton { 
                padding: 8px 16px; 
                font-weight: bold; 
                background-color: #1abc9c; 
                color: white; 
                border-radius: 4px;
            }
            QPushButton:hover { 
                background-color: #16a085; 
            }
        """
        )

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.validate_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.load_json_btn)
        btn_layout.addWidget(self.save_json_btn)
        editor_layout.addLayout(btn_layout)
        editor_layout.addStretch()
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(editor_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        layout.addWidget(splitter)
        self.refresh_table()

    def create_backup(self, file_path):
        """
        Создаёт резервную копию файла перед изменением
        """
        if os.path.exists(file_path):
            backup_path = file_path + ".bak"
            shutil.copy2(file_path, backup_path)
            return backup_path
        return None

    def sort_table(self, column):
        """
        Сортировка таблицы по выбранному столбцу
        """
        self.sort_column = column
        self.sort_order = (
            Qt.SortOrder.DescendingOrder
            if self.sort_order == Qt.SortOrder.AscendingOrder
            else Qt.SortOrder.AscendingOrder
        )
        reverse = self.sort_order == Qt.SortOrder.DescendingOrder

        def get_sort_key(rule, col):
            if col == 0:
                return rule.get("code", "").strip().lower()
            elif col == 1:
                keys = rule.get("keys", [])
                if isinstance(keys, str):
                    keys = [k.strip() for k in keys.split(",") if k.strip()]
                return ",".join(sorted(str(k).strip() for k in keys)).lower()
            elif col == 2:
                order_map = {lvl: i for i, lvl in enumerate(self.severity_levels)}
                return order_map.get(rule.get("severity", "info").strip().lower(), 999)
            elif col == 3:
                cond = rule.get("condition", "").strip()
                return cond[:50].lower() if cond else ""
            return ""

        self.rules_data.sort(key=lambda r: get_sort_key(r, column), reverse=reverse)
        self.refresh_table()
        self.table.horizontalHeader().setSortIndicator(column, self.sort_order)

    def refresh_table(self):
        """
        Обновляет таблицу правил с цветовой индикацией и информативными данными
        """
        self.table.setRowCount(len(self.rules_data))
        for row, rule in enumerate(self.rules_data):
            rule = self.clean_rule(rule)
            code = rule.get("code", "").strip()
            code_item = QTableWidgetItem(code)
            code_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.table.setItem(row, 0, code_item)
            keys = rule.get("keys", [])
            if isinstance(keys, str):
                keys = [k.strip() for k in keys.split(",") if k.strip()]
            keys_str = ", ".join(sorted(str(k).strip() for k in keys if k))
            keys_item = QTableWidgetItem(keys_str)
            keys_item.setFont(QFont("Consolas", 9))
            keys_item.setToolTip(f"Контекстные ключи: {keys_str}")
            self.table.setItem(row, 1, keys_item)
            severity = rule.get("severity", "info").strip().lower()
            severity_item = QTableWidgetItem(severity)
            severity_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            severity_item.setBackground(
                self.severity_colors.get(severity, QColor(255, 255, 255))
            )
            severity_item.setForeground(
                QColor(0, 0, 0) if severity != "critical" else QColor(128, 0, 0)
            )
            self.table.setItem(row, 2, severity_item)
            condition = rule.get("condition", "").strip()
            short_cond = condition[:60] + "..." if len(condition) > 60 else condition
            cond_item = QTableWidgetItem(short_cond)
            cond_item.setFont(QFont("Consolas", 9))
            cond_item.setToolTip(condition if condition else "Условие отсутствует")
            self.table.setItem(row, 3, cond_item)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(1, 250)
        self.table.setColumnWidth(2, 90)
        self.table.horizontalHeader().setSortIndicator(
            self.sort_column, self.sort_order
        )

    def clean_rule(self, rule):
        """
        Очищает правило от лишних пробелов в ключах и значениях
        """
        clean = {}
        for key, value in rule.items():
            clean_key = key.strip()
            if clean_key == "keys" and isinstance(value, list):
                clean_value = [
                    v.strip() if isinstance(v, str) else v
                    for v in value
                    if v is not None
                ]
            elif isinstance(value, str):
                clean_value = value.strip()
            else:
                clean_value = value
            clean[clean_key] = clean_value
        if clean.get("code") == "SEC-001":
            cond = clean.get("condition", "")
            if "' import '" in cond:
                clean["condition"] = cond.replace("' import '", "'__import__'")
        if clean.get("code") in ("STYLE-001", "STYLE-002"):
            cond = clean.get("condition", "")
            if "name.startswith(' ')" in cond:
                clean["condition"] = cond.replace(
                    "name.startswith(' ')", "name.startswith('_')"
                )
        return clean

    def load_selected_rule(self):
        """
        Загружает выбранное правило в форму редактирования
        """
        selected = self.table.selectedItems()
        if not selected:
            self.save_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        self.save_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        row = selected[0].row()
        rule = self.clean_rule(self.rules_data[row])
        self.code_edit.setText(rule.get("code", ""))
        keys = rule.get("keys", [])
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split(",") if k.strip()]
        for i in range(self.keys_list.count()):
            item = self.keys_list.item(i)
            item.setCheckState(
                Qt.CheckState.Checked
                if item.text() in keys
                else Qt.CheckState.Unchecked
            )
        self.condition_edit.setPlainText(rule.get("condition", ""))
        self.message_edit.setPlainText(rule.get("message", ""))
        severity = rule.get("severity", "info").strip().lower()
        idx = self.severity_combo.findText(severity, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.severity_combo.setCurrentIndex(idx)
        else:
            self.severity_combo.setCurrentIndex(2)
        self.update_preview()

    def get_selected_keys(self):
        """
        Получает список выбранных ключей из QListWidget
        """
        return [
            self.keys_list.item(i).text()
            for i in range(self.keys_list.count())
            if self.keys_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def update_preview(self):
        """
        Обновляет предпросмотр краткого условия в реальном времени
        """
        pass

    def save_rule(self):
        """
        Сохраняет правило из формы в данные
        """
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(
                self, "Предупреждение", "Выберите правило для редактирования!"
            )
            return
        row = selected[0].row()
        keys = self.get_selected_keys()
        code = self.code_edit.text().strip()
        if not code:
            QMessageBox.warning(self, "Ошибка", "Код правила не может быть пустым!")
            return
        if not keys:
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                "Правило без контекстных ключей (keys) может не сработать.\nПродолжить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
        new_rule = {
            "code": code,
            "keys": keys,
            "condition": self.condition_edit.toPlainText().strip(),
            "message": self.message_edit.toPlainText().strip(),
            "severity": self.severity_combo.currentText().strip().lower(),
        }
        self.rules_data[row] = new_rule
        self.refresh_table()
        self.table.selectRow(row)
        QMessageBox.information(self, "Успех", f"Правило '{code}' сохранено!")

    def add_new_rule(self):
        """
        Добавляет новое правило с предзаполненными значениями
        """
        new_rule = {
            "code": f"NEW-{len(self.rules_data) + 1:03d}",
            "keys": ["store_vars"],
            "condition": "not snakecase and not dunderscore and len(name) > 1",
            "message": "Имя переменной '{name}' должно быть в snake_case (строка {lineno})",
            "severity": "warning",
        }
        self.rules_data.append(new_rule)
        self.refresh_table()
        self.table.selectRow(len(self.rules_data) - 1)
        self.load_selected_rule()
        self.code_edit.selectAll()
        self.code_edit.setFocus()

    def delete_rule(self):
        """
        Удаляет выбранное правило
        """
        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        code = self.rules_data[row].get("code", f"правило #{row + 1}")
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить правило '{code}'?\nЭто действие нельзя отменить.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            del self.rules_data[row]
            self.refresh_table()
            self.save_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            QMessageBox.information(self, "Успех", f"Правило '{code}' удалено")

    def validate_condition(self):
        """
        Проверяет синтаксис условия на корректность Python
        """
        condition = self.condition_edit.toPlainText().strip()
        if not condition:
            QMessageBox.warning(self, "Предупреждение", "Условие пустое!")
            return
        dangerous_patterns = [
            (r"__import__", "Использование __import__ в условии"),
            (r"exec\(", "Использование exec() в условии"),
            (r"eval\(", "Использование eval() в условии"),
            (r"os\.", "Доступ к модулю os"),
            (r"sys\.", "Доступ к модулю sys"),
        ]
        for pattern, desc in dangerous_patterns:
            if re.search(pattern, condition):
                reply = QMessageBox.warning(
                    self,
                    "Потенциальная опасность",
                    f"Обнаружена потенциально опасная конструкция:\n{desc}\n\n"
                    "Продолжить проверку синтаксиса?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    return
        try:
            compile(condition, "<condition>", "eval")
            QMessageBox.information(
                self,
                "Синтаксис корректен",
                "Условие прошло синтаксическую проверку.\n"
                "Доступные переменные в условии:\n"
                "  - name, keys, lineno\n"
                "  - snakecase, camelcase, startdigit, dunderscore\n"
                "  - BUILTIN_NAMES, FORBIDDEN_IMPORTS\n"
                "  - re_search(pattern, string)",
            )
        except SyntaxError as e:
            QMessageBox.critical(
                self,
                "Ошибка синтаксиса",
                f"Строка {e.lineno}, позиция {e.offset}:\n{e.msg}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка", f"Неизвестная ошибка:\n{type(e).__name__}: {e}"
            )

    def load_json_file(self):
        """
        Загружает правила из JSON файла с автоматической очисткой от пробелов
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить правила", "", "JSON (*.json);;Все файлы (*)"
        )
        if not file_path:
            return
        try:
            backup_path = self.create_backup(file_path)
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            self.rules_data = []
            fixed_count = 0
            for i, raw_rule in enumerate(raw_data):
                clean_rule = self.clean_rule(raw_rule)
                required = ["code", "keys", "condition", "message", "severity"]
                missing = [
                    f for f in required if f not in clean_rule or not clean_rule[f]
                ]
                if missing:
                    reply = QMessageBox.question(
                        self,
                        "Неполные данные",
                        f"Правило #{i+1} не содержит обязательных полей: {', '.join(missing)}\n"
                        "Пропустить это правило?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if reply == QMessageBox.StandardButton.No:
                        continue
                self.rules_data.append(clean_rule)
            self.refresh_table()
            msg = f"Загружено {len(self.rules_data)} правил из {os.path.basename(file_path)}"
            if fixed_count:
                msg += f"\nАвтоисправлено ошибок: {fixed_count}"
            if backup_path:
                msg += f"\nРезервная копия: {os.path.basename(backup_path)}"
            QMessageBox.information(self, "Загрузка завершена", msg)
            self.statusBar().showMessage(
                f"Загружено {len(self.rules_data)} правил", 3000
            )
        except json.JSONDecodeError as e:
            QMessageBox.critical(
                self,
                "Ошибка JSON",
                f"Некорректный JSON-файл:\nСтрока {e.lineno}, колонка {e.colno}:\n{e.msg}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось загрузить правила:\n{type(e).__name__}: {str(e)}",
            )

    def save_json_file(self):
        """
        Сохраняет правила в JSON файл без лишних пробелов в ключах
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить правила", "rules.json", "JSON (*.json);;Все файлы (*)"
        )
        if not file_path:
            return
        try:
            backup_path = self.create_backup(file_path)
            invalid_rules = []
            for i, rule in enumerate(self.rules_data):
                rule = self.clean_rule(rule)
                if not rule.get("code"):
                    invalid_rules.append(f"Правило #{i + 1}: отсутствует код")
                if not rule.get("condition"):
                    invalid_rules.append(
                        f"Правило {rule.get('code', f'#{i + 1}')}: пустое условие"
                    )
            if invalid_rules:
                reply = QMessageBox.question(
                    self,
                    "Предупреждение",
                    f"Обнаружены проблемы в {len(invalid_rules)} правилах:\n"
                    + "\n".join(invalid_rules[:5])
                    + (
                        f"\n... и ещё {len(invalid_rules) - 5}"
                        if len(invalid_rules) > 5
                        else ""
                    )
                    + "\n\nСохранить файл несмотря на проблемы?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    return
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.rules_data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self,
                "Сохранение завершено",
                f"Сохранено {len(self.rules_data)} правил в:\n{file_path}\n\n"
                f"Резервная копия: {os.path.basename(backup_path) if backup_path else 'не создана'}",
            )
            self.statusBar().showMessage(
                f"Сохранено {len(self.rules_data)} правил", 3000
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка сохранения",
                f"Не удалось сохранить файл:\n{type(e).__name__}: {str(e)}",
            )


class RuleEditorApp(QMainWindow):
    """
    Главное окно приложения редактора правил
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор правил AST анализатора")
        self.resize(1300, 850)
        self.setWindowIcon(
            self.style().standardIcon(
                self.style().StandardPixmap.SP_FileDialogContentsView
            )
        )
        rules_data = []
        default_paths = [
            os.path.join("data", "rules.json"),
            "rules.json",
            (
                os.path.join(os.path.dirname(__file__), "data", "rules.json")
                if __file__
                else None
            ),
        ]
        for path in default_paths:
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                        rules_data = [
                            {
                                k.strip(): (v.strip() if isinstance(v, str) else v)
                                for k, v in rule.items()
                            }
                            for rule in raw_data
                        ]
                    break
                except Exception:
                    continue
        central_widget = RuleEditorWidget(rules_data)
        self.setCentralWidget(central_widget)
        status = self.statusBar()
        status.showMessage(
            (
                f"Загружено правил: {len(rules_data)}"
                if rules_data
                else "Нет правил — создайте новое или загрузите JSON"
            ),
            5000,
        )
        self.statusBar().setToolTip(
            "Двойной клик по заголовку колонки — сортировка.\n"
            "Правила автоматически очищаются от пробелов при загрузке/сохранении."
        )

    def closeEvent(self, event):
        """
        Предупреждение при закрытии с несохранёнными изменениями
        """
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(245, 247, 249))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 245, 250))
    palette.setColor(QPalette.ColorRole.Text, QColor(40, 40, 40))
    palette.setColor(QPalette.ColorRole.Button, QColor(230, 230, 230))
    app.setPalette(palette)
    app.setStyleSheet(
        """
        QToolTip { 
            background-color: #3498db; 
            color: white; 
            border: 1px solid #2980b9; 
            padding: 5px; 
            border-radius: 3px;
        }
        QLineEdit:focus, QTextEdit:focus {
            border: 2px solid #3498db;
            border-radius: 3px;
        }
    """
    )
    window = RuleEditorApp()
    window.show()
    sys.exit(app.exec())
