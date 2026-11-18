# Python Script, API Version = V19
# -*- coding: utf-8 -*-
import os
import sys
from SpaceClaim.Api.V19 import *

# ===== ID КОНСТРУКЦИИ =====
# Номер конструкции (например, номер проекта Workbench). None — ID берётся из имени
# документа (Project_<id>); если и там нет, скрипт остановится с понятной ошибкой.
# Зашитого дефолта нет: FR-2, PLAN-MERGE §4.6.
STRUCTURE_ID = None

# ===== ПОДКЛЮЧЕНИЕ ЧИСТЫХ ПОМОЩНИКОВ =====
def _add_helpers_to_path():
    """Добавляет каталог скрипта в sys.path, чтобы работал 'import sc_helpers'.

    В SpaceClaim скрипт исполняется из редактора, и каталог скрипта не всегда попадает
    в sys.path. Порядок поиска: каталог скрипта -> ANSYS_AUTOMATION_ROOT/src/SpaceClaim
    -> cwd/src/SpaceClaim -> cwd.
    """
    candidates = []
    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass
    root = os.environ.get("ANSYS_AUTOMATION_ROOT")
    if root:
        candidates.append(os.path.join(root, "src", "SpaceClaim"))
    candidates.append(os.path.join(os.getcwd(), "src", "SpaceClaim"))
    candidates.append(os.getcwd())
    for path in candidates:
        if path and os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)

_add_helpers_to_path()

try:
    import sc_helpers
except ImportError as exc:
    print("CRITICAL ERROR: sc_helpers.py is not importable ({0}). "
          "Script stopped: without helpers the structure ID and config cannot be resolved.".format(exc))
    raise

# ===== NAMED SELECTION CREATION METHODS (FROM ORIGINAL SCRIPT) =====
def create_named_selections_for_unique_parts(doc):
    """Создает Named Selection для каждого уникального префикса имени тела"""
    if not doc:
        return
    
    root_part = GetRootPart()
    allBodies = root_part.GetAllBodies()
    names = [sc_helpers.body_name(body) for body in allBodies]

    for base_name in sc_helpers.unique_body_prefixes(names):
        matching_bodies = sc_helpers.select_bodies_by_prefix(allBodies, base_name)
        if matching_bodies:
            matching_selection = Selection.CreateByObjects(matching_bodies)
            NamedSelection.Create(matching_selection, Selection.Empty()).CreatedNamedSelection.SetName(base_name)
            print("Named Selection '{0}' created with {1} bodies".format(base_name, len(matching_bodies)))

def create_gu_fixed_lowest(doc):
    """Создает Named Selection 'gu_fixed' для самой нижней поверхности"""
    if not doc:
        return None
        
    try:
        root_part = GetRootPart()
        allBodies = root_part.GetAllBodies()
        minZCoord = float('inf')
        minZFace = None
        
        for b in allBodies:
            faces = b.Faces
            for f in faces:
                fSel = FaceSelection.Create(f)
                centroid = MeasureHelper.GetCentroid(fSel)
                if centroid.Z < minZCoord:
                    minZCoord = centroid.Z
                    minZFace = fSel
        
        if minZFace:
            new_group = NamedSelection.Create(minZFace, Selection.Empty())
            new_group.CreatedNamedSelection.SetName("gu_fixed")
            print("Named Selection 'gu_fixed' created successfully (lowest surface)")
            return new_group
        else:
            print("No suitable face found for 'gu_fixed'")
            return None
            
    except Exception as ex:
        print("Exception in create_gu_fixed_lowest():" + str(ex))
        return None

def create_gu_fixed_perimeter(doc):
    """Named Selection 'gu_fixed' по периметру — НЕ реализован (PLAN-MERGE Q8, ветвь A).

    Единственная конструкция с criteria='perimeter' — 10558, и она вне минимального
    прототипа. Реализовывать геометрию периметра «по догадке» нельзя, а тихо подменять
    criteria на 'bottom_faces' запрещено: это меняет смысл конфига. Поэтому функция
    честно останавливает скрипт с сообщением, а не возвращает None молча.
    """
    raise sc_helpers.PerimeterNotImplementedError(
        sc_helpers.PERIMETER_NOT_IMPLEMENTED_MESSAGE)

def create_gu_force_ns(doc):
    """Создает Named Selection 'gu_force' в центре масс труб"""
    if not doc:
        return None
        
    try:
        root_part = GetRootPart()
        bodies = root_part.GetAllBodies(r'^truba\d+')
        
        if not bodies:
            print("No bodies with 'truba' prefix found for 'gu_force'")
            return None

        curvePoints = []
        for b in bodies:
            for edge in b.Edges:
                # НЕ ПОДТВЕРЖДЕНО источником: 'GetChildren[ICurvePoint]()' — это
                # IronPython-синтаксис вызова generic-метода GetChildren<ICurvePoint>().
                # В RESEARCH-ANSYS-API.md §4 такого вызова нет (там описаны
                # BodySelection/FaceSelection, NamedSelection.Create, GetAllBodies,
                # body.Faces, body.Shape.Volume). Замену «по догадке» не ставлю:
                # нужен источник (CHM SpaceClaim.Api.V19) или прогон в 21R1.
                curvePoints.append(edge.GetChildren[ICurvePoint]())
                       
        sel = Selection.CreateByObjects(bodies)
        massCenter = MeasureHelper.GetCenterOfMass(sel)
        myPoint = Geometry.Point.Create(round(massCenter.X,4), round(massCenter.Y,4), round(massCenter.Z,4))
        Selection.Clear()

        forcePoint = []
        for curvePoint in curvePoints:
            for p in curvePoint:
                if (round(p.Position.X,4) == myPoint.Position.X and 
                    round(p.Position.Y,4) == myPoint.Position.Y and 
                    round(p.Position.Z,4) == myPoint.Position.Z):
                    forcePoint.append(p)
                
        if len(forcePoint) >0:
            print("forcePoint located SUCCESSFULLY")
            se = Selection.CreateByObjects(forcePoint[0])
            new_group = NamedSelection.Create(se, Selection.Empty())
            new_group.CreatedNamedSelection.SetName("gu_force")
            return new_group
        else:
            print("No force point found at center of mass")
            return None
            
    except Exception as ex:
        print("Exception in create_gu_force_ns():" + str(ex))
        return None

