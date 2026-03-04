# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Registry Entries - Registers existing generators with the Equipment Registry.

This is the ONLY integration point. No existing generator code is modified.
"""

from .equipment_registry import (
    EquipmentRegistry, EquipmentEntry, GeneratorAdapter, ParamDef,
    PortDef, ParamType, DetailLevel
)


def register_all():
    """Register all existing generators. Called from extension on_startup."""
    registry = EquipmentRegistry.instance()

    # -- Trapeze Hanger -- Type A --
    from ..objects.mep.trapeze import Trapeze
    registry.register(EquipmentEntry(
        id="trapeze",
        name="Trapeze Hanger",
        category="MEP Systems",
        generator_type_key="Trapeze",
        adapter=GeneratorAdapter(Trapeze, GeneratorAdapter.STAGE_AWARE),
        params=[
            ParamDef("span", ParamType.FLOAT, 24.0,
                     label="Span", unit="in", min_val=6.0, max_val=120.0),
            ParamDef("cantilever", ParamType.FLOAT, 2.0,
                     label="Cantilever", unit="in", min_val=0.5, max_val=12.0),
            ParamDef("drop_length", ParamType.FLOAT, 36.0,
                     label="Drop Length", unit="in", min_val=6.0, max_val=240.0),
            ParamDef("rod_diameter", ParamType.FLOAT, 0.5,
                     label="Rod Diameter", unit="in", min_val=0.25, max_val=1.5),
            ParamDef("strut_gauge", ParamType.ENUM, "12 Ga",
                     label="Strut Gauge",
                     choices=["16 Ga", "14 Ga", "12 Ga", "10 Ga"]),
        ],
        detail_levels=[DetailLevel.PLACEHOLDER, DetailLevel.PARAMETRIC],
        tags=["hanger", "trapeze", "support", "MEP"],
        description="Strut channel trapeze hanger with threaded rods",
    ))

    # -- Wide Flange Beam -- Type B (geometry only) --
    from ..objects.structural.wide_flange import WideFlangeGenerator
    registry.register(EquipmentEntry(
        id="wide_flange",
        name="Wide Flange Beam",
        category="Structural",
        generator_type_key="wide_flange",
        adapter=GeneratorAdapter(
            WideFlangeGenerator,
            GeneratorAdapter.GEOMETRY_ONLY,
        ),
        params=[
            ParamDef("depth", ParamType.FLOAT, 12.22,
                     label="Depth (d)", unit="in", group="Section"),
            ParamDef("flange_width", ParamType.FLOAT, 6.49,
                     label="Flange Width (bf)", unit="in", group="Section"),
            ParamDef("flange_thickness", ParamType.FLOAT, 0.38,
                     label="Flange Thickness (tf)", unit="in", group="Section"),
            ParamDef("web_thickness", ParamType.FLOAT, 0.23,
                     label="Web Thickness (tw)", unit="in", group="Section"),
            ParamDef("fillet_radius", ParamType.FLOAT, 0.5,
                     label="Fillet Radius (k)", unit="in", group="Section"),
            ParamDef("length", ParamType.FLOAT, 120.0,
                     label="Length", unit="in", min_val=1.0, max_val=960.0),
        ],
        detail_levels=[DetailLevel.PLACEHOLDER, DetailLevel.PARAMETRIC, DetailLevel.DETAILED],
        tags=["steel", "beam", "W-shape", "structural", "AISC"],
        description="AISC wide flange I-beam",
    ))

    # -- Duct (Straight) -- Type A --
    from ..objects.mep.duct_warp import DuctWarpGenerator
    registry.register(EquipmentEntry(
        id="duct_straight",
        name="Straight Duct",
        category="MEP Systems/Ductwork",
        generator_type_key="duct_straight",
        adapter=GeneratorAdapter(
            DuctWarpGenerator,
            GeneratorAdapter.STAGE_AWARE,
            param_mapping={},
        ),
        params=[
            ParamDef("width", ParamType.FLOAT, 20.0,
                     label="Width", unit="in", min_val=4.0, max_val=120.0),
            ParamDef("height", ParamType.FLOAT, 10.0,
                     label="Height", unit="in", min_val=4.0, max_val=120.0),
            ParamDef("length", ParamType.FLOAT, 48.0,
                     label="Length", unit="in", min_val=1.0, max_val=600.0),
            ParamDef("shape", ParamType.ENUM, "rectangular",
                     label="Shape", choices=["rectangular", "round"]),
            ParamDef("add_flanges", ParamType.BOOL, True,
                     label="Add Flanges"),
            ParamDef("radius", ParamType.FLOAT, 0.0,
                     label="Bend Radius", unit="in"),
            ParamDef("angle_deg", ParamType.FLOAT, 0.0,
                     label="Bend Angle", unit="deg"),
        ],
        ports=[
            PortDef("Anchor_Start", port_type="HVAC", shape="Rectangular"),
            PortDef("Anchor_End", port_type="HVAC", shape="Rectangular"),
        ],
        detail_levels=[DetailLevel.PLACEHOLDER, DetailLevel.PARAMETRIC],
        tags=["duct", "HVAC", "MEP", "rectangular", "round", "sheet metal"],
        description="Rectangular or round duct section",
    ))

    # -- Industrial Stair -- Type A --
    from ..objects.components.stair import Stair
    registry.register(EquipmentEntry(
        id="stair",
        name="Industrial Stair",
        category="Components",
        generator_type_key="stair",
        adapter=GeneratorAdapter(Stair, GeneratorAdapter.STAGE_AWARE),
        params=[
            ParamDef("total_rise", ParamType.FLOAT, 120.0,
                     label="Total Rise", unit="in", min_val=12.0, max_val=480.0),
            ParamDef("width", ParamType.FLOAT, 36.0,
                     label="Width", unit="in", min_val=24.0, max_val=72.0),
            ParamDef("run", ParamType.FLOAT, 10.0,
                     label="Tread Run", unit="in", min_val=8.0, max_val=14.0),
            ParamDef("platform_depth", ParamType.FLOAT, 48.0,
                     label="Platform Depth", unit="in", min_val=24.0, max_val=96.0),
            ParamDef("material", ParamType.ENUM, "Steel",
                     label="Material",
                     choices=["Steel", "Aluminum"]),
        ],
        detail_levels=[DetailLevel.PLACEHOLDER, DetailLevel.PARAMETRIC],
        tags=["stair", "industrial", "egress", "platform"],
        description="Industrial stair with treads and risers",
    ))

    # -- C-Channel -- Type B (geometry only) --
    from ..objects.structural.channel import ChannelGenerator
    registry.register(EquipmentEntry(
        id="channel",
        name="C-Channel",
        category="Structural",
        generator_type_key="channel",
        adapter=GeneratorAdapter(
            ChannelGenerator,
            GeneratorAdapter.GEOMETRY_ONLY,
        ),
        params=[
            ParamDef("depth", ParamType.FLOAT, 6.0,
                     label="Depth (d)", unit="in", group="Section"),
            ParamDef("flange_width", ParamType.FLOAT, 2.0,
                     label="Flange Width (bf)", unit="in", group="Section"),
            ParamDef("flange_thickness", ParamType.FLOAT, 0.343,
                     label="Flange Thickness (tf)", unit="in", group="Section"),
            ParamDef("web_thickness", ParamType.FLOAT, 0.200,
                     label="Web Thickness (tw)", unit="in", group="Section"),
            ParamDef("length", ParamType.FLOAT, 120.0,
                     label="Length", unit="in", min_val=1.0, max_val=960.0),
            ParamDef("fillet_radius", ParamType.FLOAT, 0.25,
                     label="Fillet Radius", unit="in", group="Section"),
        ],
        detail_levels=[DetailLevel.PLACEHOLDER, DetailLevel.PARAMETRIC],
        tags=["steel", "channel", "C-shape", "structural", "AISC"],
        description="AISC C-channel steel shape",
    ))

    # -- HSS Tube (Rectangular) -- Type B (geometry only) --
    from ..objects.structural.hss_tube import HSSGenerator
    registry.register(EquipmentEntry(
        id="hss_tube",
        name="HSS Tube (Rectangular)",
        category="Structural",
        generator_type_key="hss_tube",
        adapter=GeneratorAdapter(
            HSSGenerator,
            GeneratorAdapter.GEOMETRY_ONLY,
            create_method="create_rectangular",
        ),
        params=[
            ParamDef("outer_width", ParamType.FLOAT, 4.0,
                     label="Outer Width", unit="in", min_val=1.0, max_val=24.0,
                     group="Section"),
            ParamDef("outer_height", ParamType.FLOAT, 4.0,
                     label="Outer Height", unit="in", min_val=1.0, max_val=24.0,
                     group="Section"),
            ParamDef("wall_thickness", ParamType.FLOAT, 0.25,
                     label="Wall Thickness", unit="in", min_val=0.065, max_val=1.0,
                     group="Section"),
            ParamDef("length", ParamType.FLOAT, 120.0,
                     label="Length", unit="in", min_val=1.0, max_val=960.0),
        ],
        detail_levels=[DetailLevel.PLACEHOLDER, DetailLevel.PARAMETRIC],
        tags=["steel", "HSS", "tube", "rectangular", "structural", "AISC"],
        description="AISC HSS rectangular/square tube",
    ))

    # -- Strongback -- Type A --
    from ..objects.structural.strongback import Strongback
    registry.register(EquipmentEntry(
        id="strongback",
        name="Strongback",
        category="Components",
        generator_type_key="strongback",
        adapter=GeneratorAdapter(Strongback, GeneratorAdapter.STAGE_AWARE),
        params=[
            ParamDef("length", ParamType.FLOAT, 24.0,
                     label="Length", unit="in", min_val=6.0, max_val=240.0),
            ParamDef("width", ParamType.FLOAT, 8.0,
                     label="Width", unit="in", min_val=2.0, max_val=24.0),
            ParamDef("height", ParamType.FLOAT, 4.0,
                     label="Height", unit="in", min_val=1.0, max_val=12.0),
            ParamDef("thickness", ParamType.FLOAT, 0.125,
                     label="Thickness", unit="in"),
            ParamDef("variant", ParamType.ENUM, "C-Channel",
                     label="Variant",
                     choices=["C-Channel", "Strongback", "Stiffener Post"]),
            ParamDef("gauge", ParamType.ENUM, "14 Ga",
                     label="Gauge",
                     choices=["16 Ga", "14 Ga", "12 Ga", "10 Ga"]),
        ],
        detail_levels=[DetailLevel.PLACEHOLDER, DetailLevel.PARAMETRIC],
        tags=["strongback", "stiffener", "sheet metal", "support"],
        description="Sheet metal strongback with multiple cross-section variants",
    ))

    # -- Screen Guard -- Type A --
    from ..objects.components.screen_guard import ScreenGuard
    registry.register(EquipmentEntry(
        id="screen_guard",
        name="Screen Guard",
        category="Components",
        generator_type_key="screen_guard",
        adapter=GeneratorAdapter(ScreenGuard, GeneratorAdapter.STAGE_AWARE),
        params=[
            ParamDef("length", ParamType.FLOAT, 96.0,
                     label="Length", unit="in", min_val=24.0, max_val=240.0),
            ParamDef("height", ParamType.FLOAT, 96.0,
                     label="Height", unit="in", min_val=24.0, max_val=144.0),
            ParamDef("corner_type", ParamType.ENUM, "None",
                     label="Corner Type",
                     choices=["None", "Left", "Right"]),
            ParamDef("finish", ParamType.ENUM, "Safety Yellow",
                     label="Finish",
                     choices=["Safety Yellow", "Machine Gray", "Galvanized", "Black"]),
            ParamDef("include_end_post", ParamType.BOOL, True,
                     label="Include End Post"),
        ],
        detail_levels=[DetailLevel.PLACEHOLDER, DetailLevel.PARAMETRIC],
        tags=["guard", "screen", "safety", "protection", "industrial"],
        description="Industrial screen guard with posts and mesh panels",
    ))

    # -- Pyramid -- Type B (geometry only) --
    from ..objects.components.pyramid import PyramidGenerator
    registry.register(EquipmentEntry(
        id="pyramid",
        name="Pyramid / Tapered Extrusion",
        category="Components",
        generator_type_key="pyramid",
        adapter=GeneratorAdapter(
            PyramidGenerator,
            GeneratorAdapter.GEOMETRY_ONLY,
        ),
        params=[
            ParamDef("base", ParamType.FLOAT, 100.0,
                     label="Base Size", unit="in", min_val=1.0, max_val=600.0),
            ParamDef("height", ParamType.FLOAT, 100.0,
                     label="Height", unit="in", min_val=1.0, max_val=600.0),
            ParamDef("taper_angle", ParamType.FLOAT, -15.0,
                     label="Taper Angle", unit="deg", min_val=-45.0, max_val=45.0),
        ],
        detail_levels=[DetailLevel.PLACEHOLDER, DetailLevel.PARAMETRIC],
        tags=["pyramid", "taper", "extrusion", "shape"],
        description="Tapered extrusion / pyramid shape with feature support",
    ))

    print(f"[IEIP Registry] Registered {len(registry.all_entries())} generators")
