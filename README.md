# 🦉 Minerva  
### Educational Static Analysis Tool for Python

**Minerva** is a lightweight, AST-based static code analyzer designed specifically for teaching and learning programming. Unlike general-purpose linters (e.g., Flake8, Pylint) or security scanners (e.g., Bandit), Minerva focuses on *pedagogical correctness*—helping students write not just working, but **didactically appropriate** code.

> _“Not every syntactically correct program is educationally sound.”_

---

## 🎯 Why Minerva?

Traditional linters enforce style or catch bugs—but they don’t understand classroom assignments. Minerva fills this gap by enabling instructors to define **custom educational rules** without writing plugins or modifying the core tool. It detects issues that matter in learning contexts, such as:

- ✍️ **Stylistic violations** (e.g., variable naming against assignment guidelines)  
- 🔤 **Homonymic symbol misuse** (e.g., `l`, `1`, `I` confusion)  
- 📝 **Assignment requirement violations** (e.g., “use a `for` loop, not `while`”)  
- 🗑️ **Repository pollution** (e.g., leftover debug prints, unused imports in submissions)  
- 🔄 **Procedural norm violations** (e.g., missing docstrings, incorrect function structure)

All rules are written in pure Python and loaded dynamically—no installation, no packaging.

---

## ⚡ Quick Start

Install Minerva:
```bash
pip install pyqt6
```
