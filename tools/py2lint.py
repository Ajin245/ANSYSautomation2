# -*- coding: utf-8 -*-
"""Запрет py3-only конструкций в продуктовом коде src/ (PLAN-MERGE §6.1, §6.2).

Ищет в исходниках:
  * f-строки                 (FSTRING)
  * ``async`` / ``await``     (ASYNC)
  * ``yield from``           (YIELD-FROM)
  * ``nonlocal``             (NONLOCAL)
  * аннотации типов          (TYPE-HINT): ``def f(x: int)`` и ``->``
  * импорты ``pathlib``, ``subprocess``, ``numpy``, ``pandas``, ``pip``  (PY3-IMPORT)

Py2-конструкции намеренно НЕ считаются нарушением: ``print "..."``, ``u"..."``,
``.iteritems()``, ``raise E, "..."``, ``<>``, ``long``, ``0777``, ``ur"..."`` — они
допустимы в целевой среде (IronPython 2.7 в ANSYS Workbench 21R1).

Разбор лексический (``tokenize``), поэтому слова внутри строк и комментариев не ловятся.
Проверяется только ``src/`` — это код, который исполняется в ANSYS. ``tools/`` и ``tests/``
работают под python3 и проверяются синтаксическим гейтом ``check_py2.py``.

Запуск: ``python3 tools/py2lint.py``. Код возврата 0 — ``PY2-LINT-OK``.
"""

from __future__ import print_function

import io
import os
import re
import sys
import tokenize

SCAN_DIR = "src"
SKIP_DIRS = ("__pycache__", ".git")
FORBIDDEN_MODULES = ("pathlib", "subprocess", "numpy", "pandas", "pip")

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


def string_is_fstring(token_text):
    match = _STRING_PREFIX.match(token_text)
    if not match:
        return False
    return "f" in match.group(1).lower()


def lint_source(path):
    """Список найденных нарушений в виде (код, строка, подробности)."""
    handle = open(path, "rb")
    try:
        tokens = list(tokenize.tokenize(handle.readline))
    finally:
        handle.close()

    violations = []
    significant = []
    for token in tokens:
        if token.type in (tokenize.INDENT, tokenize.DEDENT, tokenize.NL,
                          tokenize.COMMENT, tokenize.ENCODING, tokenize.ENDMARKER):
            continue
        significant.append(token)

    in_def_signature = False
    paren_depth = 0
    # Состояние разбора инструкции импорта:
    #   None        — вне импорта;
    #   "modules"   — после ``import``: каждое имя до NEWLINE — модуль;
    #   "from_mod"  — после ``from``: следующее имя — модуль;
    #   "from_rest" — модуль уже прочитан, ждём ``import``;
    #   "names"     — после ``from M import``: имена — не модули, не проверяем.
    import_state = None
    import_as = False

    for index, token in enumerate(significant):
        text = token.string

        if token.type == tokenize.NEWLINE:
            # Конец логической строки: состояние импорта сбрасывается.
            import_state = None
            import_as = False
            continue

        if token.type == tokenize.STRING:
            if string_is_fstring(text):
                violations.append(("FSTRING", token.start[0], text[:60]))
            continue

        if token.type == tokenize.OP:
            if text == "->":
                violations.append(("TYPE-HINT", token.start[0], "'->' в сигнатуре"))
            elif text == "(":
                paren_depth += 1
            elif text == ")":
                paren_depth = max(paren_depth - 1, 0)
            elif text == ":":
                if in_def_signature and paren_depth > 0:
                    violations.append(("TYPE-HINT", token.start[0], "аннотация в параметрах def"))
                elif paren_depth == 0:
                    in_def_signature = False
            continue

        if token.type != tokenize.NAME:
            continue

        if text in ("async", "await"):
            violations.append(("ASYNC", token.start[0], "'%s' — py3-only ключевое слово" % text))
        elif text == "nonlocal":
            violations.append(("NONLOCAL", token.start[0], "'nonlocal' — py3-only"))
        elif text == "yield":
            if _next_name(significant, index) == "from":
                violations.append(("YIELD-FROM", token.start[0], "'yield from' — py3-only"))
        elif text == "def":
            in_def_signature = True
            paren_depth = 0
        elif text == "import":
            if import_state == "from_rest":
                import_state = "names"
            else:
                import_state = "modules"
        elif text == "from":
            import_state = "from_mod"
        elif text == "as":
            import_as = True
        elif import_state in ("modules", "from_mod"):
            if import_as:
                # Имя после ``as`` — локальная привязка, не модуль.
                import_as = False
            else:
                # 'os.subprocess' -> проверяем корень 'os'.
                module = text.split(".")[0]
                if module in FORBIDDEN_MODULES:
                    violations.append(("PY3-IMPORT", token.start[0],
                                       "импорт '%s' запрещён (NFR-2)" % module))
            if import_state == "from_mod":
                import_state = "from_rest"
    return violations


def _next_name(tokens, index):
    for token in tokens[index + 1:]:
        if token.type == tokenize.NAME:
            return token.string
        if token.type == tokenize.OP and token.string in (",", ")", "]"):
            return None
    return None


def main():
    paths = iter_py_files()
    if not paths:
        err("PY2-LINT-FAIL: в %s/ нет .py файлов" % SCAN_DIR)
        return 1

    total = 0
    for path in paths:
        try:
            violations = lint_source(path)
        except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
            print("PY2-LINT-VIOLATION %s: не удалось разобрать: %s"
                  % (os.path.relpath(path, ROOT), exc))
            total += 1
            continue
        for code, line, details in violations:
            print("PY2-LINT-VIOLATION %s:%d %s %s"
                  % (os.path.relpath(path, ROOT), line, code, details))
            total += 1

    if total:
        print("PY2-LINT-FAIL %d (проверено %d файлов)" % (total, len(paths)))
        return 1

    print("PY2-LINT-OK %d" % len(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
