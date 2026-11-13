# -*- coding: utf-8 -*-
"""config_merge.py: рекурсивное слияние конфигов (этап 2).

Кейсы — PLAN-MERGE §6.2: вложенное слияние, переопределение, пустой override,
списки, глубокие копии, `None`.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from Mechanical import config_merge


class ConfigMergeTestCase(unittest.TestCase):
    """Слияние конфигов без изменения входных структур."""

    def test_nested_merge_keeps_siblings(self):
        base = {'mesh_settings': {'truba': {'meshCoef': 4.0, 'elementOrder': 'Quadratic'}},
                'project': {'name': 'base'}}
        override = {'mesh_settings': {'truba': {'meshCoef': 6.0}}}
        merged = config_merge.merge_configs(base, override)

        self.assertEqual(merged['mesh_settings']['truba']['meshCoef'], 6.0)
        self.assertEqual(merged['mesh_settings']['truba']['elementOrder'], 'Quadratic')
        self.assertEqual(merged['project']['name'], 'base')

    def test_override_adds_new_key(self):
        merged = config_merge.merge_configs({'a': 1}, {'b': 2})
        self.assertEqual(merged, {'a': 1, 'b': 2})

    def test_scalar_override(self):
        merged = config_merge.merge_configs({'a': 1, 'b': 2}, {'b': 3})
        self.assertEqual(merged, {'a': 1, 'b': 3})

    def test_empty_override_returns_copy(self):
        base = {'a': {'b': 1}}
        for override in ({}, None):
            merged = config_merge.merge_configs(base, override)
            self.assertEqual(merged, base)
            self.assertIsNot(merged, base)

    def test_none_base(self):
        self.assertEqual(config_merge.merge_configs(None, {'a': 1}), {'a': 1})
        self.assertEqual(config_merge.merge_configs(None, None), {})

    def test_lists_are_replaced_not_merged(self):
        base = {'load_factors': [0.5, 1.0, 1.5], 'patterns': ['a', 'b']}
        override = {'load_factors': [1.0]}
        merged = config_merge.merge_configs(base, override)

        self.assertEqual(merged['load_factors'], [1.0])
        self.assertEqual(merged['patterns'], ['a', 'b'])

    def test_deep_copy_of_nested_structures(self):
        base = {'groups': {'Bonded': ['shov']}}
        merged = config_merge.merge_configs(base, {})
        merged['groups']['Bonded'].append('truba')

        self.assertEqual(base['groups']['Bonded'], ['shov'])

    def test_override_structure_is_not_aliased(self):
        override = {'groups': {'Bonded': ['shov']}}
        merged = config_merge.merge_configs({}, override)
        merged['groups']['Bonded'].append('mbolt')

        self.assertEqual(override['groups']['Bonded'], ['shov'])

    def test_base_input_is_not_modified(self):
        base = {'a': {'b': 1}}
        config_merge.merge_configs(base, {'a': {'b': 2, 'c': 3}})
        self.assertEqual(base, {'a': {'b': 1}})


if __name__ == '__main__':
    unittest.main()
