# -*- coding: utf-8 -*-
"""Гейт синтаксиса Python 2.7 для всего продуктового кода (PLAN-MERGE §6.1, §6.2).

Три режима, выбираются по доступности окружения:

1. ``python2`` в PATH          -> настоящая компиляция ``compile(source, path, "exec")``
                                  под Python 2.7. Отчёт: ``PY2-SYNTAX-OK <n>``.
2. нет ``python2``, есть ``lib2to3`` -> разбор исходника парсером ``lib2to3``
                                  (``pygram.python_grammar``). Отчёт: ``PY2-SYNTAX-OK <n>``.
3. ни того, ни другого        -> fallback: нормализация py2-синтаксиса и ``compile()``
                                  под python3. Отчёт: ``PY2-SYNTAX-FALLBACK <n>``.

Границы режимов (важно для чтения отчёта):
  * Грамматика ``lib2to3`` — гибридная: она принимает py2-конструкции (``print "x"``,
    ``raise E, "m"``, ``<>``) и одновременно часть py3 (аннотации, ``async``, ``yield from``,
    walrus), потому что lib2to3 исторически разбирает и py3-код. Поэтому режим 2 доказывает,
    что файл **разбирается**, но сам по себе не доказывает py2-совместимость.
  * Режим 3 — тем более не компиляция 2.7: он ловит грубые ошибки после нормализации.
  * Py3-only конструкции ловит отдельный гейт ``tools/py2lint.py`` (чёрный список токенов),
    f-строки — ``tools/check_fstrings.py``. Вместе они и образуют статический гейт §6.1.
  * Настоящая компиляция 2.7 возможна только в режиме 1 и на ручном прогоне в ANSYS.

Запуск: ``python3 tools/check_py2.py``. Код возврата 0 — нарушений нет, 1 — есть.
"""

from __future__ import print_function

import os
import re
import subprocess
import sys

# Каталоги, в которых лежит код, обязанный работать в IronPython 2.7
# (scripts/ — журнал Workbench, он исполняется тем же IronPython).
SCAN_DIRS = ("src", "tools", "scripts")
SKIP_DIRS = ("__pycache__", ".git")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def err(msg):
    """Пишем в stderr без keyword-аргументов print (грамматика py2 их не знает)."""
    sys.stderr.write(msg + "\n")


def iter_py_files():
    """Все .py в src/ и tools/, отсортированные по пути."""
    files = []
    for rel in SCAN_DIRS:
        base = os.path.join(ROOT, rel)
        if not os.path.isdir(base):
            err("WARN: нет каталога %s — пропускаю" % base)
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                if name.endswith(".py"):
                    files.append(os.path.join(dirpath, name))
    return files


def read_source(path):
    handle = open(path, "rb")
    try:
        data = handle.read()
    finally:
        handle.close()
    return data.decode("utf-8")


def find_python2():
    """Первый исполняемый python2*, найденный в PATH. Иначе None."""
    for name in ("python2", "python2.7", "python27"):
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            if not directory:
                continue
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


# ---------------------------------------------------------------- режим 1

PY2_COMPILE_SNIPPET = (
    "import sys\n"
    "path = sys.argv[1]\n"
    "handle = open(path, 'rb')\n"
    "source = handle.read()\n"
    "handle.close()\n"
    "compile(source, path, 'exec')\n"
)


