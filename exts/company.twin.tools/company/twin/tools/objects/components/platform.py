import build123d as bd
from build123d import *
from typing import List, Dict, Any
from pxr import Gf, UsdGeom, UsdShade, Sdf


# All 8 base node names and their position functions
BASE_NODE_NAMES = [
    "Base_Corner_FR", "Base_Corner_FL",
    "Base_Corner_BR", "Base_Corner_BL",
    "Base_Mid_Front", "Base_Mid_Back",
    "Base_Mid_Right", "Base_Mid_Left",
]


def _base_node_positions(width, depth, height):
    """Return dict mapping node name → (x, y, z) at base of construction cube."""
    w2 = width / 2.0
    h2 = height / 2.0
    d2 = depth / 2.0
    y = -h2
    return {
        "Base_Corner_FR": (w2, y, d2),
        "Base_Corner_FL": (-w2, y, d2),
        "Base_Corner_BR": (w2, y, -d2),
        "Base_Corner_BL": (-w2, y, -d2),
        "Base_Mid_Front": (0.0, y, d2),
        "Base_Mid_Back":  (0.0, y, -d2),
        "Base_Mid_Right": (w2, y, 0.0),
        "Base_Mid_Left":  (-w2, y, 0.0),
    }


# Leg profile definitions: (outer_size, wall_thickness, corner_radius)
LEG_PROFILES = {
    'HSS2x2x1/8': (2.0, 0.125, 0.25),
    'HSS4x4x1/4': (4.0, 0.250, 0.50),
}
LEG_PROFILE_NAMES = list(LEG_PROFILES.keys())

# Frame profile definitions: (height, width, wall_thickness, corner_radius)
# height = vertical dim (Y), width = horizontal dim (transverse)
FRAME_PROFILES = {
    'HSS2x2x1/8': (2.0, 2.0, 0.125, 0.25),
    'HSS4x4x1/4': (4.0, 4.0, 0.250, 0.50),
}
FRAME_PROFILE_NAMES = list(FRAME_PROFILES.keys())

# Beam segments: pairs of adjacent nodes and their span axis
# Each tuple: (node_from, node_to, axis)
#   axis='x' means beam runs along X, axis='z' means beam runs along Z
def _build_frame_segments(active_nodes):
    """
    Build frame segment list based on which nodes are active.
    If a mid node is active, split the edge into two segments (corner↔mid).
    If not, span the full edge corner-to-corner.
    """
    active = set(active_nodes)
    segments = []

    # Each edge: (corner_a, mid, corner_b, axis)
    edges = [
        ("Base_Corner_FL", "Base_Mid_Front", "Base_Corner_FR", "x"),  # front
        ("Base_Corner_BL", "Base_Mid_Back",  "Base_Corner_BR", "x"),  # back
        ("Base_Corner_FR", "Base_Mid_Right", "Base_Corner_BR", "z"),  # right
        ("Base_Corner_FL", "Base_Mid_Left",  "Base_Corner_BL", "z"),  # left
    ]

    for ca, mid, cb, axis in edges:
        if mid in active:
            # Split into two segments through mid
            if ca in active:
                segments.append((ca, mid, axis))
            if cb in active:
                segments.append((mid, cb, axis))
        else:
            # Direct corner-to-corner
            if ca in active and cb in active:
                segments.append((ca, cb, axis))

    # Cross beams (only if both mids active)
    if "Base_Mid_Left" in active and "Base_Mid_Right" in active:
        segments.append(("Base_Mid_Left", "Base_Mid_Right", "x"))
    if "Base_Mid_Front" in active and "Base_Mid_Back" in active:
        segments.append(("Base_Mid_Front", "Base_Mid_Back", "z"))

    return segments


