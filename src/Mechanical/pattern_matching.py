# -*- coding: utf-8 -*-
"""Сопоставление имён с шаблонами и извлечение номера из имени.

Чистые помощники вместо ``fnmatch`` (его нет в целевом IronPython-окружении).
Источник смысла — ``v1/utils/pattern_matching.py:8-58``; код переписан без
глобального состояния и без ANSYS-зависимостей.
"""

import re

# Завершающее число имени: "mbolt12" -> "mbolt" + 12.0, "opora_15" -> "opora_" + 15.0.
_TRAILING_NUMBER = re.compile(r"^(.*?)([+-]?\d*\.\d+|\d+\.?\d*)$")


def simple_pattern_match(name, pattern):
    """Проверяет имя по шаблону, где ``*`` означает любую подстроку.

    Реализация — регулярное выражение из экранированных частей шаблона
    (``*`` -> ``.*``), а не ``fnmatch``: его нет в целевом IronPython.
    В отличие от v1 (там корректно работал только один ``*``), шаблоны вида
    ``*bolt*`` и ``gu_*_f`` сопоставляются полностью, иначе анализ Named
    Selections всегда давал бы ``False``.

    Args:
        name (str): проверяемое имя.
        pattern (str): шаблон с ``*`` или без него.

    Returns:
        bool: True, если имя соответствует шаблону целиком.
    """
    if not pattern or not name:
        return False

    if '*' not in pattern:
        return name == pattern

    regex = '^' + '.*'.join(re.escape(part) for part in pattern.split('*')) + '$'
    return re.match(regex, name) is not None


def match_any_pattern(name, patterns):
    """True, если имя подходит хотя бы под один шаблон из списка."""
    if not patterns:
        return False
    return any(simple_pattern_match(name, pattern) for pattern in patterns)


def find_matching_names(names, pattern):
    """Возвращает список имён, подходящих под шаблон (порядок сохраняется)."""
    if not names:
        return []
    return [name for name in names if simple_pattern_match(name, pattern)]


def extract_number_from_name(entity_name):
    """Делит имя на базу и завершающее число.

    Примеры: ``"mbolt12"`` -> ``("mbolt", 12.0)``, ``"opora_15"`` ->
    ``("opora_", 15.0)``, ``"truba245"`` -> ``("truba", 245.0)``.

    Args:
        entity_name (str): имя сущности.

    Returns:
        tuple: ``(base_name, number)`` или ``None``, если числа в конце нет.
    """
    if not entity_name:
        return None

    match = _TRAILING_NUMBER.match(entity_name)
    if match:
        return match.group(1), float(match.group(2))
    return None
