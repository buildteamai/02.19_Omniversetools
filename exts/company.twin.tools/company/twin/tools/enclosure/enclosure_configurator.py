# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Enclosure Configurator Window and Renderer.
Following TunnelModel pattern for clean separation of data, rendering, and UI.
"""

import omni.ui as ui
import omni.usd
from pxr import UsdGeom, Gf, Sdf

from .enclosure_model import EnclosureModel, GridStrategy
from .panels import instantiate_panel
from ..utils.port import Port


def render_enclosure(stage, model: EnclosureModel, root_path="/SheetMetal_Enclosure"):
    """
    Renders the EnclosureModel to the USD Stage.
    
    Coordinate System (Y-up):
    - X-Z Plane = Floor/Ground (horizontal)
    - Y = Vertical (height direction)
    - Length = X axis (tunnel length direction)
    - Width = Z axis (left-right span)
    - Height = Y axis (vertical)
    
    Generates: Left Wall, Right Wall, Roof (3 walls forming tunnel cross-section)
    
    Uses same direct placement approach as Tunnel Builder for accurate positioning.
    """
    # root_path is now passed in.
    
    # Check if we are overwriting or creating new. 
    # The caller manages uniqueness, but we ensure clean slate for this path.
    # The caller manages uniqueness, but we ensure clean slate for this path.
    current_transform = []
    from ..utils import usd_utils

    if stage.GetPrimAtPath(root_path):
        # Capture transform before removing
        prim = stage.GetPrimAtPath(root_path)
        if prim:
            current_transform = usd_utils.get_local_transform(prim)
            
        # We only remove if it's a "Rebuild" of the same object.
        # Ideally, we should just update, but for now, full rebuild is safer for data consistency.
        stage.RemovePrim(root_path)

    # Root Xform
    root_prim = stage.DefinePrim(root_path, "Xform")
    
    # Store enclosure metadata
    root_prim.CreateAttribute("custom:length", Sdf.ValueTypeNames.Double).Set(model.length)
    root_prim.CreateAttribute("custom:width", Sdf.ValueTypeNames.Double).Set(model.width)
    root_prim.CreateAttribute("custom:height", Sdf.ValueTypeNames.Double).Set(model.height)
    root_prim.CreateAttribute("custom:gauge", Sdf.ValueTypeNames.Int).Set(model.gauge)

    # Serialize full model state for reload
    model.serialize(root_prim)

    thickness = model.thickness
    flange_depth = model.flange_depth

    # --- LEFT WALL (Z = 0) ---
    # Panels face inward (+Z), arranged along X (length) and Y (height)
    left_path = f"{root_path}/Wall_Left"
    left_prim = stage.DefinePrim(left_path, "Xform")
    # Wall Left at Z=0. Normally faces +Z (Inside). 
    # Rotate 180 Y to point -Z (Outside).
    # Origin shifts to (Length, 0, 0) because Local X is inverted.
    UsdGeom.XformCommonAPI(left_prim).SetTranslate(Gf.Vec3d(model.length, 0, 0))
    UsdGeom.XformCommonAPI(left_prim).SetRotate(Gf.Vec3f(0, 180, 0))
    
    _render_wall_direct(stage, model.left, left_path, 
                        wall_type="left",
                        tunnel_length=model.length,
                        tunnel_width=model.width, 
                        tunnel_height=model.height,
                        thickness=thickness,
                        flange_depth=flange_depth,
                        gauge=model.gauge)

    # --- RIGHT WALL (Z = width) ---
    # Panels face inward (-Z). We rotate 180 Y.
    # Origin at (Length, 0, Width).
    right_path = f"{root_path}/Wall_Right"
    right_prim = stage.DefinePrim(right_path, "Xform")
    
    right_xform = UsdGeom.XformCommonAPI(right_prim)
    # Wall Right at Z=Width. Normally faces +Z (Outside).
    # No rotation needed.
    right_xform.SetTranslate(Gf.Vec3d(0, 0, model.width))
    right_xform.SetRotate(Gf.Vec3f(0, 0, 0))

    _render_wall_direct(stage, model.right, right_path,
                        wall_type="right",
                        tunnel_length=model.length,
                        tunnel_width=model.width,
                        tunnel_height=model.height,
                        thickness=thickness,
                        flange_depth=flange_depth,
                        gauge=model.gauge)

    # --- ROOF (Y = height) ---
    # Panels face downward (-Y).
    # Cols along X, Rows along Z.
    # --- ROOF (Y = height) ---
    # Panels face Up (+Y) for Outside.
    # Local Z (Thick) -> Global +Y.
    # Rot X=90: Y->-Z (Cols along Z? No, Cols along X), Z->+Y.
    # Origin needs to shift because Local Y maps to -Z.
    # --- ROOF (Y = height) ---
    # Panels face Up (+Y) for Outside.
    # Local Z (Thick) -> Global +Y (Out).
    # Rot X=90: Y->Z, Z->-Y. (Down/In).
    # Rot X=-90: Y->-Z, Z->+Y. (Up/Out).
    # Start: (0, H, W).
    # Cols (Local X) -> +X. (Along Length).
    # Rows (Local Y) -> -Z. (From W -> 0).
    roof_path = f"{root_path}/Wall_Roof"
    roof_prim = stage.DefinePrim(roof_path, "Xform")
    
    roof_xform = UsdGeom.XformCommonAPI(roof_prim)
    roof_xform.SetTranslate(Gf.Vec3d(0, model.height, model.width))
    roof_xform.SetRotate(Gf.Vec3f(-90, 0, 0))
    
    _render_wall_direct(stage, model.top, roof_path,
                        wall_type="roof",
                        tunnel_length=model.length,
                        tunnel_width=model.width,
                        tunnel_height=model.height,
                        thickness=thickness,
                        flange_depth=flange_depth,
                        gauge=model.gauge)

    if model.has_entry_wall:
        # --- ENTRY WALL (Back) ---
        # At X=0, spanning Width (Z) x Height (Y).
        # Thickness inward (+X). Rotate Y=+90: X->Z, Z->X? No.
        # Start at (0, 0, Width). Rotate Y=90 (Counter Clockwise around Y).
        # Local X (Cols) -> -Z (Along Width 0 to -W... wait).
        # If we want Cols to run along Z (0 to Width), we need specific rotation.
        # Local X (width) needs to map to Global Z (width).
        # Local Y (height) needs to map to Global Y (height).
        # Local Z (thick) needs to map to Global X (Length).
        
        # Rot Y=90: X->Z, Z->-X? No, R(90) = [[0,0,1],[0,1,0],[-1,0,0]]
        # X(1,0,0) -> (0,0,-1) = -Z.
        # Z(0,0,1) -> (1,0,0) = +X.
        # So Local X goes to -Z. Wall width is model.width.
        # If we start at (0,0,W), and go -Z, we go to (0,0,0). Correct span.
        # Local Z goes to +X. This is inward for Entry Wall (at X=0). Correct.
        # Local Z (Thick) -> +X (Inward).
        # --- ENTRY WALL (Back) ---
        # At X=0. Face -X (Outside).
        # Rot Y=-90: Z->-X. X->Z.
        # Local X (Cols) -> +Z. (0..Width).
        back_path = f"{root_path}/Wall_Entry"
        back_prim = stage.DefinePrim(back_path, "Xform")
        
        back_xform = UsdGeom.XformCommonAPI(back_prim)
        back_xform.SetTranslate(Gf.Vec3d(0, 0, 0))
        back_xform.SetRotate(Gf.Vec3f(0, -90, 0))

        _render_wall_direct(stage, model.back, back_path, "back",
                            model.length, model.width, model.height,
                            thickness, flange_depth, gauge=model.gauge,
                            opening_w=model.opening_width, opening_h=model.opening_height)

    if model.has_exit_wall:
        # --- EXIT WALL (Front) ---
        # At X=Length, spanning Width (Z) x Height (Y)
        # Thickness inward (-X).
        # Translate (Length, 0, 0). Rotate Y=-90.
        # Rot Y=-90: X->-Z, Z->+X.
        # X(1,0,0) -> (0,0,1) = +Z.
        # Z(0,0,1) -> (-1,0,0) = -X.
        # Local X (Cols) -> +Z. Wall width is model.width.
        # If we start at (Length, 0, 0) and go +Z, we go to (Length, 0, Width). Correct span.
        # Local Z (Thick) -> -X. This is inward for Exit Wall (at X=Length). Correct.
        # --- EXIT WALL (Front) ---
        # At X=Length. Face +X (Outside).
        # Rot Y=90: Z->+X. X->-Z.
        # Local X (Cols) -> -Z. (Width..0).
        # Start at (Length, 0, Width).
        front_path = f"{root_path}/Wall_Exit"
        front_prim = stage.DefinePrim(front_path, "Xform")
        
        front_xform = UsdGeom.XformCommonAPI(front_prim)
        front_xform.SetTranslate(Gf.Vec3d(model.length, 0, model.width))
        front_xform.SetRotate(Gf.Vec3f(0, 90, 0))

        _render_wall_direct(stage, model.front, front_path, "front",
                            model.length, model.width, model.height,
                            thickness, flange_depth, gauge=model.gauge,
                            opening_w=model.opening_width, opening_h=model.opening_height)

    if model.has_floor:
        # --- FLOOR (Bottom) ---
        # At Y=0, spanning Length (X) x Width (Z)
        # Thickness Down (-Y).
        # Rotate X=90.
        # --- FLOOR (Bottom) ---
        # At Y=0. Face -Y (Outside/Down).
        # Rot X=-90: Z->-Y. Y->Z.
        # --- FLOOR (Bottom) ---
        # At Y=0. Face -Y (Outside/Down).
        # Rot X=90: Y->Z, Z->-Y. (Down/Out).
        # Start: (0, 0, 0).
        # Cols (Local X) -> +X.
        # Rows (Local Y) -> +Z. (0..W).
        floor_path = f"{root_path}/Floor"
        floor_prim = stage.DefinePrim(floor_path, "Xform")
        
        floor_xform = UsdGeom.XformCommonAPI(floor_prim)
        floor_xform.SetTranslate(Gf.Vec3d(0, 0, 0))
        floor_xform.SetRotate(Gf.Vec3f(90, 0, 0))
        
        _render_wall_direct(stage, model.bottom, floor_path, "floor",
                            model.length, model.width, model.height,
                            thickness, flange_depth, gauge=model.gauge)

    # --- ENTRY ANCHOR (Floor Center at Entry) ---
    if model.has_entry_wall:
        Port.define(stage, root_path, "Anchor_Entry",
            Gf.Vec3d(0, 0, model.width / 2.0),
            Gf.Vec3d(-1, 0, 0), # Pointing Outward (-X)
            port_type="Entry",
            shape="Rectangular",
            width=model.opening_width,
            height=model.opening_height
        )
        # Add custom is_anchor tag
        prim = stage.GetPrimAtPath(f"{root_path}/Anchor_Entry")
        if prim:
            prim.CreateAttribute("custom:is_anchor", Sdf.ValueTypeNames.Bool).Set(True)

    # --- EXIT ANCHOR (Floor Center at Exit) ---
    if model.has_exit_wall:
        Port.define(stage, root_path, "Anchor_Exit",
            Gf.Vec3d(model.length, 0, model.width / 2.0),
            Gf.Vec3d(1, 0, 0), # Pointing Outward (+X)
            port_type="Exit",
            shape="Rectangular",
            width=model.opening_width,
            height=model.opening_height
        )
        # Add custom is_anchor tag
        prim = stage.GetPrimAtPath(f"{root_path}/Anchor_Exit")
        if prim:
            prim.CreateAttribute("custom:is_anchor", Sdf.ValueTypeNames.Bool).Set(True)

    # --- PORTS ---
    # Add a default Exhaust Port on the Roof Center (for testing)
    Port.define(stage, root_path, "Port_Roof_Exhaust",
        Gf.Vec3d(model.length / 2.0, model.height, model.width / 2.0),
        Gf.Vec3d(0, 1, 0), # Up
        port_type="HVAC",
        shape="Rectangular",
        width=12.0, # Standard 12x12
        height=12.0
    )

    # Restore Transform
    if current_transform:
        root_prim = stage.GetPrimAtPath(root_path)
        if root_prim:
            usd_utils.set_local_transform(root_prim, current_transform)

    print(f"[EnclosureConfigurator] Rendered Enclosure at {root_path}")


    print(f"[EnclosureConfigurator] Rendered Enclosure at {root_path}")


    # We can infer from the root prim attributes if needed, or pass them in.
    # For now, let's assume the wall object *could* carry this info, 
    # but currently it doesn't. 
    # Let's Modify the signature or pass 'model' instead of unpacking everything.
    # BUT, to be minimally invasive, let's fetch from the root prim we just created/updated?
    # No, that's slow. 
    # The clean way is to pass opening dims to this function.
    # Since I cannot easily change all calls without refactoring render_enclosure above, 
    # I'll rely on a small trick: The wall object is part of the model. 
    # Does 'wall' have parent access? No.
    
    # REFACTOR: Let's assume standard opening dims for now unless I update render_enclosure to pass them.
    # I will update render_enclosure to pass a context dict or similar? 
    # Or just use the attributes I just set on the Root Prim? 
    # Actually, I am writing _render_wall_direct below.
    # Let's update the call sites in render_enclosure first? 
    # No, I can't easily do that with replacement chunks.
    
    # BETTER PLAN: Update render_enclosure calls to pass 'model' or opening dims.
    # But since I am editing the file anyway, I can change the signature.
    # I will assume `opening_w` and `opening_h` are passed as kwargs or similar.
    pass

def _render_wall_direct(stage, wall, parent_path, wall_type, tunnel_length, tunnel_width, tunnel_height, thickness, flange_depth, gauge=16, opening_w=0, opening_h=0):
    """
    Renders a wall using direct panel placement.
    """
    def get_cumulative_pos(sizes, index):
        return sum(sizes[:index])
    
    # Extract column widths and row heights
    col_widths = [col[0].width for col in wall.columns if col]
    if not col_widths:
        return
        
    # Get row heights from first column
    row_heights = [p.height for p in wall.columns[0]] if wall.columns else []
    
    for row_idx, row_height in enumerate(row_heights):
        cumulative_row_pos = get_cumulative_pos(row_heights, row_idx)
        
        for col_idx, col_width in enumerate(col_widths):
            cumulative_col_pos = get_cumulative_pos(col_widths, col_idx)
            
            # Get panel from model
            panel = wall.columns[col_idx][row_idx] if col_idx < len(wall.columns) and row_idx < len(wall.columns[col_idx]) else None
            if not panel:
                continue
                
            panel_path = f"{parent_path}/Panel_{col_idx}_{row_idx}"
            
            # --- PANEL OMISSION LOGIC ---
            # If this is an Entry/Exit wall and we have an opening defined
            should_skip = False
            try:
                # Ensure opening dims are valid floats
                op_w = float(opening_w) if opening_w is not None else 0.0
                op_h = float(opening_h) if opening_h is not None else 0.0
                
                if (wall_type in ["back", "front"]) and (op_w > 0.1 and op_h > 0.1):
                    # Panel Bounds in Wall Space (X=Width, Y=Height)
                    p_y_min = cumulative_row_pos
                    p_y_max = cumulative_row_pos + panel.height
                    
                    p_x_min = cumulative_col_pos
                    p_x_max = cumulative_col_pos + panel.width
                    
                    # Opening Bounds (Centered on Wall Width, Bottom Aligned at Y=0)
                    wall_width_total = tunnel_width
                    if wall_type in ["back"]:
                         # Back Wall runs 0..Width or Width..0?
                         # Our logic above says Back Wall X maps to Global -Z.
                         # Start (0,0,W) -> End (0,0,0).
                         # So Panel X=0 is Global Z=W. Panel X=W is Global Z=0.
                         # This reversal might matter if Opening is asymmetric. 
                         # But Opening is centered, so it's fine.
                         pass

                    op_x_center = wall_width_total / 2.0
                    op_x_min = op_x_center - (op_w / 2.0)
                    op_x_max = op_x_center + (op_w / 2.0)
                    
                    op_y_min = 0.0
                    op_y_max = op_h
                    
                    # Check Intersection
                    intersect_x = max(0, min(p_x_max, op_x_max) - max(p_x_min, op_x_min))
                    intersect_y = max(0, min(p_y_max, op_y_max) - max(p_y_min, op_y_min))
                    
                    intersection_area = intersect_x * intersect_y
                    panel_area = panel.width * panel.height
                    
                    # Omission Threshold: If significant intersection
                    if intersection_area > (panel_area * 0.15):
                        should_skip = True
            except Exception as e:
                print(f"[EnclosureConfigurator] Error in omission logic: {e}")
                should_skip = False # Default to showing panel if check fails

            if should_skip:
                continue

            # Instantiate panel geometry
            instantiate_panel(
                stage,
                panel_path,
                panel.width,
                panel.height,
                thickness,
                panel.type,
                panel.variant_params,
                flange_depth,
                gauge=getattr(wall, 'gauge', 16) # Fallback if wall doesn't have it, but usually model has it
            )
            
            # Position based on wall type
            prim = stage.GetPrimAtPath(panel_path)
            if not prim.IsValid():
                continue
                
            xform_api = UsdGeom.XformCommonAPI(prim)
            
            # Position Panel in Wall Space (2D)
            # Origin of Panel Geometry is Bottom-Center-Back of the panel volume.
            # X: cumulative_col_pos is left edge. Panel origin is Center X.
            # Y: cumulative_row_pos is bottom edge. Panel origin is Bottom Y.
            
            p_x = cumulative_col_pos + (panel.width / 2.0)
            p_y = cumulative_row_pos
            p_z = 0.0
            
            xform_api.SetTranslate(Gf.Vec3d(p_x, p_y, p_z))


class EnclosureConfiguratorWindow(ui.Window):
    """
    UI Window for configuring Sheet Metal Enclosures.
    """
    def __init__(self, title="Enclosure Configurator", **kwargs):
        super().__init__(title, width=450, height=600, **kwargs)
        
        self._model = EnclosureModel()
        
        # Dimension Models (Ft/In)
        self._length_ft = ui.SimpleIntModel(5)
        self._length_in = ui.SimpleFloatModel(0.0)
        
        self._width_ft = ui.SimpleIntModel(5)
        self._width_in = ui.SimpleFloatModel(0.0)
        
        self._height_ft = ui.SimpleIntModel(6)
        self._height_in = ui.SimpleFloatModel(0.0)
        
        # Gauge
        self._gauge_combo = None
        
        # Panel Properties
        self._panel_width_model = ui.SimpleFloatModel(30.0)
        self._panel_depth_model = ui.SimpleFloatModel(1.5)
        
        # Wall Options
        self._entry_wall_model = ui.SimpleBoolModel(False)
        self._exit_wall_model = ui.SimpleBoolModel(False)
        self._exit_wall_model = ui.SimpleBoolModel(False)
        self._floor_model = ui.SimpleBoolModel(False)
        
        # Openings
        self._opening_w_model = ui.SimpleFloatModel(0.0)
        self._opening_h_model = ui.SimpleFloatModel(0.0)
        
        # Grid Strategy
        self._strategy_combo = None
        
        # Variant Selection
        self._variant_combo = None
        
        # Window Parameters
        self._win_w_model = ui.SimpleFloatModel(24.0)
        self._win_h_model = ui.SimpleFloatModel(24.0)
        self._win_y_model = ui.SimpleFloatModel(36.0)
        
        # Name
        self._name_model = ui.SimpleStringModel("Enclosure")

        self.frame.set_build_fn(self._build_ui)

    def _build_ui(self):
        with ui.VStack(spacing=8, style={"margin": 10}):
            # Header
            ui.Label("Sheet Metal Enclosure Configurator", style={"font_size": 18, "color": 0xFF00B4FF})
            ui.Line(height=2, style={"color": 0xFF333333})

            # Name Section
            with ui.HStack(height=22):
                ui.Label("Name:", width=100)
                ui.StringField(model=self._name_model)
            
            # --- Dimensions Section ---
            ui.Label("Dimensions", style={"font_size": 14, "color": 0xFFAAAAAA})
            
            def add_dim_row(label, ft_model, in_model):
                with ui.HStack(height=22):
                    ui.Label(label, width=100)
                    ui.IntField(model=ft_model, width=50)
                    ui.Label("ft", width=20)
                    ui.Spacer(width=5)
                    ui.FloatField(model=in_model, width=60)
                    ui.Label("in", width=20)
            
            add_dim_row("Width (X):", self._length_ft, self._length_in)
            add_dim_row("Length (Z):", self._width_ft, self._width_in)
            add_dim_row("Height (Y):", self._height_ft, self._height_in)

            
            # Gauge Selection
            ui.Spacer(height=5)
            with ui.HStack(height=22):
                ui.Label("Gauge:", width=100)
                self._gauge_combo = ui.ComboBox(3, "10ga", "12ga", "14ga", "16ga", "18ga")
            
                
            # Panel Width (Only for Equal Strategy)
            with ui.HStack(height=22):
                ui.Label("Panel Width:", width=100)
                ui.FloatField(model=self._panel_width_model, width=60)
                ui.Label("in (Equal Mode)", width=100)
                
            # Grid Strategy
            with ui.HStack(height=22):
                ui.Label("Grid Strategy:", width=100)
                self._strategy_combo = ui.ComboBox(0, "Equal Spacing", "Fabrication (Max 48\")")

            # Panel Depth
            with ui.HStack(height=22):
                ui.Label("Panel Depth:", width=100)
                ui.FloatField(model=self._panel_depth_model, width=60)
                ui.Label("in", width=20)

            # --- Options Section ---
            ui.Spacer(height=10)
            ui.Label("Options", style={"font_size": 14, "color": 0xFFAAAAAA})
            with ui.HStack(height=22):
                ui.Label("Entry Wall:", width=80)
                ui.CheckBox(model=self._entry_wall_model)
                ui.Spacer(width=20)
                ui.Label("Exit Wall:", width=80)
                ui.CheckBox(model=self._exit_wall_model)
                ui.Spacer(width=20)
                ui.Label("Floor:", width=60)
                ui.CheckBox(model=self._floor_model)
                ui.Spacer(width=20)
                ui.Label("Floor:", width=60)
                ui.CheckBox(model=self._floor_model)
            
            # Opening Dimensions
            with ui.HStack(height=22):
                ui.Label("Opening W:", width=80)
                ui.FloatField(model=self._opening_w_model, width=50)
                ui.Spacer(width=10)
                ui.Label("H:", width=20)
                ui.FloatField(model=self._opening_h_model, width=50)
            ui.Button("Build Enclosure", height=35, clicked_fn=self._on_build_clicked,
                     style={"background_color": 0xFF2B5B2B})
            
            with ui.HStack(height=30):
                ui.Button("Load from Selection", clicked_fn=self._on_load_clicked)
                ui.Spacer(width=10)
                ui.Button("Add Exhaust Tap", clicked_fn=self._on_tap_tool_clicked)
            
            # --- Panel Properties Section ---
            ui.Spacer(height=10)
            ui.Line(height=2, style={"color": 0xFF333333})
            ui.Label("Panel Properties (Select Panel First)", style={"font_size": 14, "color": 0xFFAAAAAA})
            
            with ui.HStack(height=22):
                ui.Label("Variant:", width=100)
                self._variant_combo = ui.ComboBox(0, "Solid", "Window", "Louver", "Door", "AccessPanel")
            
            # Variant Parameters (shared/contextual)
            ui.Label("Variant Settings:", style={"font_size": 12, "color": 0xFF888888})
            with ui.HStack(height=22):
                ui.Label("  W:", width=30)
                ui.FloatField(model=self._win_w_model, width=50)
                ui.Label("H:", width=20)
                ui.FloatField(model=self._win_h_model, width=50)
                ui.Label("Y:", width=20)
                ui.FloatField(model=self._win_y_model, width=50)
            
            ui.Spacer(height=5)
            ui.Button("Apply to Selected Panels", height=30, clicked_fn=self._on_apply_variant_clicked)
            
            # Status
            ui.Spacer(height=10)
            self._status_label = ui.Label("Ready.", style={"color": 0xFF888888})

    def _on_build_clicked(self):
        """
        Builds the enclosure from scratch.
        """
        stage = omni.usd.get_context().get_stage()
        if not stage:
            self._status_label.text = "No stage available!"
            return
        
        # Convert Ft/In to total Inches
        length = (self._length_ft.get_value_as_int() * 12.0) + self._length_in.get_value_as_float()
        width = (self._width_ft.get_value_as_int() * 12.0) + self._width_in.get_value_as_float()
        height = (self._height_ft.get_value_as_int() * 12.0) + self._height_in.get_value_as_float()
        
        # Gauge
        gauge_map = [10, 12, 14, 16, 18]
        gauge_idx = self._gauge_combo.model.get_item_value_model().as_int
        gauge = gauge_map[gauge_idx]
        
        panel_width = self._panel_width_model.get_value_as_float()
        panel_depth = self._panel_depth_model.get_value_as_float()
        
        # Update Model
        self._model = EnclosureModel(length, width, height, panel_depth)
        self._model.set_gauge(gauge)
        
        self._model.has_entry_wall = self._entry_wall_model.get_value_as_bool()
        self._model.has_exit_wall = self._exit_wall_model.get_value_as_bool()
        self._model.has_floor = self._floor_model.get_value_as_bool()
        
        self._model.opening_width = self._opening_w_model.get_value_as_float()
        self._model.opening_height = self._opening_h_model.get_value_as_float()
        
        # Grid Strategy
        strategy_idx = self._strategy_combo.model.get_item_value_model().as_int
        strategy = GridStrategy.FABRICATION if strategy_idx == 1 else GridStrategy.EQUAL

        # Initialize walls
        self._model.initialize_default(panel_width, strategy)
        
        # Render
        # Construct Root Path based on Name
        name_raw = self._name_model.get_value_as_string()
        safe_name = "".join(x for x in name_raw if x.isalnum() or x in "_-")
        if not safe_name:
            safe_name = "Enclosure"
            
        # Unique Path Logic?
        # If user types "Enclosure", they expect to update "Enclosure".
        # If they type "Enclosure_02", they get a new one.
        # We'll allow explicit overwrites.
        # But we should probably check if it exists and we haven't touched it?
        # For now, simplistic "User controls the name" approach.
        
        # Ensure it starts with /World if not absolute (standard practice)
        # But Enclosure tool historically used /SheetMetal_Enclosure (root level).
        # Let's pivot to /World/<Name> for cleaner scene org, OR keep root level.
        # Users asking for "Multiple" implies scene organization.
        # Let's try /World/<Name> but fallback to /<Name> if preferred.
        # Creating at Root Level is often annoying. Let's default to /World/Name
        
        root_path = f"/World/{safe_name}"
        
        # Check if we should auto-increment to avoid accidental overwrite?
        # User request: "add multiple enclosures".
        # If I leave it as overwrite, user must manually rename.
        # Let's check existence. If exists, maybe warn? Or just overwrite?
        # "Configurator" implies "Configure this thing".
        # Let's use the explicit name. Use creates "Enclosure A", then changes name to "Enclosure B".
        
        render_enclosure(stage, self._model, root_path=root_path)
        
        self._status_label.text = f"Built Enclosure: {length}\" x {width}\" x {height}\" ({gauge}ga)"

    def _on_apply_variant_clicked(self):
        """
        Applies the selected variant to the currently selected panels.
        """
        import re
        
        ctx = omni.usd.get_context()
        selection = ctx.get_selection().get_selected_prim_paths()
        
        if not selection:
            self._status_label.text = "No panels selected."
            return
        
        stage = ctx.get_stage()
        
        # Get variant type
        idx = self._variant_combo.model.get_item_value_model().as_int
        v_type = ["Solid", "Window", "Louver", "Door", "AccessPanel"][idx]
        
        v_params = {}
        if v_type in ["Window", "Louver", "AccessPanel"]:
            # Reusing win_ fields for access panel / louver generic dims
            v_params = {
                "win_width": self._win_w_model.get_value_as_float(),
                "win_height": self._win_h_model.get_value_as_float(),
                "win_y": self._win_y_model.get_value_as_float(),
                "ap_width": self._win_w_model.get_value_as_float(),
                "ap_height": self._win_h_model.get_value_as_float(),
                "ap_y": self._win_y_model.get_value_as_float()
            }
        elif v_type == "Door":
             v_params = {
                "door_width": self._win_w_model.get_value_as_float(),
                "door_height": self._win_h_model.get_value_as_float()
            }
        
        updates = 0
        root_paths_touched = set()
        
        for path in selection:
            # We enforce that we only edit Enclosures created by this tool or compatible
            # This check was: if "/SheetMetal_Enclosure/" not in path:
            # Now we must be more flexible. 
            pass # Remove the hard check, relying on structure matching logic below
            
            if "Panel_" not in path:
                continue
            
            # Parse Panel_{col}_{row} or Floor/Panel_{col}_{row}
            match = re.search(r"(?:Wall_(\w+)|Floor)/Panel_(\d+)_(\d+)", path)
            if not match:
                continue
            
            wall_name_raw = match.group(1) if match.group(1) else "Floor"
            col_idx = int(match.group(2))
            row_idx = int(match.group(3))
            
            # Map rendered wall names to model wall names
            wall_name_map = {
                "Left": "Left",
                "Right": "Right",
                "Roof": "Top",
                "Entry": "Back",
                "Exit": "Front",
                "Floor": "Bottom"
            }
            wall_name = wall_name_map.get(wall_name_raw, wall_name_raw)
            
            wall = self._model.get_wall_by_name(wall_name)
            if wall:
                wall.set_panel_type(col_idx, row_idx, v_type, v_params)
                updates += 1
                
                # Identify root path for this panel
                # path is like /World/Enclosure/Wall_Left/Panel...
                # split by Wall_ or Floor
                if "Wall_" in path:
                    root = path.split("/Wall_")[0]
                else:
                    root = path.split("/Floor")[0]
                root_paths_touched.add(root)
        
        if updates > 0:
            # Re-render all touched enclosures
            for root_path in root_paths_touched:
                render_enclosure(stage, self._model, root_path=root_path)
            self._status_label.text = f"Updated {updates} panel(s) in {len(root_paths_touched)} enclosure(s)."
        else:
            self._status_label.text = "No valid enclosure panels found in selection."

    def _on_load_clicked(self):
        """
        Loads the enclosure model from the selected prim.
        """
        ctx = omni.usd.get_context()
        selection = ctx.get_selection().get_selected_prim_paths()
        if not selection:
            self._status_label.text = "Select an Enclosure Root to load."
            return

        stage = ctx.get_stage()
        prim = stage.GetPrimAtPath(selection[0])
        
        if not prim.IsValid():
            return

        # Try to load
        if self._model.deserialize(prim):
            self._status_label.text = f"Loaded {prim.GetName()}"
            self._update_ui_from_model()
            
            # Update Name field to match loaded prim
            self._name_model.set_value(prim.GetName())
        else:
            self._status_label.text = "Failed to load Enclosure (Missing attributes?)"

    def _update_ui_from_model(self):
        """
        Updates UI widgets to match current model state.
        """
        # Dimensions
        self._length_ft.set_value(int(self._model.length // 12))
        self._length_in.set_value(self._model.length % 12)
        
        self._width_ft.set_value(int(self._model.width // 12))
        self._width_in.set_value(self._model.width % 12)
        
        self._height_ft.set_value(int(self._model.height // 12))
        self._height_in.set_value(self._model.height % 12)
        
        # Gauge
        gauge_map = [10, 12, 14, 16, 18]
        if self._model.gauge in gauge_map:
            idx = gauge_map.index(self._model.gauge)
            self._gauge_combo.model.get_item_value_model().as_int = idx
            
        # Options
        self._entry_wall_model.set_value(self._model.has_entry_wall)
        self._exit_wall_model.set_value(self._model.has_exit_wall)
        self._floor_model.set_value(self._model.has_floor)
        
        self._opening_w_model.set_value(self._model.opening_width)
        self._opening_h_model.set_value(self._model.opening_height)
        
        # Grid Strategy
        if self._model.grid_strategy == GridStrategy.FABRICATION:
            self._strategy_combo.model.get_item_value_model().as_int = 1
        else:
            self._strategy_combo.model.get_item_value_model().as_int = 0

    def _on_tap_tool_clicked(self):
        """
        Launches the Tap Tool Window.
        """
        # Lazy import to avoid circular dependency if any
        from .tap_window import TapWindow
        
        # We need to keep a reference to prevent garbage collection
        if not hasattr(self, "_tap_window"):
            self._tap_window = None
            
        if not self._tap_window:
            self._tap_window = TapWindow()
            
        self._tap_window.visible = True
