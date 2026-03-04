"""
Fan Assembly Generator — Step 6 of 7 in the physics-first fan engineering system.

Takes all engineering parameters from Steps 1-5 (via FanAcousticResult chain)
and generates actual 3D geometry using build123d, assembled into a multi-prim
USD hierarchy.

Two-layer design (same as stair.py pattern):
    Layer A — Pure geometry functions (build123d only, no USD). Independently testable.
    Layer B — FanAssembly.create(stage, path, acoustic_result) USD assembly creator.

USD hierarchy:
    /World/Fan_01/           (Xform root)
        ImpellerDisks        (Mesh — hub + shroud annular disks)
        Blades               (Mesh — blade circular array)
        Housing              (Mesh — 270° logarithmic spiral volute, tongue at 90° upblast)
        DischargeFrame       (Mesh — 2x2x1/4 angle perimeter at discharge)
        InletRing            (Mesh — 3-piece revolved inlet ring)
        BaseFrame            (Mesh — low channel-iron base frame under entire assembly)
        Pedestal             (Mesh — trapezoidal stand behind scroll for bearings/motor)
        BearingShimA         (Mesh — steel riser block under bearing A)
        BearingShimB         (Mesh — steel riser block under bearing B)
        BearingA             (Mesh — inboard pillow block bearing)
        BearingB             (Mesh — outboard pillow block bearing)
        Shaft                (Mesh — fan drive shaft)
        Coupling             (Mesh — shaft coupling)
        MotorShaft           (Mesh — motor stub shaft)
        MotorShimL           (Mesh — 1/2" alignment shim under left motor foot)
        MotorShimR           (Mesh — 1/2" alignment shim under right motor foot)
        Motor                (Mesh — NEMA motor frame)

Coordinate convention:
    Shaft along Z (horizontal, pointing into scene)
    Impeller rotates in XY plane
    +Y is up
    Scroll spiral wraps around Z axis in XY plane (snail-shell when viewed along Z)
    Tongue at 90° math angle (top, upblast configuration)
    Scroll wraps CW 270° from tongue; flat wall closes upper-left quadrant
    Discharge exits upward (+Y) at tongue via 12" straight duct section
    Base bottom sits at Y=0, fan center at Y = base_height + max_radius

Geometry normalization:
    All scroll/flange dimensions normalized to D=1.0 (impeller diameter).
    Multiply by actual tip_diameter_in to get real dimensions.
    Logarithmic spiral: R(θ) = R_cutoff × 1.0017^θ_scroll (0° to 270°)

References:
    - Bleier, "Fan Handbook", McGraw-Hill, Ch. 6 (scroll design)
    - AMCA 99-16 — Standards Handbook
    - Steps 1-5 solver chain for all engineering parameters
"""

import math
from typing import List, Optional

import build123d as bd

# ---------------------------------------------------------------------------
# Layer A — Pure geometry functions (build123d only, no USD)
# ---------------------------------------------------------------------------


