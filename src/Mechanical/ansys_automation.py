# -*- coding: utf-8 -*-
import sys
import clr
clr.AddReference("System.IO")
from System.IO import Path

# ПРИНУДИТЕЛЬНО ОТКЛЮЧАЕМ _json
sys.modules['_json'] = None

# ПУТЬ К РЕПОЗИТОРИЮ (через .NET)
PROJECT_ROOT = r"C:\Users\user\source\repos\ANSYSautomation2"
src_path = Path.Combine(PROJECT_ROOT, "src")
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
        # Собираем необходимые Enum и классы из глобального контекста ANSYS
        ansys_enums = {
            "MethodType": MethodType,
            "MeshMethodAlgorithm": MeshMethodAlgorithm,
            "ElementOrder": ElementOrder
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