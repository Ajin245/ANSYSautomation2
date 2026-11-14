# -*- coding: utf-8 -*-
"""Контекст проекта: идентификация проекта/исполнения и загрузка конфигов.

Источник смысла — ``v2/src/Mechanical/project_context.py`` (рабочее ядро v2) и
пункты 5, 8, 9, 12 таблицы слияния (``PLAN-MERGE.md`` §2.2). Что изменено:

* ``project_id`` берётся, в порядке приоритета, из (1) пути к ``.wbpj`` в
  ``ANSYS_AUTOMATION_PROJECT`` — путь кладёт журнал Workbench
  (``GetProjectFile()``), идентификатор извлекается из имени файла
  (``...\Project_8946.wbpj`` -> ``8946``); (2) имени проекта
  ``ExtAPI.DataModel.Project.Name`` через ``execution_parser.parse_project_id``
  — только как последний шанс: в Mechanical это имя часто дефолтное ``Project``
  и идентификатора не содержит, поэтому такой источник пишется в лог как
  предупреждение;
* ``execution_no``/``pipe_diameter`` — из имени модели ``NN-DDD`` через
  ``execution_parser``, с сохранением v2-поведения ``re.search`` для имён с
  префиксом или суффиксом (``Model_18-245_v2``);
* если ``Project_XXX`` в имени проекта нет, включается fallback на шаблоны v1
  (``structure_detector``): тип конструкции определяется по имени модели, имена
  Named Selections передаются детектору как данные (Q2 плана, ветвь A). Если не
  сработало и это — ``ValueError`` с перечислением того, что именно не найдено;
* ``configs["merged"]`` — слияние общих конфигов и конфига конструкции через
  ``config_merge.merge_configs``, доступное только для чтения;
* обязательные ключи проверяются ``validators`` до старта конвейера (FR-9);
* корень проекта — единый ``utils.get_project_root`` (NFR-4); дублирование
  разрешения путей из v2 (``project_context.py:118-137``) удалено.

Не изменены ``AnsysLogger`` (логирование на событиях Ansys) и передача
``Quantity``/Enum через конструктор — обход ``TypeError`` при изоляции сборок
(``RULES.md``, «Quantity/Enum Handling»).
"""

import os
import re

import clr
clr.AddReference("System.Web.Extensions")
from System.Web.Script.Serialization import JavaScriptSerializer
from System.IO import File

from Mechanical import config_merge
from Mechanical import execution_parser
from Mechanical import structure_detector
from Mechanical import validators
from Mechanical.utils import get_project_root

# Общие конфиги (FR-3): файл в config/mechanical_configs -> ключ в ``configs``.
COMMON_CONFIGS = (
    ("mesh_config.json", "mesh_config"),
    ("contact_settings.json", "contact_settings"),
    ("analysis_scenarios.json", "analysis_scenarios"),
    ("project_settings.json", "project_settings"),
    ("bolt_pretension.json", "bolt_pretension"),
)

# Путь к .wbpj, который журнал Workbench передаёт в Mechanical через окружение
# (``GetProjectFile()``): единственный надёжный источник идентификатора проекта,
# потому что ``Project.Name`` в Mechanical дефолтный ('Project') и ID не несёт.
PROJECT_PATH_ENV = "ANSYS_AUTOMATION_PROJECT"

STRUCTURE_CONFIG_KEY = "structure_type"
MERGED_CONFIG_KEY = "merged"

# v2 разбирал исполнение через ``re.search`` (``project_context.py:99-108``),
# поэтому имя вида ``Model_18-245_v2`` тоже давало 18/245. Оставляем это
# последним шагом после строгих шаблонов ``execution_parser``.
EXECUTION_SEARCH_PATTERN = re.compile(r"(\d+)-(\d+)")

READ_ONLY_MESSAGE = u"configs['merged'] только для чтения: изменение запрещено"


