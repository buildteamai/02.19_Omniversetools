import build123d as bd
from typing import Dict, Any, Tuple, List
from .wide_flange import WideFlangeGenerator

class FrameSkeleton:
    """
    Holds the wireframe topology of the frame.
    Simple container for Edges.
    """
    def __init__(self):
        self.edges: Dict[str, bd.Edge] = {}

class FrameGenerator:
    """
    Generator for Structural Steel Frames using Skeleton-based design.
    """
    
    @staticmethod
    def create_simple_frame(
        column_section: Dict[str, Any],
        header_section: Dict[str, Any],
        width: float,
        height: float,
        base_plate_size: Tuple[float, float, float] = (12.0, 12.0, 0.75),
        rotate_columns: bool = False,
    ) -> Dict[str, Any]:
        """
        Creates a frame by first defining a skeleton, then skinning it with profiles.
        """
        bp_len, bp_wid, bp_thk = base_plate_size
        col_depth = column_section['depth_d']
        header_depth = header_section['depth_d']
        
        # 1. Create Skeleton (Wireframe)
        # -----------------------------
        # Columns run FULL HEIGHT from base plate to cube corner (continuous members).
        # Header beam fits between columns at the top.
        
        col_top_y = height  # Full height — matches cube corner nodes
        header_center_y = height - (header_depth / 2)  # Header hangs from top
        
        skeleton = FrameSkeleton()
        
        # Left Column Line: Full height
        skeleton.edges['column_left'] = bd.Edge.make_line(
            bd.Vector(-width/2, bp_thk, 0),
            bd.Vector(-width/2, col_top_y, 0)
        )
        
        # Right Column Line: Full height
        skeleton.edges['column_right'] = bd.Edge.make_line(
            bd.Vector(width/2, bp_thk, 0),
            bd.Vector(width/2, col_top_y, 0)
        )
        
        # Header Line (Horizontal) — top of frame, between columns
        skeleton.edges['header'] = bd.Edge.make_line(
            bd.Vector(-width/2, header_center_y, 0),
            bd.Vector(width/2, header_center_y, 0)
        )
        
        # 2. Skin Skeleton (Create Geometry)
        # ----------------------------------
        parts = {}
        transforms = {}
        anchors = {}
        
        # Base Plates (Simple placement relative to skeleton start points)
        base_plate = bd.Box(
            bp_len, bp_thk, bp_wid,
            align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.CENTER)
        )
        
        # Left BP
        parts['base_plate_left'] = base_plate
        transforms['base_plate_left'] = bd.Location((-width/2, 0, 0))
        anchors['base_plate_left'] = {
             'bottom_face': (-width / 2, 0.0, 0.0),
             'top_face':    (-width / 2, bp_thk, 0.0),
        }

        # Right BP
        parts['base_plate_right'] = base_plate
        transforms['base_plate_right'] = bd.Location((width/2, 0, 0))
        anchors['base_plate_right'] = {
             'bottom_face': (width / 2, 0.0, 0.0),
             'top_face':    (width / 2, bp_thk, 0.0),
        }
        
        # Skin Columns
        for side in ['left', 'right']:
            edge_name = f'column_{side}'
            edge = skeleton.edges[edge_name]
            
            # Vector math for orientation
            tangent = edge.tangent_at(0) # Should be (0, 1, 0) - UP
            
            # Rotation Logic: Explicit Euler Angles (Simple Frame Assumption)
            # Standard Column (Upright): Rotation(-90, 0, 0)
            # Rotated Column (Web along X): Rotation(-90, 0, 0) * Rotation(0, 0, 90)
            # (Spin 90 deg around local Z first, then -90 around Global X to stand up)
            
            if rotate_columns:
                rot = bd.Rotation(-90, 0, 0) * bd.Rotation(0, 0, 90)
            else:
                rot = bd.Rotation(-90, 0, 0)
                
            # Create Location at start of edge with explicit rotation
            loc = bd.Location(edge.position_at(0).to_tuple()) * rot
            
            # Generate geometry length based on edge length
            length = edge.length
            
            # Create Solid (Standard Z-extrusion)
            col_solid = WideFlangeGenerator.create_from_aisc(column_section, length)
            
            # Assign to parts and set transform
            parts[edge_name] = col_solid
            transforms[edge_name] = loc
            
            # Anchors
            anchors[edge_name] = {
                'start': edge.position_at(0).to_tuple(),
                'end': edge.position_at(1).to_tuple()
            }

        # Skin Header
        # -----------
        h_edge = skeleton.edges['header']
        
        # Calculate Trimmed Length (Skeleton Length - ColDepth - Gap)
        # 1/2" gap each side.
        clearance = 0.5
        raw_length = h_edge.length
        final_len = raw_length - col_depth - (2 * clearance)
        
        # Create Center-Aligned Solid
        # WideFlangeGenerator creates from Z=0 to Z=L.
        header_solid = WideFlangeGenerator.create_from_aisc(header_section, final_len)
        # Center it along Z so origin refers to midpoint
        header_solid = header_solid.move(bd.Location((0, 0, -final_len/2)))
        
        # Header Orientation: Explicit Euler
        # Horizontal along X. World Z -> World X. 
        # Rotation(0, 90, 0) maps Z->X.
        h_rot = bd.Rotation(0, 90, 0)
        
        # Location is CENTER of the beam (since we centered the solid)
        h_loc = bd.Location(h_edge.center().to_tuple()) * h_rot
        
        parts['header'] = header_solid
        transforms['header'] = h_loc
        
        # Calculate actual start/end points for anchors
        # Start is Origin - (Length/2 * Tangent)
        # End is Origin + (Length/2 * Tangent)
        center = h_edge.center()
        h_tangent = h_edge.tangent_at(0)
        offset = h_tangent * (final_len / 2)
        
        anchors['header'] = {
            'start': (center - offset).to_tuple(),
            'end':   (center + offset).to_tuple(),
        }

        # Metadata
        return {
            'parts': parts,
            'transforms': transforms,
            'anchors': anchors,
            'metadata': {
                'width': width,
                'height': height,
                'header_length': final_len,
                'col_length': col_top_y - bp_thk
            }
        }
