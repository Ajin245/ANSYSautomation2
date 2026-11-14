# -*- coding: utf-8 -*-

from Mechanical.bolt_manager import BoltManager


# Значение ``remote_displacement`` бывает двух видов: строка — имя Named
# Selection (так задан 8946), словарь — расширенная настройка с ``ns_name``,
# ``rotation`` и ``translation`` (PLAN-MERGE §3.4).
try:  # IronPython 2.7
    _STRING_TYPES = (basestring,)
except NameError:  # python3: только статические проверки и тесты
    _STRING_TYPES = (str,)


def _iteritems(mapping):
    """Пары ключ-значение: ``.iteritems()`` в IronPython 2.7, ``.items()`` в python3.

    Модуль проверяется моками под python3, а продуктовый код исполняется на
    Python 2.7 (``RULES.md`` требует ``iteritems``), поэтому выбор — по наличию метода.
    """
    if hasattr(mapping, "iteritems"):
        return mapping.iteritems()
    return mapping.items()


def parse_remote_displacement(value):
    """Разбирает значение ``remote_displacement`` из конфига (FR-6).

    Args:
        value: строка (имя Named Selection) или словарь с ``ns_name`` и
            необязательными ``rotation``/``translation``.

    Returns:
        tuple: ``(ns_name, settings)``; ``settings`` пустой для строки.

    Raises:
        ValueError: значение пустое или имеет неподдерживаемый тип.
    """
    if isinstance(value, _STRING_TYPES):
        name = value.strip()
        if not name:
            raise ValueError(u"Remote Displacement: пустое имя Named Selection.")
        return name, {}

    if isinstance(value, dict):
        name = value.get("ns_name")
        if not name:
            raise ValueError(
                u"Remote Displacement: в словаре не задан ключ 'ns_name'.")
        return name, value

    raise ValueError(
        u"Remote Displacement: ожидается строка или словарь, получено {0}: {1}".format(
            type(value).__name__, value))


