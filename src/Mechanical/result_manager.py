# -*- coding: utf-8 -*-
"""Объекты результатов и выгрузка в CSV (FR-10, FR-11).

``setup_plot_results`` создаёт в дереве Mechanical Total Deformation и
Equivalent Stress (FR-10), ``export_results`` собирает данные с ``PlotData``
результатов и пишет ``results.csv`` через ``postprocessing`` (FR-11, Q7).

Граница честности: точный интерфейс ``Result.PlotData`` в 21R1 исследованием
не зафиксирован (RESEARCH-ANSYS-API §3.11 перечисляет варианты выгрузки, но не
структуру таблицы). Поэтому сбор строк терпимый: поддерживаются строки-словари
с ключами ``Body``/``Value``/``LoadStep`` (и их нижним регистром); иное
логируется и пропускается, а файл всё равно пишется — минимум с заголовком.
Реальный формат ``PlotData`` проверяется на ручном прогоне (NFR-6, этап 6).
"""

import os

from Mechanical import postprocessing
from Mechanical.utils import get_project_root

# Каталог и имя файла по умолчанию (PLAN-MERGE §1.2, §4.7: ``results.csv``).
DEFAULT_EXPORT_DIR = "results"
DEFAULT_EXPORT_FILE = "results.csv"

# Переменная окружения перекрывает конфиг: удобно для batch-обвязки этапа 6a,
# когда путь выгрузки задаётся на прогон, а не в репозитории.
RESULTS_PATH_ENV = "ANSYS_AUTOMATION_RESULTS"


def _configured_export_path(context):
    """Путь из ``config/mechanical_configs/project_settings.json`` или ``None``.

    Относительный путь считается от корня проекта (``utils.get_project_root``),
    потому что Mechanical запускается с произвольной рабочей директорией.
    """
    output = (context.configs.get("project_settings") or {}).get("output") or {}
    configured = output.get("results_csv")
    if not configured:
        return None
    if os.path.isabs(configured):
        return configured
    return os.path.join(get_project_root(), DEFAULT_EXPORT_DIR, configured)


def resolve_export_path(context):
    """Путь CSV-выгрузки: переменная окружения -> конфиг -> значение по умолчанию.

    Args:
        context (ProjectContext): Контекст с ``configs``.

    Returns:
        str: абсолютный или заданный явно путь к ``results.csv``.
    """
    env_path = os.environ.get(RESULTS_PATH_ENV)
    if env_path:
        return env_path

    configured = _configured_export_path(context)
    if configured:
        return configured

    return os.path.join(get_project_root(), DEFAULT_EXPORT_DIR, DEFAULT_EXPORT_FILE)


def _field(record, names, default=None):
    """Поле строки ``PlotData``: словарь или объект; иначе ``default``."""
    if isinstance(record, dict):
        for name in names:
            if name in record:
                return record[name]
        return default

    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return default


# Методы создания объектов результатов в Mechanical API (имена по релизам
# различаются, поэтому пробуем по порядку и громко падаем, если ни одного нет).
STRESS_RESULT_METHODS = {
    "Maximum Shear Stress": ("AddMaximumShearStress",),
    "Stress Intensity": ("AddStressIntensity",),
    "Equivalent Stress": ("AddEquivalentStress",),
}

# Вид напряжений -> префикс имени объекта (по нему же работает чистка).
STRESS_RESULT_PREFIXES = {
    "Maximum Shear Stress": u"MSS_",
    "Stress Intensity": u"SI_",
    "Equivalent Stress": u"SEQV_",
}


def stress_kind_for(ns_name, stress_map):
    """Вид напряжений для Named Selection.

    Ключи ``stress_results`` — подстроки имени NS (``shov``), служебный ключ
    ``default`` — для всех остальных. Швы считаются отдельным результатом
    (Maximum Shear Stress), потому что в них интересен сдвиг, а не Мизес.

    Args:
        ns_name (str): имя Named Selection.
        stress_map (dict): ``project_settings.solution_settings.stress_results``.

    Returns:
        str: имя вида напряжений.
    """
    stress_map = stress_map or {}
    name = (ns_name or u"").lower()
    for key, kind in stress_map.items():
        if key == "default":
            continue
        if key.lower() in name:
            return kind
    return stress_map.get("default") or "Stress Intensity"


