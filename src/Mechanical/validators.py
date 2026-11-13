# -*- coding: utf-8 -*-
"""Проверки конфигов и Named Selections без ANSYS.

Источник смысла — ``v1/utils/validators.py:26-161``. Код переписан под схемы v2:
``contact_settings`` — словарь правил плюс ``grouping`` (а не список
``contact_rules``), обязательные ключи ``structure_type_XXX.json`` проверяются
отдельной функцией. Глобального ``Model`` и ``load_database`` здесь нет —
эти проверки в v2 закрывает ``structure_type_XXX.json``.

Все функции поднимают ``ValueError`` (или ``IOError`` для отсутствующего файла)
с понятным сообщением: ``ValidationManager``/``ProjectContext`` перехватывают
исключение и останавливают прогон с этим текстом (FR-9).
"""

import os

REQUIRED_MESH_KEYS = ["meshCoef", "meshMethod", "elementOrder"]
REQUIRED_CONTACT_RULE_KEYS = ["type", "patterns"]
REQUIRED_STRUCTURE_KEYS = ["structure_info", "loads", "boundary_conditions"]


def validate_file_exists(file_path):
    """Проверяет, что файл существует.

    Returns:
        bool: True, если файл есть.

    Raises:
        IOError: файл не найден.
    """
    if not file_path or not os.path.exists(file_path):
        raise IOError(u"Файл не найден: " + str(file_path))
    return True


def validate_required_keys(config_dict, required_keys, context=""):
    """Проверяет наличие обязательных ключей в словаре конфига.

    Args:
        config_dict (dict): проверяемый конфиг.
        required_keys (list): обязательные ключи.
        context (str): пояснение для сообщения об ошибке.

    Returns:
        bool: True, если все ключи на месте.

    Raises:
        ValueError: перечисляет отсутствующие ключи.
    """
    if config_dict is None:
        raise ValueError(u"Пустой конфиг" + context)

    missing_keys = [key for key in required_keys if key not in config_dict]
    if missing_keys:
        raise ValueError(u"Отсутствуют обязательные ключи" + context + u": "
                         + u", ".join(missing_keys))
    return True


def _named_selection_name(item):
    """Имя Named Selection: строка как есть либо атрибут ``Name`` объекта."""
    if hasattr(item, 'Name'):
        return item.Name
    return item


def validate_named_selection(ns_name, all_named_selections):
    """Проверяет, что Named Selection с таким именем существует.

    Принимает как список имён (строк), так и коллекцию объектов с ``.Name``.

    Args:
        ns_name (str): искомое имя.
        all_named_selections: коллекция имён или объектов Named Selection.

    Returns:
        bool: True, если имя найдено; False для пустого имени.
    """
    if not ns_name:
        return False

    for item in all_named_selections or []:
        if _named_selection_name(item) == ns_name:
            return True
    return False


def validate_mesh_settings(mesh_settings):
    """Проверяет настройки сетки по схеме v2.

    Схема v2 — ``{"mesh_settings": {"<префикс тела>": {...}}}``. Допускается и
    «голый» словарь префиксов без внешней обёртки (так удобнее в тестах и
    вызовах из менеджера). У каждой записи обязательны ``meshCoef``,
    ``meshMethod`` и ``elementOrder``.

    Args:
        mesh_settings (dict): конфиг сетки.

    Returns:
        bool: True, если настройки валидны.

    Raises:
        ValueError: если настройки неполные.
    """
    if not isinstance(mesh_settings, dict):
        raise ValueError(u"Настройки сетки должны быть словарём")

    settings = mesh_settings
    nested = mesh_settings.get("mesh_settings")
    if isinstance(nested, dict):
        settings = nested

    if not settings:
        raise ValueError(u"Настройки сетки пусты")

    for key, value in settings.items():
        if not isinstance(value, dict):
            raise ValueError(u"Настройки сетки для '{0}' должны быть словарём".format(key))
        missing = [name for name in REQUIRED_MESH_KEYS if name not in value]
        if missing:
            raise ValueError(u"Неполные настройки сетки для '{0}', нет: {1}".format(
                key, u", ".join(missing)))
    return True


def validate_contact_settings(contact_settings):
    """Проверяет контакты по схеме v2: ``contact_settings`` + ``grouping``.

    Каждое правило обязано иметь ``type`` и непустой список ``patterns``.
    ``grouping`` — словарь «группа -> список имён правил»; имена обязаны
    ссылаться на существующие правила, иначе группировка контактов в ANSYS
    молча потеряет правило.

    Args:
        contact_settings (dict): содержимое ``contact_settings.json``.

    Returns:
        bool: True, если конфиг валиден.

    Raises:
        ValueError: если структура или правило неполные.
    """
    validate_required_keys(contact_settings, ["contact_settings", "grouping"],
                           u" (contact_settings)")

    rules = contact_settings["contact_settings"]
    if not isinstance(rules, dict) or not rules:
        raise ValueError(u"contact_settings должен быть непустым словарём правил")

    for rule_name, rule in rules.items():
        if not isinstance(rule, dict):
            raise ValueError(u"Правило контакта '{0}' должно быть словарём".format(rule_name))
        missing = [key for key in REQUIRED_CONTACT_RULE_KEYS if key not in rule]
        if missing:
            raise ValueError(u"Правило контакта '{0}' неполное, нет: {1}".format(
                rule_name, u", ".join(missing)))
        patterns = rule["patterns"]
        if not isinstance(patterns, list) or not patterns:
            raise ValueError(u"Правило контакта '{0}': patterns должен быть непустым списком".format(
                rule_name))

    grouping = contact_settings["grouping"]
    if not isinstance(grouping, dict) or not grouping:
        raise ValueError(u"grouping должен быть непустым словарём")

    for group_name, rule_names in grouping.items():
        if not isinstance(rule_names, list):
            raise ValueError(u"Группа '{0}' должна быть списком имён правил".format(group_name))
        unknown = [name for name in rule_names if name not in rules]
        if unknown:
            raise ValueError(u"Группа '{0}' ссылается на неизвестные правила: {1}".format(
                group_name, u", ".join(unknown)))
    return True


def validate_structure_type_config(config):
    """Проверяет обязательные ключи ``structure_type_XXX.json`` (v2).

    Требуются ``structure_info`` с непустым ``id``, непустой словарь ``loads``
    и словарь ``boundary_conditions``. Остальные поля (``torque_nm``,
    ``mesh_overrides``, ``spaceclaim_processing``) необязательны.

    Args:
        config (dict): содержимое конфига конструкции.

    Returns:
        bool: True, если конфиг валиден.

    Raises:
        ValueError: если структура конфига нарушена.
    """
    validate_required_keys(config, REQUIRED_STRUCTURE_KEYS, u" (structure_type)")

    structure_info = config["structure_info"]
    if not isinstance(structure_info, dict) or not structure_info.get("id"):
        raise ValueError(u"structure_info должен содержать непустой 'id'")

    if not isinstance(config["loads"], dict) or not config["loads"]:
        raise ValueError(u"loads должен быть непустым словарём исполнений")

    if not isinstance(config["boundary_conditions"], dict):
        raise ValueError(u"boundary_conditions должен быть словарём")
    return True
