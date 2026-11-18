# -*- coding: utf-8 -*-

# Правила контактов живут в конфиге, а не в коде: сначала глобальные пары
# классов тел (``contact_settings.pairs``), затем переопределение типа опоры
# (``support_types[<тип>].pairs``), затем ``default``. Правила с двумя
# заданными сторонами проверяются раньше правил со звёздочкой.


def body_class(side, classes):
    """Класс тела из стороны контакта: ``'SYS\\mbolt8 1'`` -> ``'mbolt'``.

    Args:
        side (str): имя тела (одна сторона контакта), регистр не важен.
        classes (iterable): классы тел, которые надо распознать.

    Returns:
        str: первый совпавший класс или ``None``.
    """
    if not side:
        return None
    tail = side.replace(u"/", u"\\").split(u"\\")[-1].strip().lower()
    for class_name in classes:
        if tail.startswith(class_name):
            return class_name
    return None


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
        # Чистый прогон: старые папки контактов от предыдущих запусков удаляем,
        # иначе в дереве оказываются две «Bonded» и три «Frictional».
        self._purge_old_groups()

        settings = self.context.configs.get("contact_settings") or {}
        inner = settings.get("contact_settings") or {}
        base_pairs = inner.get("pairs") or []
        base_default = inner.get("default") or {}
        support_rules = self._support_type_rules()
        if not base_pairs and not support_rules:
            self.log.warning(u"Настройки контактов не найдены (ни contact_settings.pairs, ни support_types).")
            return
        if support_rules:
            self.log.info(u"Переопределения контактов из типа опоры '{0}'.".format(support_rules.get("name")))
        self.log.info(u"Глобальных правил пар: {0}, тип опоры: {1}".format(
            len(base_pairs), (support_rules or {}).get("name") or u"нет"))

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
        base_pairs = ((settings or {}).get("contact_settings") or {}).get("pairs") or []
        base_default = ((settings or {}).get("contact_settings") or {}).get("default") or {}

        for contact in contacts:
            if contact.DataModelObjectCategory.ToString() == "ContactRegion":
                # Переименовываем контакт на основе тел, которые он соединяет
                try:
                    contact.RenameBasedOnDefinition()
                except:
                    pass
                rule, source = self._resolve_rule(contact, base_pairs, base_default, support_rules)
                if rule:
                    self.log.info(u"Контакт '{0}': {1} -> {2} ({3})".format(
                        contact.Name, source, rule.get("type"),
                        rule.get("interface_treatment") or u"-"))
                    self._configure_contact(contact, rule)
                else:
                    self.log.warning(u"Для контакта '{0}' нет правила и нет default.".format(contact.Name))
                self._categorize_contact(contact)

    def _purge_old_groups(self):
        """Удаляет папки контактов, созданные прошлыми прогонами конвейера."""
        names = tuple(self.groups_to_collect.keys())
        try:
            children = list(self.model.Connections.Children)
        except Exception as exc:
            self.log.debug(u"Connections.Children недоступны: {0}".format(exc))
            return
        for item in children:
            try:
                if item.DataModelObjectCategory.ToString() != "ConnectionGroup":
                    continue
                if (getattr(item, "Name", u"") or u"") not in names:
                    continue
                item.Delete()
                self.log.info(u"Удалена старая папка контактов '{0}'".format(item.Name))
            except Exception as exc:
                self.log.debug(u"Не удалось удалить папку контактов: {0}".format(exc))

    def _resolve_rule(self, contact, base_pairs, base_default, support_rules):
        """Правило для контакта: тип опоры -> глобальные пары -> default.

        Порядок важен: специфические переопределения типа опоры (например,
        «ребро всегда Bonded у скользящей направляющей») должны побеждать
        общие пары, а общий ``default`` — срабатывать последним.

        Returns:
            tuple: ``(rule, source)`` или ``(None, None)``; ``source`` — откуда
            правило взялось (для лога и разбора).
        """
        left, right = self._split_pair(contact.Name)

        if support_rules:
            rule = self._match_pairs(left, right, support_rules.get("pairs") or [])
            if rule:
                return rule, u"тип опоры '{0}'".format(support_rules.get("name"))

        rule = self._match_pairs(left, right, base_pairs)
        if rule:
            return rule, u"глобальная пара '{0}'".format(rule.get("name") or u"?")

        support_default = dict((support_rules or {}).get("default") or {})
        if support_default:
            if (support_rules or {}).get("friction_coefficient") is not None \
                    and support_default.get("friction_coefficient") is None:
                support_default["friction_coefficient"] = support_rules["friction_coefficient"]
            return support_default, u"default типа опоры"

        if base_default:
            return dict(base_default), u"глобальный default"

        return None, None

    def _match_pairs(self, left, right, pairs):
        """Первое подходящее правило из списка пар; специфичные — раньше общих."""
        if left is None or right is None:
            return None
        ordered = sorted(pairs, key=lambda rule: (
            0 if (rule.get("a") and rule.get("b") and rule.get("b") != ["*"]) else 1))
        for rule in ordered:
            if self._pair_matches(left, right, rule):
                return dict(rule)
        return None

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