class ReadOnlyConfig(dict):
    """Словарь, который нельзя изменить после сборки.

    В IronPython 2.7 нет ``types.MappingProxyType``, поэтому запрет делается
    переопределением методов изменения. Наполнение — через ``dict.__setitem__``
    напрямую, чтобы обойти этот запрет внутри самого класса.
    """

    def __setitem__(self, key, value):
        raise TypeError(READ_ONLY_MESSAGE)

    def __delitem__(self, key):
        raise TypeError(READ_ONLY_MESSAGE)

    def clear(self):
        raise TypeError(READ_ONLY_MESSAGE)

    def pop(self, key, *args):
        raise TypeError(READ_ONLY_MESSAGE)

    def popitem(self):
        raise TypeError(READ_ONLY_MESSAGE)

    def setdefault(self, key, *args):
        raise TypeError(READ_ONLY_MESSAGE)

    def update(self, *args, **kwargs):
        raise TypeError(READ_ONLY_MESSAGE)


def _freeze(value):
    """Рекурсивно превращает словари в ``ReadOnlyConfig``.

    Списки копируются как есть: в конфигах это ``patterns`` и ``load_factors``,
    менеджеры читают их поэлементно и не должны получать другой тип.
    """
    if isinstance(value, dict):
        frozen = ReadOnlyConfig()
        for key, item in value.items():
            dict.__setitem__(frozen, key, _freeze(item))
        return frozen
    if isinstance(value, list):
        return [_freeze(item) for item in value]
    return value


def make_read_only(mapping):
    """Возвращает глубокое read-only представление словаря конфигов."""
    return _freeze(mapping or {})


