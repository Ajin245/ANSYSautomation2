# -*- coding: utf-8 -*-
"""Преднатяг болтов (FR-8).

Логика извлечена из ``v2/src/Mechanical/analysis_manager.py:229-292``
(``_setup_bolt_pretensions`` и ``_create_bolt_pretension``). Идея отдельного
менеджера и шаблон имени Named Selection ``gu_bolt*_f`` — из
``v1/managers/bolt_manager.py:9-67``; ``bolt_database`` v1 не используется
(Q10): единственный источник момента затяжки — ``structure_type_XXX.json ->
torque_nm``.

Формула преднатяга живёт только в ``pretension.py`` (Q6, ветвь A):
``T / (0.37 * d / 1000)``. Здесь — ANSYS-обвязка и ничего больше, чтобы формула
не разъезжалась между модулями.

В 21R1 ``BoltLoadDefineBy`` не содержит ``Torque`` (RESEARCH-ANSYS-API §3.10),
поэтому момент заранее пересчитывается в силу, а в API уходит уже ``Quantity``
в ньютонах; начиная со второго шага болт блокируется (``Lock``), как в v2.
"""

from Mechanical import pretension

# Имена NS болтов в Mechanical: gu_bolt..._f (v1 и v2 используют один шаблон).
BOLT_NS_PREFIX = "gu_bolt"
BOLT_NS_SUFFIX = "_f"

# С какого шага болт блокируется: шаг 1 — затяжка, шаги 2..N — Lock (v2:283-285).
LOCK_FROM_STEP = 2


class BoltManager(object):
    """Создаёт объекты Bolt Pretension по моменту затяжки из конфига."""

    def __init__(self, context):
        """Инициализация менеджера болтов.

        Args:
            context (ProjectContext): Контекст проекта (модель, анализ, конфиги).
        """
        self.context = context
        self.log = context.log
        self.analysis = context.analysis
        self.model = context.model

    def setup_bolt_pretensions(self):
        """Настраивает преднатяг всех болтов ``gu_bolt*_f``.

        Момент берётся из ``structure_type.torque_nm`` по диаметру болта, диаметр —
        из имени Named Selection (``mbolt8`` или ``gu_bolt8_f``); сама формула —
        ``pretension.torque_to_pretension``.
        """
        if not self.analysis:
            self.log.error(u"Объект Analysis не найден. Преднатяг болтов невозможен.")
            return

        try:
            ns_objects = self._named_selections()
            bolt_ns = [ns for ns in ns_objects if self._is_bolt_ns(ns)]
            if not bolt_ns:
                self.log.debug(u"Named Selections болтов (gu_bolt*_f) не найдены.")
                return

            torque_data = self.context.configs.get("structure_type", {}).get("torque_nm", {})
            # v2 брал один диаметр из первого NS с mboltNN и применял его ко всем
            # болтам. Здесь диаметр сначала ищется в имени самого болта, и только
            # если его там нет — берётся общий по модели (поведение v2).
            default_diameter = pretension.select_bolt_diameter(ns_objects)

            for ns_obj in bolt_ns:
                self._setup_single_bolt(ns_obj, torque_data, default_diameter)

        except Exception as e:
            self.log.warning(u"Ошибка при настройке болтов: {0}".format(e))

    def _setup_single_bolt(self, ns_obj, torque_data, default_diameter):
        """Считает преднатяг для одного болта и создаёт ``BoltPretension``."""
        try:
            diameter = pretension.select_bolt_diameter([ns_obj])
            if diameter is None:
                diameter = default_diameter

            if diameter is None:
                self.log.warning(
                    u"Не найден диаметр болта для '{0}' (ни mboltNN, ни boltNN).".format(
                        ns_obj.Name))
                return

            torque = pretension.select_torque(torque_data, diameter)
            preload_n = pretension.torque_to_pretension(torque, diameter)
            if preload_n is None:
                self.log.warning(
                    u"Момент затяжки для диаметра {0} не найден; болт '{1}' пропущен.".format(
                        diameter, ns_obj.Name))
                return

            self._create_bolt_pretension(ns_obj, preload_n, torque, diameter)
        except Exception as e:
            self.log.warning(u"Ошибка при создании преднатяга для '{0}': {1}".format(
                ns_obj.Name, e))

    def _create_bolt_pretension(self, ns_obj, preload_n, torque, diameter):
        """Создаёт объект Bolt Pretension с преднатягом ``preload_n`` (Н)."""
        bolt_load_define_by = self._bolt_load_define_by()
        if bolt_load_define_by is None:
            return

        Quantity = self.context.Quantity
        if not Quantity:
            self.log.error(u"Класс Quantity не доступен в контексте ProjectContext.")
            return

        bolt_item = self.analysis.AddBoltPretension()
        bolt_item.Location = ns_obj
        bolt_item.Name = u"Bolt_{0}".format(ns_obj.Name)
        bolt_item.Preload.Output.SetDiscreteValue(0, Quantity(preload_n, "N"))

        steps = int(self.analysis.AnalysisSettings.NumberOfSteps)
        for step in range(LOCK_FROM_STEP, steps + 1):
            bolt_item.SetDefineBy(step, bolt_load_define_by.Lock)

        self.log.debug(
            u"Настроен болт {0}: момент {1} Нм, диаметр {2} мм -> преднатяг {3:.1f} Н".format(
                ns_obj.Name, torque, diameter, preload_n))

    def _bolt_load_define_by(self):
        """Перечисление ``BoltLoadDefineBy`` из контекста или из Ansys Enums."""
        enum = self.context.enums.get("BoltLoadDefineBy")
        if enum:
            return enum

        try:
            from Ansys.Mechanical.DataModel.Enums import BoltLoadDefineBy
            return BoltLoadDefineBy
        except ImportError:
            self.log.error(u"Enum BoltLoadDefineBy не доступен.")
            return None

    def _named_selections(self):
        """Список Named Selections модели (пустой список, если API недоступен)."""
        if not self.model:
            self.log.warning(u"Объект Model не найден. Named Selections недоступны.")
            return []

        try:
            children = self.model.NamedSelections.Children
        except Exception as e:
            self.log.warning(u"Named Selections недоступны: {0}".format(e))
            return []

        return list(children or [])

    def _is_bolt_ns(self, ns_obj):
        """True, если имя NS соответствует шаблону ``gu_bolt*_f``."""
        name = getattr(ns_obj, "Name", u"") or u""
        lowered = name.lower()
        return lowered.startswith(BOLT_NS_PREFIX) and lowered.endswith(BOLT_NS_SUFFIX)
