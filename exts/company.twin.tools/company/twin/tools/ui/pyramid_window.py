import omni.ui as ui
import omni.usd
from ..objects.pyramid import PyramidGenerator
from ..utils import usd_utils
import json
import os
from pxr import Usd

DATA_PATH = "c:/Programming/buildteamai/data/pyramids.json"

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

class PyramidWindow(ui.Window):
    def __init__(self, title="Create Pyramid", **kwargs):
        super().__init__(title, width=400, height=550, **kwargs)

        self._base_model = ui.SimpleFloatModel(100.0)
        self._height_model = ui.SimpleFloatModel(100.0)
        self._angle_model = ui.SimpleFloatModel(-15.0) # Default taper

        # Features list: [{'type': 'fillet', 'edges': 'vertical', 'radius': 5.0, 'enabled': True}]
        self._features = []
        self._features_container = None

        # Edit mode tracking
        self._editing_prim_path = None
        self._create_button = None

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
                print(f"Error loading variants: {e}")
        return []

    def _build_ui(self):
        with self.frame:
            with ui.VStack(height=0, spacing=10, padding=15):
                ui.Label("Pyramid Parameters", style={"highlight_color": 0xFF00FF00, "font_size": 18})

                # Variants Dropdown
                if self._variant_model:
                    with ui.HStack(height=20):
                        ui.Label("Variant:", width=100)
                        ui.ComboBox(self._variant_model)

                ui.Spacer(height=5)
                ui.Separator(height=5)
                ui.Spacer(height=5)

                with ui.HStack(height=20):
                    ui.Label("Base Length:", width=100)
                    ui.FloatDrag(model=self._base_model, min=0.1, max=1000.0)

                with ui.HStack(height=20):
                    ui.Label("Height:", width=100)
                    ui.FloatDrag(model=self._height_model, min=0.1, max=1000.0)

                with ui.HStack(height=20):
                    ui.Label("Taper Angle:", width=100)
                    ui.FloatDrag(model=self._angle_model, min=-89.0, max=89.0)

                ui.Spacer(height=10)
                ui.Separator(height=5)
                ui.Spacer(height=10)

                # Features Section
                ui.Label("Features", style={"highlight_color": 0xFF00AAFF, "font_size": 16})

                # Features List Container
                with ui.ScrollingFrame(height=120, horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF):
                    self._features_container = ui.VStack(spacing=5)
                    self._rebuild_features_list()

                # Add Feature Buttons
                with ui.HStack(height=30, spacing=5):
                    ui.Button("Add Fillet", clicked_fn=self._on_add_fillet)
                    ui.Button("Add Sketch", clicked_fn=self._on_add_sketch)

                ui.Spacer(height=10)

                # Edit mode controls
                with ui.HStack(height=35, spacing=5):
                    ui.Button("Load Selected", clicked_fn=self._on_load_selected, height=35)
                    ui.Button("Clear", clicked_fn=self._on_clear, height=35)

                ui.Spacer(height=5)

                # Create/Update button (changes based on edit mode)
                self._create_button = ui.Button("Create Pyramid", clicked_fn=self._on_create, height=40)

    def _rebuild_features_list(self):
        """Rebuilds the features list UI"""
        if self._features_container:
            self._features_container.clear()
            with self._features_container:
                if not self._features:
                    ui.Label("No features added", style={"color": 0xFF888888})
                else:
                    for i, feature in enumerate(self._features):
                        self._build_feature_row(i, feature)

    def _build_feature_row(self, index: int, feature: dict):
        """Builds a single feature row in the UI"""
        with ui.HStack(height=25, spacing=5):
            # Checkbox for enable/disable
            enabled_model = ui.SimpleBoolModel(feature.get('enabled', True))
            enabled_model.add_value_changed_fn(lambda m, idx=index: self._on_feature_toggled(idx, m.as_bool))
            ui.CheckBox(enabled_model, width=20)

            # Feature description
            feature_type = feature.get('type')
            if feature_type == 'sketch':
                face = feature.get('face', 'front')
                op = feature.get('operation', 'cut')
                label_text = f"Sketch - {op.title()} on {face.title()}"
            else:
                edge_group = feature.get('edges', 'unknown')
                radius = feature.get('radius', 0.0)
                label_text = f"Fillet - {edge_group.title()} Edges (r={radius:.1f})"
                
            ui.Label(label_text, width=0)  # width=0 means it takes remaining space

            # Edit button
            ui.Button("Edit", width=50, clicked_fn=lambda idx=index: self._on_edit_feature(idx))

            # Delete button
            ui.Button("X", width=30, clicked_fn=lambda idx=index: self._on_delete_feature(idx))

    def _on_feature_toggled(self, index: int, enabled: bool):
        """Toggles a feature on/off"""
        if 0 <= index < len(self._features):
            self._features[index]['enabled'] = enabled

    def _on_add_fillet(self):
        """Opens dialog to add a new fillet feature"""
        self._open_fillet_dialog()

    def _on_add_sketch(self):
         """Opens dialog to add a new sketch feature"""
         self._open_sketch_dialog()

    def _on_edit_feature(self, index: int):
        """Opens dialog to edit an existing feature"""
        if 0 <= index < len(self._features):
            feature = self._features[index]
            if feature.get('type') == 'sketch':
                self._open_sketch_dialog(edit_index=index, existing_feature=feature)
            else:
                self._open_fillet_dialog(edit_index=index, existing_feature=feature)

    def _on_delete_feature(self, index: int):
        """Deletes a feature from the list"""
        if 0 <= index < len(self._features):
            self._features.pop(index)
            self._rebuild_features_list()

    def _open_fillet_dialog(self, edit_index: int = None, existing_feature: dict = None):
        """Opens a dialog to add or edit a fillet feature"""
        dialog_title = "Edit Fillet" if edit_index is not None else "Add Fillet"
        dialog = ui.Window(dialog_title, width=300, height=200)

        # Models for dialog inputs
        edge_options = ["vertical", "base", "top", "all"]
        current_edges = existing_feature.get('edges', 'vertical') if existing_feature else 'vertical'
        current_radius = existing_feature.get('radius', 5.0) if existing_feature else 5.0

        edge_index = edge_options.index(current_edges) if current_edges in edge_options else 0
        edge_model = ui.SimpleIntModel(edge_index)
        radius_model = ui.SimpleFloatModel(current_radius)

        with dialog.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Fillet Parameters", style={"font_size": 16})

                with ui.HStack(height=20):
                    ui.Label("Edge Group:", width=100)
                    edge_combo_items = [ListItem(opt.title()) for opt in edge_options]
                    edge_list_model = ListItemModel([opt.title() for opt in edge_options])
                    edge_list_model.get_item_value_model(None, 0).set_value(edge_index)
                    ui.ComboBox(edge_list_model)

                with ui.HStack(height=20):
                    ui.Label("Radius:", width=100)
                    ui.FloatDrag(model=radius_model, min=0.1, max=50.0)

                ui.Spacer(height=10)

                with ui.HStack(height=30, spacing=10):
                    ui.Button("OK", clicked_fn=lambda: self._on_fillet_dialog_ok(
                        dialog, edit_index, edge_options, edge_list_model, radius_model))
                    ui.Button("Cancel", clicked_fn=lambda: setattr(dialog, 'visible', False))

    def _on_fillet_dialog_ok(self, dialog, edit_index, edge_options, edge_model, radius_model):
        """Handles OK button in fillet dialog"""
        edge_index = edge_model.get_item_value_model(None, 0).as_int
        edge_group = edge_options[edge_index]
        radius = radius_model.as_float

        feature = {
            'type': 'fillet',
            'edges': edge_group,
            'radius': radius,
            'enabled': True
        }

        if edit_index is not None:
            # Edit existing feature
            self._features[edit_index] = feature
        else:
            # Add new feature
            self._features.append(feature)

        self._rebuild_features_list()
        dialog.visible = False

    def _open_sketch_dialog(self, edit_index: int = None, existing_feature: dict = None):
        """Opens a dialog to add or edit a sketch feature"""
        dialog_title = "Edit Sketch" if edit_index is not None else "Add Sketch"
        dialog = ui.Window(dialog_title, width=350, height=450)
        
        # Default values
        face_opts = ["front", "back", "left", "right", "top", "base"]
        profile_opts = ["circle", "rectangle"]
        op_opts = ["cut", "extrude"]
        
        cur_face = existing_feature.get('face', 'front') if existing_feature else 'front'
        cur_profile = existing_feature.get('profile', 'circle') if existing_feature else 'circle'
        cur_op = existing_feature.get('operation', 'cut') if existing_feature else 'cut'
        cur_amt = existing_feature.get('amount', 10.0) if existing_feature else 10.0
        
        center = existing_feature.get('center', [0, 0]) if existing_feature else [0, 0]
        cur_u = center[0]
        cur_v = center[1]
        
        dims = existing_feature.get('dimensions', {}) if existing_feature else {}
        if isinstance(dims, (int, float)): dims = {'radius': dims}
        cur_rad = dims.get('radius', 10.0)
        cur_w = dims.get('width', 20.0)
        cur_h = dims.get('height', 20.0)

        # Models
        face_model = ListItemModel([f.title() for f in face_opts])
        face_model.get_item_value_model(None, 0).set_value(face_opts.index(cur_face))
        
        profile_model = ListItemModel([p.title() for p in profile_opts])
        profile_model.get_item_value_model(None, 0).set_value(profile_opts.index(cur_profile))
        
        op_model = ListItemModel([o.title() for o in op_opts])
        op_model.get_item_value_model(None, 0).set_value(op_opts.index(cur_op))
        
        amt_model = ui.SimpleFloatModel(cur_amt)
        u_model = ui.SimpleFloatModel(cur_u)
        v_model = ui.SimpleFloatModel(cur_v)
        rad_model = ui.SimpleFloatModel(cur_rad)
        w_model = ui.SimpleFloatModel(cur_w)
        h_model = ui.SimpleFloatModel(cur_h)

        with dialog.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Sketch Parameters", style={"highlight_color": 0xFF00AAFF, "font_size": 16})
                
                # Face
                with ui.HStack(height=20):
                    ui.Label("Face:", width=80)
                    ui.ComboBox(face_model)
                
                # Profile
                with ui.HStack(height=20):
                    ui.Label("Profile:", width=80)
                    ui.ComboBox(profile_model)
                    
                # Operation
                with ui.HStack(height=20):
                    ui.Label("Operation:", width=80)
                    ui.ComboBox(op_model)
                    
                # Amount
                with ui.HStack(height=20):
                    ui.Label("Amount:", width=80)
                    ui.FloatDrag(model=amt_model, min=0.0)

                ui.Separator(height=10)
                ui.Label("Position (Face Center Relative)", style={"color": 0xFFAAAAAA})
                with ui.HStack(height=20):
                    ui.Label("Center U:", width=80)
                    ui.FloatDrag(model=u_model)
                with ui.HStack(height=20):
                    ui.Label("Center V:", width=80)
                    ui.FloatDrag(model=v_model)

                ui.Separator(height=10)
                ui.Label("Dimensions", style={"color": 0xFFAAAAAA})
                with ui.HStack(height=20):
                    ui.Label("Radius/W:", width=80)
                    ui.FloatDrag(model=rad_model, min=0.1) # Reused for Width if rect
                with ui.HStack(height=20):
                    ui.Label("Height:", width=80)
                    ui.FloatDrag(model=h_model, min=0.1)
                
                ui.Spacer(height=10)
                with ui.HStack(height=30, spacing=10):
                    ui.Button("OK", clicked_fn=lambda: self._on_sketch_dialog_ok(
                        dialog, edit_index, 
                        face_opts, face_model, 
                        profile_opts, profile_model,
                        op_opts, op_model,
                        amt_model, u_model, v_model, 
                        rad_model, h_model # rad_model used for Width/Radius
                    ))
                    ui.Button("Cancel", clicked_fn=lambda: setattr(dialog, 'visible', False))

    def _on_sketch_dialog_ok(self, dialog, edit_index, 
                             face_opts, face_model, 
                             profile_opts, profile_model,
                             op_opts, op_model,
                             amt_model, u_model, v_model, 
                             rad_model, h_model):
                             
        face = face_opts[face_model.get_item_value_model(None, 0).as_int]
        profile = profile_opts[profile_model.get_item_value_model(None, 0).as_int]
        op = op_opts[op_model.get_item_value_model(None, 0).as_int]
        amount = amt_model.as_float
        center = [u_model.as_float, v_model.as_float]
        
        dims = {}
        if profile == 'circle':
            dims['radius'] = rad_model.as_float
        else:
            dims['width'] = rad_model.as_float # Reused
            dims['height'] = h_model.as_float
            
        feature = {
            'type': 'sketch',
            'face': face,
            'profile': profile,
            'operation': op,
            'amount': amount,
            'center': center,
            'dimensions': dims,
            'enabled': True
        }
        
        if edit_index is not None:
            self._features[edit_index] = feature
        else:
            self._features.append(feature)
            
        self._rebuild_features_list()
        dialog.visible = False

    def _on_load_selected(self):
        """Loads parameters from selected pyramid prim"""
        try:
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            if not stage:
                print("Error: No USD Stage open")
                return

            selection = ctx.get_selection()
            selected_paths = selection.get_selected_prim_paths()

            if not selected_paths:
                print("No prim selected. Please select a pyramid to edit.")
                return

            # Get first selected prim
            prim_path = selected_paths[0]
            prim = stage.GetPrimAtPath(prim_path)

            if not prim:
                print(f"Error: Could not get prim at {prim_path}")
                return

            # Check if it's a pyramid
            custom_data = prim.GetCustomData()
            generator_type = custom_data.get('generatorType')

            if generator_type != 'pyramid':
                print(f"Selected prim is not a pyramid (type: {generator_type})")
                return

            # Load parameters
            base = custom_data.get('base', 100.0)
            height = custom_data.get('height', 100.0)
            angle = custom_data.get('angle', -15.0)
            features_json = custom_data.get('features', '[]')

            # Deserialize features from JSON
            if isinstance(features_json, str):
                self._features = json.loads(features_json)
            else:
                self._features = []

            # Update UI models
            self._base_model.as_float = float(base)
            self._height_model.as_float = float(height)
            self._angle_model.as_float = float(angle)
            self._rebuild_features_list()

            # Set edit mode
            self._editing_prim_path = prim_path
            if self._create_button:
                self._create_button.text = "Update Pyramid"

            print(f"Loaded pyramid from {prim_path}")
            print(f"  Base={base}, Height={height}, Angle={angle}, Features={len(self._features)}")

        except Exception as e:
            print(f"Error loading selected pyramid: {e}")
            import traceback
            traceback.print_exc()

    def _on_clear(self):
        """Clears edit mode and resets to create mode"""
        self._editing_prim_path = None
        if self._create_button:
            self._create_button.text = "Create Pyramid"
        print("Cleared edit mode - ready to create new pyramid")

    def _on_variant_changed(self, index):
        if 0 <= index < len(self._variants):
            data = self._variants[index]
            self._base_model.as_float = data.get("base", 100.0)
            self._height_model.as_float = data.get("height", 100.0)
            self._angle_model.as_float = data.get("angle", -15.0)

            # Load features from variant if present
            self._features = data.get("features", [])
            self._rebuild_features_list()

    def _on_create(self):
        base = self._base_model.as_float
        height = self._height_model.as_float
        angle = self._angle_model.as_float

        is_update = self._editing_prim_path is not None
        action = "Updating" if is_update else "Creating"

        print(f"{action} Pyramid: Base={base}, Height={height}, Angle={angle}")
        if self._features:
            print(f"  Features: {len(self._features)} feature(s)")

        try:
            # Generate Geometry with features
            solid = PyramidGenerator.create(base, height, angle, features=self._features)

            # Get Stage
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            if not stage:
                print("Error: No USD Stage open")
                return

            # Determine path
            if is_update:
                # Update existing pyramid
                path = self._editing_prim_path
                # Remove old prim
                stage.RemovePrim(path)
            else:
                # Find unique path for new pyramid
                path_root = "/World/Pyramid"
                path = path_root
                idx = 1
                while stage.GetPrimAtPath(path):
                    path = f"{path_root}_{idx}"
                    idx += 1

            # Convert to USD
            mesh_prim = usd_utils.create_mesh_from_shape(stage, path, solid)

            # Store metadata for editability
            if mesh_prim:
                prim = mesh_prim.GetPrim()
                prim.SetCustomDataByKey('generatorType', 'pyramid')
                prim.SetCustomDataByKey('base', float(base))
                prim.SetCustomDataByKey('height', float(height))
                prim.SetCustomDataByKey('angle', float(angle))
                # USD metadata doesn't support dicts/lists directly, so serialize to JSON
                prim.SetCustomDataByKey('features', json.dumps(self._features))

            action_past = "Updated" if is_update else "Created"
            print(f"{action_past} Pyramid at {path}")
            if self._features:
                enabled_count = len([f for f in self._features if f.get('enabled', True)])
                print(f"  Applied {enabled_count} enabled feature(s)")

            # If we were updating, stay in edit mode
            if is_update:
                print(f"  Still editing {path} - modify and click 'Update Pyramid' again, or 'Clear' to create new")

        except Exception as e:
            print(f"Error {action.lower()} pyramid: {e}")
            import traceback
            traceback.print_exc()
