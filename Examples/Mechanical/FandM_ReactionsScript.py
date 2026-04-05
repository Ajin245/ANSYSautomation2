# -*- coding: utf-8 -*-

# Получение объектов решения
solution = ExtAPI.DataModel.GetObjectsByType(DataModelObjectCategory.Solution)[0]

# Получение всех систем координат и поверхностей
coordinate_systems = ExtAPI.DataModel.GetObjectsByType(DataModelObjectCategory.CoordinateSystem)
surfaces = ExtAPI.DataModel.GetObjectsByType(DataModelObjectCategory.Surface)

print "=== НАЧАЛО ОБРАБОТКИ ==="
print "Найдено систем координат: {}".format(coordinate_systems.Count)
print "Найдено поверхностей: {}".format(surfaces.Count)

# Проверка существования поверхностей
if surfaces.Count == 0:
    print "\n=== ПРЕДУПРЕЖДЕНИЕ ==="
    print "В проекте не найдено ни одной поверхности (Surface)."
    print "Создание реакций невозможно."
    print "=== ОБРАБОТКА ПРЕРВАНА ==="
    
    # Прерывание выполнения скрипта
    raise Exception("В проекте отсутствуют поверхности. Добавьте поверхности и запустите скрипт снова.")
else:
    print "✓ Поверхности найдены, продолжаем обработку..."

# Создание словарей для быстрого поиска
cs_dict = {}
if coordinate_systems.Count > 0:
    for cs in coordinate_systems:
        cs_name = cs.Name
        cs_dict[cs_name] = cs
        print "Система координат: {}".format(cs_name)
else:
    print "В проекте не найдено систем координат"

# Проверка соответствия поверхностей и систем координат
missing_cs = []
valid_surfaces = []

for surf in surfaces:
    surface_name = surf.Name
    expected_cs_name = surface_name + "_CS"
    
    print "\nПроверка поверхности: {}".format(surface_name)
    print "Ожидаемая система координат: {}".format(expected_cs_name)
    
    if expected_cs_name in cs_dict:
        print "✓ Система координат найдена"
        valid_surfaces.append((surf, expected_cs_name))
    else:
        print "✗ Система координат НЕ найдена"
        missing_cs.append(surface_name)

# Вывод результатов проверки
if missing_cs:
    print "\n=== ВНИМАНИЕ: Отсутствуют системы координат для поверхностей ==="
    for surf_name in missing_cs:
        print "Поверхность: {} -> Отсутствует система: {}".format(surf_name, surf_name + "_CS")
else:
    print "\n✓ Все поверхности имеют соответствующие системы координат"

# Проверка наличия валидных поверхностей для обработки
if len(valid_surfaces) == 0:
    print "\n=== ПРЕДУПРЕЖДЕНИЕ ==="
    print "Нет ни одной поверхности с соответствующей системой координат."
    print "Создание реакций невозможно."
    
    if surfaces.Count > 0 and coordinate_systems.Count > 0:
        print "\nВозможные причины:"
        print "1. Несоответствие имен поверхностей и систем координат"
        print "2. Отсутствие постфикса '_CS' в именах систем координат"
    elif surfaces.Count > 0 and coordinate_systems.Count == 0:
        print "\nПричина: В проекте отсутствуют системы координат"
    
    print "=== ОБРАБОТКА ПРЕРВАНА ==="
    
    # Прерывание выполнения скрипта
    raise Exception("Нет валидных поверхностей для обработки.")
else:
    print "\n✓ Найдено {} поверхностей с системами координат для обработки".format(len(valid_surfaces))

# Создание реакций только для валидных поверхностей
for surf, cs_name in valid_surfaces:
    surface_name = surf.Name
    
    print "\n--- Обработка поверхности: {} ---".format(surface_name)
    print "Используемая система координат: {}".format(cs_name)
    
    # Создание Force Reaction
    force_reaction1 = solution.AddForceReaction()
    force_reaction1.LocationMethod = LocationDefinitionMethod.Surface
    force_reaction1.SurfaceSelection = surf
    
    # Установка системы координат для Force Reaction
    force_reaction1.Orientation = cs_dict[cs_name]
    
    # Переименование Force Reaction
    force_reaction_name = "F_" + surface_name
    force_reaction1.Name = force_reaction_name
    print "Создана Force Reaction: {}".format(force_reaction_name)
    
    # Создание Moment Reaction
    moment_reaction1 = solution.AddMomentReaction()
    moment_reaction1.LocationMethod = LocationDefinitionMethod.Surface
    moment_reaction1.SurfaceSelection = surf
    moment_reaction1.Summation = MomentsAtSummationPointType.OrientationSystem
    
    # Установка системы координат для Moment Reaction
    moment_reaction1.Orientation = cs_dict[cs_name]
    
    # Переименование Moment Reaction
    moment_reaction_name = "M_" + surface_name
    moment_reaction1.Name = moment_reaction_name
    print "Создана Moment Reaction: {}".format(moment_reaction_name)
    
    print "✓ Обработка поверхности {} завершена".format(surface_name)

print "\n=== ОБРАБОТКА ЗАВЕРШЕНА ==="
print "Итоговые результаты:"
print "- Всего поверхностей в проекте: {}".format(surfaces.Count)
print "- Обработано поверхностей: {}".format(len(valid_surfaces))
print "- Пропущено поверхностей (без систем координат): {}".format(len(missing_cs))

if len(valid_surfaces) > 0:
    print "\nСозданные реакции:"
    for surf, cs_name in valid_surfaces:
        surface_name = surf.Name
        print "  Поверхность {}: F_{}, M_{}".format(surface_name, surface_name, surface_name)
    
    print "\n✓ Автоматизация постобработки успешно выполнена!"
else:
    print "\n⚠ Не создано ни одной реакции"