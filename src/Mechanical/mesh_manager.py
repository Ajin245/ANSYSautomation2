# -*- coding: utf-8 -*-

class MeshManager:
    """
    Класс для управления настройками сетки КЭ в ANSYS Mechanical.
    Применяет методы мешинга (Sweep, MultiZone) и размеры элементов на основе Named Selections.
    """
    def __init__(self, context):
        """
        Инициализация менеджера сетки.

        Args:
            context (ProjectContext): Контекст текущего проекта.
        """
        self.context = context
        self.log = context.log
        self.model = context.model

    def apply_mesh_settings(self):
        """
        Основной метод для применения настроек сетки. Проходит по правилам из конфига
        и создает Mesh Controls для соответствующих Named Selections.
        """
        self.log.info(u"Запуск настройки сетки КЭ...")
        
        if not self.model:
            self.log.error(u"Модель не найдена. Настройка сетки невозможна.")
            return

        settings = self.context.configs.get("mesh_config")
        if not settings:
            self.log.warning(u"Настройки сетки не найдены в конфигурации (mesh_config).")
            return

        mesh_rules = settings.get("mesh_settings", {})
        
        # Получаем объект Mesh
        mesh = self.model.Mesh
        
        for ns_name, params in mesh_rules.iteritems():
            # Находим Named Selection
            ns_object = self._get_named_selection(ns_name)
            if ns_object:
                self._apply_mesh_to_ns(mesh, ns_object, params)
            else:
                self.log.debug(u"Named Selection '{0}' не найден, настройки сетки пропущены.".format(ns_name))

        self.log.info(u"Настройка сетки КЭ завершена.")

    def _get_named_selection(self, name):
        """Возвращает объект Named Selection по имени."""
        for ns in self.model.NamedSelections.Children:
            if ns.Name == name:
                return ns
        return None

    def _apply_mesh_to_ns(self, mesh_obj, ns_obj, params):
        """
        Применяет метод и размер сетки к конкретному Named Selection.
        """
        try:
            ns_name = ns_obj.Name
            mesh_coef = params.get("meshCoef")
            mesh_method_type = params.get("meshMethod")
            
            # 1. Добавление Sizing (Размер элемента)
            if mesh_coef:
                sizing = mesh_obj.AddSizing()
                sizing.Name = u"Sizing_{0}".format(ns_name)
                sizing.Location = ns_obj
                # Здесь логика перевода meshCoef в реальный размер (зависит от проекта)
                # Для примера установим напрямую, если это размер в мм
                # sizing.ElementSize = Quantity(mesh_coef, "mm") 
                self.log.debug(u"Добавлен Sizing для '{0}' (Coef: {1})".format(ns_name, mesh_coef))

            # 2. Добавление Method (Sweep, MultiZone и т.д.)
            if mesh_method_type:
                method = mesh_obj.AddAutomaticMethod()
                method.Name = u"Method_{0}_{1}".format(mesh_method_type, ns_name)
                method.Location = ns_obj
                
                if mesh_method_type == "Sweep":
                    method.Method = method.Method.Sweep
                elif mesh_method_type == "MultiZone":
                    method.Method = method.Method.MultiZone
                
                # Дополнительные настройки метода
                algo = params.get("meshAlgorithm")
                if algo == "Axisymmetric":
                    # В некоторых версиях API настройки специфичны для метода
                    pass
                
                self.log.debug(u"Добавлен метод '{0}' для '{1}'".format(mesh_method_type, ns_name))

        except Exception as e:
            self.log.warning(u"Ошибка при настройке сетки для '{0}': {1}".format(ns_obj.Name, e))
