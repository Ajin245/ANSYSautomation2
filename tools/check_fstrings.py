# -*- coding: utf-8 -*-
"""Ноль f-строк в продуктовом коде src/ (PLAN-MERGE §6.1, RULES.md).

f-строки — синтаксис Python 3.6+, в IronPython 2.7 (ANSYS Workbench 21R1) они не работают,
поэтому их количество в ``src/`` обязано быть нулевым.

Запуск: ``python3 tools/check_fstrings.py``.
Вывод: ``FSTRINGS-OK 0`` при нуле; иначе строки ``FSTRING <путь>:<строка>`` и код возврата 1.

Поиск лексический (``tokenize``): f-строка в комментарии или в тексте обычной строки
нарушением не считается.
"""

from __future__ import print_function

import os
import re
import sys
import tokenize

SCAN_DIR = "src"
SKIP_DIRS = ("__pycache__", ".git")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

_STRING_PREFIX = re.compile(r"^([A-Za-z]*)(?='''|\"\"\"|'|\")")


def err(msg):
    sys.stderr.write(msg + "\n")


def iter_py_files():
    files = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, SCAN_DIR)):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(".py"):
                files.append(os.path.join(dirpath, name))
    return files


def find_fstrings(path):
    """Список (строка, начало текста) для каждого f-строкового литерала в файле."""
    handle = open(path, "rb")
    try:
        tokens = tokenize.tokenize(handle.readline)
        found = []
        for token in tokens:
            if token.type != tokenize.STRING:
                continue
            match = _STRING_PREFIX.match(token.string)
            if not match:
                continue
            if "f" in match.group(1).lower():
                found.append((token.start[0], token.string[:60]))
    finally:
        handle.close()
    return found


def main():
    paths = iter_py_files()
    if not paths:
        err("FSTRINGS-FAIL: в %s/ нет .py файлов" % SCAN_DIR)
        return 1

    total = 0
    for path in paths:
        try:
            found = find_fstrings(path)
        except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
            print("FSTRINGS-FAIL %s: не удалось разобрать: %s"
                  % (os.path.relpath(path, ROOT), exc))
            total += 1
            continue
        for line, text in found:
            print("FSTRING %s:%d %s" % (os.path.relpath(path, ROOT), line, text))
            total += 1

    if total:
        print("FSTRINGS-FAIL %d" % total)
        return 1

    print("FSTRINGS-OK 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
