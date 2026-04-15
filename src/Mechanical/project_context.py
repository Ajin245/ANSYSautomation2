# -*- coding: utf-8 -*-
import clr
clr.AddReference("System.Web.Extensions")
from System.Web.Script.Serialization import JavaScriptSerializer
from System.IO import File, Path
import sys

class ProjectContext:
    def __init__(self, ext_api, quantity_class=None, enums=None):
        self.ext_api = ext_api
        self.Quantity = quantity_class
        self.enums = enums or {}
        self.model = None
        self.analysis = None
        self.project_id = None
        self.configs = {}
        self._setup_logger()
        self.log.info(u"ProjectContext инициализирован.")
        self._initialize_project()

    def _setup_logger(self):
        class AnsysLogger:
            def info(self, msg): print("INFO: " + msg)
            def warning(self, msg): print("WARNING: " + msg)
            def error(self, msg): print("ERROR: " + msg)
            def debug(self, msg): print("DEBUG: " + msg)
        self.log = AnsysLogger()

    def _get_project_id(self):
        try:
            name = self.ext_api.DataModel.Project.Name
            import re
            match = re.search(r"Project_(\w+)", name)
            return match.group(1) if match else None
        except: return None

    def _convert_to_py(self, obj):
        if hasattr(obj, 'Keys') and hasattr(obj, 'Item'):
            return {k: self._convert_to_py(obj[k]) for k in obj.Keys}
        elif hasattr(obj, 'Count') and hasattr(obj, 'GetEnumerator') and not isinstance(obj, basestring):
            return [self._convert_to_py(item) for item in obj]
        else:
            return obj

    def _load_json_config(self, file_path):
        try:
            import re
            content = File.ReadAllText(file_path)
            content = re.sub(r'(?m)^\s*//.*$', '', content)
            serializer = JavaScriptSerializer()
            net_obj = serializer.DeserializeObject(content)
            return self._convert_to_py(net_obj)
        except Exception as e:
            self.log.error(u"Ошибка JSON в {0}: {1}".format(file_path, e))
            return None

    def _initialize_project(self):
        self.project_id = self._get_project_id()
        try:
            self.model = self.ext_api.DataModel.Project.Model
            if self.model.Analyses.Count > 0: self.analysis = self.model.Analyses[0]
        except: pass
            
        root = r"C:\Users\user\source\repos\ANSYSautomation2"
        cfg_dir = Path.Combine(root, "config", "mechanical_configs")
        
        common = {"mesh_config.json": "mesh_config", "contact_settings.json": "contact_settings", 
                  "analysis_scenarios.json": "analysis_scenarios", "project_settings.json": "project_settings"}
        
        for fname, key in common.items():
            path = Path.Combine(cfg_dir, fname)
            data = self._load_json_config(path)
            if data: self.configs[key] = data

        if self.project_id:
            path = Path.Combine(root, "config", "structure_type_{0}.json".format(self.project_id))
            data = self._load_json_config(path)
            if data: 
                self.configs["structure_type"] = data
                # Вывод информации о проекте
                info = data.get("structure_info", {})
                self.log.info(u"--- Информация о конструкции ---")
                self.log.info(u"Тип: {0}".format(info.get("type", "N/A")))
                self.log.info(u"Описание: {0}".format(info.get("description", "N/A")))
                
                # Парсинг номера исполнения и диаметра из имени проекта (напр. Project_18-245)
                project_name = self.ext_api.DataModel.Project.Name
                import re
                match = re.search(r"(\d+)-(\d+)", project_name)
                if match:
                    self.execution_no = match.group(1)
                    self.pipe_diameter = match.group(2)
                    self.log.info(u"Номер исполнения: {0}".format(self.execution_no))
                    self.log.info(u"Диаметр трубопровода: {0} мм".format(self.pipe_diameter))
                else:
                    self.execution_no = None
                    self.pipe_diameter = None
                self.log.info(u"---------------------------------")
