# -*- coding: utf-8 -*-
"""pretension.py: torque_to_pretension, select_torque, select_bolt_diameter (этап 2).

Кейсы — PLAN-MERGE §6.2: `torque_to_pretension(11.8, 8) ~= 3986.5`;
`select_torque` по строковому и числовому ключу; `select_bolt_diameter` по NS;
отсутствие момента; момент `0`.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from Mechanical import pretension


class _NamedSelection(object):
    """Двойник Named Selection с атрибутом Name."""

    def __init__(self, name):
        self.Name = name


class PretensionTestCase(unittest.TestCase):
    """Преднатяг болта по моменту затяжки."""

    def test_torque_to_pretension_reference_value(self):
        # 11.8 / (0.37 * 8 / 1000) = 3986.48... Н — формула v2 (Q6: допущение).
        self.assertAlmostEqual(pretension.torque_to_pretension(11.8, 8), 3986.5, delta=0.1)

    def test_torque_to_pretension_exact_formula(self):
        self.assertAlmostEqual(pretension.torque_to_pretension(888, 30), 80000.0, places=6)

    def test_torque_to_pretension_zero_torque(self):
        self.assertEqual(pretension.torque_to_pretension(0, 8), 0.0)

    def test_torque_to_pretension_none_torque(self):
        self.assertIsNone(pretension.torque_to_pretension(None, 8))

    def test_torque_to_pretension_invalid_diameter(self):
        self.assertRaises(ValueError, pretension.torque_to_pretension, 11.8, 0)
        self.assertRaises(ValueError, pretension.torque_to_pretension, 11.8, None)

    def test_select_torque_string_key(self):
        self.assertEqual(pretension.select_torque({'8': 11.8, '10': 18.5}, 8), 11.8)

    def test_select_torque_int_key(self):
        self.assertEqual(pretension.select_torque({8: 11.8}, 8), 11.8)

    def test_select_torque_missing(self):
        self.assertIsNone(pretension.select_torque({'8': 11.8}, 12))
        self.assertIsNone(pretension.select_torque(None, 8))
        self.assertIsNone(pretension.select_torque({'8': 11.8}, None))

    def test_select_torque_zero_is_treated_as_missing(self):
        self.assertIsNone(pretension.select_torque({'8': 0}, 8))

    def test_select_bolt_diameter_mbolt(self):
        self.assertEqual(pretension.select_bolt_diameter(['gu_fixed', 'mbolt8']), 8)

    def test_select_bolt_diameter_gu_bolt(self):
        self.assertEqual(pretension.select_bolt_diameter(['gu_bolt12_f']), 12)

    def test_select_bolt_diameter_priority(self):
        # mbolt<d> имеет приоритет над общим bolt<d>.
        self.assertEqual(pretension.select_bolt_diameter(['gu_bolt12_f', 'mbolt8']), 8)

    def test_select_bolt_diameter_not_found(self):
        self.assertIsNone(pretension.select_bolt_diameter(['gu_fixed', 'opora']))
        self.assertEqual(pretension.select_bolt_diameter([], default=10), 10)

    def test_select_bolt_diameter_objects(self):
        names = [_NamedSelection('mbolt10'), _NamedSelection('gu_fixed')]
        self.assertEqual(pretension.select_bolt_diameter(names), 10)


if __name__ == '__main__':
    unittest.main()
