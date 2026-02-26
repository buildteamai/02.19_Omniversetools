from build123d import *
from ..utils import usd_utils
import omni.usd
from pxr import UsdGeom, Sdf, Gf


class Trapeze:
    """MEP Trapeze Hanger generator.

    Assembly (Y-Up):
        - Strut channel runs along **Z-axis**, centered at origin.
        - Two threaded rods extend in **+Y** at Z = ±span/2.
        - Hardware (nut + washer) sandwiches the strut channel.
          - Upper Nut + Washer above the web (ceiling side).
          - Lower Washer + Nut below the opening (floor side).
    """

    @staticmethod
    def create(
        stage,
        path,
        span=24.0,
        cantilever=2.0,
        drop_length=36.0,
        rod_diameter=0.5,
        strut_width=1.625,
        strut_height=1.625,
        strut_gauge="12 Ga",
    ):
        GAUGE_MAP = {
            "16 Ga": 0.0598,
            "14 Ga": 0.0747,
            "12 Ga": 0.1046,
            "10 Ga": 0.1345,
        }
        thickness = GAUGE_MAP.get(strut_gauge, 0.1046)

        # Hardware sizing (visual approximations)
        nut_height = rod_diameter * 0.8
        nut_width = rod_diameter * 1.75
        # Ensure washer is wider than the strut to clearly show support (shelf)
        washer_side = max(rod_diameter * 3.0, strut_width + 0.25)
        washer_thick = 0.125

        strut_length = span + 2.0 * cantilever
        w = strut_width
        h = strut_height
        t = thickness

        try:
            # ---- Build each component as a standalone Part ----

            # 1. STRUT — U-channel profile in XY, extruded along Z
            #    Opening faces DOWN (-Y), web (closed back) on TOP at Y = h
            with BuildPart() as strut_bp:
                with BuildSketch(Plane.XY):
                    Polygon([
                        (-w / 2,  0),          # open edge left
                        (-w / 2,  h),          # top left (web)
                        ( w / 2,  h),          # top right (web)
                        ( w / 2,  0),          # open edge right
                        ( w / 2 - t,  0),      # inner open edge right
                        ( w / 2 - t,  h - t),  # inner top right
                        (-w / 2 + t,  h - t),  # inner top left
                        (-w / 2 + t,  0),      # inner open edge left
                    ])
                extrude(amount=strut_length / 2.0, both=True)

            strut = strut_bp.part

            # 2. CLEARANCE HOLES IN STRUT (for rods)
            # Create cylinders where rods will pass through to avoid clash/mating issues
            rod_z_positions = [-span / 2.0, span / 2.0]
            
            for rz in rod_z_positions:
                hole = Cylinder(radius=rod_diameter / 2.0 * 1.05, height=h * 3.0) # slightly larger than rod
                # Cylinder defaults along Z; rotate to Y
                hole = hole.rotate(Axis.X, 90)
                hole = hole.translate((0, h / 2.0, rz))
                strut = strut - hole
            
            assembly = strut

            # 3. RODS + Single Upper Washer (per user request)
            #    Rods extend vertically along Y axis (Upward).
            #    Washer sits on TOP of the Strut (Y = h).
            
            # Bottom of rod: 2" below strut bottom (Y=0)
            rod_bottom_y = -2.0
            rod_total_height = drop_length - rod_bottom_y
            
            rod_y_center = rod_bottom_y + rod_total_height / 2.0
            
            # Washer Logic:
            # Box centered at (0,0,0).
            # Height = washer_thick.
            # We want Bottom Face at Y = h.
            # Center Y needs to be h + washer_thick/2.
            washer_y_center = h / 2.0  + washer_thick / 2.0

            for rz in rod_z_positions:
                # CLEARANCE HOLE in Strut
                hole = Cylinder(radius=rod_diameter/2 * 1.05, height=h*3)
                hole = hole.rotate(Axis.X, -90)
                hole = hole.translate((0, h/2, rz))
                assembly = assembly - hole
                
                # ROD
                rod = Cylinder(radius=rod_diameter/2, height=rod_total_height)
                rod = rod.rotate(Axis.X, -90)
                rod = rod.translate((0, rod_y_center, rz))
                assembly = assembly.fuse(rod)
                
                # UPPER WASHER
                # Standard Box is centered.
                washer = Box(washer_side, washer_thick, washer_side)
                washer = washer.translate((0, washer_y_center, rz))
                assembly = assembly.fuse(washer)

                # LOWER WASHER
                # User edited position: -washer_thick/2 - h/2
                lower_washer_y_center = -washer_thick / 2.0 - h / 2.0
                l_washer = Box(washer_side, washer_thick, washer_side)
                l_washer = l_washer.translate((0, lower_washer_y_center, rz))
                assembly = assembly.fuse(l_washer)

                # UPPER NUT
                # Sits on top of Upper Washer.
                # Top Washer Top Face = washer_y_center + washer_thick/2
                # Nut Center = Top Face + nut_height/2
                upper_nut_center = washer_y_center + washer_thick / 2.0 + nut_height / 2.0
                u_nut = Box(nut_width, nut_height, nut_width)
                u_nut = u_nut.translate((0, upper_nut_center, rz))
                assembly = assembly.fuse(u_nut)

                # LOWER NUT
                # Sits below Lower Washer.
                # Lower Washer Bottom Face = lower_washer_y_center - washer_thick/2
                # Nut Center = Bottom Face - nut_height/2
                lower_nut_center = lower_washer_y_center - washer_thick / 2.0 - nut_height / 2.0
                l_nut = Box(nut_width, nut_height, nut_width)
                l_nut = l_nut.translate((0, lower_nut_center, rz))
                assembly = assembly.fuse(l_nut)

            # ---- Export to USD ----
            mesh_prim = usd_utils.create_mesh_from_shape(stage, path, assembly)

            if mesh_prim:
                prim = mesh_prim.GetPrim()
                prim.CreateAttribute("custom:span", Sdf.ValueTypeNames.Double).Set(span)
                prim.CreateAttribute("custom:drop_length", Sdf.ValueTypeNames.Double).Set(drop_length)
                prim.CreateAttribute("custom:rod_diameter", Sdf.ValueTypeNames.Double).Set(rod_diameter)
                prim.CreateAttribute("custom:strut_length", Sdf.ValueTypeNames.Double).Set(strut_length)
                prim.CreateAttribute("custom:generatorType", Sdf.ValueTypeNames.String).Set("Trapeze")

            return mesh_prim

        except Exception as e:
            print(f"[Trapeze] Error generating geometry: {e}")
            import traceback
            traceback.print_exc()
            return None
