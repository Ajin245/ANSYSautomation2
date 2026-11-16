# -*- coding: utf-8 -*-
"""Разбор имени модели: идентификатор проекта, исполнение, диаметр, нагрузки.

Источник смысла — ``v1/core/execution_manager.py:30-60`` и
``v1/utils/validators.py:133-161``. ``load_database`` не переносится: в v2
нагрузки лежат в ``structure_type.loads[execution]``, поэтому ``select_loads``
работает с конфигом конструкции, а не с отдельной базой.

Поддерживаются обе схемы имён:

* v2: ``Project_8946`` (проект) и ``18-245`` (исполнение-диаметр, мм);
* v1: ``151-02-F2`` (тип-вариант-группа нагрузок) — как fallback.

Модуль чистый: только ``re``, без ANSYS.
"""

import re

PROJECT_PATTERN = re.compile(r'Project_(\w+)')
EXECUTION_DIAMETER_PATTERN = re.compile(r'^(\d+)-(\d+)$')
V1_EXECUTION_PATTERN = re.compile(r'^(\d+)-(\d{2})-([Ff]\d)$')


def parse_project_id(text):
    """Идентификатор проекта из имени ``Project_8946``.

    Args:
        text (str): имя проекта.

    Returns:
        str: идентификатор (``"8946"``) или ``None``, если шаблона нет.
    """
    if not text:
        return None
    match = PROJECT_PATTERN.search(text)
    if match:
        return match.group(1)
    return None


def parse_execution(model_name):
    """Номер исполнения из имени модели.

    ``18-245`` -> ``"18"`` (v2), ``151-02-F2`` -> ``"151"`` (v1 fallback).

    Args:
        model_name (str): имя модели.

    Returns:
        str: номер исполнения или ``None`` при несовпадении.
    """
    if not model_name:
        return None

    match = EXECUTION_DIAMETER_PATTERN.match(model_name)
    if match:
        return match.group(1)

    match = V1_EXECUTION_PATTERN.match(model_name)
    if match:
        return match.group(1)
    return None


def parse_diameter(model_name):
    """Диаметр (или номер варианта в схеме v1) из имени модели.

    ``18-245`` -> ``"245"`` (мм), ``151-02-F2`` -> ``"02"`` (v1: номер
    варианта, не диаметр — в схеме v1 диаметра в имени нет).

    Args:
        model_name (str): имя модели.

    Returns:
        str: значение второго числа или ``None`` при несовпадении.
    """
    if not model_name:
        return None

    match = EXECUTION_DIAMETER_PATTERN.match(model_name)
    if match:
        return match.group(2)

    match = V1_EXECUTION_PATTERN.match(model_name)
    if match:
        return match.group(2)
    return None


def parse_load_group(model_name):
    """Группа нагрузок ``F1``/``F2`` из имени схемы v1 (fallback).

    В v2 групп нагрузок нет — нагрузки адресуются только исполнением. Функция
    нужна, чтобы разбор v1-имён был полным и проверяемым.

    Args:
        model_name (str): имя модели.

    Returns:
        str: группа в верхнем регистре или ``None``.
    """
    if not model_name:
        return None

    match = V1_EXECUTION_PATTERN.match(model_name)
    if match:
        return match.group(3).upper()
    return None


def select_loads(structure_type, execution):
    """Нагрузки исполнения из ``structure_type.loads``.

    Ключи в конфигах v2 — строки с ведущим нулём (``"08"``), а из имени модели
    исполнение приходит как ``"8"``, поэтому проверяются оба варианта (и
    числовой ключ на случай словаря из Python).

    Args:
        structure_type (dict): конфиг конструкции (``structure_type_XXX.json``).
        execution (str|int): номер исполнения.

    Returns:
        dict: запись нагрузок (например ``{"nominal_forces": {...}}``) или
        ``None``, если исполнения в конфиге нет.
    """
    if not isinstance(structure_type, dict) or execution is None:
        return None

    loads = structure_type.get("loads")
    if not isinstance(loads, dict) or not loads:
        return None

    key = str(execution).strip()
    candidates = [key]
    if len(key) == 1:
        candidates.append("0" + key)
    try:
        candidates.append(int(key))
    except ValueError:
        pass

    for candidate in candidates:
        if candidate in loads:
            return loads[candidate]

    # Ключи другого типа, но то же число ("08" vs 8).
    for stored_key in loads.keys():
        if str(stored_key) == key:
            return loads[stored_key]
    return None


