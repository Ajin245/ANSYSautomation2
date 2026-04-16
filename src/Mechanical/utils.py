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
