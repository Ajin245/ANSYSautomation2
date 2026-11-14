# -*- coding: utf-8 -*-
"""Журнал Workbench для batch-прогона Mechanical (ANSYS 21R1, IronPython 2.7).

Запускается из ``scripts/run_ansys.bat`` командой::

    runwb2 -B -F "<project>.wbpj" -R "scripts\\workbench_journal.py"

Что делает журнал:

1. берёт систему Mechanical (``MECH_SYSTEM_NAME`` или первую с контейнером
   ``Model``) из **уже открытого** проекта — проект открывает сам Workbench
   аргументом ``-F``;
2. публикует путь к ``.wbpj`` в окружение как ``ANSYS_AUTOMATION_PROJECT``:
   ``ProjectContext`` берёт из него идентификатор проекта, потому что
   ``DataModel.Project.Name`` в Mechanical дефолтный (``'Project'``) и ID не
   содержит. Путь читается подтверждённым вызовом ``GetProjectFile()``;
3. первым ``SendCommand`` выполняет настройку модели
   (``src/Mechanical/ansys_automation.py``);
4. вторым ``SendCommand`` выполняет ``src/Mechanical/solve_and_export.py``:
   решение (``Analysis.Solve(True)``) и выгрузку ``results.csv`` после него.
   У ``DataReference`` из журнала нет метода ``Solve`` (живая диагностика
   21R1), поэтому решение выполняется внутри Mechanical;
5. ждёт ``results.csv`` со строками данных и сохраняет проект.

Канал доставки — ``model.SendCommand`` на контейнере ``Model``. Живой прогон
2026-11-14 показал: команда доходит и выполняется, **когда в проекте загружена
геометрия**; на пустом проекте вызов молча возвращает ``None``. Поэтому
отсутствие ``results.csv`` печатает ``AUTOMATION-FAILED`` с подсказкой про
геометрию, а не тихий успех.

Из журнала **не** используются ``GetProject()`` и ``system.Solve()``: живые
прогоны показали, что в journal-API 21R1 таких имён нет. Подтверждены и
используются ``GetAllSystems``, ``GetSystem(Name=)``,
``GetContainer(ComponentName="Model")``, ``GetProjectFile``, ``Save``.

Каждая ветка провала печатает ``AUTOMATION-FAILED: <шаг>: <причина>`` (его
ищет bat-обёртка) и завершается с кодом 1.
"""

import os
import sys
import time

MARKER = "AUTOMATION-FAILED"
OK_MARKER = "AUTOMATION-OK"

# Путь к .wbpj, из которого ProjectContext берёт идентификатор проекта.
PROJECT_ENV = "ANSYS_AUTOMATION_PROJECT"

# Сколько секунд ждать results.csv после команды решения.
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


def _project_file():
    """Путь к ``.wbpj`` открытого проекта (``GetProjectFile()``), иначе пустая строка.

    ``GetProjectFile`` — подтверждённое имя journal-API 21R1. Если его нет
    (старая сборка, ручной прогон), используется ``ANSYS_PROJECT_PATH`` из
    ``run_ansys.bat``, чтобы идентификатор проекта всё равно был известен.
    """
    try:
        path = GetProjectFile()
    except Exception:
        path = ""
    if path is None:
        path = ""
    path = "%s" % path
    if path.strip():
        return path.strip()
    return os.environ.get("ANSYS_PROJECT_PATH", "").strip()


def _publish_project_path():
    """Положить путь к ``.wbpj`` в окружение перед ``SendCommand``.

    ``SendCommand`` исполняется в том же процессе Mechanical, поэтому
    переменные окружения журнала ему видны — отдельный sidecar-файл не нужен.
    """
    path = _project_file()
    if path:
        os.environ[PROJECT_ENV] = path
        print("INFO: %s=%s" % (PROJECT_ENV, path))
    else:
        print("WARNING: project .wbpj path is unknown (GetProjectFile failed); "
              "ProjectContext will fall back to Project.Name")
    return path


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
    name = os.environ.get("MECH_SYSTEM_NAME", "").strip()
    if name:
        system = GetSystem(Name=name)
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


