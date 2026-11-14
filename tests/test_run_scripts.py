# -*- coding: utf-8 -*-
"""Статические проверки обвязки запуска, без живого ANSYS.

Проверяем не поведение Workbench (оно требует Windows + лицензии), а контракт
файлов: аргументы batch-запуска, отсутствие мёртвого канала передачи команды,
ACT-расширение как канал доставки, ожидание ``results.csv`` и разделение
режимов в docs.
"""

import io
import os
import tokenize
import unittest
import xml.dom.minidom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.path.join(ROOT, "scripts", "run_ansys.bat")
INSTALL = os.path.join(ROOT, "scripts", "install_act_extension.bat")
JOURNAL = os.path.join(ROOT, "scripts", "workbench_journal.py")
SC_GUIDE = os.path.join(ROOT, "scripts", "run_spaceclaim.md")
RUN_MODES = os.path.join(ROOT, "docs", "run-modes.md")
ACT_DOC = os.path.join(ROOT, "docs", "act-extension.md")
ACT_XML = os.path.join(ROOT, "src", "act", "ansys_automation", "ansys_automation.xml")
ACT_MODULE = os.path.join(ROOT, "src", "act", "ansys_automation",
                          "ansys_automation_act.py")

DEAD_CHANNEL = "".join(["Send", "Command"])


def read_text(path):
    handle = io.open(path, "r", encoding="utf-8")
    try:
        return handle.read()
    finally:
        handle.close()


def find_fstrings(path):
    """Номера строк с f-строковыми литералами (лексически, как в tools)."""
    handle = io.open(path, "rb")
    try:
        tokens = tokenize.tokenize(handle.readline)
        found = []
        for token in tokens:
            if token.type != tokenize.STRING:
                continue
            prefix = token.string[:3].lower()
            quote_at = 0
            while quote_at < len(prefix) and prefix[quote_at] in "rubf":
                quote_at += 1
            if "f" in prefix[:quote_at]:
                found.append(token.start[0])
    finally:
        handle.close()
    return found


class RunAnsysBatTestCase(unittest.TestCase):
    """run_ansys.bat: batch-аргументы, окружение и коды возврата."""

    def setUp(self):
        self.text = read_text(BAT)

    def test_batch_flags_are_present(self):
        self.assertIn("-B", self.text)
        self.assertIn('-F "%PROJECT%"', self.text)
        self.assertIn('-R "%JOURNAL%"', self.text)

    def test_journal_path_points_to_scripts(self):
        self.assertIn("workbench_journal.py", self.text)
        self.assertIn("scripts\\workbench_journal.py", self.text)

    def test_ansys_exe_is_configurable_with_default_v211(self):
        self.assertIn("ANSYS_WB_EXE", self.text)
        self.assertIn("v211", self.text)
        self.assertIn("runwb2.exe", self.text)

    def test_missing_runwb2_returns_code_2(self):
        marker = 'runwb2.exe not found'
        self.assertIn(marker, self.text)
        position = self.text.rindex(marker)
        tail = self.text[position:position + 500]
        self.assertIn("exit /b 2", tail)

    def test_missing_extension_returns_code_5(self):
        marker = "ACT extension is not installed"
        self.assertIn(marker, self.text)
        position = self.text.rindex(marker)
        tail = self.text[position:position + 600]
        self.assertIn("install_act_extension.bat", tail)
        self.assertIn("exit /b 5", tail)

    def test_sets_root_and_run_flag_for_act_extension(self):
        self.assertIn('set "ANSYS_AUTOMATION_ROOT=%ROOT%"', self.text)
        self.assertIn('set "ANSYS_AUTOMATION_RUN=1"', self.text)
        self.assertIn('set "STRUCTURE_ID=%STRUCTURE_ID%"', self.text)

    def test_creates_logs_and_redirects_both_streams(self):
        self.assertIn("logs", self.text)
        self.assertIn("> \"%LOG%\" 2>&1", self.text)
        self.assertIn("run-%STAMP%.log", self.text)
        self.assertIn("act-run.log", self.text)

    def test_requires_explicit_success_marker(self):
        self.assertIn("AUTOMATION-FAILED", self.text)
        self.assertIn("AUTOMATION-OK", self.text)
        self.assertIn("findstr", self.text)
        self.assertIn('if not "%RUN_RC%"=="0"', self.text)
        self.assertIn("RUN-OK", self.text)


class InstallActExtensionTestCase(unittest.TestCase):
    """install_act_extension.bat: раскладка установки ACT-расширения."""

    def setUp(self):
        self.text = read_text(INSTALL)

    def test_copies_into_user_act_extensions_dir(self):
        self.assertIn("Ansys\\v%VER%\\ACT\\extensions", self.text)
        self.assertIn('if not defined ANSYS_ACT_VER set "ANSYS_ACT_VER=211"', self.text)
        self.assertIn("ansys_automation.xml", self.text)
        self.assertIn('copy /Y "%SRC%\\*.py"', self.text)

    def test_source_is_repository_extension(self):
        self.assertIn("src\\act\\ansys_automation", self.text)

    def test_mentions_manage_extensions_and_licence(self):
        self.assertIn("Manage Extensions", self.text)
        self.assertIn("licence", self.text)


