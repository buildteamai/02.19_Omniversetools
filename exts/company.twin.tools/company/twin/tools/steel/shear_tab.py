# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Shear Tab (Single Plate) Connection Generator

Generates AISC-compliant shear tab connection geometry using build123d.
"""

import build123d as bd
from typing import Dict, Any, List, Optional
import math

from .connection_rules import (
    ConnectionRules,
    ConnectionDesign,
    BoltSpec,
    PlateSpec,
    WeldSpec,
    get_connection_rules
)


class ShearTabGenerator:
    """
    Generates shear tab connection geometry per AISC specifications.
    
    A shear tab is a single plate:
    - Shop-welded to supporting member (column or girder)
    - Field-bolted to supported beam web
    """
    
    @staticmethod
    def create(
        plate_width: float,
        plate_height: float,
        plate_thickness: float,
        bolt_diameter: float,
        bolt_count: int,
        bolt_spacing: float = 3.0,
        edge_distance_vertical: float = 1.5,
        edge_distance_horizontal: float = 2.0,
        weld_to_bolt_distance: float = 3.0
    ) -> bd.Solid:
        """
        Creates a shear tab plate with bolt holes.
        
        Args:
            plate_width: Width of plate (weld line to edge) in inches
            plate_height: Height of plate in inches
            plate_thickness: Plate thickness in inches
            bolt_diameter: Bolt diameter in inches
            bolt_count: Number of bolts
            bolt_spacing: Vertical spacing between bolts in inches
            edge_distance_vertical: Vertical edge distance in inches
            edge_distance_horizontal: Horizontal edge distance in inches
            weld_to_bolt_distance: Distance from weld line to bolt center
            
        Returns:
            bd.Solid: Shear tab plate geometry
        """
        # Get standard hole size (1/16" oversize for standard holes)
        hole_diameter = bolt_diameter + 0.0625
        
        # Create base plate
        with bd.BuildPart() as plate:
            with bd.BuildSketch():
                bd.Rectangle(plate_width, plate_height)
            bd.extrude(amount=plate_thickness)
        
        base_solid = plate.part
        
        # Calculate bolt hole positions
        # Bolts are centered at weld_to_bolt_distance from weld edge
        # Weld edge is at -plate_width/2
        bolt_x = -plate_width / 2 + weld_to_bolt_distance
        
        # Vertical distribution - centered on plate
        total_bolt_span = (bolt_count - 1) * bolt_spacing
        first_bolt_y = -total_bolt_span / 2
        
        # Create bolt holes
        holes_solid = None
        for i in range(bolt_count):
            bolt_y = first_bolt_y + i * bolt_spacing
            
            with bd.BuildPart() as hole:
                with bd.BuildSketch(bd.Plane.XY.offset(0)):
                    with bd.Locations([(bolt_x, bolt_y)]):
                        bd.Circle(hole_diameter / 2)
                bd.extrude(amount=plate_thickness * 2, both=True)
            
            if holes_solid is None:
                holes_solid = hole.part
            else:
                holes_solid = holes_solid.fuse(hole.part)
        
        # Subtract holes from plate
        if holes_solid:
            result = base_solid.cut(holes_solid)
        else:
            result = base_solid
        
        return result
    
    @staticmethod
    def create_from_design(design: ConnectionDesign) -> bd.Solid:
        """
        Creates shear tab from ConnectionDesign output.
        
        Args:
            design: ConnectionDesign from ConnectionRules.design_shear_tab()
            
        Returns:
            bd.Solid: Shear tab geometry
        """
        if design.plate is None:
            raise ValueError("ConnectionDesign has no plate specification")
        
        return ShearTabGenerator.create(
            plate_width=design.plate.width,
            plate_height=design.plate.height,
            plate_thickness=design.plate.thickness,
            bolt_diameter=design.bolts.diameter,
            bolt_count=design.bolts.count,
            bolt_spacing=design.bolts.spacing,
            edge_distance_vertical=design.bolts.edge_distance
        )
    
    @staticmethod
    def create_for_beam(
        beam_depth: float,
        shear_demand_kips: float = 30.0,
        bolt_diameter: float = 0.75,
        bolt_grade: str = "A325"
    ) -> tuple:
        """
        Creates a shear tab sized for a specific beam.
        
        Args:
            beam_depth: Depth of beam being connected
            shear_demand_kips: Required shear capacity
            bolt_diameter: Bolt diameter
            bolt_grade: Bolt specification
            
        Returns:
            tuple: (bd.Solid geometry, ConnectionDesign)
        """
        rules = get_connection_rules()
        design = rules.design_shear_tab(
            beam_depth=beam_depth,
            shear_demand_kips=shear_demand_kips,
            bolt_diameter=bolt_diameter,
            bolt_grade=bolt_grade
        )
        
        geometry = ShearTabGenerator.create_from_design(design)
        
        return geometry, design
    
    @staticmethod
    def get_metadata(design: ConnectionDesign) -> Dict[str, Any]:
        """
        Returns USD metadata for the shear tab connection.
        
        Args:
            design: ConnectionDesign specification
            
        Returns:
            Dictionary of metadata for USD customData
        """
        metadata = {
            "generatorType": "shear_tab",
            "connectionType": "SHEAR_TAB",
            "plate": {
                "width": design.plate.width,
                "height": design.plate.height,
                "thickness": design.plate.thickness
            },
            "bolts": {
                "grade": design.bolts.grade,
                "diameter": design.bolts.diameter,
                "count": design.bolts.count,
                "spacing": design.bolts.spacing
            },
            "is_valid": design.is_valid,
            "notes": design.notes
        }
        
        if design.weld:
            metadata["weld"] = {
                "electrode": design.weld.electrode,
                "size": design.weld.size,
                "length": design.weld.length
            }
        
        if design.warnings:
            metadata["warnings"] = design.warnings
        
        return metadata