def _mechanical_model(system):
    """Контейнер Model, через который Mechanical принимает команды."""
    model = system.GetContainer(ComponentName="Model")
    if model is None:
        raise RuntimeError("system has no 'Model' container")
    return model


def _exec_command(script_path):
    """Текст для SendCommand: задать __file__ и выполнить наш скрипт.

    ``execfile`` сам не выставляет ``__file__``, а наши скрипты читают его на
    уровне модуля (``get_project_root``), поэтому присваиваем явно.
    """
    return '__file__ = r"%s"\nexecfile(r"%s")' % (script_path, script_path)


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


def _wait_for_rows(root, wait_seconds):
    """Дождаться непустого ``results.csv``; вернуть число строк данных.

    ``SendCommand`` возвращает ``None`` независимо от результата, поэтому
    единственное доказательство выполненной выгрузки — строки в CSV. Ноль
    строк за отведённое время — провал: пустой файл не должен выглядеть
    успехом.

    Raises:
        RuntimeError: если строк данных так и не появилось.
    """
    results_path = _results_path(root)
    deadline = time.time() + wait_seconds

    while True:
        rows = _count_data_rows(results_path)
        if rows > 0:
            return rows
        if time.time() >= deadline:
            raise RuntimeError(
                "no data rows in %s within %d s. SendCommand is silently "
                "ignored when the project has no loaded geometry - load the "
                "geometry (SYS.scdoc) and repeat." % (results_path, wait_seconds))
        time.sleep(1)


def _save_project():
    """Сохранить проект (``Save`` подтверждён живой диагностикой 21R1)."""
    Save(Overwrite=True)


def main():
    root = _root()
    setup_script = os.environ.get(
        "ANSYS_AUTOMATION_SCRIPT",
        os.path.join(root, "src", "Mechanical", "ansys_automation.py"),
    )
    solve_script = os.environ.get(
        "ANSYS_SOLVE_SCRIPT",
        os.path.join(root, "src", "Mechanical", "solve_and_export.py"),
    )
    structure_id = os.environ.get("STRUCTURE_ID", "")
    execution = os.environ.get("EXECUTION", "")

    print("INFO: root=%s" % root)
    print("INFO: setup script=%s" % setup_script)
    print("INFO: solve/export script=%s" % solve_script)
    print("INFO: structure_id=%s execution=%s" % (structure_id, execution))

    for path in (setup_script, solve_script):
        if not os.path.exists(path):
            print("%s: script not found: %s" % (MARKER, path))
            sys.exit(1)

    # Идентификатор проекта: путь к .wbpj уходит в окружение Mechanical.
    _publish_project_path()

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

    try:
        model = _mechanical_model(system)
    except Exception as exc:
        print("%s: model container: %s" % (MARKER, exc))
        sys.exit(1)

    # Порядок конвейера: настройка -> решение -> выгрузка CSV (FR-11).
    try:
        model.SendCommand(
            Language="Python",
            Command=_exec_command(setup_script),
        )
        print("INFO: setup command sent")
    except Exception as exc:
        print("%s: SendCommand (setup): %s" % (MARKER, exc))
        sys.exit(1)

    try:
        model.SendCommand(
            Language="Python",
            Command=_exec_command(solve_script),
        )
        print("INFO: solve/export command sent")
    except Exception as exc:
        print("%s: SendCommand (solve/export): %s" % (MARKER, exc))
        sys.exit(1)

    try:
        wait_seconds = int(os.environ.get("ANSYS_SOLVE_WAIT_SECONDS", ""))
    except Exception:
        wait_seconds = DEFAULT_WAIT_SECONDS
    if wait_seconds <= 0:
        wait_seconds = DEFAULT_WAIT_SECONDS

    try:
        rows = _wait_for_rows(root, wait_seconds)
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
