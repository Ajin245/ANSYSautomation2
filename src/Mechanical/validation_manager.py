# -*- coding: utf-8 -*-

import traceback

class ValidationManager:
    """
    Класс для валидации настроек модели ANSYS Mechanical перед расчетом.
    Обеспечивает проверку наличия всех необходимых данных и объектов.
    """
    def __init__(self, context):
        """
        Инициализация менеджера валидации.

        Args:
            context (ProjectContext): Контекст текущего проекта.
        """
        self.context = context
        self.log = context.log

    def validate_model_setup(self):
        """
        Выполняет комплексную проверку настроек модели.

        Returns:
            bool: True, если валидация пройдена успешно.
        
        Raises:
            Exception: Если обнаружены критические ошибки настройки.
        """
        self.log.info(u"Запуск валидации настроек модели...")
        
        errors = []

        # 1. Проверка загрузки обязательных конфигураций
        mandatory_configs = ["project_settings", "mesh_config", "contact_settings"]
        if self.context.project_id:
            mandatory_configs.append("structure_type")

        for config_key in mandatory_configs:
            if config_key not in self.context.configs:
                errors.append(u"Отсутствует обязательная конфигурация: '{0}'".format(config_key))

        # 2. Проверка объектов ANSYS
        if not self.context.model:
            errors.append(u"Объект Model не найден в проекте.")
        
        if not self.context.analysis:
            errors.append(u"Объект Analysis не найден в проекте.")

        # 3. Проверка наличия обязательных Named Selections из конфигов
        # (Предполагаем структуру в json, где перечислены требуемые NS)
        if "structure_type" in self.context.configs:
            struct_config = self.context.configs["structure_type"]
            
            # Пример проверки NS для граничных условий
            if "boundary_conditions" in struct_config:
                for bc in struct_config["boundary_conditions"]:
                    ns_name = bc.get("named_selection")
                    if ns_name and not self._named_selection_exists(ns_name):
                        errors.append(u"Named Selection '{0}' (для BC) не найден в дереве модели.".format(ns_name))

            # Пример проверки NS для болтов
            if "bolts" in struct_config:
                for bolt in struct_config["bolts"]:
                    ns_name = bolt.get("named_selection")
                    if ns_name and not self._named_selection_exists(ns_name):
                        errors.append(u"Named Selection '{0}' (для болта) не найден в дереве модели.".format(ns_name))

        # Итоговая проверка результатов валидации
        if errors:
            self.log.error(u"Валидация НЕ ПРОЙДЕНА. Обнаружены ошибки:")
            for err in errors:
                self.log.error(u" - {0}".format(err))
            raise Exception(u"Критическая ошибка валидации модели. Дальнейшая работа остановлена.")
        
        self.log.info(u"Валидация настроек модели успешно завершена.")
        return True

    def _named_selection_exists(self, name):
        """
        Проверяет существование Named Selection в модели по имени.
        """
        try:
            # В ANSYS Mechanical API доступ к NS через Model.NamedSelections
            for ns in self.context.model.NamedSelections:
                if ns.Name == name:
                    return True
            return False
        except Exception as e:
            self.log.warning(u"Ошибка при проверке Named Selection '{0}': {1}".format(name, e))
            return False
