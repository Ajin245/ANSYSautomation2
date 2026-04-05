# -*- coding: utf-8 -*-
import re
import System
from System.IO import File, Path, StreamReader, Directory

# Configuration path and files
CONFIG_PATH = "E:\\OLEGG\\Other\\"

PROJECT_SETTINGS_FILE = CONFIG_PATH + "project_settings.json"
MESH_CONFIG_FILE = CONFIG_PATH + "mesh_config.json"
LOAD_DATABASE_FILE = CONFIG_PATH + "load_database.json"
ANALYSIS_SCENARIOS_FILE = CONFIG_PATH + "analysis_scenarios.json"
BOLT_DATABASE_FILE = CONFIG_PATH + "bolt_database.json"
CONTACT_SETTINGS_FILE = CONFIG_PATH + "contact_settings.json"

class ConfigurationManager:
    """Project configuration manager with hierarchy support"""
    
    @staticmethod
    def load_config(file_path):
        """Load configuration file with existence check"""
        if not File.Exists(file_path):
            raise System.Exception("Configuration file not found: " + file_path)
        
        try:
            with StreamReader(file_path) as stream:
                json_string = stream.ReadToEnd()
            
            # Remove comments and whitespace
            json_string = re.sub(r'//.*?\n', '', json_string)
            json_string = re.sub(r'/\*[\s\S]*?\*/', '', json_string)
            json_string = re.sub(r'\s+', '', '', json_string)
            
            return ConfigurationManager._parse_json(json_string)
            
        except Exception as e:
            raise System.Exception("Error loading " + file_path + ": " + str(e))
    
    @staticmethod
    def _parse_json(json_string):
        """Simple JSON parser for IronPython compatibility"""
        if json_string.startswith('{') and json_string.endswith('}'):
            return ConfigurationManager._parse_object(json_string[1:-1])
        elif json_string.startswith('[') and json_string.endswith(']'):
            return ConfigurationManager._parse_array(json_string[1:-1])
        elif json_string.startswith('"') and json_string.endswith('"'):
            return json_string[1:-1]
        elif json_string.lower() == 'true':
            return True
        elif json_string.lower() == 'false':
            return False
        elif json_string.lower() == 'null':
            return None
        else:
            try:
                if '.' in json_string:
                    return float(json_string)
                else:
                    return int(json_string)
            except:
                return json_string
    
    @staticmethod
    def _parse_object(obj_string):
        """Parse JSON object"""
        result = {}
        pairs = ConfigurationManager._split_pairs(obj_string)
        for pair in pairs:
            key, value = pair.split(':', 1)
            key = key.strip().strip('"')
            result[key] = ConfigurationManager._parse_json(value.strip())
        return result
    
    @staticmethod
    def _parse_array(array_string):
        """Parse JSON array"""
        result = []
        if not array_string:
            return result
        
        items = ConfigurationManager._split_items(array_string)
        for item in items:
            result.append(ConfigurationManager._parse_json(item.strip()))
        return result
    
    @staticmethod
    def _split_pairs(obj_string):
        """Split object into key-value pairs"""
        pairs = []
        depth = 0
        start = 0
        
        for i, char in enumerate(obj_string):
            if char == '{' or char == '[':
                depth += 1
            elif char == '}' or char == ']':
                depth -= 1
            elif char == ',' and depth == 0:
                pairs.append(obj_string[start:i])
                start = i + 1
        
        if start < len(obj_string):
            pairs.append(obj_string[start:])
        
        return pairs
    
    @staticmethod
    def _split_items(array_string):
        """Split array into items"""
        items = []
        depth = 0
        start = 0
        
        for i, char in enumerate(array_string):
            if char == '{' or char == '[':
                depth += 1
            elif char == '}' or char == ']':
                depth -= 1
            elif char == ',' and depth == 0:
                items.append(array_string[start:i])
                start = i + 1
        
        if start < len(array_string):
            items.append(array_string[start:])
        
        return items
    
    @staticmethod
    def load_structure_config(structure_type):
        """Load structure-specific configuration if exists"""
        structure_config_file = CONFIG_PATH + f"structure_{structure_type}_config.json"
        if File.Exists(structure_config_file):
            return ConfigurationManager.load_config(structure_config_file)
        return None
    
    @staticmethod
    def merge_configs(base_config, structure_config):
        """Merge structure config into base config (structure has priority)"""
        if not structure_config:
            return base_config
            
        merged = base_config.copy()
        for key, value in structure_config.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                # Recursive merge for dictionaries
                merged[key] = ConfigurationManager.merge_configs(merged[key], value)
            else:
                merged[key] = value
        return merged

