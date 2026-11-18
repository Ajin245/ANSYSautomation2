# -*- coding: utf-8 -*-
import os
import sys

def get_project_root():
    """
    Dynamically determines the project root directory.
    Priority:
    1. ANSYS_AUTOMATION_ROOT environment variable.
    2. Calculation based on current file location (searches for 'src' folder).
    3. Calculation based on current working directory.
    4. Fallback to default user path.
    """
    # 1. Приоритет переменной окружения
    env_root = os.environ.get("ANSYS_AUTOMATION_ROOT")
    if env_root: return env_root

    # 2. Попытка определить по расположению текущего файла
    try:
        cur_file = sys._getframe().f_code.co_filename
    except:
        cur_file = __file__

    if cur_file and not cur_file.startswith('<'):
        cur_file = os.path.abspath(cur_file)
        if "src" in cur_file:
            parts = cur_file.split(os.sep)
            for i in range(len(parts) - 1, -1, -1):
                if parts[i] == "src":
                    return os.sep.join(parts[:i])

    # 3. Попытка через рабочую директорию
    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, "src")):
        return cwd

    # 4. Резервный вариант (стандартный путь)
    return os.path.join(os.path.expanduser("~"), "source", "repos", "ANSYSautomation2")

def _category_name(obj):
    """Имя категории объекта Mechanical (``Body``, ``Part``, ...) или ``None``."""
    try:
        category = obj.DataModelObjectCategory
    except Exception:
        return None
    try:
        return unicode(category)
    except Exception:
        try:
            return str(category)
        except Exception:
            return None


def _is_body(obj):
    """True, если объект — тело, а не группа/сборка."""
    name = _category_name(obj)
    if name:
        return name.strip().lower().endswith(u"body")
    # Fallback: у тела есть объём и материал, у группы — нет.
    return hasattr(obj, "Volume") and hasattr(obj, "Material")


def iter_bodies(model):
    """Тела модели в обход дерева геометрии в глубину.

    ``Model.Geometry.Children`` отдаёт верхний уровень: там бывают **группы**
    (``SYS``, ``NIZ``, ``Opora_verh``), а тела лежат глубже. Ходить по одному
    уровню нельзя — получишь имена сборок вместо ``mbolt8``/``truba42``.

    Args:
        model: объект ``Model`` Mechanical.

    Returns:
        list: объекты тел (может быть пустым, если API недоступен).
    """
    bodies = []
    if model is None:
        return bodies

    try:
        stack = list(model.Geometry.Children or [])
    except Exception:
        return bodies

    while stack:
        obj = stack.pop()
        if _is_body(obj):
            bodies.append(obj)
            continue
        try:
            children = obj.Children
        except Exception:
            children = None
        if children:
            stack.extend(list(children))

    return bodies


def body_names(model):
    """Имена тел модели (для логов и диагностики)."""
    names = []
    for body in iter_bodies(model):
        name = getattr(body, "Name", None)
        names.append(name if name is not None else u"?")
    return names

# Объекты, которые создаёт конвейер. По этим префиксам они удаляются перед
# повторной настройкой: Mechanical хранит модель в ``SYS.mechdb``, поэтому без
# чистки каждый прогон добавлял ещё один набор ГУ/нагрузок (живой прогон 21R1).
AUTOMATIC_PREFIXES = (
    u"Fixed_",
    u"RemoteDisp_",
    u"Force_",
    u"Bolt_",
    u"Sizing_",
    u"Method_",
    u"Auto_",
)


# Имена без префикса, которые тоже создаёт конвейер (старые версии называли
# нагрузку просто ``Force``, результаты — по умолчанию).
AUTOMATIC_EXACT_NAMES = (u"Force", u"Total Deformation", u"Equivalent Stress")


import re as _re

_AUTOMATIC_PATTERNS = (
    _re.compile(u"^Force( \\d+)?$"),
    _re.compile(u"^FixedSupport( \\d+)?$"),
)


def is_automatic_object(obj):
    """True, если объект создан конвейером (по префиксу имени)."""
    name = getattr(obj, "Name", None)
    if not name:
        return False
    if name in AUTOMATIC_EXACT_NAMES:
        return True
    for pattern in _AUTOMATIC_PATTERNS:
        if pattern.match(name):
            return True
    for prefix in AUTOMATIC_PREFIXES:
        if name.startswith(prefix):
            return True
    return False


def purge_automatic_objects(container, logger=None):
    """Удалить объекты конвейера из контейнера (``Model.Mesh``, ``Analysis``).

    ``Delete()`` у объекта Mechanical подтверждён живым прогоном 21R1;
    ``Tree.Delete``/``RemoveObject`` в этой сборке отсутствуют.

    Args:
        container: контейнер с ``Children`` (Mesh, Analysis, Solution).
        logger: лог контекста (необязательно).

    Returns:
        int: сколько объектов удалено.
    """
    removed = 0
    if container is None:
        return removed

    try:
        children = list(container.Children)
    except Exception:
        return removed

    for obj in children:
        if not is_automatic_object(obj):
            continue
        try:
            obj.Delete()
            removed += 1
        except Exception as exc:
            if logger is not None:
                logger.warning(u"Не удалось удалить '{0}': {1}".format(
                    getattr(obj, "Name", u"?"), exc))
    return removed
