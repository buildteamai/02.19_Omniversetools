import omni.ui as ui
import omni.usd
from pxr import Gf, UsdGeom, Usd, Tf, Sdf
import json
import os
import math
from ..objects.mep.duct_warp import DuctWarpGenerator
from ..objects.mep.trapeze import Trapeze
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
        
        # Trapeze support generation
        self._add_trapeze_model = ui.SimpleBoolModel(True)
        self._trapeze_drop_length_model = ui.SimpleFloatModel(36.0)

        # Edit mode tracking — list supports single and multi-select
        self._editing_prim_paths = []
        self._create_button = None
        self._status_label = None

        # Chain propagation — flag suppresses notice handler during code-driven writes
        self._updating = False
        self._notice_listener = None
        
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

                    with ui.HStack(height=22):
                        ui.Label("Add Trapezes:", width=100)
                        ui.CheckBox(model=self._add_trapeze_model)
                        ui.Label("(straight only)", style={"color": 0xFF888888})

                    with ui.HStack(height=22):
                        ui.Label("  Drop Length:", width=100)
                        ui.FloatDrag(model=self._trapeze_drop_length_model, min=6.0, max=120.0)
                        ui.Label("in", width=20, style={"color": 0xFF888888})

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
        """Loads parameters from all selected duct prims.

        Cross-section params (width/height/diameter) are read from the first
        valid duct and shown in the UI — these are the bulk-apply fields.
        Per-duct params (length, radius, angle, segments) are preserved from
        each duct's own metadata at update time.
        """
        try:
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            if not stage:
                self._status_label.text = "Error: No USD Stage open"
                return

            self._ensure_stage_subscription(stage)

            selected_paths = ctx.get_selection().get_selected_prim_paths()
            if not selected_paths:
                self._status_label.text = "No prim selected"
                return

            valid_types = {'duct_bent', 'duct_straight', 'duct_round_bent', 'duct_round_straight'}
            valid_paths = []
            for prim_path in selected_paths:
                prim = stage.GetPrimAtPath(prim_path)
                if prim and prim.GetCustomData().get('generatorType') in valid_types:
                    valid_paths.append(prim_path)

            if not valid_paths:
                self._status_label.text = "No duct prims in selection"
                return

            # Load cross-section UI from first valid duct
            first = stage.GetPrimAtPath(valid_paths[0])
            cd = first.GetCustomData()
            gen_type = cd.get('generatorType', 'duct_straight')
            is_straight_type = 'straight' in gen_type
            shape_str = cd.get('shape', 'rectangular')
            is_round = (shape_str == 'round') or ('round' in gen_type)

            if is_round:
                self._shape_index.as_int = 1
                self._diameter_model.as_float = float(cd.get('diameter', 12.0))
            else:
                self._shape_index.as_int = 0
                self._width_model.as_float = float(cd.get('width', 20.0))
                self._height_model.as_float = float(cd.get('height', 10.0))

            self._type_index.as_int = 0 if is_straight_type else 1
            self._on_shape_changed(self._shape_index.as_int)
            self._on_type_changed(self._type_index.as_int)

            self._radius_model.as_float = float(cd.get('radius', 30.0))
            self._angle_model.as_float = float(cd.get('angle', 90.0))
            self._segments_model.as_int = int(cd.get('segments', 20))
            self._add_flanges_model.as_bool = bool(cd.get('add_flanges', True))
            self._length_model.as_float = float(cd.get('length', 24.0))

            self._editing_prim_paths = valid_paths
            count = len(valid_paths)
            skipped = len(selected_paths) - count

            if self._create_button:
                self._create_button.text = "Update Duct" if count == 1 else f"Update Ducts ({count})"

            skip_note = f", {skipped} non-duct skipped" if skipped else ""
            self._status_label.text = f"Loaded {count} duct(s){skip_note}"
            print(f"[Duct] Loaded {count} duct(s) for bulk edit: {valid_paths}")

        except Exception as e:
            self._status_label.text = f"Error loading: {str(e)}"
            print(f"Error loading selected duct(s): {e}")
            import traceback
            traceback.print_exc()
    
    def _on_clear(self):
        """Clears edit mode and resets to create mode"""
        self._editing_prim_paths = []
        if self._create_button:
            self._create_button.text = "Generate Duct"
        self._status_label.text = "Ready to create new duct"
        print("Cleared edit mode - ready to create new duct")
                
    def _on_generate(self):
        stage = omni.usd.get_context().get_stage()
        if not stage:
            self._status_label.text = "Error: No Stage Open"
            return

        from ..utils import usd_utils

        # === CREATE NEW (no ducts loaded) ===
        if not self._editing_prim_paths:
            path_root = "/World/Duct"
            path = path_root
            idx = 1
            while stage.GetPrimAtPath(path):
                path = f"{path_root}_{idx}"
                idx += 1
            try:
                shape = "round" if self._shape_index.as_int == 1 else "rectangular"
                is_straight = (self._type_index.as_int == 0)
                angle_val = 0.0 if is_straight else self._angle_model.as_float

                DuctWarpGenerator.create(
                    stage, path,
                    width=self._width_model.as_float,
                    height=self._height_model.as_float,
                    radius=self._radius_model.as_float,
                    angle_deg=angle_val,
                    segments=self._segments_model.as_int,
                    add_flanges=self._add_flanges_model.as_bool,
                    length=self._length_model.as_float,
                    shape=shape,
                    diameter=self._diameter_model.as_float,
                )

                if self._add_trapeze_model.as_bool and is_straight:
                    self._generate_trapezes(
                        stage, path,
                        width=self._width_model.as_float,
                        height=self._height_model.as_float,
                        length=self._length_model.as_float,
                        shape=shape,
                        diameter=self._diameter_model.as_float,
                        drop_length=self._trapeze_drop_length_model.as_float,
                    )

                self._status_label.text = f"Created at {path}"
                print(f"[Duct] Created at {path}")

            except Exception as e:
                self._status_label.text = f"Error: {str(e)}"
                print(f"[Duct] {e}")
                import traceback
                traceback.print_exc()
            return

        # === UPDATE — single or bulk ===
        # Bulk params: cross-section + length applied to every duct
        # Per-duct params: radius, angle, segments, shape — read from each duct's metadata
        self._ensure_stage_subscription(stage)

        bulk_width       = self._width_model.as_float
        bulk_height      = self._height_model.as_float
        bulk_diameter    = self._diameter_model.as_float
        bulk_length      = self._length_model.as_float
        bulk_add_flanges = self._add_flanges_model.as_bool
        bulk_add_trapezes = self._add_trapeze_model.as_bool
        bulk_drop_length = self._trapeze_drop_length_model.as_float

        updated = 0
        errors  = 0

        self._updating = True
        try:
            for prim_path in self._editing_prim_paths:
                try:
                    prim = stage.GetPrimAtPath(prim_path)
                    if not prim:
                        print(f"[Duct] Prim not found: {prim_path}")
                        errors += 1
                        continue

                    # Read per-duct params and mate links from metadata before deletion
                    cd = prim.GetCustomData()
                    gen_type     = cd.get('generatorType', 'duct_straight')
                    per_length   = bulk_length
                    per_radius   = float(cd.get('radius',   self._radius_model.as_float))
                    per_angle    = float(cd.get('angle',    90.0))
                    per_segments = int(cd.get('segments',   self._segments_model.as_int))
                    per_shape_str  = cd.get('shape', 'rectangular')
                    per_is_round   = (per_shape_str == 'round') or ('round' in gen_type)
                    per_is_straight = 'straight' in gen_type
                    per_shape      = 'round' if per_is_round else 'rectangular'
                    per_angle_val  = 0.0 if per_is_straight else per_angle

                    # Save mate chain links — lost when prim is deleted
                    saved_downstream = cd.get('mate_downstream', '')
                    saved_upstream   = cd.get('mate_upstream',   '')

                    # Capture transform; children (trapezes) deleted with prim
                    current_transform = usd_utils.get_local_transform(prim)
                    stage.RemovePrim(prim_path)

                    DuctWarpGenerator.create(
                        stage, prim_path,
                        width=bulk_width,
                        height=bulk_height,
                        radius=per_radius,
                        angle_deg=per_angle_val,
                        segments=per_segments,
                        add_flanges=bulk_add_flanges,
                        length=per_length,
                        shape=per_shape,
                        diameter=bulk_diameter,
                    )

                    new_prim = stage.GetPrimAtPath(prim_path)

                    # --- 6DOF positioning ---
                    # If upstream mate exists, let _apply_mate_positions compute
                    # the transform from scratch (avoids xformOp conflicts with
                    # set_local_transform + XformCommonAPI).
                    # Otherwise fall back to the saved local transform.
                    if saved_upstream and new_prim:
                        us_prim = stage.GetPrimAtPath(saved_upstream)
                        if us_prim:
                            ok = self._apply_mate_positions(stage, us_prim, new_prim)
                            if not ok and current_transform:
                                usd_utils.set_local_transform(new_prim, current_transform)
                                print(f"[Duct] Upstream anchors missing, fell back to saved transform")
                        elif current_transform:
                            usd_utils.set_local_transform(new_prim, current_transform)
                    elif new_prim and current_transform:
                        usd_utils.set_local_transform(new_prim, current_transform)

                    # Restore mate chain links onto the new prim
                    if new_prim and (saved_downstream or saved_upstream):
                        new_cd = dict(new_prim.GetCustomData())
                        if saved_downstream:
                            new_cd['mate_downstream'] = saved_downstream
                        if saved_upstream:
                            new_cd['mate_upstream'] = saved_upstream
                        new_prim.SetCustomData(new_cd)

                    if bulk_add_trapezes and per_is_straight:
                        self._generate_trapezes(
                            stage, prim_path,
                            width=bulk_width,
                            height=bulk_height,
                            length=per_length,
                            shape=per_shape,
                            diameter=bulk_diameter,
                            drop_length=bulk_drop_length,
                        )

                    # Cascade 6DOF downstream through the chain
                    if saved_downstream:
                        self._propagate_chain(stage, prim_path)

                    updated += 1
                    print(f"[Duct] Updated {prim_path} (W={bulk_width}, H={bulk_height}, L={bulk_length})")

                except Exception as e:
                    errors += 1
                    print(f"[Duct] Error updating {prim_path}: {e}")
                    import traceback
                    traceback.print_exc()
        finally:
            self._updating = False

        noun = "duct" if updated == 1 else "ducts"
        if errors == 0:
            self._status_label.text = f"Updated {updated} {noun}"
        else:
            self._status_label.text = f"Updated {updated}/{len(self._editing_prim_paths)}, {errors} error(s)"
        print(f"[Duct] Bulk update complete: {updated} updated, {errors} errors")

    def _calculate_trapeze_positions(self, length):
        """Return X positions (inches) for trapeze placement along a straight duct.

        Rules:
          <= 72"  (6 ft) : one trapeze at mid-span
          >  72"         : third-point spacing, capped at 48" (4 ft) max interval
        """
        if length <= 72.0:
            return [length / 2.0]
        spacing = length / 3.0
        if spacing > 48.0:
            spacing = 48.0
        positions = []
        x = spacing
        while x < length - 1.0:
            positions.append(x)
            x += spacing
        return positions

    def _generate_trapezes(self, stage, duct_path, width, height, length, shape, diameter, drop_length):
        """Create trapeze child prims under the duct prim."""
        positions = self._calculate_trapeze_positions(length)
        strut_height = 1.625  # default strut channel height

        if shape == "round":
            span = diameter + 4.0
            cradle_y = -(diameter / 2.0 + strut_height)
        else:
            span = width + 4.0
            cradle_y = -(height / 2.0 + strut_height)

        for i, x_pos in enumerate(positions):
            trap_name = "Trapeze" if i == 0 else f"Trapeze_{i}"
            trap_path = f"{duct_path}/{trap_name}"

            result = Trapeze.create(
                stage, trap_path,
                span=span,
                cantilever=2.0,
                drop_length=drop_length,
                rod_diameter=0.5,
                strut_gauge="12 Ga",
                assigned_duct_path=duct_path,
            )

            if result:
                prim = stage.GetPrimAtPath(trap_path)
                if prim:
                    xform_api = UsdGeom.XformCommonAPI(prim)
                    xform_api.SetTranslate(Gf.Vec3d(x_pos, cradle_y, 0.0))
                    print(f"[Trapeze] {trap_name} at X={x_pos:.1f}\" Y={cradle_y:.1f}\" under {duct_path}")

        count = len(positions)
        print(f"[Trapeze] Generated {count} trapeze(s) for {duct_path}")

    # ── Stage subscription ────────────────────────────────────────────────────

    def _ensure_stage_subscription(self, stage):
        """Subscribe once to USD object changes for manual-move detection."""
        if self._notice_listener is not None:
            return
        self._notice_listener = Tf.Notice.Register(
            Usd.Notice.ObjectsChanged,
            self._on_objects_changed,
            stage,
        )

    def _on_objects_changed(self, notice, stage):
        """Detect user-driven xform changes on duct prims and clear mate links."""
        if self._updating:
            return

        valid_gen_types = {
            'duct_bent', 'duct_straight', 'duct_round_bent', 'duct_round_straight'
        }
        cleared = set()

        for path in notice.GetChangedInfoOnlyPaths():
            if not path.IsPropertyPath():
                continue
            if 'xformOp' not in path.name:
                continue

            prim_path = path.GetPrimPath()
            prim_path_str = str(prim_path)
            if prim_path_str in cleared:
                continue

            prim = stage.GetPrimAtPath(prim_path)
            if not prim:
                continue
            if prim.GetCustomData().get('generatorType') not in valid_gen_types:
                continue

            self._clear_mate_relationship(stage, prim_path_str)
            cleared.add(prim_path_str)

    def _clear_mate_relationship(self, stage, prim_path_str):
        """Disconnect a duct from its chain at both ends."""
        self._updating = True
        try:
            prim = stage.GetPrimAtPath(prim_path_str)
            if not prim:
                return

            cd = dict(prim.GetCustomData())
            downstream = cd.pop('mate_downstream', '')
            upstream   = cd.pop('mate_upstream',   '')
            prim.SetCustomData(cd)

            if downstream:
                ds = stage.GetPrimAtPath(downstream)
                if ds:
                    ds_cd = dict(ds.GetCustomData())
                    ds_cd.pop('mate_upstream', None)
                    ds.SetCustomData(ds_cd)

            if upstream:
                us = stage.GetPrimAtPath(upstream)
                if us:
                    us_cd = dict(us.GetCustomData())
                    us_cd.pop('mate_downstream', None)
                    us.SetCustomData(us_cd)

            if downstream or upstream:
                print(f"[Mate] Cleared relationship for {prim_path_str}")
        finally:
            self._updating = False

    # ── Core mate alignment ───────────────────────────────────────────────────

    def _apply_mate_positions(self, stage, prim_a, prim_b):
        """6DOF-align prim_b's Anchor_Start to prim_a's Anchor_End.

        Returns True on success, False if anchors are missing.
        """
        def get_anchor(prim, name):
            for child in prim.GetChildren():
                if child.GetName() == name:
                    return child
            return None

        anchor_a = get_anchor(prim_a, "Anchor_End")
        anchor_b = get_anchor(prim_b, "Anchor_Start")
        if not anchor_a or not anchor_b:
            return False

        mat_anchor_a = omni.usd.get_world_transform_matrix(anchor_a)
        mat_anchor_b = omni.usd.get_world_transform_matrix(anchor_b)
        mat_duct_b   = omni.usd.get_world_transform_matrix(prim_b)

        pos_anchor_a = mat_anchor_a.ExtractTranslation()
        pos_anchor_b = mat_anchor_b.ExtractTranslation()
        pos_duct_b   = mat_duct_b.ExtractTranslation()

        rot_a = mat_anchor_a.ExtractRotationMatrix()
        rot_b = mat_anchor_b.ExtractRotationMatrix()
        dir_a = Gf.Vec3d(rot_a.GetColumn(0))
        dir_b = Gf.Vec3d(rot_b.GetColumn(0))

        target_dir = -dir_a
        dot = Gf.Dot(dir_b, target_dir)

        if dot > 0.9999:
            rotation_to_apply = Gf.Rotation()
        elif dot < -0.9999:
            rotation_to_apply = Gf.Rotation(Gf.Vec3d(0, 0, 1), 180)
        else:
            axis  = Gf.Cross(dir_b, target_dir).GetNormalized()
            angle = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
            rotation_to_apply = Gf.Rotation(axis, angle)

        new_rot   = rotation_to_apply * mat_duct_b.ExtractRotation()
        new_euler = new_rot.Decompose(Gf.Vec3d.XAxis(), Gf.Vec3d.YAxis(), Gf.Vec3d.ZAxis())

        local_offset   = pos_anchor_b - pos_duct_b
        rot_mat        = Gf.Matrix4d().SetRotate(rotation_to_apply)
        rotated_offset = rot_mat.TransformDir(local_offset)
        new_pos        = pos_anchor_a - rotated_offset

        # Clear existing xformOps so XformCommonAPI gets a clean slate
        # (avoids conflicts with ops left by set_local_transform or prior mates)
        UsdGeom.Xformable(prim_b).ClearXformOpOrder()

        xform_api = UsdGeom.XformCommonAPI(prim_b)
        xform_api.SetTranslate(new_pos)
        xform_api.SetRotate(new_euler)
        return True

    # ── Chain propagation ─────────────────────────────────────────────────────

    def _propagate_chain(self, stage, root_prim_path):
        """Re-mate every downstream duct starting from root_prim_path."""
        visited      = set()
        current_path = root_prim_path

        while current_path and current_path not in visited:
            visited.add(current_path)
            prim = stage.GetPrimAtPath(current_path)
            if not prim:
                break

            downstream_path = prim.GetCustomData().get('mate_downstream', '')
            if not downstream_path:
                break

            ds_prim = stage.GetPrimAtPath(downstream_path)
            if not ds_prim:
                break

            ok = self._apply_mate_positions(stage, prim, ds_prim)
            if not ok:
                print(f"[Chain] Missing anchors — stopped at {downstream_path}")
                break

            print(f"[Chain] Re-mated {downstream_path} → {current_path}")
            current_path = downstream_path

    # ─────────────────────────────────────────────────────────────────────────

    def _on_mate_selected(self):
        """Mates two selected ducts and stores the relationship in USD metadata."""
        ctx   = omni.usd.get_context()
        stage = ctx.get_stage()
        self._ensure_stage_subscription(stage)
        selection = ctx.get_selection().get_selected_prim_paths()

        if len(selection) != 2:
            self._status_label.text = "Select exactly 2 ducts to mate"
            return

        prim_a = stage.GetPrimAtPath(selection[0])
        prim_b = stage.GetPrimAtPath(selection[1])
        if not prim_a or not prim_b:
            return

        # Validate anchors exist before committing to anything
        def get_anchor(prim, name):
            for child in prim.GetChildren():
                if child.GetName() == name:
                    return child
            return None

        if not get_anchor(prim_a, "Anchor_End"):
            self._status_label.text = "First duct has no Anchor_End (exit)"
            return
        if not get_anchor(prim_b, "Anchor_Start"):
            self._status_label.text = "Second duct has no Anchor_Start (entry)"
            return

        print("[Mate] === Starting 6DOF Mate ===")

        # Suppress notice handler — we are doing intentional writes
        self._updating = True
        try:
            # 6DOF alignment
            ok = self._apply_mate_positions(stage, prim_a, prim_b)
            if not ok:
                self._status_label.text = "Mate failed — missing anchors"
                return

            a_path = str(prim_a.GetPath())
            b_path = str(prim_b.GetPath())

            # Clear any stale downstream from A
            a_cd = dict(prim_a.GetCustomData())
            old_ds = a_cd.get('mate_downstream', '')
            if old_ds and old_ds != b_path:
                old_ds_prim = stage.GetPrimAtPath(old_ds)
                if old_ds_prim:
                    c = dict(old_ds_prim.GetCustomData())
                    c.pop('mate_upstream', None)
                    old_ds_prim.SetCustomData(c)

            # Clear any stale upstream from B
            b_cd = dict(prim_b.GetCustomData())
            old_us = b_cd.get('mate_upstream', '')
            if old_us and old_us != a_path:
                old_us_prim = stage.GetPrimAtPath(old_us)
                if old_us_prim:
                    c = dict(old_us_prim.GetCustomData())
                    c.pop('mate_downstream', None)
                    old_us_prim.SetCustomData(c)

            # Write new relationship
            a_cd['mate_downstream'] = b_path
            prim_a.SetCustomData(a_cd)

            b_cd['mate_upstream'] = a_path
            prim_b.SetCustomData(b_cd)

            print(f"[Mate] Stored: {a_path} → {b_path}")

        finally:
            self._updating = False

        self._status_label.text = f"Mated {prim_b.GetName()} to {prim_a.GetName()}"
        print(f"[Mate] Success: {prim_a.GetName()} → {prim_b.GetName()}")

    def destroy(self):
        """Revoke USD notice listener on window close."""
        if self._notice_listener is not None:
            self._notice_listener.Revoke()
            self._notice_listener = None
        super().destroy()
