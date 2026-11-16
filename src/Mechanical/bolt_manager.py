# -*- coding: utf-8 -*-
"""Преднатяг болтов (FR-8).

Источник преднатяга — конфиг болтов ``config/mechanical_configs/bolt_pretension.json``
(решение владельца 2026-11-14): там статичная таблица «диаметр резьбы → сила
затяжки» и значение ``default`` для диаметров, которых в таблице нет.
``torque_nm`` в ``structure_type_XXX.json`` больше не используется.

Правила (решения владельца):

* **основная проверка** — в геометрии есть тела болтов с именем ``mbolt<d>``
  (``mbolt10`` → резьба 10 мм). Нет таких тел — преднатяг не задаётся, в лог
  идёт предупреждение (это не ошибка расчёта);
* Named Selection ``gu_bolt<N>_f`` приходит из SpaceClaim и служит только
  поверхностью приложения нагрузки — номер в имени ничего не значит и для
  вычислений не нужен;
* диаметр берётся из имени тела болта, а не из имени Named Selection;
* шаг 1 — затяжка, шаги 2..N — ``Lock`` (поведение v2).

Модуль работает в ANSYS (Python 2.7 / IronPython), поэтому без f-строк,
``print`` без скобок допустим, ``.iteritems()`` вместо ``.items()``.
"""

from Mechanical import pretension
from Mechanical import utils

# Имена NS болтов: gu_bolt<N>_f — поверхность приложения нагрузки.
BOLT_NS_PREFIX = "gu_bolt"
BOLT_NS_SUFFIX = "_f"

# Префикс имён тел болтов: mbolt10 -> резьба 10 мм.
BOLT_BODY_PREFIX = "mbolt"

# С какого шага болт блокируется: шаг 1 — затяжка, шаги 2..N — Lock.
LOCK_FROM_STEP = 2


class BoltManager(object):
    """Создаёт объекты Bolt Pretension по силе затяжки из конфига болтов."""

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
        """Настраивает преднатяг болтов, если в модели есть тела ``mbolt*``."""
        if not self.analysis:
            self.log.error(u"Объект Analysis не найден. Преднатяг болтов невозможен.")
            return

        bolt_bodies = self._bolt_bodies()
        if not bolt_bodies:
            self.log.warning(
                u"Тела болтов с именем 'mbolt*' не найдены: преднатяг не задаётся.")
            return

        ns_objects = [ns for ns in self._named_selections() if self._is_bolt_ns(ns)]
        if not ns_objects:
            self.log.warning(
                u"Named Selections 'gu_bolt*_f' не найдены: преднатяг не задаётся.")
            return

        diameters = sorted(set(diameter for _name, diameter in bolt_bodies))
        if len(diameters) > 1:
            self.log.warning(
                u"В модели болты разных диаметров {0}: автоматическое сопоставление "
                u"тела и Named Selection не реализовано, преднатяг не задан.".format(
                    diameters))
            return

        diameter = diameters[0]
        config = self.context.configs.get("bolt_pretension", {}) or {}
        preload_n, source = pretension.select_pretension(config, diameter)
        if preload_n is None:
            self.log.warning(
                u"Для диаметра {0} мм нет силы затяжки ни в таблице, ни в default — "
                u"преднатяг не задан.".format(diameter))
            return

        self.log.info(
            u"Болты: диаметр {0} мм, сила затяжки {1} Н ({2}), тел {3}, NS {4}.".format(
                diameter, preload_n, source, len(bolt_bodies), len(ns_objects)))

        for ns_obj in ns_objects:
            self._create_bolt_pretension(ns_obj, preload_n, diameter)

    def has_bolt_bodies(self):
        """True, если в геометрии есть тела ``mbolt*`` (нужен шаг затяжки)."""
        return bool(self._bolt_bodies())

    def _bolt_bodies(self):
        """Список пар ``(имя тела, диаметр)`` по телам ``mbolt<d>``.

        Обход рекурсивный: ``Geometry.Children`` верхнего уровня — это группы
        (``SYS``, ``NIZ``), тела лежат внутри них (см. ``utils.iter_bodies``).
        """
        bodies = []
        if not self.model:
            return bodies

        try:
            found = utils.iter_bodies(self.model)
        except Exception as exc:
            self.log.warning(u"Геометрия недоступна: {0}".format(exc))
            return bodies

        for body in found:
            name = getattr(body, "Name", u"") or u""
            diameter = self._diameter_from_body(name)
            if diameter is not None:
                bodies.append((name, diameter))
        return bodies

    def _diameter_from_body(self, name):
        """Диаметр резьбы из имени тела ``mbolt<d>`` (``None``, если не оно)."""
        lowered = (name or u"").lower()
        if not lowered.startswith(BOLT_BODY_PREFIX):
            return None
        digits = u""
        for char in lowered[len(BOLT_BODY_PREFIX):]:
            if char.isdigit():
                digits += char
            else:
                break
        if not digits:
            return None
        return int(digits)

    def _create_bolt_pretension(self, ns_obj, preload_n, diameter):
        """Создаёт объект Bolt Pretension с преднатягом ``preload_n`` (Н)."""
        bolt_load_define_by = self._bolt_load_define_by()
        if bolt_load_define_by is None:
            return

        Quantity = self.context.Quantity
        if not Quantity:
            self.log.error(u"Класс Quantity не доступен в контексте ProjectContext.")
            return

        try:
            bolt_item = self.analysis.AddBoltPretension()
            bolt_item.Location = ns_obj
            bolt_item.Name = u"Bolt_{0}".format(getattr(ns_obj, "Name", u"?"))
            bolt_item.Preload.Output.SetDiscreteValue(0, Quantity(preload_n, "N"))

            steps = int(self.analysis.AnalysisSettings.NumberOfSteps)
            for step in range(LOCK_FROM_STEP, steps + 1):
                bolt_item.SetDefineBy(step, bolt_load_define_by.Lock)

            self.log.debug(
                u"Настроен болт {0}: диаметр {1} мм -> преднатяг {2} Н".format(
                    getattr(ns_obj, "Name", u"?"), diameter, preload_n))
        except Exception as exc:
            self.log.warning(u"Ошибка при создании преднатяга для '{0}': {1}".format(
                getattr(ns_obj, "Name", u"?"), exc))

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
        except Exception as exc:
            self.log.warning(u"Named Selections недоступны: {0}".format(exc))
            return []

        return list(children or [])

    def _is_bolt_ns(self, ns_obj):
        """True, если имя NS соответствует шаблону ``gu_bolt*_f``."""
        name = getattr(ns_obj, "Name", u"") or u""
        lowered = name.lower()
        return lowered.startswith(BOLT_NS_PREFIX) and lowered.endswith(BOLT_NS_SUFFIX)