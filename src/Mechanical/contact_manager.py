# -*- coding: utf-8 -*-

# Болт и гайка — жёсткая пара: всегда Bonded, без исключений. Правило не
# переопределяется ни типом опоры (``support_types``), ни ``contact_settings``,
# ни правилом по умолчанию: резьбовое соединение не может считаться скользящим.
# Причина появления правила: при заданном ``support_type`` ветка общих правил
# ``contact_settings`` не вызывалась вовсе, и пара болт—гайка уходила в ``default``
# типа опоры (``Frictional``).
BOLT_NUT_CLASSES = (u"mbolt", u"mgaika")
BOLT_NUT_RULE = {
    "type": "Bonded",
    "interface_treatment": "AdjustToTouch",
}


def body_class(side):
    """Класс тела из стороны контакта: ``'SYS\\mbolt8 1'`` -> ``'mbolt'``.

    Args:
        side (str): имя тела (одна сторона контакта), регистр не важен.

    Returns:
        str: ``'mbolt'``, ``'mgaika'`` или ``None``, если класс другой.
    """
    if not side:
        return None
    tail = side.replace(u"/", u"\\").split(u"\\")[-1].strip().lower()
    for class_name in BOLT_NUT_CLASSES:
        if tail.startswith(class_name):
            return class_name
    return None


def is_bolt_nut_pair(left, right):
    """Пара «болт—гайка»: одна сторона ``mbolt*``, другая ``mgaika*``.

    Порядок сторон не важен; пара двух болтов или двух гаек парой не считается.

    Args:
        left (str): первая сторона контакта.
        right (str): вторая сторона контакта.

    Returns:
        bool: True, если это контакт болта с гайкой.
    """
    return set([body_class(left), body_class(right)]) == set(BOLT_NUT_CLASSES)


