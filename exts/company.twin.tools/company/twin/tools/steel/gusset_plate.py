# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Gusset Plate Generator

Generates AISC-compliant gusset plate geometry for braced connections.
"""

import build123d as bd
from typing import Dict, Any, Optional, Tuple
import math


class GussetPlateGenerator:
    """
    Generates gusset plate geometry per AISC specifications.
    
    Gusset plates are used in:
    - Braced frame connections
    - Truss connections
    - Multi-member joints
    """
    
    @staticmethod
    def create_triangular(
        width: float,
        height: float,
        thickness: float,
        corner_radius: float = 0.5
    ) -> bd.Solid:
        """
        Creates a triangular gusset plate.
        
        Args:
            width: Base width in inches
            height: Height in inches
            thickness: Plate thickness in inches
            corner_radius: Radius for corner fillets
            
        Returns:
            bd.Solid: Triangular gusset plate
        """
        with bd.BuildPart() as plate:
            with bd.BuildSketch(bd.Plane.XY):
                # Triangle with right angle at origin
                with bd.BuildLine():
                    bd.Line((0, 0), (width, 0))
                    bd.Line((width, 0), (0, height))
                    bd.Line((0, height), (0, 0))
                bd.make_face()
            bd.extrude(amount=thickness)
            
            # Add corner fillets
            if corner_radius > 0:
                try:
                    bd.fillet(plate.part.edges(), radius=corner_radius)
                except:
                    pass  # Skip if fillet fails
        
        return plate.part
    
    @staticmethod
    def create_trapezoidal(
        base_width: float,
        top_width: float,
        height: float,
        thickness: float,
        corner_radius: float = 0.5
    ) -> bd.Solid:
        """
        Creates a trapezoidal gusset plate.
        
        Args:
            base_width: Bottom edge width in inches
            top_width: Top edge width in inches
            height: Height in inches
            thickness: Plate thickness in inches
            corner_radius: Radius for corner fillets
            
        Returns:
            bd.Solid: Trapezoidal gusset plate
        """
        # Calculate offset for centered trapezoid
        offset = (base_width - top_width) / 2
        
        with bd.BuildPart() as plate:
            with bd.BuildSketch(bd.Plane.XY):
                with bd.BuildLine():
                    bd.Line((0, 0), (base_width, 0))
                    bd.Line((base_width, 0), (base_width - offset, height))
                    bd.Line((base_width - offset, height), (offset, height))
                    bd.Line((offset, height), (0, 0))
                bd.make_face()
            bd.extrude(amount=thickness)
        
        return plate.part
    
    @staticmethod
    def create_with_bolt_pattern(
        width: float,
        height: float,
        thickness: float,
        bolt_diameter: float,
        bolt_rows: int,
        bolt_cols: int,
        row_spacing: float = 3.0,
        col_spacing: float = 3.0,
        edge_distance: float = 1.5
    ) -> bd.Solid:
        """
        Creates a rectangular gusset plate with bolt pattern.
        
        Args:
            width: Plate width in inches
            height: Plate height in inches
            thickness: Plate thickness in inches
            bolt_diameter: Bolt diameter in inches
            bolt_rows: Number of bolt rows
            bolt_cols: Number of bolt columns
            row_spacing: Vertical spacing between rows
            col_spacing: Horizontal spacing between columns
            edge_distance: Edge distance from bolts to plate edge
            
        Returns:
            bd.Solid: Gusset plate with bolt holes
        """
        hole_diameter = bolt_diameter + 0.0625
        
        # Create base plate
        with bd.BuildPart() as plate:
            with bd.BuildSketch(bd.Plane.XY):
                bd.Rectangle(width, height)
            bd.extrude(amount=thickness)
        
        base_solid = plate.part
        
        # Calculate bolt pattern center
        pattern_width = (bolt_cols - 1) * col_spacing
        pattern_height = (bolt_rows - 1) * row_spacing
        
        start_x = -pattern_width / 2
        start_y = -pattern_height / 2
        
        # Create holes
        holes_solid = None
        for row in range(bolt_rows):
            for col in range(bolt_cols):
                x = start_x + col * col_spacing
                y = start_y + row * row_spacing
                
                with bd.BuildPart() as hole:
                    with bd.BuildSketch(bd.Plane.XY):
                        with bd.Locations([(x, y)]):
                            bd.Circle(hole_diameter / 2)
                    bd.extrude(amount=thickness * 2, both=True)
                
                if holes_solid is None:
                    holes_solid = hole.part
                else:
                    holes_solid = holes_solid.fuse(hole.part)
        
        if holes_solid:
            result = base_solid.cut(holes_solid)
        else:
            result = base_solid
        
        return result
    
    @staticmethod
    def calculate_whitmore_width(
        weld_length: float,
        connection_length: float,
        angle_deg: float = 30.0
    ) -> float:
        """
        Calculates Whitmore effective width for gusset plate.
        
        Per AISC, the Whitmore section is a 30-degree dispersion
        from the start of the connection.
        
        Args:
            weld_length: Length of weld at connection
            connection_length: Length of connection
            angle_deg: Dispersion angle (typically 30 degrees)
            
        Returns:
            Effective width for block shear calculation
        """
        angle_rad = math.radians(angle_deg)
        dispersion = 2 * connection_length * math.tan(angle_rad)
        return weld_length + dispersion
    
    @staticmethod
    def get_metadata(
        shape: str,
        width: float,
        height: float,
        thickness: float,
        bolt_count: int = 0
    ) -> Dict[str, Any]:
        """
        Returns USD metadata for the gusset plate.
        """
        return {
            "generatorType": "gusset_plate",
            "connectionType": "GUSSET",
            "shape": shape,
            "width": width,
            "height": height,
            "thickness": thickness,
            "bolt_count": bolt_count,
            "notes": f"Gusset plate: {width}\"x{height}\"x{thickness}\""
        }
