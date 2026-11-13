# Python Script, API Version = V19
# -*- coding: utf-8 -*-
import os
import sys
import math
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

# ===== GEOMETRY PREPARATION METHODS (FROM ORIGINAL SCRIPT) =====
def delete_surface_bodies(doc):
    """Удаление всех тел с типом поверхность"""
    try:
        root_part = GetRootPart()
        all_bodies = root_part.GetAllBodies()
        surface_bodies = []
        for body in all_bodies:
            try:
                if body.Shape.Volume == 0.0:
                    surface_bodies.append(body)
            except:
                continue
        
        if surface_bodies:
            selection = Selection.CreateByObjects(surface_bodies)
            result = Delete.Execute(selection)
            print("Deleted " + str(len(surface_bodies)) + " surface bodies")
        else:
            print("No surface bodies found to delete")
            
    except Exception as ex:
        print("Exception in delete_surface_bodies(): " + str(ex))

def move_all_bodies_to_origin(doc):
    """Перемещение всех тел в начало координат (0,0,0)"""
    try:
        part = GetActivePart()
        bodies = part.Bodies
        selection = Selection.CreateByObjects(bodies)

        if selection.Count > 0:
            frame = Frame()
            ORIGIN_CS = CoordinateSystem.Create(part,"ORIGIN",frame)
            anchorPoint = Move.GetAnchorPoint(selection)
            upToSelection = Selection.CreateByObjects(ORIGIN_CS)
            options = MoveOptions()
            result = Move.UpTo(selection, upToSelection, anchorPoint, options)
            print("Moved all bodies to origin (0,0,0)")
        else:
            print("No bodies selected for moving to origin.")
        
    except Exception as ex:
        print("Exception in move_all_bodies_to_origin(): " + str(ex))

def rotate_tubes_to_axis(doc):
    """Поворот тел с 'truba' в имени так, чтобы их продольная ось была направлена вдоль оси X"""
    root_part = GetRootPart()
    all_bodies = root_part.GetAllBodies()
    try:

        truba_bodies = sc_helpers.select_bodies_by_keywords(all_bodies, ["truba"])
        podopor_bodies = sc_helpers.select_bodies_by_keywords(all_bodies, ["podopor"])
        
        if not truba_bodies:
            print("No bodies with 'truba' in name found for rotation")
            return
        if not podopor_bodies:
            print("No bodies with 'podopor' in name found")
            return
        
        for body in truba_bodies:
            try:
                shape = body.Shape
                
                min_x = float('inf')
                min_y = float('inf')
                min_z = float('inf')
                max_x = float('-inf')
                max_y = float('-inf')
                max_z = float('-inf')
                
                for vertex in shape.Vertices:
                    point = vertex.Position
                    if point.X < min_x: min_x = point.X
                    if point.Y < min_y: min_y = point.Y
                    if point.Z < min_z: min_z = point.Z
                    if point.X > max_x: max_x = point.X
                    if point.Y > max_y: max_y = point.Y
                    if point.Z > max_z: max_z = point.Z
                
                size_x = max_x - min_x
                size_y = max_y - min_y
                size_z = max_z - min_z
                
                print("Body {0}: size_x={1}, size_y={2}, size_z={3}".format(
                    body.GetName(), size_x, size_y, size_z))
                
                max_size = max(size_x, size_y, size_z)
                
                if max_size == size_x:
                    print("Body " + body.GetName() + " already aligned with X-axis")
                    continue
                elif max_size == size_y:
                    axis = Line.Create(Point.Create(0, 0, 0), Direction.Create(0, 0, 1))
                    angle = math.radians(90)
                else:
                    truba_origin = MeasureHelper.GetCenterOfMass(Selection.Create(body))
                    print("Center of mass for {0}: {1}".format(body.GetName(), truba_origin.Position))
                    axis = Line.Create(truba_origin, Direction.Create(0, 1, 0))
                    angle = math.radians(-90)
                
                # Поворачиваем только текущую трубу: выборка всех тел вращала сборку
                # целиком и ломала уже выровненные тела (дефект исходного скрипта).
                selection = Selection.Create(body)
                Move.Rotate(selection, axis, angle, MoveOptions())
                print("Rotated body: " + body.GetName() + " to align with X-axis")
            except Exception as e:
                print("Error rotating body " + body.GetName() + ": " + str(e))
        
        podopor_body = podopor_bodies[0]
        print("Found podopor body: " + podopor_body.GetName())
        
        largest_face = None
        max_area = 0
        
        for face in podopor_body.Faces:
            area = face.Area
            if area > max_area:
                max_area = area
                largest_face = face
        
        if largest_face is None:
            print("No faces found in podopor body")
            return
        
        print("Largest face area: "+ str(max_area))
        face_normal = largest_face.GetFaceNormal(0.5,0.5)
        z= face_normal.Z
        Selection.Create(largest_face).AddToActive()
        znorm = Direction.Create(1.0,0.0,0.0)
        vector_normal = face_normal.UnitVector
        if vector_normal.X != 0.0 or vector_normal.Y != 0.0:
            # Здесь "все тела" — намеренно: подопора разворачивает сборку как единое
            # целое, чтобы нормаль наибольшей грани легла на ось X. Это не тот случай,
            # что в цикле выше (там вращается одна труба). Оставлено как было в v2;
            # вопрос "вращать только подопору?" — в open_questions карточки.
            selection = Selection.CreateByObjects(all_bodies)
            origin_point = MeasureHelper.GetCenterOfMass(selection)
            axis = Line.Create(origin_point, Direction.Create(1, 0, 0))
            angle = math.radians(90)
            Move.Rotate(selection, axis, angle, MoveOptions())
            print("Rotated bodies to align with Z-axis")
        else:
            print("Bodies already aligned with Z-axis")
        
    except Exception as ex:
        print("Exception in rotate_tubes_to_x_axis(): " + str(ex))

