from pxr import Usd, UsdGeom, Gf, Sdf, Vt
import omni.usd

class SheetMetalPanelGenerator:
    def __init__(self):
        pass

    def create_panel(self, path: str, width: float, height: float, thickness: float, break_len: float = 2.0, return_len: float = 0.5):
        if not path:
            return
            
        stage = omni.usd.get_context().get_stage()
        if not stage:
            return

        # Validation
        # Thickness must be small enough to not self-intersect
        # Min dimension check
        if width < (return_len * 2 + thickness * 2):
            width = return_len * 2 + thickness * 2 + 1.0
        if height < (return_len * 2 + thickness * 2):
            height = return_len * 2 + thickness * 2 + 1.0
            
        # Shorthand
        W2 = width / 2.0
        H = height
        D = break_len
        R = return_len
        T = thickness
        
        # Vertices Calculation
        # We process in "rings" or layers
        
        # Layer 1: Front Face Outer (Z=0)
        # 0: BL, 1: BR, 2: TR, 3: TL
        v_front_out = [
            Gf.Vec3f(-W2, 0, 0),
            Gf.Vec3f(W2, 0, 0),
            Gf.Vec3f(W2, H, 0),
            Gf.Vec3f(-W2, H, 0)
        ]
        
        # Layer 2: Back/Depth Outer (Z=D)
        # 4: BL, 5: BR, 6: TR, 7: TL
        v_back_out = [
            Gf.Vec3f(-W2, 0, D),
            Gf.Vec3f(W2, 0, D),
            Gf.Vec3f(W2, H, D),
            Gf.Vec3f(-W2, H, D)
        ]
        
        # Layer 3: Return Edge Outer (Z=D, Inset by R)
        # 8: BL, 9: BR, 10: TR, 11: TL
        # Note: Inset applies to X and Y
        v_ret_out = [
            Gf.Vec3f(-W2 + R, R, D),
            Gf.Vec3f(W2 - R, R, D),
            Gf.Vec3f(W2 - R, H - R, D),
            Gf.Vec3f(-W2 + R, H - R, D)
        ]
        
        # Layer 4: Front Face Inner (Z=T, Inset by T approx for simple shell)
        # Strictly for miter, we inset by T perpendicular to edges.
        # Since standard box, simpler inset works.
        v_front_in = [
            Gf.Vec3f(-W2 + T, T, T),
            Gf.Vec3f(W2 - T, T, T),
            Gf.Vec3f(W2 - T, H - T, T),
            Gf.Vec3f(-W2 + T, H - T, T)
        ]
        
        # Layer 5: Back/Depth Inner (Z=D-T, Inset by T)
        # This is the inner corner of the break
        v_back_in = [
            Gf.Vec3f(-W2 + T, T, D - T),
            Gf.Vec3f(W2 - T, T, D - T),
            Gf.Vec3f(W2 - T, H - T, D - T),
            Gf.Vec3f(-W2 + T, H - T, D - T)
        ]
        
        # Layer 6: Return Edge Inner (Z=D-T, Inset by R)
        # This matches v_ret_out but at inner Z depth
        v_ret_in = [
            Gf.Vec3f(-W2 + R, R, D - T),
            Gf.Vec3f(W2 - R, R, D - T),
            Gf.Vec3f(W2 - R, H - R, D - T),
            Gf.Vec3f(-W2 + R, H - R, D - T)
        ]
        
        points = v_front_out + v_back_out + v_ret_out + v_front_in + v_back_in + v_ret_in
        
        # Indices (CCW winding for normals)
        indices = [
            # 1. Front Face Outer
            3, 2, 1, 0,
            
            # 2. Side Walls Outer
            # Bottom
            5, 4, 0, 1,
            # Right
            6, 5, 1, 2,
            # Top
            7, 6, 2, 3,
            # Left
            4, 7, 3, 0,
            
            # 3. Return Flange Outer Surface (The "Back" face trim)
            # Bottom
            9, 8, 4, 5,
            # Right
            10, 9, 5, 6,
            # Top
            11, 10, 6, 7,
            # Left
            8, 11, 7, 4,
            
            # 4. Return Flange Tips (Thickness at the gap)
            # Bottom Tip
            8, 9, 21, 20,
            # Right Tip
            9, 10, 22, 21,
            # Top Tip
            10, 11, 23, 22,
            # Left Tip
            11, 8, 20, 23,
            
            # 5. Return Flange Inner Surface (Facing Front)
            # Reverse winding of Outer
            # Bottom
            20, 21, 17, 16,
            # Right
            21, 22, 18, 17,
            # Top
            22, 23, 19, 18,
            # Left
            23, 20, 16, 19,
            
            # 6. Side Walls Inner
            # Bottom
            13, 12, 16, 17,
            # Right
            14, 13, 17, 18,
            # Top
            15, 14, 18, 19,
            # Left
            12, 15, 19, 16,
            
            # 7. Front Face Inner
            12, 13, 14, 15 
        ]
        
        # All quads
        face_vertex_counts = [4] * 22

        # Create Mesh
        mesh_path = Sdf.Path(path)
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)
        
        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexIndicesAttr(indices)
        mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
        mesh.CreateSubdivisionSchemeAttr().Set("none")
        
        # Extent
        mesh.CreateExtentAttr([
            Gf.Vec3f(-W2, 0, 0),
            Gf.Vec3f(W2, H, D)
        ])
        
        # Color
        mesh.CreateDisplayColorAttr([(0.7, 0.75, 0.8)]) # A nice bluish steel

        # ---------------------------------------------------------
        # Metadata for BOM
        # ---------------------------------------------------------
        prim = stage.GetPrimAtPath(path)
        if prim:
            custom_data = prim.GetCustomData() or {}
            custom_data['generatorType'] = 'sheet_metal_panel'
            custom_data['width'] = width
            custom_data['height'] = height
            custom_data['thickness'] = thickness
            custom_data['description'] = f"Sheet Metal Panel {width}\" x {height}\""
            # Calculate weight? 
            # Steel density ~ 0.284 lb/in^3
            # Volume approx = (W*H*T) + (Flanges...)
            # For now, just setting dimensions is good.
            # Designation
            custom_data['designation'] = f"{width}x{height}x{thickness}"
            
            prim.SetCustomData(custom_data)

        # ---------------------------------------------------------
        # Strategy 3: Semantic Attachment Points (Anchors)
        # ---------------------------------------------------------
        # We create Xforms at the center of each mating face.
        # Convention: Anchor's Z-axis points OUTWARD (Normal to face).
        # This allows a generic mating function to align -Z of Source to +Z of Target.

        # 1. Right Anchor (Normal +X)
        # Position: (W2, H/2, D/2)
        # Rotation: Y=90 (Z becomes X)
        self._create_anchor(stage, path, "Anchor_Right", 
                            Gf.Vec3d(W2, H/2.0, D/2.0), 
                            Gf.Vec3d(0, 90, 0))

        # 2. Left Anchor (Normal -X)
        # Position: (-W2, H/2, D/2)
        # Rotation: Y=-90 (Z becomes -X)
        self._create_anchor(stage, path, "Anchor_Left", 
                            Gf.Vec3d(-W2, H/2.0, D/2.0), 
                            Gf.Vec3d(0, -90, 0))

        # 3. Top Anchor (Normal +Y)
        # Position: (0, H, D/2)
        # Rotation: X=-90 (Z becomes Y)
        self._create_anchor(stage, path, "Anchor_Top", 
                            Gf.Vec3d(0, H, D/2.0), 
                            Gf.Vec3d(-90, 0, 0))

        # 4. Bottom Anchor (Normal -Y)
        # Position: (0, 0, D/2)
        # Rotation: X=90 (Z becomes -Y)
        self._create_anchor(stage, path, "Anchor_Bottom", 
                            Gf.Vec3d(0, 0, D/2.0), 
                            Gf.Vec3d(90, 0, 0))

    def _create_anchor(self, stage, parent_path, name, translate, rotate):
        anchor_path = f"{parent_path}/{name}"
        anchor = UsdGeom.Xform.Define(stage, anchor_path)
        
        # Visual Helper (Optional: Make it invisible or small)
        # For debugging, let's leave it invisible effectively (no geometry), 
        # but the prim exists.
        
        anchor.AddTranslateOp().Set(translate)
        # Rotation order: XYZ usually default
        anchor.AddRotateXYZOp().Set(rotate)