# Порядок шагов нагружения: НУЭ первым, НУЭ+ПЗ вторым, остальные — по алфавиту.
CASE_ORDER = ("НУЭ", "НУЭ+ПЗ")


def select_load_cases(structure_type, execution):
    """Шаги нагружения исполнения в порядке применения.

    Схема конфига (решение владельца 2026-11-14)::

        "loads": {"08": {"cases": {"НУЭ": {...}, "НУЭ+ПЗ": {...}}}}

    Старая схема ``{"nominal_forces": {...}}`` читается как один шаг ``НУЭ``,
    чтобы конфиги 10558 не ломались.

    Args:
        structure_type (dict): конфиг конструкции.
        execution (str|int): номер исполнения.

    Returns:
        list: список пар ``(имя_шага, dict со значениями)``; число шагов равно
        числу режимов в ``cases``.

    Raises:
        ValueError: исполнения нет в ``loads`` или в нём нет ни ``cases``,
            ни ``nominal_forces``. Решение владельца: без нагрузок расчёт не
            имеет смысла, поэтому это остановка, а не предупреждение.
    """
    entry = select_loads(structure_type, execution)
    if entry is None:
        raise ValueError(
            u"Нагрузки для исполнения '{0}' не найдены в конфиге конструкции "
            u"'{1}'".format(execution, (structure_type or {}).get(
                "structure_info", {}).get("id")))

    cases = entry.get("cases")
    if isinstance(cases, dict) and cases:
        ordered = [name for name in CASE_ORDER if name in cases]
        ordered += sorted(name for name in cases.keys() if name not in CASE_ORDER)
        return [(name, cases[name] or {}) for name in ordered]

    nominal = entry.get("nominal_forces")
    if isinstance(nominal, dict) and nominal:
        return [(u"НУЭ", nominal)]

    raise ValueError(
        u"У исполнения '{0}' нет ни 'cases', ни 'nominal_forces' в конфиге "
        u"конструкции".format(execution))

def _pairs(mapping):
    """Пары ключ-значение: ``.iteritems()`` в Python 2.7, ``.items()`` в python3."""
    if hasattr(mapping, "iteritems"):
        return mapping.iteritems()
    return mapping.items()


# Первый шаг болтового расчёта: только преднатяг, внешние нагрузки — нули.
TIGHTENING_STEP_NAME = u"Затяжка"


def _zero_values(cases):
    """Нули по всем компонентам, которые встречаются в режимах.

    Ключи берутся из самих режимов, чтобы у шага затяжки были ровно те же
    компоненты (``fx``/``fy``/``fz``/``mx``...), что и у остальных шагов:
    иначе компонент, отсутствующий в нулевом словаре, читался бы как ``None``.
    """
    values = {}
    for _name, case_values in cases:
        for key in (case_values or {}):
            values[key] = 0
    return values


def build_load_steps(cases, ramp_factor=None, tightening=False):
    """Шаги нагружения: затяжка болтов, разгон для сходимости, режимы.

    Владелец (2026-11-14): анализируемых шагов два — НУЭ и НУЭ+ПЗ; коэффициент
    0.5 вводится как промежуточный шаг, чтобы решатель вышел на нагрузку
    плавно. Промежуточный шаг в результаты не идёт.

    Владелец (2026-11-16): при наличии болтов первым идёт отдельный шаг
    затяжки с нулевыми нагрузками — на нём работает только преднатяг.
    Разгон идёт после него, поэтому шагов становится на один больше:
    ``Затяжка -> Разгон -> НУЭ -> НУЭ+ПЗ``; результаты снимаются с шагов
    режимов (3 и 4), а не с первых.

    Args:
        cases (list): пары ``(имя_шага, значения)`` из ``select_load_cases``.
        ramp_factor (float): доля первого режима для разгона (0.5). ``None`` или
            ``0`` — разгон не добавляется.
        tightening (bool): добавить первым шаг затяжки с нулевыми нагрузками
            (болтовый расчёт).

    Returns:
        list: пары ``(имя_шага, значения)``; первым идёт затяжка, если задана,
        затем разгон, затем режимы.
    """
    steps = []
    if tightening:
        steps.append((TIGHTENING_STEP_NAME, _zero_values(cases)))
    if ramp_factor and cases:
        name, values = cases[0]
        ramp = {}
        for key, value in _pairs(values):
            ramp[key] = value * ramp_factor
        steps.append((u"Разгон {0}x{1}".format(ramp_factor, name), ramp))
    steps.extend(cases)
    return steps