class ContactManager:
    """
    Класс для автоматизированной настройки и группировки контактов в ANSYS Mechanical.
    """
    def __init__(self, context):
        """
        Инициализация менеджера контактов.

        Args:
            context (ProjectContext): Контекст текущего проекта.
        """
        self.context = context
        self.log = context.log
        self.model = context.model

    def setup_contacts(self):
        """
        Основной метод для настройки контактов. Проходит по всем контактным регионам
        и применяет параметры на основе правил из конфигурации.
        """
        self.log.info(u"Запуск настройки контактов...")
        
        if not self.model:
            self.log.error(u"Модель не найдена. Настройка контактов невозможна.")
            return

        # Папки в дереве — по типу контакта (решение владельца, 2026-11-16).
        self.groups_to_collect = {
            "Bonded": [],
            "Frictional": [],
            "FrictOffset": []
        }

        settings = self.context.configs.get("contact_settings")
        support_rules = self._support_type_rules()
        if not settings and not support_rules:
            self.log.warning(u"Настройки контактов не найдены (ни contact_settings, ни support_types).")
            return
        if support_rules:
            self.log.info(u"Правила контактов из типа опоры '{0}'.".format(support_rules.get("name")))

        # Получаем все контактные группы
        try:
            connections = self.model.Connections
            if connections is None:
                raise Exception(u"Не удалось получить раздел Connections")
            contact_groups = connections.Children
            found_any = False
            for group in contact_groups:
                # В IronPython сравнение категорий может требовать ToString()
                if group.DataModelObjectCategory.ToString() == "ConnectionGroup":
                    self._process_contact_group(group, settings, support_rules)
                    found_any = True
            
            if found_any:
                self._create_tree_groups()
            else:
                self.log.warning(u"В дереве модели не найдено групп контактов (Contact Groups).")
                
        except Exception as e:
            self.log.error(u"Ошибка при доступе к контактам: {0}".format(e))

        self.log.info(u"Настройка контактов завершена.")

    def _support_type_rules(self):
        """Правила контактных пар из ``support_types[<support_type>]`` конфига конструкции.

        Почему по типу опоры: у скользящей направляющей одни пары должны быть
        Bonded (ребро, основание), а у других типов опор — иные. Держать это
        в общем ``contact_settings`` нельзя: правила конфликтуют по именам тел.

        Returns:
            dict: ``{"name": ..., "pairs": [...], "default": {...}, "friction_coefficient": ...}``
            или ``None``, если тип опоры не задан.
        """
        structure = self.context.configs.get("structure_type") or {}
        support_type = structure.get("support_type")
        if not support_type:
            return None

        support_types = structure.get("support_types") or {}
        rules = support_types.get(support_type)
        if not rules:
            self.log.warning(u"Тип опоры '{0}' не описан в support_types.".format(support_type))
            return None

        result = dict(rules)
        result["name"] = support_type
        return result

    def _process_contact_group(self, group, settings, support_rules=None):
        """
        Обрабатывает отдельную группу контактов.
        """
        contacts = group.Children
        contact_rules = (settings or {}).get("contact_settings", {})

        for contact in contacts:
            if contact.DataModelObjectCategory.ToString() == "ContactRegion":
                # Переименовываем контакт на основе тел, которые он соединяет
                try:
                    contact.RenameBasedOnDefinition()
                except:
                    pass
                # Болт—гайка проверяем до любых правил: пара Bonded безусловно.
                if self._is_bolt_nut_contact(contact):
                    self.log.info(u"Контакт '{0}': болт-гайка -> Bonded (жёсткое правило)".format(
                        contact.Name))
                    self._configure_contact(contact, dict(BOLT_NUT_RULE))
                elif support_rules:
                    self._apply_support_rules(contact, support_rules)
                else:
                    self._apply_rules_to_contact(contact, contact_rules)
                self._categorize_contact(contact)

    def _is_bolt_nut_contact(self, contact):
        """True, если контакт соединяет тело болта с телом гайки.

        Стороны берутся из имени контакта; если имя разобрать не удалось
        (переименование не сработало), проверяются классы прямо в имени —
        правило не должно зависеть от форматирования.
        """
        left, right = self._split_pair(contact.Name)
        if left and right:
            return is_bolt_nut_pair(left, right)
        name = (contact.Name or u"").lower()
        return all(class_name in name for class_name in BOLT_NUT_CLASSES)

    @staticmethod
    def _split_pair(name):
        """Имена двух тел из имени контакта: ``'Bonded - rebro1 To opora_niz22 2'``."""
        text = name or u""
        if u" - " in text:
            text = text.split(u" - ", 1)[1]
        if u" To " not in text:
            return None, None
        left, right = text.split(u" To ", 1)
        return left.strip().lower(), right.strip().lower()

    @staticmethod
    def _side_matches(side, patterns):
        """Совпадает ли сторона контакта хотя бы с одним паттерном."""
        if not patterns:
            return True
        for pattern in patterns:
            if pattern == "*":
                return True
            if pattern.lower() in side:
                return True
        return False

    def _pair_matches(self, left, right, rule):
        """Правило сработало, если стороны совпали в любом порядке."""
        a = rule.get("a") or ["*"]
        b = rule.get("b") or ["*"]
        if self._side_matches(left, a) and self._side_matches(right, b):
            return True
        return self._side_matches(right, a) and self._side_matches(left, b)

    def _apply_support_rules(self, contact, support_rules):
        """Применяет матрицу пар типа опоры; иначе — правило по умолчанию."""
        left, right = self._split_pair(contact.Name)
        pairs = support_rules.get("pairs") or []

        # Специфичные пары (обе стороны заданы) проверяем раньше общих ("rebro" - "*").
        ordered = sorted(pairs, key=lambda rule: (
            0 if (rule.get("a") and rule.get("b") and rule.get("b") != ["*"]) else 1))

        for rule in ordered:
            if left is None or right is None:
                break
            if self._pair_matches(left, right, rule):
                self.log.info(u"Контакт '{0}': пара из типа опоры '{1}' -> {2}".format(
                    contact.Name, support_rules.get("name"), rule.get("type")))
                self._configure_contact(contact, rule)
                return

        default_rule = dict(support_rules.get("default") or {})
        if support_rules.get("friction_coefficient") is not None and default_rule.get("friction_coefficient") is None:
            default_rule["friction_coefficient"] = support_rules["friction_coefficient"]
        if default_rule:
            self.log.info(u"Контакт '{0}': правило по умолчанию типа опоры -> {1}".format(
                contact.Name, default_rule.get("type")))
            self._configure_contact(contact, default_rule)
        else:
            self.log.warning(u"Для контакта '{0}' нет правила и нет default.".format(contact.Name))

    def _get_rule_priority(self, rule_params):
        """
        Определяет приоритет правила. 
        Чем меньше возвращаемое число, тем выше приоритет (правило проверяется раньше).
        """
        patterns = rule_params.get("patterns", [])
        if patterns == ["*"]:
            # Правило 'все остальные' должно быть самым последним
            return 1000
        
        # Специфичные правила (где больше паттернов) имеют более высокий приоритет
        # (возвращаем отрицательное количество паттернов)
        return -len(patterns)

    def _apply_rules_to_contact(self, contact, rules):
        """
        Применяет правила из JSON к конкретному региону контакта на основе имени.
        """
        name = contact.Name.lower()
        
        # Сортируем ключи правил по приоритету (специфичные в начале)
        # В Python 2.7 rules.keys() возвращает список ключей
        sorted_rule_keys = sorted(rules.keys(), key=lambda k: self._get_rule_priority(rules[k]))
        
        for rule_key in sorted_rule_keys:
            rule_params = rules[rule_key]
            patterns = rule_params.get("patterns", [])
            exclude_patterns = rule_params.get("exclude_patterns", [])
            
            match = False
            if patterns == ["*"]:
                match = True
            elif patterns:
                # Проверяем, что ВСЕ паттерны присутствуют в имени
                match = True
                for p in patterns:
                    if p.lower() not in name:
                        match = False
                        break
            
            # Если есть совпадение, проверяем исключения
            if match and exclude_patterns:
                for p in exclude_patterns:
                    if p.lower() in name:
                        match = False
                        break
            
            if match:
                self.log.info(u"Контакт '{0}': применено правило '{1}'".format(contact.Name, rule_key))
                self._configure_contact(contact, rule_params)
                return # Применяем только первое подошедшее правило
        
        self.log.debug(u"Для контакта '{0}' не найдено подходящих правил.".format(contact.Name))

    def _configure_contact(self, contact, params):
        """
        Устанавливает физические параметры контакта в ANSYS Mechanical.
        """
        try:
            # Установка типа контакта
            contact_type = params.get("type")
            if contact_type:
                # В API Mechanical типы задаются через свойства перечисления
                if contact_type == "Bonded":
                    contact.ContactType = contact.ContactType.Bonded
                elif contact_type == "Frictional":
                    contact.ContactType = contact.ContactType.Frictional
                    friction = params.get("friction_coefficient")
                    if friction is not None:
                        contact.FrictionCoefficient = friction
                elif contact_type == "Frictionless":
                    contact.ContactType = contact.ContactType.Frictionless
                # Добавьте другие типы при необходимости

            # Установка Interface Treatment
            it = params.get("interface_treatment")
            if it:
                if it == "AdjustToTouch":
                    contact.InterfaceTreatment = contact.InterfaceTreatment.AdjustToTouch
                elif it == "AddOffsetNoRamping":
                    contact.InterfaceTreatment = contact.InterfaceTreatment.AddOffsetNoRamping
                elif it == "Offset":
                    contact.InterfaceTreatment = contact.InterfaceTreatment.Offset

        except Exception as e:
            self.log.warning(u"Не удалось настроить параметры для '{0}': {1}".format(contact.Name, e))

    def _categorize_contact(self, contact):
        """
        Категоризирует контакт для последующей группировки.
        """
        try:
            c_type = contact.ContactType
            i_treat = contact.InterfaceTreatment
            
            # Логика категоризации согласно требованиям:
            # Bonded - bonded
            # Offset - Frictional с опцией Add Offset
            # Others - Frictional с опцией AdjustToTouch
            
            if c_type == contact.ContactType.Bonded:
                self.groups_to_collect["Bonded"].append(contact)
            elif c_type == contact.ContactType.Frictional:
                if i_treat == contact.InterfaceTreatment.AddOffsetNoRamping:
                    self.groups_to_collect["FrictOffset"].append(contact)
                else:
                    self.groups_to_collect["Frictional"].append(contact)
        except Exception as e:
            self.log.debug(u"Ошибка при категоризации контакта '{0}': {1}".format(contact.Name, e))

    def _create_tree_groups(self):
        """
        Создает группы в дереве проекта на основе собранных контактов.
        """
        self.log.info(u"Группировка контактов в дереве...")
        for group_name, contacts in self.groups_to_collect.items():
            if contacts:
                try:
                    # ExtAPI.DataModel.Tree.Group создает группу из списка объектов
                    group = self.context.ext_api.DataModel.Tree.Group(contacts)
                    group.Name = group_name
                except Exception as e:
                    self.log.error(u"Не удалось создать группу '{0}': {1}".format(group_name, e))