class StructureDetector:
    """Detect structure type from model name and Named Selections"""
    
    @staticmethod
    def detect_structure_type():
        """Determine structure type from model name patterns"""
        model_name = Model.Name
        
        # Try to extract structure type from name pattern (e.g., "151-02-F2" -> "151")
        structure_match = re.match(r'^(\d+)-(\d{2})-F\d', model_name)
        if structure_match:
            return structure_match.group(1), "standard"
        
        # Try custom structure pattern (e.g., "custom_001-01-F1")
        custom_match = re.match(r'^(custom_\d+)-(\d{2})-F\d', model_name)
        if custom_match:
            return custom_match.group(1), "custom"
        
        # Fallback: use first part of model name
        parts = model_name.split('-')
        if parts:
            return parts[0], "unknown"
        
        return "default", "unknown"
    
    @staticmethod
    def analyze_ns_patterns():
        """Analyze Named Selections patterns to detect configuration"""
        all_ns = [ns.Name for ns in Model.NamedSelections.Children]
        
        # Detect presence of different NS types
        analysis = {
            "has_bolts": any("bolt" in ns.lower() for ns in all_ns),
            "has_pressure": any("pressure" in ns.lower() for ns in all_ns),
            "has_contact": any("contact" in ns.lower() for ns in all_ns),
            "has_remote": any("remote" in ns.lower() for ns in all_ns)
        }
        
        return analysis

class NamedSelectionManager:
    """Manager for Named Selections operations"""
    
    def __init__(self, project_settings):
        self.project_settings = project_settings
        self.all_ns = Model.NamedSelections.Children
        self.ns_cache = {}
    
    def get_ns_by_name(self, ns_name):
        """Get NS by name with caching"""
        if not ns_name:  # Handle empty names
            return None
            
        if ns_name in self.ns_cache:
            return self.ns_cache[ns_name]
        
        for ns in self.all_ns:
            if ns.Name == ns_name:
                self.ns_cache[ns_name] = ns
                return ns
        return None
        
    def get_ns_by_pattern(self, pattern):
        """Find NS by pattern using simple string matching"""
        if not pattern:
            return []
            
        matched_ns = []
        for ns in self.all_ns:
            if self._simple_pattern_match(ns.Name, pattern):
                matched_ns.append(ns)
        return matched_ns

    def _simple_pattern_match(self, name, pattern):
        """Simple pattern matching without fnmatch"""
        if not pattern or not name:
            return False
            
        if '*' in pattern:
            parts = pattern.split('*', 1)
            if len(parts) == 2:
                prefix, suffix = parts
                return name.startswith(prefix) and name.endswith(suffix)
            else:
                return pattern.replace('*', '') in name
        else:
            return name == pattern
            
    def validate_required_ns(self):
        """Simple validation - check if required NS exist"""
        missing_ns = []
        
        # Check boundary conditions NS
        bc_settings = self.project_settings["boundary_conditions"]
        for bc_type, ns_name in bc_settings.items():
            if ns_name and not self.get_ns_by_name(ns_name):
                missing_ns.append(f"{bc_type}: {ns_name}")
        
        # Check loads NS
        load_settings = self.project_settings["loads"]
        for load_type, ns_name in load_settings.items():
            if ns_name and not self.get_ns_by_name(ns_name):
                missing_ns.append(f"{load_type}: {ns_name}")
        
        if missing_ns:
            message = "Missing Named Selections:\n" + "\n".join(f"  - {ns}" for ns in missing_ns)
            print("WARNING: " + message)
            return False
        
        return True

