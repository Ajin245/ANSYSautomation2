# -*- coding: utf-8 -*-
import sys
import os
from System.IO import Path

PROJECT_ROOT = os.environ.get("ANSYS_AUTOMATION_ROOT")
if not PROJECT_ROOT:
    try:
        cur_file = sys._getframe().f_code.co_filename
    except:
        cur_file = __file__
    if cur_file and not cur_file.startswith('<'):
        cur_file = os.path.abspath(cur_file)
        if "src" in cur_file:
            parts = cur_file.split(os.sep)
            for i in range(len(parts) - 1, -1, -1):
                if parts[i] == "src":
                    PROJECT_ROOT = os.sep.join(parts[:i])
                    break
    if not PROJECT_ROOT:
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, "src")):
            PROJECT_ROOT = cwd
    if not PROJECT_ROOT:
        PROJECT_ROOT = os.path.join(os.path.expanduser("~"), "source", "repos", "ANSYSautomation2")

src_path = Path.Combine(PROJECT_ROOT, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from Mechanical.project_context import ProjectContext
    print("ProjectContext import success")
    ctx = ProjectContext(ExtAPI)
    print("ProjectContext created")

    from Mechanical.contact_manager import ContactManager
    print("ContactManager import success")
    cm = ContactManager(ctx)
    print("ContactManager created")

    from Mechanical.mesh_manager import MeshManager
    print("MeshManager import success")
    mm = MeshManager(ctx)
    print("MeshManager created")

    from Mechanical.analysis_manager import AnalysisManager
    print("AnalysisManager import success")
    am = AnalysisManager(ctx)
    print("AnalysisManager created")

    from Mechanical.validation_manager import ValidationManager
    print("ValidationManager import success")
    vm = ValidationManager(ctx)
    print("ValidationManager created")

    from Mechanical.result_manager import ResultManager
    print("ResultManager import success")
    rm = ResultManager(ctx)
    print("ResultManager created")

    print("ALL MANAGERS LOADED SUCCESSFULLY")

except Exception as e:
    import traceback
    print("ERROR DURING INITIALIZATION: " + str(e))
    print(traceback.format_exc())