def create_principal_planes(doc):
    """Создание основных ортогональных плоскостей в глобальной системе координат"""
    try:
        part = GetRootPart()
        plane_xy = Plane.Create(Frame.Create(Point.Create(0, 0, 0), 
                                           Direction.Create(1, 0, 0), 
                                           Direction.Create(0, 1, 0)))
        plane_yz = Plane.Create(Frame.Create(Point.Create(0, 0, 0), 
                                           Direction.Create(0, 1, 0), 
                                           Direction.Create(0, 0, 1)))
        plane_zx = Plane.Create(Frame.Create(Point.Create(0, 0, 0), 
                                           Direction.Create(0, 0, 1), 
                                           Direction.Create(1, 0, 0)))
        if plane_xy and  plane_yz and plane_zx:
            datumplaneXY = DatumPlane.Create(part,"Plane XY",plane_xy)
            datumplaneYZ = DatumPlane.Create(part,"Plane YZ",plane_yz)
            datumplaneZX = DatumPlane.Create(part,"Plane ZX",plane_zx)
            print("Created {0} planes".format(part.DatumPlanes.Count))
            
    except Exception as ex:
        print("Exception in create_principal_planes(): " + str(ex))

def create_pipeline_axis_plane(doc):
    """Создание новой плоскости, проходящей через центр масс трубопровода и параллельной глобальной плоскости XY"""
    try:
        root_part = GetRootPart()
        pipeline_bodies = sc_helpers.select_bodies_by_keywords(root_part.GetAllBodies(),
                                                              ["truba", "tryba"])
        
        if not pipeline_bodies:
            print("No bodies with 'truba' or 'tryba' in name found for pipeline axis plane")
            return
            
        target_body = pipeline_bodies[0]
        com_point = MeasureHelper.GetCenterOfMass(Selection.Create(target_body))
        
        frame = Frame.Create(com_point, Direction.Create(1, 0, 0), Direction.Create(0, 1, 0))
        plane = Plane.Create(frame)
        
        DatumPlane.Create(root_part, "Pipeline Axis Plane", plane);
        
        print("Successfully created plane 'Pipeline Axis Plane' at Z = {0}".format(com_point.Position.Z))
        
    except Exception as ex:
        print("Exception in create_pipeline_axis_plane(): " + str(ex))

# ===== MAIN EXECUTION =====
doc = DocumentHelper.GetActiveDocument()

if doc:
    print("--- STARTING SPACECLAIM GEOMETRY PREPARATION ---")

    structure_id = None
    try:
        structure_id = sc_helpers.resolve_structure_id(STRUCTURE_ID, sc_helpers.document_name(doc))
    except sc_helpers.StructureIdError as ex:
        print("CRITICAL ERROR: " + str(ex))

    if structure_id is None:
        print("CRITICAL ERROR: structure ID is not resolved. Geometry preparation aborted.")
    else:
        print("Structure ID: {0}".format(structure_id))
        config = sc_helpers.load_structure_config(structure_id)

        if config:
            sc_proc_settings = config.get("spaceclaim_processing", {})
            if sc_proc_settings.get("clean_geometry", True): # Default to true if not specified
                delete_surface_bodies(doc)
                rotate_tubes_to_axis(doc)
                move_all_bodies_to_origin(doc)
                create_principal_planes(doc)
                create_pipeline_axis_plane(doc)
            
            print("Geometry preparation completed successfully!")
            root_part = GetRootPart()
            all_bodies = root_part.GetAllBodies()
            selection = Selection.CreateByObjects(all_bodies)
            ViewHelper.ZoomToEntity(selection)
            Selection.Clear()
        else:
            print("CRITICAL ERROR: Configuration file not loaded. Geometry preparation aborted.")
else:
    print("Document not found!")
