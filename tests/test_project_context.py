# -*- coding: utf-8 -*-
"""ProjectContext на fake ExtAPI/DataModel/JavaScriptSerializer (этап 3).

Проверяется контракт, а не поведение ANSYS (RESEARCH-ANSYS-API §6.2):
fake-модули ``clr``/``System`` подменяют .NET, ``JavaScriptSerializer`` читает
реальные файлы конфигов через ``json.loads``. Shim'ы ``unicode``/``basestring``
и ``Py2Dict.iteritems`` нужны, чтобы продуктовый код Python 2.7 исполнялся под
Python 3 без правок в ``src/``.

Кейсы — PLAN-MERGE §4.4 и §6.2: идентификация проекта/исполнения, 4 общих
конфига + конфиг конструкции, read-only ``configs["merged"]``, fallback на
шаблоны v1, ``ValueError`` при отсутствии конфига, срабатывание ``validators``.
"""

import builtins
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# --- shim'ы Python 2.7 -------------------------------------------------------
if not hasattr(builtins, "unicode"):
    builtins.unicode = str
if not hasattr(builtins, "basestring"):
    builtins.basestring = str


# --- двойники .NET-структур --------------------------------------------------
class Py2Dict(dict):
    """Словарь с py2-методами: продуктовый код может звать ``.iteritems()``."""

    def iteritems(self):
        return iter(self.items())

    def iterkeys(self):
        return iter(self.keys())

    def itervalues(self):
        return iter(self.values())


class NetList(object):
    """Двойник .NET-коллекции: ``Count``/``GetEnumerator`` + итерация."""

    def __init__(self, values):
        self._values = [_wrap(value) for value in values]

    @property
    def Count(self):
        return len(self._values)

    def GetEnumerator(self):
        return iter(self._values)

    def __iter__(self):
        return iter(self._values)

    def __getitem__(self, index):
        return self._values[index]


def _wrap(value):
    """JSON-значение -> .NET-подобный объект (словари остаются py2-словарями)."""
    if isinstance(value, dict):
        return _as_py2_dict(value)
    if isinstance(value, list):
        return [_wrap(item) for item in value]
    return value


def _as_py2_dict(data):
    result = Py2Dict()
    for key, value in data.items():
        result[key] = _wrap(value)
    return result


class NetDict(object):
    """Двойник .NET-словаря верхнего уровня: ``Keys``/``Item``.

    Вложенные словари приходят как ``Py2Dict`` — так ``_convert_to_py``
    проходит обе ветви: .NET-словарь верхнего уровня и уже python-объект.
    Массивы верхнего уровня отдаются как ``NetList`` (.NET-коллекция с
    ``Count``/``GetEnumerator``), чтобы конвертация списков тоже проверялась.
    """

    def __init__(self, data):
        self._data = _as_py2_dict(data)

    @property
    def Keys(self):
        return list(self._data.keys())

    def Item(self, key):
        value = self._data[key]
        if isinstance(value, list):
            return NetList(value)
        return value

    def __getitem__(self, key):
        return self.Item(key)


class FakeFile(object):
    """``System.IO.File``: чтение настоящего файла в UTF-8."""

    @staticmethod
    def ReadAllText(path):
        if not os.path.exists(path):
            raise IOError(u"fake File: файл не найден: " + path)
        handle = io.open(path, "r", encoding="utf-8")
        try:
            return handle.read()
        finally:
            handle.close()


class FakePath(object):
    """``System.IO.Path``: только ``Combine``, как в продуктовом коде v2."""

    Combine = staticmethod(os.path.join)


class FakeJavaScriptSerializer(object):
    """``JavaScriptSerializer``: ``json.loads`` + возможность отказать."""

    fail = False

    def DeserializeObject(self, content):
        if FakeJavaScriptSerializer.fail:
            raise ValueError(u"fake serializer: отказ разбора")
        return NetDict(json.loads(content))


