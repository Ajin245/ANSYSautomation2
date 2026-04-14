# -*- coding: utf-8 -*-

class MeshManager:
    """
    Класс для управления настройками сетки КЭ в ANSYS Mechanical.
    Применяет методы мешинга (Sweep, MultiZone) и размеры элементов на основе Named Selections.
    """
    def __init__(self, context):
        """
        Инициализация менеджера сетки.

        Args:
            context (ProjectContext): Контекст текущего проекта.
        """
        self.context = context
        self.log = context.log
        self.model = context.model
        self.enums = context.enums

    def apply_mesh_settings(self):
        """
        Основной метод для применения настроек сетки. Проходит по всем Named Selections
        в модели и применяет наиболее подходящее правило из конфигурации.
        """
        self.log.info(u"Запуск настройки сетки КЭ...")
        
        if not self.model:
            self.log.error(u"Модель не найдена. Настройка сетки невозможна.")
            return

        settings = self.context.configs.get("mesh_config")
        if not settings:
            self.log.warning(u"Настройки сетки не найдены в конфигурации (mesh_config).")
            return

        mesh_rules = settings.get("mesh_settings", {})
        mesh = self.model.Mesh
        
        # Получаем все Named Selections
        try:
            named_selections = self.model.NamedSelections.Children
            self.log.debug(u"Найдено Named Selections: {0}".format(named_selections.Count))
            for ns in named_selections:
                # ВАЖНО: Пропускаем NS, которые начинаются с 'gu_' (используются для ГУ и нагрузок)
                ns_name = ns.Name
                if ns_name.lower().startswith("gu_"):
                    self.log.debug(u"ПРОПУСК NS '{0}' (префикс gu_)".format(ns_name))
                    continue
                    
                self.log.debug(u"Анализ NS: '{0}'".format(ns_name))
                ns_name_lower = ns_name.lower()
                best_rule_key = None
                
                # Ищем лучшее совпадение (самый длинный ключ правила, который входит в имя NS)
                for rule_key in mesh_rules.keys():
                    if rule_key.lower() in ns_name_lower:
                        if best_rule_key is None or len(rule_key) > len(best_rule_key):
                            best_rule_key = rule_key
                
                if best_rule_key:
                    self.log.info(u"Сопоставлено: NS '{0}' -> Правило '{1}'".format(ns_name, best_rule_key))
                    self._apply_mesh_to_ns(mesh, ns, mesh_rules[best_rule_key])
                else:
                    self.log.warning(u"Для NS '{0}' не найдено подходящих правил в mesh_config.".format(ns_name))

        except Exception as e:
            self.log.error(u"Ошибка при обходе Named Selections для сетки: {0}".format(e))

        self.log.info(u"Настройка сетки КЭ завершена.")

    def _apply_mesh_to_ns(self, mesh_obj, ns_obj, params):
        """
        Применяет метод и размер сетки к конкретному Named Selection.
        """
        try:
            ns_name = ns_obj.Name
            mesh_coef = params.get("meshCoef")
            mesh_method_type = params.get("meshMethod")
            mesh_algorithm = params.get("meshAlgorithm")
            element_order = params.get("elementOrder")
            
            # Получаем единицы измерения из проекта
            length_unit = self.context.configs.get("project_settings", {}).get("units", {}).get("length", "mm")
            
            # Извлекаем число из конца имени NS (например, 'truba245' -> 245)
            import re
            match = re.search(r"(\d+\.?\d*)$", ns_name)
            
            # 1. Добавление Sizing (Размер элемента)
            if mesh_coef:
                sizing = mesh_obj.AddSizing()
                sizing.Name = u"Sizing_{0}".format(ns_name)
                sizing.Location = ns_obj
                
                if match:
                    val = float(match.group(1))
                    element_size = round((val / mesh_coef), 2)
                    
                    if self.context.Quantity:
                        sizing.ElementSize = self.context.Quantity(element_size, length_unit)
                    else:
                        sizing.ElementSize = element_size
                    
                    self.log.info(u"Sizing '{0}': {1} {2}".format(ns_name, element_size, length_unit))
                else:
                    self.log.warning(u"Не удалось извлечь число из '{0}' для Sizing".format(ns_name))

            # 2. Добавление Method (Sweep, MultiZone и т.д.)
            if mesh_method_type:
                method = mesh_obj.AddAutomaticMethod()
                method.Name = u"Method_{0}_{1}".format(mesh_method_type, ns_name)
                method.Location = ns_obj
                
                # Установка типа метода
                mt_enum = self.enums.get("MethodType")
                if mt_enum:
                    if "Sweep" in mesh_method_type:
                        method.Method = mt_enum.Sweep
                        # Настройка алгоритма для Sweep
                        if mesh_algorithm == "Axisymmetric":
                            ma_enum = self.enums.get("MeshMethodAlgorithm")
                            if ma_enum:
                                method.Algorithm = ma_enum.Axisymmetric
                    elif "MultiZone" in mesh_method_type:
                        method.Method = mt_enum.MultiZone
                
                # Настройка порядка элементов (Element Order)
                if element_order:
                    eo_enum = self.enums.get("ElementOrder")
                    if eo_enum:
                        if element_order == "Quadratic":
                            method.ElementOrder = eo_enum.Quadratic
                        elif element_order == "Linear":
                            method.ElementOrder = eo_enum.Linear
                        elif element_order == "ProgramControlled":
                            method.ElementOrder = eo_enum.ProgramControlled

                self.log.debug(u"Метод '{0}' для '{1}' настроен (Algorithm: {2})".format(mesh_method_type, ns_name, mesh_algorithm))

        except Exception as e:
            self.log.error(u"Ошибка настройки сетки '{0}': {1}".format(ns_name, str(e)))
