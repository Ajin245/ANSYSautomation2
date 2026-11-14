# -*- coding: utf-8 -*-
"""Определение типа конструкции по имени модели и именам Named Selections.

Источник смысла — ``v1/core/structure_detector.py:13-112``. Класс с глобальным
``Model`` не переносится: все функции чистые, данные приходят аргументами.
Регулярки v1 сохранены, добавлены шаблоны v2 (``Project_XXX`` и ``NN-DDD``).

Тип конструкции — это идентификатор, по которому выбирается
``structure_type_XXX.json``. Для имени ``NN-DDD`` (например ``18-245``)
структурного идентификатора в имени нет: это исполнение и диаметр, поэтому
``detect_structure_type`` возвращает ``(None, "execution")``, а сами числа
извлекает ``execution_parser``.
"""

import re

from Mechanical.pattern_matching import simple_pattern_match

# Порядок важен: сначала точные схемы v2 и v1, затем «свободное» NN-DDD.
STRUCTURE_PATTERNS = [
    ("project", re.compile(r'^Project_(\w+)')),
    ("standard", re.compile(r'^(\d+)-(\d{2})-F\d')),
    ("custom", re.compile(r'^(custom_\d+)-(\d{2})-F\d')),
    ("legacy", re.compile(r'^(\d{3})_')),
    ("coded", re.compile(r'^([A-Z]+)_')),
    ("execution", re.compile(r'^(\d+)-(\d+)$')),
]

# Шаблоны Named Selections для анализа (v1: :21-27).
NS_ANALYSIS_PATTERNS = [
    ("bolts", ["*bolt*", "*mbolt*", "*gaika*"]),
    ("pressure", ["*pressure*", "*nagruzka*"]),
    ("contact", ["*contact*", "*kontakt*", "*shov*"]),
    ("remote", ["*remote*", "*udal*"]),
    ("supports", ["*fixed*", "*opora*", "*support*"]),
]


def _names(ns_names):
    """Список имён из коллекции строк или объектов с атрибутом ``Name``."""
    names = []
    for item in ns_names or []:
        if hasattr(item, 'Name'):
            names.append(item.Name)
        else:
            names.append(item)
    return names


def detect_structure_type(model_name, ns_names=None):
    """Определяет тип конструкции по имени модели.

    Схемы по порядку: ``Project_XXX`` (v2) -> ``151-02-F2`` (v1 standard) ->
    ``custom_001-01-F1`` -> ``151_something`` -> ``ABC_001`` -> ``18-245``
    (v2 «исполнение-диаметр», типа конструкции нет). Если ни одна схема не
    подошла (например, дефолтное имя модели ``Model``), идентификатора
    конструкции нет: возвращается ``(None, "unknown")``, а не само имя модели —
    иначе дальше искался бы несуществующий ``structure_type_Model.json`` и
    настоящая причина (нераспознанный тип) терялась бы.

    Args:
        model_name (str): имя модели (``Model.Name`` в ANSYS).
        ns_names (list): имена Named Selections (в текущей логике не нужны,
            оставлены в сигнатуре как данные для будущих правил).

    Returns:
        tuple: ``(structure_type, category)``. ``structure_type`` — строка или
        ``None`` (для схемы ``NN-DDD``, пустого имени и нераспознанного имени).
    """
    if not model_name:
        return None, "unknown"

    for category, pattern in STRUCTURE_PATTERNS:
        match = pattern.match(model_name)
        if not match:
            continue
        if category == "execution":
            # NN-DDD: это исполнение и диаметр, а не идентификатор конструкции.
            return None, "execution"
        return match.group(1), category

    # Имя не по шаблону (в Mechanical это часто дефолтное ``Model``): типа
    # конструкции в нём нет. Возвращать само имя как тип нельзя — вызывающий
    # код принял бы его за идентификатор и искал structure_type_<имя>.json.
    return None, "unknown"


def detect_ns_patterns(ns_names):
    """Анализирует Named Selections: какие группы сущностей присутствуют.

    Args:
        ns_names (list): имена или объекты Named Selection.

    Returns:
        dict: флаги ``has_bolts``/``has_pressure``/``has_contact``/
        ``has_remote``/``has_supports``, а также ``total_ns_count`` и
        ``ns_names``.
    """
    names = _names(ns_names)
    analysis = {}
    for ns_type, patterns in NS_ANALYSIS_PATTERNS:
        analysis["has_" + ns_type] = any(
            simple_pattern_match(name, pattern)
            for name in names for pattern in patterns)
    analysis["total_ns_count"] = len(names)
    analysis["ns_names"] = names
    return analysis


def detect_load_configuration(ns_names):
    """Определяет, какие типы нагрузок адресуются Named Selections.

    Args:
        ns_names (list): имена или объекты Named Selection.

    Returns:
        dict: флаги ``has_force_load``, ``has_moment_load``,
        ``has_pressure_load``, ``has_temperature_load``, ``has_bearing_load``.
    """
    names = _names(ns_names)
    return {
        "has_force_load": any(simple_pattern_match(name, "*force*") for name in names),
        "has_moment_load": any(simple_pattern_match(name, "*moment*") for name in names),
        "has_pressure_load": any(simple_pattern_match(name, "*pressure*") for name in names),
        "has_temperature_load": any(simple_pattern_match(name, "*temperature*") for name in names),
        "has_bearing_load": any(simple_pattern_match(name, "*bearing*") for name in names),
    }


def detect_boundary_conditions(ns_names):
    """Определяет, какие граничные условия адресуются Named Selections.

    Args:
        ns_names (list): имена или объекты Named Selection.

    Returns:
        dict: флаги ``has_fixed_support``, ``has_displacement``,
        ``has_remote_displacement``, ``has_remote_force``,
        ``has_frictionless``, ``has_compression``.
    """
    names = _names(ns_names)
    return {
        "has_fixed_support": any(simple_pattern_match(name, "*fixed*") for name in names),
        "has_displacement": any(simple_pattern_match(name, "*disp*") for name in names),
        "has_remote_displacement": any(simple_pattern_match(name, "*remote_disp*") for name in names),
        "has_remote_force": any(simple_pattern_match(name, "*remote_f*") for name in names),
        "has_frictionless": any(simple_pattern_match(name, "*frictionless*") for name in names),
        "has_compression": any(simple_pattern_match(name, "*compression*") for name in names),
    }
