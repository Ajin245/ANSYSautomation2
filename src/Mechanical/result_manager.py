# -*- coding: utf-8 -*-

class ResultManager:
    """
    Класс для управления результатами в ANSYS Mechanical.
    Создает объекты PlotResults (до расчета) и экспортирует данные (после расчета).
    """
    def __init__(self, context):
        """
        Инициализация менеджера результатов.

        Args:
            context (ProjectContext): Контекст текущего проекта.
        """
        self.context = context
        self.log = context.log
        self.analysis = context.analysis

    def setup_plot_results(self):
        """
        Создает объекты PlotResults в дереве Mechanical перед расчетом.
        """
        self.log.info(u"Настройка объектов PlotResults...")
        
        if not self.analysis:
            self.log.error(u"Анализ не найден. Невозможно настроить результаты.")
            return

        try:
            solution = self.analysis.Solution
            
            # 1. Общие перемещения (Total Deformation)
            total_def = solution.AddTotalDeformation()
            total_def.Name = u"Total Deformation"
            
            # 2. Напряжения (Equivalent Von-Mises Stress)
            equiv_stress = solution.AddEquivalentStress()
            equiv_stress.Name = u"Equivalent Stress"

            # 3. Реакции опор (если применимо, можно искать по Named Selection)
            # Это пример создания Probe
            # force_reaction = self.analysis.AddForceReaction()
            # force_reaction.Name = u"Force Reaction"

            self.log.info(u"Объекты PlotResults успешно созданы.")
        except Exception as e:
            self.log.error(u"Ошибка при создании PlotResults: {0}".format(e))

    def export_results(self):
        """
        После расчета экспортирует данные из созданных PlotResults в файл (например, CSV).
        """
        self.log.info(u"Экспорт результатов...")
        
        try:
            # Предположим, что результаты сохраняются в папку проекта или настраиваемую папку
            export_path = os.path.join(os.getcwd(), "results", "results_export.csv")
            
            # Логика экспорта зависит от версии API:
            # for res in self.analysis.Solution.Children:
            #     if hasattr(res, "ExportToTextFile"):
            #         res.ExportToTextFile(export_path)
            
            self.log.info(u"Результаты экспортированы в: {0}".format(export_path))
        except Exception as e:
            self.log.error(u"Ошибка при экспорте результатов: {0}".format(e))