class PlatformGenerator:
    """
    Industrial platform generator built on construction cube technology.
    Creates a construction-line wireframe skeleton with anchors,
    then adds structural framing and deck plate geometry.
    """

    DECK_THICKNESS = 0.25  # 1/4" checkered plate

    @staticmethod
    def create(stage, path,
               width=120.0, depth=120.0, height=120.0,
               elevation=0.0,
               bp_width=12.0, bp_depth=12.0, bp_thickness=0.5,
               bp_nodes=None,
               leg_profile='HSS4x4x1/4',
               leg_nodes=None,
               frame_profile='HSS4x4x1/4',
               deck_thickness=0.25,
               deck_material='Galvanized'):
        """
        Create a platform at the given path.
        Leg length = height (Y dimension of construction cube).

        Args:
            stage: USD stage
            path: USD prim path
            width: Platform width along X (inches)
            depth: Platform depth along Z (inches)
            height: Construction cube height along Y (inches), also leg length
            elevation: Bottom of platform Y offset (inches)
            bp_width: Base plate width along X (inches)
            bp_depth: Base plate depth along Z (inches)
            bp_thickness: Base plate thickness along +Y (inches)
            bp_nodes: List of node names to place base plates on (None = all 8)
            leg_profile: HSS profile name (key into LEG_PROFILES)
            leg_nodes: List of node names to place legs on (None = same as bp_nodes)
            deck_thickness: Deck plate thickness in inches (extruded +Y)
        """
        leg_length = height
        from ..components.construction_cube import ConstructionCubeGenerator
        from ...utils import usd_utils

        usd_utils.setup_stage_units(stage)

        root_xform = UsdGeom.Xform.Define(stage, path)
        prim = root_xform.GetPrim()
        prim.SetCustomDataByKey("generatorType", "platform")
        prim.SetCustomDataByKey("width", float(width))
        prim.SetCustomDataByKey("depth", float(depth))
        prim.SetCustomDataByKey("height", float(height))
        prim.SetCustomDataByKey("elevation", float(elevation))
        prim.SetCustomDataByKey("bp_width", float(bp_width))
        prim.SetCustomDataByKey("bp_depth", float(bp_depth))
        prim.SetCustomDataByKey("bp_thickness", float(bp_thickness))
        if bp_nodes is not None:
            prim.SetCustomDataByKey("bp_nodes", ",".join(bp_nodes))
        prim.SetCustomDataByKey("leg_profile", leg_profile)
        if leg_nodes is not None:
            prim.SetCustomDataByKey("leg_nodes", ",".join(leg_nodes))
        prim.SetCustomDataByKey("frame_profile", frame_profile)
        prim.SetCustomDataByKey("deck_thickness", float(deck_thickness))
        prim.SetCustomDataByKey("deck_material", deck_material)

        # --- Construction cube wireframe skeleton ---
        edges = ConstructionCubeGenerator.create_edges(width, depth, height)
        lines_path = f"{path}/lines"
        color = Gf.Vec3f(0.0, 0.8, 1.0)  # construction cyan
        usd_utils.create_basis_curves_from_edges(stage, lines_path, edges, color, width=0.5)

        # --- Anchors ---
        anchors_grp_path = f"{path}/anchors"
        UsdGeom.Scope.Define(stage, anchors_grp_path)
        anchor_defs = ConstructionCubeGenerator.get_anchor_definitions(width, depth, height)

        for ad in anchor_defs:
            anchor_path = f"{anchors_grp_path}/{ad['name']}"
            xform = UsdGeom.Xform.Define(stage, anchor_path)
            xform.AddTranslateOp().Set(ad['translate'])
            xform.AddRotateXYZOp().Set(ad['rotate'])

            ap = xform.GetPrim()
            ap.CreateAttribute("twin:is_port", Sdf.ValueTypeNames.Bool).Set(True)
            ap.CreateAttribute("twin:port_type", Sdf.ValueTypeNames.String).Set("Construction_Anchor")
            ap.CreateAttribute("custom:is_anchor", Sdf.ValueTypeNames.Bool).Set(True)

            viz = UsdGeom.Sphere.Define(stage, f"{anchor_path}/viz")
            viz.GetRadiusAttr().Set(0.5)
            viz.GetDisplayColorAttr().Set([ad['color']])

        # --- Base nodes (8): 4 corners + 4 midpoints on bottom face ---
        PlatformGenerator._create_base_nodes(stage, path, width, depth, height)

        # --- Base plates ---
        active_nodes = bp_nodes if bp_nodes is not None else list(BASE_NODE_NAMES)
        if active_nodes:
            PlatformGenerator._create_base_plates(
                stage, path, width, depth, height,
                bp_width, bp_depth, bp_thickness, active_nodes)

        # --- Legs ---
        active_leg_nodes = leg_nodes if leg_nodes is not None else list(active_nodes)
        if active_leg_nodes and leg_profile in LEG_PROFILES:
            PlatformGenerator._create_legs(
                stage, path, width, depth, height,
                bp_thickness, leg_profile, leg_length, active_leg_nodes)

        # --- Upper frames ---
        if active_leg_nodes and frame_profile in FRAME_PROFILES:
            PlatformGenerator._create_upper_frames(
                stage, path, width, depth, height,
                bp_thickness, leg_profile, leg_length,
                frame_profile, active_leg_nodes)

        # --- Deck plate ---
        if deck_thickness > 0:
            PlatformGenerator._create_deck_plate(
                stage, path, width, depth, height,
                bp_thickness, leg_length, frame_profile,
                deck_thickness, deck_material)

        print(f"[Platform] Created at {path}  ({width}x{depth}x{height})")
        return True

    @staticmethod
    def _create_base_nodes(stage, path, width, depth, height):
        w2 = width / 2.0
        h2 = height / 2.0
        d2 = depth / 2.0
        y_base = -h2

        NODE_COLOR = Gf.Vec3f(1.0, 0.5, 0.0)  # orange
        NODE_RADIUS = 1.5

        positions = _base_node_positions(width, depth, height)
        nodes_grp = f"{path}/base_nodes"
        UsdGeom.Scope.Define(stage, nodes_grp)

        for name in BASE_NODE_NAMES:
            pos = positions[name]
            node_path = f"{nodes_grp}/{name}"
            xform = UsdGeom.Xform.Define(stage, node_path)
            xform.AddTranslateOp().Set(Gf.Vec3d(*pos))

            np = xform.GetPrim()
            np.CreateAttribute("twin:is_port", Sdf.ValueTypeNames.Bool).Set(True)
            np.CreateAttribute("twin:port_type", Sdf.ValueTypeNames.String).Set("Platform_Base_Node")
            np.CreateAttribute("custom:is_anchor", Sdf.ValueTypeNames.Bool).Set(True)

            viz = UsdGeom.Sphere.Define(stage, f"{node_path}/viz")
            viz.GetRadiusAttr().Set(NODE_RADIUS)
            viz.GetDisplayColorAttr().Set([NODE_COLOR])

    @staticmethod
    def _create_base_plates(stage, path, width, depth, height,
                            bp_w, bp_d, bp_t, node_names):
        """
        Create base plates centered on selected nodes, extruded in +Y.
        Each plate is a flat rectangular solid: bp_w x bp_t x bp_d
        centered on the node XZ position, bottom at node Y.
        """
        from ...utils import usd_utils

        positions = _base_node_positions(width, depth, height)
        plate_parts = []

        for name in node_names:
            if name not in positions:
                continue
            cx, cy, cz = positions[name]
            # Box centered at origin, then moved to node position
            # Align: CENTER X, MIN Y (+Y extrusion from node), CENTER Z
            with BuildPart() as bp:
                Box(bp_w, bp_t, bp_d,
                    align=(Align.CENTER, Align.MIN, Align.CENTER))
            plate_parts.append(bp.part.move(Location((cx, cy, cz))))

        if plate_parts:
            compound = Compound(children=plate_parts)
            usd_utils.create_mesh_from_shape(
                stage, f"{path}/BasePlates", compound)
            PlatformGenerator._apply_material(stage, f"{path}/BasePlates", "Steel")

    @staticmethod
    def _create_legs(stage, path, width, depth, height,
                     bp_thickness, profile_name, leg_length, node_names):
        """
        Create HSS legs at selected nodes. Each leg starts at the top of the
        base plate (y_node + bp_thickness) and extends upward (+Y) by leg_length.

        Coordinate convention: +Y is ALWAYS UP in Omniverse (Y-Up world).

        The HSS cross-section is built on XY plane, extruded along +Z,
        then rotated +90 around X so +Z becomes +Y (up).
        """
        from ...utils import usd_utils

        outer, wall, cr = LEG_PROFILES[profile_name]
        inner = outer - 2 * wall
        inner_cr = max(0.01, cr - wall)

        positions = _base_node_positions(width, depth, height)
        leg_parts = []

        for name in node_names:
            if name not in positions:
                continue
            cx, cy, cz = positions[name]
            y_bottom = cy + bp_thickness  # top of base plate

            # Build HSS cross-section on XY, extrude along Z
            with BuildPart() as bp:
                with BuildSketch(Plane.XY):
                    RectangleRounded(outer, outer, radius=cr)
                    RectangleRounded(inner, inner, radius=inner_cr,
                                     mode=Mode.SUBTRACT)
                extrude(amount=leg_length)

            # Rotate -90 around X so +Z extrusion becomes +Y (up)
            leg = bp.part.rotate(Axis.X, -90)
            leg = leg.move(Location((cx, y_bottom, cz)))
            leg_parts.append(leg)

        if leg_parts:
            compound = Compound(children=leg_parts)
            usd_utils.create_mesh_from_shape(
                stage, f"{path}/Legs", compound)
            PlatformGenerator._apply_material(stage, f"{path}/Legs", "Galvanized")

    @staticmethod
    def _create_upper_frames(stage, path, width, depth, height,
                             bp_thickness, leg_profile, leg_length,
                             frame_profile, active_leg_nodes):
        """
        Create upper frame beams connecting legs at the top.
        +Y is ALWAYS UP.

        - Frame top is collinear with leg top
        - Frame spans face-to-face between adjacent legs
        - Only segments where both end-nodes have active legs are created
        """
        from ...utils import usd_utils

        leg_outer = LEG_PROFILES[leg_profile][0]
        fh, fw, fwall, fcr = FRAME_PROFILES[frame_profile]
        f_inner_h = fh - 2 * fwall
        f_inner_w = fw - 2 * fwall
        f_inner_cr = max(0.01, fcr - fwall)

        positions = _base_node_positions(width, depth, height)
        active_set = set(active_leg_nodes)

        # Y position: leg top = y_base + bp_thickness + leg_length
        # Frame top collinear with leg top → frame bottom at leg_top - fh
        y_base = -height / 2.0
        y_leg_top = y_base + bp_thickness + leg_length
        y_frame_center = y_leg_top - fh / 2.0

        frame_parts = []
        segments = _build_frame_segments(active_leg_nodes)

        for n_from, n_to, axis in segments:

            x1, _, z1 = positions[n_from]
            x2, _, z2 = positions[n_to]

            if axis == "x":
                # Beam runs along X between leg faces
                lo_x = min(x1, x2) + leg_outer / 2.0
                hi_x = max(x1, x2) - leg_outer / 2.0
                span = hi_x - lo_x
                if span <= 0:
                    continue
                cz = z1  # both nodes share same Z

                # Use Box for the beam shape (solid HSS approximation)
                # span along X, fh along Y, fw along Z
                # Align MIN on X so beam starts at lo_x
                with BuildPart() as bp:
                    Box(span, fh, fw,
                        align=(Align.MIN, Align.CENTER, Align.CENTER))
                beam = bp.part.move(Location((lo_x, y_frame_center, cz)))

            else:  # axis == "z"
                # Beam runs along Z between leg faces
                lo_z = min(z1, z2) + leg_outer / 2.0
                hi_z = max(z1, z2) - leg_outer / 2.0
                span = hi_z - lo_z
                if span <= 0:
                    continue
                cx = x1  # both nodes share same X

                # span along Z, fh along Y, fw along X
                # Align MIN on Z so beam starts at lo_z
                with BuildPart() as bp:
                    Box(fw, fh, span,
                        align=(Align.CENTER, Align.CENTER, Align.MIN))
                beam = bp.part.move(Location((cx, y_frame_center, lo_z)))

            frame_parts.append(beam)

        if frame_parts:
            compound = Compound(children=frame_parts)
            usd_utils.create_mesh_from_shape(
                stage, f"{path}/UpperFrames", compound)
            PlatformGenerator._apply_material(
                stage, f"{path}/UpperFrames", "Galvanized")

    @staticmethod
    def _create_deck_plate(stage, path, width, depth, height,
                           bp_thickness, leg_length, frame_profile,
                           deck_thickness, deck_material):
        """
        Create deck plate on top of upper frames.
        +Y is ALWAYS UP. Plate covers full width (X) x depth (Z),
        thickness extruded in +Y from frame top.
        """
        from ...utils import usd_utils

        fh = FRAME_PROFILES[frame_profile][0]
        y_base = -height / 2.0
        y_leg_top = y_base + bp_thickness + leg_length
        # Frame top = leg top, deck bottom sits on frame top
        y_deck_bottom = y_leg_top

        # Box: width along X, deck_thickness along Y, depth along Z
        # Centered on X and Z, bottom at y_deck_bottom (+Y extrusion)
        with BuildPart() as bp:
            Box(width, deck_thickness, depth,
                align=(Align.CENTER, Align.MIN, Align.CENTER))
        deck = bp.part.move(Location((0, y_deck_bottom, 0)))

        usd_utils.create_mesh_from_shape(
            stage, f"{path}/DeckPlate", Compound(children=[deck]))
        PlatformGenerator._apply_material(
            stage, f"{path}/DeckPlate", deck_material)

    @staticmethod
    def _apply_material(stage, mesh_path, material_name):
        colors = {
            "Steel":      (0.45, 0.45, 0.48),
            "Aluminum":   (0.7, 0.72, 0.73),
            "Black":      (0.05, 0.05, 0.05),
            "Yellow":     (0.95, 0.80, 0.05),
            "Blue":       (0.10, 0.20, 0.65),
            "Galvanized": (0.68, 0.70, 0.72),
            "Wood":       (0.55, 0.35, 0.18),
            "Rubber":     (0.12, 0.12, 0.12),
        }
        metallic = {
            "Black": 0.3, "Yellow": 0.2, "Galvanized": 0.6,
            "Blue": 0.2, "Wood": 0.0, "Rubber": 0.0,
        }
        roughness = {
            "Black": 0.6, "Yellow": 0.5, "Galvanized": 0.45,
            "Blue": 0.5, "Wood": 0.8, "Rubber": 0.9,
        }
        color = colors.get(material_name, (0.45, 0.45, 0.48))

        looks_path = "/Looks"
        if not stage.GetPrimAtPath(looks_path):
            stage.DefinePrim(looks_path, "Scope")

        mat_path = f"{looks_path}/Platform_{material_name}"
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

        mat.CreateSurfaceOutput().ConnectToSource(pbr.ConnectableAPI(), "surface")

        mesh_prim = stage.GetPrimAtPath(mesh_path)
        if mesh_prim:
            UsdShade.MaterialBindingAPI(mesh_prim).Bind(mat)
