# Python Script, API Version = V19
# -*- coding: utf-8 -*-
import re

"""
Named Selections:
- gu_fixed
- gu_force
- gu_remote_disp
- gu_bolt1_f
- gu_bolt2_f
- gu_bolt3_f
- gu_bolt4_f
"""
#GLOBAL

fxNUE = 162500
fyNUE = 162500
fzNUE = 98000
boltPretension = 31532

fixed_support_NS = "gu_fixed"
force_NS = "gu_force"
remote_disp_NS = "gu_remote_disp"

#global coefficients Sizing Controls
#names must equal NamedSelections

meshSettings = {
 "mbolt": 
     {
     "meshCoef": 6.7, 
     "meshMethod": MethodType.Sweep,
     "elementOrder": ElementOrder.ProgramControlled,
     },
 "mgaika":
     {
     "meshCoef": 7.2, 
     "meshMethod": MethodType.Sweep,
     "elementOrder": ElementOrder.ProgramControlled,
     },
 "shaiba":
     {
     "meshCoef": 2, 
     "meshMethod": MethodType.Sweep,
     "elementOrder": ElementOrder.ProgramControlled
     },
 "kruk":
     {
     "meshCoef": 4, 
     "meshMethod": MethodType.MultiZone,
     "elementOrder": ElementOrder.ProgramControlled
     },
 "opora":
     {
     "meshCoef": 3, 
     "meshMethod": MethodType.MultiZone,
     "elementOrder": ElementOrder.ProgramControlled
     },
 "opora_niz":
     {
     "meshCoef": 5, 
     "meshMethod": MethodType.MultiZone,
     "elementOrder": ElementOrder.Quadratic
     },
 "opora_verh":
     {
     "meshCoef": 4, 
     "meshMethod": MethodType.MultiZone,
     "elementOrder": ElementOrder.Quadratic
     },
 "truba":
     {
     "meshCoef": 4.08, 
     "meshMethod": MethodType.MultiZone,
     "elementOrder": ElementOrder.Quadratic
     },
  "shponka":
     {
     "meshCoef": 4, 
     "meshMethod": MethodType.MultiZone,
     "elementOrder": ElementOrder.ProgramControlled
     },
 "osnovanie":
     {
     "meshCoef": 2, 
     "meshMethod": MethodType.MultiZone,
     "elementOrder": ElementOrder.ProgramControlled
     },
 "podoporka":
     {
     "meshCoef": 2, 
     "meshMethod": MethodType.MultiZone,
     "elementOrder": ElementOrder.ProgramControlled,
     },
 "shov":
     {
     "meshCoef": 1, 
     "meshMethod": MethodType.Sweep,
     "elementOrder": ElementOrder.ProgramControlled
     },
 "shov_truba":
     {
     "meshCoef": 1, 
     "meshMethod": MethodType.Sweep,
     "elementOrder": ElementOrder.ProgramControlled
     },
 "upor":
     {
     "meshCoef": 3, 
     "meshMethod": MethodType.MultiZone,
     "elementOrder": ElementOrder.ProgramControlled
     }
 }

ns_dict = {}

mesh = Model.Mesh
mesh.ElementOrder = ElementOrder.Linear

nss = Model.NamedSelections.Children

def extract_number(entity_name):
    #matches = re.findall(r"(\d+\.?\d*)$",entity_name)
    match = re.match(r"^(.*?)([+-]?\d*\.\d+|\d+\.?\d*)$", entity_name)
    if match:
        name = match.group(1)
        float_number = float(match.group(2))
        return name, float_number
    
    return None

def get_named_selection_type(name_selection):
    if name_selection and type(name_selection) is Ansys.ACT.Automation.Mechanical.NamedSelection:
        print("named selection: {}".format(name_selection.Name))
        entities = name_selection.Location.Entities
        for entity in entities:
            entity_type = entity.__class__.__name__
            if entity_type is "Edge":
                return entity_type
            else:
                return None
        

for ns in nss:
    ns_id = ns.ObjectId
    ns_dict.Add(ns.Name,ns_id)
    ns_type = get_named_selection_type(ns)
    if not ns.Name.Contains("gu_"):
        try:
            sizing = mesh.AddSizing()
            sizing.Location = DataModel.GetObjectById(ns_id)
            sizing.RenameBasedOnDefinition()
            parsed = extract_number(ns.Name)
            
            
            method = mesh.AddAutomaticMethod()
            method.Location = DataModel.GetObjectById(ns_id)
            if parsed:
                if meshSettings.ContainsKey(parsed[0]):
                    itemMeshSettings = meshSettings.get(parsed[0])
                    
                    itemCoef = itemMeshSettings.get("meshCoef",1)
                    itemMethod = itemMeshSettings.get("meshMethod")
                    itemOrder = itemMeshSettings.get("elementOrder")
                    
                    method.Method = itemMethod
                    method.ElementOrder = itemOrder
                    if itemMethod is MethodType.MultiZone:
                        #0 - ProgramControlled, 1 - Uniform, 2 - Pave
                        method.SurfaceMeshMethod = 1
                        method.FreeMeshType = 3
                    elif itemMethod is MethodType.Sweep:
                        method.Algorithm =  MeshMethodAlgorithm.Axisymmetric
                    print(ns.Name," Debug: coef - ", itemCoef)
                    print(ns.Name," Debug: method - ", itemMethod)
                    eSize = round((parsed[1] / itemCoef),2)
                    sizing.ElementSize = Quantity( eSize, "mm")
                else:
                    print("Cant find sizing coefficient in meshSettings!: ",ns.Name)
            
            method.RenameBasedOnDefinition()
        except Exception as ex:
            print(ex.Message)