def _install_fake_dotnet_modules():
    """Подкладывает fake-модули ``clr``/``System*`` до импорта продукта."""
    clr_module = types.ModuleType("clr")
    clr_module.AddReference = lambda name: None

    system = types.ModuleType("System")
    system.__path__ = []
    system_io = types.ModuleType("System.IO")
    system_io.File = FakeFile
    system_io.Path = FakePath
    system_web = types.ModuleType("System.Web")
    system_web.__path__ = []
    serialization = types.ModuleType("System.Web.Script.Serialization")
    serialization.JavaScriptSerializer = FakeJavaScriptSerializer

    system.IO = system_io
    system.Web = system_web
    system_web.Script = serialization

    for name, module in (("clr", clr_module),
                         ("System", system),
                         ("System.IO", system_io),
                         ("System.Web", system_web),
                         ("System.Web.Script.Serialization", serialization)):
        sys.modules.setdefault(name, module)


_install_fake_dotnet_modules()

from Mechanical.project_context import ProjectContext, ReadOnlyConfig  # noqa: E402


# --- двойники ANSYS API ------------------------------------------------------
class FakeLog(object):
    """``ExtAPI.Log``: складывает сообщения, чтобы тест мог их прочитать."""

    def __init__(self):
        self.messages = []

    def WriteMessage(self, message):
        self.messages.append(u"INFO: " + message)

    def WriteWarning(self, message):
        self.messages.append(u"WARNING: " + message)

    def WriteError(self, message):
        self.messages.append(u"ERROR: " + message)

    def text(self):
        return u"\n".join(self.messages)


class FakeNamedSelections(object):
    def __init__(self, names):
        self.Children = [_FakeNamedSelection(name) for name in names]


class _FakeNamedSelection(object):
    def __init__(self, name):
        self.Name = name


class FakeAnalyses(object):
    def __init__(self, analyses):
        self._analyses = analyses

    @property
    def Count(self):
        return len(self._analyses)

    def __getitem__(self, index):
        return self._analyses[index]


class FakeModel(object):
    def __init__(self, name, ns_names=None):
        self.Name = name
        self.NamedSelections = FakeNamedSelections(ns_names or [])
        self.Analyses = FakeAnalyses([_FakeAnalysis()])


class _FakeAnalysis(object):
    Name = "Static Structural"


class FakeProject(object):
    def __init__(self, name, model_name, ns_names=None):
        self.Name = name
        self.Model = FakeModel(model_name, ns_names)


class FakeDataModel(object):
    def __init__(self, project):
        self.Project = project


class FakeExtAPI(object):
    def __init__(self, project_name, model_name, ns_names=None):
        self.DataModel = FakeDataModel(FakeProject(project_name, model_name, ns_names))
        self.Log = FakeLog()


STRUCTURE_8946_DATA = {
    "structure_info": {"id": "8946", "type": "SG", "description": "Опора скользящая направляющая"},
    "loads": {"08": {"nominal_forces": {"fx": 1000, "fy": 1700, "fz": -3300}}},
    "torque_nm": {"8": 11.8},
    "boundary_conditions": {"fixed_support": "gu_fixed",
                            "remote_displacement": "gu_remote_disp"},
    "spaceclaim_processing": {"clean_geometry": True, "named_selections": []},
}

STRUCTURE_151_DATA = {
    "structure_info": {"id": "151", "type": "v1", "description": "Конструкция схемы v1"},
    "loads": {"02": {"nominal_forces": {"fx": 10, "fy": 20, "fz": -30}}},
    "boundary_conditions": {"fixed_support": "gu_fixed"},
}