class ProjectContext(object):
    """Проект, модель и конфиги, общие для всех менеджеров Mechanical."""

    def __init__(self, ext_api, quantity_class=None, enums=None):
        self.ext_api = ext_api
        self.Quantity = quantity_class
        self.enums = enums or {}
        self._load_fallback_enums()
        self.model = None
        self.analysis = None
        self.project_id = None
        self.project_id_source = None
        self.structure_type_id = None
        self.structure_category = None
        self.execution_no = None
        self.pipe_diameter = None
        self.ns_names = []
        self.ns_analysis = {}
        self.configs = {}
        self.project_root = get_project_root()
        self._setup_logger()
        self.log.info(u"ProjectContext инициализирован.")
        self._initialize_project()

    def _load_fallback_enums(self):
        try:
            from Ansys.Mechanical.DataModel.Enums import LoadDefineBy, MethodType, MeshMethodAlgorithm, ElementOrder
            if "LoadDefineBy" not in self.enums:
                self.enums["LoadDefineBy"] = LoadDefineBy
            if "MethodType" not in self.enums:
                self.enums["MethodType"] = MethodType
            if "MeshMethodAlgorithm" not in self.enums:
                self.enums["MeshMethodAlgorithm"] = MeshMethodAlgorithm
            if "ElementOrder" not in self.enums:
                self.enums["ElementOrder"] = ElementOrder
        except ImportError:
            pass

    def _setup_logger(self):
        class AnsysLogger:
            def __init__(self, ext_api):
                self.ext_api = ext_api

            def info(self, msg):
                try:
                    self.ext_api.Log.WriteMessage(unicode(msg))
                except:
                    print("INFO: " + msg)

            def warning(self, msg):
                try:
                    self.ext_api.Log.WriteWarning(unicode(msg))
                except:
                    print("WARNING: " + msg)

            def error(self, msg):
                try:
                    self.ext_api.Log.WriteError(unicode(msg))
                except:
                    print("ERROR: " + msg)

            def debug(self, msg):
                # Debug оставляем в стандартном выводе, чтобы не перегружать лог ANSYS
                print("DEBUG: " + msg)

        self.log = AnsysLogger(self.ext_api)

    def _get_project_name(self):
        """Имя проекта из ``DataModel.Project.Name`` (``None`` при ошибке API)."""
        try:
            return self.ext_api.DataModel.Project.Name
        except Exception as e:
            self.log.error(u"Не удалось прочитать имя проекта: {0}".format(e))
            return None

    def _get_model_name(self):
        """Имя модели из ``Model.Name`` (``None``, если модель не привязана)."""
        if self.model is None:
            return None
        try:
            return self.model.Name
        except Exception as e:
            self.log.error(u"Не удалось прочитать имя модели: {0}".format(e))
            return None

    def _get_ns_names(self):
        """Имена Named Selections модели (для fallback-детектора v1)."""
        if self.model is None:
            return []
        try:
            children = self.model.NamedSelections.Children
        except Exception as e:
            self.log.warning(u"Named Selections недоступны: {0}".format(e))
            return []

        names = []
        for item in children or []:
            if hasattr(item, 'Name'):
                names.append(item.Name)
            else:
                names.append(item)
        return names

    def _get_project_id(self):
        """Идентификатор проекта ``Project_XXX`` -> ``XXX`` (``None``, если нет)."""
        return execution_parser.parse_project_id(self._get_project_name())

    def _project_id_from_path(self, path):
        """Идентификатор из пути к ``.wbpj``: ``...\\Project_8946.wbpj`` -> ``8946``.

        Имя файла разбирается тем же ``parse_project_id``, что и имя проекта,
        поэтому ``Project_8946.wbpj`` и ``Project_8946`` дают один результат.

        Args:
            path (str): путь к файлу проекта из ``ANSYS_AUTOMATION_PROJECT``.

        Returns:
            str: идентификатор или ``None``, если путь пуст/имя не по шаблону.
        """
        if not path:
            return None
        base = os.path.basename(path.strip())
        name = os.path.splitext(base)[0]
        return execution_parser.parse_project_id(name)

    def _resolve_project_id(self, project_name):
        """Идентификатор проекта и источник, из которого он получен.

        Приоритет источников:
            1. ``ANSYS_AUTOMATION_PROJECT`` — путь к ``.wbpj`` из журнала
               Workbench (``GetProjectFile()``). Основной путь: в Mechanical
               ``Project.Name`` дефолтный и ID не содержит.
            2. ``DataModel.Project.Name`` (``Project_XXX``) — последний шанс,
               с предупреждением в лог: имя может быть ``'Project'``.

        Args:
            project_name (str): ``ExtAPI.DataModel.Project.Name``.

        Returns:
            tuple: ``(project_id, source)``; ``source`` — ``"env"``,
            ``"project_name"`` или ``None`` (идентификатор не найден).
        """
        project_path = os.environ.get(PROJECT_PATH_ENV, "")
        project_id = self._project_id_from_path(project_path)
        if project_id:
            self.log.info(u"Путь к проекту ({0}): {1}".format(PROJECT_PATH_ENV, project_path))
            return project_id, "env"

        if project_path and project_path.strip():
            self.log.warning(
                u"В пути к проекту '{0}' нет шаблона Project_XXX; "
                u"пробуем имя проекта из Mechanical.".format(project_path))

        project_id = execution_parser.parse_project_id(project_name)
        if project_id:
            self.log.warning(
                u"Идентификатор {0} взят из имени проекта '{1}' ({2} не задан). "
                u"В Mechanical имя проекта часто дефолтное 'Project', поэтому "
                u"журнал Workbench должен передавать путь к .wbpj.".format(
                    project_id, project_name, PROJECT_PATH_ENV))
            return project_id, "project_name"

        return None, None

    def _convert_to_py(self, obj):
        """Конвертация .NET-объектов ``JavaScriptSerializer`` в python-структуры."""
        if hasattr(obj, 'Keys') and hasattr(obj, 'Item'):
            return {k: self._convert_to_py(obj[k]) for k in obj.Keys}
        elif hasattr(obj, 'Count') and hasattr(obj, 'GetEnumerator') and not isinstance(obj, basestring):
            return [self._convert_to_py(item) for item in obj]
        else:
            return obj

    def _load_json_config(self, file_path):
        """Читает JSON-конфиг: ``JavaScriptSerializer``, затем ``json_parser``.

        Runtime-путь v2 (``JavaScriptSerializer``) сохранён первым. Если он
        недоступен или не разобрал файл, используется чистый ``json_parser``
        (``PLAN-MERGE.md`` §2.2, пункт 7). Ошибка обоих путей -> ``None``:
        вызывающий код сам решает, критично ли отсутствие файла.
        """
        try:
            content = File.ReadAllText(file_path)
            content = re.sub(r'(?m)^\s*//.*$', '', content)
            serializer = JavaScriptSerializer()
            net_obj = serializer.DeserializeObject(content)
            return self._convert_to_py(net_obj)
        except Exception as e:
            self.log.warning(u"JavaScriptSerializer не разобрал {0}: {1}; пробуем json_parser".format(
                file_path, e))

        try:
            # Ленивый импорт: на обычном пути ANSYS модуль json не нужен.
            from Mechanical import json_parser
            return json_parser.load_json_file(file_path)
        except Exception as e:
            self.log.error(u"Ошибка JSON в {0}: {1}".format(file_path, e))
            return None

    def _bind_model(self):
        """Привязывает ``Model`` и первый ``Analysis`` (как в v2)."""
        try:
            self.model = self.ext_api.DataModel.Project.Model
            if self.model.Analyses.Count > 0:
                self.analysis = self.model.Analyses[0]
        except Exception as e:
            self.log.error(u"Ошибка инициализации проекта: {0}".format(e))

    def _resolve_identity(self):
        """Определяет проект, тип конструкции, исполнение и диаметр.

        Основной путь — схемы v2 (``Project_XXX`` + ``NN-DDD``). Если
        ``Project_XXX`` нет, тип конструкции ищется шаблонами v1
        (``structure_detector``) по имени модели; Named Selections передаются
        детектору и попадают в ``ns_analysis``.

        Raises:
            ValueError: если ни схема v2, ни шаблоны v1 не дали идентификатор
                конструкции — без него нельзя выбрать ``structure_type_XXX.json``.
        """
        project_name = self._get_project_name()
        model_name = self._get_model_name()

        self.ns_names = self._get_ns_names()
        self.ns_analysis = structure_detector.detect_ns_patterns(self.ns_names)

        self.project_id, self.project_id_source = self._resolve_project_id(project_name)
        structure_type, category = structure_detector.detect_structure_type(
            model_name, self.ns_names)
        self.structure_category = category
        self.structure_type_id = self.project_id or structure_type

        self.execution_no = execution_parser.parse_execution(model_name)
        self.pipe_diameter = execution_parser.parse_diameter(model_name)
        if self.execution_no is None:
            match = EXECUTION_SEARCH_PATTERN.search(model_name or "")
            if match:
                self.execution_no = match.group(1)
                self.pipe_diameter = match.group(2)
                self.log.debug(u"Исполнение взято из свободного шаблона NN-DDD: {0}-{1}".format(
                    self.execution_no, self.pipe_diameter))

        if self.project_id:
            self.log.info(u"Идентификатор проекта: {0} (источник: {1})".format(
                self.project_id, self.project_id_source))
        else:
            self.log.warning(
                u"Идентификатор проекта не найден ни в {0}, ни в имени проекта "
                u"'{1}'; используется fallback v1 (тип конструкции '{2}', "
                u"категория '{3}').".format(
                    PROJECT_PATH_ENV, project_name, structure_type, category))

        if self.execution_no:
            self.log.info(u"Номер исполнения: {0}".format(self.execution_no))
            self.log.info(u"Диаметр трубопровода: {0} мм".format(self.pipe_diameter))
        else:
            # Поведение v2: без исполнения работа продолжается, но без нагрузок.
            self.log.warning(
                u"Не удалось извлечь исполнение и диаметр из имени модели: '{0}'. "
                u"Ожидается имя по шаблону NN-DDD (например 18-245); дефолтное "
                u"имя 'Model' означает, что модель не переименована.".format(model_name))

        if not self.structure_type_id:
            raise ValueError(self._identity_error(project_name, model_name))

    def _identity_error(self, project_name, model_name):
        """Текст ошибки: что именно не удалось определить и чем пробовали."""
        return (u"Не удалось определить конструкцию: в имени проекта '{0}' нет шаблона "
                u"Project_XXX, а по имени модели '{1}' и {2} Named Selections не сработали "
                u"шаблоны v1 (151-02-F2, custom_001-01-F1, 151_..., ABC_...). "
                u"Не найдено: project_id, structure_type. "
                u"Переименуйте проект в Project_<id> или модель по шаблону конструкции.").format(
                    project_name, model_name, len(self.ns_names))

    def _load_configs(self):
        """Загружает 4 общих конфига и ``structure_type_XXX.json`` (FR-3)."""
        config_dir = os.path.join(self.project_root, "config", "mechanical_configs")
        missing = []

        for file_name, key in COMMON_CONFIGS:
            path = os.path.join(config_dir, file_name)
            if not os.path.exists(path):
                missing.append(path)
                continue
            data = self._load_json_config(path)
            if data is None:
                missing.append(path)
                continue
            self.configs[key] = data

        if missing:
            raise ValueError(u"Не найдены обязательные конфиги: {0}".format(
                u", ".join(missing)))

        self._load_structure_config()
        self._build_merged_config()

    def _load_structure_config(self):
        """Загружает конфиг конструкции — единственный источник истины (Q10).

        Raises:
            ValueError: файл ``structure_type_XXX.json`` отсутствует или не
                читается; текст содержит путь и определённый идентификатор.
        """
        if self.structure_type_id is None:
            # Отдельный текст: причина — нераспознанный тип конструкции, а не
            # отсутствующий файл. Иначе ошибка выглядела бы как «нет
            # structure_type_None.json» и уводила от настоящей причины.
            raise ValueError(
                u"Тип конструкции не распознан: идентификатор не найден ни в "
                u"ANSYS_AUTOMATION_PROJECT, ни в имени проекта, ни по шаблонам "
                u"имени модели и Named Selections (категория '{0}'). "
                u"Файл конфига конструкции не выбирается.".format(self.structure_category))

        path = os.path.join(self.project_root, "config",
                            "structure_type_{0}.json".format(self.structure_type_id))
        if not os.path.exists(path):
            raise ValueError(
                u"Конфиг конструкции не найден: {0}. Идентификатор конструкции "
                u"определён как '{1}' (шаблон имени модели: '{2}'); ожидался файл "
                u"structure_type_{1}.json в каталоге config/.".format(
                    path, self.structure_type_id, self.structure_category))

        data = self._load_json_config(path)
        if data is None:
            raise ValueError(u"Конфиг конструкции не читается: {0}".format(path))

        self.configs[STRUCTURE_CONFIG_KEY] = data
        info = data.get("structure_info", {}) or {}
        self.log.info(u"--- Информация о конструкции ---")
        self.log.info(u"Тип: {0}".format(info.get("type", "N/A")))
        self.log.info(u"Описание: {0}".format(info.get("description", "N/A")))
        self.log.info(u"---------------------------------")

    def _build_merged_config(self):
        """Собирает ``configs["merged"]``: общие конфиги + конфиг конструкции."""
        merged = {}
        for file_name, key in COMMON_CONFIGS:
            merged = config_merge.merge_configs(merged, self.configs.get(key))
        merged = config_merge.merge_configs(merged, self.configs.get(STRUCTURE_CONFIG_KEY))
        self.configs[MERGED_CONFIG_KEY] = make_read_only(merged)

    def validate(self):
        """Проверяет обязательные ключи конфигов до старта конвейера (FR-9).

        Returns:
            bool: True, если конфиги валидны.

        Raises:
            ValueError: обязательный конфиг отсутствует или неполон; текст
                ошибки приходит из ``validators`` и останавливает прогон.
        """
        missing = [key for file_name, key in COMMON_CONFIGS if key not in self.configs]
        if STRUCTURE_CONFIG_KEY not in self.configs:
            missing.append(STRUCTURE_CONFIG_KEY)
        if missing:
            raise ValueError(u"Отсутствуют обязательные конфиги: {0}".format(
                u", ".join(missing)))

        validators.validate_mesh_settings(self.configs["mesh_config"])
        validators.validate_contact_settings(self.configs["contact_settings"])
        validators.validate_structure_type_config(self.configs[STRUCTURE_CONFIG_KEY])
        return True

    def _initialize_project(self):
        """Полный цикл: модель -> идентификация -> конфиги -> валидация."""
        self._bind_model()
        self._resolve_identity()
        self._load_configs()
        self.validate()
