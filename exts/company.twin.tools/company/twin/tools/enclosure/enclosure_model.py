# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Data Model for Sheet Metal Enclosure Configurator.
Following TunnelModel pattern for clean separation of data and rendering.
"""

from enum import Enum
from pxr import Sdf

__all__ = ["GridStrategy", "PanelNode", "Wall", "EnclosureModel"]


class GridStrategy(Enum):
    EQUAL = 0       # All panels equal width
    FABRICATION = 1 # Max panel width (48") + Remainder

class PanelNode:
    """
    Represents a single logical panel in a wall.
    """
    def __init__(self, p_type="Solid", width=30.0, height=30.0, row=0):
        self.type = p_type  # "Solid", "Window", "Louver", "Cutout"
        self.width = width
        self.height = height
        self.row = row
        self.variant_params = {}  # e.g. {"win_width": 24.0, "win_height": 24.0, "win_y": 12.0}

    def to_dict(self):
        return {
            "type": self.type,
            "width": self.width,
            "height": self.height,
            "row": self.row,
            "params": self.variant_params
        }


class Wall:
    """
    Represents one wall of the enclosure (e.g., Back, Front, Left, Right, Top, Bottom).
    Contains a grid of panels organized as columns.
    """
    def __init__(self, name, target_width=60.0, target_height=60.0):
        self.name = name
        self.target_width = target_width  # Total wall dimension (X or Y depending on orientation)
        self.target_height = target_height  # Total wall height (Z for vertical walls, Y or X for top/bottom)
        self.strategy = GridStrategy.EQUAL
        self.columns = []  # List[List[PanelNode]] - each column is a vertical stack

    def clear(self):
        self.columns = []

    def regenerate_default(self, panel_width=30.0, strategy=GridStrategy.EQUAL):
        """
        Regenerates the wall with standard solid panels.
        """
        self.clear()
        self.strategy = strategy

        if strategy == GridStrategy.EQUAL:
            # Calculate number of columns
            count = max(1, int(round(self.target_width / panel_width)))
            actual_width = self.target_width / count
            col_widths = [actual_width] * count
        else: # FABRICATION
            # Max 48" panels + remainder
            MAX_W = 48.0
            full_count = int(self.target_width // MAX_W)
            remainder = self.target_width - (full_count * MAX_W)
            
            col_widths = [MAX_W] * full_count
            if remainder > 0.01:
                col_widths.append(remainder)
            
            if not col_widths:
                col_widths = [self.target_width]

        # Calculate tiers (vertical stacking)
        tiers = self._calculate_tiers()

        for w in col_widths:
            col_panels = []
            for r, h in enumerate(tiers):
                p = PanelNode("Solid", w, h, r)
                col_panels.append(p)
            self.columns.append(col_panels)

    def _calculate_tiers(self):
        """
        Calculates vertical tier heights.
        
        Rule: If Wall Height is > 30" and < 96", split into 2 equal panels (50%).
        Otherwise, use max panel size (48") logic.
        """
        MAX_PANEL_HEIGHT = 96.0
        
        # User Logic: If > 96", max panel is 96", create header for remainder.
        # This implies:
        # H <= 96: Single Panel (or user can split if they want, but default is max)
        # H > 96: [96, Remainder] (Bottom-Up)

        if self.target_height <= MAX_PANEL_HEIGHT:
            return [self.target_height]
        
        # H > 96: Multi-tier logic (Max + Remainder)
        tiers = []
        remaining = self.target_height
        
        while remaining > 0.01:
            tier_h = min(MAX_PANEL_HEIGHT, remaining)
            tiers.append(tier_h)
            remaining -= tier_h
        
        return tiers

    def set_panel_type(self, col_idx, row_idx, p_type, params=None):
        """
        Sets the type and parameters of a specific panel.
        """
        if 0 <= col_idx < len(self.columns):
            column = self.columns[col_idx]
            if 0 <= row_idx < len(column):
                column[row_idx].type = p_type
                column[row_idx].variant_params = params.copy() if params else {}

    def update_column_width(self, col_idx, new_width):
        """
        Updates width of a specific column and reflows the rest.
        """
        if 0 <= col_idx < len(self.columns):
            for p in self.columns[col_idx]:
                p.width = new_width
            self._reflow_columns(col_idx)

    def _reflow_columns(self, frozen_idx):
        """
        Recalculates columns after frozen_idx to fit target_width.
        """
        used_width = sum(col[0].width for col in self.columns[:frozen_idx + 1] if col)
        remaining = self.target_width - used_width

        # Remove columns after frozen
        del self.columns[frozen_idx + 1:]

        if remaining <= 0.01:
            return

        # Fill with standard panels
        std_width = 30.0
        tiers = self._calculate_tiers()

        while remaining > 0.01:
            next_w = min(std_width, remaining)
            col_panels = [PanelNode("Solid", next_w, h, r) for r, h in enumerate(tiers)]
            self.columns.append(col_panels)
            remaining -= next_w


class EnclosureModel:
    """
    Data model for a 6-sided sheet metal enclosure.
    All dimensions in inches.
    """
    def __init__(self, length=60.0, width=60.0, height=72.0, flange_depth=1.5):
        self.length = length  # X dimension
        self.width = width    # Y dimension
        self.height = height  # Z dimension
        
        # Gauge/Thickness
        self.gauge = 14  # 14ga default
        self.thickness = 0.0747  # 14ga in inches
        
        # Flange parameters
        self.flange_depth = flange_depth  # Bend depth
        self.return_length = 0.5  # Return edge
        self.grid_strategy = GridStrategy.EQUAL  # Default strategy
        
        # Configuration Flags
        self.has_entry_wall = False
        self.has_exit_wall = False
        self.has_floor = False
        
        # Opening Dimensions (Centered on Front/Back walls)
        self.opening_width = 0.0
        self.opening_height = 0.0

        # 6 Walls
        self.back = Wall("Back", length, height)     # -Y face
        self.front = Wall("Front", length, height)   # +Y face (Door)
        self.left = Wall("Left", width, height)      # -X face
        self.right = Wall("Right", width, height)    # +X face
        self.top = Wall("Top", length, width)        # +Z face
        self.bottom = Wall("Bottom", length, width)  # -Z face

    def initialize_default(self, panel_width=30.0, strategy=GridStrategy.EQUAL):
        """
        Initializes walls with default solid panels.
        """
        self.grid_strategy = strategy
        
        # Left wall: along X (length) and Y (height)
        self.left.target_width = self.length
        self.left.target_height = self.height
        self.left.regenerate_default(panel_width, strategy)

        # Right wall: along X (length) and Y (height)
        self.right.target_width = self.length
        self.right.target_height = self.height
        self.right.regenerate_default(panel_width, strategy)

        # Roof: along X (length) and Z (width)
        self.top.target_width = self.length
        self.top.target_height = self.width
        self.top.regenerate_default(panel_width, strategy)

        # Optional Walls
        if self.has_entry_wall:
            # Entry (Back): Spans Width (Z) x Height (Y) at X=0
            self.back.target_width = self.width
            self.back.target_height = self.height
            self.back.regenerate_default(panel_width, strategy)
            
        if self.has_exit_wall:
            # Exit (Front): Spans Width (Z) x Height (Y) at X=Length
            self.front.target_width = self.width
            self.front.target_height = self.height
            self.front.regenerate_default(panel_width, strategy)
            
        if self.has_floor:
            # Floor (Bottom): Spans Length (X) x Width (Z) at Y=0
            self.bottom.target_width = self.length
            self.bottom.target_height = self.width
            self.bottom.regenerate_default(panel_width, strategy)

    def get_wall_by_name(self, name):
        """
        Returns a wall object by name.
        """
        walls = {
            "Back": self.back,
            "Front": self.front,
            "Left": self.left,
            "Right": self.right,
            "Top": self.top,
            "Bottom": self.bottom
        }
        return walls.get(name)

    def set_gauge(self, gauge):
        """
        Sets the gauge and updates thickness.
        """
        gauge_map = {
            10: 0.1345,
            11: 0.1196,
            12: 0.1046,
            14: 0.0747,
            16: 0.0598,
            18: 0.0478,
            20: 0.0359,
            22: 0.0299,
            24: 0.0239,
        }
        self.gauge = gauge
        self.thickness = gauge_map.get(gauge, 0.0747)

    def serialize(self, prim):
        """
        Saves the model state to USD attributes on the prim.
        """
        # Save scalar attributes
        prim.CreateAttribute("btai:enclosure:length", Sdf.ValueTypeNames.Double).Set(self.length)
        prim.CreateAttribute("btai:enclosure:width", Sdf.ValueTypeNames.Double).Set(self.width)
        prim.CreateAttribute("btai:enclosure:height", Sdf.ValueTypeNames.Double).Set(self.height)
        prim.CreateAttribute("btai:enclosure:gauge", Sdf.ValueTypeNames.Int).Set(self.gauge)
        prim.CreateAttribute("btai:enclosure:flange_depth", Sdf.ValueTypeNames.Double).Set(self.flange_depth)
        prim.CreateAttribute("btai:enclosure:has_entry_wall", Sdf.ValueTypeNames.Bool).Set(self.has_entry_wall)
        prim.CreateAttribute("btai:enclosure:has_exit_wall", Sdf.ValueTypeNames.Bool).Set(self.has_exit_wall)
        prim.CreateAttribute("btai:enclosure:has_floor", Sdf.ValueTypeNames.Bool).Set(self.has_floor)
        prim.CreateAttribute("btai:enclosure:opening_width", Sdf.ValueTypeNames.Double).Set(self.opening_width)
        prim.CreateAttribute("btai:enclosure:opening_height", Sdf.ValueTypeNames.Double).Set(self.opening_height)
        prim.CreateAttribute("btai:enclosure:grid_strategy", Sdf.ValueTypeNames.String).Set(self.grid_strategy.name)
        
        # We don't save every panel node here; the render process creates distinct prims.
        # However, to reload variants, we will need to walk the generated prims during load.

    def deserialize(self, prim):
        """
        Loads the model state from USD attributes.
        """
        attr_len = prim.GetAttribute("btai:enclosure:length")
        if not attr_len.IsValid():
            return False
            
        self.length = attr_len.Get()
        # Helper for safe attribute access
        def _get_attr(name, default=None):
            attr = prim.GetAttribute(name)
            if attr and attr.IsValid() and attr.HasValue():
                return attr.Get()
            return default

        self.length = _get_attr("btai:enclosure:length", 60.0)
        self.width = _get_attr("btai:enclosure:width", 60.0)
        self.height = _get_attr("btai:enclosure:height", 72.0)
        self.gauge = _get_attr("btai:enclosure:gauge", 14)
        self.set_gauge(self.gauge)
        
        self.flange_depth = _get_attr("btai:enclosure:flange_depth", 1.5)
        self.has_entry_wall = _get_attr("btai:enclosure:has_entry_wall", False)
        self.has_exit_wall = _get_attr("btai:enclosure:has_exit_wall", False)
        self.has_floor = _get_attr("btai:enclosure:has_floor", False)
        
        self.opening_width = _get_attr("btai:enclosure:opening_width", 0.0)
        self.opening_height = _get_attr("btai:enclosure:opening_height", 0.0)
        
        strategy_name = _get_attr("btai:enclosure:grid_strategy")
        if strategy_name == "FABRICATION":
            self.grid_strategy = GridStrategy.FABRICATION
        else:
            self.grid_strategy = GridStrategy.EQUAL
            
        # Initialize default geometry first to set up structure
        self.initialize_default(30.0, self.grid_strategy) # Panel width is approximate if EQUAL, ignored if FAB

        # Scan children to recover variants
        # Paths are like: root/Wall_Left/Panel_0_1
        # We need to traverse prim children
        
        for wall_name in ["Left", "Right", "Roof", "Entry", "Exit", "Floor"]:
            wall_prim_name = f"Wall_{wall_name}" if wall_name != "Floor" else "Floor"
            wall_obj = self.get_wall_by_name(wall_name)
            if not wall_obj: 
                continue

            wall_prim = prim.GetStage().GetPrimAtPath(f"{prim.GetPath()}/{wall_prim_name}")
            if not wall_prim.IsValid():
                continue

            for child in wall_prim.GetChildren():
                # Check for panel attributes
                row_attr = child.GetAttribute("btai:panel:row")
                col_attr = child.GetAttribute("btai:panel:col")
                type_attr = child.GetAttribute("custom:panel_type") # Saved by instantiate_panel relative to prim
                
                if row_attr.IsValid() and col_attr.IsValid():
                    row = row_attr.Get()
                    col = col_attr.Get()
                    p_type = type_attr.Get() if type_attr.IsValid() else "Solid"
                    
                    # Recover variants
                    v_params = {}
                    
                    # Try to read known params
                    known_keys = ["win_width", "win_height", "win_y", 
                                  "ap_width", "ap_height", "ap_y",
                                  "door_width", "door_height"]
                    
                    for k in known_keys:
                        attr = child.GetAttribute(f"custom:{k}")
                        if attr.IsValid():
                            v_params[k] = attr.Get()
                    
                    # Re-apply to memory model
                    wall_obj.set_panel_type(col, row, p_type, v_params)
        
        return True
