# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

import omni.ui as ui
import omni.usd
from pxr import Gf, UsdGeom, UsdShade, Sdf
import json
import os
import math
from ..objects.duct_warp import DuctWarpGenerator

# Only used for saving presets if needed
DATA_PATH = "c:/Programming/buildteamai/data/pipes.json"

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

class PipeWindow(ui.Window):
    def __init__(self, title="Create Pipe (Warp)", **kwargs):
        super().__init__(title, width=350, height=500, **kwargs)
        
        # Geometry Models
        self._diameter_model = ui.SimpleFloatModel(4.0)
        self._length_model = ui.SimpleFloatModel(24.0)
        self._radius_model = ui.SimpleFloatModel(6.0)  # Bend radius
        self._angle_model = ui.SimpleFloatModel(90.0)  # 0 = Straight
        self._segments_model = ui.SimpleIntModel(20)
        
        # Pipe Options
        self._materials = ["Carbon Steel", "Stainless Steel", "Copper", "PVC"]
        self._material_index = ui.SimpleIntModel(0)
        
        self._connections = ["Plain End", "Flanged"]
        self._connection_index = ui.SimpleIntModel(1)  # Default Flanged
        
        self._status_label = None
        self._create_button = None
        
        self._build_ui()
        
    def _build_ui(self):
        with self.frame:
            with ui.ScrollingFrame():
                with ui.VStack(height=0, spacing=8, padding=15):
                    ui.Label("MEP Piping Tool", style={"font_size": 18, "color": 0xFF00B4FF})
                    ui.Line(height=2, style={"color": 0xFF333333})
                    
                    # === GEOMETRY ===
                    ui.Label("Geometry", style={"font_size": 14, "color": 0xFFAAAAAA})
                    
                    with ui.HStack(height=22):
                        ui.Label("Diameter:", width=100)
                        ui.FloatDrag(model=self._diameter_model, min=0.5, max=60.0, step=0.25)
                        ui.Label("in", width=20, style={"color": 0xFF888888})

                    with ui.HStack(height=22):
                        ui.Label("Bend Angle:", width=100)
                        ui.FloatDrag(model=self._angle_model, min=0.0, max=180.0, step=15.0)
                        ui.Label("deg (0=Straight)", style={"color": 0xFF888888})

                    # Conditional logic: straight vs bent params could be visible/hidden
                    # For simplicity, we show both but explain usage based on Angle
                    
                    with ui.HStack(height=22):
                        ui.Label("Length:", width=100)
                        ui.FloatDrag(model=self._length_model, min=1.0, max=1000.0)
                        ui.Label("in (Straight)", style={"color": 0xFF888888})
                        
                    with ui.HStack(height=22):
                        ui.Label("Bend Radius:", width=100)
                        ui.FloatDrag(model=self._radius_model, min=1.0, max=1000.0)
                        ui.Label("in (Elbow)", style={"color": 0xFF888888})

                    with ui.HStack(height=22):
                        ui.Label("Segments:", width=100)
                        ui.IntSlider(model=self._segments_model, min=8, max=64)

                    ui.Spacer(height=10)
                    ui.Separator(height=5)
                    ui.Spacer(height=10)
                    
                    # === PROPERTIES ===
                    ui.Label("Properties", style={"font_size": 14, "color": 0xFFAAAAAA})
                    
                    with ui.HStack(height=22):
                        ui.Label("Material:", width=100)
                        mat_model = ListItemModel(self._materials)
                        mat_model.get_item_value_model(None, 0).as_int = self._material_index.as_int
                        mat_model.get_item_value_model(None, 0).add_value_changed_fn(
                            lambda m: setattr(self._material_index, 'as_int', m.as_int)
                        )
                        ui.ComboBox(mat_model)
                        
                    with ui.HStack(height=22):
                        ui.Label("Connection:", width=100)
                        conn_model = ListItemModel(self._connections)
                        conn_model.get_item_value_model(None, 0).as_int = self._connection_index.as_int
                        conn_model.get_item_value_model(None, 0).add_value_changed_fn(
                            lambda m: setattr(self._connection_index, 'as_int', m.as_int)
                        )
                        ui.ComboBox(conn_model)

                    ui.Spacer(height=15)
                    
                    # === ACTIONS ===
                    self._create_button = ui.Button("Create Pipe", height=40, clicked_fn=self._on_create,
                                                  style={"background_color": 0xFF2B5B2B, "font_size": 16})
                    
                    self._status_label = ui.Label("Ready", style={"color": 0xFF888888})

    def _on_create(self):
        stage = omni.usd.get_context().get_stage()
        if not stage:
            self._status_label.text = "Error: No Stage Open"
            return
            
        # Unique Path
        path_root = "/World/Pipe"
        path = path_root
        idx = 1
        while stage.GetPrimAtPath(path):
            path = f"{path_root}_{idx}"
            idx += 1
            
        try:
            diameter = self._diameter_model.as_float
            length = self._length_model.as_float
            angle = self._angle_model.as_float
            radius = self._radius_model.as_float
            segments = self._segments_model.as_int
            
            # Connection logic
            conn_idx = self._connection_index.as_int
            add_flanges = (conn_idx == 1)  # 1 = Flanged
            
            # Create Geometry using DuctWarpGenerator (Round mode)
            mesh = DuctWarpGenerator.create(
                stage=stage,
                path=path,
                width=diameter,    # Ignored for round
                height=diameter,   # Ignored for round
                radius=radius,
                angle_deg=angle,
                segments=segments,
                add_flanges=add_flanges,
                length=length,
                shape="round",
                diameter=diameter,
                system_type="pipe"
            )
            
            # Apply Material
            mat_idx = self._material_index.as_int
            mat_name = self._materials[mat_idx]
            self._apply_pipe_material(stage, path, mat_name)
            
            # Store metadata
            prim = mesh.GetPrim()
            # Generator now sets generatorType to 'pipe_straight' or 'pipe_bent'
            # We just need to add the material
            prim.SetCustomDataByKey('pipeMaterial', mat_name)
            prim.SetCustomDataByKey('connectionType', self._connections[conn_idx])
            
            self._status_label.text = f"Created {mat_name} Pipe at {path}"
            print(f"[Pipe] Created {mat_name} pipe at {path}")
            
        except Exception as e:
            self._status_label.text = f"Error: {str(e)}"
            import traceback
            traceback.print_exc()

    def _apply_pipe_material(self, stage, path, mat_name):
        """Applies specific PBR material to the pipe"""
        mat_path = f"{path}/Material"
        material = UsdShade.Material.Define(stage, mat_path)
        shader_path = f"{mat_path}/PBRShader"
        shader = UsdShade.Shader.Define(stage, shader_path)
        shader.CreateIdAttr("UsdPreviewSurface")
        
        # Default properties
        roughness = 0.4
        metallic = 0.0
        color = Gf.Vec3f(0.5, 0.5, 0.5)
        
        if mat_name == "Carbon Steel":
            color = Gf.Vec3f(0.15, 0.15, 0.15)  # Dark Grey/Black
            metallic = 0.8
            roughness = 0.5
        elif mat_name == "Stainless Steel":
            color = Gf.Vec3f(0.8, 0.8, 0.85)  # Bright Silver
            metallic = 1.0
            roughness = 0.2
        elif mat_name == "Copper":
            color = Gf.Vec3f(0.72, 0.45, 0.2)  # Copper/Orange
            metallic = 1.0
            roughness = 0.25
        elif mat_name == "PVC":
            color = Gf.Vec3f(0.95, 0.95, 0.95)  # White Plastic
            metallic = 0.0
            roughness = 0.3
            
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(color)
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
        
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        
        mesh_prim = stage.GetPrimAtPath(path)
        if mesh_prim:
            UsdShade.MaterialBindingAPI(mesh_prim).Bind(material)
