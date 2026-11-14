# -*- coding: utf-8 -*-
"""Статические проверки обвязки запуска (этап 6a), без живого ANSYS.

Проверяем не поведение Workbench (оно требует Windows + лицензии), а контракт
файлов: аргументы batch-запуска, отсутствие f-строк в журнале, вызов
``SendCommand``, маркер ``AUTOMATION-FAILED`` и разделение режимов в docs.
"""

import io
import os
import tokenize
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.path.join(ROOT, "scripts", "run_ansys.bat")
JOURNAL = os.path.join(ROOT, "scripts", "workbench_journal.py")
SC_GUIDE = os.path.join(ROOT, "scripts", "run_spaceclaim.md")
RUN_MODES = os.path.join(ROOT, "docs", "run-modes.md")


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
        position = self.text.index(marker)
        tail = self.text[position:position + 500]
        self.assertIn("exit /b 2", tail)

    def test_sets_repository_root_for_ansys_scripts(self):
        self.assertIn('set "ANSYS_AUTOMATION_ROOT=%ROOT%"', self.text)
        self.assertIn('set "ANSYS_PROJECT_PATH=%PROJECT%"', self.text)
        self.assertIn('set "STRUCTURE_ID=%STRUCTURE_ID%"', self.text)

    def test_creates_logs_and_redirects_both_streams(self):
        self.assertIn("logs", self.text)
        self.assertIn("> \"%LOG%\" 2>&1", self.text)
        self.assertIn("run-%STAMP%.log", self.text)

    def test_checks_marker_and_exit_code(self):
        self.assertIn("AUTOMATION-FAILED", self.text)
        self.assertIn("findstr", self.text)
        self.assertIn('if not "%RUN_RC%"=="0"', self.text)
        self.assertIn("RUN-OK", self.text)


class WorkbenchJournalTestCase(unittest.TestCase):
    """workbench_journal.py: py2-совместимый журнал с SendCommand и маркером."""

    def setUp(self):
        self.text = read_text(JOURNAL)

    def test_has_py2_coding_header(self):
        first_line = self.text.splitlines()[0]
        self.assertEqual(first_line, "# -*- coding: utf-8 -*-")

    def test_has_no_fstrings(self):
        self.assertEqual(find_fstrings(JOURNAL), [])

    def test_sends_python_command_to_mechanical(self):
        self.assertIn("SendCommand", self.text)
        self.assertIn('Language="Python"', self.text)
        self.assertIn("execfile", self.text)

    def test_marker_present_in_every_failure_branch(self):
        self.assertGreaterEqual(self.text.count("AUTOMATION-FAILED"), 2)
        # open project, find system, SendCommand, solve, save
        self.assertGreaterEqual(self.text.count("AUTOMATION-FAILED:"), 5)

    def test_solves_and_saves_project(self):
        self.assertIn("Solve(Wait=True)", self.text)
        self.assertIn("Save", self.text)

    def test_system_selection_uses_argument_or_first(self):
        self.assertIn("MECH_SYSTEM_NAME", self.text)
        self.assertIn("GetSystem(Name=", self.text)
        self.assertIn("STRUCTURE_ID", self.text)


class RunDocumentationTestCase(unittest.TestCase):
    """Памятки честно разделяют подтверждённое, неподтверждённое и ручное."""

    def test_run_modes_has_three_sections(self):
        text = read_text(RUN_MODES)
        self.assertIn("## Подтверждено", text)
        self.assertIn("## Не подтверждено", text)
        self.assertIn("## Ручное", text)

    def test_run_modes_marks_batch_and_sendcommand_confirmed(self):
        text = read_text(RUN_MODES)
        self.assertIn("runwb2 -B", text)
        self.assertIn("SendCommand", text)
        self.assertIn("SpaceClaim", text)

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
