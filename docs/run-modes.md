# Режимы запуска (ANSYS 21R1): что подтверждено, что нет, что остаётся ручным

Документ фиксирует границу автоматизации на целевой среде: Windows, ANSYS Workbench **21R1**
(установка `v211`), локальная лицензия. Источник фактов о режимах — `RESEARCH-ANSYS-API.md` §5
(Workbench Scripting Guide и практика пользователей).

## Сводная таблица

| Режим | Статус | Чем подтверждён | Что это значит для репозитория |
|---|---|---|---|
| Batch Workbench: `runwb2 -B -F project.wbpj -R script` | **Подтверждено** | Workbench Scripting Guide (`RESEARCH-ANSYS-API.md` §5.3) | `scripts/run_ansys.bat` — штатный путь прогона |
| Вызов Mechanical из журнала: `model.SendCommand(Language="Python", Command=...)` | **Подтверждено** | Документация Ansys + практика (§5.4) | `scripts/workbench_journal.py` использует `SendCommand` и `execfile` |
| Mechanical без GUI внутри batch Workbench | **Подтверждено с оговоркой** | §5.4: `SendCommand` открывает Mechanical в batch по наблюдениям пользователей; batch ≠ GUI | Скрипт, работающий в GUI, может вести себя иначе в batch — проверять именно `runwb2 -B` |
| Решение модели из журнала: `system.Solve(Wait=True)` | **Не подтверждено прогоном** | API-вызов документирован, но конкретная последовательность в нашем журнале не исполнялась | Считать рабочей гипотезой до прогона владельца |
| Сохранение проекта из журнала | **Не подтверждено прогоном** | `project.Save()` / `Save()` — журнальные вызовы, живой прогон не делался | То же |
| Консольный запуск SpaceClaim (headless/batch) | **Не подтверждено** | §5.1–5.4: для 21R1 подтверждения нет | В документации не обещаем; SpaceClaim-скрипты запускаются руками |
| Standalone Mechanical (`AnsysWBU.exe -DSApplet -AppModeMech`) | **Не подтверждено для 21R1** | Документирован для 2023 R2 | Не используем |
| PyMechanical (`batch=True`) | **Недоступно в 21R1** | Появился в 2023 R1+ | Не используем |
| Просмотр ошибок в Console Window batch-режима | **Подтверждено** | §5.5 | Дублируем в `logs/run-*.log` |

## Подтверждено

- **Batch Workbench.** `runwb2 -B -F <project> -R <script>`: `-B` — без UI, `-F` — загрузить проект,
  `-R` — выполнить скрипт и выйти. Это единственный подтверждённый headless-путь для 21R1.
- **`SendCommand`.** `model.SendCommand(Language="Python", Command=...)` исполняет Python-команду
  внутри Mechanical. Наш журнал передаёт туда `execfile(r"...\src\Mechanical\ansys_automation.py")`.
- **Собственный лог.** В batch-режиме консоль Workbench — единственный канал сообщений, поэтому
  `run_ansys.bat` перенаправляет stdout+stderr в `logs/run-<дата>-<время>.log`.
- **Порядок конвейера.** `SendCommand` (настройка `ansys_automation.py`) → `Solve(Wait=True)` →
  `SendCommand` (выгрузка `export_results.py`). CSV пишется только после решения: до него
  `Solution` пуст. Путь файла — `ANSYS_AUTOMATION_RESULTS` или
  `<корень проекта>/results/results.csv`, тот же, что у `ResultManager`.

## Не подтверждено

- **SpaceClaim из консоли.** Для 21R1 нет подтверждённого способа запустить SpaceClaim-скрипт
  headless. Поэтому два скрипта (`prepare_geometry.py`, `create_named_selections.py`) запускаются
  вручную — см. `scripts/run_spaceclaim.md`.
- **Конкретная последовательность журнала.** Имена вызовов (`GetProject`, `GetSystem`,
  `GetContainer`, `Solve`, `project.Save`) взяты из документации и шаблонов журналов, но весь
  `workbench_journal.py` на живом Workbench 21R1 ещё не исполнялся.
- **Факт выгрузки CSV после живого решения.** Журнал проверяет `results.csv` после второго
  `SendCommand`: нет файла или в нём только заголовок — печатается `AUTOMATION-FAILED: solve`
  и код 1. Насколько полно `PlotData` заполняется реальным решателем 21R1, оффлайн не
  проверить (RESEARCH-ANSYS-API §3.11).
- **Поведение `ansys_automation.py` в batch.** Ошибка настройки печатает маркер
  `AUTOMATION-FAILED` и пробрасывает исключение, поэтому `SendCommand` может завершиться
  исключением. Сбой, который Mechanical только записал в свой лог, маркером не ловится —
  такие случаи видны лишь при разборе `logs/run-*.log`.

## Ручное (и почему)

| Шаг | Почему ручной |
|---|---|
| Подготовка геометрии в SpaceClaim (`prepare_geometry.py`) | Консольный запуск SpaceClaim в 21R1 не подтверждён |
| Именованные выборки в SpaceClaim (`create_named_selections.py`) | То же; результат зависит от подготовленной геометрии |
| Первый запуск `run_ansys.bat` и разбор лога | Требуется живая лицензия, проект `.wbpj` и проверка фактических имён систем |
| Запуск `export_results.py` после ручного решения | В GUI-режиме журнала нет: выгрузку запускает пользователь отдельным скриптом |
| Проверка `results.csv` и физическая интерпретация | Поведение решателя нельзя проверить оффлайн |

## Ограничения batch-режима

- Batch ≠ GUI (вендорское подтверждение в PyMechanical FAQ): скрипт, работающий в интерактивном
  Mechanical, может падать в batch. Проверять нужно именно `runwb2 -B`.
- Лог — обычный текст; маркер `AUTOMATION-FAILED` печатает журнал, `run_ansys.bat` ищет его в логе
  и возвращает 1, даже если `runwb2` завершился с 0.
