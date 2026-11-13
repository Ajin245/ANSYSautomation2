# -*- coding: utf-8 -*-
"""Преднатяг болтов по моменту затяжки.

Источник — рабочая формула v2 (``v2/src/Mechanical/analysis_manager.py:275``)::

    preload_n = torque / (0.37 * diameter / 1000)

Это **инженерное допущение**, а не выведенная зависимость: коэффициент 0.37
объединяет трение в резьбе и под головкой и не учитывает смазку, класс
прочности и шаг резьбы. Вопрос Q6 ``PLAN-MERGE.md`` оставлен открытым: если
владелец выберет другую формулу, меняется только ``TORQUE_FACTOR`` и тесты
``test_pretension.py``.

Модуль чистый: только ``re``, без ANSYS. Диаметр болта берётся из имени Named
Selection (``mbolt8``), момент — из ``structure_type_XXX.json -> torque_nm``.
"""

from __future__ import division

import re

# Коэффициент формулы v2. Инженерное допущение, см. docstring модуля (Q6).
TORQUE_FACTOR = 0.37

_BOLT_DIAMETER_MBOLT = re.compile(r'mbolt(\d+)', re.IGNORECASE)
_BOLT_DIAMETER_BOLT = re.compile(r'bolt(\d+)', re.IGNORECASE)


def torque_to_pretension(torque_nm, diameter_mm):
    """Переводит момент затяжки (Н·м) в усилие преднатяга (Н).

    Формула ``T / (0.37 * d / 1000)`` — инженерное допущение (Q6 плана).

    Args:
        torque_nm (float): момент затяжки, Н·м.
        diameter_mm (float): номинальный диаметр болта, мм.

    Returns:
        float: усилие преднатяга, Н; ``None``, если момент не задан.

    Raises:
        ValueError: диаметр не задан или не положителен.
    """
    if torque_nm is None:
        return None

    if diameter_mm is None or diameter_mm <= 0:
        raise ValueError(u"Диаметр болта должен быть положительным, получено: "
                         + str(diameter_mm))

    return torque_nm / (TORQUE_FACTOR * diameter_mm / 1000.0)


def select_torque(torque_data, diameter):
    """Момент затяжки для диаметра из словаря ``torque_nm``.

    Ключи в JSON — строки (``"8": 11.8``), но допускается и числовой ключ.
    Нулевой/отсутствующий момент считается «не задан» и даёт ``None``: в v2
    ``if torque:`` именно так и трактует значение.

    Args:
        torque_data (dict): словарь ``диаметр -> момент``.
        diameter (str|int): диаметр болта.

    Returns:
        float: момент, Н·м, или ``None``.
    """
    if not isinstance(torque_data, dict) or diameter is None:
        return None

    key = str(diameter).strip()
    for candidate in (key, diameter):
        if candidate in torque_data:
            value = torque_data[candidate]
            if value:
                return value
            return None
    return None


def _names(ns_names):
    """Имена из коллекции строк или объектов Named Selection."""
    names = []
    for item in ns_names or []:
        if hasattr(item, 'Name'):
            names.append(item.Name)
        else:
            names.append(item)
    return names


def select_bolt_diameter(ns_names, default=None):
    """Диаметр болта из имён Named Selections.

    Сначала ищется шаблон v2 ``mbolt<d>`` (``mbolt8``), затем — более общий
    ``bolt<d>`` (``gu_bolt12_f``). Возвращается первое совпадение.

    Args:
        ns_names (list): имена или объекты Named Selection.
        default: значение, если диаметр не найден.

    Returns:
        int: диаметр в мм или ``default``.
    """
    names = _names(ns_names)

    for pattern in (_BOLT_DIAMETER_MBOLT, _BOLT_DIAMETER_BOLT):
        for name in names:
            match = pattern.search(name or '')
            if match:
                return int(match.group(1))
    return default
