# -*- coding: utf-8 -*-
"""Чтение JSON-конфигов с комментариями ``//`` и ``/* */``.

Модуль чистый: не импортирует сборки ANSYS и .NET-модули, поэтому одинаково
исполняется в IronPython 2.7 (ANSYS Workbench 21R1) и в CPython 3 на стенде QA.
Источник смысла — ``v1/utils/json_parser.py:11-111``; код переписан: вместо
.NET ``StreamReader`` используется ``io.open``.

Runtime-путь загрузки конфигов в v2 остаётся прежним
(``JavaScriptSerializer`` в ``project_context.py``). Этот модуль — тестируемый
fallback для конфигов, где допустимы комментарии (PLAN-MERGE §2.2, п. 7).
"""

import io
import json
import os


def _remove_json_comments(json_string):
    """Удаляет комментарии ``//`` и ``/* */``, не трогая содержимое строк JSON.

    Комментарии удаляются только вне строковых литералов: ``"a // b"`` и
    ``"x/*y*/z"`` остаются как есть. Экранирование внутри строки учитывается,
    поэтому ``"\\"//"`` не открывает комментарий.

    Args:
        json_string (str): исходный текст JSON.

    Returns:
        str: текст без комментариев.
    """
    if json_string is None:
        return None

    result = []
    in_string = False
    escaped = False
    i = 0
    length = len(json_string)

    while i < length:
        char = json_string[i]

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            i += 1
            continue

        if char == '/' and i + 1 < length:
            next_char = json_string[i + 1]

            # Строчный комментарий: // ... до конца строки.
            if next_char == '/':
                i += 2
                while i < length and json_string[i] != '\n':
                    i += 1
                continue

            # Блочный комментарий: /* ... */.
            if next_char == '*':
                i += 2
                while i + 1 < length and not (json_string[i] == '*' and json_string[i + 1] == '/'):
                    i += 1
                i += 2
                continue

        result.append(char)
        i += 1

    return ''.join(result)


def parse_json(json_string):
    """Разбирает строку JSON стандартным ``json.loads``.

    Args:
        json_string (str): текст JSON (комментарии уже должны быть удалены).

    Returns:
        object: разобранный объект Python или ``None``, если вход ``None``.

    Raises:
        ValueError: если текст не является валидным JSON.
    """
    if json_string is None:
        return None

    return json.loads(json_string)


def load_json_file(file_path):
    """Читает файл UTF-8, удаляет комментарии и разбирает JSON.

    BOM в начале файла отбрасывается: конфиги правятся в разных редакторах.

    Args:
        file_path (str): путь к JSON-файлу.

    Returns:
        object: разобранное содержимое файла.

    Raises:
        IOError: файл не найден или не читается.
        ValueError: содержимое не является валидным JSON.
    """
    if not os.path.exists(file_path):
        raise IOError(u"Файл конфигурации не найден: " + str(file_path))

    handle = io.open(file_path, 'r', encoding='utf-8')
    try:
        json_string = handle.read()
    finally:
        handle.close()

    if json_string and json_string[0] == u'\ufeff':
        json_string = json_string[1:]

    return parse_json(_remove_json_comments(json_string))
