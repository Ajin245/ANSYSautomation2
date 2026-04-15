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
            steps = scenario.get("steps", 3) # Устанавливаем 3 шага, как в конфиге
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
        Применяет закрепления (Fixed Support) и удаленные перемещения (Remote Displacement) на основе конфигурации.
        """
        try:
            struct_config = self.context.configs.get("structure_type", {})
            bc_settings = struct_config.get("boundary_conditions", {})
            Quantity = self.context.Quantity # Получаем Quantity из контекста
            
            if not Quantity:
                self.log.error(u"Класс Quantity не доступен в контексте ProjectContext.")
                raise Exception(u"Quantity class not available.")

            # --- Обработка Fixed Support ---
            fixed_support_ns_name = bc_settings.get("fixed_support")
            if fixed_support_ns_name:
                ns_obj = self._get_named_selection(fixed_support_ns_name)
                if not ns_obj:
                    self.log.warning(u"NS для Fixed Support не найден: {0}".format(fixed_support_ns_name))
                else:
                    fixed = self.analysis.AddFixedSupport()
                    fixed.Name = u"Fixed_{0}".format(fixed_support_ns_name)
                    fixed.Location = ns_obj
                    self.log.debug(u"Добавлена опора Fixed на '{0}'".format(fixed_support_ns_name))
            else:
                self.log.debug(u"Fixed Support не задан в конфигурации.")

            # --- Обработка Remote Displacement ---
            remote_displacement_config = bc_settings.get("remote_displacement")
            if remote_displacement_config and isinstance(remote_displacement_config, dict):
                remote_displacement_ns_name = remote_displacement_config.get("ns_name")
                if not remote_displacement_ns_name:
                    self.log.warning(u"Имя Named Selection для Remote Displacement не задано в конфигурации.")
                else:
                    ns_obj = self._get_named_selection(remote_displacement_ns_name)
                    if not ns_obj:
                        self.log.warning(u"NS для Remote Displacement не найден: {0}".format(remote_displacement_ns_name))
                    else:
                        remote = self.analysis.AddRemoteDisplacement()
                        remote.Name = u"RemoteDisp_{0}".format(remote_displacement_ns_name)
                        remote.Location = ns_obj
                        self.log.info(u"Добавлен Remote Displacement на '{0}'".format(remote_displacement_ns_name))
                        
                        steps = int(self.analysis.AnalysisSettings.NumberOfSteps)
                        time_points = [Quantity(i, "s") for i in range(steps + 1)]

                        # --- Настройка вращений ---
                        rotation_settings = remote_displacement_config.get("rotation", {})
                        if rotation_settings:
                            for rot_axis, rot_val in rotation_settings.iteritems():
                                if rot_val is not None:
                                    rot_values = [Quantity(float(rot_val), "rad")] * (steps + 1)
                                    # Динамическое присвоение по имени
                                    if rot_axis.lower() == "rx":
                                        remote.RotationX.Inputs[0].DiscreteValues = time_points
                                        remote.RotationX.Output.DiscreteValues = rot_values
                                        self.log.debug(u"Установлен RX: {0} [rad] для '{1}'".format(rot_val, remote_displacement_ns_name))
                                    
                                    elif rot_axis.lower() == "ry":
                                        remote.RotationY.Inputs[0].DiscreteValues = time_points
                                        remote.RotationY.Output.DiscreteValues = rot_values
                                        self.log.debug(u"Установлен RY: {0} [rad] для '{1}'".format(rot_val, remote_displacement_ns_name))
                                    
                                    elif rot_axis.lower() == "rz":
                                        remote.RotationZ.Inputs[0].DiscreteValues = time_points
                                        remote.RotationZ.Output.DiscreteValues = rot_values
                                        self.log.debug(u"Установлен RZ: {0} [rad] для '{1}'".format(rot_val, remote_displacement_ns_name))
                                else:
                                    self.log.debug(u"Вращение {0} не задано в конфигурации для '{1}'. Пропускаем.".format(rot_axis, remote_displacement_ns_name))

                        # --- Настройка перемещений ---
                        translation_settings = remote_displacement_config.get("translation", {})
                        if translation_settings:
                            for trans_axis, trans_val in translation_settings.iteritems():
                                if trans_val is not None:
                                    # Получаем единицы длины из project_settings
                                    length_unit = self.context.configs.get("project_settings", {}).get("units", {}).get("length", "mm")
                                    trans_values = [Quantity(float(trans_val), length_unit)] * (steps + 1)
                                    # Динамическое присвоение по имени
                                    if trans_axis.lower() == "ux":
                                        remote.XComponent.Inputs[0].DiscreteValues = time_points
                                        remote.XComponent.Output.DiscreteValues = trans_values
                                        self.log.debug(u"Установлен UX: {0} для '{1}'".format(trans_val, remote_displacement_ns_name))
                                    elif trans_axis.lower() == "uy":
                                        remote.YComponent.Inputs[0].DiscreteValues = time_points
                                        remote.YComponent.Output.DiscreteValues = trans_values
                                        self.log.debug(u"Установлен UY: {0} для '{1}'".format(trans_val, remote_displacement_ns_name))
                                    elif trans_axis.lower() == "uz":
                                        remote.ZComponent.Inputs[0].DiscreteValues = time_points
                                        remote.ZComponent.Output.DiscreteValues = trans_values
                                        self.log.debug(u"Установлен UZ: {0} для '{1}'".format(trans_val, remote_displacement_ns_name))
                                else:
                                    self.log.debug(u"Перемещение {0} не задано в конфигурации для '{1}'. Пропускаем.".format(trans_axis, remote_displacement_ns_name))

                        if not rotation_settings and not translation_settings:
                            self.log.debug(u"Ограничения вращения и перемещения не заданы в конфигурации для Remote Displacement '{0}'.".format(remote_displacement_ns_name))
            else:
                self.log.debug(u"Remote Displacement не задан в конфигурации или имеет некорректную структуру.")
                    
        except Exception as e:
            self.log.warning(u"Ошибка при применении ГУ: {0}".format(e))

    def _apply_loads(self):
        """
        Применяет силы на основе конфигурации для NS 'gu_force' с учетом шагов нагружения.
        """
        try:
            struct_config = self.context.configs.get("structure_type", {})
            loads_config = struct_config.get("loads", {})
            scenario = self.context.configs.get("analysis_scenarios", {}).get("standard_sequence", {})
            Quantity = self.context.Quantity
            
            # Определяем номер исполнения из контекста
            execution_no = getattr(self.context, "execution_no", None)
            if not execution_no or execution_no not in loads_config:
                self.log.warning(u"Данные нагрузок для исполнения {0} не найдены.".format(execution_no))
                return

            forces = loads_config[execution_no].get("nominal_forces", {})
            load_factors = scenario.get("load_factors", [1.0])
            ns_obj = self._get_named_selection("gu_force")
            
            if ns_obj and forces:
                force = self.analysis.AddForce()
                force.Location = ns_obj
                force.DefineBy = LoadDefineBy.Components
                
                steps = int(self.analysis.AnalysisSettings.NumberOfSteps)
                time_points = [Quantity(i, "s") for i in range(steps + 1)]
                
                # Добавляем 0 шаг [0.0] + остальные факторы из сценария [0.5, 1.0, 1.5]
                factors = [0.0] + load_factors
                
                # Настройка компонентов силы
                for axis, component in [("fx", force.XComponent), 
                                       ("fy", force.YComponent), 
                                       ("fz", force.ZComponent)]:
                    nominal_val = forces.get(axis, 0)
                    output_values = [Quantity(nominal_val * f, "N") for f in factors]
                    
                    component.Inputs[0].DiscreteValues = time_points
                    component.Output.DiscreteValues = output_values
                
                self.log.info(u"Нагрузка Force задана для 'gu_force' (FX:{0}, FY:{1}, FZ:{2}, Factors:{3})".format(forces.get("fx"), forces.get("fy"), forces.get("fz"), factors))
            else:
                self.log.warning(u"Не удалось настроить нагрузку: NS 'gu_force' или данные сил отсутствуют.")
                    
        except Exception as e:
            self.log.warning(u"Ошибка при применении нагрузок: {0}".format(e))

    def _setup_bolt_pretensions(self):
        """
        Создает объекты Bolt Pretension и рассчитывает усилие затяжки по моменту.
        """
        try:
            struct_config = self.context.configs.get("structure_type", {})
            torque_data = struct_config.get("torque_nm", {})
            
            # В ANSYS Mechanical болты ищутся по Named Selections типа 'gu_bolt...'
            for ns in self.model.NamedSelections.Children:
                if ns.Name.lower().startswith("gu_bolt"):
                    self._create_bolt_pretension(ns, torque_data)
                    
        except Exception as e:
            self.log.warning(u"Ошибка при настройке болтов: {0}".format(e))

    def _create_bolt_pretension(self, ns_obj, torque_data):
        """
        Рассчитывает преднатяг для конкретного болта.
        """
        try:
            import re
            match = re.search(r"m(\d+)", ns_obj.Name.lower())
            if not match:
                return
            
            diameter = int(match.group(1))
            torque = torque_data.get(str(diameter)) or torque_data.get(diameter)
            
            if torque:
                preload_n = (torque) / (0.2 * diameter/1000)
                
                bolt = self.analysis.AddBoltPretension()
                bolt.Location = ns_obj
                bolt.Name = u"Bolt_{0}".format(ns_obj.Name)
                
                bolt.DefineBy = bolt.DefineBy.Load
                # Установка значения для шага (обычно преднатяг на первом шаге)
                # bolt.Preload.Output.SetData(preload_n) 
                
                self.log.debug(u"Настроен болт {0}: момент {1} Нм -> преднатяг {2:.1f} Н".format(ns_obj.Name, torque, preload_n))
                
        except Exception as e:
            self.log.warning(u"Ошибка при создании преднатяга для '{0}': {1}".format(ns_obj.Name, e))

    def _get_named_selection(self, name):
        """
        Возвращает объект Named Selection по имени."""
        for ns in self.model.NamedSelections.Children:
            if ns.Name == name:
                return ns
        return None
