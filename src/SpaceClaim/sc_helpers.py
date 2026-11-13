# -*- coding: utf-8 -*-
"""Чистые помощники SpaceClaim-скриптов: ID конструкции, конфиг, имена тел, criteria.

Модуль намеренно НЕ импортирует ``SpaceClaim.Api``: здесь только строки, пути и разбор
имён, поэтому функции проверяются под python3 без ANSYS. Скрипты
``prepare_geometry.py`` и ``create_named_selections.py`` подключают его через
``import sc_helpers`` (см. ``_add_helpers_to_path()`` в каждом скрипте).

Требования (PLAN-MERGE §4.6): FR-2 — SpaceClaim не содержит зашитого номера конструкции;
FR-12 — пути и ID определяются из окружения/документа, а не из литералов.

Синтаксис — Python 2.7 (IronPython 2.7 в ANSYS 21R1): без f-строк и аннотаций типов.
Runtime-сообщения — ASCII: консоль IronPython может не пережить печать кириллицы.
Русский текст — только в docstring и комментариях.
"""

import json
import os
import re

CONFIG_DIR_NAME = "config"
STRUCTURE_CONFIG_TEMPLATE = "structure_type_{0}.json"

# Имя проекта Workbench имеет вид Project_<номер> (та же схема, что в
# src/Mechanical/project_context.py: _get_project_id()).
PROJECT_NAME_PATTERN = re.compile(r"Project_([A-Za-z0-9]+)")
# Резерв: документ назван просто номером конструкции.
DIGITS_ONLY_PATTERN = re.compile(r"^(\d{4,6})$")

# criteria для Named Selection 'gu_fixed' (config/structure_type_*.json).
LOWEST_CRITERIA = ("bottom_faces", "lowest")
PERIMETER_CRITERIA = "perimeter"

# Q8, ветвь A: конструкция 10558 (единственная с criteria='perimeter') вне минимального
# прототипа. Подмена на 'bottom_faces' запрещена — она меняет смысл конфига.
PERIMETER_NOT_IMPLEMENTED_MESSAGE = (
    "criteria='perimeter' is not implemented: structure 10558 is out of the "
    "prototype scope (PLAN-MERGE Q8, branch A). Named Selection 'gu_fixed' was NOT created. "
    "Silent fallback to 'bottom_faces' is forbidden - it changes the meaning of the config. "
    "Needs a separate task for perimeter geometry."
)


class StructureIdError(Exception):
    """ID конструкции не определён: нет ни переменной скрипта, ни номера в имени документа."""


class PerimeterNotImplementedError(NotImplementedError):
    """criteria='perimeter' (конструкция 10558) вне прототипа — PLAN-MERGE Q8, ветвь A."""


def get_project_root():
    """Корень репозитория.

    Порядок: переменная окружения ``ANSYS_AUTOMATION_ROOT`` (та же, что в
    ``src/Mechanical/utils.py``), затем путь от расположения этого файла, затем cwd.
    """
    env_root = os.environ.get("ANSYS_AUTOMATION_ROOT")
    if env_root:
        return env_root
    try:
        module_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(module_dir, "..", ".."))
    except Exception:
        return os.getcwd()


def document_name(doc):
    """Имя документа SpaceClaim или None, если хост его не отдаёт.

    ``Document.Name`` в RESEARCH-ANSYS-API.md §4 не описан — вызов не подтверждён
    источником. Ошибка здесь не критична: без имени остаётся переменная STRUCTURE_ID.
    """
    if doc is None:
        return None
    try:
        return doc.Name
    except Exception:
        return None


def parse_structure_id(name):
    """Номер конструкции из имени документа или None.

    Понимает ``Project_<id>`` и имя, состоящее только из номера (4-6 цифр).
    """
    if not name:
        return None
    text = str(name).strip()
    match = PROJECT_NAME_PATTERN.search(text)
    if match:
        return match.group(1)
    match = DIGITS_ONLY_PATTERN.match(text)
    if match:
        return match.group(1)
    return None


