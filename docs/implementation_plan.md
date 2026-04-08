# План Реализации Автоматизации ANSYS Mechanical

## Обзор
Данный документ описывает детальный план реализации скриптов для автоматизации расчетов в ANSYS Mechanical, основанный на утвержденной гибридной архитектуре с общим контекстом и отдельными менеджерами.

## Цель
Разработать набор Python-скриптов для автоматизации расчетов в ANSYS Mechanical, следуя утвержденной гибридной архитектуре с общим контекстом и отдельными менеджерами.

## Архитектура
*   **Центральный объект:** `ProjectContext`, содержащий загруженные конфигурации (JSON), ссылки на проект ANSYS Mechanical, объекты модели (`Model`, `Analysis`), функцию парсинга ID проекта и логгер.
*   **Модульный подход:** Каждый менеджер реализуется в отдельном файле в директории `src/Mechanical/`.
*   **Управление зависимостями:** Путь к `src/Mechanical/` добавляется в `sys.path` главного скрипта.
*   **Идентификатор конструкции:** Извлекается из названия проекта ANSYS (`Project_XXX`).
*   **Директории:**
    *   `config/` - для JSON конфигурационных файлов.
    *   `src/Mechanical/` - для Python скриптов автоматизации.
*   **Игнорирование файлов:** `.gitignore` не должен содержать `src/` или его содержимое.

## Менеджеры
*   **`ProjectContext` (`src/Mechanical/project_context.py`):**
    *   Класс для управления всеми настройками и объектами.
    *   Загрузка JSON-файлов (`structure_type_XXX.json`, `config/mechanical_configs/*.json`).
    *   Парсинг ID конструкции из названия проекта.
    *   Доступ к ANSYS API (`Model`, `Analysis`).
    *   Базовая система логирования.
*   **`ContactManager` (`src/Mechanical/contact_manager.py`):**
    *   Класс для настройки контактов и болтовых соединений.
    *   Загрузка настроек из `contact_settings.json` и `structure_type_XXX.json`.
    *   Применение настроек в ANSYS Mechanical.
*   **`MeshManager` (`src/Mechanical/mesh_manager.py`):**
    *   Класс для настройки сетки.
    *   Загрузка настроек сетки из `mesh_config.json` и `structure_type_XXX.json`.
    *   Применение настроек сетки к Named Selections.
*   **`AnalysisManager` (`src/Mechanical/analysis_manager.py`):**
    *   Класс для назначения граничных условий и нагрузок.
    *   Загрузка настроек из `analysis_scenarios.json` и `structure_type_XXX.json`.
    *   Применение граничных условий, нагрузок, расчет преднатяга болтов.
*   **`ValidationManager` (`src/Mechanical/validation_manager.py`):**
    *   Класс для валидации настроек модели перед расчетом.
    *   Метод `validate_model_setup(context: ProjectContext)`.
    *   Проверки: наличие конфигов, Named Selections, объектов ANSYS, корректность настроек.
*   **`ResultManager` (`src/Mechanical/result_manager.py`):**
    *   Класс для управления результатами.
    *   Метод `setup_plot_results(context: ProjectContext)`: создание объектов `PlotResults`.
    *   Метод `export_results(context: ProjectContext)`: извлечение и экспорт данных.

## Основной Скрипт

*   **`ansys_automation.py` (`src/Mechanical/ansys_automation.py`):**
    *   Главная точка входа.
    *   Импорт всех менеджеров и `ProjectContext`.
    *   Инициализация `ProjectContext`.
    *   Создание экземпляров менеджеров.
    *   Последовательный вызов методов:
        1.  `contact_manager.setup_contacts()`
        2.  `mesh_manager.apply_mesh_settings()`
        3.  `analysis_manager.apply_boundary_conditions_and_loads()`
        4.  `validation_manager.validate_model_setup()`
        5.  `result_manager.setup_plot_results()`
    *   Обработка исключений и логирование.

## План Реализации (Шаги)

1.  **Создание структуры проекта:**
    *   Создать директорию `src/Mechanical/`.
    *   Создать пустые файлы: `__init__.py`, `ansys_automation.py`, `project_context.py`, `contact_manager.py`, `mesh_manager.py`, `analysis_manager.py`, `result_manager.py`, `validation_manager.py`, `utils.py`.
    *   Убедиться, что `src/` и его содержимое не добавлены в `.gitignore`.
    *   **СТАТУС: ЗАВЕРШЕНО**
2.  **Реализация `ProjectContext`:**
    *   Разработать класс `ProjectContext` с методами для загрузки JSON, парсинга ID, доступа к ANSYS API и логирования.
    *   **СТАТУС: ЗАВЕРШЕНО**
3.  **Реализация `ValidationManager`:**
    *   Разработать класс `ValidationManager` с методом `validate_model_setup`.
    *   Реализовать базовые проверки.
    *   **СТАТУС: ЗАВЕРШЕНО**
4.  **Реализация `ContactManager`:**
    *   Разработать класс `ContactManager`.
    *   Реализовать загрузку настроек и применение логики контактов/болтов.
    *   **СТАТУС: ЗАВЕРШЕНО**
5.  **Реализация `MeshManager`:**
    *   Разработать класс `MeshManager`.
    *   Реализовать загрузку настроек сетки и применение.
    *   **СТАТУС: ЗАВЕРШЕНО**
6.  **Реализация `AnalysisManager`:**
    *   Разработать класс `AnalysisManager`.
    *   Реализовать загрузку граничных условий/нагрузок и их применение.
    *   Реализовать расчет преднатяга болтов.
    *   **СТАТУС: ЗАВЕРШЕНО**
7.  **Реализация `ResultManager`:**
    *   Разработать класс `ResultManager`.
    *   Реализовать `setup_plot_results()` и `export_results()`.
    *   **СТАТУС: ЗАВЕРШЕНО**
8.  **Реализация главного скрипта `ansys_automation.py`:**
    *   Написать логику инициализации, вызова менеджеров и обработки ошибок.
    *   **СТАТУС: ЗАВЕРШЕНО**
9.  **Тестирование и отладка:**
    *   Проверить каждый компонент в ANSYS Mechanical.
    *   Отладить скрипты.

*Этапы будут выполняться последовательно, с тестированием на каждом шаге.*