class ExecutionManager:
    """Execution type manager"""
    
    def __init__(self, project_settings, load_database):
        self.project_settings = project_settings
        self.load_database = load_database
    
    def determine_execution_type(self):
        """Determine execution type from model name"""
        geometry_name = Model.Name
        
        # Try structure-specific pattern first
        structure_pattern = self.project_settings["execution"].get("name_pattern")
        if structure_pattern:
            match = re.match(structure_pattern, geometry_name)
            if match:
                return match.group(1)
        
        # Fallback to default pattern
        default_pattern = self.project_settings["execution"].get("default_pattern", r"(\d{2}-\d{2}-[Ff]\d)")
        match = re.match(default_pattern, geometry_name)
        if match:
            return match.group(1)
        
        # Final fallback
        default_execution = self.project_settings["execution"].get("default_execution")
        if default_execution:
            return default_execution
        
        raise System.Exception("Failed to determine execution type")
    
    def validate_execution(self, execution_type):
        """Validate execution existence in load database"""
        # Extract execution number and load group (e.g., "02-02-F1" -> "02", "F1")
        parts = execution_type.split('-')
        if len(parts) >= 3:
            execution_number = parts[0]
            load_group = parts[2].upper()
        else:
            # Try alternative format
            execution_number = parts[0] if len(parts) > 0 else execution_type
            load_group = "F1"  # Default load group
        
        if execution_number not in self.load_database:
            raise System.Exception("Loads not found for execution " + execution_number)
        
        if load_group not in self.load_database[execution_number]:
            raise System.Exception("Load group " + load_group + " not found for execution " + execution_number)
        
        return execution_number, load_group

class BoltManager:
    """Bolt connections manager"""
    
    def __init__(self, bolt_database, project_settings):
        self.bolt_database = bolt_database
        self.project_settings = project_settings
        self.ns_manager = NamedSelectionManager(project_settings)
    
    def has_bolts(self):
        """Check if there are any bolts in the model"""
        bolt_pattern = self.project_settings["loads"].get("bolt_pattern", "gu_bolt*_f")
        bolt_ns_list = self.ns_manager.get_ns_by_pattern(bolt_pattern)
        return len(bolt_ns_list) > 0
        
    def get_correct_bolt_pretension(self):
        """Get correct bolt pretension by analyzing mbolt bodies in model"""
        all_bodies = Model.Geometry.GetChildren(DataModelObjectCategory.Body, True)
        
        for body in all_bodies:
            body_name = body.Name
            if "mbolt" in body_name.lower():
                diameter_match = re.search(r'mbolt(\d+(?:\.\d+)?)', body_name, re.IGNORECASE)
                if diameter_match:
                    bolt_size = diameter_match.group(1)
                    if bolt_size in self.bolt_database:
                        pretension = self.bolt_database[bolt_size]["pretension"]
                        print("DEBUG: Using pretension from " + body_name + ": " + str(pretension) + "N")
                        return pretension
        
        # Fallback
        default_pretension = self.bolt_database.get("default", {}).get("pretension", 1350)
        print("DEBUG: Using default pretension: " + str(default_pretension) + "N")
        return default_pretension
        
    def apply_bolt_loads(self, analysis, steps_count):
        """Apply bolt loads with proper step configuration"""
        bolt_pattern = self.project_settings["loads"].get("bolt_pattern", "gu_bolt*_f")
        bolt_ns_list = self.ns_manager.get_ns_by_pattern(bolt_pattern)
        
        bolt_loads = []
        for ns in bolt_ns_list:
            try:
                bolt_pretension = self.get_correct_bolt_pretension()
                
                bolt = analysis.AddBoltPretension()
                bolt.Location = ns
                
                # Step 0 - pretension
                bolt.Preload.Output.SetDiscreteValue(0, Quantity(bolt_pretension, "N"))
                
                # Other steps - lock
                for i in range(2, steps_count):
                    bolt.SetDefineBy(i, BoltLoadDefineBy.Lock)
                
                bolt_loads.append(bolt)
                print("Created load for bolt NS " + ns.Name + " with pretension " + str(bolt_pretension) + "N")
            except Exception as e:
                print("Warning: Failed to create load for bolt NS " + ns.Name + ": " + str(e))
        
        return bolt_loads

