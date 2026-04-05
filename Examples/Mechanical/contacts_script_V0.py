# -*- coding: utf-8 -*-
"""
Макрос для автоматизации назначения контактов в ANSYS Workbench Mechanical.
Выполняет переименование контактных пар, установку типа контакта (Bonded/Frictional),
коэффициента трения для Frictional, настройку InterfaceTreatment и группировку.
"""

try:
    print("Начало макроса назначения контактов")

    # Получение модели и раздела Connections
    model = ExtAPI.DataModel.Project.Model
    if model is None:
        raise Exception("Не удалось получить модель")

    connections = model.Connections
    if connections is None:
        raise Exception("Не удалось получить раздел Connections")

    # Получение всех контактных регионов (рекурсивно)
    contacts = connections.GetChildren(DataModelObjectCategory.ContactRegion, True)
    print("Найдено контактных регионов: {}".format(len(contacts)))

    # Первое переименование контактов на основе определения
    for contact in contacts:
        try:
            contact.RenameBasedOnDefinition()
        except Exception as e:
            print("Не удалось переименовать контакт {}: {}".format(contact.Name, str(e)))
    print("Первое переименование завершено")

    # Списки для группировки
    bonded_list = []
    offset_list = []
    others_list = []

    # Обработка каждого контакта: тип, коэффициент трения, InterfaceTreatment
    for contact in contacts:
        name_lower = contact.Name.lower()
        print("Обработка контакта: {}".format(contact.Name))

        # Определение типа контакта
        is_bonded = False
        if 'shov' in name_lower:
            is_bonded = True
        elif 'truba' in name_lower and 'shponka' in name_lower:
            is_bonded = True
        elif 'mgaika' in name_lower and 'mbolt' in name_lower:
            is_bonded = True

        if is_bonded:
            contact.ContactType = ContactType.Bonded
            print("  Установлен тип: Bonded")
            bonded_list.append(contact)
        else:
            contact.ContactType = ContactType.Frictional
            contact.FrictionCoefficient= 0.3  # Устанавливаем коэффициент трения
            print("  Установлен тип: Frictional, коэффициент трения = 0.3")

            # Настройка InterfaceTreatment для Frictional
            if 'mbolt' in name_lower and 'mgaika' not in name_lower:
                contact.InterfaceTreatment = ContactInitialEffect.AddOffsetNoRamping
                print("  Установлен InterfaceTreatment: Add Offset, No Ramping")
                offset_list.append(contact)
            else:
                contact.InterfaceTreatment = ContactInitialEffect.AdjustToTouch
                print("  Установлен InterfaceTreatment: AdjustToTouch")
                others_list.append(contact)

    # Второе переименование контактов после изменения свойств
    print("Второе переименование контактов...")
    for contact in contacts:
        try:
            contact.RenameBasedOnDefinition()
        except Exception as e:
            print("Не удалось переименовать контакт {}: {}".format(contact.Name, str(e)))
    print("Второе переименование завершено")

    # Группировка контактов в папки
    print("Группировка контактов...")

    # Папка Bonded
    if bonded_list:
        bonded_group = ExtAPI.DataModel.Tree.Group(bonded_list)
        bonded_group.Name = "Bonded"
        print("Создана папка Bonded с {} контактами".format(len(bonded_list)))

    # Папка Offset
    if offset_list:
        offset_group = ExtAPI.DataModel.Tree.Group(offset_list)
        offset_group.Name = "Offset"
        print("Создана папка Offset с {} контактами".format(len(offset_list)))

    # Папка Others
    if others_list:
        others_group = ExtAPI.DataModel.Tree.Group(others_list)
        others_group.Name = "Others"
        print("Создана папка Others с {} контактами".format(len(others_list)))

    Tree.Refresh()

    print("Макрос успешно выполнен")

except Exception as e:
    print("Ошибка выполнения макроса: {}".format(str(e)))