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

# Путь v2: results/ рядом с рабочей директорией Mechanical.
DEFAULT_EXPORT_DIR = "results"
DEFAULT_EXPORT_FILE = "results_export.csv"


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


class ResultManager(object):
    """Создаёт объекты результатов и экспортирует их в CSV."""

    def __init__(self, context):
        """Инициализация менеджера результатов.

        Args:
            context (ProjectContext): Контекст текущего проекта.
        """
        self.context = context
        self.log = context.log
        self.analysis = context.analysis

    def setup_plot_results(self):
        """Создаёт объекты PlotResults в дереве Mechanical перед расчётом (FR-10)."""
        self.log.info(u"Настройка объектов PlotResults...")

        if not self.analysis:
            self.log.error(u"Анализ не найден. Невозможно настроить результаты.")
            return

        try:
            solution = self.analysis.Solution

            # 1. Общие перемещения (Total Deformation)
            total_def = solution.AddTotalDeformation()
            total_def.Name = u"Total Deformation"

            # 2. Напряжения (Equivalent Von-Mises Stress)
            equiv_stress = solution.AddEquivalentStress()
            equiv_stress.Name = u"Equivalent Stress"

            self.log.info(u"Объекты PlotResults успешно созданы.")
        except Exception as e:
            self.log.error(u"Ошибка при создании PlotResults: {0}".format(e))

    def export_results(self, export_path=None):
        """Собирает результаты и пишет CSV (FR-11).

        Args:
            export_path (str): путь к файлу; по умолчанию
                ``<cwd>/results/results_export.csv`` (как в v2).

        Returns:
            str: путь записанного файла или ``None``, если запись не удалась.
        """
        self.log.info(u"Экспорт результатов...")

        try:
            path = export_path or os.path.join(os.getcwd(), DEFAULT_EXPORT_DIR,
                                               DEFAULT_EXPORT_FILE)
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