class MeshManager:
    """Mesh settings manager"""
    
    def __init__(self, mesh_config, project_settings):
        self.mesh_config = mesh_config
        self.project_settings = project_settings
        if "mesh_settings" in mesh_config:
            self.sorted_keys = sorted(mesh_config["mesh_settings"].keys(), key=lambda x: len(x), reverse=True)
        else:
            self.sorted_keys = []
    
    def apply_mesh_settings(self):
        """Apply mesh settings to all NS"""
        mesh = Model.Mesh
        mesh.ElementOrder = ElementOrder.Linear
        
        ns_manager = NamedSelectionManager(self.project_settings)
        
        for ns in ns_manager.all_ns:
            if self._is_load_or_bc_ns(ns.Name):
                continue
                
            try:
                mesh_settings = self._get_mesh_settings(ns.Name)
                if mesh_settings:
                    self._create_sizing_and_method(ns, mesh_settings)
            except Exception as e:
                print("Warning during mesh creation for " + ns.Name + ": " + str(e))
        
        mesh.GroupAllSimilarChildren()
        mesh.GenerateMesh()
    
    def _is_load_or_bc_ns(self, ns_name):
        """Check if NS is for load or boundary condition"""
        bc_ns = []
        load_ns = []
        
        bc_settings = self.project_settings["boundary_conditions"]
        for bc_type in bc_settings:
            ns_name_val = bc_settings[bc_type]
            if ns_name_val:
                bc_ns.append(ns_name_val)
        
        load_settings = self.project_settings["loads"]
        for load_type in load_settings:
            ns_name_val = load_settings[load_type]
            if ns_name_val:
                load_ns.append(ns_name_val)
        
        all_special_ns = bc_ns + load_ns
        
        bolt_pattern = self.project_settings["loads"].get("bolt_pattern", "gu_bolt*_f")
        if self._simple_pattern_match(ns_name, bolt_pattern):
            return True
                
        return ns_name in all_special_ns
        
    def _simple_pattern_match(self, name, pattern):
        """Simple pattern matching"""
        if not pattern or not name:
            return False
            
        if '*' in pattern:
            parts = pattern.split('*', 1)
            if len(parts) == 2:
                prefix, suffix = parts
                return name.startswith(prefix) and name.endswith(suffix)
            else:
                return pattern.replace('*', '') in name
        else:
            return name == pattern
            
    def _get_mesh_settings(self, ns_name):
        """Get mesh settings for NS"""
        if not ns_name or "mesh_settings" not in self.mesh_config:
            return None
            
        parsed = self._extract_number(ns_name)
        if not parsed:
            return None
            
        base_name = parsed[0]
        
        for key in self.sorted_keys:
            if key == base_name or key in base_name:
                return self.mesh_config["mesh_settings"][key]
        
        return None
    
    def _extract_number(self, entity_name):
        """Extract number from entity name"""
        match = re.match(r"^(.*?)([+-]?\d*\.\d+|\d+\.?\d*)$", entity_name)
        if match:
            return match.group(1), float(match.group(2))
        return None
    
    def _create_sizing_and_method(self, ns, mesh_settings):
        """Create sizing and method for NS"""
        mesh = Model.Mesh
        
        sizing = mesh.AddSizing()
        sizing.Location = ns
        sizing.RenameBasedOnDefinition()
        
        parsed = self._extract_number(ns.Name)
        if parsed:
            dimension = parsed[1]
            mesh_coef = mesh_settings["meshCoef"]
            element_size = round(dimension / mesh_coef,3)
            sizing.ElementSize = Quantity(element_size, "mm")
        
        method = mesh.AddAutomaticMethod()
        method.Location = ns
        
        mesh_method = getattr(MethodType, mesh_settings["meshMethod"])
        element_order = getattr(ElementOrder, mesh_settings["elementOrder"])
        
        method.Method = mesh_method
        method.ElementOrder = element_order
        
        if mesh_method == MethodType.MultiZone:
            method.SurfaceMeshMethod = 1
        elif mesh_method == MethodType.Sweep:
            method.Algorithm = MeshMethodAlgorithm.Axisymmetric
        
        method.RenameBasedOnDefinition()

