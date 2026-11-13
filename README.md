# ANSYS Automation

Скрипты автоматизации подготовки расчёта в ANSYS Workbench: SpaceClaim подготавливает геометрию
и именованные выборки, Mechanical настраивает контакты, сетку, граничные условия, нагрузки и
объекты результатов. Сам расчёт запускает пользователь — скрипты автоматизируют шаги до и после
него.

## Статус

Репозиторий содержит рабочую копию второго поколения скриптов (v2) и находится на **этапе 1**
плана слияния с v1: добавлены статические проверки и скелет юнит-тестов, логика v2 не менялась.
Этапы 2–5 добавляют чистые модули (`json_parser`, `execution_parser`, `pretension`,
`postprocessing`, `BoltManager` и др.) — их в этом репозитории пока нет.

## Требования

- ANSYS Workbench **21R1**.
- Mechanical: **IronPython 2.7** (встроенный scripting-движок Workbench).
- SpaceClaim: **API V19**.
- Вне ANSYS код проверяется **python3** (только для статических проверок; продуктовый код
  остаётся на Python 2.7).

## Структура

```
src/Mechanical/        скрипты Mechanical (точка входа — ansys_automation.py)
src/SpaceClaim/        скрипты SpaceClaim
config/                JSON-конфиги
tools/                 статические проверки (python3)
tests/                 скелет юнит-тестов (python3)
docs/                  план реализации
results/               результаты расчётов (генерируется, в .gitignore)
qa-workspace/          рабочая песочница QA (в .gitignore)
```

## Как запустить в ANSYS

Пути не зашиты: корень проекта определяется функцией `get_project_root()`
(`src/Mechanical/utils.py`) — сначала переменная окружения `ANSYS_AUTOMATION_ROOT`, затем путь,
вычисленный от расположения скрипта, затем текущий каталог.

### Mechanical

1. Открыть проект Workbench 21R1 с моделью.
2. В Mechanical: `Automation` → `Script` → открыть `src/Mechanical/ansys_automation.py`.
3. Запустить скрипт. Точка входа — `run_automation()` в конце файла; она создаёт
   `ProjectContext`, вызывает `ContactManager`, `MeshManager`, `AnalysisManager`,
   `ValidationManager`, `ResultManager` и включает `SaveProjectBeforeSolution`.
4. Расчёт запускает пользователь вручную.

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
- `tests/` на этапе 1 — **скелет**: модули созданы, тестовых методов ещё нет, поэтому
  `unittest` сообщает `Ran 0 tests … OK`. Реальные тесты пишутся на этапах 2–4.
- Ни одна из этих проверок не подтверждает работу ANSYS API, геометрии и физики. Единственное
  доказательство — ручной прогон в ANSYS.

## Правила кода

Код в `src/` обязан соответствовать `RULES.md`: UTF-8, заголовок кодировки, без f-строк,
`print "…"`, `u"…"` для русского текста, `.iteritems()`, без C-расширений и `pip`.
