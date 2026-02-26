# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
AISC HSS Tube Generator

Generates HSS (Hollow Structural Section) steel shapes using build123d.
Supports rectangular, square, and round HSS sections.
"""

import build123d as bd
from typing import Dict, Any, List, Optional
import json
import os
import math


class HSSGenerator:
    """
    Generator for AISC HSS (Hollow Structural Section) steel shapes.
    
    Creates HSS profiles with:
    - Accurate AISC dimensions
    - Corner radii (typically 2t for formed HSS)
    - Parametric length
    - Fabrication features
    """
    
    @staticmethod
    def create_rectangular(
        outer_width: float,
        outer_height: float,
        wall_thickness: float,
        length: float,
        corner_radius: float = None,
        features: List[Dict[str, Any]] = None
    ) -> bd.Solid:
        """
        Creates a rectangular/square HSS tube.
        
        Args:
            outer_width: Outer width (B) in inches
            outer_height: Outer height (H) in inches (= width for square)
            wall_thickness: Wall thickness (t) in inches
            length: Tube length in inches
            corner_radius: Outer corner radius (default: 2t)
            features: Optional fabrication features
            
        Returns:
            bd.Solid: HSS tube geometry
        """
        if corner_radius is None:
            corner_radius = 2 * wall_thickness
        
        inner_width = outer_width - 2 * wall_thickness
        inner_height = outer_height - 2 * wall_thickness
        inner_corner_radius = max(0.01, corner_radius - wall_thickness)
        
        with bd.BuildPart() as hss:
            with bd.BuildSketch(bd.Plane.XY):
                # Outer rectangle with rounded corners
                bd.RectangleRounded(
                    outer_width, outer_height, 
                    radius=corner_radius
                )
                # Inner rectangle (subtracted) with rounded corners
                bd.RectangleRounded(
                    inner_width, inner_height,
                    radius=inner_corner_radius,
                    mode=bd.Mode.SUBTRACT
                )
            bd.extrude(amount=length)
        
        solid = hss.part
        
        # Apply features if specified
        if features:
            for feature in features:
                if feature.get('enabled', True):
                    solid = HSSGenerator._apply_feature(
                        solid, feature, outer_width, outer_height, 
                        wall_thickness, length
                    )
        
        return solid
    
    @staticmethod
    def create_round(
        outer_diameter: float,
        wall_thickness: float,
        length: float,
        features: List[Dict[str, Any]] = None
    ) -> bd.Solid:
        """
        Creates a round HSS tube.
        
        Args:
            outer_diameter: Outer diameter in inches
            wall_thickness: Wall thickness in inches
            length: Tube length in inches
            features: Optional fabrication features
            
        Returns:
            bd.Solid: Round HSS tube geometry
        """
        outer_radius = outer_diameter / 2
        inner_radius = outer_radius - wall_thickness
        
        with bd.BuildPart() as hss:
            with bd.BuildSketch(bd.Plane.XY):
                # Outer circle
                bd.Circle(outer_radius)
                # Inner circle (subtracted)
                bd.Circle(inner_radius, mode=bd.Mode.SUBTRACT)
            bd.extrude(amount=length)
        
        solid = hss.part
        
        if features:
            for feature in features:
                if feature.get('enabled', True):
                    solid = HSSGenerator._apply_feature_round(
                        solid, feature, outer_diameter, wall_thickness, length
                    )
        
        return solid
    
    @staticmethod
    def _apply_feature(
        solid: bd.Solid,
        feature: Dict[str, Any],
        width: float,
        height: float,
        wall_thickness: float,
        length: float
    ) -> bd.Solid:
        """Applies a fabrication feature to rectangular HSS."""
        feature_type = feature.get('type', '')
        
        if feature_type == 'bolt_holes':
            return HSSGenerator._apply_bolt_holes(
                solid, feature, width, height, wall_thickness, length
            )
        elif feature_type == 'slot':
            return HSSGenerator._apply_slot(
                solid, feature, width, height, wall_thickness, length
            )
        elif feature_type == 'through_plate_slot':
            return HSSGenerator._apply_through_plate_slot(
                solid, feature, width, height, wall_thickness, length
            )
        
        return solid
    
    @staticmethod
    def _apply_feature_round(
        solid: bd.Solid,
        feature: Dict[str, Any],
        diameter: float,
        wall_thickness: float,
        length: float
    ) -> bd.Solid:
        """Applies a fabrication feature to round HSS."""
        feature_type = feature.get('type', '')
        
        if feature_type == 'bolt_holes':
            return HSSGenerator._apply_bolt_holes_round(
                solid, feature, diameter, wall_thickness, length
            )
        
        return solid
    
    @staticmethod
    def _apply_bolt_holes(
        solid: bd.Solid,
        feature: Dict[str, Any],
        width: float,
        height: float,
        wall_thickness: float,
        length: float
    ) -> bd.Solid:
        """Adds bolt holes to HSS face."""
        face = feature.get('face', 'front')  # 'front', 'back', 'left', 'right'
        position = feature.get('position', 'end')
        diameter = feature.get('diameter', 0.875)
        count = feature.get('count', 2)
        spacing = feature.get('spacing', 3.0)
        
        hole_diameter = diameter + 0.0625
        
        if position == 'start':
            start_z = 2.0
        elif position == 'end':
            start_z = length - 2.0 - (count - 1) * spacing
        else:
            total_span = (count - 1) * spacing
            start_z = (length - total_span) / 2
        
        holes_solid = None
        
        for i in range(count):
            z_pos = start_z + i * spacing
            
            if face in ['front', 'back']:
                x_pos = 0
                y_pos = height / 2 if face == 'front' else -height / 2
                plane = bd.Plane.XZ.offset(y_pos)
            else:
                x_pos = width / 2 if face == 'right' else -width / 2
                y_pos = 0
                plane = bd.Plane.YZ.offset(x_pos)
            
            with bd.BuildPart() as hole:
                with bd.BuildSketch(plane):
                    with bd.Locations([(0, z_pos)]):
                        bd.Circle(hole_diameter / 2)
                bd.extrude(amount=wall_thickness * 3, both=True)
            
            if holes_solid is None:
                holes_solid = hole.part
            else:
                holes_solid = holes_solid.fuse(hole.part)
        
        if holes_solid:
            return solid.cut(holes_solid)
        return solid
    
    @staticmethod
    def _apply_bolt_holes_round(
        solid: bd.Solid,
        feature: Dict[str, Any],
        diameter: float,
        wall_thickness: float,
        length: float
    ) -> bd.Solid:
        """Adds bolt holes to round HSS."""
        angle_deg = feature.get('angle', 0)  # Position around circumference
        position = feature.get('position', 'end')
        bolt_diameter = feature.get('diameter', 0.875)
        count = feature.get('count', 2)
        spacing = feature.get('spacing', 3.0)
        
        hole_diameter = bolt_diameter + 0.0625
        radius = diameter / 2
        
        if position == 'start':
            start_z = 2.0
        elif position == 'end':
            start_z = length - 2.0 - (count - 1) * spacing
        else:
            total_span = (count - 1) * spacing
            start_z = (length - total_span) / 2
        
        holes_solid = None
        angle_rad = math.radians(angle_deg)
        
        for i in range(count):
            z_pos = start_z + i * spacing
            x_pos = radius * math.cos(angle_rad)
            y_pos = radius * math.sin(angle_rad)
            
            # Create hole through wall
            with bd.BuildPart() as hole:
                with bd.BuildSketch(bd.Plane.XY.offset(z_pos)):
                    with bd.Locations([(x_pos, y_pos)]):
                        bd.Circle(hole_diameter / 2)
                bd.extrude(amount=wall_thickness * 3, both=True)
            
            if holes_solid is None:
                holes_solid = hole.part
            else:
                holes_solid = holes_solid.fuse(hole.part)
        
        if holes_solid:
            return solid.cut(holes_solid)
        return solid
    
    @staticmethod
    def _apply_through_plate_slot(
        solid: bd.Solid,
        feature: Dict[str, Any],
        width: float,
        height: float,
        wall_thickness: float,
        length: float
    ) -> bd.Solid:
        """Creates slot for through-plate connection per Design Guide 24."""
        position = feature.get('position', 'end')
        slot_height = feature.get('slot_height', height * 0.7)
        plate_thickness = feature.get('plate_thickness', 0.5)
        
        # Position at specified end
        if position == 'start':
            z_start = -0.1
            z_end = 3.0  # Typical extension
        else:
            z_start = length - 3.0
            z_end = length + 0.1
        
        slot_depth = z_end - z_start
        
        # Create slot through both faces
        with bd.BuildPart() as slot:
            with bd.BuildSketch(bd.Plane.XZ.offset(height / 2)):
                with bd.Locations([(0, z_start + slot_depth / 2)]):
                    bd.Rectangle(plate_thickness + 0.0625, slot_depth)
            bd.extrude(amount=wall_thickness * 2)
        
        slot1 = slot.part
        
        with bd.BuildPart() as slot_back:
            with bd.BuildSketch(bd.Plane.XZ.offset(-height / 2)):
                with bd.Locations([(0, z_start + slot_depth / 2)]):
                    bd.Rectangle(plate_thickness + 0.0625, slot_depth)
            bd.extrude(amount=-wall_thickness * 2)
        
        slot2 = slot_back.part
        
        return solid.cut(slot1).cut(slot2)
    
    @staticmethod
    def _apply_slot(
        solid: bd.Solid,
        feature: Dict[str, Any],
        width: float,
        height: float,
        wall_thickness: float,
        length: float
    ) -> bd.Solid:
        """Creates a simple slot in HSS face."""
        face = feature.get('face', 'front')
        slot_width = feature.get('slot_width', 2.0)
        slot_length = feature.get('slot_length', 4.0)
        z_pos = feature.get('z_position', length / 2)
        
        if face in ['front', 'back']:
            y_pos = height / 2 if face == 'front' else -height / 2
            with bd.BuildPart() as slot:
                with bd.BuildSketch(bd.Plane.XZ.offset(y_pos)):
                    with bd.Locations([(0, z_pos)]):
                        bd.Rectangle(slot_width, slot_length)
                bd.extrude(amount=wall_thickness * 2, both=True)
        else:
            x_pos = width / 2 if face == 'right' else -width / 2
            with bd.BuildPart() as slot:
                with bd.BuildSketch(bd.Plane.YZ.offset(x_pos)):
                    with bd.Locations([(0, z_pos)]):
                        bd.Rectangle(slot_width, slot_length)
                bd.extrude(amount=wall_thickness * 2, both=True)
        
        return solid.cut(slot.part)
    
    @staticmethod
    def create_from_aisc(
        aisc_data: Dict[str, Any],
        length: float,
        features: List[Dict[str, Any]] = None
    ) -> bd.Solid:
        """
        Creates HSS from AISC data dictionary.
        
        Args:
            aisc_data: Dictionary with AISC HSS dimensions
            length: Tube length in inches
            features: Optional fabrication features
            
        Returns:
            bd.Solid: HSS geometry
        """
        shape = aisc_data.get('shape', 'square')
        
        if shape == 'round':
            return HSSGenerator.create_round(
                outer_diameter=aisc_data.get('outer_diameter', 6.0),
                wall_thickness=aisc_data.get('wall_thickness', 0.25),
                length=length,
                features=features
            )
        else:
            return HSSGenerator.create_rectangular(
                outer_width=aisc_data.get('outer_width', 6.0),
                outer_height=aisc_data.get('outer_height', 6.0),
                wall_thickness=aisc_data.get('wall_thickness', 0.25),
                length=length,
                features=features
            )
    
    @staticmethod
    def load_aisc_data() -> List[Dict[str, Any]]:
        """Loads AISC HSS data from JSON file."""
        # Path from objects/ up to buildteamai/data/
        data_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..', '..', '..', '..', 
            'data', 'aisc_hss.json'
        )
        data_path = os.path.normpath(data_path)
        
        if os.path.exists(data_path):
            try:
                with open(data_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[HSSGenerator] Error loading AISC data: {e}")
        
        # Return default data if file not found
        print(f"[HSSGenerator] AISC data not found at {data_path}, using defaults")
        return [
            {"designation": "HSS3x3x1/4", "shape": "square", "outer_width": 3.0, "outer_height": 3.0, "wall_thickness": 0.233, "weight_lb_ft": 8.81},
            {"designation": "HSS4x4x1/4", "shape": "square", "outer_width": 4.0, "outer_height": 4.0, "wall_thickness": 0.233, "weight_lb_ft": 12.21},
            {"designation": "HSS5x5x1/4", "shape": "square", "outer_width": 5.0, "outer_height": 5.0, "wall_thickness": 0.233, "weight_lb_ft": 15.62},
            {"designation": "HSS6x6x1/4", "shape": "square", "outer_width": 6.0, "outer_height": 6.0, "wall_thickness": 0.233, "weight_lb_ft": 19.02},
            {"designation": "HSS6x6x3/8", "shape": "square", "outer_width": 6.0, "outer_height": 6.0, "wall_thickness": 0.349, "weight_lb_ft": 27.48},
            {"designation": "HSS8x8x1/4", "shape": "square", "outer_width": 8.0, "outer_height": 8.0, "wall_thickness": 0.233, "weight_lb_ft": 25.82},
            {"designation": "HSS8x8x3/8", "shape": "square", "outer_width": 8.0, "outer_height": 8.0, "wall_thickness": 0.349, "weight_lb_ft": 37.69},
            {"designation": "HSS10x10x3/8", "shape": "square", "outer_width": 10.0, "outer_height": 10.0, "wall_thickness": 0.349, "weight_lb_ft": 47.90},
        ]
    
    @staticmethod
    def check_wall_adequacy(
        wall_thickness: float,
        face_width: float
    ) -> tuple:
        """
        Checks if HSS wall is adequate for connections per Design Guide 24.
        
        Args:
            wall_thickness: Wall thickness in inches
            face_width: Width of connecting face in inches
            
        Returns:
            Tuple of (is_adequate, b_over_t_ratio, message)
        """
        b_over_t = face_width / wall_thickness if wall_thickness > 0 else 999
        
        # AISC slenderness limit for connections
        slender_limit = 35
        min_wall = 0.25
        
        if wall_thickness < min_wall:
            return False, b_over_t, f"Wall {wall_thickness}\" < minimum {min_wall}\""
        
        if b_over_t > slender_limit:
            return False, b_over_t, f"b/t = {b_over_t:.1f} > {slender_limit} (slender)"
        
        return True, b_over_t, f"Wall adequate (b/t = {b_over_t:.1f})"
    
    @staticmethod
    def get_metadata(
        designation: str,
        length: float,
        aisc_data: Dict[str, Any],
        features: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Returns USD metadata for the HSS."""
        shape = aisc_data.get('shape', 'square')
        
        metadata = {
            "generatorType": "hss_tube",
            "memberType": "HSS_RECT" if shape != 'round' else "HSS_ROUND",
            "designation": designation,
            "length": length,
            "shape": shape,
            "aisc_data": {
                "outer_width": aisc_data.get('outer_width'),
                "outer_height": aisc_data.get('outer_height'),
                "wall_thickness": aisc_data.get('wall_thickness'),
                "weight_lb_ft": aisc_data.get('weight_lb_ft')
            },
            "features": features or []
        }
        
        if shape == 'round':
            metadata["aisc_data"]["outer_diameter"] = aisc_data.get('outer_diameter')
        
        return metadata
