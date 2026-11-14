# -*- coding: utf-8 -*-
"""ACT-модуль расширения ``ansys_automation`` (ANSYS 21R1, IronPython 2.7).

Это новый канал доставки нашего скрипта в Mechanical. Прежний канал — python-
команда на контейнере Model из журнала Workbench — на сборке 21.1.0.2020110819
не доставляет команду: вызов возвращает ``None`` и не производит эффекта
(четыре живых прогона 2026-11-14, см. ``docs/run-modes.md``).

Как это работает:

1. ``scripts/run_ansys.bat`` выставляет ``ANSYS_AUTOMATION_RUN=1`` и
   ``ANSYS_AUTOMATION_ROOT=<корень репозитория>``, затем запускает
   ``runwb2 -B -F <project> -R scripts/workbench_journal.py``.
2. Журнал вызывает ``system.Refresh()`` и ``system.Update()``. Update поднимает
   Mechanical для этой системы; при старте Mechanical загружает установленные
   ACT-расширения и вызывает ``on_init(context)`` (колбэк ``<oninit>``).
3. ``on_init`` выполняет полный конвейер: ``ansys_automation.py`` (настройка) ->
   ``Analysis.Solve(True)`` -> ``export_results.py`` (``results.csv``).
4. Журнал ждёт ``results.csv`` (успех) или маркера провала в ``logs/act-run.log``.

Почему расширение само решает модель: ACT не даёт документированной точки
«после решения» для журнала Workbench — без прежнего канала у журнала нет
собственного способа выполнить код внутри Mechanical. Поэтому шаги «настройка -> решение -> выгрузка»
выполняются внутри Mechanical одним заходом. ``Analysis.Solve(Boolean wait)``
подтверждён справочником ACT 2021 R1 (``act/v211``).

НЕ ПОДТВЕРЖДЕНО (см. ``docs/run-modes.md``): загрузка ACT-расширения именно в
batch-режиме ``runwb2 -B``; доступность ACT-лицензии на целевой машине; момент
вызова ``on_init`` относительно загрузки модели. Всё это проверяется только
живым прогоном.
"""

import os
import time
import traceback

# Маркеры: их ищет журнал (scripts/workbench_journal.py) и bat-обёртка.
RUN_FLAG = "ANSYS_AUTOMATION_RUN"
START_MARKER = "ACT-RUN-START"
OK_MARKER = "ACT-RUN-OK"
SKIP_MARKER = "ACT-RUN-SKIP"
FAIL_MARKER = "AUTOMATION-FAILED"

LOG_FILE = "act-run.log"


