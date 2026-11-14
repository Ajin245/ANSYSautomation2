# -*- coding: utf-8 -*-
"""Журнал Workbench для batch-прогона Mechanical (ANSYS 21R1, IronPython 2.7).

Запускается из ``scripts/run_ansys.bat`` командой::

    runwb2 -B -F "<project>.wbpj" -R "scripts\\workbench_journal.py"

Что делает журнал:

1. берёт систему Mechanical (``MECH_SYSTEM_NAME`` или первую с контейнером
   ``Model``) из **уже открытого** проекта — проект открывает сам Workbench
   аргументом ``-F``;
2. вызывает ``system.Refresh()`` и ``system.Update()``. Update поднимает
   Mechanical, а тот при загрузке поднимает установленное ACT-расширение
   ``ansys_automation`` (``src/act/ansys_automation/``), которое выполняет
   конвейер: настройка -> решение -> выгрузка ``results.csv``;
3. ждёт ``results.csv`` и маркер ``ACT-RUN-OK`` в ``logs/act-run.log``;
4. сохраняет проект.

Команда в Mechanical **не передаётся**: канал «python-команда на контейнере
Model» на сборке 21.1.0.2020110819 молча ничего не делает — вызов возвращает
None и не производит эффекта (четыре живых прогона 2026-11-14, факты —
в ``docs/run-modes.md``). Мёртвый путь удалён, доставка идёт через
ACT-расширение.

Имена Workbench API взяты из живой диагностики на целевой сборке:
``GetAllSystems``, ``GetSystem``, ``GetContainer``, ``Refresh``, ``Update``,
``Save`` есть; ``GetProject`` — нет.

Каждая ветка провала печатает ``AUTOMATION-FAILED: <шаг>: <причина>`` (его
ищет bat-обёртка) и завершается с кодом 1.
"""

import os
import sys
import time

MARKER = "AUTOMATION-FAILED"
OK_MARKER = "AUTOMATION-OK"

ACT_LOG = os.path.join("logs", "act-run.log")
ACT_START = "ACT-RUN-START"
ACT_OK = "ACT-RUN-OK"

# Сколько секунд ждать results.csv/маркер после Update(). Update() сам
# синхронный, поэтому запас нужен только на случай асинхронного хвоста.
DEFAULT_WAIT_SECONDS = 300


def _root():
    """Корень репозитория: переменная окружения или каталог над scripts/."""
    root = os.environ.get("ANSYS_AUTOMATION_ROOT")
    if root:
        return root
    try:
        here = os.path.abspath(__file__)
        return os.path.abspath(os.path.join(os.path.dirname(here), ".."))
    except Exception:
        return os.getcwd()


def _systems():
    """Все системы открытого проекта (``GetAllSystems``)."""
    systems = GetAllSystems()
    if systems is None:
        return []
    result = []
    for system in systems:
        result.append(system)
    return result


def _find_mechanical_system(systems):
    """Mechanical-система по MECH_SYSTEM_NAME, иначе первая с контейнером Model."""
    name = os.environ.get("MECH_SYSTEM_NAME", "")
    if name and name.strip():
        system = GetSystem(Name=name.strip())
        if system is None:
            raise RuntimeError("Workbench system '%s' not found" % name)
        return system

    for system in systems:
        try:
            model = system.GetContainer(ComponentName="Model")
        except Exception:
            model = None
        if model is not None:
            return system

    raise RuntimeError("no system with a Mechanical 'Model' container found")


def _results_path(root):
    """Путь CSV-выгрузки: ``ANSYS_AUTOMATION_RESULTS`` или ``results/results.csv``.

    Совпадает с ``ResultManager.resolve_export_path`` для штатного конфига
    (``project_settings.output.results_csv = "results.csv"``).
    """
    env_path = os.environ.get("ANSYS_AUTOMATION_RESULTS", "")
    if env_path and env_path.strip():
        return env_path.strip()
    return os.path.join(root, "results", "results.csv")


def _count_data_rows(path):
    """Число строк данных в CSV (без заголовка); 0, если файла нет."""
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


