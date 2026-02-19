# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Double Angle Connection Generator

Generates AISC-compliant double angle (clip angle) connection geometry using build123d.
"""

import build123d as bd
from typing import Dict, Any, List, Tuple, Optional
import math


class DoubleAngleGenerator:
    """
    Generates double angle connection geometry per AISC specifications.
    
    A double angle connection consists of:
    - Two L-angles, one on each side of beam web
    - Bolted or welded to beam web (outstanding leg)
    - Bolted or welded to support (attached leg)
    """
    
    # Standard angle sizes (leg1 x leg2 x thickness)
    ANGLE_SIZES = {
        "L3x3x1/4": (3.0, 3.0, 0.25),
        "L3x3x3/8": (3.0, 3.0, 0.375),
        "L4x3x1/4": (4.0, 3.0, 0.25),
        "L4x3x3/8": (4.0, 3.0, 0.375),
        "L4x4x3/8": (4.0, 4.0, 0.375),
        "L5x3x3/8": (5.0, 3.0, 0.375),
        "L5x5x3/8": (5.0, 5.0, 0.375),
    }
    
    @staticmethod
    def create_single_angle(
        leg_vertical: float,
        leg_horizontal: float,
        thickness: float,
        length: float,
        fillet_radius: float = 0.25
    ) -> bd.Solid:
        """
        Creates a single L-angle extrusion.
        
        Args:
            leg_vertical: Vertical leg length (attached to support)
            leg_horizontal: Horizontal leg length (outstanding, connects to beam)
            thickness: Angle thickness
            length: Length of angle (height)
            fillet_radius: Fillet at inside corner
            
        Returns:
            bd.Solid: Single angle geometry
        """
        with bd.BuildPart() as angle:
            with bd.BuildSketch(bd.Plane.XY):
                # Create L-shape profile
                # Vertical leg along +Y, horizontal leg along +X
                with bd.BuildLine():
                    # Start at origin, go up vertical leg
                    bd.Line((0, 0), (0, leg_vertical))
                    bd.Line((0, leg_vertical), (thickness, leg_vertical))
                    bd.Line((thickness, leg_vertical), (thickness, thickness))
                    bd.Line((thickness, thickness), (leg_horizontal, thickness))
                    bd.Line((leg_horizontal, thickness), (leg_horizontal, 0))
                    bd.Line((leg_horizontal, 0), (0, 0))
                bd.make_face()
            
            # Extrude along Z (length of angle)
            bd.extrude(amount=length)
            
            # Add fillet at inside corner if specified
            if fillet_radius > 0:
                try:
                    # Find inside corner edge
                    inside_edges = angle.part.edges().filter_by(
                        lambda e: e.length == length
                    )
                    if inside_edges:
                        bd.fillet(inside_edges, radius=fillet_radius)
                except:
                    pass  # Skip fillet if it fails
        
        return angle.part
    
    @staticmethod
    def create(
        angle_size: str,
        angle_length: float,
        bolt_diameter: float,
        bolt_count: int,
        bolt_spacing: float = 3.0,
        gage_outstanding: float = 2.0,
        gage_attached: float = 2.5,
        edge_distance: float = 1.5,
        include_both_angles: bool = True
    ) -> bd.Solid:
        """
        Creates a double angle connection.
        
        Args:
            angle_size: Standard angle designation (e.g., "L4x3x3/8")
            angle_length: Length of angles in inches
            bolt_diameter: Bolt diameter in inches
            bolt_count: Number of bolts per leg
            bolt_spacing: Vertical spacing between bolts
            gage_outstanding: Bolt gage on outstanding leg (beam side)
            gage_attached: Bolt gage on attached leg (support side)
            edge_distance: Edge distance for bolts
            include_both_angles: If True, creates both angles; if False, creates one
            
        Returns:
            bd.Solid: Double angle geometry (or single if specified)
        """
        # Get angle dimensions
        if angle_size in DoubleAngleGenerator.ANGLE_SIZES:
            leg1, leg2, thickness = DoubleAngleGenerator.ANGLE_SIZES[angle_size]
        else:
            # Parse from string like "L4x3x3/8"
            parts = angle_size.replace("L", "").split("x")
            leg1 = float(parts[0])
            leg2 = float(parts[1])
            # Handle fraction
            if "/" in parts[2]:
                num, denom = parts[2].split("/")
                thickness = float(num) / float(denom)
            else:
                thickness = float(parts[2])
        
        # Vertical leg = attached to support (leg1)
        # Horizontal leg = outstanding, connects to beam web (leg2)
        
        hole_diameter = bolt_diameter + 0.0625
        
        # Create first angle
        angle1 = DoubleAngleGenerator.create_single_angle(
            leg_vertical=leg1,
            leg_horizontal=leg2,
            thickness=thickness,
            length=angle_length
        )
        
        # Add bolt holes to outstanding leg (horizontal, beam side)
        total_span = (bolt_count - 1) * bolt_spacing
        first_bolt_z = (angle_length - total_span) / 2
        
        outstanding_holes = None
        for i in range(bolt_count):
            bolt_z = first_bolt_z + i * bolt_spacing
            # Hole in horizontal leg, at gage distance from heel
            bolt_x = gage_outstanding
            bolt_y = thickness / 2
            
            with bd.BuildPart() as hole:
                with bd.BuildSketch(bd.Plane.XY.offset(bolt_z)):
                    with bd.Locations([(bolt_x, bolt_y)]):
                        bd.Circle(hole_diameter / 2)
                bd.extrude(amount=thickness * 2)
            
            if outstanding_holes is None:
                outstanding_holes = hole.part
            else:
                outstanding_holes = outstanding_holes.fuse(hole.part)
        
        # Add bolt holes to attached leg (vertical, support side)
        attached_holes = None
        for i in range(bolt_count):
            bolt_z = first_bolt_z + i * bolt_spacing
            # Hole in vertical leg, at gage distance from heel
            bolt_x = thickness / 2
            bolt_y = gage_attached
            
            with bd.BuildPart() as hole:
                with bd.BuildSketch(bd.Plane.XY.offset(bolt_z)):
                    with bd.Locations([(bolt_x, bolt_y)]):
                        bd.Circle(hole_diameter / 2)
                bd.extrude(amount=thickness * 2)
            
            if attached_holes is None:
                attached_holes = hole.part
            else:
                attached_holes = attached_holes.fuse(hole.part)
        
        # Subtract holes
        if outstanding_holes:
            angle1 = angle1.cut(outstanding_holes)
        if attached_holes:
            angle1 = angle1.cut(attached_holes)
        
        if not include_both_angles:
            return angle1
        
        # Create second angle (mirror across the beam web)
        # Mirror in X direction and offset by gap (web thickness + clearance)
        angle2 = angle1.mirror(bd.Plane.YZ)
        
        # Combine both angles
        result = angle1.fuse(angle2)
        
        return result
    
    @staticmethod
    def select_angle_size(
        beam_depth: float,
        shear_demand_kips: float = 30.0
    ) -> Tuple[str, int, float]:
        """
        Selects appropriate angle size based on beam and load.
        
        Args:
            beam_depth: Beam depth in inches
            shear_demand_kips: Required shear capacity
            
        Returns:
            Tuple of (angle_size, bolt_count, angle_length)
        """
        # Simple selection logic based on beam depth
        if beam_depth <= 8:
            angle_size = "L3x3x1/4"
            max_bolts = 3
        elif beam_depth <= 12:
            angle_size = "L4x3x3/8"
            max_bolts = 4
        elif beam_depth <= 18:
            angle_size = "L4x4x3/8"
            max_bolts = 6
        else:
            angle_size = "L5x3x3/8"
            max_bolts = 8
        
        # Estimate bolt count from shear
        # Rough: 15 kips per 3/4" A325 bolt (conservative)
        bolt_count = max(2, min(max_bolts, int(shear_demand_kips / 15) + 1))
        
        # Calculate angle length
        spacing = 3.0
        edge = 1.5
        angle_length = (bolt_count - 1) * spacing + 2 * edge
        
        return angle_size, bolt_count, angle_length
    
    @staticmethod
    def get_metadata(
        angle_size: str,
        angle_length: float,
        bolt_count: int,
        bolt_diameter: float,
        bolt_grade: str = "A325"
    ) -> Dict[str, Any]:
        """
        Returns USD metadata for the double angle connection.
        """
        if angle_size in DoubleAngleGenerator.ANGLE_SIZES:
            leg1, leg2, thickness = DoubleAngleGenerator.ANGLE_SIZES[angle_size]
        else:
            leg1, leg2, thickness = 4.0, 3.0, 0.375
        
        return {
            "generatorType": "double_angle",
            "connectionType": "DOUBLE_ANGLE",
            "angle_size": angle_size,
            "angle_length": angle_length,
            "leg_vertical": leg1,
            "leg_horizontal": leg2,
            "thickness": thickness,
            "bolts": {
                "grade": bolt_grade,
                "diameter": bolt_diameter,
                "count": bolt_count,
                "spacing": 3.0
            },
            "notes": f"Double angle: 2-{angle_size} with {bolt_count}-{bolt_diameter}\" {bolt_grade} bolts"
        }
