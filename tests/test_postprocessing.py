# -*- coding: utf-8 -*-
"""postprocessing.py: build_csv_rows, write_csv (этап 4, FR-11, Q7).

Формат проверяется без ANSYS: 7 колонок в фиксированном порядке, UTF-8,
RFC 4180 quoting, пустой список результатов -> только заголовок.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from Mechanical import postprocessing

EXPECTED_HEADER = "structure_id,execution,load_step,result_name,body,value,unit"


class _ResultObject(object):
    """Двойник результата ANSYS с атрибутами вместо словаря."""

    def __init__(self, name, body, value, unit, load_step):
        self.Name = name
        self.Body = body
        self.Value = value
        self.Unit = unit
        self.LoadStep = load_step


def _read_text(path):
    handle = io.open(path, "r", encoding="utf-8")
    try:
        return handle.read()
    finally:
        handle.close()


class BuildCsvRowsTestCase(unittest.TestCase):
    """build_csv_rows: порядок и число колонок."""

    def test_records_give_seven_columns_in_order(self):
        records = [
            {"load_step": 1, "result_name": "Total Deformation",
             "body": "truba", "value": 0.12, "unit": "mm"},
            {"load_step": 2, "result_name": "Equivalent Stress",
             "body": u"шов", "value": 123.4, "unit": "MPa"},
        ]
        rows = postprocessing.build_csv_rows(records, "8946", "08")

        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(len(row), 7)
        self.assertEqual(rows[0],
                         ("8946", "08", "1", "Total Deformation", "truba", "0.12", "mm"))
        self.assertEqual(rows[1],
                         ("8946", "08", "2", "Equivalent Stress", u"шов", "123.4", "MPa"))

    def test_object_records_with_ansys_attribute_names(self):
        records = [_ResultObject("Total Deformation", "truba", 0.5, "mm", 3)]
        rows = postprocessing.build_csv_rows(records, "8946", "08")

        self.assertEqual(rows, [("8946", "08", "3", "Total Deformation", "truba", "0.5", "mm")])

    def test_record_level_ids_override_run_defaults(self):
        records = [{"structure_id": "10558", "execution": "09", "load_step": 1,
                    "result_name": "Total Deformation", "body": "truba",
                    "value": 0.1, "unit": "mm"}]
        rows = postprocessing.build_csv_rows(records, "8946", "08")

        self.assertEqual(rows[0][0], "10558")
        self.assertEqual(rows[0][1], "09")

    def test_none_value_becomes_empty_cell(self):
        records = [{"load_step": 1, "result_name": "Total Deformation",
                    "body": None, "value": None, "unit": None}]
        rows = postprocessing.build_csv_rows(records, "8946", "08")

        self.assertEqual(rows[0], ("8946", "08", "1", "Total Deformation", "", "", ""))

    def test_empty_results_give_no_data_rows(self):
        self.assertEqual(postprocessing.build_csv_rows([], "8946", "08"), [])
        self.assertEqual(postprocessing.build_csv_rows(None, "8946", "08"), [])


class WriteCsvTestCase(unittest.TestCase):
    """write_csv: файл, заголовок, quoting, кодировка."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="postprocessing-")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _path(self):
        # Каталога results ещё нет: write_csv обязан его создать.
        return os.path.join(self.tmpdir, "results", "results.csv")

    def test_writes_header_and_rows_in_utf8(self):
        rows = [("8946", "08", "1", u"Эквивалентное напряжение",
                 u"шов №1", "123.4", "MPa")]
        path = postprocessing.write_csv(self._path(), rows)

        self.assertTrue(os.path.isfile(path))
        content = _read_text(path)
        lines = content.splitlines()
        self.assertEqual(lines[0], EXPECTED_HEADER)
        self.assertEqual(lines[1],
                         u"8946,08,1,Эквивалентное напряжение,шов №1,123.4,MPa")

    def test_empty_rows_write_header_only(self):
        path = postprocessing.write_csv(self._path(), [])
        lines = _read_text(path).splitlines()

        self.assertEqual(lines, [EXPECTED_HEADER])

    def test_quotes_comma_quote_and_newline(self):
        rows = [("8946", "08", "1", u"Имя, с запятой",
                 u'шов "А"', "1,5", "mm")]
        path = postprocessing.write_csv(self._path(), rows)
        content = _read_text(path)

        self.assertIn(u'"Имя, с запятой"', content)
        self.assertIn(u'"шов ""А"""', content)
        self.assertIn(u'"1,5"', content)

    def test_line_with_wrong_cell_count_is_rejected(self):
        self.assertRaises(ValueError, postprocessing.write_csv,
                          self._path(), [("8946", "08", "1")])

    def test_columns_constant_is_the_contract(self):
        self.assertEqual(postprocessing.CSV_COLUMNS,
                         ("structure_id", "execution", "load_step",
                          "result_name", "body", "value", "unit"))


if __name__ == '__main__':
    unittest.main()
