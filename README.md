# ANSYS Automation

Скрипты автоматизации подготовки расчёта в ANSYS Workbench: SpaceClaim подготавливает геометрию
и именованные выборки, Mechanical настраивает контакты, сетку, граничные условия, нагрузки и
объекты результатов. Сам расчёт запускает пользователь — скрипты автоматизируют шаги до и после
него.

## Статус

Репозиторий содержит слитую реализацию (v1 + v2), **этапы 1–5 плана слияния закрыты**
(`PLAN-MERGE.md`):
чистые модули (`json_parser`, `execution_parser`, `pretension`, `postprocessing`), контекст проекта
с валидацией (`project_context`), менеджеры `ContactManager`/`MeshManager`/`AnalysisManager`/
`BoltManager`/`ValidationManager`/`ResultManager`, SpaceClaim-скрипты без литералов и заглушек.
Юнит-тесты: `python3 -m unittest discover -s tests` (138 тестов на закрытии этапа 4, дальше
набор растёт); статический гейт — `tools/`.
Ручной сквозной прогон в ANSYS (этап 6) и упаковка README (этап 7) ещё впереди, поэтому
инструкция запуска ниже неполна: границу «что проверено машинно, что только руками» держит
`qa/`.

## Требования

- ANSYS Workbench **21R1**.
- Mechanical: **IronPython 2.7** (встроенный scripting-движок Workbench).
- SpaceClaim: **API V19**.
- Вне ANSYS код проверяется **python3** (только для статических проверок; продуктовый код
  остаётся на Python 2.7).

## Структура

```
src/Mechanical/        скрипты Mechanical (точка входа — ansys_automation.py)
src/act/               ACT-расширение — канал доставки скрипта в Mechanical
src/SpaceClaim/        скрипты SpaceClaim
config/                JSON-конфиги
tools/                 статические проверки (python3)
tests/                 юнит-тесты чистых модулей и моков (python3)
docs/                  план реализации
results/               результаты расчётов (генерируется, в .gitignore)
qa-workspace/          рабочая песочница QA (в .gitignore)
```

## Как запустить в ANSYS

Пути не зашиты: корень проекта определяется функцией `get_project_root()`
(`src/Mechanical/utils.py`) — сначала переменная окружения `ANSYS_AUTOMATION_ROOT`, затем путь,
вычисленный от расположения скрипта, затем текущий каталог.

### Mechanical

Последовательность одна и та же во всех режимах: **настройка → решение → выгрузка CSV**.
Выгрузка до решения смысла не имеет: `Solution` пуст, и файл получил бы один заголовок.

Скрипт живёт в двух местах запуска:

1. **Batch-канал (ACT-расширение)** — `scripts\run_ansys.bat "<project>.wbpj" 8946 [18]`.
   Скрипт в Mechanical передаёт не журнал, а ACT-расширение `src/act/ansys_automation/`:
   журнал `scripts/workbench_journal.py` открывает проект, делает `system.Refresh()` +
   `system.Update()`, Mechanical при загрузке вызывает колбэк расширения `<oninit>`, и расширение
   выполняет `ansys_automation.py` → `Analysis.Solve(True)` → `export_results.py`. Журнал ждёт
   `results.csv` и маркер `ACT-RUN-OK` в `logs/act-run.log`.
   Прежний канал (команда на контейнер `Model`) на сборке 21.1.0.2020110819 молча не работал и
   удалён — факты в [`docs/run-modes.md`](docs/run-modes.md).
   Установка расширения (один раз): `scripts\install_act_extension.bat`, затем при необходимости
   включить его в Mechanical → `Extensions` → `Manage Extensions`. Нужна ACT-лицензия; подробности
   и список неподтверждённого — [`docs/act-extension.md`](docs/act-extension.md).
2. **Ручной канал** — Mechanical → `Automation` → `Script` → открыть
   `src/Mechanical/ansys_automation.py` → Run. Это только настройка: CSV на этом шаге не пишется.
   После решения запустить `src/Mechanical/export_results.py` (шаг 4 конвейера,
   `ResultManager.export_results`).

Путь выгрузки: переменная окружения `ANSYS_AUTOMATION_RESULTS` (полный путь к файлу), иначе
`output.results_csv` из `config/mechanical_configs/project_settings.json`, иначе
`<корень проекта>/results/results.csv`. Формат — 7 колонок
`structure_id,execution,load_step,result_name,body,value,unit`.

