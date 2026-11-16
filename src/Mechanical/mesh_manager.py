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
        self.enums = context.enums

    def apply_mesh_settings(self):
        """
        Основной метод для применения настроек сетки. Проходит по всем Named Selections
        в модели и применяет наиболее подходящее правило из конфигурации.
        """
        self.log.info(u"Запуск настройки сетки КЭ...")
        
        if not self.model:
            self.log.error(u"Модель не найдена. Настройка сетки невозможна.")
            return

        self.sizings_to_collect = []
        self.methods_to_collect = []

        settings = self.context.configs.get("mesh_config")
        if not settings:
            self.log.warning(u"Настройки сетки не найдены в конфигурации (mesh_config).")
            return

        mesh_rules = settings.get("mesh_settings", {})
        mesh = self.model.Mesh
        
        # Получаем все Named Selections
        try:
            named_selections = self.model.NamedSelections.Children
            self.log.debug(u"Найдено Named Selections: {0}".format(named_selections.Count))
            for ns in named_selections:
                # ВАЖНО: Пропускаем NS, которые начинаются с 'gu_' (используются для ГУ и нагрузок)
                ns_name = ns.Name
                if ns_name.lower().startswith("gu_"):
                    self.log.debug(u"ПРОПУСК NS '{0}' (префикс gu_)".format(ns_name))
                    continue
                    
                self.log.debug(u"Анализ NS: '{0}'".format(ns_name))
                ns_name_lower = ns_name.lower()
                best_rule_key = None
                
                # Ищем лучшее совпадение (самый длинный ключ правила, который входит в имя NS)
                for rule_key in mesh_rules.keys():
                    if rule_key.lower() in ns_name_lower:
                        if best_rule_key is None or len(rule_key) > len(best_rule_key):
                            best_rule_key = rule_key
                
                if best_rule_key:
                    self.log.info(u"Сопоставлено: NS '{0}' -> Правило '{1}'".format(ns_name, best_rule_key))
                    
                    # Клонируем параметры для возможности переопределения
                    params = mesh_rules[best_rule_key].copy()
                    
                    # Проверяем наличие специфичных переопределений для данного типа конструкции
                    st_config = self.context.configs.get("structure_type", {})
                    mesh_overrides = st_config.get("mesh_overrides", {})
                    for ov_key, ov_params in mesh_overrides.items():
                        if ov_key.lower() in ns_name_lower:
                            self.log.info(u"Применено переопределение сетки '{0}' для '{1}'".format(ov_key, ns_name))
                            params.update(ov_params)

                    self._apply_mesh_to_ns(mesh, ns, params)
                else:
                    self.log.warning(u"Для NS '{0}' не найдено подходящих правил в mesh_config.".format(ns_name))

            self._create_tree_groups()

        except Exception as e:
            self.log.error(u"Ошибка при обходе Named Selections для сетки: {0}".format(e))

        self._apply_mesh_to_bodies(mesh, mesh_rules)

        self.log.info(u"Настройка сетки КЭ завершена.")

    def _selection_info(self, body):
        """``ISelectionInfo`` для тела.

        Живой прогон 21R1: ``sizing.Location = body`` падает
        ``TypeError: expected ISelectionInfo, got Body``. Поэтому строим
        выборку через ``ExtAPI.SelectionManager`` (RESEARCH-ANSYS-API §3.9, факт 22).
        """
        manager = self.context.ext_api.SelectionManager
        enum_cls = None
        try:
            from Ansys.Mechanical.DataModel.Enums import SelectionTypeEnum as enum_cls
        except Exception:
            enum_cls = globals().get("SelectionTypeEnum") or self.enums.get("SelectionTypeEnum")
        if enum_cls is None:
            raise RuntimeError(u"SelectionTypeEnum недоступен в этой сборке")

        info = manager.CreateSelectionInfo(enum_cls.GeometryEntities)
        try:
            ids = [body.GetGeoBody().Id]
        except Exception:
            try:
                ids = [body.Id]
            except Exception:
                ids = [getattr(body, "Name", None)]
        info.Ids = ids
        return info

    def generate_mesh(self):
        """Сгенерировать сетку и убедиться, что элементы действительно есть.

        ``Analysis.Solve(True)`` в 21R1 возвращает управление без исключения
        даже при нулевом числе элементов, поэтому проверка обязательна:
        иначе ``results.csv`` выгружается с одним заголовком.
        """
        if not self.model:
            raise RuntimeError(u"модель недоступна: сетку генерировать нечем")

        mesh = self.model.Mesh
        self.log.info(u"Генерация сетки КЭ...")
        mesh.GenerateMesh()

        elements = None
        try:
            elements = mesh.Elements
        except Exception as exc:
            self.log.warning(u"Не удалось прочитать число элементов: {0}".format(exc))

        self.log.info(u"Элементов после генерации: {0}".format(elements))
        if not elements:
            raise RuntimeError(
                u"сетка не сгенерирована (элементов 0): проверьте контролы Sizing/Method "
                u"и размеры элементов")
        return elements

    def _apply_mesh_to_ns(self, mesh_obj, ns_obj, params, label=None, location=None):
        """
        Применяет метод и размер сетки к Named Selection или к телу.

        Args:
            mesh_obj: объект ``Model.Mesh``.
            ns_obj: Named Selection **или** тело геометрии (у обоих есть ``Name``
                и они годятся как ``Location``).
            params: правило из ``mesh_config``.
            label: имя для логов и для извлечения числа; по умолчанию ``ns_obj.Name``.
        """
        ns_name = label if label else u"?"
        try:
            if not label:
                ns_name = ns_obj.Name
            mesh_coef = params.get("meshCoef")
            mesh_method_type = params.get("meshMethod")
            mesh_algorithm = params.get("meshAlgorithm")
            element_order = params.get("elementOrder")
            
            # Получаем единицы измерения из проекта
            length_unit = self.context.configs.get("project_settings", {}).get("units", {}).get("length", "mm")
            
            # Извлекаем число из конца имени (например, 'truba245' -> 245).
            # У тел бывает индекс через пробел ('truba42 1') — его отбрасываем.
            import re
            base_name = re.sub(r"\s+\d+$", "", ns_name)
            match = re.search(r"(\d+\.?\d*)$", base_name)
            
            # 1. Добавление Sizing (Размер элемента)
            if mesh_coef:
                sizing = mesh_obj.AddSizing()
                sizing.Name = u"Sizing_{0}".format(ns_name)
                sizing.Location = location if location is not None else ns_obj
                self.sizings_to_collect.append(sizing)
                
                if match:
                    val = float(match.group(1))
                    element_size = round((val / mesh_coef), 2)
                    
                    if self.context.Quantity:
                        sizing.ElementSize = self.context.Quantity(element_size, length_unit)
                    else:
                        sizing.ElementSize = element_size
                    
                    self.log.info(u"Sizing '{0}': {1} {2}".format(ns_name, element_size, length_unit))
                else:
                    self.log.warning(u"Не удалось извлечь число из '{0}' для Sizing".format(ns_name))

            # 2. Добавление Method (Sweep, MultiZone и т.д.)
            if mesh_method_type:
                method = mesh_obj.AddAutomaticMethod()
                method.Name = u"Method_{0}_{1}".format(mesh_method_type, ns_name)
                method.Location = location if location is not None else ns_obj
                self.methods_to_collect.append(method)
                
                # Установка типа метода
                mt_enum = self.enums.get("MethodType")
                if mt_enum:
                    if "Sweep" in mesh_method_type:
                        method.Method = mt_enum.Sweep
                        # Настройка алгоритма для Sweep
                        if mesh_algorithm == "Axisymmetric":
                            ma_enum = self.enums.get("MeshMethodAlgorithm")
                            if ma_enum:
                                method.Algorithm = ma_enum.Axisymmetric
                    elif "MultiZone" in mesh_method_type:
                        method.Method = mt_enum.MultiZone
                        
                        # Настройка SurfaceMeshMethod для MultiZone (0-ProgramControlled, 1-Uniform, 2-Pave)
                        smm_str = params.get("surfaceMeshMethod")
                        self.log.debug(u"smm_str: {0}".format(smm_str))
                        if smm_str:
                            smm_map = {"ProgramControlled": 0, "Uniform": 1, "Pave": 2}
                            smm_val = smm_map.get(smm_str)
                            if smm_val is not None:
                                method.SurfaceMeshMethod = smm_val
                                self.log.debug(u"Установлен SurfaceMeshMethod: {0} ({1})".format(smm_str, smm_val))

                        # Настройка FreeMeshType для MultiZone (0-NotAllowed, 1-Tetra, 2-Tetra/Pyramid, 3-HexaDominant, 4-HexaCore)
                        fmt_str = params.get("freeMeshType")
                        if fmt_str:
                            fmt_map = {"NotAllowed": 0, "Tetra": 1, "TetraPyramid": 2, "HexaDominant": 3, "HexaCore": 4}
                            fmt_val = fmt_map.get(fmt_str)
                            if fmt_val is not None:
                                method.FreeMeshType = fmt_val
                                self.log.debug(u"Установлен FreeMeshType: {0} ({1})".format(fmt_str, fmt_val))
                
                # Настройка порядка элементов (Element Order)
                if element_order:
                    eo_enum = self.enums.get("ElementOrder")
                    if eo_enum:
                        if element_order == "Quadratic":
                            method.ElementOrder = eo_enum.Quadratic
                        elif element_order == "Linear":
                            method.ElementOrder = eo_enum.Linear
                        elif element_order == "ProgramControlled":
                            method.ElementOrder = eo_enum.ProgramControlled

                self.log.debug(u"Метод '{0}' для '{1}' настроен (Algorithm: {2})".format(mesh_method_type, ns_name, mesh_algorithm))

        except Exception as e:
            self.log.error(u"Ошибка настройки сетки '{0}': {1}".format(ns_name, str(e)))

    def _create_tree_groups(self):
        """
        Создает группы в дереве проекта на основе собранных объектов сетки.
        """
        self.log.info(u"Группировка настроек сетки в дереве...")
        groups = {
            "Sizing": self.sizings_to_collect,
            "Method": self.methods_to_collect
        }
        
        for group_name, objects in groups.items():
            if objects:
                try:
                    group = self.context.ext_api.DataModel.Tree.Group(objects)
                    group.Name = group_name
                except Exception as e:
                    self.log.error(u"Не удалось создать группу '{0}': {1}".format(group_name, e))

    def _apply_mesh_to_bodies(self, mesh, mesh_rules):
        """Размер на тела, которым не досталось Named Selection.

        Труба приходит из SpaceClaim без NS (``truba42``), а именно её диаметр
        задаёт размер сетки. Без этого шага труба остаётся с сеткой по
        умолчанию — самой крупной в сборке.
        """
        import re
        from Mechanical import utils

        covered = []
        try:
            for ns in self.model.NamedSelections.Children:
                covered.append((ns.Name or u"").lower())
        except Exception as exc:
            self.log.warning(u"Не удалось прочитать NS для проверки тел: {0}".format(exc))

        try:
            bodies = utils.iter_bodies(self.model)
        except Exception as exc:
            self.log.warning(u"Тела для проверки сетки недоступны: {0}".format(exc))
            return

        for body in bodies:
            name = getattr(body, "Name", u"") or u""
            if not name:
                continue
            base = re.sub(r"\s+\d+$", "", name).lower()
            if any(ns == base or ns in base or base in ns for ns in covered):
                continue

            best_key = None
            for rule_key in mesh_rules.keys():
                if rule_key.lower() in base:
                    if best_key is None or len(rule_key) > len(best_key):
                        best_key = rule_key
            if not best_key:
                continue

            try:
                location = self._selection_info(body)
            except Exception as exc:
                self.log.warning(
                    u"Тело '{0}' без NS: выборку не построить ({1}); создайте NS вручную".format(name, exc))
                continue
            self.log.info(u"Нет NS для тела '{0}' — правило '{1}' применяется к телу".format(name, best_key))
            self._apply_mesh_to_ns(mesh, body, mesh_rules[best_key].copy(),
                                   label=base, location=location)
