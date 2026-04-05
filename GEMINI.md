# ANSYS Automation Project

## Project Overview
This project consists of a collection of Python and IronPython scripts designed to automate engineering workflows within ANSYS Mechanical. The automation covers the entire simulation pipeline, including geometry organization, contact management, meshing, solving, and post-processing of results.

### Key Technologies
- **Python / IronPython**: The primary scripting language used within the ANSYS Mechanical environment.
- **ANSYS Mechanical API**: Used to interact with the project tree, model objects, analysis settings, and results.
- **JSON**: Used for external configuration and database management (in newer versions of the scripts).

## Automation Workflow
This project implements a comprehensive automation workflow for ANSYS, integrating geometry preparation in SpaceClaim with analysis setup and post-processing in Mechanical. The detailed step-by-step algorithm is described in [Plan.md](Plan.md).

### Main Components
- **SpaceClaim Automation**: Скрипты для автоматизации ANSYS SpaceClaim будут использоваться для подготовки 3D моделей перед расчетом. Их функционал будет интегрирован в общую структуру проекта, используя JSON файлы для конфигурации ключевых идей формирования модели.
- **Configuration Management**: `ansys_automation_v01.5.py` includes a `ConfigurationManager` to handle project settings, mesh configurations, and analysis scenarios via JSON files. 
- **Contact Automation**: `SortContacts.py` and `contacts_script_V0.py` automate the renaming and grouping of contact pairs based on their definitions and naming conventions (e.g., grouping weld "shov" or bolt contacts).
- **Meshing & Solving**: `meshing+solving_script_V2.py` applies specific mesh methods (Sweep, MultiZone) and sizing controls based on Named Selections, then initiates the solution.
- **Results & Post-processing**: `ResultsScript.py` and `FandM_ReactionsScript.py` automate the creation of result objects and the extraction of reaction forces and moments.

## Usage

### Running the Scripts
These scripts are intended to be executed within the **ANSYS Mechanical Scripting Console** or as part of an ANSYS ACT extension.

1. Open your project in ANSYS Mechanical.
2. Open the **Scripting Console** (Automation tab -> Scripting).
3. Copy and paste the content of the desired script or use the `execfile()` command in IronPython.

### Configuration
Some scripts (like `ansys_automation_v01.5.py`) expect configuration files in a specific directory (defaulting to `E:\OLEGG\Other\`). These files include:
- `project_settings.json`
- `mesh_config.json`
- `analysis_scenarios.json`
- `contact_settings.json`

## Development Conventions
For detailed coding standards, environment requirements, and compatibility rules, see the [RULES.md](RULES.md) file.

### Coding Style
- **Naming Conventions**: Scripts often use `Named Selections` (e.g., `gu_fixed`, `mbolt`) to target geometry. Consistent naming in the ANSYS model is crucial for the scripts to function correctly.
- **Error Handling**: Basic `try...except` blocks are used to catch and report errors during the interaction with the ANSYS Tree.
- **Comments**: High-level descriptions are often provided in Russian or English at the beginning of the scripts.

### File Versioning
The project uses suffix-based versioning in filenames (e.g., `v01.5`, `V2`). Always refer to the latest version for the most up-to-date logic.

## TODO / Future Improvements
- [ ] Centralize all hardcoded paths into a single configuration file.
- [ ] Implement a more robust logging system that outputs to the ANSYS Message window.
- [ ] Migrate older `V0` and `V1` logic into the structured `ConfigurationManager` approach.