mesh.GroupAllSimilarChildren()
mesh.GenerateMesh()

ansys_analysis_settings_1 = DataModel.GetObjectsByName("Analysis Settings")[0]
ansys_analysis_settings_1.NumberOfSteps = 4
ansys_analysis_settings_1.LargeDeflection = 1
ansys_analysis_settings_1.NewtonRaphsonOption = NewtonRaphsonType.Unsymmetric
ansys_analysis_settings_1.NodalForces = OutputControlsNodalForcesType.Yes
ansys_analysis_settings_1.GeneralMiscellaneous = 1
ansys_analysis_settings_1.ContactMiscellaneous = 1

analysis = Model.Analyses[0]
fixed = analysis.AddFixedSupport()
fixed.Location = DataModel.GetObjectsByName(fixed_support_NS)[0]

remote_disp = analysis.AddRemoteDisplacement()
remote_disp.Location = DataModel.GetObjectsByName(remote_disp_NS)[0]

print("Добавлено Remote Displacement граничное условие")
print("Задаю нулевые углы поворота для всех степеней свободы...")

# Задание нулевых углов поворота аналогично заданию силы
time_points = [Quantity(0,"s"), Quantity(1,"s"), Quantity(2,"s"), Quantity(3,"s"), Quantity(4,"s")]
zero_values = [Quantity(0, "rad")] * 5

print("Временные точки для задания углов поворота: " + str([tp.Value for tp in time_points]))
print("Значения углов поворота: " + str([zv.Value for zv in zero_values]))

remote_disp.RotationX.Inputs[0].DiscreteValues = time_points
remote_disp.RotationX.Output.DiscreteValues = zero_values
print("RX задан: 0 рад на всех шагах")

remote_disp.RotationY.Inputs[0].DiscreteValues = time_points
remote_disp.RotationY.Output.DiscreteValues = zero_values
print("RY задан: 0 рад на всех шагах")

remote_disp.RotationZ.Inputs[0].DiscreteValues = time_points
remote_disp.RotationZ.Output.DiscreteValues = zero_values
print("RZ задан: 0 рад на всех шагах")

print("Углы поворота успешно заданы для всех 5 шагов нагружения")

force = analysis.AddForce()
force.Location = DataModel.GetObjectsByName(force_NS)[0]
force.DefineBy = LoadDefineBy.Components

force.XComponent.Inputs[0].DiscreteValues = [Quantity(0,"s"),Quantity(1,"s"),Quantity(2,"s"),Quantity(3,"s"),Quantity(4,"s")]
force.XComponent.Output.DiscreteValues=[Quantity(0,"N"),Quantity(0,"N"),Quantity(fxNUE*0.5,"N"),Quantity(fxNUE,"N"),Quantity(fxNUE*1.5,"N")]

force.YComponent.Inputs[0].DiscreteValues = [Quantity(0,"s"),Quantity(1,"s"),Quantity(2,"s"),Quantity(3,"s"),Quantity(4,"s")]
force.YComponent.Output.DiscreteValues=[Quantity(0,"N"),Quantity(fyNUE*0.1,"N"),Quantity(fyNUE*0.5,"N"),Quantity(fyNUE,"N"),Quantity(fyNUE*1.5,"N")]

force.ZComponent.Inputs[0].DiscreteValues = [Quantity(0,"s"),Quantity(1,"s"),Quantity(2,"s"),Quantity(3,"s"),Quantity(4,"s")]
force.ZComponent.Output.DiscreteValues=[Quantity(0,"N"),Quantity(fzNUE*0.1,"N"),Quantity(fzNUE*0.5,"N"),Quantity(fzNUE,"N"),Quantity(fzNUE*1.5,"N")]

for item in nss:
    if "gu_bolt" in item.Name:
        boltItem = analysis.AddBoltPretension()
        boltItem.Location = item
        boltItem.Preload.Output.SetDiscreteValue(0, Quantity(boltPretension,"N"))
        boltItem.SetDefineBy(2, BoltLoadDefineBy.Lock)
        boltItem.SetDefineBy(3, BoltLoadDefineBy.Lock)
        boltItem.SetDefineBy(4, BoltLoadDefineBy.Lock)

solu = DataModel.GetObjectsByName("Solution Information")[0]
solu.NewtonRaphsonResiduals = 4
solu.IdentifyElementViolations = 4

sol = solu.Parent
sol.AddTotalDeformation()

for ns in ns_dict:
    if ns.Contains("shov"):
        maxShear = sol.AddMaximumShearStress()
        maxShear.Location = ExtAPI.DataModel.GetObjectsByName(ns)[0]
        maxShear.DisplayOption =  ResultAveragingType.ElementalMean
    else:
        if not ns.Contains("gu_"):
            sol.AddStressIntensity().Location = ExtAPI.DataModel.GetObjectsByName(ns)[0]