class AnalysisManager:
    """Analysis setup manager"""
    
    def __init__(self, project_settings, analysis_scenarios):
        self.project_settings = project_settings
        self.analysis_scenarios = analysis_scenarios
        self.ns_manager = NamedSelectionManager(project_settings)
    
    def setup_analysis(self, scenario_name="standard_sequence", has_bolts=False):
        """Setup analysis parameters"""
        analysis_settings = DataModel.GetObjectsByName("Analysis Settings")[0]
        scenario = self.analysis_scenarios[scenario_name]
        
        analysis_settings.NumberOfSteps = scenario["steps"]
        analysis_settings.LargeDeflection = True
        analysis_settings.NewtonRaphsonOption = NewtonRaphsonType.Unsymmetric
        analysis_settings.NodalForces = OutputControlsNodalForcesType.Yes
        analysis_settings.GeneralMiscellaneous = True
        analysis_settings.ContactMiscellaneous = True
        
        return analysis_settings
    
    def apply_boundary_conditions(self, analysis):
        """Apply all types of boundary conditions"""
        bc_settings = self.project_settings["boundary_conditions"]
        
        # Fixed support
        if bc_settings.get("fixed_support"):
            fixed_ns = self.ns_manager.get_ns_by_name(bc_settings["fixed_support"])
            if fixed_ns:
                fixed_support = analysis.AddFixedSupport()
                fixed_support.Location = fixed_ns
        
        # Displacement
        if bc_settings.get("displacement"):
            disp_ns = self.ns_manager.get_ns_by_name(bc_settings["displacement"])
            if disp_ns:
                displacement = analysis.AddDisplacement()
                displacement.Location = disp_ns
        
        # Remote Displacement
        if bc_settings.get("remote_displacement"):
            remote_disp_ns = self.ns_manager.get_ns_by_name(bc_settings["remote_displacement"])
            if remote_disp_ns:
                remote_disp = analysis.AddRemoteDisplacement()
                remote_disp.Location = remote_disp_ns
        
        # Remote Force
        if bc_settings.get("remote_force"):
            remote_force_ns = self.ns_manager.get_ns_by_name(bc_settings["remote_force"])
            if remote_force_ns:
                remote_force = analysis.AddRemoteForce()
                remote_force.Location = remote_force_ns
    
    def apply_loads(self, analysis, load_config, scenario_name, has_bolts=False):
        """Apply loads with proper step configuration"""
        load_settings = self.project_settings["loads"]
        scenario = self.analysis_scenarios[scenario_name]
        
        # Time steps configuration
        if has_bolts:
            time_steps = [Quantity(i, "s") for i in range(scenario["steps"] + 1)]
            load_factors_shifted = [0] + load_config["load_factors"]
        else:
            time_steps = [Quantity(i, "s") for i in range(scenario["steps"])]
            load_factors_shifted = load_config["load_factors"]
        
        # Force load
        if load_settings.get("force"):
            force_ns = self.ns_manager.get_ns_by_name(load_settings["force"])
            if force_ns:
                force = analysis.AddForce()
                force.Location = force_ns
                force.DefineBy = LoadDefineBy.Components
                
                for comp in ["X", "Y", "Z"]:
                    comp_lower = comp.lower()
                    force_value = load_config["forces"].get("f" + comp_lower, 0)
                    if force_value != 0:
                        comp_obj = getattr(force, comp + "Component")
                        comp_obj.Inputs[0].DiscreteValues = time_steps
                        values = [Quantity(force_value * factor, "N") for factor in load_factors_shifted]
                        comp_obj.Output.DiscreteValues = values
        
        # Moment load
        if load_settings.get("moment"):
            moment_ns = self.ns_manager.get_ns_by_name(load_settings["moment"])
            if moment_ns:
                moment = analysis.AddMoment()
                moment.Location = moment_ns
                moment.DefineBy = LoadDefineBy.Components
                
                for comp in ["X", "Y", "Z"]:
                    comp_lower = comp.lower()
                    moment_value = load_config["moments"].get("m" + comp_lower, 0)
                    if moment_value != 0:
                        comp_obj = getattr(moment, comp + "Component")
                        comp_obj.Inputs[0].DiscreteValues = time_steps
                        values = [Quantity(moment_value * factor, "N*mm") for factor in load_factors_shifted]
                        comp_obj.Output.DiscreteValues = values
        
        # Pressure load
        if load_settings.get("pressure"):
            pressure_ns = self.ns_manager.get_ns_by_name(load_settings["pressure"])
            if pressure_ns and load_config.get("pressure"):
                pressure = analysis.AddPressure()
                pressure.Location = pressure_ns
                pressure.Magnitude.Output.DiscreteValues = [
                    Quantity(load_config["pressure"] * factor, "MPa") 
                    for factor in load_factors_shifted
                ]