class WorkbenchJournalTestCase(unittest.TestCase):
    """workbench_journal.py: py2-журнал без мёртвого канала, с ожиданием CSV."""

    def setUp(self):
        self.text = read_text(JOURNAL)

    def test_has_py2_coding_header(self):
        first_line = self.text.splitlines()[0]
        self.assertEqual(first_line, "# -*- coding: utf-8 -*-")

    def test_has_no_fstrings(self):
        self.assertEqual(find_fstrings(JOURNAL), [])

    def test_does_not_send_commands_into_mechanical(self):
        self.assertNotIn(DEAD_CHANNEL, self.text)
        self.assertNotIn("execfile", self.text)

    def test_refreshes_and_updates_the_system(self):
        self.assertIn("system.Refresh()", self.text)
        self.assertIn("system.Update()", self.text)
        self.assertLess(self.text.index("system.Refresh()"),
                        self.text.index("system.Update()"))

    def test_waits_for_results_and_act_marker(self):
        self.assertIn("_wait_for_results", self.text)
        self.assertIn('ACT_OK = "ACT-RUN-OK"', self.text)
        self.assertIn("ANSYS_ACT_WAIT_SECONDS", self.text)
        self.assertIn('"results", "results.csv"', self.text)
        self.assertIn("ANSYS_AUTOMATION_RESULTS", self.text)

    def test_saves_project_and_prints_success_marker(self):
        self.assertIn("Save(Overwrite=True)", self.text)
        self.assertIn("AUTOMATION-OK", self.text)

    def test_system_selection_uses_argument_or_first(self):
        self.assertIn("MECH_SYSTEM_NAME", self.text)
        self.assertIn("GetSystem(Name=", self.text)
        self.assertIn("STRUCTURE_ID", self.text)

    def test_marker_present_in_every_failure_branch(self):
        self.assertGreaterEqual(self.text.count("AUTOMATION-FAILED"), 4)

    def test_stale_act_log_is_not_success(self):
        self.assertIn("getmtime", self.text)
        self.assertIn("started", self.text)


class ActExtensionTestCase(unittest.TestCase):
    """ACT-расширение: манифест и py2-модуль конвейера."""

    def setUp(self):
        self.manifest = read_text(ACT_XML)
        self.module = read_text(ACT_MODULE)

    def test_manifest_is_well_formed_xml(self):
        xml.dom.minidom.parseString(self.manifest.encode("utf-8"))

    def test_manifest_declares_mechanical_oninit(self):
        self.assertIn('name="ansys_automation"', self.manifest)
        self.assertIn("<guid shortid=", self.manifest)
        self.assertIn('<script src="ansys_automation_act.py"/>', self.manifest)
        self.assertIn('<interface context="Mechanical">', self.manifest)
        self.assertIn("<oninit>on_init</oninit>", self.manifest)

    def test_module_is_py2_without_fstrings(self):
        self.assertEqual(self.module.splitlines()[0], "# -*- coding: utf-8 -*-")
        self.assertEqual(find_fstrings(ACT_MODULE), [])
        self.assertNotIn(DEAD_CHANNEL, self.module)

    def test_oninit_is_gated_by_run_flag(self):
        self.assertIn("def on_init(context):", self.module)
        self.assertIn('RUN_FLAG = "ANSYS_AUTOMATION_RUN"', self.module)
        self.assertIn("ACT-RUN-SKIP", self.module)

    def test_pipeline_order_setup_solve_export(self):
        setup = self.module.index("_execfile(setup_script)")
        solve = self.module.index("analysis.Solve(True)")
        export = self.module.index("_execfile(export_script)")
        self.assertLess(setup, solve, "настройка должна идти до решения")
        self.assertLess(solve, export, "выгрузка должна идти после решения")

    def test_logs_into_act_run_log(self):
        self.assertIn('LOG_FILE = "act-run.log"', self.module)
        self.assertIn("ACT-RUN-OK", self.module)
        self.assertIn("AUTOMATION-FAILED", self.module)

    def test_requires_env_root_instead_of_guessing(self):
        self.assertIn("ANSYS_AUTOMATION_ROOT", self.module)
        self.assertIn("ansys_automation.py", self.module)
        self.assertIn("export_results.py", self.module)


class PipelineTracesTestCase(unittest.TestCase):
    """Пайплайн не должен тянуть прежний канал в src/ и scripts/."""

    def test_no_dead_channel_left_in_scripts_and_src(self):
        offenders = []
        for base in ("scripts", "src"):
            for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, base)):
                dirnames[:] = [name for name in dirnames if name != "__pycache__"]
                for filename in filenames:
                    if not filename.endswith((".py", ".xml", ".bat")):
                        continue
                    path = os.path.join(dirpath, filename)
                    if DEAD_CHANNEL in read_text(path):
                        offenders.append(os.path.relpath(path, ROOT))
        self.assertEqual(offenders, [])


class RunDocumentationTestCase(unittest.TestCase):
    """Памятки честно разделяют подтверждённое, неподтверждённое и ручное."""

    def test_run_modes_has_three_sections(self):
        text = read_text(RUN_MODES)
        self.assertIn("## Подтверждено", text)
        self.assertIn("## Не подтверждено", text)
        self.assertIn("## Ручное", text)

    def test_run_modes_records_live_facts(self):
        text = read_text(RUN_MODES)
        self.assertIn("21.1.0.2020110819", text)
        self.assertIn("Опровергнуто", text)
        self.assertIn("GetProject", text)
        self.assertIn("runwb2 -B", text)
        self.assertIn("ACT-расширение", text)

    def test_act_doc_covers_install_and_unconfirmed(self):
        text = read_text(ACT_DOC)
        self.assertIn("install_act_extension.bat", text)
        self.assertIn("%APPDATA%", text)
        self.assertIn("Что не подтверждено", text)
        self.assertIn("Analysis.Solve", text)

    def test_spaceclaim_guide_is_manual(self):
        text = read_text(SC_GUIDE)
        self.assertIn("File", text)
        self.assertIn("Script", text)
        self.assertIn("Run", text)
        self.assertIn("prepare_geometry.py", text)
        self.assertIn("create_named_selections.py", text)
        self.assertIn("не подтверждён", text)


if __name__ == "__main__":
    unittest.main()
