# -*- coding: utf-8 -*-

import json
import os
import sys
import re
import traceback

class ProjectContext:
    """
    Класс для управления всеми настройками, конфигурациями и объектами ANSYS
    для текущего проекта.
    """
    def __init__(self, ext_api):
        """
        Инициализация контекста проекта.

        Args:
            ext_api: Экземпляр ExtAPI ANSYS Mechanical.
        """
        self.ext_api = ext_api
        self.model = None
        self.analysis = None
        self.project_id = None
        self.configs = {}
        self._setup_logger()
        self.log.info(u"ProjectContext инициализирован.")
        self._initialize_project()

    def _setup_logger(self):
        """Настраивает базовый логгер для вывода в консоль ANSYS."""
        class AnsysLogger:
            def __init__(self):
                self.prefix = "ProjectContext: "

            def info(self, message):
                print("{0}INFO: {1}".format(self.prefix, message))

            def warning(self, message):
                print("{0}WARNING: {1}".format(self.prefix, message))

            def error(self, message):
                print("{0}ERROR: {1}".format(self.prefix, message))

            def debug(self, message):
                print("{0}DEBUG: {1}".format(self.prefix, message))
                
        self.log = AnsysLogger()

    def _get_project_id(self):
        """
        Извлекает идентификатор проекта из названия проекта ANSYS.
        Ожидаемый формат названия: "Project_XXX", где XXX - идентификатор.
        """
        try:
            project_name = self.ext_api.DataModel.Project.Name
            self.log.info(u"Получено имя проекта: {0}".format(project_name))
            match = re.search(r"Project_(\w+)", project_name)
            if match:
                project_id = match.group(1)
                self.log.info(u"Извлечен Project ID: {0}".format(project_id))
                return project_id
            else:
                self.log.warning(u"Не удалось извлечь Project ID из названия проекта: {0}. Ожидается формат 'Project_XXX'.".format(project_name))
                return None
        except Exception as e:
            self.log.error(u"Ошибка при получении или парсинге имени проекта: {0}\n{1}".format(e, traceback.format_exc()))
            return None

    def _load_json_config(self, file_path):
        """
        Безопасно загружает JSON-файл конфигурации.
        """
        try:
            # В Python 2.7 open не принимает encoding, используем io.open если нужно, 
            # но для простых JSON достаточно обычного open.
            with open(file_path, 'r') as f:
                config_data = json.load(f)
                self.log.info(u"Успешно загружен конфиг: {0}".format(file_path))
                return config_data
        except IOError:
            self.log.error(u"Файл конфигурации не найден: {0}".format(file_path))
            return None
        except ValueError:
            self.log.error(u"Ошибка декодирования JSON в файле: {0}".format(file_path))
            return None
        except Exception as e:
            self.log.error(u"Неизвестная ошибка при загрузке конфига {0}: {1}\n{2}".format(file_path, e, traceback.format_exc()))
            return None

    def _initialize_project(self):
        """
        Инициализирует основные компоненты проекта: ID, модели, конфиги.
        """
        self.project_id = self._get_project_id()
        
        try:
            self.model = self.ext_api.DataModel.Project.Model
            if self.model.Analyses.Count > 0:
                self.analysis = self.model.Analyses[0]
                self.log.info(u"Получены ссылки на Model и Analysis.")
            else:
                self.log.warning(u"В проекте не найдено ни одного анализа.")
        except Exception as e:
            self.log.error(u"Не удалось получить доступ к Model или Analysis: {0}\n{1}".format(e, traceback.format_exc()))
            
        # Пути в ANSYS Mechanical могут быть специфичными, используем os.path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Предполагаем, что config находится на два уровня выше src/Mechanical
        project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
        mechanical_configs_dir = os.path.join(project_root, "config", "mechanical_configs")
        
        common_configs_to_load = {
            "mesh_config.json": "mesh_config",
            "contact_settings.json": "contact_settings",
            "analysis_scenarios.json": "analysis_scenarios",
            "project_settings.json": "project_settings"
        }
        
        for filename, config_key in common_configs_to_load.iteritems(): # Использование iteritems() для Python 2
            file_path = os.path.join(mechanical_configs_dir, filename)
            config_data = self._load_json_config(file_path)
            if config_data is not None:
                self.configs[config_key] = config_data
            else:
                if config_key in ["project_settings", "mesh_config", "contact_settings"]:
                    self.log.warning(u"Обязательный конфиг '{0}' не был загружен.".format(config_key))

        if self.project_id:
            structure_config_filename = "structure_type_{0}.json".format(self.project_id)
            structure_config_path = os.path.join(project_root, "config", structure_config_filename)
            structure_config_data = self._load_json_config(structure_config_path)
            if structure_config_data is not None:
                self.configs["structure_type"] = structure_config_data
            else:
                self.log.warning(u"Специфичный конфиг '{0}' не найден или не загружен.".format(structure_config_filename))
            
        # Добавляем путь к src в sys.path
        src_path = os.path.abspath(os.path.join(current_dir, ".."))
        if src_path not in sys.path:
            sys.path.append(src_path)
            self.log.info(u"Добавлен путь к модулям: {0}".format(src_path))
