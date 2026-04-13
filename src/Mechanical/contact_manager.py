# -*- coding: utf-8 -*-

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

        settings = self.context.configs.get("contact_settings")
        if not settings:
            self.log.warning(u"Настройки контактов не найдены в конфигурации (contact_settings).")
            return

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
                    self._process_contact_group(group, settings)
                    found_any = True
            if not found_any:
                self.log.warning(u"В дереве модели не найдено групп контактов (Contact Groups).")
                
        except Exception as e:
            self.log.error(u"Ошибка при доступе к контактам: {0}".format(e))

        self.log.info(u"Настройка контактов завершена.")

    def _process_contact_group(self, group, settings):
        """
        Обрабатывает отдельную группу контактов.
        """
        contacts = group.Children
        contact_rules = settings.get("contact_settings", {})

        for contact in contacts:
            if contact.DataModelObjectCategory.ToString() == "ContactRegion":
                self._apply_rules_to_contact(contact, contact_rules)

    def _apply_rules_to_contact(self, contact, rules):
        """
        Применяет правила из JSON к конкретному региону контакта на основе имени.
        """
        name = contact.Name.lower()
        
        # Перебираем правила из конфига. В Python 2 используем iteritems()
        for rule_key, rule_params in rules.iteritems():
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
                self.log.warning(u"Применение правила '{0}' к контакту '{1}'".format(rule_key, contact.Name))
                self._configure_contact(contact, rule_params)
                break # Применяем только первое подошедшее правило

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