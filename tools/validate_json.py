# -*- coding: utf-8 -*-
"""Строгая валидация всех JSON-конфигов config/**/*.json (PLAN-MERGE §6.1, §6.2).

Проверка: каждый файл читается стандартным ``json.load`` без послаблений:
  * комментарии (``//``, ``/* */``) запрещены — это не JSON;
  * ``NaN`` / ``Infinity`` запрещены (их принимает нестрогий парсер, но не JSON);
  * файл обязан быть валидным UTF-8.

Запуск: ``python3 tools/validate_json.py``.
Вывод: ``JSON-OK <n>``, где n — число проверенных файлов; при ошибке —
``JSON-FAIL <путь>: <причина>`` и код возврата 1.
"""

from __future__ import print_function

import json
import os
import sys

CONFIG_DIR = "config"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def err(msg):
    sys.stderr.write(msg + "\n")


def _reject_constant(name):
    raise ValueError("нестандартное значение JSON: %s" % name)


def iter_json_files():
    base = os.path.join(ROOT, CONFIG_DIR)
    files = []
    if not os.path.isdir(base):
        return files
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            if name.endswith(".json"):
                files.append(os.path.join(dirpath, name))
    return files


def validate(path):
    """Возвращает текст ошибки или None, если файл — валидный строгий JSON."""
    handle = open(path, "rb")
    try:
        raw = handle.read()
    finally:
        handle.close()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return "не UTF-8: %s" % exc
    try:
        json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        return "%s" % exc
    return None


def main():
    base = os.path.join(ROOT, CONFIG_DIR)
    if not os.path.isdir(base):
        err("JSON-FAIL: нет каталога %s/" % CONFIG_DIR)
        return 1

    paths = iter_json_files()
    if not paths:
        err("JSON-FAIL: в %s/ нет .json файлов" % CONFIG_DIR)
        return 1

    failed = 0
    for path in paths:
        message = validate(path)
        if message is not None:
            print("JSON-FAIL %s: %s" % (os.path.relpath(path, ROOT), message))
            failed += 1

    if failed:
        print("JSON-FAIL %d из %d" % (failed, len(paths)))
        return 1

    print("JSON-OK %d" % len(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
