# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
AISC Steel Connection Rule Engine

Implements connection type selection, validation, and sizing per AISC 360-22.
"""

import json
import os
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


class ConnectionType(Enum):
    """AISC simple shear connection types."""
    SHEAR_TAB = "shear_tab"
    DOUBLE_ANGLE = "double_angle"
    END_PLATE = "end_plate"
    THROUGH_PLATE = "through_plate"
    SEATED = "seated"


class MemberType(Enum):
    """Steel member types for connection logic."""
    WIDE_FLANGE = "W"
    CHANNEL = "C"
    HSS_RECT = "HSS_RECT"
    HSS_SQUARE = "HSS_SQUARE"
    ANGLE = "L"
    COLUMN = "COLUMN"


class ConnectionSurface(Enum):
    """Surface of member where connection attaches."""
    WEB = "web"
    FLANGE_TOP = "flange_top"
    FLANGE_BOTTOM = "flange_bottom"
    END = "end"
    HSS_FACE = "hss_face"


@dataclass
class BoltSpec:
    """Bolt specification for connection."""
    grade: str  # A307, A325, A490
    diameter: float  # inches
    count: int
    spacing: float  # vertical spacing, inches
    edge_distance: float  # inches


@dataclass
class PlateSpec:
    """Plate specification for connection."""
    width: float  # inches
    height: float  # inches
    thickness: float  # inches


@dataclass
class WeldSpec:
    """Weld specification for connection."""
    electrode: str  # E70XX
    size: float  # fillet weld leg size, inches
    length: float  # total weld length, inches


@dataclass
class ConnectionDesign:
    """Complete connection design output."""
    connection_type: ConnectionType
    plate: Optional[PlateSpec]
    bolts: BoltSpec
    weld: Optional[WeldSpec]
    is_valid: bool
    warnings: List[str]
    notes: str


class ConnectionRules:
    """
    AISC Connection Rules Engine.
    
    Loads rules from steel_connection_rules.json and provides:
    - Connection type selection based on member geometry
    - AISC-compliant dimension validation
    - Bolt and weld sizing
    """
    
    _instance = None
    _rules = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if ConnectionRules._rules is None:
            self._load_rules()
    
    def _load_rules(self):
        """Load connection rules from JSON file."""
        rules_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..', '..', '..', '..', '..', 
            'data', 'steel_connection_rules.json'
        )
        # Normalize path
        rules_path = os.path.normpath(rules_path)
        
        # Fallback to direct path if relative fails
        if not os.path.exists(rules_path):
            rules_path = os.path.join(
                os.path.dirname(__file__).split('exts')[0],
                'data', 'steel_connection_rules.json'
            )
        
        try:
            with open(rules_path, 'r') as f:
                ConnectionRules._rules = json.load(f)
        except FileNotFoundError:
            print(f"[ConnectionRules] Warning: Rules file not found at {rules_path}")
            ConnectionRules._rules = self._get_default_rules()
    
    def _get_default_rules(self) -> Dict:
        """Fallback default rules if JSON not found."""
        return {
            "bolt_sizes": {
                "3/4": {"diameter": 0.75, "hole_std": 0.8125},
                "7/8": {"diameter": 0.875, "hole_std": 0.9375}
            },
            "edge_distances": {"preferred_factor": 1.5}
        }
    
    @property
    def rules(self) -> Dict:
        return ConnectionRules._rules
    
    def get_compatible_connections(
        self,
        beam_type: MemberType,
        beam_surface: ConnectionSurface,
        support_type: MemberType,
        support_surface: ConnectionSurface
    ) -> List[ConnectionType]:
        """
        Returns valid connection types for the given member configuration.
        
        Args:
            beam_type: Type of beam being connected (W, C, HSS)
            beam_surface: Which surface of beam is connecting
            support_type: Type of support member (W, HSS, COLUMN)
            support_surface: Which surface of support receives connection
            
        Returns:
            List of valid ConnectionType enums
        """
        # Build geometry key
        beam_code = beam_type.value
        support_code = support_type.value
        
        if beam_surface == ConnectionSurface.WEB:
            beam_code += "_web"
        elif beam_surface == ConnectionSurface.END:
            beam_code += "_end"
        elif "flange" in beam_surface.value:
            beam_code += "_flange"
            
        if support_surface == ConnectionSurface.HSS_FACE:
            support_code = "HSS_face"
        elif support_surface == ConnectionSurface.WEB:
            support_code += "_web"
        elif "flange" in support_surface.value:
            support_code += "_flange"
        
        geometry_key = f"{beam_code}_to_{support_code}"
        
        compatible = []
        conn_types = self.rules.get("connection_types", {})
        
        for conn_name, conn_data in conn_types.items():
            supported = conn_data.get("supported_geometries", [])
            # Check for exact match or partial match
            for geom in supported:
                if geometry_key.lower() in geom.lower() or geom.lower() in geometry_key.lower():
                    try:
                        compatible.append(ConnectionType(conn_name))
                    except ValueError:
                        pass
                    break
        
        # Default to shear tab if nothing matches
        if not compatible and beam_surface == ConnectionSurface.WEB:
            compatible.append(ConnectionType.SHEAR_TAB)
        
        return compatible
    
    def validate_bolt_spacing(
        self,
        bolt_diameter: float,
        spacing: float,
        edge_distance: float
    ) -> Tuple[bool, List[str]]:
        """
        Validates bolt spacing per AISC J3.3 and J3.4.
        
        Args:
            bolt_diameter: Bolt diameter in inches
            spacing: Center-to-center spacing in inches
            edge_distance: Distance from bolt center to edge in inches
            
        Returns:
            (is_valid, list of warnings/errors)
        """
        issues = []
        is_valid = True
        
        # AISC minimum spacing: 2.67d (preferred 3d)
        min_spacing = 2.67 * bolt_diameter
        preferred_spacing = 3.0 * bolt_diameter
        
        if spacing < min_spacing:
            issues.append(f"Spacing {spacing}\" < min {min_spacing:.2f}\" (2.67d)")
            is_valid = False
        elif spacing < preferred_spacing:
            issues.append(f"Spacing {spacing}\" < preferred {preferred_spacing:.2f}\" (3d)")
        
        # AISC minimum edge distance (Table J3.4)
        edge_factor = self.rules.get("edge_distances", {}).get("preferred_factor", 1.5)
        min_edge = edge_factor * bolt_diameter
        
        if edge_distance < min_edge:
            issues.append(f"Edge distance {edge_distance}\" < min {min_edge:.2f}\" ({edge_factor}d)")
            is_valid = False
        
        return is_valid, issues
    
    def calculate_bolt_count(
        self,
        shear_demand_kips: float,
        bolt_grade: str = "A325",
        bolt_diameter: float = 0.75
    ) -> int:
        """
        Calculates required number of bolts for shear demand.
        
        Args:
            shear_demand_kips: Required shear capacity in kips
            bolt_grade: Bolt specification (A307, A325, A490)
            bolt_diameter: Bolt diameter in inches
            
        Returns:
            Number of bolts required
        """
        bolt_specs = self.rules.get("bolt_specifications", {})
        spec = bolt_specs.get(bolt_grade, bolt_specs.get("A325", {}))
        
        shear_stress = spec.get("shear_stress_ksi", 54.0)  # A325-N default
        
        # Single shear capacity per bolt
        import math
        area = math.pi * (bolt_diameter / 2) ** 2
        capacity_per_bolt = 0.75 * shear_stress * area  # LRFD phi = 0.75
        
        count = math.ceil(shear_demand_kips / capacity_per_bolt)
        
        # Minimum 2 bolts
        return max(2, count)
    
    def calculate_plate_thickness(
        self,
        shear_demand_kips: float,
        plate_height: float,
        bolt_diameter: float,
        num_bolts: int
    ) -> float:
        """
        Calculates minimum plate thickness per AISC J4.
        
        Checks:
        - Shear yielding
        - Shear rupture
        - Block shear
        
        Args:
            shear_demand_kips: Required shear in kips
            plate_height: Plate height in inches
            bolt_diameter: Bolt diameter in inches
            num_bolts: Number of bolts
            
        Returns:
            Minimum plate thickness in inches
        """
        Fy = 36.0  # A36 steel yield stress
        Fu = 58.0  # A36 steel ultimate stress
        
        bolt_info = self.rules.get("bolt_sizes", {}).get(
            f"{int(bolt_diameter*8)}/8" if bolt_diameter < 1 else str(int(bolt_diameter)),
            {"hole_std": bolt_diameter + 0.0625}
        )
        hole_diameter = bolt_info.get("hole_std", bolt_diameter + 0.0625)
        
        # Shear yielding: 0.6 * Fy * Ag
        # Vu <= phi * 0.6 * Fy * Ag
        # t >= Vu / (phi * 0.6 * Fy * h)
        phi_y = 1.0
        t_yielding = shear_demand_kips / (phi_y * 0.6 * Fy * plate_height)
        
        # Shear rupture: 0.6 * Fu * Anv
        # Net area = (height - n_bolts * hole_dia) * t
        net_height = plate_height - num_bolts * hole_diameter
        phi_r = 0.75
        if net_height > 0:
            t_rupture = shear_demand_kips / (phi_r * 0.6 * Fu * net_height)
        else:
            t_rupture = 1.0  # Force thick plate if net area is negative
        
        t_required = max(t_yielding, t_rupture)
        
        # Round up to standard thickness
        standard_thicknesses = self.rules.get(
            "connection_types", {}
        ).get("shear_tab", {}).get(
            "plate_thickness_options", 
            [0.25, 0.3125, 0.375, 0.4375, 0.5, 0.625, 0.75]
        )
        
        for t in standard_thicknesses:
            if t >= t_required:
                return t
        
        return standard_thicknesses[-1]  # Return thickest if none sufficient
    
    def calculate_weld_size(
        self,
        shear_demand_kips: float,
        weld_length: float,
        plate_thickness: float
    ) -> float:
        """
        Calculates fillet weld size per AISC J2.
        
        Args:
            shear_demand_kips: Load to be transferred
            weld_length: Total weld length (single side) in inches
            plate_thickness: Plate thickness in inches
            
        Returns:
            Weld leg size in inches
        """
        FEXX = 70.0  # E70XX electrode
        phi = 0.75
        
        # Weld strength = phi * 0.6 * FEXX * 0.707 * weld_size * length
        # For two-sided weld, effective length = 2 * weld_length
        effective_length = 2 * weld_length
        
        # Solve for weld size
        # Vu = phi * 0.6 * FEXX * 0.707 * w * L
        # w = Vu / (phi * 0.6 * FEXX * 0.707 * L)
        if effective_length > 0:
            w = shear_demand_kips / (phi * 0.6 * FEXX * 0.707 * effective_length)
        else:
            w = 0.25
        
        # AISC minimum weld size based on thicker part (Table J2.4)
        if plate_thickness <= 0.25:
            min_weld = 0.125
        elif plate_thickness <= 0.5:
            min_weld = 0.1875
        elif plate_thickness <= 0.75:
            min_weld = 0.25
        else:
            min_weld = 0.3125
        
        # Maximum weld = plate thickness - 1/16" for exposed edges
        max_weld = plate_thickness - 0.0625
        
        # Round to nearest 1/16"
        w_rounded = round(w * 16) / 16
        
        return max(min_weld, min(w_rounded, max_weld))
    
    def design_shear_tab(
        self,
        beam_depth: float,
        shear_demand_kips: float = 30.0,
        bolt_diameter: float = 0.75,
        bolt_grade: str = "A325"
    ) -> ConnectionDesign:
        """
        Designs a complete shear tab connection.
        
        Args:
            beam_depth: Beam depth in inches
            shear_demand_kips: Required shear capacity
            bolt_diameter: Bolt diameter
            bolt_grade: Bolt specification
            
        Returns:
            ConnectionDesign with all parameters
        """
        warnings = []
        
        # Calculate bolt count
        num_bolts = self.calculate_bolt_count(shear_demand_kips, bolt_grade, bolt_diameter)
        
        # Limit per AISC conventional shear tab
        max_bolts = self.rules.get("connection_types", {}).get(
            "shear_tab", {}
        ).get("parameters", {}).get("max_bolts", 12)
        
        if num_bolts > max_bolts:
            warnings.append(f"Bolt count {num_bolts} exceeds conventional limit {max_bolts}")
            num_bolts = max_bolts
        
        # Standard spacing
        spacing = 3.0  # AISC standard
        
        # Edge distances
        edge_horizontal = 2.0 * bolt_diameter
        edge_vertical = 1.5 * bolt_diameter
        
        # Plate dimensions
        plate_height = (num_bolts - 1) * spacing + 2 * edge_vertical
        plate_width = 3.5  # Conventional: weld to bolt line
        
        # Check plate height vs beam depth
        max_plate_height = beam_depth - 2 * 1.0  # 1" clearance top/bottom
        if plate_height > max_plate_height:
            warnings.append(f"Plate height {plate_height:.1f}\" exceeds available {max_plate_height:.1f}\"")
            # Reduce bolt count
            while plate_height > max_plate_height and num_bolts > 2:
                num_bolts -= 1
                plate_height = (num_bolts - 1) * spacing + 2 * edge_vertical
        
        # Calculate plate thickness
        plate_thickness = self.calculate_plate_thickness(
            shear_demand_kips, plate_height, bolt_diameter, num_bolts
        )
        
        # Calculate weld size
        weld_length = plate_height
        weld_size = self.calculate_weld_size(shear_demand_kips, weld_length, plate_thickness)
        
        # Validate bolt spacing
        is_valid, spacing_issues = self.validate_bolt_spacing(
            bolt_diameter, spacing, min(edge_horizontal, edge_vertical)
        )
        warnings.extend(spacing_issues)
        
        return ConnectionDesign(
            connection_type=ConnectionType.SHEAR_TAB,
            plate=PlateSpec(
                width=plate_width,
                height=plate_height,
                thickness=plate_thickness
            ),
            bolts=BoltSpec(
                grade=bolt_grade,
                diameter=bolt_diameter,
                count=num_bolts,
                spacing=spacing,
                edge_distance=edge_vertical
            ),
            weld=WeldSpec(
                electrode="E70XX",
                size=weld_size,
                length=weld_length
            ),
            is_valid=is_valid and len([w for w in warnings if "exceeds" in w]) == 0,
            warnings=warnings,
            notes=f"Conventional shear tab: {num_bolts}-{bolt_grade} {bolt_diameter}\" bolts"
        )
    
    def check_hss_wall_adequacy(
        self,
        hss_wall_thickness: float,
        hss_width: float,
        connection_type: ConnectionType = ConnectionType.SHEAR_TAB
    ) -> Tuple[bool, str]:
        """
        Checks if HSS wall is adequate for connection per Design Guide 24.
        
        Args:
            hss_wall_thickness: HSS wall thickness in inches
            hss_width: HSS face width in inches
            connection_type: Proposed connection type
            
        Returns:
            (is_adequate, recommendation)
        """
        hss_rules = self.rules.get("hss_special_rules", {})
        
        min_wall = hss_rules.get("min_wall_for_single_plate", 0.25)
        slender_limit = hss_rules.get("slender_wall_limit_b_over_t", 35)
        
        b_over_t = hss_width / hss_wall_thickness if hss_wall_thickness > 0 else 999
        
        if hss_wall_thickness < min_wall:
            return False, f"HSS wall {hss_wall_thickness}\" < min {min_wall}\" - use through-plate"
        
        if b_over_t > slender_limit:
            return False, f"HSS is slender (b/t={b_over_t:.1f} > {slender_limit}) - use through-plate"
        
        return True, "HSS wall adequate for single-plate connection"


# Convenience function for external use
def get_connection_rules() -> ConnectionRules:
    """Returns singleton ConnectionRules instance."""
    return ConnectionRules()
