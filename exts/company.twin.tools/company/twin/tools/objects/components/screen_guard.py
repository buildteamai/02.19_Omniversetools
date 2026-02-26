from build123d import *
from ..utils import usd_utils
import omni.usd
from pxr import UsdGeom, Sdf, UsdShade, Gf

class ScreenGuard:
    """
    Industrial Screen Guard Generator.
    Spec:
    - 1.5" x 1.5" Square Tube Posts
    - 1.5" x 1.5" Angle Iron Rails
    - Welded Wire Mesh
    - Standard Heights: 8' (96")
    - Standard Lengths: 4', 5', 8', 10'
    """

    VARIANTS = ["Standard"] # Only one variant for now, but good for structure
    FINISHES = {
        "Safety Yellow": (1.0, 0.8, 0.0),
        "Machine Gray": (0.3, 0.3, 0.35),
        "Galvanized": (0.6, 0.62, 0.65),
        "Black": (0.15, 0.15, 0.15),
    }
    
    # Standard Dimensions
    POST_SIZE = 1.5
    POST_WALL = 0.125
    RAIL_SIZE = 1.5
    RAIL_THICKNESS = 0.125
    SWEEP_GAP = 6.0
    TOP_INSET = 3.0
    MESH_THICKNESS = 0.125 # Representative thickness
    
    def __init__(self):
        pass

    @staticmethod
    def create(
        stage,
        path,
        length=96.0, # 8'
        height=96.0, # 8'
        corner_type="None", # None, Left, Right
        finish="Safety Yellow",
        include_end_post=True,
    ):
        """
        Generates a Screen Guard Panel.
        """
        try:
            # Define root Xform FIRST so it's transformable
            UsdGeom.Xform.Define(stage, path)
            
            print(f"[ScreenGuard] Creating fence: Length={length}, EndPost={include_end_post}")

            # --- Primary Panel Geometry (along Z) ---
            post_geo = ScreenGuard._generate_posts(length, height, "None", include_end_post)
            rails_geo = ScreenGuard._generate_rails(length, height, "None")
            mesh_geo = ScreenGuard._generate_mesh(length, height)
            base_plate_geo = ScreenGuard._generate_base_plates(length, "None", include_end_post)

            frame_part = post_geo + rails_geo + base_plate_geo

            # --- Corner Return Panel (along X) ---
            corner_frame = None
            corner_mesh = None
            if corner_type in ("Left", "Right"):
                # Return panel shares the start post (corner post at origin).
                # "Left" extends along -X, "Right" extends along +X.
                sign = -1.0 if corner_type == "Left" else 1.0
                ret_post, ret_rails, ret_mesh, ret_plates = ScreenGuard._generate_corner_return(
                    length, height, sign
                )
                corner_frame = ret_post + ret_rails + ret_plates
                corner_mesh = ret_mesh

            # --- Export Frame ---
            frame_path = f"{path}/Frame"
            if corner_frame is not None:
                total_frame = Compound(children=[frame_part, corner_frame])
            else:
                total_frame = frame_part
            usd_utils.create_mesh_from_shape(stage, frame_path, total_frame)

            # --- Export Mesh ---
            mesh_path = f"{path}/Screen"
            if corner_mesh is not None:
                total_mesh = Compound(children=[mesh_geo, corner_mesh])
            else:
                total_mesh = mesh_geo
            usd_utils.create_mesh_from_shape(stage, mesh_path, total_mesh)

            # --- Apply Materials ---
            mat_type = "Metal" if finish == "Galvanized" else "Plastic"
            ScreenGuard._apply_material(stage, frame_path, finish, material_type=mat_type)
            ScreenGuard._apply_material(stage, mesh_path, "Black", material_type="Mesh")

            # Set Metadata on Root
            root_prim = stage.GetPrimAtPath(path)
            
            root_prim.CreateAttribute("custom:length", Sdf.ValueTypeNames.Double).Set(length)
            root_prim.CreateAttribute("custom:height", Sdf.ValueTypeNames.Double).Set(height)
            root_prim.CreateAttribute("custom:corner_type", Sdf.ValueTypeNames.String).Set(corner_type)
            root_prim.CreateAttribute("custom:finish", Sdf.ValueTypeNames.String).Set(finish)
            root_prim.CreateAttribute("custom:include_end_post", Sdf.ValueTypeNames.Bool).Set(include_end_post)
            root_prim.CreateAttribute("custom:type", Sdf.ValueTypeNames.String).Set("SafetyFence")

            return root_prim

        except Exception as e:
            print(f"[ScreenGuard] Error generating geometry: {e}")
            import traceback; traceback.print_exc()
            return None

    # ------------------------------------------------------------------
    # Geometry Helpers
    # ------------------------------------------------------------------
    
    @staticmethod
    def _generate_posts(length, height, corner_type, include_end_post=True):
        s = ScreenGuard.POST_SIZE
        t = ScreenGuard.POST_WALL
        
        # Post Profile (Square Tube)
        # Vertical Post: Extrude along Y.
        # Sketch on Plane.ZX (Normal Y).
        
        with BuildSketch(Plane.ZX) as sk:
            Rectangle(s, s)
            Rectangle(s - 2*t, s - 2*t, mode=Mode.SUBTRACT)
        
        # Start Post (at 0,0,0)
        post_start = extrude(sk.sketch, amount=height)
        
        if include_end_post:
            # End Post - Regenerate to avoid duplicate node error
            post_end = extrude(sk.sketch, amount=height).move(Location((0, 0, length)))
            return Compound(children=[post_start, post_end])
        else:
            return post_start

    @staticmethod
    def _generate_rails(length, height, corner_type):
        # Rails run along Z (Horizontal).
        # Sketch should be on Plane.XY (Normal Z).
        
        s = ScreenGuard.RAIL_SIZE
        t = ScreenGuard.RAIL_THICKNESS
        p_s = ScreenGuard.POST_SIZE
        
        rail_len = length - p_s 
        
        # Top Rail
        top_y = height - ScreenGuard.TOP_INSET - s 
        bot_y = ScreenGuard.SWEEP_GAP
        
        def angle_sketch(y_pos, rotation=0):
             # Sketch on XY plane.
             # Origin relative to Plane.XY.offset(p_s/2).
             # We want rail to start at z = p_s/2.
             
             with BuildSketch(Plane.XY.offset(p_s/2)) as sk:
                 with Locations(Location((0, y_pos), rotation)): 
                     # Sketch X (Width) loops -s/2 to s/2.
                     
                     x0 = -s/2
                     y0 = 0
                     
                     Polygon(
                         (x0, y0), 
                         (x0+s, y0), 
                         (x0+s, y0+t), 
                         (x0+t, y0+t), 
                         (x0+t, y0+s), 
                         (x0, y0+s),
                         align=None
                     )
             return sk.sketch

        sk_top = angle_sketch(top_y, rotation=-90)
        top_rail = extrude(sk_top, amount=rail_len)
        
        sk_bot = angle_sketch(bot_y)
        bot_rail = extrude(sk_bot, amount=rail_len)

        return top_rail + bot_rail

    @staticmethod
    def _generate_mesh(length, height):
        p_s = ScreenGuard.POST_SIZE
        s = ScreenGuard.RAIL_SIZE
        
        h_start = ScreenGuard.SWEEP_GAP + s
        h_end = height - ScreenGuard.TOP_INSET - s
        mesh_h = h_end - h_start
        mesh_l = length - p_s
        
        # Generate Wire Grid (Local X-Y plane)
        grid = ScreenGuard._generate_wire_grid(mesh_l, mesh_h)
        
        # Orient for Main Panel:
        # Grid is X-Y. We want Z-Y.
        # Rotate 90 around Y? X->Z.
        # Grid Origin (0,0,0) -> (Mesh Start Z, Mesh Start Y, 0)?
        
        # Our grid generation creates it starting at (0,0).
        # We want it at (X=0, Y=h_start, Z=p_s/2).
        # Rotation(0, 90, 0) transforms X->Z, Y->Y, Z->X.
        
        grid = grid.rotate(Axis.Y, -90)
        grid = grid.move(Location((0, h_start, p_s/2)))
        
        return grid

    @staticmethod
    def _generate_wire_grid(width, height):
        """
        Generates a 2" x 2" wire grid on the X-Y plane.
        Origin at (0,0). Extends to (width, height).
        """
        wire_r = 0.0625 # 1/8" dia
        grid_sz = 2.0
        
        nx = int(width / grid_sz) + 1
        ny = int(height / grid_sz) + 1
        
        wires = []
        
        # Vertical Wires (along Y) at X intervals
        for i in range(nx):
            x_pos = i * grid_sz
            if x_pos > width: break
            wire = Cylinder(wire_r, height, align=(Align.CENTER, Align.CENTER, Align.MIN), rotation=(-90, 0, 0))
            wire = wire.move(Location((x_pos, 0, 0)))
            wires.append(wire)
            
        # Horizontal Wires (along X) at Y intervals
        for j in range(ny):
            y_pos = j * grid_sz
            if y_pos > height: break
            wire = Cylinder(wire_r, width, align=(Align.CENTER, Align.CENTER, Align.MIN), rotation=(0, 90, 0))
            wire = wire.move(Location((0, y_pos, 0)))
            wires.append(wire)
            
        return Compound(children=wires)

    @staticmethod
    def _generate_base_plates(length, corner_type, include_end_post=True):
        # 6"x6" x 0.25" plate at bottom of each post.
        bs = 6.0
        bt = 0.25
        
        # Plate on Floor (Plane.ZX)
        with BuildSketch(Plane.ZX) as sk:
            Rectangle(bs, bs)
            
        # Start Plate
        p1 = extrude(sk.sketch, amount=bt)
        
        if include_end_post:
            # End Plate - Regenerate to avoid duplicate node error
            p2 = extrude(sk.sketch, amount=bt).move(Location((0, 0, length)))
            return Compound(children=[p1, p2])
        else:
            return p1

    @staticmethod
    def _generate_corner_return(length, height, sign):
        """
        Generates a perpendicular return panel along the X-axis.
        sign: -1.0 for Left, +1.0 for Right.
        The corner post at origin is shared with the main panel.
        """
        s = ScreenGuard.POST_SIZE
        t = ScreenGuard.POST_WALL
        p_s = s
        rail_s = ScreenGuard.RAIL_SIZE
        rail_t = ScreenGuard.RAIL_THICKNESS
        rail_len = length - p_s

        # --- Return Post (at x = sign*length, z=0) ---
        with BuildSketch(Plane.ZX) as sk:
            Rectangle(s, s)
            Rectangle(s - 2*t, s - 2*t, mode=Mode.SUBTRACT)
        ret_post = extrude(sk.sketch, amount=height)
        ret_post = ret_post.move(Location((sign * length, 0, 0)))

        # --- Return Rails (along X) ---
        # Sketch on YZ plane (Normal X).
        # Plane.YZ normal is +X.  For sign=-1 we need to go -X.
        top_y = height - ScreenGuard.TOP_INSET - rail_s
        bot_y = ScreenGuard.SWEEP_GAP

        def x_angle_sketch(y_pos, rotation=0):
            with BuildSketch(Plane.YZ.offset(p_s/2 * sign)) as sk:
                with Locations(Location((0, y_pos), rotation)):
                    x0 = -rail_s/2
                    y0 = 0
                    Polygon(
                        (x0, y0),
                        (x0+rail_s, y0),
                        (x0+rail_s, y0+rail_t),
                        (x0+rail_t, y0+rail_t),
                        (x0+rail_t, y0+rail_s),
                        (x0, y0+rail_s),
                        align=None
                    )
            return sk.sketch

        sk_top = x_angle_sketch(top_y, rotation=-90)
        top_rail = extrude(sk_top, amount=sign * rail_len)

        sk_bot = x_angle_sketch(bot_y)
        bot_rail = extrude(sk_bot, amount=sign * rail_len)

        ret_rails = top_rail + bot_rail

        # --- Return Mesh ---
        h_start = ScreenGuard.SWEEP_GAP + rail_s
        h_end = height - ScreenGuard.TOP_INSET - rail_s
        mesh_h = h_end - h_start
        mesh_l = length - p_s

        # Grid X-Y
        grid = ScreenGuard._generate_wire_grid(mesh_l, mesh_h)
        
        # Orient:
        # Main Grid was Z-Y.
        # Return Grid is X-Y. (Along X).
        # If sign > 0: +X. Grid fits perfectly (Starts 0, ends mesh_l).
        # We move it to (p_s/2, h_start, 0).
        # If sign < 0: -X. Grid needs to go -X.
        # Rotate 180 around Y? No, Grid is symmetric mostly but origin matter.
        # Grid (0 to L). We want (0 to -L).
        # Rotate Z 180? (X->-X, Y->-Y). bad.
        # Rotate Y 180? (X->-X, Z->-Z). OK.
        
        if sign > 0:
            grid = grid.move(Location((p_s/2, h_start, 0)))
        else:
             # Rotate 180 around Y so X -> -X.
             # Origin (0,0) -> (0,0). box (L, H) -> (-L, H).
             # We want it to start at -p_s/2 and go -L.
             grid = grid.rotate(Axis.Y, 180)
             grid = grid.move(Location((-p_s/2, h_start, 0)))

        # --- Return Base Plate ---
        bs = 6.0
        bt = 0.25
        with BuildSketch(Plane.ZX) as sk:
            Rectangle(bs, bs)
        ret_plate = extrude(sk.sketch, amount=bt)
        ret_plate = ret_plate.move(Location((sign * length, 0, 0)))

        return ret_post, ret_rails, grid, ret_plate

    @staticmethod
    def _apply_material(stage, path, finish, material_type="Plastic"):
        """
        Creates/updates a USD material and binds it to the prim at path.
        """
        color = ScreenGuard.FINISHES.get(finish, (0.5, 0.5, 0.5))

        looks_path = "/Looks"
        if not stage.GetPrimAtPath(looks_path):
            stage.DefinePrim(looks_path, "Scope")

        mat_name = finish.replace(" ", "")
        if material_type == "Mesh":
            mat_name += "_Mesh"

        mat_path = f"{looks_path}/{mat_name}"

        # Always (re)create shader to ensure correct properties
        mat = UsdShade.Material.Define(stage, mat_path)
        shader_path = f"{mat_path}/PBRShader"
        pbr = UsdShade.Shader.Define(stage, shader_path)
        pbr.CreateIdAttr("UsdPreviewSurface")

        pbr.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))

        if material_type == "Metal":
            pbr.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.8)
            pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.3)
        elif material_type == "Mesh":
            # Solid Mesh (Wires)
            pbr.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(1.0)
            pbr.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
            pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.8)
        else:  # Plastic / Paint
            pbr.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.1)
            pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.35)

        # Connect shader -> material surface output
        out = mat.CreateSurfaceOutput()
        out.ConnectToSource(UsdShade.ConnectableAPI(pbr.GetPrim()), "surface")

        # Bind with strong binding
        prim = stage.GetPrimAtPath(path)
        if prim:
            binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
            binding_api.Bind(mat, bindingStrength=UsdShade.Tokens.strongerThanDescendants)
