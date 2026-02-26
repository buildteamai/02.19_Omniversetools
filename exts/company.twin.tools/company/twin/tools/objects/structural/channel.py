# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
AISC Channel (C-Shape) Generator

Generates C-channel steel shapes using build123d per AISC specifications.
"""

import build123d as bd
from typing import Dict, Any, List, Optional
import json
import os


class ChannelGenerator:
    """
    Generator for AISC C-channel steel shapes.
    
    Creates C-channel profiles with:
    - Accurate AISC dimensions
    - Web-to-flange fillets
    - Parametric length
    - Fabrication features (bolt holes, copes)
    """
    
    @staticmethod
    def create(
        depth: float,
        flange_width: float,
        flange_thickness: float,
        web_thickness: float,
        length: float,
        fillet_radius: float = 0.25,
        features: List[Dict[str, Any]] = None
    ) -> bd.Solid:
        """
        Creates a C-channel with specified dimensions.
        
        Args:
            depth: Overall channel depth (d) in inches
            flange_width: Flange width (bf) in inches
            flange_thickness: Flange thickness (tf) in inches
            web_thickness: Web thickness (tw) in inches
            length: Channel length in inches
            fillet_radius: Fillet radius at web-flange junctions
            features: Optional fabrication features
            
        Returns:
            bd.Solid: C-channel geometry
        """
        # Create C-channel profile on XY plane
        # Channel is oriented with:
        # - Web along Y axis (vertical)
        # - Flanges extending in +X direction
        # - Extrusion along Z axis (length)
        
        half_depth = depth / 2
        
        with bd.BuildPart() as channel:
            with bd.BuildSketch(bd.Plane.XY):
                # Outer rectangle
                with bd.Locations([(flange_width / 2, 0)]):
                    bd.Rectangle(flange_width, depth)
                
                # Subtract inner cutout to create C-shape
                # Inner dimensions
                inner_width = flange_width - web_thickness
                inner_height = depth - 2 * flange_thickness
                
                with bd.Locations([(flange_width / 2 + web_thickness / 2, 0)]):
                    bd.Rectangle(inner_width, inner_height, mode=bd.Mode.SUBTRACT)
            
            bd.extrude(amount=length)
            
            # Add fillets at inside corners (web-flange junctions)
            if fillet_radius > 0:
                try:
                    # Find edges at the inside corners
                    inside_edges = []
                    for edge in channel.part.edges():
                        # Look for longitudinal edges at the web-flange junction
                        if abs(edge.length - length) < 0.01:
                            # Check if edge is at inner corner
                            center = edge.center()
                            if abs(abs(center.Y) - (half_depth - flange_thickness)) < 0.1:
                                if center.X > web_thickness / 2:
                                    inside_edges.append(edge)
                    
                    if inside_edges:
                        bd.fillet(inside_edges, radius=fillet_radius)
                except Exception as e:
                    print(f"[ChannelGenerator] Fillet failed: {e}")
        
        solid = channel.part
        
        # Apply features if specified
        if features:
            for feature in features:
                if feature.get('enabled', True):
                    solid = ChannelGenerator._apply_feature(
                        solid, feature, depth, flange_width, length
                    )
        
        return solid
    
    @staticmethod
    def _apply_feature(
        solid: bd.Solid,
        feature: Dict[str, Any],
        depth: float,
        flange_width: float,
        length: float
    ) -> bd.Solid:
        """Applies a fabrication feature to the channel."""
        feature_type = feature.get('type', '')
        
        if feature_type == 'bolt_holes':
            return ChannelGenerator._apply_bolt_holes(
                solid, feature, depth, flange_width, length
            )
        elif feature_type == 'cope':
            return ChannelGenerator._apply_cope(
                solid, feature, depth, flange_width, length
            )
        
        return solid
    
    @staticmethod
    def _apply_bolt_holes(
        solid: bd.Solid,
        feature: Dict[str, Any],
        depth: float,
        flange_width: float,
        length: float
    ) -> bd.Solid:
        """Adds bolt holes to the channel web."""
        location = feature.get('location', 'web')
        position = feature.get('position', 'end')  # 'start', 'end', 'center'
        diameter = feature.get('diameter', 0.875)
        count = feature.get('count', 2)
        spacing = feature.get('spacing', 3.0)
        
        hole_diameter = diameter + 0.0625  # Standard hole oversize
        
        # Calculate Z position (along length)
        if position == 'start':
            start_z = 2.0  # Edge distance from start
        elif position == 'end':
            start_z = length - 2.0 - (count - 1) * spacing
        else:  # center
            total_span = (count - 1) * spacing
            start_z = (length - total_span) / 2
        
        holes_solid = None
        
        for i in range(count):
            z_pos = start_z + i * spacing
            
            if location == 'web':
                # Holes in web at mid-height
                x_pos = 0
                y_pos = 0
                
                with bd.BuildPart() as hole:
                    with bd.BuildSketch(bd.Plane.YZ.offset(x_pos)):
                        with bd.Locations([(y_pos, z_pos)]):
                            bd.Circle(hole_diameter / 2)
                    bd.extrude(amount=flange_width * 2, both=True)
            else:
                # Holes in flange
                x_pos = flange_width / 2
                y_pos = depth / 2 if 'top' in location else -depth / 2
                
                with bd.BuildPart() as hole:
                    with bd.BuildSketch(bd.Plane.XZ.offset(y_pos)):
                        with bd.Locations([(x_pos, z_pos)]):
                            bd.Circle(hole_diameter / 2)
                    bd.extrude(amount=depth / 2, both=True)
            
            if holes_solid is None:
                holes_solid = hole.part
            else:
                holes_solid = holes_solid.fuse(hole.part)
        
        if holes_solid:
            return solid.cut(holes_solid)
        return solid
    
    @staticmethod
    def _apply_cope(
        solid: bd.Solid,
        feature: Dict[str, Any],
        depth: float,
        flange_width: float,
        length: float
    ) -> bd.Solid:
        """Adds a cope cut to the channel."""
        end = feature.get('end', 'start')  # 'start' or 'end'
        flange = feature.get('flange', 'top')  # 'top' or 'bottom'
        cope_depth = feature.get('depth', 2.0)  # Into web direction
        cope_height = feature.get('height', 1.5)  # Vertical
        
        # Position cope at specified end
        if end == 'start':
            z_start = -0.1
            z_end = cope_depth + 0.1
        else:
            z_start = length - cope_depth - 0.1
            z_end = length + 0.1
        
        # Calculate Y position
        half_depth = depth / 2
        if flange == 'top':
            y_start = half_depth - cope_height
            y_end = half_depth + 0.1
        else:
            y_start = -half_depth - 0.1
            y_end = -half_depth + cope_height
        
        with bd.BuildPart() as cope_cut:
            with bd.BuildSketch(bd.Plane.XY.offset(z_start)):
                with bd.Locations([(flange_width / 2, (y_start + y_end) / 2)]):
                    bd.Rectangle(flange_width + 0.2, abs(y_end - y_start))
            bd.extrude(amount=z_end - z_start)
        
        return solid.cut(cope_cut.part)
    
    @staticmethod
    def create_from_aisc(
        aisc_data: Dict[str, Any],
        length: float,
        features: List[Dict[str, Any]] = None
    ) -> bd.Solid:
        """
        Creates a channel from AISC data dictionary.
        
        Args:
            aisc_data: Dictionary with AISC dimensions
            length: Channel length in inches
            features: Optional fabrication features
            
        Returns:
            bd.Solid: Channel geometry
        """
        return ChannelGenerator.create(
            depth=aisc_data.get('depth_d', 8.0),
            flange_width=aisc_data.get('flange_width_bf', 2.26),
            flange_thickness=aisc_data.get('flange_thickness_tf', 0.39),
            web_thickness=aisc_data.get('web_thickness_tw', 0.22),
            length=length,
            fillet_radius=0.25,
            features=features
        )
    
    @staticmethod
    def load_aisc_data() -> List[Dict[str, Any]]:
        """Loads AISC channel data from JSON file."""
        # Path from objects/ up to buildteamai/data/
        # objects -> tools -> twin -> company -> company.twin.tools -> exts -> buildteamai -> data
        data_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..', '..', '..', '..', 
            'data', 'aisc_channels.json'
        )
        data_path = os.path.normpath(data_path)
        
        if os.path.exists(data_path):
            try:
                with open(data_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ChannelGenerator] Error loading AISC data: {e}")
        
        # Return default data if file not found
        print(f"[ChannelGenerator] AISC data not found at {data_path}, using defaults")
        return [
            {"designation": "C3x4.1", "depth_d": 3.0, "flange_width_bf": 1.41, "flange_thickness_tf": 0.273, "web_thickness_tw": 0.17, "weight_lb_ft": 4.1},
            {"designation": "C4x5.4", "depth_d": 4.0, "flange_width_bf": 1.58, "flange_thickness_tf": 0.296, "web_thickness_tw": 0.184, "weight_lb_ft": 5.4},
            {"designation": "C5x6.7", "depth_d": 5.0, "flange_width_bf": 1.75, "flange_thickness_tf": 0.320, "web_thickness_tw": 0.190, "weight_lb_ft": 6.7},
            {"designation": "C6x8.2", "depth_d": 6.0, "flange_width_bf": 1.92, "flange_thickness_tf": 0.343, "web_thickness_tw": 0.200, "weight_lb_ft": 8.2},
            {"designation": "C7x9.8", "depth_d": 7.0, "flange_width_bf": 2.09, "flange_thickness_tf": 0.366, "web_thickness_tw": 0.210, "weight_lb_ft": 9.8},
            {"designation": "C8x11.5", "depth_d": 8.0, "flange_width_bf": 2.26, "flange_thickness_tf": 0.390, "web_thickness_tw": 0.220, "weight_lb_ft": 11.5},
            {"designation": "C10x15.3", "depth_d": 10.0, "flange_width_bf": 2.60, "flange_thickness_tf": 0.436, "web_thickness_tw": 0.240, "weight_lb_ft": 15.3},
            {"designation": "C12x20.7", "depth_d": 12.0, "flange_width_bf": 2.94, "flange_thickness_tf": 0.501, "web_thickness_tw": 0.282, "weight_lb_ft": 20.7},
        ]
    
    @staticmethod
    def get_metadata(
        designation: str,
        length: float,
        aisc_data: Dict[str, Any],
        features: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Returns USD metadata for the channel."""
        return {
            "generatorType": "channel",
            "memberType": "C",
            "designation": designation,
            "length": length,
            "aisc_data": {
                "depth_d": aisc_data.get('depth_d'),
                "flange_width_bf": aisc_data.get('flange_width_bf'),
                "flange_thickness_tf": aisc_data.get('flange_thickness_tf'),
                "web_thickness_tw": aisc_data.get('web_thickness_tw'),
                "weight_lb_ft": aisc_data.get('weight_lb_ft')
            },
            "features": features or []
        }
