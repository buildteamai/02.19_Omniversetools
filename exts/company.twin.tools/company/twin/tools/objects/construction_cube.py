import build123d as bd
from typing import List, Dict, Any, Tuple
from pxr import Gf

class ConstructionCubeGenerator:
    """
    Generator for Construction Line Cube.
    Creates a wireframe box with anchors at corners and mid-lines.
    """

    @staticmethod
    def create_edges(width: float, depth: float, height: float) -> List[bd.Edge]:
        """
        Creates the wireframe edges for the cube.
        
        Args:
            width (float): Dimension along X
            depth (float): Dimension along Z (following standard length/depth convention in this codebase)
            height (float): Dimension along Y
            
        Returns:
            List[bd.Edge]: The edges defining the box
        """
        # Create a box and extract edges
        # Align: CENTER for X and Z, MIN for Y (sit on ground) to match frame/rack conventions?
        # User said "Construction Line Cube". Usually cubes are centered or corner-based.
        # Let's align CENTER, CENTER, CENTER for a true "Construction Cube" unless specified otherwise.
        # Actually, standard props in this codebase often sit on ground (Y=0).
        # Let's default to Centered XY, Bottom on Z=0? 
        # Wait, codebase uses Y-up. Depth is usually Z.
        # Let's align CENTER X, MIN Y, CENTER Z to be compatible with typical "Prop" placement.
        
        print(f"[ConstructionCube] Creating edges: {width}x{height}x{depth}")
        
        with bd.BuildPart() as bp:
            bd.Box(width, height, depth, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
            
        return [e for e in bp.edges()]

    @staticmethod
    def get_anchor_definitions(width: float, depth: float, height: float) -> List[Dict[str, Any]]:
        """
        Calculates position and orientation for all anchors.
        
        Anchors:
        - 8 Corners
        - 12 Mid-lines
        - 6 Face Centers (optional but good for construction)
        
        Returns:
            List of dicts with 'name', 'translate', 'rotate', 'color'
        """
        anchors = []
        
        w2 = width / 2
        h2 = height / 2
        d2 = depth / 2
        
        # Color constants
        COLOR_CORNER = Gf.Vec3f(1.0, 0.0, 0.0) # Red
        COLOR_MID_EDGE = Gf.Vec3f(0.0, 1.0, 0.0) # Green
        COLOR_FACE = Gf.Vec3f(0.0, 0.8, 1.0) # Cyan
        
        # Helper to add anchor
        def add(name, x, y, z, rot_x=0, rot_y=0, rot_z=0, color=COLOR_CORNER):
            anchors.append({
                "name": name,
                "translate": Gf.Vec3d(x, y, z),
                "rotate": Gf.Vec3f(rot_x, rot_y, rot_z),
                "color": color
            })

        # --- CORNERS (8) ---
        # Top Corners (Y = +h2)
        add("Corner_Top_Front_Right",  w2,  h2,  d2, 0, 0, 0, COLOR_CORNER)
        add("Corner_Top_Front_Left",  -w2,  h2,  d2, 0, 0, 0, COLOR_CORNER)
        add("Corner_Top_Back_Right",   w2,  h2, -d2, 0, 0, 0, COLOR_CORNER)
        add("Corner_Top_Back_Left",   -w2,  h2, -d2, 0, 0, 0, COLOR_CORNER)
        
        # Bottom Corners (Y = -h2)
        add("Corner_Bot_Front_Right",  w2, -h2,  d2, 0, 0, 0, COLOR_CORNER)
        add("Corner_Bot_Front_Left",  -w2, -h2,  d2, 0, 0, 0, COLOR_CORNER)
        add("Corner_Bot_Back_Right",   w2, -h2, -d2, 0, 0, 0, COLOR_CORNER)
        add("Corner_Bot_Back_Left",   -w2, -h2, -d2, 0, 0, 0, COLOR_CORNER)
        
        # --- MID-EDGES (12) ---
        # Vertical Edges (4)
        add("Mid_Vert_Front_Right",  w2, 0,  d2, 0, 0, 0, COLOR_MID_EDGE)
        add("Mid_Vert_Front_Left",  -w2, 0,  d2, 0, 0, 0, COLOR_MID_EDGE)
        add("Mid_Vert_Back_Right",   w2, 0, -d2, 0, 0, 0, COLOR_MID_EDGE)
        add("Mid_Vert_Back_Left",   -w2, 0, -d2, 0, 0, 0, COLOR_MID_EDGE)
        
        # Horizontal Z Edges (4) (Top/Bot, Left/Right)
        add("Mid_HorzZ_Top_Right",  w2,  h2, 0, 0, 0, 0, COLOR_MID_EDGE)
        add("Mid_HorzZ_Top_Left",  -w2,  h2, 0, 0, 0, 0, COLOR_MID_EDGE)
        add("Mid_HorzZ_Bot_Right",  w2, -h2, 0, 0, 0, 0, COLOR_MID_EDGE)
        add("Mid_HorzZ_Bot_Left",  -w2, -h2, 0, 0, 0, 0, COLOR_MID_EDGE)
        
        # Horizontal X Edges (4) (Top/Bot, Front/Back)
        add("Mid_HorzX_Top_Front", 0,  h2,  d2, 0, 0, 0, COLOR_MID_EDGE)
        add("Mid_HorzX_Top_Back",  0,  h2, -d2, 0, 0, 0, COLOR_MID_EDGE)
        add("Mid_HorzX_Bot_Front", 0, -h2,  d2, 0, 0, 0, COLOR_MID_EDGE)
        add("Mid_HorzX_Bot_Back",  0, -h2, -d2, 0, 0, 0, COLOR_MID_EDGE)
        
        # --- FACE CENTERS (6) ---
        add("Center_Top",    0,  h2,  0,  90, 0, 0, COLOR_FACE) # Normal +Y
        add("Center_Bot",    0, -h2,  0, -90, 0, 0, COLOR_FACE) # Normal -Y
        add("Center_Front",  0,  0,  d2,   0, 0, 0, COLOR_FACE) # Normal +Z
        add("Center_Back",   0,  0, -d2, 180, 0, 0, COLOR_FACE) # Normal -Z
        add("Center_Right",  w2, 0,   0,   0, 90, 0, COLOR_FACE) # Normal +X
        add("Center_Left",  -w2, 0,   0,   0, -90, 0, COLOR_FACE) # Normal -X

        return anchors
