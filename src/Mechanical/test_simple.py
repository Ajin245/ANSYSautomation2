# -*- coding: utf-8 -*-
import sys
from System.IO import Path

PROJECT_ROOT = r"C:\Users\user\source\repos\ANSYSautomation2"
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
