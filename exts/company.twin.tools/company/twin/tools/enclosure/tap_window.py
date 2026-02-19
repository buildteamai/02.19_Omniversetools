# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Tap Window — Add Exhaust Taps to Enclosure Walls/Panels.

Coordinate Convention (matches enclosure_configurator.py + panels.py):
  - Panel Xform origin: Bottom-Center-Back of the panel volume.
  - Panel Face child: translate (0, H/2, T/2), scale (W/2, H/2, T/2).
  - Local +Z is the "outward" direction (face normal pointing OUT of enclosure).
  - Wall rotations map Local Z → World outward normal:
      Left Wall:  rot Y=180  → Local +Z → World -Z  (outward)
      Right Wall: no rot     → Local +Z → World +Z  (outward)
      Roof:       rot X=-90  → Local +Z → World +Y  (upward/outward)
"""

import re
import omni.ui as ui
import omni.usd
from pxr import Usd, UsdGeom, Gf, Sdf
from ..utils.port import Port
from .panels import _apply_galvanized_material


class TapWindow(ui.Window):
    """
    Window to add Exhaust Taps (Duct Connections) to enclosure walls/panels.
    """
    def __init__(self, title="Add Enclosure Tap", **kwargs):
        super().__init__(title, width=400, height=500, **kwargs)
        
        self.frame.set_build_fn(self._build_ui)
        
        # Models (all in inches)
        self._width_model = ui.SimpleFloatModel(12.0)
        self._height_model = ui.SimpleFloatModel(12.0)
        self._length_model = ui.SimpleFloatModel(4.0)  # Stub length
        
        self._x_offset_model = ui.SimpleFloatModel(24.0)
        self._y_offset_model = ui.SimpleFloatModel(48.0)
        
        self._status_label = None

    def _build_ui(self):
        with ui.VStack(spacing=10, style={"margin": 10}):
            ui.Label("Add Exhaust Tap", style={"font_size": 18, "color": 0xFF00B4FF})
            ui.Label("Select Panel(s) or a Wall to attach to.", style={"font_size": 12, "color": 0xFF888888})
            ui.Line(height=2, style={"color": 0xFF333333})
            
            # Dimensions
            with ui.HStack(height=22):
                ui.Label("Tap Width:", width=100)
                ui.FloatField(model=self._width_model)
            with ui.HStack(height=22):
                ui.Label("Tap Height:", width=100)
                ui.FloatField(model=self._height_model)
            with ui.HStack(height=22):
                ui.Label("Stub Length:", width=100)
                ui.FloatField(model=self._length_model)
                
            ui.Spacer(height=5)
            
            # Position (only used for Wall selections)
            with ui.HStack(height=22):
                ui.Label("Offset X:", width=100)
                ui.FloatField(model=self._x_offset_model)
            with ui.HStack(height=22):
                ui.Label("Offset Y:", width=100)
                ui.FloatField(model=self._y_offset_model)
                
            ui.Spacer(height=10)
            
            ui.Button("Create Tap", height=40, clicked_fn=self._on_create_clicked, 
                     style={"background_color": 0xFF2B5B2B})
            
            self._status_label = ui.Label("", style={"color": 0xFFFFFF00})

    # ------------------------------------------------------------------ #
    #  Main Entry Point                                                    #
    # ------------------------------------------------------------------ #
    def _on_create_clicked(self):
        ctx = omni.usd.get_context()
        selection = ctx.get_selection().get_selected_prim_paths()
        if not selection:
            self._status_label.text = "Error: No selection."
            return
            
        stage = ctx.get_stage()
        
        # --- Gather targets ---
        targets = []
        for path in selection:
            prim = stage.GetPrimAtPath(path)
            if not prim.IsValid():
                continue
                
            target_prim = prim
            is_panel = False
            
            # Walk up max 3 levels to find Panel root (has custom:panel_type)
            for _ in range(3):
                if target_prim.GetAttribute("custom:panel_type").IsValid():
                    is_panel = True
                    break
                parent = target_prim.GetParent()
                if not parent.IsValid() or str(parent.GetPath()) == "/":
                    break
                target_prim = parent
            
            final_prim = target_prim if is_panel else prim
            targets.append((str(final_prim.GetPath()), final_prim, is_panel))
            
        if not targets:
            self._status_label.text = "Error: No valid panels or walls selected."
            return

        # Get UI values (inches)
        tap_w = self._width_model.as_float
        tap_h = self._height_model.as_float
        stub_l = self._length_model.as_float
        
        # Split into panel vs wall selections
        panel_targets = [t for t in targets if t[2]]
        wall_targets  = [t for t in targets if not t[2]]
        
        created_count = 0
        
        # --- Process Wall selections (manual offset) ---
        for path_str, prim, _ in wall_targets:
            off_x = self._x_offset_model.as_float
            off_y = self._y_offset_model.as_float
            # Tap position in Wall local space (Bottom-Center convention)
            # User provides X (along wall length), Y (up from bottom)
            # Z = 0 means at the wall surface; stub extrudes outward (+Z)
            pos = Gf.Vec3d(off_x, off_y, 0)
            self._create_tap(stage, path_str, pos, tap_w, tap_h, stub_l)
            created_count += 1

        # --- Process Panel selections (combine + filler + tap) ---
        if panel_targets:
            # Group panels by their parent Wall
            panels_by_wall = {}
            for path_str, prim, _ in panel_targets:
                wall_path_str = str(prim.GetParent().GetPath())
                if wall_path_str not in panels_by_wall:
                    panels_by_wall[wall_path_str] = []
                panels_by_wall[wall_path_str].append((path_str, prim))
                
            for wall_path_str, panels in panels_by_wall.items():
                # Calculate combined bounding box in Wall-local space
                min_x, min_y =  1e9,  1e9
                max_x, max_y = -1e9, -1e9
                thick_val = 0.0747  # default 14ga
                
                for p_path_str, p_prim in panels:
                    # Get panel translation via XformCommonAPI
                    xform_api = UsdGeom.XformCommonAPI(p_prim)
                    trans, _, _, _, _ = xform_api.GetXformVectors(Usd.TimeCode.Default())
                    
                    
                    # Read panel dimensions from attributes
                    w_attr = p_prim.GetAttribute("custom:width")
                    h_attr = p_prim.GetAttribute("custom:height")
                    
                    p_w = float(w_attr.Get() if w_attr and w_attr.IsValid() and w_attr.HasValue() else 30.0)
                    p_h = float(h_attr.Get() if h_attr and h_attr.IsValid() and h_attr.HasValue() else 30.0)
                    
                    p_t_attr = p_prim.GetAttribute("custom:thickness")
                    if p_t_attr and p_t_attr.IsValid() and p_t_attr.HasValue():
                        thick_val = float(p_t_attr.Get())
                    
                    # Panel origin convention (from _render_wall_direct):
                    #   Xform at (cumCol + w/2, cumRow, 0)
                    #   → Bottom-Center.  X is center, Y is bottom edge.
                    curr_min_x = trans[0] - p_w / 2.0
                    curr_max_x = trans[0] + p_w / 2.0
                    curr_min_y = trans[1]
                    curr_max_y = trans[1] + p_h
                    
                    min_x = min(min_x, curr_min_x)
                    max_x = max(max_x, curr_max_x)
                    min_y = min(min_y, curr_min_y)
                    max_y = max(max_y, curr_max_y)

                # Derived values
                center_x = (min_x + max_x) / 2.0
                filler_w = max_x - min_x
                filler_h = max_y - min_y
                
                # 1. Hide original panels (set to Cutout)
                for p_path_str, p_prim in panels:
                    p_prim.GetAttribute("custom:panel_type").Set("Cutout")
                    for child in p_prim.GetChildren():
                        imageable = UsdGeom.Imageable(child)
                        if imageable:
                            imageable.MakeInvisible()
                
                # 2. Create Filler Panel
                #    Matches panels.py convention:
                #    Xform at Bottom-Center: (center_x, min_y, 0)
                #    Face child at (0, H/2, T/2) with scale (W/2, H/2, T/2)
                filler_path = f"{wall_path_str}/MergedPanel_{created_count}"
                filler_xform = UsdGeom.Xform.Define(stage, filler_path)
                filler_xform.AddTranslateOp().Set(Gf.Vec3d(center_x, min_y, 0))
                
                face = UsdGeom.Cube.Define(stage, f"{filler_path}/Face")
                face.AddTranslateOp().Set(Gf.Vec3d(0, filler_h / 2.0, thick_val / 2.0))
                face.AddScaleOp().Set(Gf.Vec3d(filler_w / 2.0, filler_h / 2.0, thick_val / 2.0))
                face.CreateDisplayColorAttr([(0.65, 0.68, 0.72)])  # Match galvanized color
                _apply_galvanized_material(stage, face)
                
                # Tag filler with metadata
                filler_prim = filler_xform.GetPrim()
                filler_prim.CreateAttribute("custom:panel_type", Sdf.ValueTypeNames.String).Set("Merged")
                filler_prim.CreateAttribute("custom:width", Sdf.ValueTypeNames.Double).Set(filler_w)
                filler_prim.CreateAttribute("custom:height", Sdf.ValueTypeNames.Double).Set(filler_h)
                filler_prim.CreateAttribute("custom:thickness", Sdf.ValueTypeNames.Double).Set(thick_val)
                
                # 3. Create Tap at filler center
                #    Position: center_x horizontally, center of height vertically
                #    Z = 0 (at wall surface). Stub extrudes in +Z (outward).
                tap_center_y = min_y + filler_h / 2.0
                tap_pos = Gf.Vec3d(center_x, tap_center_y, 0)
                self._create_tap(stage, wall_path_str, tap_pos, tap_w, tap_h, stub_l)
                created_count += 1
                
        if created_count > 0:
            merged = len(panel_targets) if panel_targets else 0
            if merged > 1:
                self._status_label.text = f"Created {created_count} Tap(s), merged {merged} panels."
            else:
                self._status_label.text = f"Created {created_count} Tap(s)."

    # ------------------------------------------------------------------ #
    #  Tap Geometry Creation                                               #
    # ------------------------------------------------------------------ #
    def _create_tap(self, stage, parent_path_str, pos, w, h, l):
        """
        Creates an Exhaust Tap (Flange + Stub + Port) under parent_path_str.
        
        Coordinate convention:
          - Tap Xform is at `pos` in Wall Local Space.
          - Flange sits AT the wall surface (Z ≈ 0).
          - Stub extrudes OUTWARD in +Z direction (which Wall rotation
            maps to the correct world-space outward normal).
          - Port is at the end of the stub (+Z = +l).
        
        All dimensions in inches.
        """
        # Unique path
        base_name = "Exhaust_Tap"
        tap_path = f"{parent_path_str}/{base_name}"
        count = 1
        while stage.GetPrimAtPath(tap_path):
            tap_path = f"{parent_path_str}/{base_name}_{count}"
            count += 1

        xform = UsdGeom.Xform.Define(stage, tap_path)
        xform.AddTranslateOp().Set(pos)
        
        # 1. Flange (visual base, 1" border around opening)
        #    Centered at Z = T/2 (thin slab sitting on the wall surface)
        flange_thick = 0.125  # 1/8"
        flange = UsdGeom.Cube.Define(stage, f"{tap_path}/Flange")
        flange.AddTranslateOp().Set(Gf.Vec3d(0, 0, flange_thick / 2.0))
        flange.AddScaleOp().Set(Gf.Vec3d(w / 2.0 + 1.0, h / 2.0 + 1.0, flange_thick / 2.0))
        flange.CreateDisplayColorAttr([(0.6, 0.6, 0.65)])
        
        # 2. Stub (duct connection, extrudes outward in +Z)
        stub = UsdGeom.Cube.Define(stage, f"{tap_path}/Stub")
        stub.AddTranslateOp().Set(Gf.Vec3d(0, 0, l / 2.0))
        stub.AddScaleOp().Set(Gf.Vec3d(w / 2.0, h / 2.0, l / 2.0))
        stub.CreateDisplayColorAttr([(0.7, 0.7, 0.75)])
        
        # 3. Port (at the end of the stub, pointing outward +Z)
        Port.define(stage, tap_path, "Port_Exhaust",
            Gf.Vec3d(0, 0, l),       # Position at stub end
            Gf.Vec3d(0, 0, 1),       # Direction (outward +Z)
            port_type="Exhaust",
            shape="Rectangular",
            width=w,
            height=h
        )
