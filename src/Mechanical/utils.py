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
