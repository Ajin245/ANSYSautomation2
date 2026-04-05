# -*- coding: utf-8 -*-
import os
import csv

# Получение модели и пути проекта
model = ExtAPI.DataModel.Project.Model
project_path = ExtAPI.DataModel.AnalysisList[0].WorkingDir
solu = DataModel.GetObjectsByName("Solution Information")[0]
solution = solu.Parent
model_name = model.Name
csv_file = os.path.join(project_path, model_name + ".csv")
named_selections = Model.NamedSelections.Children
stress_unit = ExtAPI.DataModel.CurrentUnitFromQuantityName("Stress")
# Создание таблицы для результатов
results_table = []
# Список для хранения созданных результатов
created_results = []

# Шаг 1: Создание всех plot result без вычисления
for ns in named_selections:
    # Приведение имени NS к нижнему регистру для проверки
    ns_name_lower = ns.Name.lower()
    
    # Фильтрация нежелательных NS
    if ns_name_lower.startswith("gu_") or "hdst" in ns_name_lower:
        continue  # Пропускаем этот NS
    
    ns_object = ExtAPI.DataModel.GetObjectsByName(ns.Name)[0]
    
    if "shov" in ns_name_lower:
        # Создание Maximum Shear Stress для двух временных шагов
        for display_time in [Quantity(3,"s"), Quantity(4,"s")]:
            maxShear = solution.AddMaximumShearStress()
            maxShear.Location = ns_object
            maxShear.DisplayOption = ResultAveragingType.ElementalMean
            maxShear.DisplayTime = display_time
            maxShear.RenameBasedOnDefinition()
            # Сохраняем информацию о результате для последующего извлечения данных
            created_results.append((maxShear, ns.Name, display_time.Value))

    else:
        # Создание Stress Intensity для двух временных шагов
        for display_time in [Quantity(3,"s"), Quantity(4,"s")]:
            stress_intensity = solution.AddStressIntensity()
            stress_intensity.Location = ns_object
            stress_intensity.DisplayTime = display_time
            stress_intensity.RenameBasedOnDefinition()
            # Сохраняем информацию о результате для последующего извлечения данных
            created_results.append((stress_intensity, ns.Name, display_time.Value))

# Шаг 2: Единоразовое вычисление всех результатов
solution.EvaluateAllResults()

# Шаг 3: Извлечение максимальных значений после вычисления
for result, ns_name, display_time in created_results:
    max_value = round(result.Maximum.Value)
    results_table.append([ns_name, display_time, max_value])

# Сохранение в CSV файл
with open(csv_file, "wb") as file:
    writer = csv.writer(file)
    writer.writerow(["NS Name", "Display Time", "Max Value "+ "(" + stress_unit + ")"])
    for row in results_table:
        writer.writerow([str(row[0]), str(row[1]), str(row[2])])
print(csv_file)
print("FINISH")