class ContactManager:
    """Contact pairs configuration manager"""
    """TODO Сейчас это работает не так. Нужен словарь в котором будут сопоставления 2 тех и на это сопоставление будет накладываться контакт"""
    def __init__(self, contact_settings):
        self.contact_settings = contact_settings
    
    def analyze_and_configure_contacts(self):
        """Configure contact pairs"""
        try:
            print("Configuring automatic contacts...")
            
            connections = Model.Connections
            contacts = connections.Children
            
            if contacts.Count > 0:
                connection_group = DataModel.GetObjectById(contacts[0].ObjectId)
                connection_group.ToleranceType = ContactToleranceType.Value
                connection_group.ToleranceValue = Quantity(0.5, "mm")
                
                Model.Connections.CreateAutomaticConnections()
                
                configured_count = 0
                for contact in connection_group.Children:
                    if contact.__class__.__name__ == "ContactRegion":
                        contact.RenameBasedOnDefinition()
                        if self._configure_contact(contact):
                            configured_count += 1
                
                print("Successfully configured " + str(configured_count) + " contact pairs")
                
        except Exception as e:
            print("Warning during contact configuration: " + str(e))
    
    def _configure_contact(self, contact):
        """Configure individual contact pair"""
        try:
            contact_bodies = contact.ContactBodies
            target_bodies = contact.TargetBodies
            
            if not contact_bodies or not target_bodies:
                return False
            
            config = self._find_contact_config(contact_bodies, target_bodies)
            if config:
                self._apply_contact_config(contact, config)
                return True
            return False
                
        except Exception as e:
            print("Error configuring contact: " + str(e))
            return False
    
    def _find_contact_config(self, contact_bodies, target_bodies):
        """Find contact configuration based on body names"""
        for config in self.contact_settings["contact_rules"]:
            if self._matches_config(contact_bodies, target_bodies, config):
                return config
        return None
    
    def _matches_config(self, contact_bodies, target_bodies, config):
        """Check if bodies match configuration patterns"""
        contact_pattern = config["contact_pattern"]
        target_pattern = config["target_pattern"]
        
        contact_match = any(self._simple_match(body, contact_pattern) for body in contact_bodies)
        target_match = any(self._simple_match(body, target_pattern) for body in target_bodies)
        
        return contact_match and target_match
    
    def _simple_match(self, name, pattern):
        """Simple pattern matching"""
        if not pattern or not name:
            return False
            
        if '*' in pattern:
            prefix, suffix = pattern.split('*', 1)
            return name.startswith(prefix) and name.endswith(suffix)
        else:
            return name == pattern
    
    def _apply_contact_config(self, contact, config):
        """Apply configuration to contact pair"""
        try:
            contact_type = getattr(ContactType, config["type"])
            contact.ContactType = contact_type
            
            if contact_type == ContactType.Frictional:
                contact.FrictionCoefficient = config["friction_coefficient"]
            
            detection_method = getattr(ContactDetectionPoint, config["detection_method"])
            contact.DetectionMethod = detection_method
            
            interface_treatment = getattr(ContactInitialEffect, config["interface_treatment"])
            contact.InterfaceTreatment = interface_treatment
            
            if contact_type == ContactType.Frictional and "offset" in config:
                contact.UserOffset = Quantity(config["offset"], "mm")
                
        except Exception as e:
            print("Error applying contact configuration: " + str(e))

