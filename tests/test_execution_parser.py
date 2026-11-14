# -*- coding: utf-8 -*-
"""execution_parser.py: Project_XXX, NN-DDD, выбор нагрузок (этап 2).

Кейсы — PLAN-MERGE §6.2: `Project_8946 -> 8946`; `18-245 -> 18, 245`;
`151-02-F2 -> 151, 02, F2`; `None` при несовпадении; `select_loads` для `18`.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from Mechanical import execution_parser as ep


class ExecutionParserTestCase(unittest.TestCase):
    """Разбор имени модели и выбор нагрузок исполнения."""

    def test_parse_project_id(self):
        self.assertEqual(ep.parse_project_id('Project_8946'), '8946')
        self.assertEqual(ep.parse_project_id('Project_10558'), '10558')

    def test_parse_project_id_mismatch(self):
        self.assertIsNone(ep.parse_project_id('Model_8946'))
        self.assertIsNone(ep.parse_project_id(None))

    def test_parse_execution_v2(self):
        self.assertEqual(ep.parse_execution('18-245'), '18')

    def test_parse_execution_v1(self):
        self.assertEqual(ep.parse_execution('151-02-F2'), '151')

    def test_parse_execution_mismatch(self):
        self.assertIsNone(ep.parse_execution('Project_8946'))
        self.assertIsNone(ep.parse_execution('opora'))
        self.assertIsNone(ep.parse_execution(None))

    def test_parse_diameter_v2(self):
        self.assertEqual(ep.parse_diameter('18-245'), '245')

    def test_parse_diameter_v1(self):
        self.assertEqual(ep.parse_diameter('151-02-F2'), '02')

    def test_parse_diameter_mismatch(self):
        self.assertIsNone(ep.parse_diameter('Project_8946'))
        self.assertIsNone(ep.parse_diameter(None))

    def test_parse_load_group(self):
        self.assertEqual(ep.parse_load_group('151-02-F2'), 'F2')
        self.assertEqual(ep.parse_load_group('151-02-f1'), 'F1')
        self.assertIsNone(ep.parse_load_group('18-245'))
        self.assertIsNone(ep.parse_load_group(None))

    def test_select_loads_v2_config(self):
        structure_type = {'loads': {'18': {'nominal_forces': {'fx': 1200}}}}
        self.assertEqual(ep.select_loads(structure_type, '18'),
                         {'nominal_forces': {'fx': 1200}})

    def test_select_loads_zero_padded_key(self):
        structure_type = {'loads': {'08': {'nominal_forces': {'fx': 1000}}}}
        self.assertEqual(ep.select_loads(structure_type, '8'),
                         {'nominal_forces': {'fx': 1000}})
        self.assertEqual(ep.select_loads(structure_type, 8),
                         {'nominal_forces': {'fx': 1000}})

    def test_select_loads_missing_execution(self):
        structure_type = {'loads': {'18': {'nominal_forces': {}}}}
        self.assertIsNone(ep.select_loads(structure_type, '99'))
        self.assertIsNone(ep.select_loads({'loads': {}}, '18'))
        self.assertIsNone(ep.select_loads(None, '18'))
        self.assertIsNone(ep.select_loads(structure_type, None))

    def test_select_loads_real_8946_config(self):
        path = os.path.join(ROOT, 'config', 'structure_type_8946.json')
        handle = open(path, 'r')
        try:
            structure_type = json.load(handle)
        finally:
            handle.close()

        loads = ep.select_loads(structure_type, '8')
        self.assertEqual(loads['cases']['НУЭ']['fx'], 1000)
        self.assertIsNone(ep.select_loads(structure_type, '99'))

        cases = ep.select_load_cases(structure_type, '8')
        self.assertEqual([name for name, _values in cases], ['НУЭ', 'НУЭ+ПЗ'])
        self.assertEqual(cases[1][1]['fz'], -4950)
        with self.assertRaises(ValueError):
            ep.select_load_cases(structure_type, '99')


if __name__ == '__main__':
    unittest.main()
