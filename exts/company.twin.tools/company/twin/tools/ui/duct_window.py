import omni.ui as ui
import omni.usd
from pxr import Gf, UsdGeom, Usd
import json
import os
import math
from ..objects.duct_warp import DuctWarpGenerator
from ..core.smacna import SMACNADuctSizer, PressureClass

DATA_PATH = "c:/Programming/buildteamai/data/ducts.json"

class ListItem(ui.AbstractItem):
    def __init__(self, text):
        super().__init__()
        self.model = ui.SimpleStringModel(text)

class ListItemModel(ui.AbstractItemModel):
    def __init__(self, items):
        super().__init__()
        self._items = [ListItem(text) for text in items]
        self._current_index = ui.SimpleIntModel()
        self._current_index.add_value_changed_fn(self._on_index_changed)
        
    def _on_index_changed(self, model):
        self._item_changed(None)

    def get_item_children(self, item):
        return self._items if item is None else []

    def get_item_value_model(self, item, column_id):
        if item is None:
            return self._current_index
        return item.model

class DuctWindow(ui.Window):
    def __init__(self, title="Create Duct (Warp)", **kwargs):
        super().__init__(title, width=380, height=550, **kwargs)
        
        self._width_model = ui.SimpleFloatModel(20.0)
        self._height_model = ui.SimpleFloatModel(10.0)
        
        # Type selection (Straight vs Elbow)
        self._type_index = ui.SimpleIntModel(0) # 0=Straight, 1=Elbow
        self._types = ["Straight", "Elbow"]
        self._straight_fields = None
        self._elbow_fields = None
        self._radius_model = ui.SimpleFloatModel(30.0)
        self._angle_model = ui.SimpleFloatModel(90.0)
        self._length_model = ui.SimpleFloatModel(24.0)  # For straight ducts
        self._segments_model = ui.SimpleIntModel(20)
        self._add_flanges_model = ui.SimpleBoolModel(True)
        
        # Shape selection (Rectangular or Round)
        self._shape_index = ui.SimpleIntModel(0)  # 0 = Rectangular, 1 = Round
        self._shapes = ["Rectangular", "Round"]
        self._diameter_model = ui.SimpleFloatModel(12.0)  # For round ducts
        
        # UI elements to toggle visibility
        self._rect_fields = None
        self._round_fields = None
        
        # Engineering inputs (SMACNA)
        self._cfm_model = ui.SimpleFloatModel(1000.0)  # Airflow in CFM
        self._velocity_model = ui.SimpleFloatModel(1200.0)  # Velocity in FPM
        self._pressure_class_index = ui.SimpleIntModel(2)  # Index into pressure classes
        self._aspect_ratio_model = ui.SimpleFloatModel(1.0)  # 1.0 = square
        self._pressure_classes = ["1/2\" w.g.", "1\" w.g.", "2\" w.g.", "3\" w.g.", "4\" w.g."]
        self._pressure_values = [0.5, 1.0, 2.0, 3.0, 4.0]
        
        # Calculated outputs
        self._gauge_label = None
        self._stiffener_label = None
        
        # Edit mode tracking
        self._editing_prim_path = None
        self._create_button = None
        self._status_label = None
        
        # Load variants
        self._variants = self._load_variants()
        if self._variants:
            self._variant_names = [v["name"] for v in self._variants]
            self._variant_model = ListItemModel(self._variant_names)
            self._variant_model.get_item_value_model(None, 0).add_value_changed_fn(
                lambda m: self._on_variant_changed(m.as_int)
            )
        else:
            self._variant_names = []
            self._variant_model = None
        
        self._build_ui()
        
    def _load_variants(self):
        if os.path.exists(DATA_PATH):
            try:
                with open(DATA_PATH, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading duct variants: {e}")
        return []
        
    def _on_variant_changed(self, index):
        if 0 <= index < len(self._variants):
            data = self._variants[index]
            self._width_model.as_float = data.get("width", 20.0)
            self._height_model.as_float = data.get("height", 10.0)
            self._radius_model.as_float = data.get("radius", 30.0)
            self._angle_model.as_float = data.get("angle", 90.0)
            self._segments_model.as_int = data.get("segments", 20)
    
    def _on_shape_changed(self, index):
        """Toggle UI visibility based on shape selection"""
        self._shape_index.as_int = index
        is_round = (index == 1)
        
        if self._rect_fields:
            self._rect_fields.visible = not is_round
        if self._round_fields:
            self._round_fields.visible = is_round
        if hasattr(self, '_flange_label') and self._flange_label:
            self._flange_label.text = "(companion)" if is_round else "(angle iron)"

    def _on_type_changed(self, index):
        """Toggle UI visibility based on type selection (Straight/Elbow)"""
        self._type_index.as_int = index
        is_straight = (index == 0)
        
        if self._straight_fields:
            self._straight_fields.visible = is_straight
        if self._elbow_fields:
            self._elbow_fields.visible = not is_straight
        
    def _build_ui(self):
        with self.frame:
            with ui.ScrollingFrame():
                with ui.VStack(height=0, spacing=8, padding=15):
                    # === ENGINEERING INPUTS ===
                    ui.Label("Engineering Inputs", style={"highlight_color": 0xFF00AAFF, "font_size": 18})
                    ui.Label("Enter airflow requirements to auto-calculate duct size", style={"color": 0xFF888888, "font_size": 12})
                    
                    with ui.HStack(height=22):
                        ui.Label("CFM:", width=100)
                        ui.FloatDrag(model=self._cfm_model, min=50.0, max=50000.0, step=50)
                        ui.Label("cfm", width=30, style={"color": 0xFF888888})
                    
                    with ui.HStack(height=22):
                        ui.Label("Velocity:", width=100)
                        ui.FloatDrag(model=self._velocity_model, min=200.0, max=4000.0, step=50)
                        ui.Label("fpm", width=30, style={"color": 0xFF888888})
                    
                    with ui.HStack(height=22):
                        ui.Label("Pressure Class:", width=100)
                        pressure_model = ListItemModel(self._pressure_classes)
                        pressure_model.get_item_value_model(None, 0).as_int = self._pressure_class_index.as_int
                        pressure_model.get_item_value_model(None, 0).add_value_changed_fn(
                            lambda m: setattr(self._pressure_class_index, 'as_int', m.as_int)
                        )
                        ui.ComboBox(pressure_model)
                    
                    with ui.HStack(height=22):
                        ui.Label("Aspect Ratio:", width=100)
                        ui.FloatSlider(model=self._aspect_ratio_model, min=1.0, max=4.0, step=0.1)
                        ui.Label("(W/H)", width=40, style={"color": 0xFF888888})
                    
                    ui.Spacer(height=5)
                    ui.Button("Calculate Size", clicked_fn=self._on_calculate_size, height=30, 
                              style={"background_color": 0xFF2D5A27})
                    
                    # Calculated results display
                    with ui.HStack(height=20):
                        ui.Label("Gauge:", width=60)
                        self._gauge_label = ui.Label("--", style={"color": 0xFF00FF88})
                        ui.Spacer(width=20)
                        ui.Label("Stiffener:", width=60)
                        self._stiffener_label = ui.Label("--", style={"color": 0xFF00FF88})
                    
                    ui.Spacer(height=5)
                    ui.Separator(height=5)
                    ui.Spacer(height=5)
                    
                    # === GEOMETRY PARAMETERS ===
                    ui.Label("Geometry Parameters", style={"font_size": 16})
                    
                    # Shape Selection (Rectangular or Round)
                    with ui.HStack(height=22):
                        ui.Label("Shape:", width=100)
                        shape_model = ListItemModel(self._shapes)
                        shape_model.get_item_value_model(None, 0).as_int = self._shape_index.as_int
                        shape_model.get_item_value_model(None, 0).add_value_changed_fn(
                            lambda m: self._on_shape_changed(m.as_int)
                        )
                        ui.ComboBox(shape_model)

                    # Type Selection (Straight or Elbow)
                    with ui.HStack(height=22):
                        ui.Label("Type:", width=100)
                        type_model = ListItemModel(self._types)
                        type_model.get_item_value_model(None, 0).as_int = self._type_index.as_int
                        type_model.get_item_value_model(None, 0).add_value_changed_fn(
                            lambda m: self._on_type_changed(m.as_int)
                        )
                        ui.ComboBox(type_model)
                    
                    # Variants Dropdown
                    if self._variant_model:
                        with ui.HStack(height=20):
                            ui.Label("Preset:", width=100)
                            ui.ComboBox(self._variant_model)
                    
                    # === RECTANGULAR DUCT FIELDS ===
                    self._rect_fields = ui.VStack(height=0, spacing=4)
                    with self._rect_fields:
                        with ui.HStack(height=22):
                            ui.Label("Width:", width=100)
                            ui.FloatDrag(model=self._width_model, min=1.0, max=500.0)
                            ui.Label("in", width=20, style={"color": 0xFF888888})
                            
                        with ui.HStack(height=22):
                            ui.Label("Height:", width=100)
                            ui.FloatDrag(model=self._height_model, min=1.0, max=500.0)
                            ui.Label("in", width=20, style={"color": 0xFF888888})
                    
                    # === ROUND DUCT FIELDS ===
                    self._round_fields = ui.VStack(height=0, spacing=4, visible=False)
                    with self._round_fields:
                        with ui.HStack(height=22):
                            ui.Label("Diameter:", width=100)
                            ui.FloatDrag(model=self._diameter_model, min=4.0, max=60.0)
                            ui.Label("in", width=20, style={"color": 0xFF888888})
                    
                    # === COMMON FIELDS ===
                    # STRAIGHT FIELDS (Length)
                    self._straight_fields = ui.VStack(height=0, spacing=4)
                    with self._straight_fields:
                        with ui.HStack(height=22):
                            ui.Label("Length:", width=100)
                            ui.FloatDrag(model=self._length_model, min=1.0, max=1000.0)
                            ui.Label("(inches)", style={"color": 0xFF888888})
                    
                    # ELBOW FIELDS (Radius, Angle, Segments)
                    self._elbow_fields = ui.VStack(height=0, spacing=4, visible=False)
                    with self._elbow_fields:
                        with ui.HStack(height=22):
                            ui.Label("Bend Radius:", width=100)
                            ui.FloatDrag(model=self._radius_model, min=1.0, max=1000.0)
                            ui.Label("in", width=20, style={"color": 0xFF888888})
                            
                        with ui.HStack(height=22):
                            ui.Label("Angle (deg):", width=100)
                            ui.FloatDrag(model=self._angle_model, min=1.0, max=180.0)
                            
                        with ui.HStack(height=22):
                            ui.Label("Segments:", width=100)
                            ui.IntSlider(model=self._segments_model, min=4, max=100)
                    
                    with ui.HStack(height=22):
                        ui.Label("Add Flanges:", width=100)
                        ui.CheckBox(model=self._add_flanges_model)
                        self._flange_label = ui.Label("(angle iron)", style={"color": 0xFF888888})
                        
                    ui.Spacer(height=10)
                    ui.Separator(height=5)
                    ui.Spacer(height=10)
                    
                    # Edit mode controls
                    with ui.HStack(height=35, spacing=5):
                        ui.Button("Load Selected", clicked_fn=self._on_load_selected, height=35)
                        ui.Button("Clear", clicked_fn=self._on_clear, height=35)
                    
                    ui.Spacer(height=5)
                    
                    # Create/Update button
                    self._create_button = ui.Button("Generate Duct", clicked_fn=self._on_generate, height=40)
                    
                    self._status_label = ui.Label("", style={"color": 0xFF888888})
                    
                    ui.Spacer(height=10)
                    ui.Separator(height=10)
                    
                    ui.Label("Assembly Tools", style={"font_size": 16})
                    ui.Label("Select two ducts to mate them.", style={"color": 0xFFAAAAAA, "font_size": 12})
                    with ui.HStack(height=30, spacing=10):
                        ui.Button("Mate Selected", clicked_fn=self._on_mate_selected)
    
    def _on_calculate_size(self):
        """Calculate duct size from CFM and velocity using SMACNA standards."""
        cfm = self._cfm_model.as_float
        velocity = self._velocity_model.as_float
        aspect_ratio = self._aspect_ratio_model.as_float
        pressure_index = self._pressure_class_index.as_int
        pressure_class = self._pressure_values[pressure_index] if pressure_index < len(self._pressure_values) else 2.0
        
        # Calculate duct size
        duct_size = SMACNADuctSizer.calculate_duct_size(cfm, velocity, aspect_ratio)
        
        # Update width/height models
        self._width_model.as_float = duct_size.width
        self._height_model.as_float = duct_size.height
        
        # Get gauge
        gauge_info = SMACNADuctSizer.get_gauge(duct_size.width, duct_size.height, pressure_class)
        
        # Get stiffener requirements
        length = self._length_model.as_float
        stiffener_req = SMACNADuctSizer.get_stiffener_requirements(
            duct_size.width, duct_size.height, length, gauge_info.gauge, pressure_class
        )
        
        # Update display labels
        if self._gauge_label:
            self._gauge_label.text = f"{gauge_info.gauge} ga ({gauge_info.thickness_in:.4f}\")"
        if self._stiffener_label:
            self._stiffener_label.text = stiffener_req.stiffener_type.value.replace("_", " ").title()
        
        # Update status
        if self._status_label:
            actual_velocity = cfm / (duct_size.area_sqin / 144.0)
            self._status_label.text = f"Calculated: {duct_size.width}\" × {duct_size.height}\" (Actual: {actual_velocity:.0f} FPM)"
        
        print(f"[MEP] Calculated duct: {duct_size.width}\" × {duct_size.height}\"")
        print(f"[MEP] Gauge: {gauge_info.gauge}, Stiffener: {stiffener_req.stiffener_type.value}")
    
    def _on_shape_changed(self, index):
        """Toggles visibility of shape-specific fields"""
        # Update the source of truth model
        self._shape_index.as_int = index
        
        is_round = (index == 1)
        if self._rect_fields:
            self._rect_fields.visible = not is_round
        if self._round_fields:
            self._round_fields.visible = is_round
            
    def _on_load_selected(self):
        """Loads parameters from selected duct prim"""
        try:
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            if not stage:
                self._status_label.text = "Error: No USD Stage open"
                return

            selection = ctx.get_selection()
            selected_paths = selection.get_selected_prim_paths()

            if not selected_paths:
                self._status_label.text = "No prim selected"
                return

            # Get first selected prim
            prim_path = selected_paths[0]
            prim = stage.GetPrimAtPath(prim_path)

            if not prim:
                self._status_label.text = f"Error: Could not get prim at {prim_path}"
                return

            # Check if it's a duct
            custom_data = prim.GetCustomData()
            generator_type = custom_data.get('generatorType')

            valid_types = ['duct_bent', 'duct_straight', 'duct_round_bent', 'duct_round_straight']
            if generator_type not in valid_types:
                self._status_label.text = f"Selected prim is not a duct (type: {generator_type})"
                return

            # Determine Type (Straight vs Elbow)
            is_straight_type = 'straight' in str(generator_type)
            
            # Load parameters
            width = custom_data.get('width', 20.0)
            height = custom_data.get('height', 10.0)
            radius = custom_data.get('radius', 30.0)
            angle = custom_data.get('angle', 90.0)
            segments = custom_data.get('segments', 20)
            add_flanges = custom_data.get('add_flanges', True)
            length = custom_data.get('length', 24.0)
            diameter = custom_data.get('diameter', 12.0)
            shape_str = custom_data.get('shape', 'rectangular')

            # Update UI models
            is_round = (shape_str == 'round') or ('round' in str(generator_type))
            
            if is_round:
                self._shape_index.as_int = 1
                self._diameter_model.as_float = float(diameter)
            else:
                self._shape_index.as_int = 0
                self._width_model.as_float = float(width)
                self._height_model.as_float = float(height)
            
            # Update Type Index (0=Straight, 1=Elbow)
            self._type_index.as_int = 0 if is_straight_type else 1
            
            # Manually trigger visibility updates
            self._on_shape_changed(self._shape_index.as_int)
            self._on_type_changed(self._type_index.as_int)

            self._radius_model.as_float = float(radius)
            self._angle_model.as_float = float(angle)
            self._segments_model.as_int = int(segments)
            self._add_flanges_model.as_bool = bool(add_flanges)
            self._length_model.as_float = float(length)

            # Set edit mode
            self._editing_prim_path = prim_path
            if self._create_button:
                self._create_button.text = "Update Duct"

            self._status_label.text = f"Loaded from {prim_path}"
            print(f"Loaded duct from {prim_path} (Type: {'Straight' if is_straight_type else 'Elbow'})")
            print(f"  W={width}, H={height}, R={radius}, Angle={angle}°, Segments={segments}")

        except Exception as e:
            self._status_label.text = f"Error loading: {str(e)}"
            print(f"Error loading selected duct: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_clear(self):
        """Clears edit mode and resets to create mode"""
        self._editing_prim_path = None
        if self._create_button:
            self._create_button.text = "Generate Duct"
        self._status_label.text = "Ready to create new duct"
        print("Cleared edit mode - ready to create new duct")
                
    def _on_generate(self):
        stage = omni.usd.get_context().get_stage()
        if not stage:
            self._status_label.text = "Error: No Stage Open"
            return
        
        is_update = self._editing_prim_path is not None
        action = "Updating" if is_update else "Creating"
        
        # Determine path
        # Determine path
        current_transform = []
        if is_update:
            path = self._editing_prim_path
            # Capture transform before removing
            from ..utils import usd_utils
            prim = stage.GetPrimAtPath(path)
            if prim:
                current_transform = usd_utils.get_local_transform(prim)
            
            # Remove old prim
            stage.RemovePrim(path)
        else:
            path_root = "/World/Duct"
            path = path_root
            idx = 1
            while stage.GetPrimAtPath(path):
                path = f"{path_root}_{idx}"
                idx += 1
            
        try:
            # Determine shape
            shape = "round" if self._shape_index.as_int == 1 else "rectangular"
            
            # Determine Type (Straight vs Elbow)
            is_straight = (self._type_index.as_int == 0)
            
            # If Straight, Force Angle = 0. If Elbow, use Angle model.
            angle_val = 0.0 if is_straight else self._angle_model.as_float
            
            DuctWarpGenerator.create(
                stage, 
                path,
                width=self._width_model.as_float,
                height=self._height_model.as_float,
                radius=self._radius_model.as_float,
                angle_deg=angle_val,
                segments=self._segments_model.as_int,
                add_flanges=self._add_flanges_model.as_bool,
                length=self._length_model.as_float,
                shape=shape,
                diameter=self._diameter_model.as_float
            )
            
            # Restore Transform if we captured one
            from ..utils import usd_utils
            if current_transform:
                new_prim = stage.GetPrimAtPath(path)
                if new_prim:
                    usd_utils.set_local_transform(new_prim, current_transform)
            elif not is_update:
                # Smart Placement (Optional): Place near selection if new?
                # For now, let it spawn at origin or user can move it.
                pass
            
            action_past = "Updated" if is_update else "Created"
            self._status_label.text = f"{action_past} at {path}"
            print(f"{action_past} duct at {path}")
            
            # If we were updating, stay in edit mode
            if is_update:
                print(f"  Still editing {path} - modify and click 'Update Duct' again, or 'Clear' to create new")
                
        except Exception as e:
            self._status_label.text = f"Error: {str(e)}"
            print(f"[Duct] {e}")
            import traceback
            traceback.print_exc()

    def _on_mate_selected(self):
        """
        Mates two selected ducts by aligning their closest anchors.
        """
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        selection = ctx.get_selection().get_selected_prim_paths()
        
        if len(selection) != 2:
            self._status_label.text = "Select exactly 2 ducts to mate"
            return
            
        prim_a = stage.GetPrimAtPath(selection[0])
        prim_b = stage.GetPrimAtPath(selection[1])
        
        if not prim_a or not prim_b:
            return

        # Find anchors for both objects
        def get_anchor(prim, name):
            for child in prim.GetChildren():
                if child.GetName() == name:
                    return child
            return None
        
        # For proper HVAC airflow:
        # Duct A's EXIT (Anchor_End) connects to Duct B's ENTRY (Anchor_Start)
        # This means B moves so its Start aligns with A's End
        
        anchor_a = get_anchor(prim_a, "Anchor_End")  # Exit of first duct
        anchor_b = get_anchor(prim_b, "Anchor_Start")  # Entry of second duct
        
        if not anchor_a:
            self._status_label.text = "First duct has no Anchor_End (exit)"
            return
        if not anchor_b:
            self._status_label.text = "Second duct has no Anchor_Start (entry)"
            return
            
        # === Full 6DOF Mating ===
        # Goal: Move and Rotate B so its Anchor_Start aligns with A's Anchor_End
        # The anchors face OUTWARD (+X in their local frame)
        # For mating, B's anchor should face OPPOSITE to A's anchor (they face each other)
        
        print("[Mate] === Starting 6DOF Mate ===")
        
        # 1. Get world transforms of both anchors
        mat_anchor_a = omni.usd.get_world_transform_matrix(anchor_a)
        mat_anchor_b = omni.usd.get_world_transform_matrix(anchor_b)
        mat_duct_b = omni.usd.get_world_transform_matrix(prim_b)
        
        pos_anchor_a = mat_anchor_a.ExtractTranslation()
        pos_anchor_b = mat_anchor_b.ExtractTranslation()
        pos_duct_b = mat_duct_b.ExtractTranslation()
        
        print(f"[Mate] Anchor A pos: {pos_anchor_a}")
        print(f"[Mate] Anchor B pos: {pos_anchor_b}")
        print(f"[Mate] Duct B pos: {pos_duct_b}")
        
        # 2. Extract directions (X-axis of each anchor in world space)
        # The first column of the rotation matrix is the X-axis
        rot_a = mat_anchor_a.ExtractRotationMatrix()
        rot_b = mat_anchor_b.ExtractRotationMatrix()
        
        dir_a = Gf.Vec3d(rot_a.GetColumn(0))  # A's exit direction
        dir_b = Gf.Vec3d(rot_b.GetColumn(0))  # B's entry direction
        
        print(f"[Mate] Dir A (exit): {dir_a}")
        print(f"[Mate] Dir B (entry): {dir_b}")
        
        # 3. Calculate required rotation
        # We want dir_b to become -dir_a (opposite directions)
        # Rotation from dir_b to -dir_a
        target_dir = -dir_a
        
        # Calculate rotation axis and angle
        dot = Gf.Dot(dir_b, target_dir)
        
        if dot > 0.9999:
            # Already aligned, no rotation needed
            rotation_to_apply = Gf.Rotation()
            print("[Mate] Already aligned, no rotation needed")
        elif dot < -0.9999:
            # Opposite directions, rotate 180 around Z
            rotation_to_apply = Gf.Rotation(Gf.Vec3d(0, 0, 1), 180)
            print("[Mate] Opposite, rotating 180 around Z")
        else:
            # General case: rotate around the cross product
            axis = Gf.Cross(dir_b, target_dir).GetNormalized()
            angle = math.degrees(math.acos(max(-1.0, min(1.0, dot))))  # Clamp for numerical stability
            rotation_to_apply = Gf.Rotation(axis, angle)
            print(f"[Mate] Rotating {angle:.1f} deg around {axis}")
        
        # 4. Apply rotation to duct B
        # Get current rotation of duct B
        current_rot = mat_duct_b.ExtractRotation()
        new_rot = rotation_to_apply * current_rot
        
        # Convert to Euler angles (XYZ)
        new_euler = new_rot.Decompose(Gf.Vec3d.XAxis(), Gf.Vec3d.YAxis(), Gf.Vec3d.ZAxis())
        print(f"[Mate] New rotation (Euler XYZ): {new_euler}")
        
        xform_api = UsdGeom.XformCommonAPI(prim_b)
        xform_api.SetRotate(new_euler)
        
        # 5. NOW recalculate positions (after rotation)
        # Re-fetch the world transform of anchor_b after rotation
        # Actually we need to predict where it will be after rotation
        
        # The anchor offset from duct origin (in local space)
        local_anchor_offset = pos_anchor_b - pos_duct_b
        
        # Apply rotation to the offset
        rot_mat = Gf.Matrix4d().SetRotate(rotation_to_apply)
        rotated_offset = rot_mat.TransformDir(local_anchor_offset)
        
        # New duct position so rotated anchor is at target
        new_pos = pos_anchor_a - rotated_offset
        print(f"[Mate] Rotated anchor offset: {rotated_offset}")
        print(f"[Mate] New duct B pos: {new_pos}")
        
        xform_api.SetTranslate(new_pos)
        
        self._status_label.text = f"Mated {prim_b.GetName()} to {prim_a.GetName()}"
        print(f"[Mate] Success: Mated {prim_b.GetName()} to {prim_a.GetName()}")
