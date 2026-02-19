import omni.ui as ui
import omni.usd

from company.twin.solvers.frame_solver import FrameSolver
from ..utils import usd_utils
import json
import os
from pxr import Usd, UsdGeom, Gf, Sdf

DATA_PATH = "c:/Programming/buildteamai/data/aisc_wide_flanges.json"
HSS_DATA_PATH = "c:/Programming/buildteamai/data/aisc_hss.json"

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

class FrameWindow(ui.Window):
    def __init__(self, title="Create Structural Frame", **kwargs):
        super().__init__(title, width=450, height=500, **kwargs)

        # Load AISC data
        self._aisc_sections = self._load_aisc_data()
        
        # Defaults
        self._width_model = ui.SimpleFloatModel(144.0)  # 12 ft
        self._height_model = ui.SimpleFloatModel(120.0) # 10 ft
        self._col_section = None
        self._header_section = None
        
        # New: Multi-Frame / Bay Defaults
        self._num_frames_model = ui.SimpleIntModel(1)
        self._frame_spacing_model = ui.SimpleFloatModel(144.0) # 12 ft default
        self._conn_beam_section = None
        self._conn_beam_list_model = None
        
        # Drive State
        # Drive State
        self._is_driven = False
        self._driver_prim = None
        self._is_extension = False # New: Extension Mode
        self._extension_parent = None
        self._status_text = "Mode: Manual"
        
        # Extension Models
        self._ext_direction_model = ui.SimpleStringModel("Linear (Continue)")
        self._ext_direction_items = ["Linear (Continue)", "Turn Left (90°)", "Turn Right (90°)"]
        self._ext_direction_list_model = ListItemModel(self._ext_direction_items)
        
        # Subscribe to Selection
        self._stage_event_sub = omni.usd.get_context().get_stage_event_stream().create_subscription_to_pop(
            self._on_stage_event, name="FrameWindowStageEvent"
        )
        
        # Verify initial selection
        self._on_selection_changed()

        # Base Plate defaults
        self._bp_len_model = ui.SimpleFloatModel(14.0)
        self._bp_wid_model = ui.SimpleFloatModel(14.0)
        self._bp_thk_model = ui.SimpleFloatModel(0.75)
        self._rotate_cols_model = ui.SimpleBoolModel(False)
        
        # Engineering Models
        self._point_load_model = ui.SimpleFloatModel(1000.0)
        self._validation_text = "Engineering Status: N/A"
        self._validation_color = 0xFFAAAAAA

        # Build dropdown models
        if self._aisc_sections:
            self._section_names = [s["designation"] for s in self._aisc_sections]
            self._col_model = ListItemModel(self._section_names)
            self._header_model = ListItemModel(self._section_names)
            
            # Re-use section names for Connecting Beam
            self._conn_beam_list_model = ListItemModel(self._section_names)
            
            # Set initials
            self._col_model.get_item_value_model(None, 0).set_value(0)
            self._header_model.get_item_value_model(None, 0).set_value(0)
            
            self._col_section = self._aisc_sections[0]
            self._header_section = self._aisc_sections[0]
            self._conn_beam_section = self._aisc_sections[0]
            self._conn_beam_list_model.get_item_value_model(None, 0).set_value(0)
            
            
            # Lambdas for updates
            self._col_model.get_item_value_model(None, 0).add_value_changed_fn(
                lambda m: self._on_col_changed(m.as_int)
            )
            self._header_model.get_item_value_model(None, 0).add_value_changed_fn(
                lambda m: self._on_header_changed(m.as_int)
            )
            self._conn_beam_list_model.get_item_value_model(None, 0).add_value_changed_fn(
                lambda m: self._on_conn_beam_changed(m.as_int)
            )
        else:
            self._col_model = None
            self._header_model = None

        self._build_ui()
        
    def on_shutdown(self):
        self._stage_event_sub = None

    def _on_stage_event(self, event):
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            self._on_selection_changed()

    def _on_selection_changed(self):
        ctx = omni.usd.get_context()
        selection = ctx.get_selection().get_selected_prim_paths()
        stage = ctx.get_stage()
        
        if not stage or not selection:
            self._set_manual_mode()
            return
            
        prim_path = selection[0]
        prim = stage.GetPrimAtPath(prim_path)
        
        # Helper to find frame root
        def find_frame_root(p):
            # Check self
            if p and p.GetCustomDataByKey("generatorType") == "structural_frame":
                return p
            # Check parent (1 level up)
            if p and p.GetParent() and p.GetParent().GetCustomDataByKey("generatorType") == "structural_frame":
                return p.GetParent()
            return None

        # Check for Cube Driver
        if prim and prim.GetCustomDataByKey("generatorType") == "construction_cube":
            self._set_driven_mode(prim)
            return

        # Check for Structural Frame (or child)
        frame_root = find_frame_root(prim)
        if frame_root:
             self._set_extension_mode(frame_root)
        else:
            self._set_manual_mode()

    def _set_extension_mode(self, prim):
        self._is_driven = False
        self._driver_prim = None
        self._is_extension = True
        self._extension_parent = prim
        
        if hasattr(self, '_status_label') and self._status_label:
            self._status_label.text = f"Mode: EXTENSION (Parent: {prim.GetName()})"
            
        # Pre-fill dimensions from parent to match
        # Try to read engineering data or attributes if available, 
        # otherwise we assume user wants to match roughly or we just use current defaults?
        # Ideally we read the "length" of columns/headers from the first child found?
        # Or we act as if we are creating a NEW frame but attached.
        
        # Let's try to infer Width/Height from CustomData if we stored it?
        # We didn't store "width/height" on the root prim explicitly in previous steps, 
        # only on BOM items.
        # But we did store "driver_path".
        # Let's check if we can get it from the header length + cols?
        # It's safer to let user define dimensions, but maybe auto-match Header Profile?
        pass

    def _set_driven_mode(self, prim):
        self._is_extension = False
        self._extension_parent = None
        self._is_driven = True
        self._driver_prim = prim
        if hasattr(self, '_status_label') and self._status_label:
            self._status_label.text = "Mode: DRIVEN (Construction Cube)"
        
        # Read Data
        w = prim.GetCustomDataByKey("width")
        h = prim.GetCustomDataByKey("height")
        # Depth implies frame width? Or Frame creates on a face?
        # For "Simple Frame", we usually assume "Width" = span, "Height" = column height.
        # If Cube is selected, let's assume "Width" = Cube Width, "Height" = Cube Height.
        # Cube Depth is ignored for a single 2D frame unless we add "Length" parameter to frame?
        # Let's start with Width/Height match.
        
        if w: self._width_model.as_float = float(w)
        if h: self._height_model.as_float = float(h)
        
        # Force redraw or update sensitive widgets if needed
        # (FloatDrag handles disabled state via style but native doesn't support 'enabled' easily without refactor)
        # We will visually indicate via label and maybe ignoring input in _on_create.

    def _set_manual_mode(self):
        self._is_driven = False
        self._driver_prim = None
        self._is_extension = False
        self._extension_parent = None
        if hasattr(self, '_status_label') and self._status_label:
            self._status_label.text = "Mode: Manual"

    def _load_aisc_data(self):
        data = []
        # Load Wide Flanges
        if os.path.exists(DATA_PATH):
            try:
                with open(DATA_PATH, "r") as f:
                    data.extend(json.load(f))
            except Exception as e:
                print(f"Error loading AISC Wide Flange data: {e}")
        
        # Load HSS
        if os.path.exists(HSS_DATA_PATH):
            try:
                with open(HSS_DATA_PATH, "r") as f:
                    data.extend(json.load(f))
            except Exception as e:
                print(f"Error loading AISC HSS data: {e}")
                
        return data

    def _on_col_changed(self, index):
        if 0 <= index < len(self._aisc_sections):
            self._col_section = self._aisc_sections[index]

    def _on_header_changed(self, index):
        if 0 <= index < len(self._aisc_sections):
            self._header_section = self._aisc_sections[index]

    def _on_conn_beam_changed(self, index):
        if 0 <= index < len(self._aisc_sections):
            self._conn_beam_section = self._aisc_sections[index]

    def _build_ui(self):
        with self.frame:
            with ui.VStack(height=0, spacing=10, padding=15):
                ui.Label("Structural Frame Generator", style={"highlight_color": 0xFFFF6600, "font_size": 18})
                
                # Status Label
                # Status Label
                self._status_label = ui.Label(self._status_text, style={"color": 0xFF88AA00, "font_size": 14})
                
                # Extension UI (Visible only if in Extension Mode, or always visible but disabled? Dictionary-based visibility is hard in immediate mode without redraw)
                # We'll just show it always but label it "Extension Settings"
                
                with ui.CollapsableFrame("Extension Settings", collapsed=False):
                    with ui.VStack(height=0, spacing=5, padding=5):
                        with ui.HStack(height=20):
                            ui.Label("Direction:", width=120)
                            ui.ComboBox(self._ext_direction_list_model)
                
                ui.Separator(height=5)
                
                # Dimensions
                ui.Label("Dimensions", style={"font_size": 14, "color": 0xFFAAAAAA})
                with ui.HStack(height=20):
                    ui.Label("Width (C-C):", width=120)
                    ui.FloatDrag(model=self._width_model, min=24.0, max=1200.0)
                with ui.HStack(height=20):
                    ui.Label("Height:", width=120)
                    ui.FloatDrag(model=self._height_model, min=24.0, max=600.0)
                    
                ui.Spacer(height=5)
                
                # Sections
                ui.Label("Members", style={"font_size": 14, "color": 0xFFAAAAAA})
                
                if self._col_model:
                    with ui.HStack(height=20):
                        ui.Label("Columns:", width=120)
                        ui.ComboBox(self._col_model)
                
                if self._header_model:
                    with ui.HStack(height=20):
                        ui.Label("Header:", width=120)
                        ui.ComboBox(self._header_model)
                        
                ui.Spacer(height=5)
                
                # Multi-Bay / Array
                ui.Label("Multi-Frame Array", style={"font_size": 14, "color": 0xFFAAAAAA})
                with ui.HStack(height=20):
                    ui.Label("Num Frames:", width=120)
                    ui.IntDrag(model=self._num_frames_model, min=1, max=50)
                with ui.HStack(height=20):
                    ui.Label("Spacing (Depth):", width=120)
                    ui.FloatDrag(model=self._frame_spacing_model, min=24.0, max=1200.0)
                
                if self._conn_beam_list_model:
                    with ui.HStack(height=20):
                        ui.Label("Conn. Beam:", width=120)
                        ui.ComboBox(self._conn_beam_list_model)
                
                ui.Spacer(height=5)
                
                # Base Plate
                ui.Label("Base Plates", style={"font_size": 14, "color": 0xFFAAAAAA})
                with ui.HStack(height=20):
                    ui.Label("Size (LxW):", width=120)
                    ui.FloatDrag(model=self._bp_len_model, min=4.0, max=48.0)
                    ui.Label("x", width=20, alignment=ui.Alignment.CENTER)
                    ui.FloatDrag(model=self._bp_wid_model, min=4.0, max=48.0)
                with ui.HStack(height=20):
                    ui.Label("Thickness:", width=120)
                    ui.FloatDrag(model=self._bp_thk_model, min=0.125, max=4.0)

                ui.Spacer(height=5)
                ui.Label("Options", style={"font_size": 14, "color": 0xFFAAAAAA})
                with ui.HStack(height=20):
                    ui.Label("Rotate Columns 90°:", width=120)
                    ui.CheckBox(model=self._rotate_cols_model)

                ui.Spacer(height=5)
                ui.Label("Engineering", style={"font_size": 14, "color": 0xFFAAAAAA})
                with ui.HStack(height=20):
                    ui.Label("Center Load (lbs):", width=120)
                    ui.FloatDrag(model=self._point_load_model, min=100.0, max=50000.0)
                
                ui.Spacer(height=5)
                self._validation_label = ui.Label(self._validation_text, style={"color": self._validation_color, "font_size": 12})

                ui.Spacer(height=15)
                ui.Separator(height=5)
                
                # Create Button
                self._create_btn = ui.Button("Create Frame", clicked_fn=self._on_create, height=40)

    def _find_linked_frame(self, stage, driver_path):
        """Find an existing StructuralFrame linked to the given driver cube path."""
        for prim in stage.Traverse():
            if prim.GetCustomDataByKey("generatorType") == "structural_frame":
                if prim.GetCustomDataByKey("driver_path") == driver_path:
                    return prim.GetPath().pathString
        return None

    def _on_create(self):
        if not self._col_section or not self._header_section:
            print("Error: Missing section data")
            return

        # If driven, re-read latest dimensions from the cube
        if self._is_driven and self._driver_prim:
            w = self._driver_prim.GetCustomDataByKey("width")
            h = self._driver_prim.GetCustomDataByKey("height")
            if w: self._width_model.as_float = float(w)
            if h: self._height_model.as_float = float(h)

        width = self._width_model.as_float
        height = self._height_model.as_float
        bp_size = (self._bp_len_model.as_float, self._bp_wid_model.as_float, self._bp_thk_model.as_float)
        
        print(f"Creating Frame: {width}x{height}, Cols={self._col_section['designation']}, Header={self._header_section['designation']}")

        try:
            # Generate Frame Data
            col_orientation = 90.0 if self._rotate_cols_model.as_bool else 0.0
            
            solver_inputs = {
                'width': width,
                'height': height,
                'col_profile': self._col_section,
                'header_profile': self._header_section,
                'col_orientation': col_orientation,
                'gap': 0.5,
                'bp_size': bp_size,
                'point_load_lbs': self._point_load_model.as_float,
                'num_frames': self._num_frames_model.as_int,
                'frame_spacing': self._frame_spacing_model.as_float,
                'num_frames': self._num_frames_model.as_int,
                'frame_spacing': self._frame_spacing_model.as_float,
                'conn_beam_profile': self._conn_beam_section,
                # Extension Flags (Will be set below if extension)
                'skip_start_col_left': False,
                'skip_start_col_right': False
            }
            
            # EXTENSION LOGIC: Transform Calculation
            ext_transform = Gf.Matrix4d().SetIdentity()
            parent_transform = Gf.Matrix4d().SetIdentity()
            
            if self._is_extension and self._extension_parent:
                # Get Parent Transform
                parent_transform = usd_utils.get_world_transform_matrix(self._extension_parent)
                
                # Determine "End" of parent frame
                # Note: We didn't store "Total Depth" on parent. We have to guess or calculate from its children?
                # Or assume user "Spacing" input matches the parent?
                # Let's assume the parent has "num_frames" and "spacing" ... which we stored in metadata?
                # We didn't store num_frames/spacing in CustomData on root. 
                # Let's fetch it from `engineering_data` or just assume we extend from the *Origin* of the parent + some offset?
                
                # Actually, checking `task.md`, we generated `connector_beam` length in metadata.
                # Let's assume standard spacing from the UI (User must match spacing manually for now?)
                # OR we calculate based on the current ui setting for spacing.
                
                direction_idx = self._ext_direction_list_model.get_item_value_model(None, 0).as_int
                direction_str = self._ext_direction_items[direction_idx]
                
                # Offset Magnitude = Num_Frames_Parent * Spacing_Parent?
                # We don't know Parent's dimensions reliably without stored data.
                # HACK: For now, we extend from the *Local Origin* of the parent, user must use the Gizmo to adjust? 
                # No, that defeats the purpose.
                # Let's try to read `length` from a beam in the parent to guess spacing?
                # Or just use the Current UI Spacing (assuming user sets it to match).
                
                # But wait, if we extend "Linearly", we want to start where the last frame ended.
                # If Parent had 1 frame, we start at Spacing distance?
                # If Parent had 3 frames (0, 1, 2), they are at Z=0, -S, -2S.
                # The "End" is at -2S ? Or -3S?
                # Usually we attach to the last columns.
                # Last columns are at Z = -(N-1)*S.
                
                # We need to know N of parent. 
                # We can count children named `column_left_*`.
                parent_children = self._extension_parent.GetChildren()
                col_indices = [int(c.GetName().split('_')[-1]) for c in parent_children if "column_left_" in c.GetName() and c.GetName().split('_')[-1].isdigit()]
                n_parent = max(col_indices) + 1 if col_indices else 1
                
                # We also need Spacing of parent. 
                # If N > 1, we can measure distance between column_left_0 and column_left_1.
                parent_spacing = self._frame_spacing_model.as_float # Default to UI
                if n_parent > 1:
                     p0 = self._extension_parent.GetChild(f"column_left_0")
                     p1 = self._extension_parent.GetChild(f"column_left_1")
                     if p0 and p1:
                         # Dist
                         t0_attr = p0.GetAttribute("xformOp:translate")
                         t1_attr = p1.GetAttribute("xformOp:translate")
                         
                         t0 = t0_attr.Get() if t0_attr and t0_attr.IsValid() and t0_attr.HasValue() else Gf.Vec3d(0,0,0)
                         t1 = t1_attr.Get() if t1_attr and t1_attr.IsValid() and t1_attr.HasValue() else Gf.Vec3d(0,0,0)
                         # Z diff
                         parent_spacing = abs(t0[2] - t1[2])
                
                # Z position of last frame of parent
                z_last = -(n_parent - 1) * parent_spacing
                
                # Offset for NEW frame
                
                if "Linear" in direction_str:
                    # New frame starts at z_last - parent_spacing (i.e., next slot)
                    # AND we should SKIP start columns if we want to share the last columns of parent?
                    # Actually, if we share, we start AT z_last?
                    # If we start AT z_last, we clash.
                    # Build123d solver generates from Z=0.
                    # We want Frame 2's "Start" to be Frame 1's "End".
                    # If Frame 2 starts at Z_Last, its 0-columns overlap Frame 1's last columns.
                    # So we SKIP start columns.
                    
                    z_start = z_last
                    
                    mtx = Gf.Matrix4d().SetTranslate(Gf.Vec3d(0, 0, z_start))
                    ext_transform = mtx
                    
                    # Logic: We are attaching to the existing columns at z_last.
                    solver_inputs['skip_start_col_left'] = True
                    solver_inputs['skip_start_col_right'] = True
                    
                elif "Left" in direction_str:
                    # Turn Left (Positive X relative to current facing? No, Left is -X usually)
                    # Pivot at Left Column of Last Frame.
                    # Last Frame Left Col Pos: (-W/2, 0, z_last)
                    
                    pivot_x = -width / 2.0 # Assuming width matches? using current UI width
                    pivot_y = 0
                    pivot_z = z_last
                    
                    # New Frame Orientation: Rotated 90 deg around Y? 
                    # If moving "Left", we point along -X?
                    # Frame is generated along -Z.
                    # Rotate 90 deg -> -Z becomes -X?
                    # -90 deg -> -Z becomes X?
                    # Let's rotate -90 around Y. (Right Hand Rule: Y is up. Z->X is +90. Z-> -X is -90?)
                    # Wait, X cross Y = Z.
                    # Rotation +90 around Y (Up): Z goes to X. X goes to -Z.
                    # We want -Z (depth) to go to -X (Left).
                    # So -Z -> -X.
                    # Z -> X.
                    # This is +90 rotation.
                    
                    rot_mtx = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,1,0), 90))
                    
                    # Translate to Pivot
                    trans_mtx = Gf.Matrix4d().SetTranslate(Gf.Vec3d(pivot_x, pivot_y, pivot_z))
                    
                    # Combined: Rotate, then Translate (Local to World)
                    # But the frame is generated at Origin.
                    # We want its "Left Column" (which is at -W_new/2) to align with Pivot?
                    # OR we want its "Start Plane" to align.
                    # If we rotate 90, its width axis (X) becomes Z. Its depth axis (-Z) becomes -X.
                    # The "Left Column" of the new frame is at (-W/2, 0, 0) in local.
                    # After rotation 90: (-W/2, 0, 0) -> (0, 0, +W/2).
                    # We want this point to be at Pivot (Last Left Col).
                    # Pivot is at (-W_parent/2, 0, z_last).
                    
                    # So we need to offset the local origin so that (0,0, W/2) ends up at Pivot.
                    # Or simpler:
                    # Place Origin at Pivot.
                    # Rotate 90.
                    # Then "Left Column of New Frame" (locally -W/2) is at (0, 0, W/2) relative to Pivot.
                    # This is NOT the Pivot point. The Pivot is the shared column.
                    # We want the shared column to be the "Start Left" or "Start Right" of the new frame?
                    # "Turn Left": The corner is the Left Column of Parent (End) AND the **Left Column of New Frame (Start)**?
                    # No, if we turn Left, the New Frame travels Left. 
                    # Use your hands: Walking along -Z. Left Column is on left.
                    # Turn Left (face -X). Now "Left" is -Z direction, "Right" is +Z direction.
                    # The "Corner" was the Left Column of the old path.
                    # In the new path, this corner is on the... Left? No, Back-Left?
                    # It's the "Right" column of the new frame? No.
                    # If I turn left, the pivot is on my left.
                    # So it's the Left Column of the new frame too?
                    # Yes.
                    # So New Frame Left Column (Start) == Parent Last Left Column.
                    
                    # New Frame Left Col is at (-W/2, 0, 0).
                    # Rotated 90 (Z->X): (-W/2, 0, 0) becomes (0, 0, W/2) ??
                    # Rotation of +90 around Y:
                    # x' = z  (0->0)
                    # z' = -x (-[-W/2] = W/2)
                    # Yes.
                    
                    # So we need to translate such that this point matches Pivot.
                    # Pivot = (-W_parent/2, 0, z_last).
                    
                    # Solver Flags: Skip Start Left?
                    solver_inputs['skip_start_col_left'] = True
                    # Right column is new.
                    
                    # Matrix construction:
                    # 1. Rotate 90.
                    # 2. Translate so that (0,0,W/2) -> (0,0,0). (Offset -W/2 in Z?)
                    # 3. Translate to Pivot.
                    
                    # Let's do it by composition.
                    # T_offset = Translate(0, 0, -W_new/2)
                    # R = RotY(90)
                    # T_pos = Translate(Pivot)
                    # But is (-W/2) correct? 
                    # Let's assume Width matches for corner? If widths differ, it gets messy.
                    
                    # Simplified: Just place origin at Pivot, Rotate 90.
                    # Then Local (-W/2, 0, 0) is at (0, 0, W/2).
                    # We want it at (0,0,0) relative to pivot.
                    # So we must shift the new frame by (0, 0, -W/2) BEFORE rotation?
                    # No, Shift X by +W/2 so Left Col is at Origin.
                    # Local: (-W/2, 0, 0). Add (W/2, 0, 0) -> (0,0,0).
                    # Then Rotate. Then Translate to Pivot.
                    
                    # Shift to align Left Col to Origin:
                    shift_vec = Gf.Vec3d(width/2.0, 0, 0)
                    m_shift = Gf.Matrix4d().SetTranslate(shift_vec)
                    m_rot = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,1,0), 90))
                    m_trans = Gf.Matrix4d().SetTranslate(Gf.Vec3d(pivot_x, pivot_y, pivot_z))
                    
                    ext_transform = m_shift * m_rot * m_trans
                    
                elif "Right" in direction_str:
                    # Turn Right. Pivot is Right Col of Last Frame (Width/2, 0, z_last).
                    # New Frame Directions: -Z -> +X.
                    # Rotation -90 around Y.
                    # Shared Column is Right Col of New Frame (Start).
                    # New Frame Right Col is at (W/2, 0, 0).
                    
                    pivot_x = width / 2.0
                    pivot_y = 0
                    pivot_z = z_last
                    
                    # Align Right Col to Origin:
                    # Shift X by -W/2.
                    shift_vec = Gf.Vec3d(-width/2.0, 0, 0)
                    
                    m_shift = Gf.Matrix4d().SetTranslate(shift_vec)
                    m_rot = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,1,0), -90))
                    m_trans = Gf.Matrix4d().SetTranslate(Gf.Vec3d(pivot_x, pivot_y, pivot_z))
                    
                    ext_transform = m_shift * m_rot * m_trans
                    
                    solver_inputs['skip_start_col_right'] = True

            # CALL SOLVER
            solver = FrameSolver()
            frame_data = solver.solve(solver_inputs)
            
            # Update Validation UI
            val = frame_data['metadata'].get('validation', {})
            status = val.get('status', 'UNKNOWN')
            defl = val.get('deflection', 0.0)
            lim = val.get('limit_deflection', 0.0)
            
            if status == "FAIL":
                self._validation_label.text = f"FAIL: Deflection {defl:.3f} > {lim:.3f}"
                self._validation_label.style = {"color": 0xFF0000FF} # Red
            else:
                self._validation_label.text = f"PASS: Deflection {defl:.3f} < {lim:.3f}"
                self._validation_label.style = {"color": 0xFF00FF00} # Green
            
            parts = frame_data['parts']
            transforms = frame_data['transforms']
            anchors = frame_data.get('anchors', {})
            
            # USD Setup
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            if not stage:
                return

            usd_utils.setup_stage_units(stage)
            
            # Check for existing linked frame (update-in-place)
            is_update = False
            driver_path_str = None
            
            if self._is_driven and self._driver_prim:
                driver_path_str = self._driver_prim.GetPath().pathString
                existing_path = self._find_linked_frame(stage, driver_path_str)
                
                if existing_path:
                    # Remove old frame, reuse path
                    stage.RemovePrim(existing_path)
                    root_path = existing_path
                    is_update = True
                    print(f"[Frame] Updating existing frame at {root_path}")
                else:
                    # Create new path
                    root_path = "/World/StructuralFrame"
                    idx = 1
                    while stage.GetPrimAtPath(f"{root_path}_{idx}"):
                        idx += 1
                    root_path = f"{root_path}_{idx}"
            else:
                # Manual mode - always new
                root_path = "/World/StructuralFrame"
                idx = 1
                while stage.GetPrimAtPath(f"{root_path}_{idx}"):
                    idx += 1
                root_path = f"{root_path}_{idx}"
            
            root_xform = UsdGeom.Xform.Define(stage, root_path)
            root_prim = root_xform.GetPrim()
            
            # Store metadata
            root_prim.SetCustomDataByKey("generatorType", "structural_frame")
            if driver_path_str:
                root_prim.SetCustomDataByKey("driver_path", driver_path_str)
            
            # STORE ENGINEERING DATA
            validation_data = frame_data['metadata'].get('validation')
            if validation_data:
                root_prim.SetCustomDataByKey("engineering_data", json.dumps(validation_data))
            
            # Position Logic
            if self._is_driven and self._driver_prim:
                # Copy driver transform
                driver_tf = usd_utils.get_local_transform(self._driver_prim)
                if driver_tf:
                     usd_utils.set_local_transform(root_prim, driver_tf)
                
                # Offset frame to bottom of cube (Cube origin = center, Frame origin = bottom)
                h = self._height_model.as_float
                root_xform.AddTranslateOp(precision=UsdGeom.XformOp.PrecisionDouble).Set(Gf.Vec3d(0, -h/2, 0))
            
            elif self._is_extension and self._extension_parent:
                # Apply Calculated Extension Transform (Relative to Parent's Parent? i.e. World?)
                # get_world_transform_matrix returned World.
                # So we set World transform on new prim?
                # USD: It's better to parenting it?
                # No, we want flat hierarchy.
                # So apply (ParentWorld * ComputedRel) = NewWorld?
                # My logic above: 'ext_transform' = Computed relative to Local parent frame space (Pivot was local).
                # So we need to multiply by Parent World Transform.
                
                # Wait, z_last was calculated in PARENT LOCAL space (relative to parent origin).
                # So ext_transform is Local-to-Parent-Local.
                # We need Parent-Local-to-World.
                
                final_world = ext_transform * parent_transform
                
                # Decompose to SRT
                # But XformCommonAPI sets local.
                # If we are valid root, local == world (if parent is World).
                # Assuming /World/StructuralFrame_X.
                
                # Extract Translation, Rotate, Scale
                # Gf Matrix decomposition
                # No clean Gf API for decomposition in Python usually?
                # Use usd_utils or set via MatrixOp?
                
                # Let's try to set Matrix op directly or decompose manually.
                # MatrixOp is robust.
                root_xform.AddTransformOp().Set(final_world)

            # ---------------------------------------------------------
            
            # Create sub-prims
            for name, solid in parts.items():
                part_path = f"{root_path}/{name}"
                mesh_prim = usd_utils.create_mesh_from_shape(stage, part_path, solid)
                
                if name in transforms:
                    loc = transforms[name]
                    pos = loc.position
                    
                    xform_api = UsdGeom.XformCommonAPI(mesh_prim)
                    xform_api.SetTranslate((pos.X, pos.Y, pos.Z))
                    
                    rot = loc.to_tuple()[1]
                    xform_api.SetRotate(rot)
                    xform_api.SetScale((1, 1, 1))
                
                
                        
                # ---------------------------------------------------------
                # BOM METADATA
                # ---------------------------------------------------------
                prim = mesh_prim.GetPrim() if hasattr(mesh_prim, 'GetPrim') else mesh_prim
                
                # Default material
                prim.SetCustomDataByKey("material", "ASTM A992")
                
                if "column" in name:
                    profile = self._col_section
                    designation = profile['designation']
                    gen_type = 'hss_tube' if 'HSS' in designation else 'wide_flange'
                    length = frame_data['metadata']['col_length']
                    
                    prim.SetCustomDataByKey("generatorType", gen_type)
                    prim.SetCustomDataByKey("designation", designation)
                    prim.SetCustomDataByKey("length", length)
                    prim.SetCustomDataByKey("aisc_data", json.dumps(profile))
                    
                elif "header" in name:
                    profile = self._header_section
                    designation = profile['designation']
                    gen_type = 'hss_tube' if 'HSS' in designation else 'wide_flange'
                    length = frame_data['metadata']['header_length']
                    
                    prim.SetCustomDataByKey("generatorType", gen_type)
                    prim.SetCustomDataByKey("designation", designation)
                    prim.SetCustomDataByKey("length", length)
                    prim.SetCustomDataByKey("aisc_data", json.dumps(profile))
                    
                elif "conn_beam" in name:
                    profile = self._conn_beam_section
                    designation = profile['designation']
                    gen_type = 'hss_tube' if 'HSS' in designation else 'wide_flange'
                    # Retrieve calculated length from metadata or calculate?
                    # Better to store in metadata from solver per beam, or common length
                    length = frame_data['metadata'].get('conn_beam_length', 0.0)
                    
                    prim.SetCustomDataByKey("generatorType", gen_type)
                    prim.SetCustomDataByKey("designation", designation)
                    prim.SetCustomDataByKey("length", length)
                    prim.SetCustomDataByKey("aisc_data", json.dumps(profile))
                    
                elif "base_plate" in name:
                    # Treat as Gusset Plate for BOM classification
                    prim.SetCustomDataByKey("generatorType", "gusset_plate")
                    prim.SetCustomDataByKey("designation", f"PL {bp_size[0]}x{bp_size[1]}x{bp_size[2]}")
                    prim.SetCustomDataByKey("width", bp_size[1])  # W
                    prim.SetCustomDataByKey("height", bp_size[0]) # L (Height in local Y for plates often implies length)
                    prim.SetCustomDataByKey("thickness", bp_size[2])
                    prim.SetCustomDataByKey("material", "ASTM A36")
            
            action = "Updated" if is_update else "Created"
            print(f"[Frame] {action} at {root_path}")

        except Exception as e:
            print(f"Error creating frame: {e}")
            import traceback
            traceback.print_exc()
