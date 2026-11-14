# Режимы запуска (ANSYS 21R1): что подтверждено, что нет, что остаётся ручным

Документ фиксирует границу автоматизации на целевой среде: Windows, ANSYS Workbench **21R1**
(установка `v211`, сборка **21.1.0.2020110819**), локальная лицензия.

Все статусы ниже — из **живых прогонов 2026-11-14 на ноутбуке владельца** и из справочника
`RESEARCH-ANSYS-API.md`; где подтверждения нет, так и написано.

## Сводная таблица

| Режим / вызов | Статус | Чем подтверждён | Что это значит для репозитория |
|---|---|---|---|
| Batch Workbench: `runwb2 -B -F project.wbpj -R journal` | **Подтверждено** | Живой прогон: журнал исполняется, `runwb2` возвращает 0 | `scripts/run_ansys.bat` — обёртка прогона |
| Передача команды в Mechanical с контейнера `Model` (`DataContainerReference`) | **Опровергнуто** | 4 живых прогона: вызов возвращает `None`, файлов не появляется, исключений нет | Путь удалён из `scripts/` и `src/`; `grep` по нему даёт 0 |
| `GetProject()` в journal-API | **Отсутствует** | Живой прогон: `UnboundNameException: global name 'GetProject' is not defined` | Журнал не использует; проект открывается аргументом `-F` |
| `GetAllSystems()`, `GetSystem(Name=…)`, `GetContainer(ComponentName="Model")` | **Подтверждено** | Живая диагностика API: имена есть в globals/у системы | Выбор Mechanical-системы в `workbench_journal.py` |
| `system.Refresh()` и `system.Update()` | **Подтверждено вызовом** | Живой прогон: оба вызова проходят без исключений | Журнал поднимает Mechanical через `Update()` |
| `system.Edit()`, `system.Solve()` | **Отсутствует** у `DataReference` | Живая диагностика: методов нет | Журнал их не вызывает |
| `Save(Overwrite=True)` (journal-API) | **Подтверждено вызовом** | Живой прогон: вызов есть и проходит | Сохранение проекта в конце журнала |
| ACT-расширение `ansys_automation` (наш канал доставки) | **Не подтверждено** | Манифест и колбэк `<oninit>` — по публичным ACT-расширениям для Mechanical (см. `docs/act-extension.md`); загрузка в batch-режиме не проверялась | Канал реализации; первый живой прогон — за владельцем |
| `Analysis.Solve(Boolean wait)` внутри Mechanical | **Подтверждено справочником**, не живым прогоном | ACT 2021 R1 Reference: `Analysis.Solve(Boolean)` | Решение модели запускает ACT-расширение |
| `result.PlotData` / выгрузка CSV | **Не подтверждено** | RESEARCH §3.11: структура `PlotData` в 21R1 не зафиксирована | `ResultManager` собирает терпимо, пустой CSV = провал |
| Ручной запуск скрипта в Mechanical (`Automation` → `Script`) | **Подтверждено документацией**, по определению ручное | RESEARCH §5.1 | Резервный путь и путь для отладки |
| Консольный запуск SpaceClaim (headless/batch) | **Не подтверждено** | RESEARCH §5.1–5.4 | SpaceClaim-скрипты запускаются руками |
| Standalone Mechanical (`AnsysWBU.exe -DSApplet -AppModeMech`) | **Не подтверждено для 21R1** | Документирован для 2023 R2 | Не используем |
| PyMechanical (`batch=True`) | **Недоступно в 21R1** | Появился в 2023 R1+ | Не используем |

## Подтверждено

- **Batch Workbench.** `runwb2 -B -F <project> -R <script>`: `-B` — без UI, `-F` — загрузить проект,
  `-R` — выполнить скрипт и выйти. Журнал на целевой сборке исполняется и завершается с rc=0.
- **Batch-журнал сам по себе не доставляет код в Mechanical.** Четыре прогона 2026-11-14:

  | # | Режим | Что проверяли | Итог |
  |---|---|---|---|
  | 1 | `-B -R` | `GetProject()` | `UnboundNameException` — имени нет в journal-API |
  | 2 | `-B -R` | `Open` + `GetAllSystems` + отправка команды на контейнер | журнал прошёл (rc=0), вызов вернул `None`, файла нет |
  | 3 | `-X -R` | то же при живом Mechanical (`AnsysFWW.exe` поднялся) | то же: `None`, файла нет |
  | 4 | `-X -R` | `Refresh()` + команда + `Update()` | `Refresh`/`Update` OK, команда → `None`, файла нет |

