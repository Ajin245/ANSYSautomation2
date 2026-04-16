# -*- coding: utf-8 -*-
import sys
import os
import clr
clr.AddReference("System.IO")
from System.IO import Path

# ПРИНУДИТЕЛЬНО ОТКЛЮЧАЕМ _json
sys.modules['_json'] = None

# ПУТЬ К РЕПОЗИТОРИЮ (динамически)
def get_project_root():
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

PROJECT_ROOT = get_project_root()
src_path = os.path.abspath(os.path.join(PROJECT_ROOT, "src"))

# Diagnostic logging
print(u"INFO: PROJECT_ROOT: {0}".format(PROJECT_ROOT))
print(u"INFO: src_path: {0}".format(src_path))

if not os.path.exists(src_path):
    print(u"ERROR: src_path NOT FOUND!")
    try:
        print(u"DEBUG: sys._getframe: {0}".format(sys._getframe().f_code.co_filename))
    except: pass
    print(u"DEBUG: __file__: {0}".format(__file__))
    print(u"DEBUG: cwd: {0}".format(os.getcwd()))

if src_path not in sys.path:
    sys.path.insert(0, src_path)

def run_automation():
    # Импортируем менеджеры здесь
    from Mechanical.project_context import ProjectContext
    from Mechanical.contact_manager import ContactManager
    from Mechanical.mesh_manager import MeshManager
    from Mechanical.analysis_manager import AnalysisManager
    from Mechanical.validation_manager import ValidationManager
    from Mechanical.result_manager import ResultManager

    try:
        # Импортируем Quantity из Ansys.Core.Units
        from Ansys.Core.Units import Quantity
        # Импортируем LoadDefineBy из того же модуля Enums
        from Ansys.Mechanical.DataModel.Enums import LoadDefineBy

    # Собираем необходимые Enum и классы из глобального контекста ANSYS
        ansys_enums = {
            "MethodType": MethodType,
            "MeshMethodAlgorithm": MeshMethodAlgorithm,
            "ElementOrder": ElementOrder,
            "LoadDefineBy": LoadDefineBy
        }
        context = ProjectContext(ExtAPI, Quantity, ansys_enums)
        context.log.info(u"Начало работы...")

        contact_mgr = ContactManager(context)
        mesh_mgr = MeshManager(context)
        analysis_mgr = AnalysisManager(context)
        validation_mgr = ValidationManager(context)
        result_mgr = ResultManager(context)
    
        contact_mgr.setup_contacts()
        mesh_mgr.apply_mesh_settings()
        analysis_mgr.apply_boundary_conditions_and_loads()
        validation_mgr.validate_model_setup()
        result_mgr.setup_plot_results()
    
        context.log.info(u"Автоматизация успешно завершена.")

    except Exception as e:
        # Убираем использование traceback, раз он недоступен
        print(u"Критическая ошибка (без traceback):{0}".format(str(e)))

run_automation()