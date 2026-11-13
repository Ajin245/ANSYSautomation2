# -*- coding: utf-8 -*-
"""structure_detector.py: тип конструкции по имени/NS, fallback (этап 2).

Кейсы — PLAN-MERGE §6.2: v1-шаблоны `151-02-F2`, `custom_001-01-F1`,
`151_something`, `ABC_001`; v2-шаблоны `Project_8946`, `18-245`; fallback;
NS-паттерны `gu_bolt*_f`, `gu_fixed`, `gu_remote_disp`, `gu_force`.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from Mechanical import structure_detector as sd


class _NamedSelection(object):
    """Минимальный двойник объекта Named Selection с атрибутом Name."""

    def __init__(self, name):
        self.Name = name


class StructureDetectorTestCase(unittest.TestCase):
    """Определение типа конструкции и анализ Named Selections."""

    def test_v1_standard_pattern(self):
        self.assertEqual(sd.detect_structure_type('151-02-F2'), ('151', 'standard'))

    def test_v1_custom_pattern(self):
        self.assertEqual(sd.detect_structure_type('custom_001-01-F1'),
                         ('custom_001', 'custom'))

    def test_v1_legacy_pattern(self):
        self.assertEqual(sd.detect_structure_type('151_something'), ('151', 'legacy'))

    def test_v1_coded_pattern(self):
        self.assertEqual(sd.detect_structure_type('ABC_001'), ('ABC', 'coded'))

    def test_v2_project_pattern(self):
        self.assertEqual(sd.detect_structure_type('Project_8946'), ('8946', 'project'))

    def test_v2_execution_pattern_has_no_structure_id(self):
        # 18-245 — исполнение и диаметр, идентификатора конструкции в имени нет.
        self.assertEqual(sd.detect_structure_type('18-245'), (None, 'execution'))

    def test_unknown_fallback(self):
        self.assertEqual(sd.detect_structure_type('weird-name'), ('weird', 'unknown'))

    def test_empty_input(self):
        self.assertEqual(sd.detect_structure_type(''), (None, 'unknown'))
        self.assertEqual(sd.detect_structure_type(None), (None, 'unknown'))

    def test_detect_ns_patterns(self):
        result = sd.detect_ns_patterns(['gu_bolt12_f', 'gu_fixed', 'gu_force'])
        self.assertTrue(result['has_bolts'])
        self.assertTrue(result['has_supports'])
        self.assertFalse(result['has_remote'])
        self.assertEqual(result['total_ns_count'], 3)
        self.assertEqual(result['ns_names'], ['gu_bolt12_f', 'gu_fixed', 'gu_force'])

    def test_detect_ns_patterns_accepts_objects(self):
        names = [_NamedSelection('mbolt8'), _NamedSelection('gu_remote_disp')]
        result = sd.detect_ns_patterns(names)
        self.assertTrue(result['has_bolts'])
        self.assertTrue(result['has_remote'])
        self.assertEqual(result['ns_names'], ['mbolt8', 'gu_remote_disp'])

    def test_detect_ns_patterns_empty(self):
        result = sd.detect_ns_patterns([])
        self.assertFalse(result['has_bolts'])
        self.assertEqual(result['total_ns_count'], 0)

    def test_detect_load_configuration(self):
        result = sd.detect_load_configuration(['gu_force', 'gu_moment', 'gu_fixed'])
        self.assertTrue(result['has_force_load'])
        self.assertTrue(result['has_moment_load'])
        self.assertFalse(result['has_pressure_load'])

    def test_detect_boundary_conditions(self):
        result = sd.detect_boundary_conditions(['gu_fixed', 'gu_remote_disp', 'gu_disp'])
        self.assertTrue(result['has_fixed_support'])
        self.assertTrue(result['has_remote_displacement'])
        self.assertTrue(result['has_displacement'])
        self.assertFalse(result['has_frictionless'])

    def test_detect_boundary_conditions_empty(self):
        result = sd.detect_boundary_conditions([])
        self.assertFalse(result['has_fixed_support'])
        self.assertFalse(result['has_remote_force'])


if __name__ == '__main__':
    unittest.main()
