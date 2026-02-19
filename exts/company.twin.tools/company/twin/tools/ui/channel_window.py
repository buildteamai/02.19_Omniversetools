# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Channel Window

UI for creating AISC C-channel steel shapes.
"""

import omni.ui as ui
from pxr import Usd, UsdGeom, Gf, Sdf
import omni.usd
import json

from ..objects.channel import ChannelGenerator


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


class ChannelWindow(ui.Window):
    """
    Window for creating AISC C-channel steel shapes.
    """
    
    def __init__(self, title: str = "Channel (C-Shape)"):
        super().__init__(title, width=380, height=420)
        
        # Load AISC data
        self._aisc_data = ChannelGenerator.load_aisc_data()
        self._section_names = [s['designation'] for s in self._aisc_data]
        if not self._section_names:
            self._section_names = ["C8x11.5"]
            self._aisc_data = [{"designation": "C8x11.5", "depth_d": 8.0, 
                               "flange_width_bf": 2.26, "flange_thickness_tf": 0.39,
                               "web_thickness_tw": 0.22, "weight_lb_ft": 11.5}]
        
        self._section_index = ui.SimpleIntModel(min(5, len(self._section_names) - 1))
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
                            ui.ComboBox(model, width=180).model.add_item_changed_fn(
                                lambda m, i: setattr(self._section_index, 'as_int', m.get_item_value_model(None, 0).as_int)
                            )
                        
                        # Show section properties
                        self._props_label = ui.Label("", word_wrap=True)
                        self._update_props_display()
                
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
                    ui.Button("Create Channel", clicked_fn=self._on_create, width=180,
                             style={"Button": {"background_color": 0xFF44AA44, "font_size": 16}})
                    ui.Spacer(width=60)
                
                ui.Spacer()
    
    def _update_props_display(self):
        idx = self._section_index.as_int
        if idx < len(self._aisc_data):
            data = self._aisc_data[idx]
            text = f"Depth: {data.get('depth_d', 0)}\", Flange: {data.get('flange_width_bf', 0)}\", "
            text += f"Weight: {data.get('weight_lb_ft', 0)} lb/ft"
            self._props_label.text = text
    
    def _set_length(self, inches):
        self._length.as_float = inches
    
    def _on_create(self):
        """Creates the channel geometry."""
        stage = omni.usd.get_context().get_stage()
        if not stage:
            print("[Channel] No USD stage")
            return
        
        idx = self._section_index.as_int
        aisc_data = self._aisc_data[idx]
        length = self._length.as_float
        designation = aisc_data['designation']
        
        print(f"[Channel] Creating {designation} x {length}\"")
        
        try:
            # Generate geometry
            solid = ChannelGenerator.create_from_aisc(aisc_data, length)
            
            # Create USD path
            base_path = "/World/Channel"
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
                metadata = ChannelGenerator.get_metadata(designation, length, aisc_data)
                for key, value in metadata.items():
                    # USD can't store Python lists/dicts - serialize to JSON
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value)
                    prim.SetCustomDataByKey(key, value)
                
                # Create anchors
                self._create_anchors(stage, path, length, aisc_data.get('depth_d', 8.0))
                
                print(f"[Channel] Created at {path}")
                
        except Exception as e:
            print(f"[Channel] Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_anchors(self, stage, parent_path, length, depth):
        """Creates anchor points on the channel."""
        half_length = length / 2
        half_depth = depth / 2
        
        # Anchor at start
        anchor_start = UsdGeom.Xform.Define(stage, f"{parent_path}/Anchor_Start")
        anchor_start.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0))
        prim_start = anchor_start.GetPrim()
        prim_start.CreateAttribute("twin:is_port", Sdf.ValueTypeNames.Bool).Set(True)
        prim_start.CreateAttribute("custom:is_anchor", Sdf.ValueTypeNames.Bool).Set(True)
        
        # Anchor at end
        anchor_end = UsdGeom.Xform.Define(stage, f"{parent_path}/Anchor_End")
        anchor_end.AddTranslateOp().Set(Gf.Vec3d(0, 0, length))
        prim_end = anchor_end.GetPrim()
        prim_end.CreateAttribute("twin:is_port", Sdf.ValueTypeNames.Bool).Set(True)
        prim_end.CreateAttribute("custom:is_anchor", Sdf.ValueTypeNames.Bool).Set(True)
        
        # Visualize anchors
        viz_start = UsdGeom.Sphere.Define(stage, f"{parent_path}/Anchor_Start/viz")
        viz_start.GetRadiusAttr().Set(0.5)
        viz_start.GetDisplayColorAttr().Set([Gf.Vec3f(0, 0.8, 0)])
        
        viz_end = UsdGeom.Sphere.Define(stage, f"{parent_path}/Anchor_End/viz")
        viz_end.GetRadiusAttr().Set(0.5)
        viz_end.GetDisplayColorAttr().Set([Gf.Vec3f(0.8, 0, 0)])
