from build123d import *
from ...utils import usd_utils
import omni.usd
from pxr import UsdGeom, UsdShade, Sdf, Gf
import math


class Stair:
    """
    Industrial Stair Generator — built component by component.
    Reference: multi_elevation_stairs.STEP (SolidWorks weldment, AISC sections).

    Coordinate convention (Y-Up):
        X = horizontal run direction (stair goes along +X)
        Y = vertical rise direction (UP)
        Z = width direction (centered at Z=0)

    Current components:
        {path}/Stringers — AISC C10x20 channels, toed out at floor and landing
    """

    # AISC C10x20 channel dimensions (inches)
    C_DEPTH = 10.000
    C_BF = 2.739      # flange width (web face to flange tip)
    C_TW = 0.379      # web thickness
    C_TF = 0.606      # flange thickness

    # AISC C6x8.2 platform frame channel dimensions (inches)
    C6_DEPTH = 6.000
    C6_BF = 1.920
    C6_TW = 0.200
    C6_TF = 0.343

    # Connection stub at top of stringer
    STUB_LEN = 2.0
    PLATE_T = 0.25  # 1/4" end plate

    # Handrail posts — 2" NPS pipe (from STEP reference)
    POST_OD = 2.375       # 2" NPS outer diameter
    POST_WALL = 0.197     # 5mm wall thickness
    POST_HEIGHT = 42.0    # OSHA rail height above tread nosing
    POST_SPACING = 39.0   # ~1000mm horizontal spacing between posts

    @staticmethod
    def create(
        stage,
        path,
        total_rise=120.0,
        width=48.0,
        angle_deg=43.5,
        platform_length=48.0,
        platform_width=48.0,
        exit_side="end",
        include_platform=True,
        material="Steel"
    ):
        """
        Generate stair at the given path.

        Args:
            total_rise: floor-to-landing height (inches)
            width: clear width between stringer flange tips (inches)
            angle_deg: stair angle from horizontal (degrees)
            platform_length: platform depth in X direction (inches)
            platform_width: platform width in Z direction (inches)
            exit_side: which side is open for exit — "end", "left", or "right"
            material: surface material name
        """
        # --- Step geometry from angle ---
        angle_rad = math.radians(angle_deg)
        ideal_rise = 8.13  # from STEP reference
        num_steps = max(round(total_rise / ideal_rise), 1)
        actual_rise = total_rise / num_steps
        run = actual_rise / math.tan(angle_rad)
        total_run = run * (num_steps - 1)

        # Stringer extends one extra run past last tread
        stringer_run = run * num_steps

        print(f"[Stair] angle={angle_deg}°, num_steps={num_steps}, "
              f"rise/step={actual_rise:.3f}\", run/step={run:.3f}\"")
        print(f"[Stair] total_run={total_run:.1f}\", total_rise={total_rise:.1f}\"")

        try:
            root_xform = UsdGeom.Xform.Define(stage, path)

            # ==========================================================
            # STRINGERS — C10x20, toed out at floor (Y=0) and landing
            # ==========================================================
            # Left stringer: flanges point toward +Z (inward)
            #   flange tips at Z = -width/2
            #   web outer face at Z = -(width/2 + C_BF)
            # Right stringer: mirror of left
            s1 = Stair._create_stringer(stringer_run, total_rise, actual_rise,
                                        include_platform=include_platform)
            s1 = s1.move(Location((0, 0, -(width / 2))))
            s2 = s1.mirror(Plane.XY)

            stringer_compound = Compound(children=[s1, s2])
            usd_utils.create_mesh_from_shape(
                stage, f"{path}/Stringers", stringer_compound)
            Stair._apply_material(stage, f"{path}/Stringers", "Galvanized")

            # ==========================================================
            # TREADS — flat plate, open riser, spanning between stringers
            # ==========================================================
            tread_parts = []
            tread_thickness = 1  # 1/4" plate
            tread_width = width - 2  # 1/2" clearance each side for clip angles

            for i in range(num_steps):
                x_pos = run * (i - 0.5)           # front edge of tread
                y_pos = actual_rise * (i + 1)  # tread top surface

                with BuildPart() as bp:
                    Box(run, tread_thickness, tread_width,
                        align=(Align.MIN, Align.MAX, Align.CENTER))
                tread_parts.append(
                    bp.part.move(Location((x_pos, y_pos, 0))))

            tread_compound = Compound(children=tread_parts)
            usd_utils.create_mesh_from_shape(
                stage, f"{path}/Treads", tread_compound)
            Stair._apply_material(stage, f"{path}/Treads", "Black")

            # ==========================================================
            # POSTS — 2" NPS pipe, vertical, both sides
            # ==========================================================
            post_parts = Stair._create_posts(
                num_steps, actual_rise, run, width)
            if post_parts:
                post_compound = Compound(children=post_parts)
                usd_utils.create_mesh_from_shape(
                    stage, f"{path}/Posts", post_compound)
                Stair._apply_material(stage, f"{path}/Posts", "Yellow")

            # ==========================================================
            # STAIR HANDRAIL — top + mid rails along slope with end fittings
            # ==========================================================
            rail_parts = Stair._create_stair_handrail(
                num_steps, actual_rise, run, width)
            if rail_parts:
                rail_compound = Compound(children=rail_parts)
                usd_utils.create_mesh_from_shape(
                    stage, f"{path}/StairHandrail", rail_compound)
                Stair._apply_material(stage, f"{path}/StairHandrail", "Yellow")

            if include_platform:
                # ==========================================================
                # PLATFORM FRAME — C6x8.2, four-sided, toes in
                # ==========================================================
                frame_parts = Stair._create_platform_frame(
                    stringer_run, total_rise, platform_length, platform_width)
                if frame_parts:
                    frame_compound = Compound(children=frame_parts)
                    usd_utils.create_mesh_from_shape(
                        stage, f"{path}/PlatformFrame", frame_compound)
                    Stair._apply_material(stage, f"{path}/PlatformFrame", "Galvanized")

                # ==========================================================
                # DECK PLATE — 1/4" checkered plate on top of C6 frame
                # ==========================================================
                stub_top_y = total_rise + Stair.C_DEPTH
                plate_y = stub_top_y
                plate_x = stringer_run + Stair.STUB_LEN + Stair.PLATE_T
                deck_t = 0.25
                with BuildPart() as bp:
                    Box(platform_length, deck_t, platform_width,
                        align=(Align.MIN, Align.MIN, Align.CENTER))
                deck_plate = bp.part.move(Location((plate_x, plate_y, 0)))
                usd_utils.create_mesh_from_shape(
                    stage, f"{path}/DeckPlate", Compound(children=[deck_plate]))
                Stair._apply_material(stage, f"{path}/DeckPlate", "Black")

                # ==========================================================
                # KICK PLATE — 4" tall, 1/4" plate, platform perimeter
                # ==========================================================
                kick_h = 4.0
                kick_t = 0.25
                deck_top_y = plate_y + deck_t
                kick_parts = []

                if exit_side != "end":
                    with BuildPart() as bp:
                        Box(kick_t, kick_h, platform_width,
                            align=(Align.MIN, Align.MIN, Align.CENTER))
                    kick_parts.append(bp.part.move(
                        Location((plate_x + platform_length, deck_top_y, 0))))

                if exit_side != "right":
                    with BuildPart() as bp:
                        Box(platform_length, kick_h, kick_t,
                            align=(Align.MIN, Align.MIN, Align.MAX))
                    kick_parts.append(bp.part.move(
                        Location((plate_x, deck_top_y, platform_width / 2))))

                if exit_side != "left":
                    with BuildPart() as bp:
                        Box(platform_length, kick_h, kick_t,
                            align=(Align.MIN, Align.MIN, Align.MIN))
                    kick_parts.append(bp.part.move(
                        Location((plate_x, deck_top_y, -platform_width / 2))))

                if kick_parts:
                    kick_compound = Compound(children=kick_parts)
                    usd_utils.create_mesh_from_shape(
                        stage, f"{path}/KickPlate", kick_compound)
                    Stair._apply_material(stage, f"{path}/KickPlate", "Yellow")

                # ==========================================================
                # PLATFORM GUARDRAIL — posts + top/mid rails
                # ==========================================================
                guard_parts = Stair._create_platform_guardrail(
                    stringer_run, total_rise, platform_length, platform_width,
                    exit_side)
                if guard_parts:
                    guard_compound = Compound(children=guard_parts)
                    usd_utils.create_mesh_from_shape(
                        stage, f"{path}/PlatformGuardrail", guard_compound)
                    Stair._apply_material(stage, f"{path}/PlatformGuardrail", "Yellow")

            # --- Metadata ---
            prim = root_xform.GetPrim()
            prim.SetCustomDataByKey("twin:generator", "stair")
            prim.SetCustomDataByKey("twin:total_rise", total_rise)
            prim.SetCustomDataByKey("twin:width", width)
            prim.SetCustomDataByKey("twin:angle_deg", angle_deg)
            prim.SetCustomDataByKey("twin:num_steps", num_steps)
            prim.SetCustomDataByKey("twin:platform_length", platform_length)
            prim.SetCustomDataByKey("twin:platform_width", platform_width)
            prim.SetCustomDataByKey("twin:exit_side", exit_side)

            return root_xform

        except Exception as e:
            print(f"[Stair] Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ------------------------------------------------------------------
    # Posts — 2" NPS pipe, vertical, on both sides of stair
    # ------------------------------------------------------------------

    @staticmethod
    def _create_posts(num_steps, actual_rise, run, width):
        """
        Vertical 2" NPS pipe posts on both sides.
        Posts at first step, last step, and every POST_SPACING in between.
        Post bottom at tread nosing Y. Post center Z on stringer top flange.
        """
        od = Stair.POST_OD
        wall = Stair.POST_WALL
        height = Stair.POST_HEIGHT
        spacing = Stair.POST_SPACING

        # Post Z center: tangent to inside face of web
        # Web outer face at ±width/2, inner face at ±(width/2 - C_TW)
        # Post OD touches web inner face, post sits inside the channel
        post_z = width / 2 - Stair.C_TW + od / 4

        # Determine which steps get a post
        steps_per_post = max(1, round(spacing / run))
        post_steps = [0]
        idx = steps_per_post
        while idx < num_steps - 1:
            post_steps.append(idx)
            idx += steps_per_post
        post_steps.append(num_steps - 1)  # always at top step

        parts = []
        for step_idx in post_steps:
            x = run * step_idx
            y = actual_rise * (step_idx + 1.625)  # tread nosing Y

            for z in [-post_z, post_z]:
                with BuildPart() as bp:
                    Cylinder(od / 2, height,
                             align=(Align.CENTER, Align.CENTER, Align.MIN),
                             rotation=(-90, 0, 0))
                    Cylinder((od - 2 * wall) / 2, height,
                             align=(Align.CENTER, Align.CENTER, Align.MIN),
                             rotation=(-90, 0, 0),
                             mode=Mode.SUBTRACT)
                parts.append(bp.part.move(Location((x, y, z))))

        print(f"[Stair] Posts: {len(parts)} x 2\" NPS pipe, "
              f"height={height}\", spacing ~{spacing}\"")
        return parts

    # ------------------------------------------------------------------
    # Stair Handrail — sloped rails with end fittings
    # ------------------------------------------------------------------

    RAIL_OD = 1.660       # 1-1/4" NPS pipe outer diameter
    RAIL_WALL = 0.140     # wall thickness
    RAIL_CAP_OD = 2.375   # ball cap / return fitting OD
    TOP_RAIL_H = 42.0     # top rail height above tread nosing
    MID_RAIL_H = 21.0     # mid rail height above tread nosing

    @staticmethod
    def _create_stair_handrail(num_steps, actual_rise, run, width):
        """
        Top and mid rails along the stair slope on both sides.
        End fittings: ball caps at bottom, horizontal returns at top.
        """
        od = Stair.POST_OD
        rail_od = Stair.RAIL_OD
        rail_wall = Stair.RAIL_WALL
        cap_od = Stair.RAIL_CAP_OD
        spacing = Stair.POST_SPACING

        # Post Z positions (must match _create_posts)
        post_z = width / 2 - Stair.C_TW + od / 4

        # Determine which steps get a post (same logic as _create_posts)
        steps_per_post = max(1, round(spacing / run))
        post_steps = [0]
        idx = steps_per_post
        while idx < num_steps - 1:
            post_steps.append(idx)
            idx += steps_per_post
        post_steps.append(num_steps - 1)

        # Post top positions: (x, y_top) for each post
        post_tops = []
        for step_idx in post_steps:
            x = run * step_idx
            y_base = actual_rise * (step_idx + 1.625)
            post_tops.append((x, y_base + Stair.POST_HEIGHT))

        parts = []

        # Slope angle for rail direction
        slope_angle = math.degrees(math.atan2(actual_rise, run))

        for rail_height in [Stair.TOP_RAIL_H, Stair.MID_RAIL_H]:
            # Rail positions at each post (x, y at rail height above tread)
            rail_pts = []
            for step_idx in post_steps:
                x = run * step_idx
                y_base = actual_rise * (step_idx + 1.625)
                rail_pts.append((x, y_base + rail_height))

            for z_sign in [-1, 1]:
                z = z_sign * post_z

                # --- Sloped rail segments between consecutive posts ---
                for i in range(len(rail_pts) - 1):
                    x0, y0 = rail_pts[i]
                    x1, y1 = rail_pts[i + 1]
                    dx = x1 - x0
                    dy = y1 - y0
                    seg_len = math.sqrt(dx * dx + dy * dy)
                    seg_angle = math.degrees(math.atan2(dy, dx))

                    with BuildPart() as bp:
                        Cylinder(rail_od / 2, seg_len,
                                 align=(Align.CENTER, Align.CENTER, Align.MIN),
                                 rotation=(0, 90, 0))
                        Cylinder((rail_od - 2 * rail_wall) / 2, seg_len,
                                 align=(Align.CENTER, Align.CENTER, Align.MIN),
                                 rotation=(0, 90, 0),
                                 mode=Mode.SUBTRACT)
                    rail_seg = bp.part.rotate(Axis.Z, seg_angle)
                    parts.append(rail_seg.move(Location((x0, y0, z))))

                # Rails terminate at first and last post — no end fittings

        print(f"[Stair] Handrail: top ({Stair.TOP_RAIL_H}\") + mid ({Stair.MID_RAIL_H}\"), "
              f"both sides, {len(post_steps)} post spans")
        return parts

    # ------------------------------------------------------------------
    # Stringer — AISC C10x20 channel along the slope, toed out
    # ------------------------------------------------------------------

    @staticmethod
    def _create_stringer(stringer_run, total_rise, actual_rise, include_platform=True):
        """
        C10x20 channel stringer oriented along the stair slope.

        Cross-section (looking from floor toward landing):
            Web at Z=0 (inner face toward treads), flanges extend toward -Z (toes out).
            Depth measured in the local Y direction (perpendicular to slope).

        Construction:
            1. Sketch C-profile on Plane.YZ, extrude oversized along X
            2. Rotate to slope angle around Z axis
            3. Translate so web bottom sits at Y=0 at floor
            4. Boolean cut horizontally at Y=0 (floor) and Y=total_rise (landing)

        After positioning, web face is at Z=0 (tread side).
        Caller offsets to Z = -(width/2) so web faces the tread area.
        Mirror across XY gives the right stringer with toes out on the other side.
        """
        d = Stair.C_DEPTH       # 10.000"
        bf = Stair.C_BF         # 2.739"
        tw = Stair.C_TW         # 0.379"
        tf = Stair.C_TF         # 0.606"

        diag = math.sqrt(stringer_run**2 + total_rise**2)
        angle = math.degrees(math.atan2(total_rise, stringer_run))
        angle_rad = math.radians(angle)

        # Extra length so toe cuts have material to cut through
        extra = d * 2
        extrude_len = diag + 2 * extra

        # C-section profile on Plane.YZ
        # u = local Y (depth direction), v = local Z
        # Web outer face at Z=0, flanges extend toward -Z (toes out)
        # Profile origin at web center (Y=0 = mid-depth)
        c_profile = [
            (-d / 2, 0),               # web bottom, outer face
            (-d / 2, -bf),             # bottom flange tip (toes out)
            (-d / 2 + tf, -bf),        # bottom flange inner corner
            (-d / 2 + tf, -tw),        # web inner, above bottom flange
            (d / 2 - tf, -tw),         # web inner, below top flange
            (d / 2 - tf, -bf),         # top flange inner corner
            (d / 2, -bf),             # top flange tip (toes out)
            (d / 2, 0),               # web top, outer face
        ]

        # Extrude along +X
        with BuildPart() as bp:
            with BuildSketch(Plane.YZ):
                Polygon(c_profile)
            extrude(amount=extrude_len)
        channel = bp.part

        # Shift so extrusion is centered: X from -extra to diag+extra
        channel = channel.move(Location((-extra, 0, 0)))

        # Rotate to slope angle (around Z axis, in the XY plane)
        channel = channel.rotate(Axis.Z, angle)

        # Translate so bottom of web (Y = -d/2 in local) sits at Y=0 at floor.
        # After rotation, the bottom-of-web offset in world coords:
        #   X offset = -(-d/2) * sin(angle) = (d/2) * sin(angle)  ... wait
        # The point (-d/2, 0) in local (pre-rotation) was at the web bottom.
        # After rotation by angle around Z:
        #   world_x = (-d/2) * (-sin(angle)) = (d/2) * sin(angle)  ... no.
        # Rotation matrix for angle around Z:
        #   x' = x*cos(a) - y*sin(a)
        #   y' = x*sin(a) + y*cos(a)
        # The web bottom pre-rotation is at local (0, -d/2, 0) in the
        # cross-section. But in our extrusion, the profile center is at Y=0,
        # so web bottom is at Y = -d/2 relative to the extrusion axis.
        # After rotating the extrusion axis by 'angle':
        #   The web bottom line moves to:
        #     dx = -(-d/2) * sin(angle_rad) = (d/2) * sin(angle_rad)
        #     dy = (-d/2) * cos(angle_rad) = -(d/2) * cos(angle_rad)
        # Wait, the profile is on YZ, so the depth is along Y.
        # The rotation is around Z, so it rotates X and Y.
        # Point at (x=0, y=-d/2) pre-rotation:
        #   x' = 0*cos - (-d/2)*sin = (d/2)*sin(a)
        #   y' = 0*sin + (-d/2)*cos = -(d/2)*cos(a)
        # We want this point at Y=0 (floor), so translate by:
        #   tx = -(d/2)*sin(a)
        #   ty = (d/2)*cos(a)
        x_off = -(d / 2) * math.sin(angle_rad)
        y_off = (d / 2) * math.cos(angle_rad)
        channel = channel.move(Location((x_off, y_off, 0)))

        # --- Cuts: floor toe + plumb at top ---
        big = extrude_len * 3

        # Cut everything below Y=0 (floor toe)
        with BuildPart() as cut_bp:
            Box(big, big, big)
        floor_cut = cut_bp.part.move(Location((stringer_run / 2, -big / 2, 0)))
        channel = channel.cut(floor_cut)

        # Vertical plumb cut at X = stringer_run (one run past top tread)
        # Full channel cross-section visible — platform connection face
        with BuildPart() as cut_bp:
            Box(big, big, big)
        plumb_cut = cut_bp.part.move(Location((stringer_run + big / 2, total_rise / 2, 0)))
        channel = channel.cut(plumb_cut)

        if include_platform:
            # --- Horizontal connection stub at top (2" along +X) ---
            stub_len = Stair.STUB_LEN
            with BuildPart() as stub_bp:
                with BuildSketch(Plane.YZ):
                    Polygon(c_profile)
                extrude(amount=stub_len)
            stub = stub_bp.part.move(
                Location((stringer_run, total_rise + d / 2, 0)))

            # --- End plate: full face of channel at end of stub ---
            plate_t = Stair.PLATE_T
            with BuildPart() as plate_bp:
                Box(plate_t, d, bf)
            end_plate = plate_bp.part.move(
                Location((stringer_run + stub_len + plate_t / 2,
                          total_rise + d / 2, 0)))

            # Horizontal cut at top of stub — trim sloped stringer flush
            stub_top_y = total_rise + d
            with BuildPart() as cut_bp:
                Box(big, big, big)
            top_cut = cut_bp.part.move(
                Location((stringer_run / 2, stub_top_y + big / 2, 0)))
            channel = channel.cut(top_cut)

            # Fuse stringer + stub + end plate into single solid
            channel = channel.fuse(stub).fuse(end_plate)

        print(f"[Stringer] C10x20 toed out — diag={diag:.1f}\", angle={angle:.1f}°, "
              f"stringer_run={stringer_run:.1f}\"")
        return channel

    # ------------------------------------------------------------------
    # Platform Frame — C6x8.2, four-sided, toes in (web out)
    # ------------------------------------------------------------------

    @staticmethod
    def _create_platform_frame(stringer_run, total_rise, platform_length, platform_width):
        """
        C6x8.2 four-sided rectangular frame, toes in (web facing outward).
        Top aligned with stub channel top (total_rise + C10 depth).
        Front face aligned with stub end plate face.
        """
        d6 = Stair.C6_DEPTH
        bf6 = Stair.C6_BF
        tw6 = Stair.C6_TW
        tf6 = Stair.C6_TF

        # Frame Y: top aligned with stub channel top
        stub_top_y = total_rise + Stair.C_DEPTH
        frame_center_y = stub_top_y - d6 / 2

        # Frame X: front face aligned with stub end plate face
        frame_x = stringer_run + Stair.STUB_LEN + Stair.PLATE_T

        pl = platform_length
        pw = platform_width

        # C6 profile on YZ (depth in Y, web at Z=0, flanges toward -Z)
        c6_yz = [
            (-d6 / 2, 0),
            (-d6 / 2, -bf6),
            (-d6 / 2 + tf6, -bf6),
            (-d6 / 2 + tf6, -tw6),
            (d6 / 2 - tf6, -tw6),
            (d6 / 2 - tf6, -bf6),
            (d6 / 2, -bf6),
            (d6 / 2, 0),
        ]

        # C6 profile on XY: front — web at X=0 facing -X (outward), flanges +X (inward)
        c6_xy_front = [
            (0, -d6 / 2),
            (bf6, -d6 / 2),
            (bf6, -d6 / 2 + tf6),
            (tw6, -d6 / 2 + tf6),
            (tw6, d6 / 2 - tf6),
            (bf6, d6 / 2 - tf6),
            (bf6, d6 / 2),
            (0, d6 / 2),
        ]

        # C6 profile on XY: back — web at X=0 facing +X (outward), flanges -X (inward)
        c6_xy_back = [
            (0, -d6 / 2),
            (-bf6, -d6 / 2),
            (-bf6, -d6 / 2 + tf6),
            (-tw6, -d6 / 2 + tf6),
            (-tw6, d6 / 2 - tf6),
            (-bf6, d6 / 2 - tf6),
            (-bf6, d6 / 2),
            (0, d6 / 2),
        ]

        parts = []

        # --- Right side (along X): web at Z=+pw/2 facing +Z, flanges -Z ---
        with BuildPart() as bp:
            with BuildSketch(Plane.YZ):
                Polygon(c6_yz)
            extrude(amount=pl)
        right_raw = bp.part

        # Cope cuts: notch flanges at both ends so web fits against front/back
        # Cope length = bf6 (flange width of connecting channel)
        # Cope depth = tf6 (flange thickness) from top and bottom of channel
        cope_len = bf6
        cope_depth = tf6
        flange_extent = bf6 - tw6  # flange protrusion beyond web inner face

        # Bottom flange cope at front end (X=0 side)
        with BuildPart() as cb:
            Box(cope_len, cope_depth, flange_extent)
        right_raw = right_raw.cut(cb.part.move(
            Location((cope_len / 2, -d6 / 2 + cope_depth / 2, -(tw6 + flange_extent / 2)))))

        # Top flange cope at front end
        right_raw = right_raw.cut(cb.part.move(
            Location((cope_len / 2, d6 / 2 - cope_depth / 2, -(tw6 + flange_extent / 2)))))

        # Bottom flange cope at back end (X=pl side)
        right_raw = right_raw.cut(cb.part.move(
            Location((pl - cope_len / 2, -d6 / 2 + cope_depth / 2, -(tw6 + flange_extent / 2)))))

        # Top flange cope at back end
        right_raw = right_raw.cut(cb.part.move(
            Location((pl - cope_len / 2, d6 / 2 - cope_depth / 2, -(tw6 + flange_extent / 2)))))

        right = right_raw.move(Location((frame_x, frame_center_y, pw / 2)))
        parts.append(right)

        # --- Left side: mirror of right across Z=0 ---
        left = right.mirror(Plane.XY)
        parts.append(left)

        # --- Front (along Z): web at frame_x facing -X, flanges +X ---
        with BuildPart() as bp:
            with BuildSketch(Plane.XY):
                Polygon(c6_xy_front)
            extrude(amount=pw)
        front = bp.part.move(Location((frame_x, frame_center_y, -pw / 2)))
        parts.append(front)

        # --- Back (along Z): web at frame_x+pl facing +X, flanges -X ---
        with BuildPart() as bp:
            with BuildSketch(Plane.XY):
                Polygon(c6_xy_back)
            extrude(amount=pw)
        back = bp.part.move(Location((frame_x + pl, frame_center_y, -pw / 2)))
        parts.append(back)

        print(f"[Stair] Platform frame: C6x8.2, {pl}\" x {pw}\", "
              f"top at Y={stub_top_y:.1f}\"")
        return parts

    # ------------------------------------------------------------------
    # Platform Guardrail — posts + top/mid rails, 3 sides
    # ------------------------------------------------------------------

    @staticmethod
    def _create_platform_guardrail(stringer_run, total_rise, platform_length, platform_width, exit_side="end"):
        """
        2" NPS pipe posts and rails on platform perimeter.
        Front (stair access) and exit_side are open.
        Top rail at 42", mid rail at 21" above deck.
        """
        od = Stair.POST_OD
        wall = Stair.POST_WALL
        rail_od = 1.660       # 1-1/4" NPS pipe for rails
        rail_wall = 0.140
        post_height = Stair.POST_HEIGHT
        mid_rail_h = 21.0     # mid rail height above deck
        spacing = Stair.POST_SPACING

        # Deck top Y
        deck_top_y = total_rise + Stair.C_DEPTH + 0.25  # C6 top + deck plate

        # Platform origin X
        plat_x = stringer_run + Stair.STUB_LEN + Stair.PLATE_T
        pl = platform_length
        pw = platform_width

        parts = []

        # --- Corner post positions (X, Z) ---
        # Front-left, front-right (at stair opening edge)
        # Back-left, back-right (far edge)
        corners = {
            'fl': (plat_x, -pw / 2),
            'fr': (plat_x, pw / 2),
            'bl': (plat_x + pl, -pw / 2),
            'br': (plat_x + pl, pw / 2),
        }

        # --- Collect all post positions for each side ---
        def posts_along(x0, z0, x1, z1, side_len):
            """Generate post (X,Z) positions along a side including endpoints."""
            positions = [(x0, z0)]
            num_intermediate = max(0, int(side_len / spacing) - 1)
            for i in range(1, num_intermediate + 1):
                t = i / (num_intermediate + 1)
                positions.append((x0 + t * (x1 - x0), z0 + t * (z1 - z0)))
            positions.append((x1, z1))
            return positions

        # Build post lists for each side (skip exit side)
        side_posts = {}
        if exit_side != "right":
            side_posts['right'] = posts_along(*corners['fr'], *corners['br'], pl)
        if exit_side != "left":
            side_posts['left'] = posts_along(*corners['fl'], *corners['bl'], pl)
        if exit_side != "end":
            side_posts['back'] = posts_along(*corners['bl'], *corners['br'], pw)

        # --- Create posts ---
        all_post_positions = set()
        for pos_list in side_posts.values():
            for pos in pos_list:
                # Deduplicate corners
                key = (round(pos[0], 3), round(pos[1], 3))
                if key not in all_post_positions:
                    all_post_positions.add(key)
                    x, z = pos
                    with BuildPart() as bp:
                        Cylinder(od / 2, post_height,
                                 align=(Align.CENTER, Align.CENTER, Align.MIN),
                                 rotation=(-90, 0, 0))
                        Cylinder((od - 2 * wall) / 2, post_height,
                                 align=(Align.CENTER, Align.CENTER, Align.MIN),
                                 rotation=(-90, 0, 0),
                                 mode=Mode.SUBTRACT)
                    parts.append(bp.part.move(Location((x, deck_top_y, z))))

        # --- Create rails (top + mid) on each side ---
        def make_rail(x0, z0, x1, z1, height_above_deck):
            """Horizontal rail pipe between two points at given height."""
            dx = x1 - x0
            dz = z1 - z0
            length = math.sqrt(dx * dx + dz * dz)
            if length < 0.1:
                return None
            rail_y = deck_top_y + height_above_deck

            # Rail along X by default, rotate around Y for angle
            # Y-rotation maps +X to (cos θ, 0, -sin θ), so negate dz
            angle_y = math.degrees(math.atan2(-dz, dx))

            with BuildPart() as bp:
                Cylinder(rail_od / 2, length,
                         align=(Align.CENTER, Align.CENTER, Align.MIN),
                         rotation=(0, 90, 0))
                Cylinder((rail_od - 2 * rail_wall) / 2, length,
                         align=(Align.CENTER, Align.CENTER, Align.MIN),
                         rotation=(0, 90, 0),
                         mode=Mode.SUBTRACT)
            rail = bp.part
            if abs(angle_y) > 0.01:
                rail = rail.rotate(Axis.Y, angle_y)
            return rail.move(Location((x0, rail_y, z0)))

        # Rails on same sides as posts
        rail_sides = []
        if exit_side != "right":
            rail_sides.append((*corners['fr'], *corners['br']))
        if exit_side != "left":
            rail_sides.append((*corners['fl'], *corners['bl']))
        if exit_side != "end":
            rail_sides.append((*corners['bl'], *corners['br']))

        for x0, z0, x1, z1 in rail_sides:
            for h in [post_height, mid_rail_h]:
                rail = make_rail(x0, z0, x1, z1, h)
                if rail:
                    parts.append(rail)

        num_sides = len(rail_sides)
        print(f"[Stair] Platform guardrail: {len(all_post_positions)} posts, "
              f"{num_sides * 2} rails (top+mid, {num_sides} sides)")
        return parts

    # ------------------------------------------------------------------
    # Material Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_material(stage, mesh_path, material_name):
        colors = {
            "Steel":      (0.45, 0.45, 0.48),
            "Aluminum":   (0.7, 0.72, 0.73),
            "Black":      (0.05, 0.05, 0.05),
            "Yellow":     (0.95, 0.80, 0.05),
            "Galvanized": (0.68, 0.70, 0.72),
        }
        metallic = {
            "Black": 0.3, "Yellow": 0.2, "Galvanized": 0.6,
        }
        roughness = {
            "Black": 0.6, "Yellow": 0.5, "Galvanized": 0.45,
        }
        color = colors.get(material_name, (0.45, 0.45, 0.48))

        looks_path = "/Looks"
        if not stage.GetPrimAtPath(looks_path):
            stage.DefinePrim(looks_path, "Scope")

        mat_path = f"{looks_path}/Stair_{material_name}"
        mat = UsdShade.Material.Define(stage, mat_path)
        shader_path = f"{mat_path}/PBRShader"
        pbr = UsdShade.Shader.Define(stage, shader_path)
        pbr.CreateIdAttr("UsdPreviewSurface")
        pbr.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(*color))
        pbr.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(
            metallic.get(material_name, 0.8))
        pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(
            roughness.get(material_name, 0.35))

        out = mat.CreateSurfaceOutput()
        out.ConnectToSource(UsdShade.ConnectableAPI(pbr.GetPrim()), "surface")

        prim = stage.GetPrimAtPath(mesh_path)
        if prim:
            binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
            binding_api.Bind(mat,
                             bindingStrength=UsdShade.Tokens.strongerThanDescendants)
