# -*- coding: utf-8 -*-
"""validators.py: проверки конфигов v2 и Named Selections (этап 2).

Схемы взяты из реальных конфигов v2: `contact_settings.json`
(`contact_settings` + `grouping`) и `structure_type_8946.json`.
"""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from Mechanical import validators


def _load_config(*parts):
    """Читает реальный конфиг репозитория (строгий JSON)."""
    path = os.path.join(ROOT, 'config', *parts)
    handle = open(path, 'r')
    try:
        return json.load(handle)
    finally:
        handle.close()


class _NamedSelection(object):
    """Двойник Named Selection с атрибутом Name."""

    def __init__(self, name):
        self.Name = name


class ValidatorsTestCase(unittest.TestCase):
    """Проверки обязательных ключей, NS, сетки, контактов и structure_type."""

    def test_validate_file_exists(self):
        handle = tempfile.NamedTemporaryFile(delete=False)
        try:
            self.assertTrue(validators.validate_file_exists(handle.name))
        finally:
            handle.close()
            os.remove(handle.name)

    def test_validate_file_exists_raises(self):
        missing = os.path.join(tempfile.gettempdir(), 'no_such_file_98765.json')
        self.assertRaises(IOError, validators.validate_file_exists, missing)

    def test_validate_required_keys_ok(self):
        self.assertTrue(validators.validate_required_keys({'a': 1, 'b': 2}, ['a', 'b']))

    def test_validate_required_keys_reports_missing(self):
        try:
            validators.validate_required_keys({'a': 1}, ['a', 'b', 'c'], ' (test)')
        except ValueError as exc:
            self.assertIn('b', str(exc))
            self.assertIn('c', str(exc))
        else:
            self.fail('ValueError не поднят')

    def test_validate_required_keys_none_config(self):
        self.assertRaises(ValueError, validators.validate_required_keys, None, ['a'])

    def test_validate_named_selection_names(self):
        names = ['gu_fixed', 'gu_force']
        self.assertTrue(validators.validate_named_selection('gu_fixed', names))
        self.assertFalse(validators.validate_named_selection('gu_bolt8_f', names))

    def test_validate_named_selection_objects(self):
        objects = [_NamedSelection('gu_fixed'), _NamedSelection('gu_force')]
        self.assertTrue(validators.validate_named_selection('gu_force', objects))
        self.assertFalse(validators.validate_named_selection('gu_remote_disp', objects))

    def test_validate_named_selection_empty_name(self):
        self.assertFalse(validators.validate_named_selection('', ['gu_fixed']))
        self.assertFalse(validators.validate_named_selection(None, ['gu_fixed']))

    def test_validate_mesh_settings_bare_dict(self):
        mesh = {'truba': {'meshCoef': 4.08, 'meshMethod': 'MultiZone',
                          'elementOrder': 'Quadratic'}}
        self.assertTrue(validators.validate_mesh_settings(mesh))

    def test_validate_mesh_settings_v2_wrapper(self):
        self.assertTrue(validators.validate_mesh_settings(
            _load_config('mechanical_configs', 'mesh_config.json')))

    def test_validate_mesh_settings_missing_key(self):
        mesh = {'truba': {'meshCoef': 4.08, 'meshMethod': 'MultiZone'}}
        self.assertRaises(ValueError, validators.validate_mesh_settings, mesh)

    def test_validate_mesh_settings_empty(self):
        self.assertRaises(ValueError, validators.validate_mesh_settings, {})

    def test_validate_contact_settings_pairs_config(self):
        self.assertTrue(validators.validate_contact_settings(
            _load_config('mechanical_configs', 'contact_settings.json')))

    def test_validate_contact_settings_requires_default(self):
        config = {'contact_settings': {'pairs': [{'name': 'a', 'a': ['mbolt'], 'b': ['mgaika'],
                                              'type': 'Bonded'}]}}
        self.assertRaises(ValueError, validators.validate_contact_settings, config)

    def test_validate_contact_settings_rule_missing_type(self):
        config = {'contact_settings': {'pairs': [{'name': 'a', 'a': ['mbolt'], 'b': ['mgaika']}],
                                       'default': {'type': 'Frictional'}}}
        self.assertRaises(ValueError, validators.validate_contact_settings, config)

    def test_validate_contact_settings_unknown_type(self):
        config = {'contact_settings': {'pairs': [{'name': 'a', 'a': ['mbolt'], 'b': ['mgaika'],
                                                   'type': 'Slippery'}],
                                       'default': {'type': 'Frictional'}}}
        self.assertRaises(ValueError, validators.validate_contact_settings, config)

    def test_validate_contact_settings_pair_without_sides(self):
        config = {'contact_settings': {'pairs': [{'name': 'a', 'type': 'Bonded'}],
                                       'default': {'type': 'Frictional'}}}
        self.assertRaises(ValueError, validators.validate_contact_settings, config)

    def test_validate_contact_settings_old_v2_schema_rejected(self):
        # Схема «rules + grouping» заменена парами: старый файл не должен
        # проходить валидацию, иначе правила молча не применятся.
        config = {'contact_settings': {'default': {'type': 'Bonded', 'patterns': ['*']}},
                  'grouping': {'Others': ['default']}}
        self.assertRaises(ValueError, validators.validate_contact_settings, config)

    def test_validate_contact_settings_old_v1_schema_rejected(self):
        # Схема v1 (contact_rules-список) в v2 не принимается — это и есть смысл порта.
        config = {'contact_rules': [{'contact_pattern': '*', 'target_pattern': '*',
                                     'type': 'Frictional',
                                     'detection_method': 'ProgramControlled'}]}
        self.assertRaises(ValueError, validators.validate_contact_settings, config)

    def test_validate_structure_type_config_real_8946(self):
        self.assertTrue(validators.validate_structure_type_config(
            _load_config('structure_type_8946.json')))

    def test_validate_structure_type_config_missing_loads(self):
        config = {'structure_info': {'id': '8946'}, 'boundary_conditions': {}}
        self.assertRaises(ValueError, validators.validate_structure_type_config, config)

    def test_validate_structure_type_config_empty_id(self):
        config = {'structure_info': {'id': ''}, 'loads': {'08': {}},
                  'boundary_conditions': {}}
        self.assertRaises(ValueError, validators.validate_structure_type_config, config)


if __name__ == '__main__':
    unittest.main()