def resolve_structure_id(override, name=None):
    """ID конструкции: явная переменная скрипта -> имя документа -> StructureIdError.

    Молчаливого дефолта нет (FR-2): если ID не найден, поднимается StructureIdError
    с инструкцией, что задать.
    """
    if override is not None:
        value = str(override).strip()
        if value:
            return value
    from_name = parse_structure_id(name)
    if from_name:
        return from_name
    raise StructureIdError(
        "Structure ID is not resolved: script variable STRUCTURE_ID is empty and the document "
        "name '{0}' contains neither 'Project_<id>' nor a bare structure number. "
        "Set STRUCTURE_ID at the top of the script to the Workbench project number.".format(name)
    )


def structure_config_path(structure_id, root=None):
    """Путь к ``config/structure_type_<id>.json``."""
    if root is None:
        root = get_project_root()
    return os.path.join(root, CONFIG_DIR_NAME, STRUCTURE_CONFIG_TEMPLATE.format(structure_id))


def load_structure_config(structure_id, root=None):
    """Читает ``config/structure_type_<id>.json``.

    Возвращает dict или None. None всегда сопровождается напечатанной причиной
    (какие пути искали) — молчаливого дефолта нет.
    """
    if structure_id is None or not str(structure_id).strip():
        raise StructureIdError("load_structure_config() called without a structure ID.")
    structure_id = str(structure_id).strip()

    candidates = [structure_config_path(structure_id, root)]
    # Резерв на случай запуска не из корня репозитория (поведение исходного скрипта).
    candidates.append(os.path.join(CONFIG_DIR_NAME,
                                   STRUCTURE_CONFIG_TEMPLATE.format(structure_id)))

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            handle = open(path, "r")
            try:
                return json.load(handle)
            finally:
                handle.close()
        except Exception as exc:
            print("ERROR: failed to read config {0}: {1}".format(path, exc))
            return None

    print("CRITICAL ERROR: config for structure '{0}' not found. Tried: {1}. "
          "Check the structure ID and the ANSYS_AUTOMATION_ROOT environment variable.".format(
              structure_id, "; ".join(candidates)))
    return None


def body_name(body):
    """Имя тела через ``GetName()``; для объекта без имени — пустая строка."""
    if body is None:
        return ""
    try:
        name = body.GetName()
    except Exception:
        return ""
    if not name:
        return ""
    return name


def body_prefix(name):
    """Первый токен имени тела: ``'truba1 25'`` -> ``'truba1'``. Пустое имя -> ``''``."""
    if not name:
        return ""
    parts = str(name).split()
    if not parts:
        return ""
    return parts[0]


def unique_body_prefixes(names):
    """Уникальные префиксы имён в стабильном (отсортированном) порядке."""
    prefixes = set()
    for name in names:
        prefix = body_prefix(name)
        if prefix:
            prefixes.add(prefix)
    return sorted(prefixes)


def select_bodies_by_prefix(bodies, prefix):
    """Тела, имя которых начинается с префикса (семантика исходного скрипта)."""
    if not prefix:
        return []
    return [body for body in bodies if body_name(body).startswith(prefix)]


def select_bodies_by_keywords(bodies, keywords):
    """Тела, в имени которых (без учёта регистра) есть любое из ключевых слов.

    Заменяет повторяющиеся условия вида ``"truba" in body.GetName().lower()``.
    """
    lowered = [keyword.lower() for keyword in keywords]
    selected = []
    for body in bodies:
        name = body_name(body).lower()
        for keyword in lowered:
            if keyword in name:
                selected.append(body)
                break
    return selected


def fixed_criteria_handler(criteria):
    """Какой обработчик вызывать для Named Selection 'gu_fixed'.

    Возвращает ``'lowest'`` для ``'bottom_faces'``/``'lowest'`` и ``'perimeter'`` для
    ``'perimeter'`` (сам обработчик поднимает PerimeterNotImplementedError — Q8, ветвь A).
    Неизвестное значение — ValueError: без gu_fixed расчёт неверен, тихо пропускать нельзя.
    """
    value = (criteria or "").strip().lower()
    if value in LOWEST_CRITERIA:
        return "lowest"
    if value == PERIMETER_CRITERIA:
        return "perimeter"
    raise ValueError(
        "Unknown criteria '{0}' for Named Selection 'gu_fixed'; supported: {1}".format(
            criteria, ", ".join(LOWEST_CRITERIA + (PERIMETER_CRITERIA,)))
    )
