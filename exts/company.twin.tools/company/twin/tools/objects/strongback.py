from build123d import *
from ..utils import usd_utils
import omni.usd
from pxr import UsdGeom, Sdf

class Strongback:
    """Strongback generator with multiple cross-section variants."""

    VARIANTS = ["C-Channel", "Strongback", "Stiffener Post"]

    GAUGE_MAP = {
        "16 Ga": 0.0598,
        "14 Ga": 0.0747,
        "12 Ga": 0.1046,
        "10 Ga": 0.1345,
    }
    GAUGE_OPTIONS = list(GAUGE_MAP.keys())

    def __init__(self):
        pass

    @staticmethod
    def create(
        stage,
        path,
        length=24.0,
        width=8.0,
        height=4.0,
        thickness=0.125,
        variant="C-Channel",
        left_height=2.0,
        flange_width=1.0,
        # Stiffener Post params
        leg_depth=2.0,
        return_flange=1.0,
        gauge="14 Ga",
        end_cap_thickness=0.125,
    ):
        """
        Generates a Strongback and adds it to the USD stage.

        Args:
            stage:  USD stage
            path:   Prim path
            length: Extrusion length (in)
            width:  Overall profile width / face width (in)
            height: Overall profile height (in)
            thickness: Wall thickness (in)
            variant: Profile variant
            left_height: Height of the short left wall (Strongback only)
            flange_width: Width of the top flange (Strongback only)
            leg_depth: Depth of symmetrical legs (Stiffener Post only)
            return_flange: Width of inward return flange (Stiffener Post only)
            gauge: Steel gauge – determines wall thickness (Stiffener Post only)
            end_cap_thickness: Thickness of welded end cap plates (Stiffener Post only)
        """
        try:
            with BuildPart() as bp:
                # --- Build profile sketch ---
                if variant == "Stiffener Post":
                    wall_t = Strongback.GAUGE_MAP.get(gauge, 0.0747)
                    with BuildSketch(Plane.XZ):
                        Strongback._create_stiffener_post_profile(
                            width, leg_depth, return_flange, wall_t,
                        )
                    extrude(amount=length)

                    # --- End cap plates ---
                    if end_cap_thickness > 0:
                        # Cap at y = 0
                        with BuildSketch(Plane.XZ):
                            Rectangle(width, leg_depth,
                                      align=(Align.MIN, Align.MIN))
                        extrude(amount=end_cap_thickness)
                        # Cap at y = length
                        with BuildSketch(Plane.XZ.offset(length - end_cap_thickness)):
                            Rectangle(width, leg_depth,
                                      align=(Align.MIN, Align.MIN))
                        extrude(amount=end_cap_thickness)

                elif variant == "Strongback":
                    with BuildSketch(Plane.XZ):
                        Strongback._create_strongback_profile(
                            width, height, left_height,
                            flange_width, thickness,
                        )
                    extrude(amount=length)

                else:
                    with BuildSketch(Plane.XZ):
                        Strongback._create_c_channel_profile(
                            width, height, thickness,
                        )
                    extrude(amount=length)

            # --- Export to USD ---
            mesh_prim = usd_utils.create_mesh_from_shape(stage, path, bp.part)

            if mesh_prim:
                prim = mesh_prim.GetPrim()
                prim.CreateAttribute("custom:length", Sdf.ValueTypeNames.Double).Set(length)
                prim.CreateAttribute("custom:width", Sdf.ValueTypeNames.Double).Set(width)
                prim.CreateAttribute("custom:height", Sdf.ValueTypeNames.Double).Set(height)
                prim.CreateAttribute("custom:type", Sdf.ValueTypeNames.String).Set("Strongback")
                prim.CreateAttribute("custom:variant", Sdf.ValueTypeNames.String).Set(variant)
                if variant == "Stiffener Post":
                    prim.CreateAttribute("custom:gauge", Sdf.ValueTypeNames.String).Set(gauge)

            return mesh_prim

        except Exception as e:
            print(f"[Strongback] Error generating geometry: {e}")
            import traceback; traceback.print_exc()
            return None

    # ------------------------------------------------------------------
    # Profile helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_c_channel_profile(width, height, thickness):
        """Original C-Channel (open-top U shape).

        Uses Polygon (sketch-level primitive) to avoid BuildLine/make_face issues.
        """
        t = thickness
        # Outer U shape
        Polygon(
            (0, height),
            (0, 0),
            (width, 0),
            (width, height),
            align=None,
        )
        # Inner U cutout
        Polygon(
            (t, height),
            (width - t, height),
            (width - t, t),
            (t, t),
            align=None,
            mode=Mode.SUBTRACT,
        )

    @staticmethod
    def _create_strongback_profile(width, height, left_height, flange_width, thickness):
        """
        Asymmetric strongback profile derived from reference polyline:

            (0, lh)                      (w-fw, h)──(w, h)
               │                             │          │
               │   (open edge)               │          │
               │                             │          │
            (0, 0)─────────────────────────(w, 0)

        w  = width          lh = left_height
        h  = height         fw = flange_width

        Built as a single closed perimeter polygon tracing the
        thin-walled solid cross-section (wall thickness = t).
        """
        t  = thickness
        w  = width
        h  = height
        lh = left_height
        fw = flange_width

        # Trace the solid-wall cross-section as one closed polygon.
        # Outer path  → inner path (offset inward by t).
        Polygon(
            # -- outer --
            (0, lh),          # top of short left wall
            (0, 0),           # bottom-left
            (w, 0),           # bottom-right
            (w, h),           # top-right
            (w - fw, h),      # end of top flange
            # -- inner (traced back) --
            (w - fw, h - t),  # under top flange
            (w - t, h - t),   # inner right-wall / flange corner
            (w - t, t),       # inner bottom-right
            (t, t),           # inner bottom-left
            (t, lh),          # inner top of left wall
            align=None,
        )

    @staticmethod
    def _create_stiffener_post_profile(face_width, leg_depth, return_flange, thickness):
        """
        Flat Channel Sheet Metal Stiffener Post – C-profile with returned flanges.

           rf←→                 ←→rf
           ┌──┐                 ┌──┐
           │  │                 │  │
           │  │  leg_depth      │  │
           │  │                 │  │
           │  └─────────────────┘  │
           └───────────────────────┘
                  face_width

        rf = return_flange      t = thickness (gauge-derived)

        Traced as a single closed perimeter polygon representing
        the thin-walled solid cross-section.
        """
        t  = thickness
        fw = face_width
        ld = leg_depth
        rf = return_flange

        Polygon(
            # -- outer boundary (clockwise) --
            (0, 0),               # outer bottom-left
            (0, ld),              # outer top of left leg
            (rf, ld),             # outer left return flange tip
            # -- cross wall at left return --
            (rf, ld - t),         # inner left return tip
            (t, ld - t),          # inner left leg / return junction
            (t, t),               # inner bottom-left
            (fw - t, t),          # inner bottom-right
            (fw - t, ld - t),     # inner right leg / return junction
            (fw - rf, ld - t),    # inner right return tip
            # -- cross wall at right return --
            (fw - rf, ld),        # outer right return flange tip
            (fw, ld),             # outer top of right leg
            (fw, 0),              # outer bottom-right
            align=None,
        )
