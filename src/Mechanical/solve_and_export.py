# -*- coding: utf-8 -*-
"""Решение модели и выгрузка ``results.csv`` внутри Mechanical (шаг 4 конвейера).

Запускается журналом Workbench (``scripts/workbench_journal.py``) вторым
``SendCommand`` после настройки модели: ``SendCommand`` исполняет Python-код
внутри Mechanical, поэтому ``Analysis.Solve(True)`` и выгрузка выполняются там,
где доступны ``ExtAPI``/``Model``.

Порядок важен: CSV пишется только после решения — до него ``Solution`` пуст и
файл получил бы один заголовок. Поэтому решение и выгрузка живут в одном
скрипте: журнал не может вызвать их по отдельности, у ``DataReference`` из
журнала нет метода ``Solve`` (живая диагностика 21R1).

``Analysis.Solve(Boolean wait)`` подтверждён справочником ACT 2021 R1, но живым
прогоном ещё не проверялся — см. ``docs/run-modes.md``.

Исключения не глотаются: ``ansys_automation.py`` и ``export_results.py`` сами
печатают ``AUTOMATION-FAILED``, а журнал по пустому ``results.csv`` считает
прогон проваленным.
"""

import os
import sys

# Директория src в sys.path: импорты ``Mechanical.*`` работают независимо от
# рабочей директории Mechanical (как в ansys_automation.py).
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


def _first_analysis():
    """Первый объект ``Analysis`` модели; ``RuntimeError``, если их нет.

    ``Model`` — глобальная точка входа Mechanical; на раннем старте она может
    быть None, тогда модель берётся через ``ExtAPI.DataModel.Project.Model``.
    """
    model = globals().get("Model")
    if model is None:
        model = ExtAPI.DataModel.Project.Model
    analyses = model.Analyses
    if analyses is None or analyses.Count < 1:
        raise RuntimeError(u"в модели нет ни одного объекта Analysis")
    return analyses[0]


def _export_script_path():
    """Путь к ``export_results.py``: ``ANSYS_EXPORT_SCRIPT`` или рядом с этим файлом."""
    path = os.environ.get("ANSYS_EXPORT_SCRIPT", "")
    if path and path.strip():
        return path.strip()
    return os.path.join(current_dir, "export_results.py")


def run_solve_and_export():
    """Решить модель и выгрузить ``results.csv``; вернуть путь выгрузки."""
    analysis = _first_analysis()
    print(u"INFO: solve: Analysis.Solve(True)")
    analysis.Solve(True)
    print(u"INFO: solve: готово")

    export_script = _export_script_path()
    if not os.path.exists(export_script):
        message = u"AUTOMATION-FAILED: export script not found: {0}".format(export_script)
        print(message)
        raise RuntimeError(message)

    # export_results.py — самостоятельный скрипт (выполняется на import),
    # поэтому ему нужен явный namespace с __file__ (его читает get_project_root).
    namespace = {"__name__": "solve_and_export_script", "__file__": export_script}
    execfile(export_script, namespace)
    return export_script


run_solve_and_export()
