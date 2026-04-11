# -*- coding: utf-8 -*-

import sys
import os
import traceback

# Добавляем путь к папке src (которая содержит Mechanical) в sys.path
# Это позволяет импортировать модули как from project_context import ProjectContext
script_dir = os.path.dirname(os.path.abspath(__file__))
print(script_dir)
# src_path должен быть родительской директорией для src/Mechanical
src_path = os.path.abspath(os.path.join(script_dir, "..")) 

if src_path not in sys.path:
    sys.path.insert(0, src_path) # Используем insert(0) для приоритета

# Теперь можно импортировать остальные модули
from project_context import ProjectContext
from contact_manager import ContactManager
from mesh_manager import MeshManager
from analysis_manager import AnalysisManager
from validation_manager import ValidationManager
from result_manager import ResultManager

def run_automation():
    """
    Главная точка входа для скрипта автоматизации ANSYS Mechanical.
    Оркестрирует работу всех менеджеров.
    """
    try:
        # Инициализация контекста
        print("Initialization")
        context = ProjectContext(ExtAPI)
        log = context.log
        log.info(u"Начало работы скрипта автоматизации...")

        # Инициализация менеджеров
        contact_mgr = ContactManager(context)
        print("TEST")
        mesh_mgr = MeshManager(context)
        analysis_mgr = AnalysisManager(context)
        validation_mgr = ValidationManager(context)
        result_mgr = ResultManager(context)

        # 1. Настройка контактов
        contact_mgr.setup_contacts()

        # 2. Настройка сетки
        mesh_mgr.apply_mesh_settings()

        # 3. Настройка граничных условий и нагрузок
        analysis_mgr.apply_boundary_conditions_and_loads()

        # 4. Валидация модели перед расчетом
        validation_mgr.validate_model_setup()

        # 5. Настройка результатов
        result_mgr.setup_plot_results()

        log.info(u"Автоматизация настройки модели успешно завершена.")
        log.info(u"Теперь можно запустить расчет.")

    except Exception as e:
        error_msg = u"Критическая ошибка автоматизации: {0} {1}".format(e, traceback.format_exc())
        print(error_msg)
        if 'context' in locals():
            context.log.error(error_msg)

if __name__ == "__main__":
    run_automation()