def _now():
    """Отметка времени без локали-зависимых форматов."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _root():
    """Корень репозитория из ANSYS_AUTOMATION_ROOT; пустая строка, если не задан."""
    root = os.environ.get("ANSYS_AUTOMATION_ROOT", "")
    if root is None:
        return ""
    return root.strip()


def _log_path(root):
    return os.path.join(root, "logs", LOG_FILE)


def _as_text(value):
    """Привести значение к unicode: traceback в py2 бывает и str, и unicode."""
    if isinstance(value, unicode):
        return value
    if isinstance(value, str):
        try:
            return value.decode("utf-8", "replace")
        except Exception:
            return value
    return unicode(value)


def _write(root, line):
    """Дописать строку в ``logs/act-run.log``.

    Ошибка логирования не поднимается: она не должна маскировать исходный сбой
    конвейера. Строка дублируется в stdout Mechanical — в batch он попадает в
    лог, который пишет run_ansys.bat.
    """
    text = _as_text(line)
    try:
        print("ACT: %s" % text.encode("utf-8"))
    except Exception:
        pass
    try:
        log_dir = os.path.join(root, "logs")
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)
        handle = open(_log_path(root), "a")
        try:
            handle.write((u"[%s] %s\n" % (_now(), text)).encode("utf-8"))
            handle.flush()
        finally:
            handle.close()
    except Exception:
        pass


def _execfile(path):
    """Выполнить скрипт как самостоятельный модуль.

    ``execfile`` не выставляет ``__file__``, а наши скрипты читают его на
    уровне модуля (``get_project_root``), поэтому передаём явный namespace.
    """
    namespace = {"__name__": "ansys_automation_act_script", "__file__": path}
    execfile(path, namespace)


def _first_analysis():
    """Первый объект ``Analysis`` в модели.

    ``Model`` — глобальная точка входа Mechanical; на раннем старте она может
    быть None, тогда берём модель через ``ExtAPI.DataModel.Project.Model``.
    """
    model = globals().get("Model")
    if model is None:
        model = ExtAPI.DataModel.Project.Model
    analyses = model.Analyses
    if len(analyses) < 1:
        raise RuntimeError(u"в модели нет ни одного объекта Analysis")
    return analyses[0]


def _results_path(root):
    """Путь CSV: ANSYS_AUTOMATION_RESULTS или ``<root>/results/results.csv``.

    Совпадает с ``ResultManager.resolve_export_path`` для штатного конфига
    (``project_settings.output.results_csv = "results.csv"``). Если в конфиге
    задан другой путь, прогон нужно запускать с ANSYS_AUTOMATION_RESULTS —
    разбор JSON в IronPython здесь намеренно не делается (см. комментарий в
    ``ansys_automation.py`` про отключение ``_json``).
    """
    env_path = os.environ.get("ANSYS_AUTOMATION_RESULTS", "")
    if env_path and env_path.strip():
        return env_path.strip()
    return os.path.join(root, "results", "results.csv")


def _count_data_rows(path):
    """Число строк данных в CSV без заголовка; 0, если файла нет."""
    if not os.path.exists(path):
        return 0
    count = -1
    handle = open(path, "r")
    try:
        for line in handle:
            if line.strip():
                count += 1
    finally:
        handle.close()
    if count < 0:
        return 0
    return count


def _run_pipeline(root):
    """Настройка -> решение -> выгрузка. Исключения пробрасываются в on_init."""
    setup_script = os.environ.get("ANSYS_AUTOMATION_SCRIPT", "").strip()
    if not setup_script:
        setup_script = os.path.join(root, "src", "Mechanical", "ansys_automation.py")
    export_script = os.environ.get("ANSYS_EXPORT_SCRIPT", "").strip()
    if not export_script:
        export_script = os.path.join(root, "src", "Mechanical", "export_results.py")

    for path in (setup_script, export_script):
        if not os.path.exists(path):
            raise RuntimeError(u"скрипт не найден: %s" % path)

    _write(root, u"setup: %s" % setup_script)
    _execfile(setup_script)
    _write(root, u"setup: готово")

    analysis = _first_analysis()
    _write(root, u"solve: Analysis.Solve(True)")
    analysis.Solve(True)
    _write(root, u"solve: готово")

    _write(root, u"export: %s" % export_script)
    _execfile(export_script)

    results_path = _results_path(root)
    rows = _count_data_rows(results_path)
    if rows <= 0:
        raise RuntimeError(u"в %s нет строк данных после решения" % results_path)
    _write(root, u"export: строк=%d путь=%s" % (rows, results_path))
    return results_path, rows


def on_init(context):
    """Колбэк ``<oninit>``: точка входа расширения при загрузке Mechanical.

    Без ``ANSYS_AUTOMATION_RUN=1`` расширение только отмечает пропуск в логе:
    установленное расширение не должно запускать конвейер при обычной работе
    инженера в Mechanical.
    """
    root = _root()
    flag = os.environ.get(RUN_FLAG, "")
    if flag is None:
        flag = ""
    if flag.strip() != "1":
        if root:
            _write(root, u"%s: %s != 1" % (SKIP_MARKER, RUN_FLAG))
        else:
            print("ACT: %s: %s != 1" % (SKIP_MARKER, RUN_FLAG))
        return

    if not root:
        print("ACT: %s: ANSYS_AUTOMATION_ROOT is empty" % FAIL_MARKER)
        return

    _write(root, START_MARKER)
    try:
        results_path, rows = _run_pipeline(root)
        _write(root, u"%s: rows=%d path=%s" % (OK_MARKER, rows, results_path))
    except Exception:
        _write(root, u"%s: act extension: %s"
               % (FAIL_MARKER, _as_text(traceback.format_exc())))
