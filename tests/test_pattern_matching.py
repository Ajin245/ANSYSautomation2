# -*- coding: utf-8 -*-
"""pattern_matching.py: simple_pattern_match, extract_number_from_name (этап 2).

Кейсы — PLAN-MERGE §6.2: `*` в начале/середине/конце, точное совпадение,
`match_any_pattern`, `extract_number_from_name` (`mbolt12`, `opora_15`, `truba245`).
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from Mechanical import pattern_matching as pm


class PatternMatchingTestCase(unittest.TestCase):
    """Сопоставление имён по шаблонам."""

    def test_exact_match(self):
        self.assertTrue(pm.simple_pattern_match('gu_fixed', 'gu_fixed'))
        self.assertFalse(pm.simple_pattern_match('gu_fixed', 'gu_force'))

    def test_star_at_end(self):
        self.assertTrue(pm.simple_pattern_match('gu_bolt12_f', 'gu_bolt*'))
        self.assertFalse(pm.simple_pattern_match('gu_fixed', 'gu_bolt*'))

    def test_star_at_start(self):
        self.assertTrue(pm.simple_pattern_match('gu_bolt12_f', '*_f'))
        self.assertFalse(pm.simple_pattern_match('gu_bolt12', '*_f'))

    def test_star_in_middle(self):
        self.assertTrue(pm.simple_pattern_match('opora_niz', 'opora*iz'))
        self.assertFalse(pm.simple_pattern_match('opora_verh', 'opora*iz'))

    def test_star_all(self):
        self.assertTrue(pm.simple_pattern_match('mbolt8', '*'))

    def test_empty_name_or_pattern(self):
        self.assertFalse(pm.simple_pattern_match('', '*'))
        self.assertFalse(pm.simple_pattern_match('name', ''))
        self.assertFalse(pm.simple_pattern_match(None, '*'))

    def test_match_any_pattern(self):
        patterns = ['*bolt*', '*gaika*']
        self.assertTrue(pm.match_any_pattern('mbolt8', patterns))
        self.assertTrue(pm.match_any_pattern('mgaika10', patterns))
        self.assertFalse(pm.match_any_pattern('opora', patterns))
        self.assertFalse(pm.match_any_pattern('opora', []))

    def test_find_matching_names_preserves_order(self):
        names = ['opora_verh', 'mbolt8', 'mgaika8', 'truba']
        # Один `*`: шаблон делится на префикс и суффикс (ограничение v1).
        found = pm.find_matching_names(names, 'm*')
        self.assertEqual(found, ['mbolt8', 'mgaika8'])
        self.assertEqual(pm.find_matching_names([], '*'), [])

    def test_extract_number_from_name(self):
        self.assertEqual(pm.extract_number_from_name('mbolt12'), ('mbolt', 12.0))
        self.assertEqual(pm.extract_number_from_name('opora_15'), ('opora_', 15.0))
        self.assertEqual(pm.extract_number_from_name('truba245'), ('truba', 245.0))

    def test_extract_number_from_name_decimal(self):
        self.assertEqual(pm.extract_number_from_name('x1.5'), ('x', 1.5))

    def test_extract_number_from_name_without_number(self):
        self.assertIsNone(pm.extract_number_from_name('opora'))
        self.assertIsNone(pm.extract_number_from_name(''))
        self.assertIsNone(pm.extract_number_from_name(None))


if __name__ == '__main__':
    unittest.main()