class ResultsManager:
    """Results setup manager"""
    
    def __init__(self, project_settings):
        self.project_settings = project_settings
        self.ns_manager = NamedSelectionManager(project_settings)
    
    def setup_results(self):
        """Setup result sections"""
        solution_info = DataModel.GetObjectsByName("Solution Information")[0]
        solution_info.NewtonRaphsonResiduals = 4
        solution_info.IdentifyElementViolations = 4
        
        solution = solution_info.Parent
        solution.AddTotalDeformation()
        
        # Results for important NS
        important_keywords = self.project_settings.get("mesh_settings", {}).get("result_keywords", ["shov", "bolt", "opora", "truba", "osnovanie"])
        
        for ns in self.ns_manager.all_ns:
            if self._should_create_result_for_ns(ns.Name, important_keywords):
                self._create_stress_result(ns)
    
    def _should_create_result_for_ns(self, ns_name, important_keywords):
        """Determine if result should be created for NS"""
        # Skip load and BC NS
        bc_settings = self.project_settings["boundary_conditions"]
        load_settings = self.project_settings["loads"]
        
        all_special_ns = []
        for ns_list in [bc_settings, load_settings]:
            for ns_name_val in ns_list.values():
                if ns_name_val:
                    all_special_ns.append(ns_name_val)
        
        bolt_pattern = self.project_settings["loads"].get("bolt_pattern", "gu_bolt*_f")
        if self._simple_pattern_match(ns_name, bolt_pattern):
            return False
                
        if ns_name in all_special_ns:
            return False
        
        return any(keyword in ns_name for keyword in important_keywords)
    
    def _simple_pattern_match(self, name, pattern):
        """Simple pattern matching"""
        if not pattern or not name:
            return False
            
        if '*' in pattern:
            parts = pattern.split('*', 1)
            if len(parts) == 2:
                prefix, suffix = parts
                return name.startswith(prefix) and name.endswith(suffix)
            else:
                return pattern.replace('*', '') in name
        else:
            return name == pattern
    
    def _create_stress_result(self, ns):
        """Create stress results for NS"""
        solution = DataModel.GetObjectsByName("Solution")[0]
        
        if "shov" in ns.Name:
            shear_stress = solution.AddMaximumShearStress()
            shear_stress.Location = ns
            shear_stress.DisplayOption = ResultAveragingType.ElementalMean
        else:
            stress_intensity = solution.AddStressIntensity()
            stress_intensity.Location = ns

