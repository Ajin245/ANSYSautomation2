# -*- coding: utf-8 -*-
"""Повторная выгрузка ``results.csv`` после решения (FR-11, шаг 4 конвейера).

Скрипт самостоятельный: строит ``ProjectContext`` и ``ResultManager`` так же,
как ``ansys_automation.py``, но модель не настраивает — только пишет CSV.
Вызывается:

* ACT-расширением ``src/act/ansys_automation/`` сразу после
  ``Analysis.Solve(True)`` — тогда ``Solution.Children`` уже содержат объекты
  результатов и ``PlotData`` доступны;
* вручную из Mechanical (``Automation`` -> ``Script``) после расчёта, когда
  прогон идёт без batch-обвязки.

Путь файла — тот же, что у ``ResultManager.export_results``:
``ANSYS_AUTOMATION_RESULTS``, затем ``project_settings.output.results_csv``,
затем ``<корень проекта>/results/results.csv``.

Ошибка выгрузки не глотается: печатается ``AUTOMATION-FAILED`` и исключение
пробрасывается, чтобы провал не выглядел успехом.
"""

import os
import sys

# Директория src в sys.path: импорты ``Mechanical.*`` работают независимо от
# рабочей директории Mechanical (как в ansys_automation.py).
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from Mechanical.project_context import ProjectContext
from Mechanical.result_manager import ResultManager

FAILURE_MARKER = u"AUTOMATION-FAILED: export"


def run_export():
    """Построить контекст, выгрузить CSV и вернуть путь файла.

    Raises:
        RuntimeError: если ``export_results`` не записал файл.
    """
    from Ansys.Core.Units import Quantity

    context = ProjectContext(ExtAPI, Quantity, {})
    context.log.info(u"Повторная выгрузка результатов после решения...")

    path = ResultManager(context).export_results()
    if not path:
        message = u"{0}: results.csv не записан".format(FAILURE_MARKER)
        context.log.error(message)
        print(message)
        raise RuntimeError(message)

    print(u"INFO: export_results.py: {0}".format(path))
    return path


run_export()
