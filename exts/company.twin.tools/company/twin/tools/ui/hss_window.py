# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
HSS Tube Window

UI for creating AISC HSS (Hollow Structural Section) steel shapes.
"""

import omni.ui as ui
from pxr import Usd, UsdGeom, Gf, Sdf
import omni.usd

from ..objects.hss_tube import HSSGenerator


class ComboItem(ui.AbstractItem):
    """Simple item for combo box."""
    def __init__(self, text):
        super().__init__()
        self.model = ui.SimpleStringModel(text)


class ComboModel(ui.AbstractItemModel):
    """Proper combo box model using AbstractItem objects."""
    def __init__(self, items):
        super().__init__()
        self._items = [ComboItem(item) for item in items]
        self._current_index = ui.SimpleIntModel(0)
    
    def get_item_children(self, item=None):
        return self._items
    
    def get_item_value_model_count(self, item):
        return 1
    
    def get_item_value_model(self, item, column_id):
        if item is None:
            return self._current_index
        return item.model


class HSSWindow(ui.Window):
    """
    Window for creating AISC HSS tube steel shapes.
    """
    
    def __init__(self, title: str = "HSS Tube"):
        super().__init__(title, width=380, height=450)
        
        # Load AISC data
        self._aisc_data = HSSGenerator.load_aisc_data()
        self._section_names = [s['designation'] for s in self._aisc_data]
        if not self._section_names:
            self._section_names = ["HSS6x6x1/4"]
            self._aisc_data = [{"designation": "HSS6x6x1/4", "shape": "square",
                               "outer_width": 6.0, "outer_height": 6.0,
                               "wall_thickness": 0.233, "weight_lb_ft": 19.02}]
        
        self._section_index = ui.SimpleIntModel(min(3, len(self._section_names) - 1))
        self._length = ui.SimpleFloatModel(120.0)
        
        self.frame.set_build_fn(self._build_ui)
    
    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=6):
                ui.Spacer(height=4)
                
                # Section Selection
                with ui.CollapsableFrame("AISC Section", height=0):
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=24):
                            ui.Label("Section:", width=80)
                            model = ComboModel(self._section_names)
                            model.get_item_value_model(None, 0).as_int = self._section_index.as_int
                            ui.ComboBox(model, width=200).model.add_item_changed_fn(
                                lambda m, i: setattr(self._section_index, 'as_int', m.get_item_value_model(None, 0).as_int)
                            )
                        
                        # Properties display
                        self._props_label = ui.Label("", word_wrap=True)
                        self._update_props_display()
                        
                        # Wall adequacy check
                        self._wall_label = ui.Label("", word_wrap=True, style={"color": 0xFF88FF88})
                        self._check_wall_adequacy()
                
                # Length
                with ui.CollapsableFrame("Dimensions", height=0):
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=24):
                            ui.Label("Length:", width=80)
                            ui.FloatSlider(self._length, min=12.0, max=600.0, width=160)
                            ui.Label("  in", width=40)
                        
                        # Quick presets
                        with ui.HStack(height=28):
                            ui.Label("Presets:", width=80)
                            for ft in [6, 8, 10, 12, 16, 20]:
                                ui.Button(f"{ft}'", width=35, clicked_fn=lambda f=ft: self._set_length(f * 12))
                
                ui.Spacer(height=16)
                
                # Create Button
                with ui.HStack(height=40):
                    ui.Spacer(width=60)
                    ui.Button("Create HSS", clicked_fn=self._on_create, width=180,
                             style={"Button": {"background_color": 0xFF44AA44, "font_size": 16}})
                    ui.Spacer(width=60)
                
                ui.Spacer()
    
    def _update_props_display(self):
        idx = self._section_index.as_int
        if idx < len(self._aisc_data):
            data = self._aisc_data[idx]
            shape = data.get('shape', 'square')
            if shape == 'square':
                text = f"{data.get('outer_width', 0)}\" square, "
            else:
                text = f"{data.get('outer_width', 0)}\"x{data.get('outer_height', 0)}\", "
            text += f"Wall: {data.get('wall_thickness', 0)}\", Weight: {data.get('weight_lb_ft', 0)} lb/ft"
            self._props_label.text = text
    
    def _check_wall_adequacy(self):
        idx = self._section_index.as_int
        if idx < len(self._aisc_data):
            data = self._aisc_data[idx]
            wall = data.get('wall_thickness', 0.25)
            width = data.get('outer_width', 6.0)
            
            is_ok, b_over_t, msg = HSSGenerator.check_wall_adequacy(wall, width)
            
            self._wall_label.text = msg
            if is_ok:
                self._wall_label.style = {"color": 0xFF88FF88}
            else:
                self._wall_label.style = {"color": 0xFFFF8888}
    
    def _set_length(self, inches):
        self._length.as_float = inches
    
    def _on_create(self):
        """Creates the HSS tube geometry."""
        stage = omni.usd.get_context().get_stage()
        if not stage:
            print("[HSS] No USD stage")
            return
        
        idx = self._section_index.as_int
        aisc_data = self._aisc_data[idx]
        length = self._length.as_float
        designation = aisc_data['designation']
        
        print(f"[HSS] Creating {designation} x {length}\"")
        
        try:
            # Generate geometry
            solid = HSSGenerator.create_from_aisc(aisc_data, length)
            
            # Create USD path
            base_path = "/World/HSS"
            path = base_path
            counter = 1
            while stage.GetPrimAtPath(path).IsValid():
                path = f"{base_path}_{counter}"
                counter += 1
            
            # Export to USD
            from ..utils.usd_utils import export_solid_to_usd
            export_solid_to_usd(stage, solid, path)
            
            # Set metadata
            prim = stage.GetPrimAtPath(path)
            if prim.IsValid():
                import json
                metadata = HSSGenerator.get_metadata(designation, length, aisc_data)
                for key, value in metadata.items():
                    # USD can't store Python lists/dicts - serialize to JSON
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value)
                    prim.SetCustomDataByKey(key, value)
                
                # Create anchors
                self._create_anchors(stage, path, length, aisc_data)
                
                print(f"[HSS] Created at {path}")
                
        except Exception as e:
            print(f"[HSS] Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_anchors(self, stage, parent_path, length, aisc_data):
        """Creates anchor points on the HSS tube."""
        width = aisc_data.get('outer_width', 6.0)
        height = aisc_data.get('outer_height', width)
        
        # Define rotations (USD Gf.Rotation is used via XformOp)
        # Port "Flow" axis is +X. We stand at the port looking OUT.
        
        # Anchor_Start (Z=0): Pointing -Z.
        # Rotate -90 around Y axis.
        self._create_anchor(stage, f"{parent_path}/Anchor_Start", 
                            translate=Gf.Vec3d(0, 0, 0),
                            rotate_xyz=Gf.Vec3f(0, -90, 0),
                            port_type="Steel_End", shape="HSS")

        # Anchor_End (Z=Length): Pointing +Z.
        # Rotate +90 around Y axis.
        self._create_anchor(stage, f"{parent_path}/Anchor_End", 
                            translate=Gf.Vec3d(0, 0, length),
                            rotate_xyz=Gf.Vec3f(0, 90, 0),
                            port_type="Steel_End", shape="HSS")

        # Surface Ports at Mid-Span
        mid_z = length / 2.0
        
        # Anchor_Top (Y=height/2): Pointing +Y.
        # Rotate +90 around Z axis.
        self._create_anchor(stage, f"{parent_path}/Anchor_Top", 
                            translate=Gf.Vec3d(0, height/2, mid_z),
                            rotate_xyz=Gf.Vec3f(0, 0, 90),
                            port_type="Steel_Face", shape="Flat", color=Gf.Vec3f(0, 0.8, 0.8))

        # Anchor_Bottom (Y=-height/2): Pointing -Y.
        # Rotate -90 around Z axis.
        self._create_anchor(stage, f"{parent_path}/Anchor_Bottom", 
                            translate=Gf.Vec3d(0, -height/2, mid_z),
                            rotate_xyz=Gf.Vec3f(0, 0, -90),
                            port_type="Steel_Face", shape="Flat", color=Gf.Vec3f(0, 0.8, 0.8))

        # Anchor_Left (X=-width/2): Pointing -X.
        # Rotate 180 around Z (or Y) axis. 
        self._create_anchor(stage, f"{parent_path}/Anchor_Left", 
                            translate=Gf.Vec3d(-width/2, 0, mid_z),
                            rotate_xyz=Gf.Vec3f(0, 0, 180),
                            port_type="Steel_Face", shape="Flat", color=Gf.Vec3f(0, 0.8, 0.8))

        # Anchor_Right (X=width/2): Pointing +X.
        # Identity rotation.
        self._create_anchor(stage, f"{parent_path}/Anchor_Right", 
                            translate=Gf.Vec3d(width/2, 0, mid_z),
                            rotate_xyz=Gf.Vec3f(0, 0, 0),
                            port_type="Steel_Face", shape="Flat", color=Gf.Vec3f(0, 0.8, 0.8))

        print(f"[HSS] Created 6 anchors (Start, End, Top, Bottom, Left, Right)")

    def _create_anchor(self, stage, path, translate, rotate_xyz, port_type, shape, color=Gf.Vec3f(0, 1, 0)):
        """Helper to create a single anchor."""
        xform = UsdGeom.Xform.Define(stage, path)
        xform.AddTranslateOp().Set(translate)
        xform.AddRotateXYZOp().Set(rotate_xyz)
        
        prim = xform.GetPrim()
        prim.CreateAttribute("twin:is_port", Sdf.ValueTypeNames.Bool).Set(True)
        prim.CreateAttribute("twin:port_type", Sdf.ValueTypeNames.String).Set(port_type)
        prim.CreateAttribute("twin:port_shape", Sdf.ValueTypeNames.String).Set(shape)
        prim.CreateAttribute("custom:is_anchor", Sdf.ValueTypeNames.Bool).Set(True)
        
        # Visualizer
        viz = UsdGeom.Sphere.Define(stage, f"{path}/viz")
        viz.GetRadiusAttr().Set(0.5)
        viz.GetDisplayColorAttr().Set([color])