def _act_state(log_path, since):
    """Состояние последнего запуска расширения по ``logs/act-run.log``.

    Args:
        log_path (str): путь к логу расширения.
        since (float): время начала текущего прогона (``time.time()``).
            Лог, не обновлявшийся после этой отметки, считается отсутствующим:
            иначе маркер прошлого успешного прогона дал бы ложный успех.

    Returns:
        tuple: (state, detail), где state — ``"none"`` (лога нет),
        ``"running"`` (старт есть, результата нет), ``"ok"``, ``"failed"``.
    """
    if not os.path.exists(log_path):
        return "none", ""
    if os.path.getmtime(log_path) < since - 1:
        return "none", ""

    handle = open(log_path, "r")
    try:
        text = handle.read()
    finally:
        handle.close()

    start = text.rfind(ACT_START)
    if start < 0:
        return "none", ""
    tail = text[start:]
    if ACT_OK in tail:
        return "ok", tail
    if "AUTOMATION-FAILED" in tail:
        return "failed", tail
    return "running", tail


def _wait_for_results(root, wait_seconds, started):
    """Дождаться результата ACT-прогона.

    Args:
        root (str): корень репозитория.
        wait_seconds (int): сколько ждать после Update().
        started (float): время начала прогона; старые results.csv/лог не
            считаются доказательством успеха.

    Returns:
        int: число строк данных в results.csv (0 — успеха не было).

    Raises:
        RuntimeError: если расширение не отработало или упало — текст причины.
    """
    results_path = _results_path(root)
    log_path = os.path.join(root, ACT_LOG)
    deadline = started + wait_seconds

    while True:
        state, tail = _act_state(log_path, started)
        if state == "failed":
            raise RuntimeError("ACT extension failed (see %s): %s"
                               % (log_path, _last_failure_line(tail)))
        rows = _count_data_rows(results_path)
        if state == "ok" and rows > 0:
            if os.path.getmtime(results_path) >= started - 1:
                return rows
        if time.time() >= deadline:
            if state == "none":
                raise RuntimeError(
                    "ACT extension did not run: %s absent. Install it per "
                    "docs/act-extension.md (scripts\\install_act_extension.bat) "
                    "and check that Mechanical loads it in batch mode."
                    % log_path)
            if state == "running":
                raise RuntimeError("ACT extension did not finish within %d s "
                                   "(see %s)" % (wait_seconds, log_path))
            raise RuntimeError("no data rows in %s (act state: %s)"
                               % (results_path, state))
        time.sleep(1)


def _last_failure_line(tail):
    """Последняя строка с маркером провала — короткая причина для консоли."""
    lines = [line for line in tail.splitlines() if "AUTOMATION-FAILED" in line]
    if not lines:
        return ""
    return lines[-1].strip()


def _save_project():
    """Сохранить проект (``Save`` подтверждён живой диагностикой 21R1)."""
    Save(Overwrite=True)


def main():
    root = _root()
    print("INFO: root=%s" % root)
    print("INFO: structure_id=%s execution=%s"
          % (os.environ.get("STRUCTURE_ID", ""), os.environ.get("EXECUTION", "")))

    try:
        systems = _systems()
        print("INFO: systems=%d" % len(systems))
    except Exception as exc:
        print("%s: list systems: %s" % (MARKER, exc))
        sys.exit(1)

    if not systems:
        print("%s: no systems in opened project (pass -F <project.wbpj>)" % MARKER)
        sys.exit(1)

    try:
        system = _find_mechanical_system(systems)
        print("INFO: system=%s" % system.Name)
    except Exception as exc:
        print("%s: find Mechanical system: %s" % (MARKER, exc))
        sys.exit(1)

    # Отметка старта: лог расширения обновляется во время Update(), поэтому
    # «свежесть» лога и CSV проверяем относительно этого момента.
    started = time.time()

    try:
        system.Refresh()
        print("INFO: refreshed")
    except Exception as exc:
        print("%s: refresh: %s" % (MARKER, exc))
        sys.exit(1)

    # Update поднимает Mechanical; ACT-расширение выполняет конвейер.
    try:
        system.Update()
        print("INFO: update finished")
    except Exception as exc:
        print("%s: update: %s" % (MARKER, exc))
        sys.exit(1)

    try:
        wait_seconds = int(os.environ.get("ANSYS_ACT_WAIT_SECONDS", ""))
    except Exception:
        wait_seconds = DEFAULT_WAIT_SECONDS
    if wait_seconds <= 0:
        wait_seconds = DEFAULT_WAIT_SECONDS

    try:
        rows = _wait_for_results(root, wait_seconds, started)
    except Exception as exc:
        print("%s: solve: %s" % (MARKER, exc))
        sys.exit(1)

    print("INFO: results.csv rows=%d path=%s" % (rows, _results_path(root)))

    try:
        _save_project()
        print("INFO: project saved")
    except Exception as exc:
        print("%s: save project: %s" % (MARKER, exc))
        sys.exit(1)

    print(OK_MARKER)


if __name__ == "__main__":
    main()