def result_object_name(kind, ns_name):
    """Имя объекта результата: префикс по виду напряжений + имя NS."""
    prefix = STRESS_RESULT_PREFIXES.get(kind, u"RES_")
    return u"{0}{1}".format(prefix, ns_name)


class ResultManager(object):
    """Создаёт объекты результатов и экспортирует их в CSV."""

    def __init__(self, context):
        """Инициализация менеджера результатов.

        Args:
            context (ProjectContext): Контекст текущего проекта.
        """
        self.context = context
        self.log = context.log
        self.model = context.model
        self.analysis = context.analysis

    def setup_plot_results(self):
        """Создаёт объекты результатов по конфигу (FR-10).

        Правила берутся из ``project_settings.solution_settings``:

        - ``default_results`` — объекты на всю модель (Total Deformation);
        - ``stress_results`` — вид напряжений по NS (``shov`` -> Maximum Shear
          Stress, ``default`` -> Stress Intensity); NS с префиксом ``gu_``
          пропускаются, это граничные условия, а не тела;
        - ``stress_averaging`` — ``ElementalMean`` для этих результатов.

        Before: ``AddTotalDeformation()``/``AddEquivalentStress()`` без области
        охвата, а ``Solution`` не чистился — отсюда дубли по всем телам после
        каждого прогона.
        """
        self.log.info(u"Настройка объектов PlotResults...")

        if not self.analysis:
            self.log.error(u"Анализ не найден. Невозможно настроить результаты.")
            return

        try:
            solution = self.analysis.Solution
        except Exception as exc:
            self.log.error(u"Solution недоступен: {0}".format(exc))
            return

        # Дубли копятся между прогонами: чистим результаты конвейера.
        try:
            from Mechanical import utils as mei_utils
            removed = mei_utils.purge_automatic_objects(solution, self.log)
            if removed:
                self.log.info(u"Удалено объектов результатов прошлого прогона: {0}".format(removed))
        except Exception as exc:
            self.log.warning(u"Не удалось очистить Solution: {0}".format(exc))

        settings = (self.context.configs.get("project_settings") or {}).get(
            "solution_settings") or {}
        averaging = settings.get("stress_averaging") or u"ElementalMean"

        # 1. Объекты на всю модель (по умолчанию — Total Deformation).
        for result_name in settings.get("default_results") or [u"Total Deformation"]:
            if result_name == u"Total Deformation":
                try:
                    obj = solution.AddTotalDeformation()
                    obj.Name = u"TD_all"
                    self.log.info(u"Результат '{0}' создан на всю модель.".format(obj.Name))
                except Exception as exc:
                    self.log.error(u"Total Deformation не создан: {0}".format(exc))
            else:
                self.log.warning(u"Результат '{0}' из default_results не поддержан.".format(result_name))

        # 2. Напряжения по Named Selection (кроме gu_*).
        stress_map = settings.get("stress_results") or {}
        for ns in self._result_named_selections():
            kind = stress_kind_for(ns.Name, stress_map)
            self._add_stress_result(solution, kind, ns, averaging)

    def _result_named_selections(self):
        """Named Selections для результатов: всё, кроме ``gu_*``."""
        selections = []
        try:
            for ns in self.model.NamedSelections.Children:
                name = getattr(ns, "Name", u"") or u""
                if name.lower().startswith(u"gu_"):
                    continue
                selections.append(ns)
        except Exception as exc:
            self.log.warning(u"Named Selections недоступны: {0}".format(exc))
        return selections

    def _add_stress_result(self, solution, kind, ns, averaging):
        """Создаёт объект напряжений нужного вида, привязанный к NS."""
        methods = STRESS_RESULT_METHODS.get(kind, ())
        for method_name in methods:
            factory = getattr(solution, method_name, None)
            if factory is None:
                continue
            try:
                obj = factory()
                obj.Name = result_object_name(kind, ns.Name)
                try:
                    obj.Location = ns
                except Exception as exc:
                    self.log.warning(u"Location для '{0}' не задан: {1}".format(obj.Name, exc))
                self._set_averaged(obj, averaging)
                self.log.info(u"Результат '{0}': {1} по NS '{2}', усреднение {3}".format(
                    obj.Name, kind, ns.Name, averaging))
                return obj
            except Exception as exc:
                self.log.warning(u"{0} не создан для '{1}': {2}".format(method_name, ns.Name, exc))
        self.log.error(u"Ни один метод для '{0}' не доступен в этой сборке (NS '{1}').".format(
            kind, ns.Name))
        return None

    def _set_averaged(self, obj, value):
        """Пробует выставить ``Averaged = ElementalMean`` (имя перечисления по релизам)."""
        if not value:
            return
        try:
            current = obj.Averaged
            target = getattr(current, value, None)
            if target is None:
                self.log.warning(u"Перечисление Averaged.{0} недоступно у '{1}'".format(
                    value, getattr(obj, "Name", u"?")))
                return
            obj.Averaged = target
        except Exception as exc:
            self.log.warning(u"Averaged не выставлен у '{0}': {1}".format(
                getattr(obj, "Name", u"?"), exc))

    def export_results(self, export_path=None):
        """Собирает результаты и пишет CSV (FR-11).

        Args:
            export_path (str): путь к файлу; по умолчанию — из переменной
                окружения ``ANSYS_AUTOMATION_RESULTS``, затем
                ``project_settings.output.results_csv``, затем
                ``<корень проекта>/results/results.csv``.

        Returns:
            str: путь записанного файла или ``None``, если запись не удалась.
        """
        self.log.info(u"Экспорт результатов...")

        try:
            path = export_path or resolve_export_path(self.context)
            records = self.collect_result_rows()
            rows = postprocessing.build_csv_rows(
                records, self._structure_id(), getattr(self.context, "execution_no", None))
            postprocessing.write_csv(path, rows)
            self.log.info(u"Результаты экспортированы в: {0} (строк: {1})".format(
                path, len(rows)))
            return path
        except Exception as e:
            self.log.error(u"Ошибка при экспорте результатов: {0}".format(e))
            return None

    def collect_result_rows(self):
        """Собирает записи результатов из ``Solution.Children``.

        Returns:
            list: записи с полями ``result_name``, ``body``, ``load_step``,
            ``value``, ``unit``; пустой список, если данных нет.
        """
        rows = []
        if not self.analysis:
            self.log.warning(u"Анализ не найден: результаты не собраны.")
            return rows

        try:
            children = self.analysis.Solution.Children
        except Exception as e:
            self.log.warning(u"Solution.Children недоступны: {0}".format(e))
            return rows

        for result in children or []:
            name = getattr(result, "Name", None)
            if not name:
                continue

            unit = getattr(result, "Unit", None)
            try:
                plot_data = result.PlotData
            except Exception as e:
                self.log.warning(u"PlotData результата '{0}' недоступен: {1}".format(name, e))
                continue

            rows.extend(self._rows_from_plot_data(name, unit, plot_data))

        return rows

    def _rows_from_plot_data(self, result_name, unit, plot_data):
        """Строки одного результата: ``PlotData`` -> записи для CSV."""
        if plot_data is None:
            self.log.warning(u"У результата '{0}' нет PlotData.".format(result_name))
            return []

        records = []
        try:
            iterator = iter(plot_data)
        except TypeError:
            self.log.warning(
                u"PlotData результата '{0}' не итерируется; структура таблицы "
                u"не подтверждена (RESEARCH-ANSYS-API §3.11).".format(result_name))
            return []

        for item in iterator:
            records.append({
                "result_name": result_name,
                "body": _field(item, ("Body", "body")),
                "load_step": _field(item, ("LoadStep", "load_step", "Step", "step")),
                "value": _field(item, ("Value", "value", "Values", "values")),
                "unit": _field(item, ("Unit", "unit"), unit),
            })

        if not records:
            self.log.warning(u"PlotData результата '{0}' пуст.".format(result_name))
        return records

    def _structure_id(self):
        """Идентификатор конструкции для колонки ``structure_id``."""
        return (getattr(self.context, "structure_type_id", None)
                or getattr(self.context, "project_id", None))