def create_hub_disk(
    tip_diameter_in: float,
    hub_diameter_in: float,
    thickness: float = 0.0,
) -> bd.Solid:
    """
    Annular disk (impeller backplate).

    OD = tip_diameter, ID = hub_diameter.
    Axis along Z. Sits at Z=0..thickness.
    Thickness defaults to 1% of D for viewport visibility.
    """
    if thickness <= 0:
        thickness = 0.01 * tip_diameter_in
    tip_r = tip_diameter_in / 2.0
    hub_r = hub_diameter_in / 2.0
    with bd.BuildPart() as bp:
        bd.Cylinder(tip_r, thickness,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        bd.Cylinder(hub_r, thickness,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
                    mode=bd.Mode.SUBTRACT)
    return bp.part.solid()


def create_shroud_disk(
    tip_diameter_in: float,
    hub_diameter_in: float,
    outlet_width_in: float,
    thickness: float = 0.0,
) -> bd.Solid:
    """
    Shroud disk (front plate of impeller with eye opening).

    Positioned at Z = outlet_width (front face). Eye opening = hub_diameter.
    Thickness defaults to 1% of D for viewport visibility.
    """
    if thickness <= 0:
        thickness = 0.01 * tip_diameter_in
    tip_r = tip_diameter_in / 2.0
    hub_r = hub_diameter_in / 2.0
    with bd.BuildPart() as bp:
        bd.Cylinder(tip_r, thickness,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        bd.Cylinder(hub_r, thickness,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
                    mode=bd.Mode.SUBTRACT)
    disk = bp.part.solid()
    return disk.moved(bd.Location((0, 0, outlet_width_in)))


def create_impeller_disks(
    tip_diameter_in: float,
    hub_diameter_in: float,
    outlet_width_in: float,
) -> bd.Compound:
    """Hub disk + shroud disk compound."""
    hub = create_hub_disk(tip_diameter_in, hub_diameter_in)
    shroud = create_shroud_disk(tip_diameter_in, hub_diameter_in,
                                outlet_width_in)
    return bd.Compound(children=[hub, shroud])


def create_blade(
    hub_radius: float,
    tip_radius: float,
    outlet_width: float,
    stagger_deg: float,
    thickness: float = 2.0,
) -> bd.Solid:
    """
    Single flat-plate blade at stagger angle.

    Blade spans from hub_radius to tip_radius radially,
    Z = 0..outlet_width (between hub and shroud disks).
    Thickness 2.0" for viewport visibility (physical is 0.125").
    """
    radial_extent = tip_radius - hub_radius
    with bd.BuildPart() as bp:
        bd.Box(radial_extent, thickness, outlet_width,
               align=(bd.Align.MIN, bd.Align.CENTER, bd.Align.MIN))
    blade = bp.part.solid()
    # Position blade starting at hub_radius along +X
    blade = blade.moved(bd.Location((hub_radius, 0, 0)))
    # Rotate by stagger angle around Z axis
    if abs(stagger_deg) > 0.01:
        blade = blade.moved(bd.Location((0, 0, 0), (0, 0, stagger_deg)))
    return blade


def create_blades(
    tip_diameter_in: float,
    hub_diameter_in: float,
    outlet_width_in: float,
    num_blades: int,
    stagger_deg: float,
) -> bd.Compound:
    """
    Blade set as a circular array.

    Each blade is built independently at its angular position to avoid
    accumulated rotation errors from copying.
    """
    tip_r = tip_diameter_in / 2.0
    hub_r = hub_diameter_in / 2.0
    radial_extent = tip_r - hub_r
    thickness = 2.0

    blade_copies = []
    for i in range(num_blades):
        array_angle = 360.0 * i / num_blades
        total_angle = stagger_deg + array_angle

        # Build each blade fresh at origin, then position it
        with bd.BuildPart() as bp:
            bd.Box(radial_extent, thickness, outlet_width_in,
                   align=(bd.Align.MIN, bd.Align.CENTER, bd.Align.MIN))
        blade = bp.part.solid()

        # Move to hub radius, then rotate to final position
        blade = blade.moved(bd.Location((hub_r, 0, 0)))
        blade = blade.moved(bd.Location((0, 0, 0), (0, 0, total_angle)))
        blade_copies.append(blade)

    return bd.Compound(children=blade_copies)


def create_impeller(
    tip_diameter_in: float,
    hub_diameter_in: float,
    outlet_width_in: float,
    num_blades: int,
    stagger_deg: float,
) -> bd.Compound:
    """Complete impeller: hub disk + shroud disk + blades."""
    disks = create_impeller_disks(tip_diameter_in, hub_diameter_in,
                                  outlet_width_in)
    blades = create_blades(tip_diameter_in, hub_diameter_in,
                           outlet_width_in, num_blades, stagger_deg)
    return bd.Compound(children=[disks, blades])


def create_scroll_housing(
    tip_radius_in: float,
    volute_width_in: float,
    wall_thickness_in: float,
    hub_diameter_in: float,
    scroll_arc_deg: float = 270.0,
) -> bd.Solid:
    """
    Scroll / volute housing — logarithmic spiral, solid-then-hollow.

    Builds a scroll shape using the spec logarithmic spiral profile:
        R(θ) = R_cutoff × 1.0017^θ_scroll
    Tongue at 90° math angle (top, upblast). Discharge exits upward (+Y).

    The scroll wraps CW from the tongue for scroll_arc_deg (default 270°).
    A flat wall closes the housing from the scroll end back to the tongue,
    forming a rectangular transition to the discharge opening.

    Construction: extrude solid spiral polygon → hollow via cavity cut →
    cut eye, shaft hole, and outlet opening.

    All dimensions normalized to D = tip_radius_in * 2 (impeller diameter).
    The housing is centered on Z (shaft axis) when returned.
    """
    D = tip_radius_in * 2.0  # impeller diameter

    # Spiral profile normalized to D; depth from solver's volute_width_in
    R_cutoff = 0.540 * D       # tongue radius at θ_scroll=0
    wall_t = 0.012 * D         # front/back plate thickness
    W_ext = volute_width_in    # total housing depth from solver
    W_int = W_ext - 2 * wall_t # internal airway width
    eye_r = 0.36 * D           # inlet eye radius (0.72D dia / 2)
    shaft_hole_r = 0.04 * D    # shaft hole radius (0.08D dia / 2)
    R_end = R_cutoff * (1.0017 ** scroll_arc_deg)  # max spiral radius at scroll end

    tongue_math = 90.0  # tongue position in math angle — upblast: tongue at top, discharge +Y

    # Step 1 — Logarithmic spiral outer polygon (XY plane)
    # Spiral winds CW from tongue (90°) for scroll_arc_deg.
    # For 270°: tongue at top (90°) → right (0°) → bottom (270°) → left (180°).
    # Flat closing walls connect the scroll end back to the tongue,
    # forming a rectangular housing corner in the upper-left quadrant.
    num_spiral_steps = int(scroll_arc_deg / 5.0)
    spiral_pts = []
    for i in range(num_spiral_steps + 1):  # 0° to scroll_arc_deg in 5° steps
        theta_scroll = i * 5.0
        R = R_cutoff * (1.0017 ** theta_scroll)
        theta_math = (tongue_math - theta_scroll) % 360.0  # CW winding
        rad = math.radians(theta_math)
        spiral_pts.append((R * math.cos(rad), R * math.sin(rad)))

    # Close polygon: flat walls from scroll end back to tongue area.
    # For 270° scroll ending at 180° math (-X direction):
    #   (-R_end, 0) → (-R_end, R_end)  = flat left wall going up
    #   (-R_end, R_end) → (0, R_end)   = flat top wall going right
    #   (0, R_end) → (0, R_cutoff)     = auto-close = discharge opening
    end_theta_math = (tongue_math - scroll_arc_deg) % 360.0
    end_rad = math.radians(end_theta_math)
    end_x = R_end * math.cos(end_rad)
    end_y = R_end * math.sin(end_rad)

    # Tongue start point (first spiral point)
    tongue_rad_angle = math.radians(tongue_math)
    start_x = R_cutoff * math.cos(tongue_rad_angle)
    start_y = R_cutoff * math.sin(tongue_rad_angle)

    # Upper corner on scroll-end side, then discharge collar above tongue.
    # Extend the polygon PAST the tongue (X > 0) by half the discharge radial
    # span so the discharge opening can be centered at X = 0.
    spiral_pts.append((end_x, R_end))    # upper-left corner (left wall going up)
    spiral_pts.append((start_x, R_end))  # top wall across to above tongue
    # Polygon auto-closes to first point (start_x, R_cutoff) = (0, R_cutoff)
    # The vertical gap from (0, R_end) to (0, R_cutoff) is the discharge opening

    # Step 2 — Extrude solid spiral polygon to full housing depth
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.XY):
            bd.Polygon(spiral_pts, align=None)
        bd.extrude(amount=W_ext)
    scroll_solid = bp.part.solid()

    # Step 3 — Shell the housing interior using an inner scroll polygon
    # The cavity follows the same spiral profile offset inward by wall_t,
    # creating a true thin-walled shell (like sheet metal).
    inner_pts = []
    for i in range(num_spiral_steps + 1):
        theta_scroll = i * 5.0
        R_inner = R_cutoff * (1.0017 ** theta_scroll) - wall_t
        theta_math = (tongue_math - theta_scroll) % 360.0
        rad = math.radians(theta_math)
        inner_pts.append((R_inner * math.cos(rad), R_inner * math.sin(rad)))

    # Inner closing walls (offset inward by wall_t from outer walls)
    # Left wall inner:   X = -R_end + wall_t
    # Top wall inner:    Y = R_end - wall_t
    # Tongue wall inner: X = -wall_t (creates wall_t-thick tongue)
    inner_pts.append((-R_end + wall_t, R_end - wall_t))   # upper-left inner corner
    inner_pts.append((-wall_t, R_end - wall_t))            # upper-right inner (tongue side)
    inner_pts.append((-wall_t, R_cutoff - wall_t))         # tongue wall bottom
    # Auto-close to first inner point (0, R_cutoff - wall_t) — tongue lip

    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.XY):
            bd.Polygon(inner_pts, align=None)
        bd.extrude(amount=W_int)
    cavity = bp.part.solid()
    cavity = cavity.moved(bd.Location((0, 0, wall_t)))
    housing = scroll_solid.cut(cavity)
    if not isinstance(housing, bd.Solid):
        housing = max(list(housing), key=lambda s: s.volume)

    # Step 4 — Cut eye opening on front plate (Z ≈ 0)
    with bd.BuildPart() as bp:
        bd.Cylinder(eye_r, wall_t * 3,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    eye_cut = bp.part.solid()
    eye_cut = eye_cut.moved(bd.Location((0, 0, -wall_t)))
    housing = housing.cut(eye_cut)
    if not isinstance(housing, bd.Solid):
        housing = max(list(housing), key=lambda s: s.volume)

    # Step 5 — Cut shaft hole on back plate (Z ≈ W_ext)
    with bd.BuildPart() as bp:
        bd.Cylinder(shaft_hole_r, wall_t * 3,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    shaft_cut = bp.part.solid()
    shaft_cut = shaft_cut.moved(bd.Location((0, 0, W_ext - wall_t)))
    housing = housing.cut(shaft_cut)
    if not isinstance(housing, bd.Solid):
        housing = max(list(housing), key=lambda s: s.volume)

    # Step 6 — Open discharge through top wall
    # The shell leaves a wall_t-thick top wall at Y = R_end.
    # Remove the entire top plate across the full transition zone width.
    discharge_w = R_end                    # full transition zone width
    with bd.BuildPart() as bp:
        bd.Box(discharge_w, wall_t * 3, W_int,
               align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
    top_cut = bp.part.solid()
    top_cut = top_cut.moved(
        bd.Location((-R_end / 2.0, R_end, W_ext / 2)))
    housing = housing.cut(top_cut)
    if not isinstance(housing, bd.Solid):
        housing = max(list(housing), key=lambda s: s.volume)

    # Step 7 — Center on Z
    housing = housing.moved(bd.Location((0, 0, -W_ext / 2)))

    return housing


def create_discharge_frame(
    x_span: float,
    z_span: float,
    leg: float = 2.0,
    t: float = 0.25,
) -> bd.Compound:
    """
    4-piece butt-jointed 2x2x1/4 angle frame around discharge opening.

    Frame at Y=0 with toe down (-Y) and toe out (away from opening).
    Opening spans X from -x_span to 0, Z from -z_span/2 to +z_span/2.
    Front/back pieces run full X width; left/right pieces butt between.
    """
    half_z = z_span / 2.0
    parts = []

    def _leg_box(lx, ly, lz, px, py, pz):
        """Box with dims (lx, ly, lz), MIN-aligned corner at (px, py, pz)."""
        with bd.BuildPart() as bp:
            bd.Box(lx, ly, lz,
                   align=(bd.Align.MIN, bd.Align.MIN, bd.Align.MIN))
        return bp.part.solid().moved(bd.Location((px, py, pz)))

    # --- Front piece (Z = -half_z, runs along X, toe out -Z) ---
    # Vertical leg: hangs down -Y on front face
    parts.append(_leg_box(x_span, leg, t,
                          -x_span, -leg, -half_z - t))
    # Horizontal leg: goes -Z outward
    parts.append(_leg_box(x_span, t, leg,
                          -x_span, -t, -half_z - leg))

    # --- Back piece (Z = +half_z, runs along X, toe out +Z) ---
    parts.append(_leg_box(x_span, leg, t,
                          -x_span, -leg, half_z))
    parts.append(_leg_box(x_span, t, leg,
                          -x_span, -t, half_z))

    # Full Z extent including front/back toe-out (no corner gaps)
    z_full = z_span + 2 * leg
    z_start = -(half_z + leg)

    # --- Left piece (X = -x_span, runs along Z, toe out -X) ---
    # Extended in ±Z to reach front/back toe outer edges
    parts.append(_leg_box(t, leg, z_full,
                          -x_span - t, -leg, z_start))
    parts.append(_leg_box(leg, t, z_full,
                          -x_span - leg, -t, z_start))

    # --- Right piece (X = 0, runs along Z, toe out +X) ---
    # Extended in ±Z to reach front/back toe outer edges
    parts.append(_leg_box(t, leg, z_full,
                          0, -leg, z_start))
    parts.append(_leg_box(leg, t, z_full,
                          0, -t, z_start))

    return bd.Compound(children=parts)


def create_outlet_duct(
    width_in: float,
    height_in: float,
    length_in: float,
) -> bd.Solid:
    """
    Rectangular outlet duct extending from the scroll tongue.

    width_in: Z span (0.42 * D)
    height_in: radial span (0.468 * D)
    length_in: extension length (0.25 * D)
    """
    with bd.BuildPart() as bp:
        bd.Box(length_in, height_in, width_in,
               align=(bd.Align.MIN, bd.Align.CENTER, bd.Align.CENTER))
    return bp.part.solid()


def create_inlet_flange(
    impeller_diameter_in: float,
) -> bd.Solid:
    """
    Square plate with circular center opening and 8 bolt holes.

    All dimensions normalized to D = impeller_diameter_in.
    Built at Z=0, positioned by assembly.
    """
    D = impeller_diameter_in
    side = 0.920 * D
    thickness = 0.016 * D
    opening_r = 0.720 * D / 2.0
    pcd = 0.800 * D  # bolt circle diameter
    bolt_r = 0.014 * D / 2.0

    # Square plate
    with bd.BuildPart() as bp:
        bd.Box(side, side, thickness,
               align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        # Center opening
        bd.Cylinder(opening_r, thickness,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
                    mode=bd.Mode.SUBTRACT)
        # 8 bolt holes at 45° intervals on PCD
        for i in range(8):
            angle = i * 45.0
            rad = math.radians(angle)
            bx = (pcd / 2.0) * math.cos(rad)
            by = (pcd / 2.0) * math.sin(rad)
            with bd.Locations([(bx, by)]):
                bd.Cylinder(bolt_r, thickness,
                            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
                            mode=bd.Mode.SUBTRACT)
    return bp.part.solid()


def create_outlet_flange(
    impeller_diameter_in: float,
    duct_width_in: float = 0.0,
    duct_height_in: float = 0.0,
) -> bd.Solid:
    """
    Rectangular frame with 8 bolt holes for outlet duct end.

    When duct_width_in / duct_height_in are provided, the flange inner
    opening matches the duct cross-section exactly.  Otherwise falls back
    to D-based defaults.

    Built flat at Z=0, positioned/rotated by assembly.
    """
    D = impeller_diameter_in
    flange_margin = 0.060 * D   # frame width around the opening
    thickness = 0.016 * D
    bolt_r = 0.014 * D / 2.0

    if duct_width_in > 0 and duct_height_in > 0:
        inner_w = duct_width_in
        inner_h = duct_height_in
    else:
        inner_w = 0.420 * D
        inner_h = 0.468 * D

    outer_w = inner_w + 2 * flange_margin
    outer_h = inner_h + 2 * flange_margin

    # Frame margins for bolt placement
    margin_w = flange_margin
    margin_h = flange_margin

    with bd.BuildPart() as bp:
        # Outer rectangle
        bd.Box(outer_w, outer_h, thickness,
               align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        # Inner opening
        bd.Box(inner_w, inner_h, thickness,
               align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
               mode=bd.Mode.SUBTRACT)
        # 8 bolt holes — 2 per edge, evenly spaced
        bolt_positions = []
        # Top/bottom edges (along width)
        for sx in (-0.25, 0.25):
            for sy in (1, -1):
                bx = sx * outer_w
                by = sy * (outer_h / 2.0 - margin_h / 2.0)
                bolt_positions.append((bx, by))
        # Left/right edges (along height)
        for sy in (-0.25, 0.25):
            for sx in (1, -1):
                bx = sx * (outer_w / 2.0 - margin_w / 2.0)
                by = sy * outer_h
                bolt_positions.append((bx, by))
        for bx, by in bolt_positions:
            with bd.Locations([(bx, by)]):
                bd.Cylinder(bolt_r, thickness,
                            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
                            mode=bd.Mode.SUBTRACT)
    return bp.part.solid()


def create_shaft(diameter_in: float, length_in: float) -> bd.Solid:
    """Drive shaft cylinder along Z, centered at origin."""
    with bd.BuildPart() as bp:
        bd.Cylinder(diameter_in / 2.0, length_in,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
    return bp.part.solid()


# ---------------------------------------------------------------------------
# Pillow block bearing lookup (UCP200 series proportions)
# bore: (base_w, base_l, base_t, housing_od, housing_h, bolt_spacing, bolt_dia)
# All dimensions in inches.
# ---------------------------------------------------------------------------
_PILLOW_BLOCK = {
    0.750: (3.75, 1.50, 0.56, 2.25, 1.50, 2.75, 0.44),
    0.875: (4.00, 1.63, 0.63, 2.50, 1.63, 3.00, 0.44),
    1.000: (4.25, 1.75, 0.69, 2.75, 1.75, 3.25, 0.50),
    1.125: (4.75, 1.88, 0.75, 3.00, 1.88, 3.50, 0.50),
    1.250: (5.00, 2.00, 0.81, 3.25, 2.00, 3.75, 0.56),
    1.375: (5.25, 2.13, 0.88, 3.50, 2.13, 4.00, 0.56),
    1.500: (5.75, 2.25, 0.94, 3.75, 2.25, 4.25, 0.63),
    1.625: (6.00, 2.38, 1.00, 4.00, 2.50, 4.50, 0.63),
    1.750: (6.50, 2.50, 1.06, 4.25, 2.63, 4.75, 0.69),
    1.875: (6.75, 2.63, 1.13, 4.50, 2.75, 5.00, 0.69),
    2.000: (7.00, 2.75, 1.19, 4.75, 2.88, 5.25, 0.75),
    2.125: (7.50, 2.88, 1.25, 5.00, 3.00, 5.50, 0.75),
    2.375: (8.25, 3.13, 1.38, 5.50, 3.25, 6.00, 0.88),
}


def _pillow_block_lookup(bore: float):
    """Return pillow block dims for nearest standard bore size."""
    keys = sorted(_PILLOW_BLOCK.keys())
    for k in keys:
        if bore <= k:
            return _PILLOW_BLOCK[k]
    return _PILLOW_BLOCK[keys[-1]]


def create_pillow_block_bearing(shaft_bore_in: float) -> bd.Compound:
    """
    UCP-series pillow block bearing sized from shaft bore.

    Geometry: rectangular base plate with 2 bolt holes, cylindrical housing
    on top with bore hole through center.  Built with base bottom at Y=0,
    housing bore axis along Z, centered at X=0.
    """
    base_w, base_l, base_t, housing_od, housing_h, bolt_sp, bolt_d = \
        _pillow_block_lookup(shaft_bore_in)

    housing_r = housing_od / 2.0
    bore_r = shaft_bore_in / 2.0
    bolt_r = bolt_d / 2.0

    parts = []

    # Base plate — centered on X and Z, bottom at Y=0
    with bd.BuildPart() as bp:
        bd.Box(base_w, base_t, base_l,
               align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.CENTER))
    parts.append(bp.part.solid())

    # Housing cylinder — centered on base, bottom at Y=base_t
    # Bore axis along Z (shaft axis)
    with bd.BuildPart() as bp:
        bd.Cylinder(housing_r, base_l,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
    housing = bp.part.solid()
    housing = housing.moved(bd.Location((0, base_t + housing_r, 0)))

    # Bore hole through housing center (along Z)
    with bd.BuildPart() as bp:
        bd.Cylinder(bore_r, base_l + 2.0,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER))
    bore_cyl = bp.part.solid()
    bore_cyl = bore_cyl.moved(bd.Location((0, base_t + housing_r, 0)))

    housing = housing.cut(bore_cyl)
    if not isinstance(housing, bd.Solid):
        housing = max(list(housing), key=lambda s: s.volume)
    parts.append(housing)

    # 2 bolt holes through base plate
    for sx in (-1, 1):
        with bd.BuildPart() as bp:
            bd.Cylinder(bolt_r, base_t * 3,
                        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        hole = bp.part.solid()
        hole = hole.moved(bd.Location((sx * bolt_sp / 2.0, -base_t, 0)))
        # Cut from base plate (first part)
        parts[0] = parts[0].cut(hole)
        if not isinstance(parts[0], bd.Solid):
            parts[0] = max(list(parts[0]), key=lambda s: s.volume)

    return bd.Compound(children=parts)


def create_shim_plate(
    width: float,
    length: float,
    thickness: float,
) -> bd.Solid:
    """
    Steel shim plate — flat rectangular block.

    Used under motor feet (thin, ~0.5") or under bearing bases (thicker,
    machined riser block).  Bottom at Y=0, centered in X and Z.
    """
    with bd.BuildPart() as bp:
        bd.Box(width, thickness, length,
               align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.CENTER))
    return bp.part.solid()


def create_coupling(
    shaft_diameter_in: float,
    length: float = 0.0,
) -> bd.Solid:
    """
    Shaft coupling between fan shaft and motor shaft.

    Stepped cylinder: two flanges (OD = 2× shaft) with a hub between.
    Built along Z, centered at Z=0.

    length defaults to 1.5× shaft diameter if not specified.
    """
    shaft_r = shaft_diameter_in / 2.0
    if length <= 0:
        length = shaft_diameter_in * 1.5
    flange_od = shaft_diameter_in * 2.0
    flange_r = flange_od / 2.0
    hub_od = shaft_diameter_in * 1.5
    hub_r = hub_od / 2.0
    flange_len = length * 0.2
    hub_len = length - 2 * flange_len

    parts = []
    # Fan-side flange (-Z)
    with bd.BuildPart() as bp:
        bd.Cylinder(flange_r, flange_len,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    parts.append(bp.part.solid().moved(
        bd.Location((0, 0, -length / 2.0))))

    # Hub (center)
    with bd.BuildPart() as bp:
        bd.Cylinder(hub_r, hub_len,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    parts.append(bp.part.solid().moved(
        bd.Location((0, 0, -length / 2.0 + flange_len))))

    # Motor-side flange (+Z)
    with bd.BuildPart() as bp:
        bd.Cylinder(flange_r, flange_len,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    parts.append(bp.part.solid().moved(
        bd.Location((0, 0, length / 2.0 - flange_len))))

    return bd.Compound(children=parts)


# ---------------------------------------------------------------------------
# NEMA motor frame lookup (approximate dimensions by HP at 1800 RPM)
# Keys: shaft_hp → (frame_dia, frame_length, foot_height, shaft_stub_dia)
# All dimensions in inches.
# ---------------------------------------------------------------------------
_NEMA_FRAMES = {
    0.5:  (5.5,  7.0,  2.75, 0.625),
    0.75: (5.5,  7.5,  2.75, 0.625),
    1.0:  (6.5,  8.0,  3.25, 0.750),
    1.5:  (6.5,  9.0,  3.25, 0.750),
    2.0:  (7.0,  9.5,  3.50, 0.875),
    3.0:  (7.5, 10.5,  3.75, 0.875),
    5.0:  (8.5, 12.0,  4.25, 1.125),
    7.5:  (9.5, 13.0,  4.75, 1.125),
    10.0: (10.5, 14.5, 5.25, 1.375),
    15.0: (11.0, 16.0, 5.50, 1.625),
    20.0: (12.0, 18.0, 6.00, 1.625),
    25.0: (13.0, 19.0, 6.50, 1.875),
    30.0: (13.0, 20.0, 6.50, 1.875),
    40.0: (14.0, 22.0, 7.00, 2.125),
    50.0: (15.0, 24.0, 7.50, 2.375),
}


def _nema_lookup(hp: float):
    """Return (frame_dia, frame_len, foot_h, stub_dia) for nearest NEMA frame."""
    keys = sorted(_NEMA_FRAMES.keys())
    # Find the smallest frame that meets or exceeds the HP
    for k in keys:
        if hp <= k:
            return _NEMA_FRAMES[k]
    return _NEMA_FRAMES[keys[-1]]


def create_motor(
    shaft_hp: float,
    shaft_diameter_in: float = 0.0,
) -> bd.Compound:
    """
    NEMA motor — simplified representation from HP rating.

    Built along +Z from Z=0 (front endbell = drive end).
    Components:
        - Front endbell (short cylinder, drive end)
        - Stator frame (main body cylinder)
        - Rear endbell + fan cowl (slightly larger cylinder)
        - Mounting feet (two boxes at bottom)
        - Terminal box (box on top)

    Motor centerline at Y=foot_height (elevated by mounting feet).
    """
    frame_dia, frame_len, foot_h, stub_dia = _nema_lookup(shaft_hp)
    if shaft_diameter_in > 0:
        stub_dia = shaft_diameter_in

    frame_r = frame_dia / 2.0
    endbell_len = frame_len * 0.12
    body_len = frame_len * 0.64
    cowl_len = frame_len * 0.24
    cowl_r = frame_r * 1.08

    parts = []
    z = 0.0

    # Front endbell (drive end, at Z=0)
    with bd.BuildPart() as bp:
        bd.Cylinder(frame_r, endbell_len,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    parts.append(bp.part.solid().moved(bd.Location((0, 0, z))))
    z += endbell_len

    # Stator frame (main body)
    with bd.BuildPart() as bp:
        bd.Cylinder(frame_r * 0.98, body_len,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    parts.append(bp.part.solid().moved(bd.Location((0, 0, z))))
    z += body_len

    # Rear endbell + fan cowl
    with bd.BuildPart() as bp:
        bd.Cylinder(cowl_r, cowl_len,
                    align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    parts.append(bp.part.solid().moved(bd.Location((0, 0, z))))

    # Mounting feet (two boxes, one each side in X)
    foot_w = frame_dia * 0.25       # X width of each foot
    foot_len = frame_len * 0.80     # Z length of feet
    foot_t = 0.375                  # foot plate thickness (Y)
    foot_z0 = frame_len * 0.10     # start slightly inset from front

    for sx in (-1, 1):
        with bd.BuildPart() as bp:
            bd.Box(foot_w, foot_t, foot_len,
                   align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN))
        foot = bp.part.solid()
        foot = foot.moved(bd.Location((
            sx * frame_r * 0.7,
            -frame_r,
            foot_z0)))
        parts.append(foot)

    # Terminal box (on top of stator frame)
    tb_w = frame_dia * 0.40
    tb_h = frame_dia * 0.30
    tb_d = body_len * 0.35
    with bd.BuildPart() as bp:
        bd.Box(tb_w, tb_h, tb_d,
               align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.CENTER))
    tbox = bp.part.solid()
    tbox = tbox.moved(bd.Location((
        0, frame_r * 0.85,
        endbell_len + body_len * 0.5)))
    parts.append(tbox)

    # The motor is built with centerline at Y=0.
    # Feet bottom at Y = -frame_r. NEMA foot_h = shaft center to base
    # (the "D" dimension). Shift so foot bottom at Y=0, shaft center at
    # Y=foot_h.
    result = bd.Compound(children=parts)
    result = result.moved(bd.Location((0, foot_h, 0)))

    return result


def create_base_frame(
    length_in: float,
    width_in: float,
    height_in: float,
    member_size: float = 3.0,
) -> bd.Compound:
    """
    Low structural base frame (channel iron).

    4 vertical legs at corners + 4 horizontal rails at top forming a
    rectangular frame.  The scroll housing sits directly on this frame.
    Bottom at Y=0, centered in X and Z.

    Typical height: 4–8" (just enough for forklift tines / anchor bolts).
    """
    half_w = width_in / 2.0
    half_l = length_in / 2.0
    m = member_size

    parts = []

    # 4 vertical legs at corners
    for sx in (-1, 1):
        for sz in (-1, 1):
            with bd.BuildPart() as bp:
                bd.Box(m, height_in, m,
                       align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.CENTER))
            leg = bp.part.solid()
            leg = leg.moved(bd.Location((sx * (half_w - m / 2),
                                         0,
                                         sz * (half_l - m / 2))))
            parts.append(leg)

    # 2 long rails along Z at top of legs
    rail_z_len = length_in - 2 * m
    if rail_z_len > 0:
        for sx in (-1, 1):
            with bd.BuildPart() as bp:
                bd.Box(m, m, rail_z_len,
                       align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.CENTER))
            rail = bp.part.solid()
            rail = rail.moved(bd.Location((sx * (half_w - m / 2),
                                           height_in - m,
                                           0)))
            parts.append(rail)

    # 2 short rails along X at top of legs
    rail_x_len = width_in - 2 * m
    if rail_x_len > 0:
        for sz in (-1, 1):
            with bd.BuildPart() as bp:
                bd.Box(rail_x_len, m, m,
                       align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.CENTER))
            rail = bp.part.solid()
            rail = rail.moved(bd.Location((0,
                                           height_in - m,
                                           sz * (half_l - m / 2))))
            parts.append(rail)

    return bd.Compound(children=parts)


def create_inlet_ring(
    eye_diameter_in: float,
    sleeve_length: float = 6.0,
    leg: float = 2.0,
    t: float = 0.25,
) -> bd.Compound:
    """
    Fan inlet ring assembly — 3 revolved pieces concentric to inlet eye.

    Part 3 (+Z, housing side): 2x2x1/4 angle, toe radially out.
        Radial flange at housing face (+Z side); axial leg extends -Z into sleeve.
    Part 2 (sleeve): 1/4" plate cylinder, sleeve_length long.
    Part 1 (-Z, duct side): 2x2x1/4 angle, toe radially out.
        Radial flange faces +Z (duct stops against it); axial leg extends +Z
        into sleeve bore.

    Built with housing face at Z=0.  Sleeve extends -Z.
    Duct connection flange faces +Z.
    Positioned by assembly at the front plate (Z = -W_ext/2).
    """
    eye_r = eye_diameter_in / 2.0
    parts = []

    # --- Part 3: Housing-side angle (corner at Z=0) ---
    # Radial flange: Z from 0 to +t (against housing cheek, extends +Z).
    # Axial leg: Z from 0 to -leg (extends into sleeve).
    p3 = [
        (eye_r, t),
        (eye_r + leg, t),
        (eye_r + leg, 0),
        (eye_r + t, 0),
        (eye_r + t, -leg),
        (eye_r, -leg),
    ]
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.XZ):
            bd.Polygon(p3, align=None)
        bd.revolve(axis=bd.Axis.Z, revolution_arc=360)
    parts.append(bp.part.solid())

    # --- Part 2: Sleeve (cylindrical plate) ---
    # Runs from Z=0 to Z=-sleeve_length between the two angle flanges.
    p2 = [
        (eye_r, 0),
        (eye_r + t, 0),
        (eye_r + t, -sleeve_length),
        (eye_r, -sleeve_length),
    ]
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.XZ):
            bd.Polygon(p2, align=None)
        bd.revolve(axis=bd.Axis.Z, revolution_arc=360)
    parts.append(bp.part.solid())

    # --- Part 1: Duct-side angle (corner at Z=-sleeve_length) ---
    # Radial flange: Z from -sleeve_length to -(sleeve_length - t), faces +Z.
    # Axial leg: Z from -sleeve_length to -(sleeve_length - leg), extends +Z
    #            into sleeve bore.
    z1 = -sleeve_length
    p1 = [
        (eye_r, z1),
        (eye_r + leg, z1),
        (eye_r + leg, z1 + t),
        (eye_r + t, z1 + t),
        (eye_r + t, z1 + leg),
        (eye_r, z1 + leg),
    ]
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.XZ):
            bd.Polygon(p1, align=None)
        bd.revolve(axis=bd.Axis.Z, revolution_arc=360)
    parts.append(bp.part.solid())

    return bd.Compound(children=parts)


def create_pedestal(
    bottom_width: float,
    top_width: float,
    height: float,
    depth: float,
    plate_t: float = 0.25,
    access_hole_dia: float = 0.0,
) -> bd.Compound:
    """
    Unified fan pedestal — fully enclosed trapezoidal box.

    Supports the entire drive side: bearings, coupling, and motor all
    mount on the top plate.  Trapezoid profile in XY plane, centered
    on X=0.  Bottom edge (wider) at Y=0, top edge (narrower) at Y=height.
    Two side plates spaced ``depth`` apart in Z, connected by top plate
    and front/back closure plates.  Access holes in each side plate.

    Parameters
    ----------
    bottom_width : X-span of the wider bottom edge.
    top_width    : X-span of the narrower top edge.
    height       : Y distance from base to mounting surface.
    depth        : Z spacing between the two side plates.
    plate_t      : plate thickness (default 1/4").
    access_hole_dia : circular access/ventilation hole in each side plate.
                      0 = no hole.
    """
    half_bot = bottom_width / 2.0
    half_top = top_width / 2.0
    half_d = depth / 2.0

    parts = []

    # --- Side plates (×2) ---
    trap_pts = [
        (-half_bot, 0),
        (half_bot, 0),
        (half_top, height),
        (-half_top, height),
    ]

    for sz in (-1, 1):
        with bd.BuildPart() as bp:
            with bd.BuildSketch(bd.Plane.XY):
                bd.Polygon(trap_pts, align=None)
            bd.extrude(amount=plate_t)
        plate = bp.part.solid()

        # Cut access hole if requested
        if access_hole_dia > 0:
            hole_cx = 0.0
            hole_cy = height * 0.40  # centered at 40% of height
            with bd.BuildPart() as hp:
                bd.Cylinder(access_hole_dia / 2.0, plate_t * 3,
                            align=(bd.Align.CENTER, bd.Align.CENTER,
                                   bd.Align.MIN))
            hole = hp.part.solid()
            # Cylinder built along Z; rotate to align with plate normal
            hole = hole.moved(bd.Location((hole_cx, hole_cy, -plate_t)))
            plate = plate.cut(hole)
            if not isinstance(plate, bd.Solid):
                plate = max(list(plate), key=lambda s: s.volume)

        # Position: plate extrusion is in +Z from Z=0.
        # Side 1: inner face at Z = -half_d, outer at -(half_d + plate_t)
        # Side 2: inner face at Z = +half_d, outer at +(half_d + plate_t)
        if sz == -1:
            z_pos = -(half_d + plate_t)
        else:
            z_pos = half_d
        plate = plate.moved(bd.Location((0, 0, z_pos)))
        parts.append(plate)

    # --- Top plate (horizontal, connects the two side plates) ---
    with bd.BuildPart() as bp:
        bd.Box(top_width, plate_t, depth,
               align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.CENTER))
    top_plate = bp.part.solid()
    top_plate = top_plate.moved(bd.Location((0, height, 0)))
    parts.append(top_plate)

    # --- Left and right closure plates (angled, matching trapezoid slope) ---
    # Each closure plate follows the slope of the trapezoid from bottom edge
    # to top edge, filling the gap between the two side plates (in Z).
    # Profile in YZ plane, extruded plate_t in X.
    for sx in (-1, 1):
        # Trapezoid edge runs from (±half_bot, 0) to (±half_top, height).
        # Build a rectangular plate in YZ, then position at the slope.
        x_bot = sx * half_bot
        x_top = sx * half_top
        # The angled plate profile as a parallelogram in XY, extruded in Z
        slope_pts = [
            (x_bot, 0),
            (x_bot + sx * plate_t, 0),
            (x_top + sx * plate_t, height),
            (x_top, height),
        ]
        with bd.BuildPart() as bp:
            with bd.BuildSketch(bd.Plane.XY):
                bd.Polygon(slope_pts, align=None)
            bd.extrude(amount=depth + 2 * plate_t)
        closure = bp.part.solid()
        closure = closure.moved(bd.Location((0, 0, -(half_d + plate_t))))
        parts.append(closure)

    return bd.Compound(children=parts)


# ---------------------------------------------------------------------------
# Layer B — USD Assembly Creator
# ---------------------------------------------------------------------------

_COLORS = {
    "ImpellerDisks": (0.60, 0.62, 0.65),
    "Blades":        (0.70, 0.72, 0.75),
    "Housing":       (0.45, 0.45, 0.48),
    "OutletDuct":    (0.48, 0.48, 0.50),
    "OutletFlange":  (0.40, 0.40, 0.42),
    "InletFlange":   (0.40, 0.40, 0.42),
    "InletRing":     (0.85, 0.45, 0.20),
    "Shaft":         (0.55, 0.55, 0.58),
    "BaseFrame":     (0.35, 0.35, 0.38),
    "Pedestal":      (0.45, 0.45, 0.48),
    "BearingA":      (0.30, 0.30, 0.32),
    "BearingB":      (0.30, 0.30, 0.32),
    "BearingShimA":  (0.50, 0.50, 0.52),
    "BearingShimB":  (0.50, 0.50, 0.52),
    "MotorShimL":    (0.50, 0.50, 0.52),
    "MotorShimR":    (0.50, 0.50, 0.52),
    "Coupling":      (0.50, 0.50, 0.52),
    "Motor":         (0.30, 0.40, 0.60),
}


_DISCHARGE_ANGLES = {"right": 0.0, "up": 90.0, "left": 180.0, "down": 270.0}


class FanAssembly:
    """USD assembly creator for centrifugal fan geometry."""

    @staticmethod
    def create(stage, path: str, acoustic_result, discharge: str = "right"):
        from pxr import UsdGeom, Gf, Vt
        from ...utils import usd_utils

        acou = acoustic_result
        struct = acou.structural
        vol = struct.volute
        aero = vol.aero
        cls = aero.classification

        tip_d = aero.passage.tip_diameter_in
        hub_d = aero.passage.hub_diameter_in
        num_blades = aero.blade.num_blades
        stagger = aero.blade.stagger_deg
        tip_r = tip_d / 2.0
        D = tip_d  # impeller diameter for normalized dimensions
        volute_width = vol.volute_width_in

        shaft_d = struct.shaft.diameter_in
        bearing_span = struct.shaft.bearing_span_in
        overhang = struct.shaft.overhang_in

        cfm, inwg = cls.design_point.to_us()

        # Spec-derived dimensions (spiral normalized to D, depth from solver)
        scroll_arc_deg = 270.0
        R_cutoff = 0.540 * D
        R_end = R_cutoff * (1.0017 ** scroll_arc_deg)
        max_r = R_end * 1.05
        wall_t = 0.012 * D
        W_ext = volute_width
        W_int = W_ext - 2 * wall_t
        half_w = W_ext / 2.0
        flange_t = 0.016 * D

        # Impeller blade width = housing internal width minus running clearance
        impeller_clearance = 0.25  # 1/8" each side
        impeller_width = W_int - impeller_clearance

        # Motor dimensions from NEMA lookup
        hp = cls.shaft_power_hp
        frame_dia, motor_frame_len, motor_foot_h, _ = _nema_lookup(hp)
        coupling_len = shaft_d * 1.5

        # -----------------------------------------------------------------
        # Drivetrain layout along Z axis (shaft axis)
        # Housing centered at Z=0, back plate at Z = +half_w
        # Tight layout — components close together like real fan
        # -----------------------------------------------------------------
        housing_back_z = half_w

        # Bearing A (inboard) — tight clearance from back plate
        bearing_A_z = housing_back_z + shaft_d * 1.5
        # Bearing B (outboard) — bearing_span from A
        bearing_B_z = bearing_A_z + bearing_span
        # Impeller position — cantilevered before bearing A
        impeller_z = bearing_A_z - overhang

        # Coupling sits just past bearing B
        coupling_gap = shaft_d * 1.0
        coupling_z = bearing_B_z + coupling_gap + coupling_len / 2.0

        # Motor starts just past coupling (tight gap)
        motor_gap = shaft_d * 0.5
        motor_z_start = coupling_z + coupling_len / 2.0 + motor_gap
        motor_z_end = motor_z_start + motor_frame_len

        # Fan shaft: from impeller through both bearings to coupling
        shaft_z_fan = impeller_z
        shaft_z_coupling = coupling_z - coupling_len / 2.0
        shaft_total_len = shaft_z_coupling - shaft_z_fan
        shaft_center_z = (shaft_z_fan + shaft_z_coupling) / 2.0

        # Impeller Z position (hub disk start in housing)
        imp_z = -half_w + wall_t + impeller_clearance / 2.0

        # -----------------------------------------------------------------
        # Support structure (SWSI Arrangement 1/3):
        #
        # 1. BASE FRAME — low channel-iron frame under scroll + drivetrain.
        #    Height ~6".  Scroll housing sits directly on this.
        #    center_y = base_h + max_r  (housing center = shaft center)
        #
        # 2. PEDESTAL — trapezoidal stand behind scroll back plate.
        #    Sits on base frame.  Z depth = 2× motor length.
        #    Top plate is a flat mounting surface.
        #
        # 3. MOTOR SHIMS — 1/2" steel plates under each motor foot.
        #    Fine alignment adjustment (standard practice).
        #
        # 4. BEARING SHIM BLOCKS — steel risers under each pillow block.
        #    Make up the height difference between motor_foot_h and
        #    bearing_rise so both shaft centerlines align.
        # -----------------------------------------------------------------
        pb_dims = _pillow_block_lookup(shaft_d)
        pb_base_t = pb_dims[2]
        pb_housing_r = pb_dims[3] / 2.0
        pb_base_w = pb_dims[0]  # pillow block base width
        pb_base_l = pb_dims[1]  # pillow block base length
        bearing_rise = pb_base_t + pb_housing_r

        # Base frame
        base_h = max(6.0, D * 0.08)
        base_member = max(2.0, D * 0.04)

        # Validate discharge direction (stored in metadata, geometry always +Y for now)
        discharge = discharge if discharge in _DISCHARGE_ANGLES else "right"

        # Shaft centerline: base top + scroll center radius
        center_y = base_h + max_r

        # Motor shim thickness (standard alignment shim)
        motor_shim_t = 0.5  # 1/2"

        # Pedestal top plate: motor feet + shim reach shaft centerline.
        # ped_top + motor_shim_t + motor_foot_h = center_y
        ped_top_y = center_y - motor_foot_h - motor_shim_t
        ped_height = max(ped_top_y - base_h, 4.0)

        # Bearing shim blocks: make up difference so bearing center = shaft
        # ped_top + brg_shim_t + bearing_rise = center_y
        brg_shim_t = center_y - (base_h + ped_height) - bearing_rise
        brg_shim_t = max(brg_shim_t, 0.25)  # minimum 1/4" shim

        # Bearing Y: shim bottom on pedestal top, bearing on shim
        bearing_y = base_h + ped_height + brg_shim_t

        # Motor Y: shim bottom on pedestal top, motor feet on shim
        motor_y = base_h + ped_height + motor_shim_t

        # Base frame: spans full assembly
        base_w = 2.0 * max_r + 4.0
        base_front_z = -half_w - 2.0
        base_rear_z = motor_z_end + 2.0
        base_l = base_rear_z - base_front_z
        base_center_z = (base_front_z + base_rear_z) / 2.0

        # Pedestal: flush with housing back plate, covers entire drivetrain
        ped_front_z = housing_back_z   # flush with scroll back plate
        ped_rear_z = motor_z_end + 1.0  # 1" past motor rear
        ped_depth = ped_rear_z - ped_front_z
        ped_center_z = (ped_front_z + ped_rear_z) / 2.0

        # Pedestal widths — proportioned to drivetrain
        motor_foot_x_span = frame_dia * 0.7 + frame_dia * 0.25
        ped_top_w = max(motor_foot_x_span + 2.0, pb_base_w + 2.0)
        ped_bot_w = ped_top_w * 1.4
        ped_hole = min(0.15 * D, ped_height * 0.5) if ped_height > 6.0 else 0.0

        # ----- DEBUG DUMP — all drivetrain dimensions -----
        print(f"[FanAssembly] === DRIVETRAIN DEBUG ===")
        print(f"  tip_d={tip_d:.2f}  hp={hp:.1f}  shaft_d={shaft_d:.3f}")
        print(f"  base_h={base_h:.1f}  max_r={max_r:.2f}  center_y={center_y:.2f}")
        print(f"  bearing_span={bearing_span:.2f}  overhang={overhang:.2f}")
        print(f"  motor: dia={frame_dia:.1f}  len={motor_frame_len:.1f}  foot_h={motor_foot_h:.2f}")
        print(f"  bearing_rise={bearing_rise:.2f}  brg_shim_t={brg_shim_t:.2f}  motor_shim_t={motor_shim_t:.2f}")
        print(f"  ped: h={ped_height:.2f} top_y={base_h+ped_height:.2f}  depth={ped_depth:.1f}")
        print(f"  bearing_y={bearing_y:.2f}  brg_center={bearing_y+bearing_rise:.2f}  shaft={center_y:.2f}")
        print(f"  motor_y={motor_y:.2f}  motor_shaft={motor_y+motor_foot_h:.2f}  shaft={center_y:.2f}")
        print(f"  ped: bot_w={ped_bot_w:.1f}  top_w={ped_top_w:.1f}  z={ped_front_z:.1f}..{ped_rear_z:.1f}")
        print(f"  base: w={base_w:.1f}  l={base_l:.1f}  h={base_h:.1f}")
        print(f"  Z: brg_A={bearing_A_z:.1f} brg_B={bearing_B_z:.1f} coupling={coupling_z:.1f} motor={motor_z_start:.1f}..{motor_z_end:.1f}")
        print(f"[FanAssembly] === END DEBUG ===")

        root_xform = UsdGeom.Xform.Define(stage, path)

        def _component(name, solid_or_compound, translate=None,
                       rotate=None, color_key=None):
            """Create a USD mesh for a component with optional transform."""
            try:
                child_path = f"{path}/{name}"
                usd_utils.create_mesh_from_shape(stage, child_path,
                                                 solid_or_compound)
                prim = stage.GetPrimAtPath(child_path)
                if prim.IsValid():
                    xf = UsdGeom.Xformable(prim)
                    if translate:
                        xf.AddTranslateOp().Set(translate)
                    if rotate:
                        xf.AddRotateXYZOp().Set(rotate)
                if color_key and color_key in _COLORS:
                    prim = stage.GetPrimAtPath(child_path)
                    if prim.IsValid():
                        mesh = UsdGeom.Mesh(prim)
                        if mesh:
                            mesh.CreateDisplayColorAttr().Set(
                                Vt.Vec3fArray([Gf.Vec3f(*_COLORS[color_key])]))
                print(f"[FanAssembly] {name}: OK")
                return True
            except Exception as e:
                print(f"[FanAssembly] {name} FAILED: {e}")
                import traceback; traceback.print_exc()
                return False

        # --- IMPELLER DISKS ---
        disks = create_impeller_disks(tip_d, hub_d, impeller_width)
        _component("ImpellerDisks", disks,
                    Gf.Vec3d(0, center_y, imp_z), color_key="ImpellerDisks")

        # --- BLADES ---
        blades = create_blades(tip_d, hub_d, impeller_width,
                               num_blades, stagger)
        _component("Blades", blades,
                    Gf.Vec3d(0, center_y, imp_z), color_key="Blades")

        # --- SCROLL HOUSING ---
        try:
            print(f"[FanAssembly] Housing: tip_r={tip_r:.2f}, volute_w={volute_width:.2f}, "
                  f"wall_t={struct.housing.wall_thickness_in:.3f}, hub_d={hub_d:.2f}")
            housing = create_scroll_housing(
                tip_r, volute_width,
                struct.housing.wall_thickness_in, hub_d)
            _component("Housing", housing,
                        Gf.Vec3d(0, center_y, 0), color_key="Housing")
        except Exception as e:
            print(f"[FanAssembly] Housing GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- DISCHARGE FRAME (2x2x1/4 angle perimeter) ---
        try:
            frame = create_discharge_frame(R_end, W_ext)
            _component("DischargeFrame", frame,
                        Gf.Vec3d(0, center_y + R_end, 0),
                        color_key="Housing")
        except Exception as e:
            print(f"[FanAssembly] DischargeFrame GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- INLET RING (3-piece revolved assembly at eye opening) ---
        try:
            eye_dia = 0.72 * D
            inlet_ring = create_inlet_ring(eye_dia)
            _component("InletRing", inlet_ring,
                        Gf.Vec3d(0, center_y, -half_w),
                        color_key="InletRing")
        except Exception as e:
            print(f"[FanAssembly] InletRing GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- BASE FRAME (low channel frame under entire assembly) ---
        try:
            base = create_base_frame(base_l, base_w, base_h,
                                     member_size=base_member)
            _component("BaseFrame", base,
                        Gf.Vec3d(0, 0, base_center_z),
                        color_key="BaseFrame")
        except Exception as e:
            print(f"[FanAssembly] BaseFrame GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- PEDESTAL (short stand behind scroll, on base frame) ---
        try:
            pedestal = create_pedestal(
                ped_bot_w, ped_top_w, ped_height, ped_depth,
                access_hole_dia=ped_hole)
            _component("Pedestal", pedestal,
                        Gf.Vec3d(0, base_h, ped_center_z),
                        color_key="Pedestal")
        except Exception as e:
            print(f"[FanAssembly] Pedestal GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- BEARING SHIM BLOCKS (steel risers on pedestal top plate) ---
        ped_top_abs_y = base_h + ped_height
        try:
            brg_shim_a = create_shim_plate(pb_base_w, pb_base_l, brg_shim_t)
            _component("BearingShimA", brg_shim_a,
                        Gf.Vec3d(0, ped_top_abs_y, bearing_A_z),
                        color_key="BearingShimA")
        except Exception as e:
            print(f"[FanAssembly] BearingShimA GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        try:
            brg_shim_b = create_shim_plate(pb_base_w, pb_base_l, brg_shim_t)
            _component("BearingShimB", brg_shim_b,
                        Gf.Vec3d(0, ped_top_abs_y, bearing_B_z),
                        color_key="BearingShimB")
        except Exception as e:
            print(f"[FanAssembly] BearingShimB GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- BEARING A (inboard, nearest housing) ---
        try:
            bearing_a = create_pillow_block_bearing(shaft_d)
            _component("BearingA", bearing_a,
                        Gf.Vec3d(0, bearing_y, bearing_A_z),
                        color_key="BearingA")
        except Exception as e:
            print(f"[FanAssembly] BearingA GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- BEARING B (outboard) ---
        try:
            bearing_b = create_pillow_block_bearing(shaft_d)
            _component("BearingB", bearing_b,
                        Gf.Vec3d(0, bearing_y, bearing_B_z),
                        color_key="BearingB")
        except Exception as e:
            print(f"[FanAssembly] BearingB GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- SHAFT ---
        try:
            shaft_solid = create_shaft(shaft_d, shaft_total_len)
            _component("Shaft", shaft_solid,
                        Gf.Vec3d(0, center_y, shaft_center_z),
                        color_key="Shaft")
        except Exception as e:
            print(f"[FanAssembly] Shaft GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- COUPLING ---
        try:
            coupling = create_coupling(shaft_d, coupling_len)
            _component("Coupling", coupling,
                        Gf.Vec3d(0, center_y, coupling_z),
                        color_key="Coupling")
        except Exception as e:
            print(f"[FanAssembly] Coupling GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- MOTOR SHAFT (stub from motor drive end to coupling) ---
        try:
            motor_shaft_z_start = coupling_z + coupling_len / 2.0
            motor_shaft_len = motor_z_start - motor_shaft_z_start
            if motor_shaft_len > 0:
                motor_shaft_center_z = (motor_shaft_z_start + motor_z_start) / 2.0
                motor_shaft = create_shaft(shaft_d, motor_shaft_len)
                _component("MotorShaft", motor_shaft,
                            Gf.Vec3d(0, center_y, motor_shaft_center_z),
                            color_key="Shaft")
        except Exception as e:
            print(f"[FanAssembly] MotorShaft GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- MOTOR SHIMS (1/2" plates under each motor foot) ---
        try:
            # Motor foot positions (must match create_motor internals)
            foot_w = frame_dia * 0.25
            foot_len = motor_frame_len * 0.80
            foot_z0 = motor_frame_len * 0.10
            motor_shim_z = motor_z_start + foot_z0 + foot_len / 2.0
            for sx, name in [(-1, "MotorShimL"), (1, "MotorShimR")]:
                shim = create_shim_plate(foot_w + 1.0, foot_len + 1.0,
                                         motor_shim_t)
                shim_x = sx * frame_dia / 2.0 * 0.7
                _component(name, shim,
                            Gf.Vec3d(shim_x, ped_top_abs_y, motor_shim_z),
                            color_key=name)
        except Exception as e:
            print(f"[FanAssembly] MotorShims GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- MOTOR (NEMA frame from HP rating) ---
        try:
            motor = create_motor(hp, shaft_d)
            # Motor foot bottom at Y=0 in local coords, shaft at Y=foot_h.
            # Place so foot bottom sits on motor shims.
            _component("Motor", motor,
                        Gf.Vec3d(0, motor_y, motor_z_start),
                        color_key="Motor")
        except Exception as e:
            print(f"[FanAssembly] Motor GEOMETRY FAILED: {e}")
            import traceback; traceback.print_exc()

        # --- Metadata ---
        prim = root_xform.GetPrim()
        prim.SetCustomDataByKey("twin:generator", "fan_assembly")
        prim.SetCustomDataByKey("twin:discharge_direction", discharge)
        prim.SetCustomDataByKey("twin:fan_type", cls.fan_type.name)
        prim.SetCustomDataByKey("twin:cfm", cfm)
        prim.SetCustomDataByKey("twin:pressure_inwg", inwg)
        prim.SetCustomDataByKey("twin:rpm", float(aero.rpm))
        prim.SetCustomDataByKey("twin:discharge_velocity_fts", float(vol.discharge.velocity_fts))
        prim.SetCustomDataByKey("twin:impeller_diameter_in", tip_d)
        prim.SetCustomDataByKey("twin:shaft_hp", cls.shaft_power_hp)
        prim.SetCustomDataByKey("twin:overall_lw_dba",
                                acou.spectrum.overall_lw_a_db)

        # Airflow visualization metadata (used by FanAirflowVisualizer)
        prim.SetCustomDataByKey("twin:center_y",    float(center_y))
        prim.SetCustomDataByKey("twin:tip_r",       float(tip_r))
        prim.SetCustomDataByKey("twin:eye_r",       float(0.36 * D))
        prim.SetCustomDataByKey("twin:half_w",      float(half_w))
        prim.SetCustomDataByKey("twin:R_end",       float(R_end))
        prim.SetCustomDataByKey("twin:R_cutoff",    float(R_cutoff))
        prim.SetCustomDataByKey("twin:imp_z",       float(imp_z))
        prim.SetCustomDataByKey("twin:inlet_Cm",    float(aero.inlet_triangle.Cm))
        prim.SetCustomDataByKey("twin:outlet_Cm",   float(aero.outlet_triangle.Cm))
        prim.SetCustomDataByKey("twin:outlet_Cu",   float(aero.outlet_triangle.Cu))

        print(f"[FanAssembly] {path} — {cls.fan_type.name}, "
              f"{cfm:,.0f} CFM @ {inwg:.1f} in.WG, "
              f"D={tip_d:.1f}\", {num_blades} blades, "
              f"center_y={center_y:.1f}\", "
              f"bearing_span={bearing_span:.1f}\", "
              f"bearings at Z={bearing_A_z:.1f}/{bearing_B_z:.1f}")

        return root_xform
