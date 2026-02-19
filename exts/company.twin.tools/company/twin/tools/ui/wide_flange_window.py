import omni.ui as ui
import omni.usd
from ..objects.wide_flange import WideFlangeGenerator
from ..utils import usd_utils
from ..fabrication.drawings.wide_flange_drawing import WideFlangeDrawing
from ..fabrication.drawings.base_drawing import DrawingMetadata
from ..fabrication.exporters.dxf_exporter import export_to_dxf
from ..fabrication.exporters.pdf_exporter import export_to_pdf
import json
import os
from pxr import Usd

DATA_PATH = "c:/Programming/buildteamai/data/aisc_wide_flanges.json"

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

class WideFlangeWindow(ui.Window):
    def __init__(self, title="Create Wide Flange Beam", **kwargs):
        super().__init__(title, width=450, height=600, **kwargs)

        # Load AISC data
        self._aisc_sections = self._load_aisc_data()

        # Models for beam parameters
        self._length_model = ui.SimpleFloatModel(120.0)  # 10 feet default

        # Current AISC section
        self._current_section = None

        # Features list
        self._features = []
        self._features_container = None

        # Edit mode tracking
        self._editing_prim_path = None
        self._create_button = None

        # Build AISC dropdown model
        if self._aisc_sections:
            self._section_names = [s["designation"] for s in self._aisc_sections]
            self._section_model = ListItemModel(self._section_names)
            self._section_model.get_item_value_model(None, 0).add_value_changed_fn(
                lambda m: self._on_section_changed(m.as_int)
            )
            # Set default to first section
            self._current_section = self._aisc_sections[0]
        else:
            self._section_names = []
            self._section_model = None

        self._build_ui()

    def _load_aisc_data(self):
        """Load AISC wide flange data from JSON"""
        if os.path.exists(DATA_PATH):
            try:
                with open(DATA_PATH, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading AISC data: {e}")
        return []

    def _build_ui(self):
        with self.frame:
            with ui.VStack(height=0, spacing=10, padding=15):
                ui.Label("Wide Flange Beam", style={"highlight_color": 0xFFFF6600, "font_size": 18})

                # AISC Section Selection
                if self._section_model:
                    with ui.HStack(height=20):
                        ui.Label("AISC Section:", width=120)
                        ui.ComboBox(self._section_model)

                    # Display current section info
                    if self._current_section:
                        ui.Spacer(height=5)
                        with ui.VStack(spacing=3):
                            section = self._current_section
                            ui.Label(f"Depth: {section['depth_d']}\"  |  Flange: {section['flange_width_bf']}\"  |  {section['weight_lb_ft']} lb/ft",
                                   style={"color": 0xFFAAAAAA, "font_size": 12})

                ui.Spacer(height=5)
                ui.Separator(height=5)
                ui.Spacer(height=5)

                # Length parameter
                with ui.HStack(height=20):
                    ui.Label("Length (inches):", width=120)
                    ui.FloatDrag(model=self._length_model, min=12.0, max=600.0)

                # Quick length presets
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Quick:", width=50)
                    ui.Button("8'", width=40, clicked_fn=lambda: setattr(self._length_model, 'as_float', 96.0))
                    ui.Button("10'", width=40, clicked_fn=lambda: setattr(self._length_model, 'as_float', 120.0))
                    ui.Button("12'", width=40, clicked_fn=lambda: setattr(self._length_model, 'as_float', 144.0))
                    ui.Button("16'", width=40, clicked_fn=lambda: setattr(self._length_model, 'as_float', 192.0))
                    ui.Button("20'", width=40, clicked_fn=lambda: setattr(self._length_model, 'as_float', 240.0))

                ui.Spacer(height=10)
                ui.Separator(height=5)
                ui.Spacer(height=10)

                # Features Section
                ui.Label("Features / Connectors", style={"highlight_color": 0xFF00AAFF, "font_size": 16})

                # Features List Container
                with ui.ScrollingFrame(height=150, horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF):
                    self._features_container = ui.VStack(spacing=5)
                    self._rebuild_features_list()

                # Add Feature Buttons
                with ui.HStack(height=30, spacing=5):
                    ui.Button("Add Bolt Holes", clicked_fn=self._on_add_bolt_holes)
                    ui.Button("Add End Plate", clicked_fn=self._on_add_end_plate)
                with ui.HStack(height=30, spacing=5):
                    ui.Button("Add Cope", clicked_fn=self._on_add_cope)

                ui.Spacer(height=10)

                # Edit mode controls
                with ui.HStack(height=35, spacing=5):
                    ui.Button("Load Selected", clicked_fn=self._on_load_selected, height=35)
                    ui.Button("Clear", clicked_fn=self._on_clear, height=35)

                ui.Spacer(height=5)

                # Create/Update button
                self._create_button = ui.Button("Create Beam", clicked_fn=self._on_create, height=40)

                ui.Spacer(height=10)
                ui.Separator(height=5)

                # Export Drawings button
                ui.Button("Export Fabrication Drawings", clicked_fn=self._on_export_drawings,
                         height=40, style={"background_color": 0xFF336600})

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
            if feature_type == 'bolt_holes':
                loc = feature.get('location', 'web')
                count = feature.get('count', 2)
                label_text = f"Bolt Holes - {loc.title()} ({count}x)"
            elif feature_type == 'end_plate':
                end = feature.get('end', 'start')
                label_text = f"End Plate - {end.title()}"
            elif feature_type == 'cope':
                flange = feature.get('flange', 'top')
                end = feature.get('end', 'start')
                label_text = f"Cope - {flange.title()} {end.title()}"
            else:
                label_text = f"{feature_type.title()}"

            ui.Label(label_text, width=0)

            # Edit button
            ui.Button("Edit", width=50, clicked_fn=lambda idx=index: self._on_edit_feature(idx))

            # Delete button
            ui.Button("X", width=30, clicked_fn=lambda idx=index: self._on_delete_feature(idx))

    def _on_feature_toggled(self, index: int, enabled: bool):
        """Toggles a feature on/off"""
        if 0 <= index < len(self._features):
            self._features[index]['enabled'] = enabled

    def _on_add_bolt_holes(self):
        """Opens dialog to add bolt holes"""
        self._open_bolt_holes_dialog()

    def _on_add_end_plate(self):
        """Opens dialog to add end plate"""
        self._open_end_plate_dialog()

    def _on_add_cope(self):
        """Opens dialog to add cope cut"""
        self._open_cope_dialog()

    def _on_edit_feature(self, index: int):
        """Opens dialog to edit an existing feature"""
        if 0 <= index < len(self._features):
            feature = self._features[index]
            feature_type = feature.get('type')
            if feature_type == 'bolt_holes':
                self._open_bolt_holes_dialog(edit_index=index, existing_feature=feature)
            elif feature_type == 'end_plate':
                self._open_end_plate_dialog(edit_index=index, existing_feature=feature)
            elif feature_type == 'cope':
                self._open_cope_dialog(edit_index=index, existing_feature=feature)

    def _on_delete_feature(self, index: int):
        """Deletes a feature from the list"""
        if 0 <= index < len(self._features):
            self._features.pop(index)
            self._rebuild_features_list()

    def _open_bolt_holes_dialog(self, edit_index: int = None, existing_feature: dict = None):
        """Dialog for adding/editing bolt holes"""
        dialog = ui.Window("Bolt Holes", width=300, height=300)

        # Default values
        location_opts = ["web", "top_flange", "bottom_flange"]
        cur_loc = existing_feature.get('location', 'web') if existing_feature else 'web'
        cur_dia = existing_feature.get('diameter', 0.875) if existing_feature else 0.875
        cur_count = existing_feature.get('count', 2) if existing_feature else 2
        cur_spacing = existing_feature.get('spacing', 3.0) if existing_feature else 3.0
        cur_pos = existing_feature.get('position', 'end') if existing_feature else 'end'

        # Models
        location_model = ListItemModel([loc.replace('_', ' ').title() for loc in location_opts])
        location_model.get_item_value_model(None, 0).set_value(location_opts.index(cur_loc))
        dia_model = ui.SimpleFloatModel(cur_dia)
        count_model = ui.SimpleIntModel(cur_count)
        spacing_model = ui.SimpleFloatModel(cur_spacing)

        position_opts = ["end", "start", "center"]
        position_model = ListItemModel([p.title() for p in position_opts])
        position_model.get_item_value_model(None, 0).set_value(position_opts.index(cur_pos) if cur_pos in position_opts else 0)

        with dialog.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Bolt Holes", style={"font_size": 16})

                with ui.HStack(height=20):
                    ui.Label("Location:", width=100)
                    ui.ComboBox(location_model)

                with ui.HStack(height=20):
                    ui.Label("Position:", width=100)
                    ui.ComboBox(position_model)

                with ui.HStack(height=20):
                    ui.Label("Diameter (in):", width=100)
                    ui.FloatDrag(model=dia_model, min=0.25, max=2.0)

                with ui.HStack(height=20):
                    ui.Label("Count:", width=100)
                    ui.IntDrag(model=count_model, min=1, max=10)

                with ui.HStack(height=20):
                    ui.Label("Spacing (in):", width=100)
                    ui.FloatDrag(model=spacing_model, min=1.0, max=12.0)

                ui.Spacer(height=10)

                with ui.HStack(height=30, spacing=10):
                    ui.Button("OK", clicked_fn=lambda: self._on_bolt_holes_ok(
                        dialog, edit_index, location_opts, location_model, position_opts, position_model,
                        dia_model, count_model, spacing_model))
                    ui.Button("Cancel", clicked_fn=lambda: setattr(dialog, 'visible', False))

    def _on_bolt_holes_ok(self, dialog, edit_index, location_opts, location_model,
                          position_opts, position_model, dia_model, count_model, spacing_model):
        """Handle OK in bolt holes dialog"""
        feature = {
            'type': 'bolt_holes',
            'location': location_opts[location_model.get_item_value_model(None, 0).as_int],
            'position': position_opts[position_model.get_item_value_model(None, 0).as_int],
            'diameter': dia_model.as_float,
            'count': count_model.as_int,
            'spacing': spacing_model.as_float,
            'enabled': True
        }

        if edit_index is not None:
            self._features[edit_index] = feature
        else:
            self._features.append(feature)

        self._rebuild_features_list()
        dialog.visible = False

    def _open_end_plate_dialog(self, edit_index: int = None, existing_feature: dict = None):
        """Dialog for adding/editing end plate"""
        dialog = ui.Window("End Plate", width=300, height=250)

        # Default values
        end_opts = ["start", "end"]
        cur_end = existing_feature.get('end', 'start') if existing_feature else 'start'
        cur_thickness = existing_feature.get('thickness', 0.5) if existing_feature else 0.5
        cur_height = existing_feature.get('height', 0) if existing_feature else 0  # 0 = auto
        cur_width = existing_feature.get('width', 0) if existing_feature else 0    # 0 = auto

        # Models
        end_model = ListItemModel([e.title() for e in end_opts])
        end_model.get_item_value_model(None, 0).set_value(end_opts.index(cur_end))
        thickness_model = ui.SimpleFloatModel(cur_thickness)
        height_model = ui.SimpleFloatModel(cur_height)
        width_model = ui.SimpleFloatModel(cur_width)

        with dialog.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("End Plate", style={"font_size": 16})

                with ui.HStack(height=20):
                    ui.Label("End:", width=100)
                    ui.ComboBox(end_model)

                with ui.HStack(height=20):
                    ui.Label("Thickness (in):", width=100)
                    ui.FloatDrag(model=thickness_model, min=0.25, max=2.0)

                with ui.HStack(height=20):
                    ui.Label("Height (in):", width=100)
                    ui.FloatDrag(model=height_model, min=0.0, max=24.0)
                ui.Label("(0 = auto-size)", style={"color": 0xFF888888, "font_size": 10})

                with ui.HStack(height=20):
                    ui.Label("Width (in):", width=100)
                    ui.FloatDrag(model=width_model, min=0.0, max=24.0)
                ui.Label("(0 = auto-size)", style={"color": 0xFF888888, "font_size": 10})

                ui.Spacer(height=10)

                with ui.HStack(height=30, spacing=10):
                    ui.Button("OK", clicked_fn=lambda: self._on_end_plate_ok(
                        dialog, edit_index, end_opts, end_model, thickness_model, height_model, width_model))
                    ui.Button("Cancel", clicked_fn=lambda: setattr(dialog, 'visible', False))

    def _on_end_plate_ok(self, dialog, edit_index, end_opts, end_model, thickness_model, height_model, width_model):
        """Handle OK in end plate dialog"""
        height = height_model.as_float
        width = width_model.as_float

        # Auto-size if 0
        if height == 0 and self._current_section:
            height = self._current_section['depth_d'] + 2
        if width == 0 and self._current_section:
            width = self._current_section['flange_width_bf']

        feature = {
            'type': 'end_plate',
            'end': end_opts[end_model.get_item_value_model(None, 0).as_int],
            'thickness': thickness_model.as_float,
            'height': height,
            'width': width,
            'enabled': True
        }

        if edit_index is not None:
            self._features[edit_index] = feature
        else:
            self._features.append(feature)

        self._rebuild_features_list()
        dialog.visible = False

    def _open_cope_dialog(self, edit_index: int = None, existing_feature: dict = None):
        """Dialog for adding/editing cope cut"""
        dialog = ui.Window("Cope Cut", width=300, height=250)

        # Default values
        end_opts = ["start", "end"]
        flange_opts = ["top", "bottom"]
        cur_end = existing_feature.get('end', 'start') if existing_feature else 'start'
        cur_flange = existing_feature.get('flange', 'top') if existing_feature else 'top'
        cur_depth = existing_feature.get('depth', 2.0) if existing_feature else 2.0
        cur_height = existing_feature.get('height', 1.5) if existing_feature else 1.5

        # Models
        end_model = ListItemModel([e.title() for e in end_opts])
        end_model.get_item_value_model(None, 0).set_value(end_opts.index(cur_end))
        flange_model = ListItemModel([f.title() for f in flange_opts])
        flange_model.get_item_value_model(None, 0).set_value(flange_opts.index(cur_flange))
        depth_model = ui.SimpleFloatModel(cur_depth)
        height_model = ui.SimpleFloatModel(cur_height)

        with dialog.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Cope Cut", style={"font_size": 16})

                with ui.HStack(height=20):
                    ui.Label("End:", width=100)
                    ui.ComboBox(end_model)

                with ui.HStack(height=20):
                    ui.Label("Flange:", width=100)
                    ui.ComboBox(flange_model)

                with ui.HStack(height=20):
                    ui.Label("Depth (in):", width=100)
                    ui.FloatDrag(model=depth_model, min=0.5, max=12.0)

                with ui.HStack(height=20):
                    ui.Label("Height (in):", width=100)
                    ui.FloatDrag(model=height_model, min=0.5, max=6.0)

                ui.Spacer(height=10)

                with ui.HStack(height=30, spacing=10):
                    ui.Button("OK", clicked_fn=lambda: self._on_cope_ok(
                        dialog, edit_index, end_opts, end_model, flange_opts, flange_model,
                        depth_model, height_model))
                    ui.Button("Cancel", clicked_fn=lambda: setattr(dialog, 'visible', False))

    def _on_cope_ok(self, dialog, edit_index, end_opts, end_model, flange_opts, flange_model,
                    depth_model, height_model):
        """Handle OK in cope dialog"""
        feature = {
            'type': 'cope',
            'end': end_opts[end_model.get_item_value_model(None, 0).as_int],
            'flange': flange_opts[flange_model.get_item_value_model(None, 0).as_int],
            'depth': depth_model.as_float,
            'height': height_model.as_float,
            'enabled': True
        }

        if edit_index is not None:
            self._features[edit_index] = feature
        else:
            self._features.append(feature)

        self._rebuild_features_list()
        dialog.visible = False

    def _on_section_changed(self, index):
        """Handle AISC section selection change"""
        if 0 <= index < len(self._aisc_sections):
            self._current_section = self._aisc_sections[index]
            # Rebuild UI to show updated section info
            # Note: In a production system, you'd update the info label directly
            # For now, the info is shown in the _build_ui method

    def _on_load_selected(self):
        """Loads parameters from selected beam prim"""
        try:
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            if not stage:
                print("Error: No USD Stage open")
                return

            selection = ctx.get_selection()
            selected_paths = selection.get_selected_prim_paths()

            if not selected_paths:
                print("No prim selected. Please select a beam to edit.")
                return

            prim_path = selected_paths[0]
            prim = stage.GetPrimAtPath(prim_path)

            if not prim:
                print(f"Error: Could not get prim at {prim_path}")
                return

            # Check if it's a wide flange
            custom_data = prim.GetCustomData()
            generator_type = custom_data.get('generatorType')

            if generator_type != 'wide_flange':
                print(f"Selected prim is not a wide flange beam (type: {generator_type})")
                return

            # Load parameters
            designation = custom_data.get('designation', 'W8x24')
            length = custom_data.get('length', 120.0)
            features_json = custom_data.get('features', '[]')

            # Deserialize features
            if isinstance(features_json, str):
                self._features = json.loads(features_json)
            else:
                self._features = []

            # Update UI
            self._length_model.as_float = float(length)

            # Find and set AISC section
            for i, section in enumerate(self._aisc_sections):
                if section['designation'] == designation:
                    if self._section_model:
                        self._section_model.get_item_value_model(None, 0).set_value(i)
                    self._current_section = section
                    break

            self._rebuild_features_list()

            # Set edit mode
            self._editing_prim_path = prim_path
            if self._create_button:
                self._create_button.text = "Update Beam"

            print(f"Loaded beam from {prim_path}")
            print(f"  {designation}, Length={length}\", Features={len(self._features)}")

        except Exception as e:
            print(f"Error loading selected beam: {e}")
            import traceback
            traceback.print_exc()

    def _on_clear(self):
        """Clears edit mode and resets to create mode"""
        self._editing_prim_path = None
        if self._create_button:
            self._create_button.text = "Create Beam"
        print("Cleared edit mode - ready to create new beam")

    def _on_create(self):
        """Creates or updates a wide flange beam"""
        if not self._current_section:
            print("Error: No AISC section selected")
            return

        length = self._length_model.as_float
        designation = self._current_section['designation']

        is_update = self._editing_prim_path is not None
        action = "Updating" if is_update else "Creating"

        print(f"{action} Wide Flange: {designation}, Length={length}\"")
        if self._features:
            print(f"  Features: {len(self._features)} feature(s)")

        try:
            # Generate geometry
            solid = WideFlangeGenerator.create_from_aisc(
                self._current_section,
                length,
                features=self._features
            )

            # Get Stage
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            if not stage:
                print("Error: No USD Stage open")
                return

            # Determine path
            current_transform = []
            
            if is_update:
                path = self._editing_prim_path
                # Capture current transform before removing
                prim = stage.GetPrimAtPath(path)
                if prim:
                    current_transform = usd_utils.get_local_transform(prim)
                stage.RemovePrim(path)
            else:
                path_root = "/World/WideFlange"
                path = path_root
                idx = 1
                while stage.GetPrimAtPath(path):
                    path = f"{path_root}_{idx}"
                    idx += 1
            
            # Enforce Units
            usd_utils.setup_stage_units(stage)

            # Convert to USD
            mesh_prim = usd_utils.create_mesh_from_shape(stage, path, solid)
            
            # Restore Transform if we captured one
            if current_transform and mesh_prim:
                usd_utils.set_local_transform(mesh_prim.GetPrim(), current_transform)
            elif not is_update:
                 # Smart Placement for new objects
                 selection = ctx.get_selection().get_selected_prim_paths()
                 if selection:
                    ref_path = selection[0]
                    ref_prim = stage.GetPrimAtPath(ref_path)
                    if ref_prim:
                        # Copy transform from selection to be near it
                        tf = usd_utils.get_local_transform(ref_prim)
                        if tf and mesh_prim:
                             usd_utils.set_local_transform(mesh_prim.GetPrim(), tf)

            # Store metadata
            if mesh_prim:
                prim = mesh_prim.GetPrim()
                prim.SetCustomDataByKey('generatorType', 'wide_flange')
                prim.SetCustomDataByKey('designation', designation)
                prim.SetCustomDataByKey('length', float(length))
                prim.SetCustomDataByKey('aisc_data', json.dumps(self._current_section))
                prim.SetCustomDataByKey('features', json.dumps(self._features))
                
                # Create Anchors for mating/connection
                depth = self._current_section['depth_d']
                self._create_beam_anchors(stage, path, length, depth)

            action_past = "Updated" if is_update else "Created"
            print(f"{action_past} Wide Flange at {path}")
            if self._features:
                enabled_count = len([f for f in self._features if f.get('enabled', True)])
                print(f"  Applied {enabled_count} enabled feature(s)")

        except Exception as e:
            print(f"Error {action.lower()} beam: {e}")
            import traceback
            traceback.print_exc()

    def _create_beam_anchors(self, stage, parent_path, length, depth):
        """
        Creates anchor points on a steel beam for mating/connection.
        Include Top, Bottom, and Web Face anchors.
        """
        from pxr import UsdGeom, Gf, Sdf
        
        # Helper to create anchor
        def create_anchor(name, translate, rotate_xyz, port_type="Steel_Face", color=Gf.Vec3f(0, 0.8, 0.8)):
            path = f"{parent_path}/{name}"
            xform = UsdGeom.Xform.Define(stage, path)
            xform.AddTranslateOp().Set(translate)
            xform.AddRotateXYZOp().Set(rotate_xyz)
            
            prim = xform.GetPrim()
            prim.CreateAttribute("twin:is_port", Sdf.ValueTypeNames.Bool).Set(True)
            prim.CreateAttribute("twin:port_type", Sdf.ValueTypeNames.String).Set(port_type)
            prim.CreateAttribute("custom:is_anchor", Sdf.ValueTypeNames.Bool).Set(True)
            
            # Visualizer
            viz = UsdGeom.Sphere.Define(stage, f"{path}/viz")
            viz.GetRadiusAttr().Set(1.0)
            viz.GetDisplayColorAttr().Set([color])

        # Anchor_Start (Z=0): Pointing -Z.
        create_anchor("Anchor_Start", 
                      Gf.Vec3d(0, 0, 0), 
                      Gf.Vec3f(0, -90, 0), 
                      port_type="Steel_End", color=Gf.Vec3f(0, 1, 0))

        # Anchor_End (Z=Length): Pointing +Z.
        create_anchor("Anchor_End", 
                      Gf.Vec3d(0, 0, length), 
                      Gf.Vec3f(0, 90, 0), 
                      port_type="Steel_End", color=Gf.Vec3f(0, 1, 0))

        mid_z = length / 2.0
        
        # Anchor_Top (Top Flange, Y=depth/2): Pointing +Y
        create_anchor("Anchor_Top", 
                      Gf.Vec3d(0, depth/2, mid_z), 
                      Gf.Vec3f(0, 0, 90))

        # Anchor_Bottom (Bottom Flange, Y=-depth/2): Pointing -Y
        create_anchor("Anchor_Bottom", 
                      Gf.Vec3d(0, -depth/2, mid_z), 
                      Gf.Vec3f(0, 0, -90))
        
        # Anchor_WebRight (Web Face, X=0 usually, but let's say "Right" is +X).
        # Note: Actual web is thin. Using X=0 might bury the anchor in the web if we don't offset.
        # But usually we snap to center-lines for steel.
        # If we want surface mating, we should probably offset by web_thickness/2.
        # But simple centerline snapping is often preferred for schematic.
        # Let's stick to X=0 for now, but ensure orientation is +X.
        create_anchor("Anchor_WebRight", 
                      Gf.Vec3d(0, 0, mid_z), 
                      Gf.Vec3f(0, 0, 0)) # Pointing +X by default

        # Anchor_WebLeft (Web Face, X=0, pointing -X)
        create_anchor("Anchor_WebLeft", 
                      Gf.Vec3d(0, 0, mid_z), 
                      Gf.Vec3f(0, 0, 180)) # Pointing -X

        print(f"[WideFlange] Created 6 anchors (Start, End, Top, Bottom, WebLeft, WebRight)")

    def _on_export_drawings(self):
        """Opens dialog to export fabrication drawings"""
        self._open_export_dialog()

    def _open_export_dialog(self):
        """Dialog for configuring drawing export"""
        dialog = ui.Window("Export Fabrication Drawings", width=400, height=400)

        # Models
        format_opts = ["DXF", "PDF", "Both"]
        format_model = ListItemModel(format_opts)

        project_model = ui.SimpleStringModel("Steel Fabrication Project")
        engineer_model = ui.SimpleStringModel("")
        dwg_number_model = ui.SimpleStringModel("S-001")
        output_dir_model = ui.SimpleStringModel("C:/Programming/buildteamai/output")

        with dialog.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Export Fabrication Drawings", style={"highlight_color": 0xFFFF6600, "font_size": 16})

                ui.Spacer(height=5)

                # Output format
                with ui.HStack(height=20):
                    ui.Label("Format:", width=120)
                    ui.ComboBox(format_model)

                ui.Spacer(height=5)
                ui.Separator(height=5)
                ui.Spacer(height=5)

                ui.Label("Title Block Information", style={"font_size": 14})

                # Project name
                with ui.HStack(height=20):
                    ui.Label("Project Name:", width=120)
                    ui.StringField(model=project_model)

                # Engineer
                with ui.HStack(height=20):
                    ui.Label("Engineer:", width=120)
                    ui.StringField(model=engineer_model)

                # Drawing number
                with ui.HStack(height=20):
                    ui.Label("Drawing Number:", width=120)
                    ui.StringField(model=dwg_number_model)

                ui.Spacer(height=5)
                ui.Separator(height=5)
                ui.Spacer(height=5)

                # Output directory
                with ui.HStack(height=20):
                    ui.Label("Output Folder:", width=120)
                    ui.StringField(model=output_dir_model)

                ui.Spacer(height=10)

                # Info text
                ui.Label("Drawings will include:", style={"color": 0xFFAAAAAA, "font_size": 11})
                ui.Label("  • Multi-view drawings (front, side, details)", style={"color": 0xFFAAAAAA, "font_size": 10})
                ui.Label("  • Dimensions and GD&T callouts", style={"color": 0xFFAAAAAA, "font_size": 10})
                ui.Label("  • Cut list / bill of materials", style={"color": 0xFFAAAAAA, "font_size": 10})
                ui.Label("  • AISC standard notes", style={"color": 0xFFAAAAAA, "font_size": 10})

                ui.Spacer(height=10)

                # Export buttons
                with ui.HStack(height=35, spacing=10):
                    ui.Button("Export", clicked_fn=lambda: self._on_export_ok(
                        dialog, format_opts, format_model, project_model,
                        engineer_model, dwg_number_model, output_dir_model),
                             height=35)
                    ui.Button("Cancel", clicked_fn=lambda: setattr(dialog, 'visible', False), height=35)

    def _on_export_ok(self, dialog, format_opts, format_model, project_model,
                      engineer_model, dwg_number_model, output_dir_model):
        """Handle export OK button"""
        if not self._current_section:
            print("[Export] Error: No beam section selected")
            return

        # Get export settings
        format_choice = format_opts[format_model.get_item_value_model(None, 0).as_int]
        project_name = project_model.as_string
        engineer = engineer_model.as_string
        dwg_number = dwg_number_model.as_string
        output_dir = output_dir_model.as_string

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Prepare component data for drawing
        component_data = {
            'designation': self._current_section['designation'],
            'length': self._length_model.as_float,
            'aisc_data': self._current_section,
            'features': self._features
        }

        # Create metadata
        metadata = DrawingMetadata(
            project_name=project_name,
            drawing_title=f"{self._current_section['designation']} × {self._length_model.as_float/12:.1f}'-0\" Beam",
            drawing_number=dwg_number,
            engineer=engineer,
            designer="BuildTeamAI",
            scale="1:10"
        )

        # Create drawing
        print(f"[Export] Generating fabrication drawings...")
        drawing = WideFlangeDrawing(component_data, metadata)
        drawing.add_standard_notes()

        # Base filename
        base_filename = f"{self._current_section['designation']}_L{self._length_model.as_float:.0f}"

        # Export based on format
        success = False
        try:
            if format_choice in ["DXF", "Both"]:
                dxf_path = os.path.join(output_dir, f"{base_filename}.dxf")
                print(f"[Export] Exporting DXF to: {dxf_path}")
                success = export_to_dxf(drawing, dxf_path)

            if format_choice in ["PDF", "Both"]:
                pdf_path = os.path.join(output_dir, f"{base_filename}.pdf")
                print(f"[Export] Exporting PDF to: {pdf_path}")
                success = export_to_pdf(drawing, pdf_path)

            if success:
                print(f"[Export] ✓ Fabrication drawings exported successfully!")
                print(f"[Export]   Output folder: {output_dir}")
                dialog.visible = False
            else:
                print(f"[Export] ✗ Export failed. Check console for errors.")

        except Exception as e:
            print(f"[Export] Error during export: {e}")
            import traceback
            traceback.print_exc()
