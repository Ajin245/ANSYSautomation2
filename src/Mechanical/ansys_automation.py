# -*- coding: utf-8 -*-
import sys
import os
import clr
clr.AddReference("System.IO")
from System.IO import Path

# ПРИНУДИТЕЛЬНО ОТКЛЮЧАЕМ _json
sys.modules['_json'] = None

# Добавляем директорию src в sys.path для корректных импортов
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from Mechanical.utils import get_project_root

# ПУТЬ К РЕПОЗИТОРИЮ
PROJECT_ROOT = get_project_root()
src_path = os.path.abspath(os.path.join(PROJECT_ROOT, "src"))

# Diagnostic logging
print(u"INFO: PROJECT_ROOT: {0}".format(PROJECT_ROOT))
print(u"INFO: src_path: {0}".format(src_path))

if not os.path.exists(src_path):
    print(u"ERROR: src_path NOT FOUND!")
    print(u"DEBUG: __file__: {0}".format(__file__))
    print(u"DEBUG: cwd: {0}".format(os.getcwd()))

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

        ExtAPI.DataModel.Project.SaveProjectBeforeSolution = True
    
        context.log.info(u"Автоматизация успешно завершена.")

    except Exception as e:
        # Убираем использование traceback, раз он недоступен
        print(u"Критическая ошибка (без traceback):{0}".format(str(e)))

run_automation()