def check_with_python2(binary, paths):
    """Настоящая компиляция под Python 2.7 через ``python2 -c compile``."""
    violations = []
    for path in paths:
        process = subprocess.Popen(
            [binary, "-c", PY2_COMPILE_SNIPPET, path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = process.communicate()[0]
        if process.returncode != 0:
            message = output.decode("utf-8", "replace").strip()
            violations.append((path, message.splitlines()[-1] if message else "compile failed"))
    return violations


# ---------------------------------------------------------------- режим 2

def check_with_lib2to3(paths):
    """Разбор грамматикой Python 2 из lib2to3 (доступна до Python 3.12 включительно)."""
    import warnings

    warnings.simplefilter("ignore")
    from lib2to3 import pygram, pytree
    from lib2to3.pgen2 import driver

    # pygram.python_grammar — именно грамматика Python 2 (print — оператор).
    parser = driver.Driver(pygram.python_grammar, convert=pytree.convert)

    violations = []
    for path in paths:
        source = read_source(path)
        if not source.endswith("\n"):
            source += "\n"
        try:
            parser.parse_string(source)
        except Exception as exc:  # ParseError, TokenError, IndentationError
            violations.append((path, "%s: %s" % (type(exc).__name__, exc)))
    return violations


# ---------------------------------------------------------------- режим 3

_U_PREFIX = re.compile(r"(?<![A-Za-z0-9_])[uU][rR](?=['\"])")
_U_ONLY = re.compile(r"(?<![A-Za-z0-9_])[uU](?=['\"])")
_PRINT_STMT = re.compile(r"^(\s*)print\s+(?!\(|\s*$)(.*)$")
_PRINT_CHEVRON = re.compile(r"^(\s*)print\s*>>\s*([^,]+),\s*(.*)$")
_EXCEPT_COMMA = re.compile(r"^(\s*except\s+[^:,]+?)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*:")
_RAISE_COMMA = re.compile(r"^(\s*)raise\s+([A-Za-z_][A-Za-z0-9_.]*)\s*,\s*(.+)$")
_OCTAL = re.compile(r"(?<![A-Za-z0-9_])0([0-7]{2,})(?![0-9])")


def normalize_py2(source):
    """Грубая замена py2-конструкций на py3-эквиваленты (только для fallback-режима)."""
    source = _U_PREFIX.sub("r", source)
    source = _U_ONLY.sub("", source)
    lines = source.split("\n")
    out = []
    for line in lines:
        match = _PRINT_CHEVRON.match(line)
        if match:
            line = "%sprint(%s, file=%s)" % (match.group(1), match.group(3), match.group(2).strip())
        else:
            match = _PRINT_STMT.match(line)
            if match and not line.lstrip().startswith("#"):
                line = "%sprint(%s)" % (match.group(1), match.group(2))
        match = _EXCEPT_COMMA.match(line)
        if match:
            line = "%s as %s:" % (match.group(1), match.group(2))
        match = _RAISE_COMMA.match(line)
        if match:
            line = "%sraise %s(%s)" % (match.group(1), match.group(2), match.group(3))
        line = line.replace("<>", "!=")
        line = _OCTAL.sub(r"0o\1", line)
        out.append(line)
    source = "\n".join(out)
    source = source.replace(".iteritems()", ".items()")
    source = source.replace(".iterkeys()", ".keys()")
    source = source.replace(".itervalues()", ".values()")
    return source


def check_fallback(paths):
    """Нормализация py2 -> py3 и compile(). Не заменяет компиляцию 2.7."""
    violations = []
    for path in paths:
        source = normalize_py2(read_source(path))
        try:
            compile(source, path, "exec")
        except SyntaxError as exc:
            violations.append((path, "SyntaxError: %s (line %s)" % (exc.msg, exc.lineno)))
    return violations


# ---------------------------------------------------------------- выход

def main():
    paths = iter_py_files()
    if not paths:
        err("PY2-SYNTAX-FAIL 0 (нет файлов для проверки)")
        return 1

    python2 = find_python2()
    if python2 is not None:
        mode = "python2"
        token = "PY2-SYNTAX-OK"
        violations = check_with_python2(python2, paths)
    else:
        try:
            violations = check_with_lib2to3(paths)
            mode = "lib2to3"
            token = "PY2-SYNTAX-OK"
        except ImportError:
            mode = "fallback"
            token = "PY2-SYNTAX-FALLBACK"
            violations = check_fallback(paths)

    for path, message in violations:
        print("PY2-SYNTAX-VIOLATION %s: %s" % (os.path.relpath(path, ROOT), message))

    print("PY2-SYNTAX-MODE %s" % mode)
    if violations:
        print("PY2-SYNTAX-FAIL %d (из %d файлов)" % (len(violations), len(paths)))
        return 1

    print("%s %d" % (token, len(paths)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
