# -*- coding: utf-8 -*-
import clr
clr.AddReference("System.Web.Extensions")
from System.Web.Script.Serialization import JavaScriptSerializer
from System.IO import File, Path
import sys

class ProjectContext:
    def __init__(self, ext_api):
        self.ext_api = ext_api
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
        self.log = AnsysLogger()

    def _get_project_id(self):
        try:
            name = self.ext_api.DataModel.Project.Name
            import re
            match = re.search(r"Project_(\w+)", name)
            return match.group(1) if match else None
        except: return None

    def _load_json_config(self, file_path):
        try:
            content = File.ReadAllText(file_path)
            serializer = JavaScriptSerializer()
            # Приводим .NET-словарь к обычному dict
            return dict(serializer.DeserializeObject(content))
        except Exception as e:
            self.log.error(u"Ошибка JSON: {0}".format(e))
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
            if data: self.configs["structure_type"] = data
