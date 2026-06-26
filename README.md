Чтобы использовать плагин `minerva-plugin` в проекте `minerva`, нужно установить его в виртуальное окружение проекта `minerva`. Вот пошаговая инструкция:

## 0. Клонировать репозиторий в ~/git/minerva-plugin

```bash
cd ~/git/
git clone git@github.com:pascal65536/minerva-plugin.git
```

## 1. Установка плагина в окружение Minerva ~/git/minerva

```bash
# Активируем виртуальное окружение проекта minerva
source ~/git/minerva/.venv/bin/activate

# Устанавливаем плагин в режиме разработки (editable)
cd ~/git/minerva-plugin
pip install -e .
```

## 2. Проверка установки

Убедитесь, что flake8 видит плагин:

```bash
flake8 --version
```

**Ожидаемый вывод** должен содержать строку с `minerva-plugin`:
```bash
7.3.0 (mccabe: 0.7.0, minerva-plugin: 1.0.0, pycodestyle: 2.14.0, pyflakes: 3.4.0) CPython 3.12.3 on Linux
```

## 3. Тестирование плагина

Создайте тестовый файл с "плохим" кодом:

```bash
flake8 ~/git/minerva/fixtures/hello.py
```

**Ожидаемый вывод** (ошибки с кодами `MN...`):

```bash
~/home/pascal65536~/git/minerva/fixtures/hello.py:3:1: MN001 variable name too short (min 2 chars)
```