class AnalysisManager:
    """
    Класс для управления граничными условиями, нагрузками и настройками анализа в ANSYS Mechanical.
    Настраивает шаги нагружения; преднатяг болтов делегирует ``BoltManager`` (FR-8).
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
        self.bolt_manager = BoltManager(context)

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

        # 4. Болты (Преднатяг) — отдельный менеджер (FR-8)
        self.bolt_manager.setup_bolt_pretensions()

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

            # --- Обработка Remote Displacement (FR-6, PLAN-MERGE §3.4) ---
            # Значение в конфиге бывает строкой (имя Named Selection, как у 8946)
            # или словарём с ``ns_name``/``rotation``/``translation``.
            self._apply_remote_displacement(bc_settings)

        except ValueError:
            # Некорректный конфиг ГУ — ошибка в данных, а не сбой API ANSYS:
            # пробрасываем наверх (QA-2, P1: условие нельзя терять молча).
            raise
        except Exception as e:
            self.log.warning(u"Ошибка при применении ГУ: {0}".format(e))

    def _apply_remote_displacement(self, bc_settings):
        """Применяет Remote Displacement по значению из конфига (FR-6).

        Строка трактуется как имя Named Selection (так задан 8946), словарь —
        как расширенная настройка с ``ns_name``/``rotation``/``translation``.
        Иное значение — ``ValueError`` из ``parse_remote_displacement``.

        Args:
            bc_settings (dict): секция ``boundary_conditions`` конфига конструкции.

        Raises:
            ValueError: значение ``remote_displacement`` не строка и не словарь.
        """
        remote_displacement_config = bc_settings.get("remote_displacement")
        if remote_displacement_config is None:
            self.log.debug(u"Remote Displacement не задан в конфигурации.")
            return

        ns_name, settings = parse_remote_displacement(remote_displacement_config)
        Quantity = self.context.Quantity

        try:
            ns_obj = self._get_named_selection(ns_name)
            if not ns_obj:
                self.log.warning(u"NS для Remote Displacement не найден: {0}".format(ns_name))
                return

            remote = self.analysis.AddRemoteDisplacement()
            remote.Name = u"RemoteDisp_{0}".format(ns_name)
            remote.Location = ns_obj
            self.log.info(u"Добавлен Remote Displacement на '{0}'".format(ns_name))

            rotation_settings = settings.get("rotation", {})
            translation_settings = settings.get("translation", {})
            if not rotation_settings and not translation_settings:
                self.log.debug(
                    u"Ограничения вращения и перемещения не заданы для Remote Displacement '{0}'.".format(ns_name))
                return

            steps = int(self.analysis.AnalysisSettings.NumberOfSteps)
            time_points = [Quantity(i, "s") for i in range(steps + 1)]

            # --- Настройка вращений ---
            for rot_axis, rot_val in _iteritems(rotation_settings):
                if rot_val is None:
                    self.log.debug(u"Вращение {0} не задано в конфигурации для '{1}'. Пропускаем.".format(rot_axis, ns_name))
                    continue
                rot_values = [Quantity(float(rot_val), "rad")] * (steps + 1)
                axis = rot_axis.lower()
                if axis == "rx":
                    remote.RotationX.Inputs[0].DiscreteValues = time_points
                    remote.RotationX.Output.DiscreteValues = rot_values
                elif axis == "ry":
                    remote.RotationY.Inputs[0].DiscreteValues = time_points
                    remote.RotationY.Output.DiscreteValues = rot_values
                elif axis == "rz":
                    remote.RotationZ.Inputs[0].DiscreteValues = time_points
                    remote.RotationZ.Output.DiscreteValues = rot_values
                else:
                    self.log.warning(u"Неизвестная ось вращения '{0}' для Remote Displacement '{1}'.".format(rot_axis, ns_name))
                    continue
                self.log.debug(u"Установлен {0}: {1} [rad] для '{2}'".format(rot_axis.upper(), rot_val, ns_name))

            # --- Настройка перемещений ---
            length_unit = (self.context.configs.get("project_settings", {})
                           .get("units", {}).get("length", "mm"))
            for trans_axis, trans_val in _iteritems(translation_settings):
                if trans_val is None:
                    self.log.debug(u"Перемещение {0} не задано в конфигурации для '{1}'. Пропускаем.".format(trans_axis, ns_name))
                    continue
                trans_values = [Quantity(float(trans_val), length_unit)] * (steps + 1)
                axis = trans_axis.lower()
                if axis == "ux":
                    remote.XComponent.Inputs[0].DiscreteValues = time_points
                    remote.XComponent.Output.DiscreteValues = trans_values
                elif axis == "uy":
                    remote.YComponent.Inputs[0].DiscreteValues = time_points
                    remote.YComponent.Output.DiscreteValues = trans_values
                elif axis == "uz":
                    remote.ZComponent.Inputs[0].DiscreteValues = time_points
                    remote.ZComponent.Output.DiscreteValues = trans_values
                else:
                    self.log.warning(u"Неизвестная ось перемещения '{0}' для Remote Displacement '{1}'.".format(trans_axis, ns_name))
                    continue
                self.log.debug(u"Установлен {0}: {1} {2} для '{3}'".format(trans_axis.upper(), trans_val, length_unit, ns_name))

        except Exception as e:
            self.log.warning(u"Ошибка при применении Remote Displacement: {0}".format(e))

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

                load_define_by = self.context.enums.get("LoadDefineBy")
                if load_define_by:
                    force.DefineBy = load_define_by.Components
                else:
                    try:
                        from Ansys.Mechanical.DataModel.Enums import LoadDefineBy
                        force.DefineBy = LoadDefineBy.Components
                    except ImportError:
                        self.log.error(u"Enum LoadDefineBy не доступен.")
                
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

    def _get_named_selection(self, name):
        """
        Возвращает объект Named Selection по имени."""
        for ns in self.model.NamedSelections.Children:
            if ns.Name == name:
                return ns
        return None