class ProjectContextTestCase(unittest.TestCase):
    """Контекст проекта без живого ANSYS."""

    def setUp(self):
        FakeJavaScriptSerializer.fail = False
        self.tmp = tempfile.mkdtemp(prefix="ctx-tests-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._old_root = os.environ.get("ANSYS_AUTOMATION_ROOT")
        self._old_project = os.environ.get("ANSYS_AUTOMATION_PROJECT")
        self.addCleanup(self._restore_root)
        self.addCleanup(self._restore_project_env)

    def _restore_root(self):
        if self._old_root is None:
            os.environ.pop("ANSYS_AUTOMATION_ROOT", None)
        else:
            os.environ["ANSYS_AUTOMATION_ROOT"] = self._old_root

    def _restore_project_env(self):
        if self._old_project is None:
            os.environ.pop("ANSYS_AUTOMATION_PROJECT", None)
        else:
            os.environ["ANSYS_AUTOMATION_PROJECT"] = self._old_project

    def _use_project_path(self, path):
        if path is None:
            os.environ.pop("ANSYS_AUTOMATION_PROJECT", None)
        else:
            os.environ["ANSYS_AUTOMATION_PROJECT"] = path
        return path

    def _make_root(self, structure_id="8946", skip_common=None, structure_data=None):
        """Собирает временный корень проекта: config/mechanical_configs + конфиг."""
        root = tempfile.mkdtemp(prefix="ctx-root-", dir=self.tmp)
        config_dir = os.path.join(root, "config")
        mech_dir = os.path.join(config_dir, "mechanical_configs")
        os.makedirs(mech_dir)

        source_dir = os.path.join(ROOT, "config", "mechanical_configs")
        for name in sorted(os.listdir(source_dir)):
            if name == skip_common:
                continue
            shutil.copy(os.path.join(source_dir, name), os.path.join(mech_dir, name))

        if structure_data is not None:
            path = os.path.join(config_dir, "structure_type_{0}.json".format(structure_id))
            handle = io.open(path, "w", encoding="utf-8")
            try:
                handle.write(json.dumps(structure_data, ensure_ascii=False, indent=2))
            finally:
                handle.close()
        elif structure_id == "8946":
            shutil.copy(os.path.join(ROOT, "config", "structure_type_8946.json"),
                        os.path.join(config_dir, "structure_type_8946.json"))
        return root

    def _use_root(self, root):
        os.environ["ANSYS_AUTOMATION_ROOT"] = root
        return root

    def _context(self, project_name="Project_8946", model_name="18-245", ns_names=None):
        return ProjectContext(FakeExtAPI(project_name, model_name, ns_names))

    # --- идентификация (FR-3) ------------------------------------------------
    def test_project_and_model_identity(self):
        self._use_root(self._make_root())
        context = self._context(ns_names=["gu_fixed", "gu_force", "gu_bolt1_f"])

        self.assertEqual(context.project_id, "8946")
        self.assertEqual(context.structure_type_id, "8946")
        self.assertEqual(context.execution_no, "18")
        self.assertEqual(context.pipe_diameter, "245")
        self.assertEqual(context.structure_category, "execution")
        self.assertIsNotNone(context.model)
        self.assertIsNotNone(context.analysis)

    # --- источники идентификатора проекта (порядок приоритета) --------------
    def test_project_id_comes_from_env_path_to_wbpj(self):
        # Приоритет 1: путь к .wbpj из журнала Workbench. Имя проекта в
        # Mechanical дефолтное ('Project') и идентификатора не содержит.
        self._use_root(self._make_root())
        self._use_project_path(u"C:\\Projects\\Model\\Project_8946.wbpj")

        context = self._context(project_name="Project", model_name="Model")

        self.assertEqual(context.project_id, "8946")
        self.assertEqual(context.project_id_source, "env")
        self.assertEqual(context.structure_type_id, "8946")
        # Дефолтное имя модели не ломает прогон: предупреждение, а не падение.
        self.assertIsNone(context.execution_no)
        self.assertEqual(set(context.configs.keys()),
                         {"mesh_config", "contact_settings", "analysis_scenarios",
                          "project_settings", "structure_type", "merged"})

    def test_project_name_is_last_resort_with_warning(self):
        # Приоритет 2: Project.Name годится, только если в нём есть Project_XXX.
        self._use_root(self._make_root())
        self._use_project_path(None)
        ext_api = FakeExtAPI("Project_8946", "18-245")

        context = ProjectContext(ext_api)

        self.assertEqual(context.project_id, "8946")
        self.assertEqual(context.project_id_source, "project_name")
        self.assertIn(u"ANSYS_AUTOMATION_PROJECT", ext_api.Log.text())
        self.assertIn(u"дефолтное", ext_api.Log.text())

    def test_env_path_without_project_id_falls_back_to_project_name(self):
        self._use_root(self._make_root())
        self._use_project_path(u"C:\\Projects\\something-else.wbpj")

        context = self._context(project_name="Project_8946", model_name="18-245")

        self.assertEqual(context.project_id, "8946")
        self.assertEqual(context.project_id_source, "project_name")

    def test_default_names_without_env_raise_identity_error(self):
        # Ни env, ни имени проекта, ни шаблона модели: явная ошибка, а не
        # поиск structure_type_Model.json.
        self._use_root(self._make_root())
        self._use_project_path(None)
        error = None
        try:
            self._context(project_name="Project", model_name="Model")
        except ValueError as exc:
            error = exc

        self.assertIsNotNone(error)
        self.assertIn(u"Не удалось определить конструкцию", u"{0}".format(error))

    def test_structure_config_without_type_reports_unknown_type(self):
        # Отдельная ветка _load_structure_config: причина — нераспознанный тип,
        # а не отсутствие файла structure_type_None.json.
        self._use_root(self._make_root())
        self._use_project_path(None)
        context = self._context()
        context.structure_type_id = None
        context.structure_category = "unknown"
        error = None
        try:
            context._load_structure_config()
        except ValueError as exc:
            error = exc

        self.assertIsNotNone(error)
        message = u"{0}".format(error)
        self.assertIn(u"Тип конструкции не распознан", message)
        self.assertNotIn(u"structure_type_None.json", message)

    def test_project_root_comes_from_environment(self):
        root = self._use_root(self._make_root())
        context = self._context()

        self.assertEqual(context.project_root, root)

    def test_named_selections_analysis_collected(self):
        self._use_root(self._make_root())
        context = self._context(ns_names=["gu_fixed", "gu_force", "gu_bolt1_f"])

        self.assertEqual(context.ns_names, ["gu_fixed", "gu_force", "gu_bolt1_f"])
        self.assertTrue(context.ns_analysis["has_supports"])
        self.assertTrue(context.ns_analysis["has_bolts"])
        self.assertEqual(context.ns_analysis["total_ns_count"], 3)
        self.assertEqual(context.ns_analysis["ns_names"],
                         ["gu_fixed", "gu_force", "gu_bolt1_f"])

    def test_execution_search_fallback_keeps_v2_behaviour(self):
        self._use_root(self._make_root())
        context = self._context(model_name="Model_18-245_v2")

        self.assertEqual(context.execution_no, "18")
        self.assertEqual(context.pipe_diameter, "245")

    # --- конфиги (FR-3) ------------------------------------------------------
    def test_configs_contain_four_common_and_structure(self):
        self._use_root(self._make_root())
        context = self._context()

        expected = {"mesh_config", "contact_settings", "analysis_scenarios",
                    "project_settings", "structure_type", "merged"}
        self.assertEqual(set(context.configs.keys()), expected)
        self.assertEqual(context.configs["structure_type"]["structure_info"]["id"], "8946")

    def test_merged_contains_structure_config_keys(self):
        self._use_root(self._make_root())
        context = self._context()
        merged = context.configs["merged"]

        for key in ("structure_info", "loads", "torque_nm",
                    "boundary_conditions", "spaceclaim_processing"):
            self.assertIn(key, merged)
        for key in ("mesh_settings", "contact_settings", "project", "standard_sequence"):
            self.assertIn(key, merged)
        self.assertEqual(merged["structure_info"]["id"], "8946")
        self.assertEqual(merged["boundary_conditions"]["fixed_support"], "gu_fixed")

    def test_merged_is_read_only(self):
        self._use_root(self._make_root())
        context = self._context()
        merged = context.configs["merged"]

        self.assertIsInstance(merged, ReadOnlyConfig)
        self.assertRaises(TypeError, merged.__setitem__, "new_key", 1)
        self.assertRaises(TypeError, merged.__delitem__, "structure_info")
        self.assertRaises(TypeError, merged.update, {"new_key": 1})
        self.assertRaises(TypeError, merged.pop, "structure_info")
        self.assertRaises(TypeError, merged.setdefault, "new_key", 1)
        self.assertRaises(TypeError, merged.clear)
        # Вложенный словарь тоже защищён от изменения.
        self.assertRaises(TypeError, merged["structure_info"].__setitem__, "id", "0000")
        self.assertEqual(merged["structure_info"]["id"], "8946")

    # --- fallback v1 (Q2, ветвь A) ------------------------------------------
    def test_v1_fallback_uses_model_name_patterns(self):
        self._use_root(self._make_root(structure_id="151", structure_data=STRUCTURE_151_DATA))
        context = self._context(project_name="SupportAssembly", model_name="151-02-F2")

        self.assertIsNone(context.project_id)
        self.assertEqual(context.structure_type_id, "151")
        self.assertEqual(context.structure_category, "standard")
        self.assertEqual(context.execution_no, "151")
        self.assertEqual(context.pipe_diameter, "02")
        self.assertIn("structure_type", context.configs)
        self.assertEqual(context.configs["structure_type"]["structure_info"]["id"], "151")

    def test_unresolvable_identity_raises_value_error(self):
        self._use_root(self._make_root())
        error = None
        try:
            self._context(project_name="SupportAssembly", model_name="18-245")
        except ValueError as exc:
            error = exc

        self.assertIsNotNone(error)
        message = u"{0}".format(error)
        self.assertIn("Project_XXX", message)
        self.assertIn("18-245", message)
        self.assertIn("structure_type", message)

    # --- ошибки конфигов (FR-9) ---------------------------------------------
    def test_missing_structure_config_raises_value_error(self):
        self._use_root(self._make_root(structure_id="9999"))
        error = None
        try:
            self._context(project_name="Project_9999")
        except ValueError as exc:
            error = exc

        self.assertIsNotNone(error)
        message = u"{0}".format(error)
        self.assertIn("structure_type_9999.json", message)
        self.assertIn("не найден", message)

    def test_missing_common_config_raises_value_error(self):
        self._use_root(self._make_root(skip_common="mesh_config.json"))
        error = None
        try:
            self._context()
        except ValueError as exc:
            error = exc

        self.assertIsNotNone(error)
        self.assertIn("mesh_config.json", u"{0}".format(error))

    def test_validators_reject_incomplete_structure_config(self):
        broken = {
            "structure_info": {"id": "8946", "type": "SG"},
            "loads": {},
            "boundary_conditions": {},
        }
        self._use_root(self._make_root(structure_id="8946", structure_data=broken))
        error = None
        try:
            self._context()
        except ValueError as exc:
            error = exc

        self.assertIsNotNone(error)
        self.assertIn("loads", u"{0}".format(error))

    def test_validate_passes_on_repository_configs(self):
        self._use_root(self._make_root())
        context = self._context()

        self.assertTrue(context.validate())

    # --- runtime-путь загрузки JSON -----------------------------------------
    def test_serializer_failure_falls_back_to_json_parser(self):
        self._use_root(self._make_root())
        FakeJavaScriptSerializer.fail = True
        try:
            context = self._context()
        finally:
            FakeJavaScriptSerializer.fail = False

        self.assertEqual(set(context.configs.keys()),
                         {"mesh_config", "contact_settings", "analysis_scenarios",
                          "project_settings", "structure_type", "merged"})
        self.assertEqual(context.configs["mesh_config"]["mesh_settings"]["mbolt"]["meshCoef"], 6.7)

    def test_logger_writes_to_ansys_log(self):
        self._use_root(self._make_root())
        ext_api = FakeExtAPI("Project_8946", "18-245")
        context = ProjectContext(ext_api)
        text = ext_api.Log.text()

        self.assertIn(u"ProjectContext инициализирован", text)
        self.assertIn(u"Идентификатор проекта: 8946", text)
        self.assertIn(u"Тип: SG", text)


if __name__ == "__main__":
    unittest.main()
