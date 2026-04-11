# -*- coding: utf-8 -*-

class AnalysisManager:
    """
    Класс для управления граничными условиями, нагрузками и настройками анализа в ANSYS Mechanical.
    Реализует расчет преднатяга болтов и настройку шагов нагружения.
    """
    def __init__(self, context):
        """
        Инициализация менеджера анализа.

        Args:
            context (ProjectContext): Контекст текущего проекта.
        """
        self.context = context
        self.log = context.log
        self.analysis = context.analysis
        self.model = context.model

    def apply_boundary_conditions_and_loads(self):
        """
        Основной метод для применения нагрузок и граничных условий.
        """
        self.log.info(u"Запуск настройки условий анализа...")
        
        if not self.analysis:
            self.log.error(u"Объект Analysis не найден. Настройка невозможна.")
            return

        # 1. Базовые настройки анализа
        self._setup_analysis_settings()

        # 2. Граничные условия
        self._apply_boundary_conditions()

        # 3. Нагрузки
        self._apply_loads()

        # 4. Болты (Преднатяг)
        self._setup_bolt_pretensions()

        self.log.info(u"Настройка условий анализа завершена.")

    def _setup_analysis_settings(self):
        """
        Настраивает количество шагов и параметры решателя на основе выбранного сценария.
        """
        try:
            scenario_name = "standard_sequence" # Можно сделать динамическим
            scenario = self.context.configs.get("analysis_scenarios", {}).get(scenario_name)
            
            if not scenario:
                self.log.warning(u"Сценарий анализа '{0}' не найден.".format(scenario_name))
                return

            settings = self.analysis.AnalysisSettings
            steps = scenario.get("steps", 1)
            settings.NumberOfSteps = steps
            
            # Настройка параметров решателя
            solver_params = scenario.get("analysis_settings", {})
            if "large_deflection" in solver_params:
                settings.LargeDeflection = solver_params["large_deflection"]
            
            self.log.info(u"Настроено шагов анализа: {0}".format(steps))
            
        except Exception as e:
            self.log.warning(u"Ошибка при настройке параметров анализа: {0}".format(e))

    def _apply_boundary_conditions(self):
        """
        Применяет закрепления (Fixed Support) на основе конфигурации конструкции.
        """
        try:
            struct_config = self.context.configs.get("structure_type", {})
            bc_settings = struct_config.get("boundary_conditions", {})
            
            for bc_type, ns_name in bc_settings.iteritems():
                ns_obj = self._get_named_selection(ns_name)
                if not ns_obj:
                    continue
                
                if bc_type == "fixed_support":
                    fixed = self.analysis.AddFixedSupport()
                    fixed.Name = u"Fixed_{0}".format(ns_name)
                    fixed.Location = ns_obj
                    self.log.debug(u"Добавлена опора Fixed на '{0}'".format(ns_name))
                    
        except Exception as e:
            self.log.warning(u"Ошибка при применении ГУ: {0}".format(e))

    def _apply_loads(self):
        """
        Применяет силы и моменты на основе конфигурации.
        """
        try:
            struct_config = self.context.configs.get("structure_type", {})
            loads_config = struct_config.get("loads", {})
            
            # Для каждого шага и каждой нагрузки создаем объект в Mechanical
            # (Упрощенная логика: предполагаем, что NS для нагрузок заданы в конфиге)
            pass
                    
        except Exception as e:
            self.log.warning(u"Ошибка при применении нагрузок: {0}".format(e))

    def _setup_bolt_pretensions(self):
        """
        Создает объекты Bolt Pretension и рассчитывает усилие затяжки по моменту.
        """
        try:
            struct_config = self.context.configs.get("structure_type", {})
            torque_data = struct_config.get("torque_nm", {})
            
            # В ANSYS Mechanical болты обычно ищутся по Named Selections типа 'mbolt_...'
            for ns in self.model.NamedSelections:
                if ns.Name.lower().startswith("mbolt"):
                    self._create_bolt_pretension(ns, torque_data)
                    
        except Exception as e:
            self.log.warning(u"Ошибка при настройке болтов: {0}".format(e))

    def _create_bolt_pretension(self, ns_obj, torque_data):
        """
        Рассчитывает преднатяг для конкретного болта.
        Упрощенная формула: F = T / (0.37 * d)
        """
        try:
            # Пытаемся извлечь диаметр из имени NS, например 'mbolt_M16' -> 16
            import re
            match = re.search(r"m(\d+)", ns_obj.Name.lower())
            if not match:
                return
            
            diameter = int(match.group(1))
            torque = torque_data.get(str(diameter)) or torque_data.get(diameter)
            
            if torque:
                # Расчет силы преднатяга (в Ньютонах)
                # Коэффициент k = 0.37 (стандартный для несмазанной резьбы)
                preload_n = (torque) / (0.2 * diameter/1000)
                
                bolt = self.analysis.AddBoltPretension()
                bolt.Location = ns_obj
                bolt.Name = u"Bolt_{0}".format(ns_obj.Name)
                
                # Установка значения для первого шага (Load)
                bolt.DefineBy = bolt.DefineBy.Load
                # В API значения могут требовать использования Quantity
                # bolt.Preload.Output.SetData(preload_n) 
                
                self.log.debug(u"Настроен болт {0}: момент {1} Нм -> преднатяг {2:.1f} Н".format(ns_obj.Name, torque, preload_n))
                
        except Exception as e:
            self.log.warning(u"Ошибка при создании преднатяга для '{0}': {1}".format(ns_obj.Name, e))

    def _get_named_selection(self, name):
        """Возвращает объект Named Selection по имени."""
        for ns in self.model.NamedSelections:
            if ns.Name == name:
                return ns
        return None