- **Управляющие вызовы, которые есть.** У системы (`DataReference`): `GetContainer`, `Name`,
  `Refresh`, `Update`. В globals: `GetSystem`, `GetAllSystems`, `GetTemplate`, `Open`, `Save`,
  `SetScriptVersion`, `GetProjectFile`. Этого достаточно, чтобы поднять Mechanical (`Update`) и
  сохранить проект (`Save`).
- **Собственный лог.** В batch-режиме консоль Workbench — единственный канал сообщений, поэтому
  `run_ansys.bat` перенаправляет stdout+stderr в `logs/run-<дата>-<время>.log`, а ACT-расширение
  пишет свой `logs/act-run.log`.
- **Порядок конвейера.** Настройка (`ansys_automation.py`) → решение (`Analysis.Solve(True)`) →
  выгрузка (`export_results.py`). CSV пишется только после решения: до него `Solution` пуст.
  Путь — `ANSYS_AUTOMATION_RESULTS` или `<корень проекта>/results/results.csv`.

## Не подтверждено

- **Загрузка ACT-расширения в batch-режиме `runwb2 -B`.** Манифест (`<extension>`, `<guid>`,
  `<script>`, `<interface context="Mechanical">`, колбэк `<oninit>`) собран по публичным
  ACT-расширениям для Mechanical; справочник `act/v211` подтверждает только объектную модель
  Mechanical, не порядок загрузки расширений. Первый живой прогон покажет, срабатывает ли
  `<oninit>` при `Update()`.
- **ACT-лицензия на целевой машине.** ACT-расширения требуют ACT-лицензию; наличие её на ноутбуке
  не проверялось.
- **Момент вызова `<oninit>` относительно загрузки модели.** Если модель ещё не загружена,
  `ansys_automation.py` упадёт — это будет видно в `logs/act-run.log` как `AUTOMATION-FAILED`.
- **Двойное решение.** ACT-расширение решает модель внутри `oninit`, а `system.Update()` в журнале
  затем ещё раз обновляет систему. Повторное решение при неизменной модели должно быть дешёвым, но
  это не проверено.
- **Конкретная последовательность журнала.** Имена `Refresh`/`Update`/`Save` есть на целевой
  сборке (см. выше), но связка «Update → Mechanical → ACT-расширение → results.csv» живым прогоном
  не проверялась.
- **Факт выгрузки CSV после живого решения.** Насколько полно `PlotData` заполняется реальным
  решателем 21R1, оффлайн не проверить (RESEARCH §3.11). Пустой файл (только заголовок) журнал
  считает провалом: `AUTOMATION-FAILED: solve`.
- **SpaceClaim из консоли.** Для 21R1 нет подтверждённого headless-способа; два скрипта
  (`prepare_geometry.py`, `create_named_selections.py`) запускаются вручную — см.
  `scripts/run_spaceclaim.md`.

## Ручное (и почему)

| Шаг | Почему ручной |
|---|---|
| Подготовка геометрии в SpaceClaim (`prepare_geometry.py`) | Консольный запуск SpaceClaim в 21R1 не подтверждён |
| Именованные выборки в SpaceClaim (`create_named_selections.py`) | То же; результат зависит от подготовленной геометрии |
| Разовый запуск `scripts\install_act_extension.bat` | Расширение копируется в `%APPDATA%\Ansys\v211\ACT\extensions`; при необходимости включается в `Extensions` → `Manage Extensions` |
| Первый запуск `run_ansys.bat` и разбор `logs\act-run.log` | Нужна живая лицензия, проект `.wbpj`, ACT-лицензия и проверка загрузки расширения |
| Резервный путь: Mechanical → `Automation` → `Script` → `Run Script` для `ansys_automation.py`, затем решение и `export_results.py` | Работает без ACT; используется, если расширение в batch не поднимается |
| Проверка `results.csv` и физическая интерпретация | Поведение решателя нельзя проверить оффлайн |

## Ограничения batch-режима

- Batch ≠ GUI: скрипт, работающий в интерактивном Mechanical, может вести себя иначе в batch.
  Проверять нужно именно `runwb2 -B`.
- Лог — обычный текст; маркеры `AUTOMATION-FAILED` / `AUTOMATION-OK` печатает журнал,
  `run_ansys.bat` ищет их в логе и возвращает 1, если успеха нет.