# MAIN EXECUTION LOGIC
try:
    print("=" * 60)
    print("AUTOMATED ANALYSIS SETUP INITIATED")
    print("=" * 60)
    
    # Step 1: Detect structure type
    print("1. Detecting structure type...")
    structure_type, structure_category = StructureDetector.detect_structure_type()
    ns_analysis = StructureDetector.analyze_ns_patterns()
    
    print(f"   Structure: {structure_type} ({structure_category})")
    print(f"   NS Analysis: {ns_analysis}")
    
    # Step 2: Load configurations with hierarchy
    print("2. Loading configuration hierarchy...")
    config_manager = ConfigurationManager()
    
    # Load base configurations
    base_project_settings = config_manager.load_config(PROJECT_SETTINGS_FILE)
    mesh_config = config_manager.load_config(MESH_CONFIG_FILE)
    base_load_database = config_manager.load_config(LOAD_DATABASE_FILE)
    analysis_scenarios = config_manager.load_config(ANALYSIS_SCENARIOS_FILE)
    bolt_database = config_manager.load_config(BOLT_DATABASE_FILE)
    contact_settings = config_manager.load_config(CONTACT_SETTINGS_FILE)
    
    # Load structure-specific configuration if exists
    structure_config = config_manager.load_structure_config(structure_type)
    if structure_config:
        print(f"   Loaded structure-specific config for {structure_type}")
        # Merge configurations (structure config has priority)
        project_settings = config_manager.merge_configs(base_project_settings, structure_config)
        
        # Use structure-specific load database if provided
        if "load_database" in structure_config:
            load_database = structure_config["load_database"]
            print("   Using structure-specific load database")
        else:
            load_database = base_load_database
    else:
        project_settings = base_project_settings
        load_database = base_load_database
        print("   Using base configuration")
    
    # Step 3: Initialize managers
    print("3. Initializing managers...")
    ns_manager = NamedSelectionManager(project_settings)
    execution_manager = ExecutionManager(project_settings, load_database)
    mesh_manager = MeshManager(mesh_config, project_settings)
    analysis_manager = AnalysisManager(project_settings, analysis_scenarios)
    bolt_manager = BoltManager(bolt_database, project_settings)
    contact_manager = ContactManager(contact_settings)
    results_manager = ResultsManager(project_settings)
    
    # Simple validation
    print("4. Validating configuration...")
    if not ns_manager.validate_required_ns():
        print("   WARNING: Some required Named Selections are missing")
    else:
        print("   Basic validation passed")
    
    # Step 5: Determine execution type
    print("5. Determining execution type...")
    execution_type = execution_manager.determine_execution_type()
    execution_number, load_group = execution_manager.validate_execution(execution_type)
    print(f"   Execution: {execution_type} (number: {execution_number}, load group: {load_group})")
    
    # Get load configuration
    execution_loads = load_database[execution_number]
    load_case = execution_loads[load_group]
    
    load_config = {
        "forces": load_case["nominal_forces"],
        "moments": load_case.get("nominal_moments", {"mx": 0, "my": 0, "mz": 0}),
        "load_factors": analysis_scenarios["standard_sequence"]["load_factors"]
    }
    
    # Add pressure if specified in load case
    if "pressure" in load_case:
        load_config["pressure"] = load_case["pressure"]
    
    # Step 6: Configure contacts
    print("6. Configuring contact pairs...")
    contact_manager.analyze_and_configure_contacts()
    
    # Step 7: Create mesh
    print("7. Creating mesh...")
    mesh_manager.apply_mesh_settings()
    
    # Step 8: Setup analysis
    print("8. Setting up analysis...")
    analysis = Model.Analyses[0]
    has_bolts = bolt_manager.has_bolts()
    
    analysis_manager.setup_analysis("standard_sequence", has_bolts)
    analysis_manager.apply_boundary_conditions(analysis)
    analysis_manager.apply_loads(analysis, load_config, "standard_sequence", has_bolts)
    
    # Apply bolt loads if present
    if has_bolts:
        bolt_manager.apply_bolt_loads(analysis, analysis_scenarios['standard_sequence']['steps'] + 1)
        print("   Bolt loads applied")
    
    # Step 9: Setup results
    print("9. Setting up results...")
    results_manager.setup_results()
    
    print("=" * 60)
    print("AUTOMATED ANALYSIS SETUP SUCCESSFULLY COMPLETED!")
    print(f"Structure: {structure_type}")
    print(f"Execution: {execution_type}") 
    print(f"Load Group: {load_group}")
    print("=" * 60)
    
except System.Exception as e:
    print("CRITICAL ERROR:")
    print("   " + str(e))
    print("   Analysis cannot be performed. Check configuration files and model.")
except Exception as e:
    print("UNKNOWN ERROR:")
    print("   " + str(e))
    print("   Please contact developer.")