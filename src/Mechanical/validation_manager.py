# -*- coding: utf-8 -*-
import traceback
class ValidationManager:
    def __init__(self, context):
        self.context = context
        self.log = context.log
    def validate_model_setup(self):
        self.log.info(u"Запуск валидации настроек модели...")
        errors = []
        mandatory_configs = ["project_settings", "mesh_config", "contact_settings"]
        if self.context.project_id:
            mandatory_configs.append("structure_type")
        for config_key in mandatory_configs:
            if config_key not in self.context.configs:
                errors.append(u"Отсутствует обязательная конфигурация: {0}".format(config_key))
        if not self.context.model:
            errors.append(u"Объект Model не найден в проекте.")
        if not self.context.analysis:
            errors.append(u"Объект Analysis не найден в проекте.")
        if "structure_type" in self.context.configs:
            struct_config = self.context.configs["structure_type"]

            if "boundary_conditions" in struct_config:
                bc_config = struct_config["boundary_conditions"]
                if isinstance(bc_config, dict):
                    # Iterate over values directly since values are NS names
                    for ns_name in bc_config.values():
                        if ns_name and not self._named_selection_exists(ns_name):
                            errors.append(u"Named Selection '{0}' (для BC) не найден.".format(ns_name))
                elif isinstance(bc_config, list):
                    for bc in bc_config:
                        if isinstance(bc, dict):
                            ns_name = bc.get("named_selection")
                            if ns_name and not self._named_selection_exists(ns_name):
                                errors.append(u"Named Selection '{0}' (для BC) не найден.".format(ns_name))

            if "bolts" in struct_config:
                bolts_config = struct_config["bolts"]
                if isinstance(bolts_config, list):
                    for bolt in bolts_config:
                        if isinstance(bolt, dict):
                            ns_name = bolt.get("named_selection")
                            if ns_name and not self._named_selection_exists(ns_name):
                                errors.append(u"Named Selection '{0}' (для болта) не найден.".format(ns_name))
        if errors:
            self.log.error(u"Валидация НЕ ПРОЙДЕНА. Обнаружены ошибки:")
            for err in errors:
                self.log.error(u" - {0}".format(err))
            raise Exception(u"Критическая ошибка валидации.")
        self.log.info(u"Валидация настроек модели успешно завершена.")
        return True
    def _named_selection_exists(self, name):
        try:
            for ns in self.context.model.NamedSelections.Children:
                if ns.Name == name:
                    return True
            return False
        except Exception as e:
            self.log.warning(u"Ошибка при проверке NS '{0}': {1}".format(name, e))
            return False
