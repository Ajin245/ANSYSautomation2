# -*- coding: utf-8 -*-
"""Журнал Workbench для batch-прогона Mechanical (ANSYS 21R1, IronPython 2.7).

Запускается из ``scripts/run_ansys.bat`` командой::

    runwb2 -B -F "<project>.wbpj" -R "scripts\\workbench_journal.py"

Проект открывает сам Workbench аргументом ``-F``. Если переменная окружения
``ANSYS_PROJECT_PATH`` задана и открытый проект ей не соответствует, журнал
пробует открыть файл явно. Mechanical-система выбирается по ``MECH_SYSTEM_NAME``,
иначе берётся первая система, у которой есть контейнер ``Model``.

Внутри Mechanical выполняется ``execfile`` нашего скрипта
``src/Mechanical/ansys_automation.py`` через ``SendCommand``. После настройки
модели журнал дожидается решения ``Solve(Wait=True)`` и сохраняет проект.

Каждая ветка обёрнута в try/except: при ошибке печатается маркер
``AUTOMATION-FAILED`` (его ищет bat-обёртка) и процесс завершается с кодом 1.

ВАЖНО: точные имена объектов Workbench API (``GetProject``, ``GetSystem``,
``GetContainer``, ``Solve``, ``project.Save``) взяты из документации/журналов
21R1, но на живом Workbench этот файл ещё не прогонялся.
"""

import os
import sys


MARKER = "AUTOMATION-FAILED"
OK_MARKER = "AUTOMATION-OK"


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


def _ensure_project():
    """Вернуть открытый проект Workbench, при необходимости открыть файл.

    Проект обычно уже открыт аргументом ``-F``. Повторно открываем только если
    проекта нет вовсе: ``project.Name`` в Workbench — отображаемое имя, а не путь,
    и сравнение с именем файла давало бы ложные переоткрытия.
    """
    project_path = os.environ.get("ANSYS_PROJECT_PATH", "").strip()

    try:
        project = GetProject()
    except Exception:
        project = None

    if project is None:
        if not project_path:
            raise RuntimeError("no open project and ANSYS_PROJECT_PATH is empty")
        print("INFO: opening project %s" % project_path)
        Open(FilePath=project_path)
        project = GetProject()

    try:
        print("INFO: project=%s" % project.Name)
    except Exception:
        pass
    return project


def _project_systems(project):
    """Список систем проекта: сначала project.Systems, затем project.Children."""
    for attribute in ("Systems", "Children"):
        try:
            value = getattr(project, attribute)
        except Exception:
            continue
        if value is None:
            continue
        items = []
        try:
            for item in value:
                items.append(item)
        except Exception:
            continue
        if items:
            return items
    return []


def _find_mechanical_system(project):
    """Mechanical-система по MECH_SYSTEM_NAME, иначе первая с контейнером Model."""
    name = os.environ.get("MECH_SYSTEM_NAME", "").strip()
    if name:
        system = GetSystem(Name=name)
        if system is None:
            raise RuntimeError("Workbench system '%s' not found" % name)
        return system

    for system in _project_systems(project):
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


def _automation_command(script_path):
    """Текст для SendCommand: задать __file__ и выполнить наш скрипт.

    ``execfile`` сам не выставляет ``__file__``, а ``ansys_automation.py``
    использует его на уровне модуля, поэтому присваиваем явно.
    """
    return '__file__ = r"%s"\nexecfile(r"%s")' % (script_path, script_path)


def _save_project(project):
    """Сохранить проект: сначала project.Save(), затем глобальный Save()."""
    try:
        project.Save()
        return
    except Exception:
        pass
    Save(Overwrite=True)


def main():
    root = _root()
    script_path = os.environ.get(
        "ANSYS_AUTOMATION_SCRIPT",
        os.path.join(root, "src", "Mechanical", "ansys_automation.py"),
    )
    structure_id = os.environ.get("STRUCTURE_ID", "")
    execution = os.environ.get("EXECUTION", "")

    print("INFO: root=%s" % root)
    print("INFO: automation script=%s" % script_path)
    print("INFO: structure_id=%s execution=%s" % (structure_id, execution))

    if not os.path.exists(script_path):
        print("AUTOMATION-FAILED: automation script not found: %s" % script_path)
        sys.exit(1)

    try:
        project = _ensure_project()
    except Exception as exc:
        print("AUTOMATION-FAILED: open project: %s" % exc)
        sys.exit(1)

    try:
        system = _find_mechanical_system(project)
        print("INFO: system=%s" % system.Name)
    except Exception as exc:
        print("AUTOMATION-FAILED: find Mechanical system: %s" % exc)
        sys.exit(1)

    try:
        model = _mechanical_model(system)
        model.SendCommand(
            Language="Python",
            Command=_automation_command(script_path),
        )
        print("INFO: Mechanical command sent")
    except Exception as exc:
        print("AUTOMATION-FAILED: SendCommand: %s" % exc)
        sys.exit(1)

    try:
        system.Solve(Wait=True)
        print("INFO: solve finished")
    except Exception as exc:
        print("AUTOMATION-FAILED: solve: %s" % exc)
        sys.exit(1)

    try:
        _save_project(project)
        print("INFO: project saved")
    except Exception as exc:
        print("AUTOMATION-FAILED: save project: %s" % exc)
        sys.exit(1)

    print(OK_MARKER)


if __name__ == "__main__":
    main()