Журнал считает пустой CSV (только заголовок) провалом: печатает `AUTOMATION-FAILED: solve` и
завершается с ненулевым кодом. `run_ansys.bat` возвращает 0 только при коде `runwb2` = 0,
отсутствии `AUTOMATION-FAILED` и наличии `AUTOMATION-OK`.

Для проверки, что модули импортируются в текущем окружении, есть smoke-скрипт
`src/Mechanical/test_simple.py`: он последовательно создаёт менеджеры и печатает статус каждого
шага. Он не проверяет ни геометрию, ни физику.

### SpaceClaim

Скрипты `src/SpaceClaim/prepare_geometry.py` и `src/SpaceClaim/create_named_selections.py`
запускаются в SpaceClaim (API V19) как обычные скрипты; первый готовит геометрию, второй создаёт
named selections.

## Конфиги

| Файл | Что задаёт |
|---|---|
| `config/mechanical_configs/project_settings.json` | проект, исполнение, граничные условия, нагрузки, настройки сетки и решения, единицы |
| `config/mechanical_configs/mesh_config.json` | параметры сетки (`mesh_settings`) |
| `config/mechanical_configs/contact_settings.json` | настройки контактов и группировка |
| `config/mechanical_configs/analysis_scenarios.json` | именованные сценарии расчёта |
| `config/structure_type_8946.json` | тип конструкции 8946: нагрузки, `torque_nm`, граничные условия, обработка в SpaceClaim |
| `config/structure_type_10558.json` | тип конструкции 10558 |

Конфиги — строгий JSON: комментарии (`//`, `/* */`) в них не допускаются.

## Проверки

Все проверки запускаются без ANSYS, из корня репозитория:

| Команда | Что проверяет | Успешный вывод |
|---|---|---|
| `python3 tools/check_py2.py` | синтаксис Python 2.7 во всех `.py` в `src/` и `tools/` | `PY2-SYNTAX-OK <n>` (режим `python2`/`lib2to3`) или `PY2-SYNTAX-FALLBACK <n>` |
| `python3 tools/py2lint.py` | запрещённые в целевой среде конструкции в `src/`: f-строки, `async`/`await`, `yield from`, `nonlocal`, аннотации типов, импорты `pathlib`/`subprocess`/`numpy`/`pandas`/`pip` | `PY2-LINT-OK <n>` |
| `python3 tools/check_fstrings.py` | отсутствие f-строк в `src/` | `FSTRINGS-OK 0` |
| `python3 tools/validate_json.py` | валидность всех `config/**/*.json` | `JSON-OK <n>` |
| `python3 -m unittest discover -s tests` | юнит-тесты чистых функций и моков менеджеров | `OK` |

Код возврата у каждой проверки: `0` — нарушений нет, `1` — есть (нарушители печатаются).

Ограничения проверок:

- `check_py2.py` использует настоящий `python2`, если он есть в `PATH`; иначе — парсер
  `lib2to3`; иначе — fallback с нормализацией под python3 (он и помечается отдельно:
  `PY2-SYNTAX-FALLBACK`). Граница честности: грамматика `lib2to3` гибридная и принимает
  часть py3-синтаксиса (аннотации, `async`, `yield from`), поэтому режимы 2–3 доказывают
  «файл разбирается», но не py2-совместимость. Py3-only конструкции ловит `py2lint.py`,
  f-строки — `check_fstrings.py`; настоящая компиляция 2.7 возможна только при наличии
  `python2` или на ручном прогоне в ANSYS.
- `py2lint.py` и `check_fstrings.py` разбирают лексику (`tokenize`), поэтому слова в строках
  и комментариях не считаются нарушением.
- `tests/` содержит реальные тесты чистых модулей и моков менеджеров (`BoltManager`,
  `ResultManager`, `ContactManager`, `MeshManager`, `AnalysisManager`). Моки проверяют контракт
  вызовов API, а не поведение ANSYS, поэтому `OK` здесь означает «вызовы совпадают с ожидаемыми»,
  а не «в ANSYS работает».
- Ни одна из этих проверок не подтверждает работу ANSYS API, геометрии и физики. Единственное
  доказательство — ручной прогон в ANSYS.

## Правила кода

Код в `src/` обязан соответствовать `RULES.md`: UTF-8, заголовок кодировки, без f-строк,
`print "…"`, `u"…"` для русского текста, `.iteritems()`, без C-расширений и `pip`.
