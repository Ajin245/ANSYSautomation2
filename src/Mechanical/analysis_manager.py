# -*- coding: utf-8 -*-

from Mechanical.bolt_manager import BoltManager
from Mechanical import execution_parser


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
        """Задаёт число шагов (по числу режимов в конфиге) и параметры решателя."""
        scenario_name = "standard_sequence"
        scenario = self.context.configs.get("analysis_scenarios", {}).get(scenario_name) or {}

        cases = self._load_steps()

        settings = self.analysis.AnalysisSettings
        settings.NumberOfSteps = len(cases)

        solver_params = scenario.get("analysis_settings", {}) or {}
        if "large_deflection" in solver_params:
            settings.LargeDeflection = solver_params["large_deflection"]

        self.log.info(u"Настроено шагов анализа: {0} ({1})".format(
            len(cases), u", ".join(name for name, _values in cases)))

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

    # Методы создания момента, которые встречаются в разных релизах Mechanical.
    # Порядок — от наиболее вероятного; отсутствие всех = ошибка конфига.
    MOMENT_METHODS = ("AddMoment", "AddMomentLoad", "AddRemoteMoment")

    def _load_steps(self):
        """Шаги нагружения с промежуточным разгоном из сценария анализа.

        Возвращает пары ``(имя_шага, значения)``. При наличии тел болтов первым
        идёт шаг затяжки с нулевыми нагрузками (на нём работает только
        преднатяг), затем разгон 0.5xНУЭ (только для сходимости, в результаты
        не идёт), затем НУЭ и НУЭ+ПЗ.
        """
        struct_config = self.context.configs.get("structure_type", {}) or {}
        execution_no = getattr(self.context, "execution_no", None)
        cases = execution_parser.select_load_cases(struct_config, execution_no)
        scenario = self.context.configs.get("analysis_scenarios", {}).get(
            "standard_sequence", {}) or {}
        ramp_factor = scenario.get("ramp_factor")
        return execution_parser.build_load_steps(
            cases, ramp_factor, tightening=self.bolt_manager.has_bolt_bodies())

    def _apply_loads(self):
        """Применяет силы (и моменты, если они есть в конфиге) по шагам.

        Схема конфига: ``loads[<исполнение>].cases = {НУЭ: {...}, НУЭ+ПЗ: {...}}``;
        число шагов анализа равно числу режимов. Если нагрузок для исполнения
        нет — это ошибка, а не предупреждение: расчёт без нагрузок не имеет
        смысла (решение владельца, 2026-11-14).
        """
        struct_config = self.context.configs.get("structure_type", {}) or {}
        project_settings = self.context.configs.get("project_settings", {}) or {}
        load_ns_map = project_settings.get("load_named_selections", {}) or {}
        force_ns_name = load_ns_map.get("force", u"gu_force")
        moment_ns_name = load_ns_map.get("moment", u"gu_moment")

        execution_no = getattr(self.context, "execution_no", None)
        cases = self._load_steps()

        Quantity = self.context.Quantity
        if not Quantity:
            raise ValueError(u"Класс Quantity не доступен в контексте ProjectContext.")

        ns_force = self._get_named_selection(force_ns_name)
        if ns_force is None:
            raise ValueError(
                u"Named Selection '{0}' для силы не найдена в модели (имя задаётся "
                u"в project_settings.load_named_selections.force).".format(force_ns_name))

        steps = len(cases)
        time_points = [Quantity(i, "s") for i in range(1, steps + 1)]

        force = self.analysis.AddForce()
        # Имя с префиксом: повторный прогон удаляет объекты по префиксу.
        force.Name = u"Force_{0}".format(ns_force.Name if ns_force is not None else u"load")
        force.Location = ns_force
        self._set_define_by(force)

        x_component = force.XComponent
        y_component = force.YComponent
        z_component = force.ZComponent
        for axis, component in (("fx", x_component), ("fy", y_component),
                                ("fz", z_component)):
            values = [Quantity((case_values or {}).get(axis, 0), "N")
                      for _name, case_values in cases]
            component.Inputs[0].DiscreteValues = time_points
            component.Output.DiscreteValues = values

        self.log.info(u"Нагрузки для '{0}' (исполнение {1}, шагов {2}): {3}".format(
            force_ns_name, execution_no, steps,
            u", ".join(u"{0}={1},{2},{3}".format(
                name,
                (values or {}).get("fx", 0),
                (values or {}).get("fy", 0),
                (values or {}).get("fz", 0)) for name, values in cases)))

        if self._cases_have_moments(cases):
            self._apply_moments(cases, moment_ns_name, time_points)

    def _set_define_by(self, load_object):
        """Выставляет ``DefineBy = Components``, если перечисление доступно."""
        load_define_by = self.context.enums.get("LoadDefineBy")
        if load_define_by:
            load_object.DefineBy = load_define_by.Components
            return
        try:
            from Ansys.Mechanical.DataModel.Enums import LoadDefineBy
            load_object.DefineBy = LoadDefineBy.Components
        except ImportError:
            self.log.error(u"Enum LoadDefineBy не доступен.")

    def _cases_have_moments(self, cases):
        """True, если хотя бы в одном режиме заданы моменты."""
        for _name, values in cases:
            values = values or {}
            for axis in ("mx", "my", "mz"):
                if values.get(axis):
                    return True
        return False

    def _apply_moments(self, cases, moment_ns_name, time_points):
        """Применяет моменты: только если они есть в конфиге."""
        ns_moment = self._get_named_selection(moment_ns_name)
        if ns_moment is None:
            raise ValueError(
                u"В конфиге заданы моменты, но Named Selection '{0}' не найдена "
                u"(имя задаётся в project_settings.load_named_selections.moment).".format(moment_ns_name))

        method = None
        for name in self.MOMENT_METHODS:
            if hasattr(self.analysis, name):
                method = getattr(self.analysis, name)
                break
        if method is None:
            raise ValueError(
                u"В конфиге заданы моменты, но в этой версии Mechanical нет метода "
                u"их создания (проверены: {0}).".format(", ".join(self.MOMENT_METHODS)))

        Quantity = self.context.Quantity
        moment = method()
        moment.Location = ns_moment
        self._set_define_by(moment)

        assigned = 0
        for axis, attribute in (("mx", "XComponent"), ("my", "YComponent"),
                                ("mz", "ZComponent")):
            if not hasattr(moment, attribute):
                continue
            component = getattr(moment, attribute)
            values = [Quantity((case_values or {}).get(axis, 0), "N mm")
                      for _name, case_values in cases]
            component.Inputs[0].DiscreteValues = time_points
            component.Output.DiscreteValues = values
            assigned += 1

        if assigned == 0:
            raise ValueError(
                u"Объект момента создан, но у него нет компонент X/Y/Z; "
                u"задание моментов в этой сборке не подтверждено.")

        self.log.info(u"Моменты заданы на '{0}' (компонент: {1}).".format(
            moment_ns_name, assigned))


    def _get_named_selection(self, name):
        """
        Возвращает объект Named Selection по имени."""
        for ns in self.model.NamedSelections.Children:
            if ns.Name == name:
                return ns
        return None
