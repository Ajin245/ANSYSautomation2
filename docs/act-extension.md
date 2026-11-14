# ACT-расширение `ansys_automation`: канал доставки скрипта в Mechanical

## Зачем

На ANSYS 21R1 (сборка 21.1.0.2020110819) журнал Workbench больше не может передать наш скрипт
в Mechanical: вызов команды на контейнере `Model` (`DataContainerReference`) возвращает `None`
и не производит эффекта. Четыре живых прогона и таблица «что подтверждено» — в
[`run-modes.md`](run-modes.md).

Новый канал — ACT-расширение. Оно живёт **внутри** Mechanical: при загрузке Mechanical вызывает
колбэк `<oninit>`, и уже оттуда выполняется наш код. Команду из журнала передавать не нужно.

## Состав

```
src/act/ansys_automation/
  ansys_automation.xml      манифест ACT: guid, script, interface context="Mechanical", <oninit>
  ansys_automation_act.py   IronPython 2.7: on_init(context) -> настройка -> решение -> выгрузка
scripts/install_act_extension.bat   копирование в каталог ACT пользователя
```

`ansys_automation_act.py` при вызове:

1. читает `ANSYS_AUTOMATION_ROOT` и `ANSYS_AUTOMATION_RUN`;
2. если `ANSYS_AUTOMATION_RUN != 1` — пишет `ACT-RUN-SKIP` и **ничего не делает** (установленное
   расширение не должно запускать конвейер при обычной работе инженера);
3. выполняет `src/Mechanical/ansys_automation.py` (настройка модели);
4. вызывает `Analysis.Solve(True)` (ACT 2021 R1 Reference: `Analysis.Solve(Boolean wait)`);
5. выполняет `src/Mechanical/export_results.py` (`results.csv`);
6. пишет `logs/act-run.log`: `ACT-RUN-START`, шаги, `ACT-RUN-OK` или `AUTOMATION-FAILED` + traceback.

## Установка

```bat
scripts\install_act_extension.bat
```

Скрипт копирует манифест и модули в пользовательский каталог ACT:

```
%APPDATA%\Ansys\v211\ACT\extensions\ansys_automation.xml
%APPDATA%\Ansys\v211\ACT\extensions\ansys_automation\ansys_automation_act.py
```

Каталог версии переопределяется: `set ANSYS_ACT_VER=211` (по умолчанию `211` = 21R1).
После установки перезапустить Workbench/Mechanical; если расширение не подхватилось —
включить его в Mechanical → `Extensions` → `Manage Extensions`.

> **ACT-лицензия.** ACT-расширения требуют ACT-лицензию. Наличие её на целевой машине не
> проверялось — это первое, что покажет живой прогон.

## Прогон

```bat
scripts\run_ansys.bat "C:\Work\Ansys\Project_8946\Model\Project_8946.wbpj" 8946 18
```

`run_ansys.bat` выставляет `ANSYS_AUTOMATION_ROOT`, `ANSYS_AUTOMATION_RUN=1`, `STRUCTURE_ID`,
`EXECUTION` и запускает `runwb2 -B -F <project> -R scripts\workbench_journal.py`.

Журнал:

1. берёт Mechanical-систему (`MECH_SYSTEM_NAME` или первую с контейнером `Model`) из уже
   открытого проекта;
2. `system.Refresh()`, затем `system.Update()` — Update поднимает Mechanical, там срабатывает
   расширение;
3. ждёт `results.csv` и `ACT-RUN-OK` в `logs/act-run.log` (таймаут — `ANSYS_ACT_WAIT_SECONDS`,
   по умолчанию 300 с);
4. сохраняет проект через `Save(Overwrite=True)`, печатает `AUTOMATION-OK`.

Коды возврата `run_ansys.bat`: `0` — успех, `5` — расширение не установлено, `1` — в логе
`AUTOMATION-FAILED`, иначе — код `runwb2`.

## Что не подтверждено

- загрузка ACT-расширения именно в batch-режиме `runwb2 -B`;
- наличие ACT-лицензии на целевой машине;
- момент вызова `<oninit>` относительно загрузки модели;
- двойное решение (`Solve` в расширении + `system.Update()` в журнале);
- фактическое наполнение `Result.PlotData` в 21R1.

Всё это видно в `logs\act-run.log` и `logs\run-*.log` первого живого прогона. Если расширение
не поднимается в batch — резервный путь описан в `run-modes.md`, раздел «Ручное»: запуск
`src/Mechanical/ansys_automation.py` из Mechanical → `Automation` → `Script`, решение, затем
`src/Mechanical/export_results.py`.

## Источники структуры манифеста

Справочник `act/v211` подтверждает объектную модель Mechanical (`Analysis.Solve`, `Model.Analyses`,
`ExtAPI`), но не описывает порядок загрузки расширений. Структура манифеста взята из публичных
ACT-расширений для Mechanical (вторичные источники):

- `Analysis.Solve(Boolean)` — ACT 2021 R1 Reference:
  `https://storage.ansys.com/act/v211/ACTReferenceHTML/Mechanical/Reference.methode.Ansys.ACT.Automation.Mechanical.Analysis.Solve.html`
- манифест с `<interface context="Mechanical">` и `<callbacks><oninit>`:
  `https://github.com/FFFFatCAT/AnsysACT` (`HiFive.xml`),
  `https://github.com/morbuzaglo/ansys-singularity-detector` (`extension/SingularityDetector.xml`)
- раскладка установки (`%APPDATA%\Ansys\v<ver>\ACT\extensions`) и необходимость ACT-лицензии:
  `https://github.com/morbuzaglo/ansys-singularity-detector` (`devtools/extension_deployer.py`)
