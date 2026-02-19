# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Steel Connection Window

UI for creating AISC-compliant steel connections between members.
"""

import omni.ui as ui
from pxr import Usd, UsdGeom, Gf, Sdf
import omni.usd
import json

from ..steel.connection_rules import (
    ConnectionType,
    MemberType,
    ConnectionSurface,
    get_connection_rules
)
from ..steel.shear_tab import ShearTabGenerator
from ..steel.double_angle import DoubleAngleGenerator


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


def _parse_custom_data(prim, key, default=None):
    """Safely parses USD custom data that may be JSON string or dict."""
    value = prim.GetCustomDataByKey(key)
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return value if isinstance(value, dict) else default


class SteelConnectionWindow(ui.Window):
    """
    Window for creating steel beam connections.
    
    Features:
    - Select two steel members
    - Auto-detect compatible connection types
    - Configure connection parameters
    - Preview and create connection geometry
    """
    
    def __init__(self, title: str = "Steel Connection"):
        super().__init__(title, width=400, height=550)
        self.frame.set_build_fn(self._build_ui)
        
        # Connection type options
        self._connection_types = ["Shear Tab", "Double Angle", "End Plate", "Through Plate"]
        self._connection_type_index = ui.SimpleIntModel(0)
        
        # Bolt options
        self._bolt_grades = ["A307", "A325", "A490"]
        self._bolt_grade_index = ui.SimpleIntModel(1)  # Default A325
        
        self._bolt_sizes = ["5/8\"", "3/4\"", "7/8\"", "1\""]
        self._bolt_diameters = [0.625, 0.75, 0.875, 1.0]
        self._bolt_size_index = ui.SimpleIntModel(2)  # Default 7/8"
        
        # Models (must be stored to prevent GC)
        self._conn_model = None
        self._grade_model = None
        self._size_model = None
        
        # Parameters
        self._bolt_count = ui.SimpleIntModel(4)
        self._bolt_spacing = ui.SimpleFloatModel(3.0)
        self._plate_thickness = ui.SimpleFloatModel(0.5)
        self._shear_demand = ui.SimpleFloatModel(30.0)
        
        # Selection state
        self._beam_a_path = None
        self._beam_b_path = None
        
        # Rules engine
        self._rules = get_connection_rules()
    
    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=6):
                ui.Spacer(height=4)
                
                # ===== Member Selection =====
                with ui.CollapsableFrame("Member Selection", height=0):
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=24):
                            ui.Label("Beam A:", width=100)
                            self._beam_a_label = ui.Label("(Select in viewport)", style={"color": 0xFFAAAAAA})
                        
                        with ui.HStack(height=24):
                            ui.Label("Beam B:", width=100)
                            self._beam_b_label = ui.Label("(Select in viewport)", style={"color": 0xFFAAAAAA})
                        
                        ui.Spacer(height=4)
                        with ui.HStack(height=28):
                            ui.Button("Load Selection", clicked_fn=self._on_load_selection,
                                     tooltip="Load the first two selected prims as Beam A and B")
                            ui.Button("Clear", clicked_fn=self._on_clear_selection, width=60)
                
                # ===== Connection Type =====
                with ui.CollapsableFrame("Connection Type", height=0):
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=24):
                            ui.Label("Type:", width=100)
                            self._conn_model = ComboModel(self._connection_types)
                            self._conn_model.get_item_value_model(None, 0).as_int = self._connection_type_index.as_int
                            ui.ComboBox(self._conn_model, width=180).model.add_item_changed_fn(
                                lambda m, i: setattr(self._connection_type_index, 'as_int', m.get_item_value_model(None, 0).as_int)
                            )
                        
                        self._compatibility_label = ui.Label("", style={"color": 0xFF88FF88})
                
                # ===== Bolt Configuration =====
                with ui.CollapsableFrame("Bolt Configuration", height=0):
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=24):
                            ui.Label("Grade:", width=100)
                            self._grade_model = ComboModel(self._bolt_grades)
                            self._grade_model.get_item_value_model(None, 0).as_int = self._bolt_grade_index.as_int
                            ui.ComboBox(self._grade_model, width=120).model.add_item_changed_fn(
                                lambda m, i: setattr(self._bolt_grade_index, 'as_int', m.get_item_value_model(None, 0).as_int)
                            )
                        
                        with ui.HStack(height=24):
                            ui.Label("Diameter:", width=100)
                            self._size_model = ComboModel(self._bolt_sizes)
                            self._size_model.get_item_value_model(None, 0).as_int = self._bolt_size_index.as_int
                            ui.ComboBox(self._size_model, width=120).model.add_item_changed_fn(
                                lambda m, i: setattr(self._bolt_size_index, 'as_int', m.get_item_value_model(None, 0).as_int)
                            )
                        
                        with ui.HStack(height=24):
                            ui.Label("Count:", width=100)
                            ui.IntSlider(self._bolt_count, min=2, max=12, width=120)
                            ui.Label("  bolts", width=50)
                        
                        with ui.HStack(height=24):
                            ui.Label("Spacing:", width=100)
                            ui.FloatSlider(self._bolt_spacing, min=2.5, max=4.0, width=120)
                            ui.Label("  in", width=50)
                
                # ===== Plate Configuration =====
                with ui.CollapsableFrame("Plate Configuration", height=0):
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=24):
                            ui.Label("Thickness:", width=100)
                            ui.FloatSlider(self._plate_thickness, min=0.25, max=1.0, width=120)
                            ui.Label("  in", width=50)
                        
                        with ui.HStack(height=24):
                            ui.Label("Shear Demand:", width=100)
                            ui.FloatSlider(self._shear_demand, min=10.0, max=100.0, width=120)
                            ui.Label("  kips", width=50)
                        
                        ui.Spacer(height=4)
                        ui.Button("Auto-Size", clicked_fn=self._on_auto_size, height=28,
                                 tooltip="Calculate bolt count and plate thickness from shear demand")
                
                # ===== Design Summary =====
                with ui.CollapsableFrame("Design Summary", height=0, collapsed=True):
                    with ui.VStack(spacing=2):
                        self._summary_label = ui.Label("Click 'Auto-Size' or 'Preview' to see design summary",
                                                       word_wrap=True, style={"color": 0xFFCCCCCC})
                
                ui.Spacer(height=8)
                
                # ===== Action Buttons =====
                with ui.HStack(height=36, spacing=8):
                    ui.Spacer(width=20)
                    ui.Button("Preview", clicked_fn=self._on_preview, width=100,
                             style={"Button": {"background_color": 0xFF4488AA}})
                    ui.Button("Create Connection", clicked_fn=self._on_create_connection, width=140,
                             style={"Button": {"background_color": 0xFF44AA44}})
                    ui.Spacer(width=20)
                
                ui.Spacer()
    
    def _on_load_selection(self):
        """Loads the current viewport selection as Beam A and B."""
        stage = omni.usd.get_context().get_stage()
        selection = omni.usd.get_context().get_selection()
        paths = selection.get_selected_prim_paths()
        
        if len(paths) >= 2:
            self._beam_a_path = paths[0]
            self._beam_b_path = paths[1]
            
            # Get prim names for display
            prim_a = stage.GetPrimAtPath(self._beam_a_path)
            prim_b = stage.GetPrimAtPath(self._beam_b_path)
            
            self._beam_a_label.text = prim_a.GetName() if prim_a.IsValid() else str(paths[0])
            self._beam_b_label.text = prim_b.GetName() if prim_b.IsValid() else str(paths[1])
            
            # Check member types and suggest connections
            self._check_compatibility(prim_a, prim_b)
        elif len(paths) == 1:
            self._beam_a_path = paths[0]
            prim_a = stage.GetPrimAtPath(self._beam_a_path)
            self._beam_a_label.text = prim_a.GetName() if prim_a.IsValid() else str(paths[0])
            self._beam_b_label.text = "(Select second member)"
            self._compatibility_label.text = "Select second member"
        else:
            self._beam_a_label.text = "(Select two members in viewport)"
            self._beam_b_label.text = ""
            self._compatibility_label.text = ""
    
    def _on_clear_selection(self):
        """Clears the selection."""
        self._beam_a_path = None
        self._beam_b_path = None
        self._beam_a_label.text = "(Select in viewport)"
        self._beam_b_label.text = "(Select in viewport)"
        self._compatibility_label.text = ""
    
    def _check_compatibility(self, prim_a, prim_b):
        """Checks what connection types are valid for the selected members."""
        # Get member types from metadata
        type_a = prim_a.GetCustomDataByKey('memberType') or "W"
        type_b = prim_b.GetCustomDataByKey('memberType') or "W"
        
        # Map to enum
        member_type_a = MemberType.WIDE_FLANGE
        if type_a == "C":
            member_type_a = MemberType.CHANNEL
        elif "HSS" in type_a:
            member_type_a = MemberType.HSS_RECT
        
        member_type_b = MemberType.WIDE_FLANGE
        if type_b == "C":
            member_type_b = MemberType.CHANNEL
        elif "HSS" in type_b:
            member_type_b = MemberType.HSS_RECT
        
        # Get compatible connections
        compatible = self._rules.get_compatible_connections(
            member_type_a, ConnectionSurface.WEB,
            member_type_b, ConnectionSurface.WEB
        )
        
        if compatible:
            names = [c.value.replace("_", " ").title() for c in compatible]
            self._compatibility_label.text = f"Compatible: {', '.join(names)}"
            self._compatibility_label.style = {"color": 0xFF88FF88}
        else:
            self._compatibility_label.text = "Default: Shear Tab"
            self._compatibility_label.style = {"color": 0xFFFFFF88}
    
    def _on_auto_size(self):
        """Auto-calculates connection parameters from shear demand."""
        shear = self._shear_demand.as_float
        bolt_dia = self._bolt_diameters[self._bolt_size_index.as_int]
        bolt_grade = self._bolt_grades[self._bolt_grade_index.as_int]
        
        # Get beam depth from selection
        beam_depth = 12.0  # Default
        if self._beam_a_path:
            stage = omni.usd.get_context().get_stage()
            prim = stage.GetPrimAtPath(self._beam_a_path)
            if prim.IsValid():
                aisc = _parse_custom_data(prim, 'aisc_data', {})
                if aisc:
                    beam_depth = aisc.get('depth_d') or aisc.get('outer_height', 12.0)
        
        # Design connection
        design = self._rules.design_shear_tab(
            beam_depth=beam_depth,
            shear_demand_kips=shear,
            bolt_diameter=bolt_dia,
            bolt_grade=bolt_grade
        )
        
        # Update UI
        self._bolt_count.as_int = design.bolts.count
        self._plate_thickness.as_float = design.plate.thickness
        self._bolt_spacing.as_float = design.bolts.spacing
        
        # Update summary
        summary = f"Design: {design.notes}\n"
        summary += f"Plate: {design.plate.width}\" x {design.plate.height}\" x {design.plate.thickness}\"\n"
        if design.weld:
            summary += f"Weld: {design.weld.size}\" fillet, {design.weld.length}\" long\n"
        if design.warnings:
            summary += f"Warnings: {'; '.join(design.warnings)}"
        
        self._summary_label.text = summary
        
        if not design.is_valid:
            self._summary_label.style = {"color": 0xFFFF8888}
        else:
            self._summary_label.style = {"color": 0xFF88FF88}
    
    def _on_preview(self):
        """Shows a preview of the connection design."""
        self._on_auto_size()
        print("[SteelConnection] Preview generated - see Design Summary")
    
    def _on_create_connection(self):
        """Creates the connection geometry in the USD stage."""
        if not self._beam_a_path:
            print("[SteelConnection] Error: No beam selected")
            return
        
        stage = omni.usd.get_context().get_stage()
        if not stage:
            print("[SteelConnection] Error: No USD stage")
            return
        
        # Get parameters
        conn_type = self._connection_types[self._connection_type_index.as_int]
        bolt_dia = self._bolt_diameters[self._bolt_size_index.as_int]
        bolt_grade = self._bolt_grades[self._bolt_grade_index.as_int]
        bolt_count = self._bolt_count.as_int
        bolt_spacing = self._bolt_spacing.as_float
        plate_thickness = self._plate_thickness.as_float
        shear_demand = self._shear_demand.as_float
        
        # Get beam info
        prim_a = stage.GetPrimAtPath(self._beam_a_path)
        aisc_a = _parse_custom_data(prim_a, 'aisc_data', {})
        beam_depth = aisc_a.get('depth_d') or aisc_a.get('outer_height', 12.0)
        
        print(f"[SteelConnection] Creating {conn_type} for {beam_depth}\" beam")
        
        try:
            if conn_type == "Shear Tab":
                # Design and create shear tab
                design = self._rules.design_shear_tab(
                    beam_depth=beam_depth,
                    shear_demand_kips=shear_demand,
                    bolt_diameter=bolt_dia,
                    bolt_grade=bolt_grade
                )
                
                geometry = ShearTabGenerator.create_from_design(design)
                metadata = ShearTabGenerator.get_metadata(design)
                
            elif conn_type == "Double Angle":
                # Select and create double angle
                angle_size, count, length = DoubleAngleGenerator.select_angle_size(
                    beam_depth, shear_demand
                )
                
                geometry = DoubleAngleGenerator.create(
                    angle_size=angle_size,
                    angle_length=length,
                    bolt_diameter=bolt_dia,
                    bolt_count=count,
                    bolt_spacing=bolt_spacing
                )
                
                metadata = DoubleAngleGenerator.get_metadata(
                    angle_size, length, count, bolt_dia, bolt_grade
                )
            else:
                print(f"[SteelConnection] Connection type '{conn_type}' not yet implemented")
                return
            
            # Export to USD
            from ..utils.usd_utils import export_solid_to_usd
            
            # Create path for connection
            parent_path = str(prim_a.GetPath())
            connection_name = f"Connection_{conn_type.replace(' ', '')}"
            conn_path = f"{parent_path}/{connection_name}"
            
            # Make unique path
            counter = 1
            while stage.GetPrimAtPath(conn_path).IsValid():
                conn_path = f"{parent_path}/{connection_name}_{counter}"
                counter += 1
            
            # Export geometry
            export_solid_to_usd(stage, geometry, conn_path)
            
            # Set metadata
            conn_prim = stage.GetPrimAtPath(conn_path)
            if conn_prim.IsValid():
                for key, value in metadata.items():
                    conn_prim.SetCustomDataByKey(key, value)
                
                print(f"[SteelConnection] Created {conn_type} at {conn_path}")
            
        except Exception as e:
            print(f"[SteelConnection] Error creating connection: {e}")
            import traceback
            traceback.print_exc()
