# -*- coding: utf-8 -*-
"""BoltManager и ResultManager на fake-объектах Mechanical (этап 4).

Проверяется контракт вызовов, а не поведение ANSYS (NFR-6):
``AddBoltPretension`` для ``gu_bolt*_f``, ``AddTotalDeformation``/
``AddEquivalentStress``, запись CSV во временный каталог. Fake-слой повторяет
формы API из RESEARCH-ANSYS-API §3.10-3.11, но не заменяет ручной прогон.
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

from Mechanical.analysis_manager import AnalysisManager
from Mechanical.bolt_manager import BoltManager
from Mechanical.result_manager import ResultManager


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


class FakeNamedSelections(object):
    def __init__(self, names):
        self.Children = [FakeNamedSelection(name) for name in names]


class FakeModel(object):
    def __init__(self, ns_names):
        self.NamedSelections = FakeNamedSelections(ns_names)


class FakeAnalysis(object):
    """Двойник ``Analysis``: болты, шаги, решение."""

    def __init__(self, steps=3, solution=None):
        self.AnalysisSettings = FakeAnalysisSettings(steps)
        self.Solution = solution or FakeSolution()
        self.bolts = []

    def AddBoltPretension(self):
        bolt = FakeBoltPretension()
        self.bolts.append(bolt)
        return bolt


class FakeContext(object):
    """Минимальный ``ProjectContext`` для менеджеров."""

    def __init__(self, ns_names=None, torque=None, steps=3, solution=None,
                 structure_type_id="8946", execution_no="08", analysis=True):
        self.log = FakeLog()
        self.Quantity = FakeQuantity
        self.enums = {"BoltLoadDefineBy": FakeEnums}
        self.model = FakeModel(ns_names or [])
        self.analysis = FakeAnalysis(steps=steps, solution=solution) if analysis else None
        self.configs = {"structure_type": {"torque_nm": torque or {}}}
        self.structure_type_id = structure_type_id
        self.execution_no = execution_no


def _read_text(path):
    handle = io.open(path, "r", encoding="utf-8")
    try:
        return handle.read()
    finally:
        handle.close()


class BoltManagerTestCase(unittest.TestCase):
    """BoltManager: преднатяг по моменту для gu_bolt*_f."""

    def test_creates_pretension_for_gu_bolt_named_selection(self):
        context = FakeContext(ns_names=["gu_fixed", "mbolt8", "gu_bolt8_f"],
                              torque={"8": 11.8}, steps=3)
        BoltManager(context).setup_bolt_pretensions()

        bolts = context.analysis.bolts
        self.assertEqual(len(bolts), 1)
        bolt = bolts[0]
        self.assertEqual(bolt.Name, "Bolt_gu_bolt8_f")
        self.assertEqual(bolt.Location.Name, "gu_bolt8_f")
        # 11.8 / (0.37 * 8 / 1000) = 3986.48... Н (формула из pretension.py, Q6).
        self.assertEqual(len(bolt.Preload.Output.values), 1)
        index, quantity = bolt.Preload.Output.values[0]
        self.assertEqual(index, 0)
        self.assertAlmostEqual(quantity.value, 3986.5, delta=0.1)
        self.assertEqual(quantity.unit, "N")
        self.assertEqual(bolt.define_by_calls, [(2, "LOCK"), (3, "LOCK")])

    def test_one_pretension_per_bolt_named_selection(self):
        context = FakeContext(ns_names=["gu_bolt8_f", "gu_bolt10_f"],
                              torque={"8": 11.8, "10": 18.5}, steps=2)
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual([bolt.Location.Name for bolt in context.analysis.bolts],
                         ["gu_bolt8_f", "gu_bolt10_f"])
        self.assertAlmostEqual(context.analysis.bolts[0].Preload.Output.values[0][1].value,
                               3986.5, delta=0.1)
        self.assertAlmostEqual(context.analysis.bolts[1].Preload.Output.values[0][1].value,
                               5000.0, delta=0.1)

    def test_ignores_named_selections_outside_pattern(self):
        context = FakeContext(ns_names=["gu_fixed", "gu_force", "gu_bolt8"],
                              torque={"8": 11.8})
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(context.analysis.bolts, [])
        self.assertTrue(context.log.has("debug"))

    def test_single_step_has_no_lock_calls(self):
        context = FakeContext(ns_names=["mbolt8", "gu_bolt8_f"],
                              torque={"8": 11.8}, steps=1)
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(len(context.analysis.bolts), 1)
        self.assertEqual(context.analysis.bolts[0].define_by_calls, [])

    def test_missing_diameter_skips_bolts(self):
        context = FakeContext(ns_names=["gu_bolt_f"], torque={"8": 11.8})
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(context.analysis.bolts, [])
        self.assertTrue(context.log.has("warning", "диаметр"))

    def test_missing_torque_skips_bolt(self):
        context = FakeContext(ns_names=["mbolt8", "gu_bolt8_f"], torque={})
        BoltManager(context).setup_bolt_pretensions()

        self.assertEqual(context.analysis.bolts, [])
        self.assertTrue(context.log.has("warning", "Момент затяжки"))

    def test_without_analysis_logs_error_and_returns(self):
        context = FakeContext(ns_names=["mbolt8", "gu_bolt8_f"],
                              torque={"8": 11.8}, analysis=False)
        BoltManager(context).setup_bolt_pretensions()

        self.assertTrue(context.log.has("error"))

    def test_analysis_manager_delegates_and_keeps_no_formula(self):
        # Болтовой код удалён из AnalysisManager: метода нет, вызов идёт через BoltManager.
        self.assertFalse(hasattr(AnalysisManager, "_setup_bolt_pretensions"))
        self.assertFalse(hasattr(AnalysisManager, "_create_bolt_pretension"))


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

    def test_default_export_path_is_under_cwd_results(self):
        solution = FakeSolution()
        context = FakeContext(solution=solution)
        previous = os.getcwd()
        os.chdir(self.tmpdir)
        try:
            path = ResultManager(context).export_results()
        finally:
            os.chdir(previous)

        self.assertEqual(path, os.path.join(self.tmpdir, "results", "results_export.csv"))
        self.assertTrue(os.path.isfile(path))


if __name__ == '__main__':
    unittest.main()
