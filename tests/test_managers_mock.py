# -*- coding: utf-8 -*-
"""Менеджеры на fake-объектах Mechanical (этапы 4–6).

Проверяется контракт вызовов, а не поведение ANSYS (NFR-6):
``AddBoltPretension`` для ``gu_bolt*_f``, ``AddRemoteDisplacement`` для
строкового и словарного ``remote_displacement`` (FR-6), ``RenameBasedOnDefinition``
и ``Tree.Group`` контактов, ``AddSizing``/``AddAutomaticMethod`` сетки,
``AddTotalDeformation``/``AddEquivalentStress`` и запись CSV. Fake-слой
повторяет формы API из RESEARCH-ANSYS-API §3.10-3.11, но не заменяет ручной
прогон.
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

from Mechanical.analysis_manager import AnalysisManager, parse_remote_displacement
from Mechanical.bolt_manager import BoltManager
from Mechanical.contact_manager import ContactManager
from Mechanical.mesh_manager import MeshManager
from Mechanical.result_manager import (ResultManager, RESULTS_PATH_ENV,
                                         resolve_export_path)


class FakeLog(object):
    """Лог в список: тест может проверить уровень и текст сообщения."""

    def __init__(self):
        self.messages = []

    def _add(self, level, message):
        self.messages.append((level, message))

    def info(self, message):
        self._add("info", message)

    def warning(self, message):
        self._add("warning", message)

    def error(self, message):
        self._add("error", message)

    def debug(self, message):
        self._add("debug", message)

    def has(self, level, fragment=None):
        for message_level, message in self.messages:
            if message_level == level and (fragment is None or fragment in message):
                return True
        return False


class FakeQuantity(object):
    """Двойник ``Ansys.Core.Units.Quantity``."""

    def __init__(self, value, unit):
        self.value = value
        self.unit = unit


class FakeEnums(object):
    """Двойник ``BoltLoadDefineBy``: важны только используемые поля."""

    Lock = "LOCK"
    Load = "LOAD"


class FakeDiscreteOutput(object):
    """``Preload.Output``: хранит пары (индекс, Quantity)."""

    def __init__(self):
        self.values = []

    def SetDiscreteValue(self, index, quantity):
        self.values.append((index, quantity))


class FakePreload(object):
    def __init__(self):
        self.Output = FakeDiscreteOutput()


class FakeBoltPretension(object):
    """Двойник объекта ``BoltPretension``."""

    def __init__(self):
        self.Name = None
        self.Location = None
        self.Preload = FakePreload()
        self.define_by_calls = []

    def SetDefineBy(self, step, define_by):
        self.define_by_calls.append((step, define_by))


class FakeAnalysisSettings(object):
    def __init__(self, steps=3):
        self.NumberOfSteps = steps


class FakeDiscreteInput(object):
    """``Inputs[0]``: хранит присвоенный ``DiscreteValues``."""

    def __init__(self):
        self.DiscreteValues = None


class FakeComponent(object):
    """Компонент ``remote``: ``Inputs[0]`` и ``Output``."""

    def __init__(self):
        self.Inputs = [FakeDiscreteInput()]
        self.Output = FakeDiscreteInput()


class FakeRemoteDisplacement(object):
    """Двойник объекта ``RemoteDisplacement``."""

    def __init__(self):
        self.Name = None
        self.Location = None
        self.RotationX = FakeComponent()
        self.RotationY = FakeComponent()
        self.RotationZ = FakeComponent()
        self.XComponent = FakeComponent()
        self.YComponent = FakeComponent()
        self.ZComponent = FakeComponent()


class FakeFixedSupport(object):
    def __init__(self):
        self.Name = None
        self.Location = None


class FakeResult(object):
    """Двойник результата ``Solution``: ``Name``, ``Unit``, ``PlotData``."""

    def __init__(self, name=None, unit=None, plot_data=None):
        self.Name = name
        self.Unit = unit
        self.PlotData = plot_data


class FakeSolution(object):
    """Двойник ``Solution``: дочерние результаты и фабрики результатов."""

    def __init__(self, children=None):
        self.Children = list(children or [])
        self.created = []

    def AddTotalDeformation(self):
        result = FakeResult()
        self.created.append(result)
        return result

    def AddEquivalentStress(self):
        result = FakeResult()
        self.created.append(result)
        return result


class FakeNamedSelection(object):
    def __init__(self, name):
        self.Name = name


class FakeCollection(list):
    """Список в форме ANSYS-коллекции: ``Children`` с ``Count`` (MeshManager)."""

    @property
    def Count(self):
        return len(self)


class FakeNamedSelections(object):
    def __init__(self, names):
        self.Children = FakeCollection(FakeNamedSelection(name) for name in names)


class FakeSizing(object):
    def __init__(self):
        self.Name = None
        self.Location = None
        self.ElementSize = None


class FakeMethod(object):
    def __init__(self):
        self.Name = None
        self.Location = None
        self.Method = None
        self.Algorithm = None
        self.ElementOrder = None
        self.SurfaceMeshMethod = None
        self.FreeMeshType = None


class FakeMesh(object):
    """Двойник ``Model.Mesh``: фабрики Sizing и AutomaticMethod."""

    def __init__(self):
        self.sizings = []
        self.methods = []

    def AddSizing(self):
        sizing = FakeSizing()
        self.sizings.append(sizing)
        return sizing

    def AddAutomaticMethod(self):
        method = FakeMethod()
        self.methods.append(method)
        return method


class FakeGroup(object):
    def __init__(self, objects):
        self.Objects = list(objects)
        self.Name = None


class FakeTree(object):
    """Двойник ``ExtAPI.DataModel.Tree``: ``Group`` запоминает вызовы."""

    def __init__(self):
        self.groups = []

    def Group(self, objects):
        group = FakeGroup(objects)
        self.groups.append(group)
        return group


class FakeDataModel(object):
    def __init__(self):
        self.Tree = FakeTree()


class FakeExtApi(object):
    def __init__(self):
        self.DataModel = FakeDataModel()


class _EnumMember(object):
    """Элемент перечисления Mechanical: сравним по имени."""

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return isinstance(other, _EnumMember) and other.name == self.name

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "EnumMember({0})".format(self.name)


class FakeContactType(_EnumMember):
    """``contact.ContactType``: у элемента есть доступ к членам класса."""


FakeContactType.Bonded = FakeContactType("Bonded")
FakeContactType.Frictional = FakeContactType("Frictional")
FakeContactType.Frictionless = FakeContactType("Frictionless")


class FakeInterfaceTreatment(_EnumMember):
    """``contact.InterfaceTreatment``: AdjustToTouch / AddOffsetNoRamping / Offset."""


FakeInterfaceTreatment.AdjustToTouch = FakeInterfaceTreatment("AdjustToTouch")
FakeInterfaceTreatment.AddOffsetNoRamping = FakeInterfaceTreatment("AddOffsetNoRamping")
FakeInterfaceTreatment.Offset = FakeInterfaceTreatment("Offset")


class FakeCategory(object):
    def __init__(self, name):
        self.name = name

    def ToString(self):
        return self.name


class FakeContact(object):
    """Двойник ``ContactRegion``: переименование и параметры контакта."""

    def __init__(self, name):
        self.Name = name
        self.DataModelObjectCategory = FakeCategory("ContactRegion")
        self.ContactType = FakeContactType.Bonded
        self.InterfaceTreatment = FakeInterfaceTreatment.AdjustToTouch
        self.FrictionCoefficient = None
        self.rename_calls = 0

    def RenameBasedOnDefinition(self):
        self.rename_calls += 1


class FakeContactGroup(object):
    def __init__(self, contacts):
        self.DataModelObjectCategory = FakeCategory("ConnectionGroup")
        self.Children = list(contacts)


class FakeConnections(object):
    def __init__(self, contacts):
        self.Children = [FakeContactGroup(contacts)] if contacts else []


class FakeBody(object):
    """Двойник тела геометрии: имя и категория (болты ``mbolt<d>``)."""

    DataModelObjectCategory = "Body"

    def __init__(self, name):
        self.Name = name
        self.Volume = 1.0
        self.Material = "Structural Steel"


class FakeBodyGroup(object):
    """Двойник группы/сборки дерева геометрии: только Children."""

    DataModelObjectCategory = "Part"

    def __init__(self, children=None):
        self.Children = FakeCollection(children or [])


class FakeGeometry(object):
    def __init__(self, bodies=None, groups=None):
        items = [FakeBody(name) for name in (bodies or [])]
        items.extend(groups or [])
        self.Children = FakeCollection(items)


class FakeForce(object):
    """Двойник объекта ``Force``: компоненты X/Y/Z и ``Location``."""

    def __init__(self):
        self.Name = None
        self.Location = None
        self.DefineBy = None
        self.XComponent = FakeComponent()
        self.YComponent = FakeComponent()
        self.ZComponent = FakeComponent()


class FakeModel(object):
    def __init__(self, ns_names, contacts=None, bodies=None, groups=None):
        self.NamedSelections = FakeNamedSelections(ns_names)
        self.Mesh = FakeMesh()
        self.Connections = FakeConnections(contacts or [])
        self.Geometry = FakeGeometry(bodies or [], groups or [])


class FakeAnalysis(object):
    """Двойник ``Analysis``: болты, шаги, решение."""

    def __init__(self, steps=3, solution=None):
        self.AnalysisSettings = FakeAnalysisSettings(steps)
        self.Solution = solution or FakeSolution()
        self.bolts = []
        self.remote_displacements = []
        self.fixed_supports = []
        self.forces = []

    def AddForce(self):
        force = FakeForce()
        self.forces.append(force)
        return force

    def AddBoltPretension(self):
        bolt = FakeBoltPretension()
        self.bolts.append(bolt)
        return bolt

    def AddRemoteDisplacement(self):
        remote = FakeRemoteDisplacement()
        self.remote_displacements.append(remote)
        return remote

    def AddFixedSupport(self):
        support = FakeFixedSupport()
        self.fixed_supports.append(support)
        return support


class FakeMethodType(object):
    Sweep = "Sweep"
    MultiZone = "MultiZone"


class FakeMeshMethodAlgorithm(object):
    Axisymmetric = "Axisymmetric"


class FakeElementOrder(object):
    Linear = "Linear"
    Quadratic = "Quadratic"
    ProgramControlled = "ProgramControlled"


class FakeContext(object):
    """Минимальный ``ProjectContext`` для менеджеров.

    ``configs`` собирается только из переданных секций: отсутствующий ключ —
    такой же контракт, как у настоящего ``ProjectContext`` (``None`` вместо
    ``project_settings`` уронил бы ``MeshManager``).
    """

    def __init__(self, ns_names=None, torque=None, steps=3, solution=None,
                 structure_type_id="8946", execution_no="08", analysis=True,
                 boundary_conditions=None, contact_settings=None,
                 mesh_config=None, project_settings=None, contacts=None,
                 bodies=None, loads=None, bolt_pretension=None,
                 analysis_scenarios=None, body_groups=None):
        self.log = FakeLog()
        self.Quantity = FakeQuantity
        self.enums = {
            "BoltLoadDefineBy": FakeEnums,
            "MethodType": FakeMethodType,
            "MeshMethodAlgorithm": FakeMeshMethodAlgorithm,
            "ElementOrder": FakeElementOrder,
        }
        self.model = FakeModel(ns_names or [], contacts=contacts, bodies=bodies,
                               groups=body_groups)
        self.analysis = FakeAnalysis(steps=steps, solution=solution) if analysis else None
        self.ext_api = FakeExtApi()
        structure_type = {
            "loads": loads if loads is not None else {
                execution_no or "08": {
                    "cases": {
                        "НУЭ": {"fx": 1000, "fy": 1700, "fz": -3300},
                        "НУЭ+ПЗ": {"fx": 1500, "fy": 2550, "fz": -4950},
                    }
                }
            }
        }
        if torque is not None:
            # Устаревший источник преднатяга: оставлен, чтобы тесты могли
            # проверить, что он больше не используется.
            structure_type["torque_nm"] = torque
        if boundary_conditions is not None:
            structure_type["boundary_conditions"] = boundary_conditions
        self.configs = {"structure_type": structure_type}
        if bolt_pretension is not None:
            self.configs["bolt_pretension"] = bolt_pretension
        if analysis_scenarios is not None:
            self.configs["analysis_scenarios"] = analysis_scenarios
        if contact_settings is not None:
            self.configs["contact_settings"] = contact_settings
        if mesh_config is not None:
            self.configs["mesh_config"] = mesh_config
        if project_settings is not None:
            self.configs["project_settings"] = project_settings
        self.structure_type_id = structure_type_id
        self.execution_no = execution_no


def _read_text(path):
    handle = io.open(path, "r", encoding="utf-8")
    try:
        return handle.read()
    finally:
        handle.close()


class BoltManagerTestCase(unittest.TestCase):
    """BoltManager: преднатяг по таблице болтов для тел ``mbolt*``."""

    BOLT_CONFIG = {
        "default": {"pretension_n": 31532, "torque_nm": 350},
        "by_diameter_mm": {
            "8": {"thread": "M8", "torque_nm": 6, "pretension_n": 2027},
            "10": {"thread": "M10", "torque_nm": 9, "pretension_n": 2432},
        },
    }

    def test_creates_pretension_when_bolt_bodies_present(self):
        context = FakeContext(ns_names=["gu_fixed", "gu_bolt1_f"],
                              bodies=["opora", "mbolt8"],
                              bolt_pretension=self.BOLT_CONFIG, steps=3)
        BoltManager(context).setup_bolt_pretensions()

        bolts = context.analysis.bolts
        self.assertEqual(len(bolts), 1)
        bolt = bolts[0]
        self.assertEqual(bolt.Name, "Bolt_gu_bolt1_f")
        self.assertEqual(bolt.Location.Name, "gu_bolt1_f")
        index, quantity = bolt.Preload.Output.values[0]
        self.assertEqual(index, 0)
        self.assertAlmostEqual(quantity.value, 2027.0, delta=0.1)
        self.assertEqual(quantity.unit, "N")
        self.assertEqual(bolt.define_by_calls, [(2, "LOCK"), (3, "LOCK")])

    def test_finds_bolt_body_inside_group(self):
        group = FakeBodyGroup([FakeBody("mbolt10")])
        context = FakeContext(ns_names=["gu_bolt1_f"], body_groups=[group],
                              bolt_pretension=self.BOLT_CONFIG, steps=2)
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(len(context.analysis.bolts), 1)
        quantity = context.analysis.bolts[0].Preload.Output.values[0][1]
        self.assertAlmostEqual(quantity.value, 2432.0, delta=0.1)

    def test_group_name_is_not_treated_as_body(self):
        group = FakeBodyGroup([FakeBody("truba42")])
        context = FakeContext(ns_names=["gu_bolt1_f"], body_groups=[group],
                              bolt_pretension=self.BOLT_CONFIG)
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(context.analysis.bolts, [])
        self.assertTrue(context.log.has("warning", "mbolt"))

    def test_uses_default_when_diameter_not_in_table(self):
        context = FakeContext(ns_names=["gu_bolt1_f"], bodies=["mbolt33"],
                              bolt_pretension=self.BOLT_CONFIG, steps=2)
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(len(context.analysis.bolts), 1)
        quantity = context.analysis.bolts[0].Preload.Output.values[0][1]
        self.assertAlmostEqual(quantity.value, 31532.0, delta=0.1)

    def test_no_bolt_bodies_logs_warning(self):
        context = FakeContext(ns_names=["gu_bolt1_f"], bodies=["opora", "truba88"],
                              bolt_pretension=self.BOLT_CONFIG)
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(context.analysis.bolts, [])
        self.assertTrue(context.log.has("warning", "mbolt"))

    def test_no_bolt_named_selection_logs_warning(self):
        context = FakeContext(ns_names=["gu_fixed", "gu_force"], bodies=["mbolt8"],
                              bolt_pretension=self.BOLT_CONFIG)
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(context.analysis.bolts, [])
        self.assertTrue(context.log.has("warning", "gu_bolt"))

    def test_multiple_diameters_logs_warning(self):
        context = FakeContext(ns_names=["gu_bolt1_f"], bodies=["mbolt8", "mbolt10"],
                              bolt_pretension=self.BOLT_CONFIG)
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(context.analysis.bolts, [])
        self.assertTrue(context.log.has("warning", "диаметр"))

    def test_without_bolt_config_logs_warning(self):
        context = FakeContext(ns_names=["gu_bolt1_f"], bodies=["mbolt8"],
                              torque={"8": 11.8})
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(context.analysis.bolts, [])
        self.assertTrue(context.log.has("warning", "затяжки"))

    def test_single_step_has_no_lock_calls(self):
        context = FakeContext(ns_names=["gu_bolt1_f"], bodies=["mbolt8"],
                              bolt_pretension=self.BOLT_CONFIG, steps=1)
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(len(context.analysis.bolts), 1)
        self.assertEqual(context.analysis.bolts[0].define_by_calls, [])

    def test_without_analysis_logs_error_and_returns(self):
        context = FakeContext(ns_names=["gu_bolt1_f"], bodies=["mbolt8"],
                              bolt_pretension=self.BOLT_CONFIG, analysis=False)
        BoltManager(context).setup_bolt_pretensions()

        self.assertTrue(context.log.has("error"))

    def test_analysis_manager_delegates_and_keeps_no_formula(self):
        # Болтовой код удалён из AnalysisManager: метода нет, вызов идёт через BoltManager.
        self.assertFalse(hasattr(AnalysisManager, "_setup_bolt_pretensions"))
        self.assertFalse(hasattr(AnalysisManager, "_create_bolt_pretension"))


class LoadsTestCase(unittest.TestCase):
    """Нагрузки: шаги из cases + промежуточный разгон для сходимости."""

    def test_ramp_adds_intermediate_step(self):
        context = FakeContext(ns_names=["gu_fixed", "gu_force"], steps=3,
                              analysis_scenarios={"standard_sequence": {"ramp_factor": 0.5}})
        AnalysisManager(context).apply_boundary_conditions_and_loads()

        self.assertEqual(context.analysis.AnalysisSettings.NumberOfSteps, 3)
        force = context.analysis.forces[0]
        values = [quantity.value for quantity in force.XComponent.Output.DiscreteValues]
        self.assertEqual(values, [500.0, 1000.0, 1500.0])
        fz_values = [quantity.value for quantity in force.ZComponent.Output.DiscreteValues]
        self.assertEqual(fz_values, [-1650.0, -3300.0, -4950.0])

    def test_without_ramp_two_steps(self):
        context = FakeContext(ns_names=["gu_fixed", "gu_force"], steps=3)
        AnalysisManager(context).apply_boundary_conditions_and_loads()

        self.assertEqual(context.analysis.AnalysisSettings.NumberOfSteps, 2)
        force = context.analysis.forces[0]
        self.assertEqual([quantity.value for quantity in force.XComponent.Output.DiscreteValues],
                         [1000.0, 1500.0])

    def test_missing_loads_raises(self):
        context = FakeContext(ns_names=["gu_fixed", "gu_force"], steps=2,
                              execution_no="99",
                              loads={"08": {"cases": {"НУЭ": {"fx": 1, "fy": 1, "fz": -1}}}})
        with self.assertRaises(ValueError):
            AnalysisManager(context).apply_boundary_conditions_and_loads()

    def test_missing_force_named_selection_raises(self):
        context = FakeContext(ns_names=["gu_fixed"], steps=2)
        with self.assertRaises(ValueError):
            AnalysisManager(context).apply_boundary_conditions_and_loads()


class RemoteDisplacementTestCase(unittest.TestCase):
    """FR-6: ``remote_displacement`` строкой (8946) и словарём."""

    def _context(self, remote_config, ns_names=None):
        return FakeContext(ns_names=ns_names or ["gu_fixed", "gu_force", "gu_remote_disp"],
                           boundary_conditions={"fixed_support": "gu_fixed",
                                                "remote_displacement": remote_config})

    def test_string_value_adds_remote_displacement(self):
        # Значение ровно из config/structure_type_8946.json:39-42.
        context = self._context("gu_remote_disp")

        AnalysisManager(context).apply_boundary_conditions_and_loads()

        remotes = context.analysis.remote_displacements
        self.assertEqual(len(remotes), 1)
        self.assertEqual(remotes[0].Name, "RemoteDisp_gu_remote_disp")
        self.assertEqual(remotes[0].Location.Name, "gu_remote_disp")
        self.assertTrue(context.log.has("info", "gu_remote_disp"))

    def test_string_value_does_not_set_step_values(self):
        context = self._context("gu_remote_disp")

        AnalysisManager(context).apply_boundary_conditions_and_loads()

        remote = context.analysis.remote_displacements[0]
        self.assertIsNone(remote.XComponent.Output.DiscreteValues)
        self.assertIsNone(remote.RotationX.Output.DiscreteValues)

    def test_dict_value_keeps_rotation_and_translation(self):
        context = self._context({
            "ns_name": "gu_remote_disp",
            "rotation": {"rx": 0.1},
            "translation": {"uz": 2.0},
        })

        AnalysisManager(context).apply_boundary_conditions_and_loads()

        remote = context.analysis.remote_displacements[0]
        self.assertEqual(remote.Location.Name, "gu_remote_disp")
        # Шагов столько, сколько режимов в конфиге: НУЭ + НУЭ+ПЗ -> точки 0..2.
        self.assertEqual(len(remote.RotationX.Output.DiscreteValues), 3)
        self.assertEqual(remote.RotationX.Output.DiscreteValues[0].value, 0.1)
        self.assertEqual(remote.RotationX.Output.DiscreteValues[0].unit, "rad")
        self.assertEqual(len(remote.ZComponent.Output.DiscreteValues), 3)
        self.assertEqual(remote.ZComponent.Output.DiscreteValues[0].value, 2.0)
        self.assertEqual(remote.ZComponent.Output.DiscreteValues[0].unit, "mm")
        self.assertIsNone(remote.YComponent.Output.DiscreteValues)

    def test_missing_named_selection_logs_warning_without_remote(self):
        context = FakeContext(ns_names=["gu_fixed", "gu_force"],
                              boundary_conditions={"remote_displacement": "gu_remote_disp"})

        AnalysisManager(context).apply_boundary_conditions_and_loads()

        self.assertEqual(context.analysis.remote_displacements, [])
        self.assertTrue(context.log.has("warning", "gu_remote_disp"))

    def test_invalid_value_raises(self):
        context = self._context(42)

        self.assertRaises(ValueError, AnalysisManager(context).apply_boundary_conditions_and_loads)

    def test_parse_string_returns_name_and_empty_settings(self):
        self.assertEqual(parse_remote_displacement(" gu_remote_disp "), ("gu_remote_disp", {}))

    def test_parse_dict_returns_settings(self):
        config = {"ns_name": "gu_remote_disp", "translation": {"uz": 1.0}}
        self.assertEqual(parse_remote_displacement(config), ("gu_remote_disp", config))

    def test_parse_rejects_empty_string_and_foreign_types(self):
        for value in ("", "   ", 0, [], object(), None):
            self.assertRaises(ValueError, parse_remote_displacement, value)


class ContactManagerTestCase(unittest.TestCase):
    """ContactManager: ``RenameBasedOnDefinition`` и группировка ``Tree.Group``."""

    CONTACT_SETTINGS = {
        "contact_settings": {
            "shov": {"type": "Bonded", "patterns": ["shov"],
                     "interface_treatment": "AdjustToTouch"},
            "mbolt_offset": {"type": "Frictional", "patterns": ["mbolt"],
                             "interface_treatment": "AddOffsetNoRamping"},
            "default_frictional": {"type": "Frictional", "patterns": ["*"],
                                   "friction_coefficient": 0.3,
                                   "interface_treatment": "AdjustToTouch"},
        },
    }

    def test_renames_every_contact_region(self):
        contacts = [FakeContact("shov_truba"), FakeContact("mbolt_mgaika")]
        context = FakeContext(contacts=contacts, contact_settings=self.CONTACT_SETTINGS)

        ContactManager(context).setup_contacts()

        self.assertEqual([contact.rename_calls for contact in contacts], [1, 1])

    def test_groups_contacts_by_type(self):
        bonded = FakeContact("shov_truba")
        offset = FakeContact("mbolt_mgaika")
        context = FakeContext(contacts=[bonded, offset],
                              contact_settings=self.CONTACT_SETTINGS)

        ContactManager(context).setup_contacts()

        groups = {group.Name: group.Objects
                  for group in context.ext_api.DataModel.Tree.groups}
        self.assertEqual(groups["Bonded"], [bonded])
        self.assertEqual(groups["Offset"], [offset])

    def test_bonded_rule_sets_contact_type(self):
        contact = FakeContact("shov_truba")
        context = FakeContext(contacts=[contact], contact_settings=self.CONTACT_SETTINGS)

        ContactManager(context).setup_contacts()

        self.assertEqual(contact.ContactType, FakeContactType.Bonded)
        self.assertEqual(contact.InterfaceTreatment, FakeInterfaceTreatment.AdjustToTouch)


class MeshManagerTestCase(unittest.TestCase):
    """MeshManager: ``AddSizing``, ``AddAutomaticMethod`` и группировка."""

    MESH_CONFIG = {
        "mesh_settings": {
            "truba": {"meshCoef": 6.0, "meshMethod": "MultiZone",
                      "elementOrder": "Quadratic"},
        },
    }

    def test_adds_sizing_for_matched_named_selection(self):
        context = FakeContext(ns_names=["truba245"], mesh_config=self.MESH_CONFIG,
                              project_settings={"units": {"length": "mm"}})

        MeshManager(context).apply_mesh_settings()

        sizings = context.model.Mesh.sizings
        self.assertEqual(len(sizings), 1)
        self.assertEqual(sizings[0].Name, "Sizing_truba245")
        self.assertEqual(sizings[0].Location.Name, "truba245")
        # 245 / 6.0 = 40.83 мм (округление до 2 знаков, как в менеджере).
        self.assertEqual(sizings[0].ElementSize.value, 40.83)
        self.assertEqual(sizings[0].ElementSize.unit, "mm")

    def test_adds_automatic_method_with_config(self):
        context = FakeContext(ns_names=["truba245"], mesh_config=self.MESH_CONFIG,
                              project_settings={"units": {"length": "mm"}})

        MeshManager(context).apply_mesh_settings()

        methods = context.model.Mesh.methods
        self.assertEqual(len(methods), 1)
        self.assertEqual(methods[0].Name, "Method_MultiZone_truba245")
        self.assertEqual(methods[0].Method, "MultiZone")
        self.assertEqual(methods[0].ElementOrder, "Quadratic")

    def test_skips_gu_named_selections(self):
        context = FakeContext(ns_names=["gu_force"], mesh_config=self.MESH_CONFIG,
                              project_settings={"units": {"length": "mm"}})

        MeshManager(context).apply_mesh_settings()

        self.assertEqual(context.model.Mesh.sizings, [])
        self.assertEqual(context.model.Mesh.methods, [])

    def test_applies_sizing_to_body_without_named_selection(self):
        # Труба приходит без NS: размер сетки задаётся на само тело.
        context = FakeContext(ns_names=[], bodies=["truba42 1", "truba42 2"],
                              mesh_config=self.MESH_CONFIG,
                              project_settings={"units": {"length": "mm"}})

        MeshManager(context).apply_mesh_settings()

        sizings = context.model.Mesh.sizings
        self.assertEqual(len(sizings), 2)
        self.assertEqual(sizings[0].Name, "Sizing_truba42")
        # 42 / 6.0 = 7.0 мм — число берётся из имени тела, индекс " 1" отброшен.
        self.assertEqual(sizings[0].ElementSize.value, 7.0)

    def test_body_with_named_selection_is_not_duplicated(self):
        context = FakeContext(ns_names=["truba42"], bodies=["truba42 1"],
                              mesh_config=self.MESH_CONFIG,
                              project_settings={"units": {"length": "mm"}})

        MeshManager(context).apply_mesh_settings()

        self.assertEqual(len(context.model.Mesh.sizings), 1)

    def test_groups_sizing_and_method_in_tree(self):
        context = FakeContext(ns_names=["truba245"], mesh_config=self.MESH_CONFIG,
                              project_settings={"units": {"length": "mm"}})

        MeshManager(context).apply_mesh_settings()

        groups = {group.Name: group.Objects
                  for group in context.ext_api.DataModel.Tree.groups}
        self.assertEqual(groups["Sizing"], context.model.Mesh.sizings)
        self.assertEqual(groups["Method"], context.model.Mesh.methods)


class ResultManagerTestCase(unittest.TestCase):
    """ResultManager: объекты результатов и реальная запись CSV."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="managers-mock-")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_setup_plot_results_adds_deformation_and_stress(self):
        solution = FakeSolution()
        context = FakeContext(solution=solution)
        ResultManager(context).setup_plot_results()

        self.assertEqual(len(solution.created), 2)
        names = [result.Name for result in solution.created]
        self.assertIn("Total Deformation", names)
        self.assertIn("Equivalent Stress", names)

    def test_export_results_writes_csv_file(self):
        solution = FakeSolution(children=[
            FakeResult(name="Total Deformation", unit="mm",
                       plot_data=[{"Body": "truba", "Value": 0.12, "LoadStep": 1}]),
        ])
        context = FakeContext(solution=solution)
        path = os.path.join(self.tmpdir, "results.csv")

        result_path = ResultManager(context).export_results(path)

        self.assertEqual(result_path, path)
        self.assertTrue(os.path.isfile(path))
        lines = _read_text(path).splitlines()
        self.assertEqual(lines[0],
                         "structure_id,execution,load_step,result_name,body,value,unit")
        self.assertEqual(lines[1], "8946,08,1,Total Deformation,truba,0.12,mm")

    def test_export_results_without_results_writes_header_only(self):
        context = FakeContext(solution=FakeSolution())
        path = os.path.join(self.tmpdir, "empty.csv")

        ResultManager(context).export_results(path)

        lines = _read_text(path).splitlines()
        self.assertEqual(lines, ["structure_id,execution,load_step,result_name,"
                                 "body,value,unit"])

    def test_export_results_survives_unsupported_plot_data(self):
        solution = FakeSolution(children=[
            FakeResult(name="Total Deformation", unit="mm", plot_data=42),
        ])
        context = FakeContext(solution=solution)
        path = os.path.join(self.tmpdir, "unsupported.csv")

        self.assertEqual(ResultManager(context).export_results(path), path)
        self.assertTrue(context.log.has("warning", "PlotData"))
        self.assertEqual(len(_read_text(path).splitlines()), 1)

    def test_export_results_without_analysis_still_writes_header(self):
        context = FakeContext(analysis=False)
        path = os.path.join(self.tmpdir, "no-analysis.csv")

        self.assertEqual(ResultManager(context).export_results(path), path)
        self.assertTrue(context.log.has("warning", "Анализ не найден"))

    def test_default_export_path_is_project_results_csv(self):
        # Имя по умолчанию — results.csv (PLAN-MERGE §1.2, §4.7), не results_export.csv.
        context = FakeContext(solution=FakeSolution())

        path = resolve_export_path(context)

        self.assertEqual(os.path.basename(path), "results.csv")
        self.assertEqual(os.path.basename(os.path.dirname(path)), "results")

    def test_env_var_overrides_export_path(self):
        path = os.path.join(self.tmpdir, "custom.csv")
        os.environ[RESULTS_PATH_ENV] = path
        try:
            context = FakeContext(solution=FakeSolution())
            written = ResultManager(context).export_results()
        finally:
            del os.environ[RESULTS_PATH_ENV]

        self.assertEqual(written, path)
        self.assertTrue(os.path.isfile(path))

    def test_config_sets_export_path(self):
        path = os.path.join(self.tmpdir, "configured.csv")
        context = FakeContext(solution=FakeSolution(),
                              project_settings={"output": {"results_csv": path}})

        self.assertEqual(ResultManager(context).export_results(), path)
        self.assertTrue(os.path.isfile(path))


if __name__ == '__main__':
    unittest.main()