def create_gu_remote_disp_ns(doc):
    """Создает Named Selection 'gu_remote_disp' для торцов труб"""
    if not doc:
        return None
        
    try:
        root_part = GetRootPart()
        
        truba_bodies = sc_helpers.select_bodies_by_keywords(root_part.GetAllBodies(), ["truba"])
        
        if not truba_bodies:
            print("No pipe bodies found for 'gu_remote_disp'")
            return None
        
        all_face_data = []
        for body in truba_bodies:
            for face in body.Faces:
                try:
                    fSel = FaceSelection.Create(face)
                    centroid = MeasureHelper.GetCentroid(fSel)
                    area = face.Area
                    all_face_data.append({'face': face, 'body': body, 'centroid': centroid, 'area': area})
                except: continue
        
        if not all_face_data: return None
        
        x_coords = [data['centroid'].X for data in all_face_data]
        global_min_x = min(x_coords)
        global_max_x = max(x_coords)
        x_range = global_max_x - global_min_x
        tolerance = x_range * 0.01
        
        end_faces = []
        for body in truba_bodies:
            body_faces = [d for d in all_face_data if d['body'] == body]
            if not body_faces: continue
            
            left_candidates = []
            right_candidates = []
            for data in body_faces:
                centroid = data['centroid']
                face = data['face']
                area = data['area']
                if abs(centroid.X - global_min_x) <= tolerance:
                    left_candidates.append((face, area, centroid.X))
                elif abs(centroid.X - global_max_x) <= tolerance:
                    right_candidates.append((face, area, centroid.X))
            
            if left_candidates:
                left_candidates.sort(key=lambda x: x[1], reverse=True)
                end_faces.append(left_candidates[0][0])
            if right_candidates:
                right_candidates.sort(key=lambda x: x[1], reverse=True)
                end_faces.append(right_candidates[0][0])
        
        if end_faces:
            unique_faces = []
            seen_ids = set()
            for face in end_faces:
                face_id = id(face)
                if face_id not in seen_ids:
                    seen_ids.add(face_id)
                    unique_faces.append(face)
            
            NamedSelection.Create(Selection.CreateByObjects(unique_faces), Selection.Empty()).CreatedNamedSelection.SetName("gu_remote_disp")
            print("Named Selection 'gu_remote_disp' created with {0} faces".format(len(unique_faces)))
            return NamedSelection
        else:
            print("No end faces found for 'gu_remote_disp'")
            return None
            
    except Exception as ex:
        print("Exception in create_gu_remote_disp_ns(): " + str(ex))
        return None

# ===== MAIN EXECUTION =====
doc = DocumentHelper.GetActiveDocument()

if doc:
    print("--- STARTING SPACECLAIM NAMED SELECTION SETUP ---")

    structure_id = None
    try:
        structure_id = sc_helpers.resolve_structure_id(STRUCTURE_ID, sc_helpers.document_name(doc))
    except sc_helpers.StructureIdError as ex:
        print("CRITICAL ERROR: " + str(ex))

    if structure_id is None:
        print("CRITICAL ERROR: structure ID is not resolved. Named Selection setup aborted.")
    else:
        print("Structure ID: {0}".format(structure_id))
        config = sc_helpers.load_structure_config(structure_id)

        if config:
            # 1. Создание Named Selections для уникальных частей (по умолчанию)
            create_named_selections_for_unique_parts(doc)

            # 2. Создание специальных Named Selections на основе конфигурации
            sc_proc_settings = config.get("spaceclaim_processing", {})
            ns_definitions = sc_proc_settings.get("named_selections", [])

            for ns_def in ns_definitions:
                name = ns_def["name"]
                criteria = ns_def.get("criteria")

                if name == "gu_fixed":
                    try:
                        handler = sc_helpers.fixed_criteria_handler(criteria)
                    except ValueError as ex:
                        # Без gu_fixed расчёт неверен: тихо пропускать нельзя.
                        print("CRITICAL ERROR: " + str(ex))
                        raise
                    if handler == "lowest":
                        create_gu_fixed_lowest(doc)
                    elif handler == "perimeter":
                        # 10558 вне прототипа (Q8, ветвь A): обработчик поднимает
                        # PerimeterNotImplementedError с понятным сообщением.
                        try:
                            create_gu_fixed_perimeter(doc)
                        except sc_helpers.PerimeterNotImplementedError as ex:
                            print("CRITICAL ERROR: " + str(ex))
                            raise
                elif name == "gu_force":
                    create_gu_force_ns(doc)
                elif name == "gu_remote_disp":
                    create_gu_remote_disp_ns(doc)
                # Добавьте сюда другие Named Selections, если они будут в JSON
                else:
                    print("WARNING: Named Selection '{0}' from config is not handled by script.".format(name))

            print("Named Selection setup completed successfully!")
        else:
            print("CRITICAL ERROR: Configuration file not loaded. Named Selection setup aborted.")
else:
    print("Document not found!")
