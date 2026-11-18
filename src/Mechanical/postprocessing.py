# -*- coding: utf-8 -*-
"""Выгрузка результатов в CSV (FR-11, PLAN-MERGE Q7, ветвь A).

Колонки и их порядок зафиксированы спецификацией и не расширяются:

    structure_id, execution, load_step, result_name, body, value, unit

Модуль чистый: ``io``/``os``, без ANSYS. Поэтому формат проверяется без
живого Mechanical (``tests/test_postprocessing.py``).

Почему CSV пишется вручную, а не через модуль ``csv``: под IronPython 2.7
``csv.writer`` не принимает ``unicode``, а текстовый поток ``io.open(...,
encoding="utf-8")`` + ``csv`` падает на кириллице (``csv`` пишет ``str``-байты
в unicode-поток). Ручное кодирование каждой строки в UTF-8 работает одинаково
в Python 2.7 и Python 3 и даёт RFC 4180-совместимое quoting.
"""

import io
import os

# Порядок колонок — контракт Q7 (ветвь A); менять только по решению владельца.
CSV_COLUMNS = (
    "structure_id",
    "execution",
    "load_step",
    "result_name",
    "body",
    "value",
    "unit",
)

# Окончание строки — CRLF, как у csv по умолчанию (Excel на Windows).
LINE_TERMINATOR = u"\r\n"

# Ячейку нужно взять в кавычки, если в ней есть разделитель, кавычка или перевод строки.
_QUOTE_TRIGGERS = (u",", u'"', u"\n", u"\r")


def _cell(value):
    """Значение -> строка CSV. ``None`` пишется пустой ячейкой, не ``u"None"``."""
    if value is None:
        return u""
    return u"{0}".format(value)


def _quote(value):
    """Экранирует ячейку по RFC 4180: кавычки удваиваются, ячейка оборачивается."""
    text = _cell(value)
    for trigger in _QUOTE_TRIGGERS:
        if trigger in text:
            return u'"' + text.replace(u'"', u'""') + u'"'
    return text


def _line(cells):
    """Одна CSV-строка (без завершающего перевода строки в списке)."""
    return u",".join([_quote(cell) for cell in cells]) + LINE_TERMINATOR


def _field(record, names, default=None):
    """Поле записи: сначала словарь, затем атрибуты объекта; иначе ``default``."""
    if isinstance(record, dict):
        for name in names:
            if name in record:
                return record[name]
        return default

    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return default


def build_csv_rows(results, structure_id=None, execution=None):
    """Превращает результаты в строки CSV в порядке ``CSV_COLUMNS``.

    Запись результата — словарь или объект с полями ``load_step``, ``result_name``,
    ``body``, ``value``, ``unit``. ``structure_id``/``execution`` берутся из записи,
    а при отсутствии — из аргументов (они общие для всего прогона). Допустимы
    ANSYS-имена атрибутов ``Name``/``Body``/``Value``/``Unit``.

    Args:
        results (list): записи результатов; пустой список допустим.
        structure_id (str): идентификатор конструкции для всех строк.
        execution (str): номер исполнения для всех строк.

    Returns:
        list: список кортежей из 7 ячеек, готовых для ``write_csv``.
    """
    rows = []
    for record in results or []:
        rows.append((
            _cell(_field(record, ("structure_id",), structure_id)),
            _cell(_field(record, ("execution",), execution)),
            _cell(_field(record, ("load_step", "LoadStep", "step", "Step"))),
            _cell(_field(record, ("result_name", "Name"))),
            _cell(_field(record, ("body", "Body"))),
            _cell(_field(record, ("value", "Value"))),
            _cell(_field(record, ("unit", "Unit"))),
        ))
    return rows


def write_csv(path, rows):
    """Пишет CSV-файл в UTF-8: заголовок и строки.

    Пустой ``rows`` даёт файл только с заголовком — это корректный и ожидаемый
    случай (результатов нет, но потребитель файла не должен падать).
    Родительский каталог создаётся при необходимости.

    Args:
        path (str): путь к файлу.
        rows (list): кортежи из ``build_csv_rows`` (или любой последовательности
            из 7 ячеек).

    Returns:
        str: путь, по которому записан файл.

    Raises:
        ValueError: строка содержит не 7 ячеек (защита от разъезда с форматом).
    """
    lines = [_line(CSV_COLUMNS)]

    for row in rows or []:
        cells = tuple(row)
        if len(cells) != len(CSV_COLUMNS):
            raise ValueError(
                u"Строка CSV должна содержать {0} колонок, получено {1}: {2}".format(
                    len(CSV_COLUMNS), len(cells), cells))
        lines.append(_line(cells))

    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)

    handle = io.open(path, "wb")
    try:
        handle.write(u"".join(lines).encode("utf-8"))
    finally:
        handle.close()

    return path
