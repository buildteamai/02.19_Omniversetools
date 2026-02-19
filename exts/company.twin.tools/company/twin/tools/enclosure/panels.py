# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Panel Instantiation for Sheet Metal Enclosure.
Creates geometric primitives for different panel types.
"""

from pxr import UsdGeom, Gf, Sdf


def _tag_subpart(prim, p_type, w, h, d, gauge, mat="Galvanized Steel"):
    """Helper to tag a prim as a sheet metal sub-part for BOM."""
    custom = prim.GetCustomData() or {}
    custom['generatorType'] = 'sheet_metal_subpart'
    custom['designation'] = f"{w:.1f}\"x{h:.1f}\" ({gauge}ga)"
    custom['description'] = f"Part: {p_type}"
    custom['thickness'] = d 
    custom['width'] = w
    custom['height'] = h
    custom['gauge'] = gauge
    custom['material'] = mat
    prim.SetCustomData(custom)


def instantiate_panel(stage, path, width, height, thickness, p_type="Solid", variant_params=None, flange_depth=1.0, gauge=16):
    """
    Creates a sheet metal panel at the given path.
    
    Args:
        stage: USD Stage
        path: Prim path for the panel
        width: Panel width (X)
        height: Panel height (Y in local space, typically Z in world)
        thickness: Material thickness
        p_type: "Solid", "Window", "Louver", "Cutout"
        variant_params: Dict with variant-specific parameters
        flange_depth: Bend/flange depth
        gauge: Sheet metal gauge (int)
    """
    if variant_params is None:
        variant_params = {}

    # Create panel root Xform
    panel_root = UsdGeom.Xform.Define(stage, path)
    
    # Store metadata
    prim = panel_root.GetPrim()
    prim.CreateAttribute("custom:panel_type", Sdf.ValueTypeNames.String).Set(p_type)
    prim.CreateAttribute("custom:width", Sdf.ValueTypeNames.Double).Set(width)
    prim.CreateAttribute("custom:height", Sdf.ValueTypeNames.Double).Set(height)
    prim.CreateAttribute("custom:thickness", Sdf.ValueTypeNames.Double).Set(thickness)
    prim.CreateAttribute("custom:gauge", Sdf.ValueTypeNames.Int).Set(gauge)
    prim.CreateAttribute("custom:material", Sdf.ValueTypeNames.String).Set("Galvanized Steel")
    
    # Save parameters for deserialization
    if variant_params:
        for k, v in variant_params.items():
            attr_name = f"custom:{k}"
            prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Double).Set(float(v))

    # Metadata for BOM
    custom_data = prim.GetCustomData() or {}
    custom_data['generatorType'] = 'sheet_metal_panel'
    custom_data['designation'] = f"{width}\"x{height}\" ({gauge}ga)"
    custom_data['description'] = f"Sheet Metal Panel - {p_type}"
    custom_data['gauge'] = gauge
    custom_data['thickness'] = thickness
    custom_data['width'] = width
    custom_data['height'] = height
    custom_data['material'] = "Galvanized Steel"
    prim.SetCustomData(custom_data)

    W2 = width / 2.0
    H = height
    D = flange_depth
    T = thickness

    # --- Create Geometry Based on Type ---

    if p_type == "Solid":
        _create_solid_panel(stage, path, width, height, thickness, flange_depth)
    elif p_type == "Window":
        _create_window_panel(stage, path, width, height, thickness, flange_depth, variant_params, gauge)
    elif p_type == "Louver":
        _create_louver_panel(stage, path, width, height, thickness, flange_depth, variant_params, gauge)
    elif p_type == "Door":
        _create_door_panel(stage, path, width, height, thickness, flange_depth, variant_params, gauge)
    elif p_type == "AccessPanel":
        _create_access_panel(stage, path, width, height, thickness, flange_depth, variant_params, gauge)
    elif p_type == "Cutout":
        pass # Create nothing (empty Xform remains)
    else:
        # Default to solid
        _create_solid_panel(stage, path, width, height, thickness, flange_depth)


def _create_solid_panel(stage, path, width, height, thickness, flange_depth):
    """
    Creates a solid sheet metal panel with 4 flanges.
    Geometry: Main Face + Top/Bottom/Left/Right Flanges
    """
    W2 = width / 2.0
    H = height
    D = flange_depth
    T = thickness

    # 1. Main Face (Flat sheet)
    face = UsdGeom.Cube.Define(stage, f"{path}/Face")
    face.AddTranslateOp().Set(Gf.Vec3d(0, H/2.0, T/2.0))
    face.AddScaleOp().Set(Gf.Vec3d(width/2.0, height/2.0, thickness/2.0))
    face.CreateDisplayColorAttr([(0.65, 0.68, 0.72)])
    _apply_galvanized_material(stage, face)

    # 2. Top Flange
    top = UsdGeom.Cube.Define(stage, f"{path}/Flange_Top")
    top.AddTranslateOp().Set(Gf.Vec3d(0, H - T/2.0, D/2.0 + T))
    top.AddScaleOp().Set(Gf.Vec3d(width/2.0, thickness/2.0, D/2.0))
    top.CreateDisplayColorAttr([(0.55, 0.58, 0.62)])
    _apply_galvanized_material(stage, top)

    # 3. Bottom Flange
    bot = UsdGeom.Cube.Define(stage, f"{path}/Flange_Bottom")
    bot.AddTranslateOp().Set(Gf.Vec3d(0, T/2.0, D/2.0 + T))
    bot.AddScaleOp().Set(Gf.Vec3d(width/2.0, thickness/2.0, D/2.0))
    bot.CreateDisplayColorAttr([(0.55, 0.58, 0.62)])
    _apply_galvanized_material(stage, bot)

    # 4. Left Flange
    left = UsdGeom.Cube.Define(stage, f"{path}/Flange_Left")
    left.AddTranslateOp().Set(Gf.Vec3d(-W2 + T/2.0, H/2.0, D/2.0 + T))
    left.AddScaleOp().Set(Gf.Vec3d(thickness/2.0, height/2.0, D/2.0))
    left.CreateDisplayColorAttr([(0.55, 0.58, 0.62)])
    _apply_galvanized_material(stage, left)

    # 5. Right Flange
    right = UsdGeom.Cube.Define(stage, f"{path}/Flange_Right")
    right.AddTranslateOp().Set(Gf.Vec3d(W2 - T/2.0, H/2.0, D/2.0 + T))
    right.AddScaleOp().Set(Gf.Vec3d(thickness/2.0, height/2.0, D/2.0))
    right.CreateDisplayColorAttr([(0.55, 0.58, 0.62)])
    _apply_galvanized_material(stage, right)


def _create_window_panel(stage, path, width, height, thickness, flange_depth, params, gauge=16):
    """
    Creates a panel with a window cutout.
    Window is represented as a gap (no geometry) in the center.
    """
    W2 = width / 2.0
    H = height
    D = flange_depth
    T = thickness

    win_w = params.get("win_width", width * 0.6)
    win_h = params.get("win_height", height * 0.4)
    win_y = params.get("win_y", height * 0.3)  # Distance from bottom

    # Calculate header/footer heights
    footer_h = win_y
    header_h = H - win_y - win_h



    # 1. Footer Section (Below Window)
    if footer_h > 0.01:
        footer = UsdGeom.Cube.Define(stage, f"{path}/Footer")
        footer.AddTranslateOp().Set(Gf.Vec3d(0, footer_h/2.0, T/2.0))
        footer.AddScaleOp().Set(Gf.Vec3d(width/2.0, footer_h/2.0, thickness/2.0))
        footer.CreateDisplayColorAttr([(0.65, 0.68, 0.72)])
        _apply_galvanized_material(stage, footer)
        # Tag Footer
        _tag_subpart(footer.GetPrim(), "Footer", width, footer_h, thickness, 16) # Assuming 16ga if not passed, need valid gauge

    # 2. Header Section (Above Window)
    if header_h > 0.01:
        header = UsdGeom.Cube.Define(stage, f"{path}/Header")
        header.AddTranslateOp().Set(Gf.Vec3d(0, win_y + win_h + header_h/2.0, T/2.0))
        header.AddScaleOp().Set(Gf.Vec3d(width/2.0, header_h/2.0, thickness/2.0))
        header.CreateDisplayColorAttr([(0.65, 0.68, 0.72)])
        _apply_galvanized_material(stage, header)
        # Tag Header
        _tag_subpart(header.GetPrim(), "Header", width, header_h, thickness, 16)

    # 3. Left Jamb (Side of Window)
    jamb_w = (width - win_w) / 2.0
    if jamb_w > 0.01:
        left_jamb = UsdGeom.Cube.Define(stage, f"{path}/Jamb_Left")
        left_jamb.AddTranslateOp().Set(Gf.Vec3d(-W2 + jamb_w/2.0, win_y + win_h/2.0, T/2.0))
        left_jamb.AddScaleOp().Set(Gf.Vec3d(jamb_w/2.0, win_h/2.0, thickness/2.0))
        left_jamb.CreateDisplayColorAttr([(0.65, 0.68, 0.72)])
        _apply_galvanized_material(stage, left_jamb)
        _tag_subpart(left_jamb.GetPrim(), "Jamb", jamb_w, win_h, thickness, 16)

        right_jamb = UsdGeom.Cube.Define(stage, f"{path}/Jamb_Right")
        right_jamb.AddTranslateOp().Set(Gf.Vec3d(W2 - jamb_w/2.0, win_y + win_h/2.0, T/2.0))
        right_jamb.AddScaleOp().Set(Gf.Vec3d(jamb_w/2.0, win_h/2.0, thickness/2.0))
        right_jamb.CreateDisplayColorAttr([(0.65, 0.68, 0.72)])
        _apply_galvanized_material(stage, right_jamb)
        _tag_subpart(right_jamb.GetPrim(), "Jamb", jamb_w, win_h, thickness, 16)

    # 4. Window Glass (Optional - Semi-transparent)
    glass = UsdGeom.Cube.Define(stage, f"{path}/Window_Glass")
    glass.AddTranslateOp().Set(Gf.Vec3d(0, win_y + win_h/2.0, T/2.0))
    glass.AddScaleOp().Set(Gf.Vec3d(win_w/2.0, win_h/2.0, 0.125))  # Thin glass
    # glass.CreateDisplayColorAttr([(0.2, 0.4, 0.6)])  # Blue-ish glass
    _apply_glass_material(stage, glass)
    
    # Tag Glass
    g_prim = glass.GetPrim()
    g_custom = g_prim.GetCustomData() or {}
    g_custom['generatorType'] = 'glazing_panel'
    g_custom['designation'] = f"{win_w:.1f}\"x{win_h:.1f}\""
    g_custom['description'] = "Window Glazing (Plexiglass)"
    g_custom['width'] = win_w
    g_custom['height'] = win_h
    g_custom['material'] = "Plexiglass"
    g_prim.SetCustomData(g_custom)
    
    # Add flanges
    _add_flanges(stage, path, width, height, thickness, flange_depth)


def _create_louver_panel(stage, path, width, height, thickness, flange_depth, params, gauge=16):
    """
    Creates a panel with louver vents.
    """
    W2 = width / 2.0
    H = height
    T = thickness

    louver_count = params.get("louver_count", 5)
    louver_spacing = H / (louver_count + 1)
    louver_angle = params.get("louver_angle", 45.0)

    # Main Face Background
    face = UsdGeom.Cube.Define(stage, f"{path}/Face")
    face.AddTranslateOp().Set(Gf.Vec3d(0, H/2.0, T/2.0))
    face.AddScaleOp().Set(Gf.Vec3d(width/2.0, height/2.0, thickness/2.0))
    face.CreateDisplayColorAttr([(0.65, 0.68, 0.72)])
    _apply_galvanized_material(stage, face)

    # Louver Blades
    blade_h = louver_spacing * 0.6
    for i in range(louver_count):
        y_pos = louver_spacing * (i + 1)
        blade = UsdGeom.Cube.Define(stage, f"{path}/Louver_{i}")
        blade.AddTranslateOp().Set(Gf.Vec3d(0, y_pos, T + blade_h/2.0))
        blade.AddRotateXOp().Set(louver_angle)
        blade.AddScaleOp().Set(Gf.Vec3d((width - 2)/2.0, blade_h/2.0, thickness/2.0))
        blade.CreateDisplayColorAttr([(0.5, 0.52, 0.55)])
        _apply_galvanized_material(stage, blade)
        # Tag Blade
        _tag_subpart(blade.GetPrim(), "Louver Blade", width-2, blade_h, thickness, gauge)

    _add_flanges(stage, path, width, height, thickness, flange_depth)


def _create_door_panel(stage, path, width, height, thickness, flange_depth, params, gauge=16):
    """
    Creates a panel with a door (Man Door or Double Door).
    Includes a viewing window and handle.
    """
    door_w = params.get("door_width", 36.0)
    door_h = params.get("door_height", 84.0)
    
    # Simple cutout represention + Frame
    W2 = width / 2.0
    H = height
    T = thickness
    
    # 1. Header (Above Door)
    header_h = H - door_h
    if header_h > 0.01:
        header = UsdGeom.Cube.Define(stage, f"{path}/Header")
        header.AddTranslateOp().Set(Gf.Vec3d(0, door_h + header_h/2.0, T/2.0))
        header.AddScaleOp().Set(Gf.Vec3d(width/2.0, header_h/2.0, thickness/2.0))
        header.CreateDisplayColorAttr([(0.65, 0.68, 0.72)])
        _apply_galvanized_material(stage, header)
        _tag_subpart(header.GetPrim(), "Door Header", width, header_h, thickness, gauge)
        
    # 2. Side Jambs
    jamb_w = (width - door_w) / 2.0
    if jamb_w > 0.01:
        left_jamb = UsdGeom.Cube.Define(stage, f"{path}/Jamb_Left")
        left_jamb.AddTranslateOp().Set(Gf.Vec3d(-W2 + jamb_w/2.0, door_h/2.0, T/2.0))
        left_jamb.AddScaleOp().Set(Gf.Vec3d(jamb_w/2.0, door_h/2.0, thickness/2.0))
        left_jamb.CreateDisplayColorAttr([(0.65, 0.68, 0.72)])
        _apply_galvanized_material(stage, left_jamb)
        _tag_subpart(left_jamb.GetPrim(), "Door Jamb", jamb_w, door_h, thickness, gauge)

        right_jamb = UsdGeom.Cube.Define(stage, f"{path}/Jamb_Right")
        right_jamb.AddTranslateOp().Set(Gf.Vec3d(W2 - jamb_w/2.0, door_h/2.0, T/2.0))
        right_jamb.AddScaleOp().Set(Gf.Vec3d(jamb_w/2.0, door_h/2.0, thickness/2.0))
        right_jamb.CreateDisplayColorAttr([(0.65, 0.68, 0.72)])
        _apply_galvanized_material(stage, right_jamb)
        _tag_subpart(right_jamb.GetPrim(), "Door Jamb", jamb_w, door_h, thickness, gauge)
        
    # --- 3. Composite Door Slab with Window ---
    # Window dimensions
    win_w = 10.0
    win_h = 10.0
    
    # Logic for window placement
    if door_h < 48.0:
        # Small door: Center window
        win_y_center = door_h / 2.0
    else:
        # Standard door: Eye level (60")
        win_y_center = 60.0

    # Ensure window fits in door
    if win_y_center + win_h/2.0 > door_h:
        win_y_center = door_h - win_h/2.0 - 2.0 # 2" margin
    if win_y_center - win_h/2.0 < 0:
        win_y_center = win_h/2.0 + 2.0
        
    # If door is too small for window, skip window?
    has_window = True
    if door_h < win_h + 4.0 or door_w < win_w + 4.0:
        has_window = False

    door_thick = 1.75
    
    if has_window:
        win_y_bottom = win_y_center - (win_h / 2.0)
        
        # Bottom Section
        bot_h = win_y_bottom
        if bot_h > 0:
            slab_bot = UsdGeom.Cube.Define(stage, f"{path}/DoorSlab_Bottom")
            slab_bot.AddTranslateOp().Set(Gf.Vec3d(0, bot_h/2.0, T))
            slab_bot.AddScaleOp().Set(Gf.Vec3d(door_w/2.0, bot_h/2.0, door_thick/2.0))
            slab_bot.CreateDisplayColorAttr([(0.6, 0.6, 0.65)]) # Industrial Grey
            _tag_subpart(slab_bot.GetPrim(), "Door Slab Bottom", door_w, bot_h, door_thick, gauge)

        # Top Section
        top_y = win_y_bottom + win_h
        top_h = door_h - top_y
        if top_h > 0:
            slab_top = UsdGeom.Cube.Define(stage, f"{path}/DoorSlab_Top")
            slab_top.AddTranslateOp().Set(Gf.Vec3d(0, top_y + top_h/2.0, T))
            slab_top.AddScaleOp().Set(Gf.Vec3d(door_w/2.0, top_h/2.0, door_thick/2.0))
            slab_top.CreateDisplayColorAttr([(0.6, 0.6, 0.65)])
            _tag_subpart(slab_top.GetPrim(), "Door Slab Top", door_w, top_h, door_thick, gauge)
            
        # Side Stiles
        stile_w = (door_w - win_w) / 2.0
        if stile_w > 0:
            # Left Stile
            stile_l = UsdGeom.Cube.Define(stage, f"{path}/DoorSlab_StileLeft")
            stile_l.AddTranslateOp().Set(Gf.Vec3d(-(door_w/2.0) + (stile_w/2.0), win_y_center, T))
            stile_l.AddScaleOp().Set(Gf.Vec3d(stile_w/2.0, win_h/2.0, door_thick/2.0))
            stile_l.CreateDisplayColorAttr([(0.6, 0.6, 0.65)])
            
            # Right Stile
            stile_r = UsdGeom.Cube.Define(stage, f"{path}/DoorSlab_StileRight")
            stile_r.AddTranslateOp().Set(Gf.Vec3d((door_w/2.0) - (stile_w/2.0), win_y_center, T))
            stile_r.AddScaleOp().Set(Gf.Vec3d(stile_w/2.0, win_h/2.0, door_thick/2.0))
            stile_r.CreateDisplayColorAttr([(0.6, 0.6, 0.65)])

        # Window Glass
        glass = UsdGeom.Cube.Define(stage, f"{path}/DoorWindow")
        glass.AddTranslateOp().Set(Gf.Vec3d(0, win_y_center, T))
        glass.AddScaleOp().Set(Gf.Vec3d(win_w/2.0, win_h/2.0, 0.125)) 
        # glass.CreateDisplayColorAttr([(0.2, 0.3, 0.4)])
        # glass.CreateDisplayOpacityAttr([0.3])
        _apply_glass_material(stage, glass)
    
    else:
        # Full solid slab
        slab = UsdGeom.Cube.Define(stage, f"{path}/DoorSlab")
        slab.AddTranslateOp().Set(Gf.Vec3d(0, door_h/2.0, T))
        slab.AddScaleOp().Set(Gf.Vec3d(door_w/2.0, door_h/2.0, door_thick/2.0))
        slab.CreateDisplayColorAttr([(0.6, 0.6, 0.65)])
        _tag_subpart(slab.GetPrim(), "Door Slab", door_w, door_h, door_thick, gauge)

    # Handle (Lever style)
    handle_h = min(36.0, door_h * 0.5) # Handle height adjusted for small doors
    handle_offset = (door_w / 2.0) - 3.0 # 3 inches from edge
    handle_root = UsdGeom.Xform.Define(stage, f"{path}/DoorHandle")
    handle_root.AddTranslateOp().Set(Gf.Vec3d(handle_offset, handle_h, T + door_thick/2.0))
    
    # Handle Base
    base = UsdGeom.Cylinder.Define(stage, f"{path}/DoorHandle/Base")
    base.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0.25))
    base.CreateHeightAttr(0.5)
    base.CreateRadiusAttr(1.5)
    base.CreateAxisAttr("Z")
    base.CreateDisplayColorAttr([(0.8, 0.8, 0.8)]) # Chrome/Silver
    
    # Handle Lever
    lever = UsdGeom.Cube.Define(stage, f"{path}/DoorHandle/Lever")
    lever.AddTranslateOp().Set(Gf.Vec3d(-2.0, 0, 0.75)) # Pointing inwards
    lever.AddScaleOp().Set(Gf.Vec3d(2.5, 0.5, 0.25))
    lever.CreateDisplayColorAttr([(0.8, 0.8, 0.8)])

    _add_flanges(stage, path, width, height, thickness, flange_depth)


def _create_access_panel(stage, path, width, height, thickness, flange_depth, params, gauge=16):
    """
    Creates a panel with a removable access hatch.
    """
    ap_w = params.get("ap_width", 18.0)
    ap_h = params.get("ap_height", 18.0)
    ap_y = params.get("ap_y", 36.0)
    
    # Base is effectively a Window panel but filled
    _create_window_panel(stage, path, width, height, thickness, flange_depth, {
        "win_width": ap_w,
        "win_height": ap_h,
        "win_y": ap_y
    }, gauge)
    
    # Add Hatch Cover
    hatch = UsdGeom.Cube.Define(stage, f"{path}/HatchCover")
    hatch.AddTranslateOp().Set(Gf.Vec3d(0, ap_y + ap_h/2.0, thickness + 0.1))
    hatch.AddScaleOp().Set(Gf.Vec3d(ap_w/2.0 + 1.0, ap_h/2.0 + 1.0, 0.1)) # Overlap
    hatch.CreateDisplayColorAttr([(0.9, 0.9, 0.9)])
    _tag_subpart(hatch.GetPrim(), "Access Hatch Cover", ap_w + 2.0, ap_h + 2.0, 0.1, gauge)



def _add_flanges(stage, path, width, height, thickness, flange_depth):
    """
    Helper to add 4 standard flanges to a panel.
    """
    W2 = width / 2.0
    H = height
    D = flange_depth
    T = thickness

    top = UsdGeom.Cube.Define(stage, f"{path}/Flange_Top")
    top.AddTranslateOp().Set(Gf.Vec3d(0, H - T/2.0, D/2.0 + T))
    top.AddScaleOp().Set(Gf.Vec3d(width/2.0, thickness/2.0, D/2.0))
    top.CreateDisplayColorAttr([(0.55, 0.58, 0.62)])
    _apply_galvanized_material(stage, top)

    bot = UsdGeom.Cube.Define(stage, f"{path}/Flange_Bottom")
    bot.AddTranslateOp().Set(Gf.Vec3d(0, T/2.0, D/2.0 + T))
    bot.AddScaleOp().Set(Gf.Vec3d(width/2.0, thickness/2.0, D/2.0))
    bot.CreateDisplayColorAttr([(0.55, 0.58, 0.62)])
    _apply_galvanized_material(stage, bot)

    left = UsdGeom.Cube.Define(stage, f"{path}/Flange_Left")
    left.AddTranslateOp().Set(Gf.Vec3d(-W2 + T/2.0, H/2.0, D/2.0 + T))
    left.AddScaleOp().Set(Gf.Vec3d(thickness/2.0, height/2.0, D/2.0))
    left.CreateDisplayColorAttr([(0.55, 0.58, 0.62)])
    _apply_galvanized_material(stage, left)

    right = UsdGeom.Cube.Define(stage, f"{path}/Flange_Right")
    right.AddTranslateOp().Set(Gf.Vec3d(W2 - T/2.0, H/2.0, D/2.0 + T))
    right.AddScaleOp().Set(Gf.Vec3d(thickness/2.0, height/2.0, D/2.0))
    right.CreateDisplayColorAttr([(0.55, 0.58, 0.62)])
    _apply_galvanized_material(stage, right)


def _apply_galvanized_material(stage, prim_schema):
    """
    Applies a standard 'Galvanized Metal' material to the prim.
    Creates the material if it doesn't exist.
    """
    from pxr import UsdShade
    
    mat_path = "/Looks/GalvanizedMetal"
    mat = UsdShade.Material.Get(stage, mat_path)
    
    if not mat:
        # Create Looks scope if needed
        if not stage.GetPrimAtPath("/Looks"):
            stage.DefinePrim("/Looks", "Scope")
            
        mat = UsdShade.Material.Define(stage, mat_path)
        pbr_shader = UsdShade.Shader.Define(stage, f"{mat_path}/PBRShader")
        pbr_shader.CreateIdAttr("UsdPreviewSurface")
        
        # Galvanized properties (Reflective)
        pbr_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set((0.6, 0.62, 0.65))
        pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.8)
        pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.2)
        pbr_shader.CreateInput("ior", Sdf.ValueTypeNames.Float).Set(1.5)
        
        mat.CreateSurfaceOutput().ConnectToSource(pbr_shader.ConnectableAPI(), "surface")

    # Bind material
    UsdShade.MaterialBindingAPI(prim_schema.GetPrim()).Bind(mat)


def _apply_glass_material(stage, prim_schema):
    """
    Applies a standard 'Glass' material to the prim.
    Creates the material if it doesn't exist.
    """
    from pxr import UsdShade
    
    mat_path = "/Looks/Glass"
    mat = UsdShade.Material.Get(stage, mat_path)
    
    if not mat:
        # Create Looks scope if needed
        if not stage.GetPrimAtPath("/Looks"):
            stage.DefinePrim("/Looks", "Scope")
            
        mat = UsdShade.Material.Define(stage, mat_path)
        pbr_shader = UsdShade.Shader.Define(stage, f"{mat_path}/PBRShader")
        pbr_shader.CreateIdAttr("UsdPreviewSurface")
        
        # Glass properties (Transparent)
        # Use dark base color so it looks like tinted glass rather than milky white
        pbr_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set((0.05, 0.05, 0.05))
        pbr_shader.CreateInput("useSpecularWorkflow", Sdf.ValueTypeNames.Int).Set(0)
        pbr_shader.CreateInput("specularColor", Sdf.ValueTypeNames.Color3f).Set((1.0, 1.0, 1.0)) # Reflective
        pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0) # Dielectric
        pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.0) # Perfectly smooth
        pbr_shader.CreateInput("clearcoat", Sdf.ValueTypeNames.Float).Set(1.0)
        pbr_shader.CreateInput("clearcoatRoughness", Sdf.ValueTypeNames.Float).Set(0.0)
        pbr_shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(0.2) # Transparent
        pbr_shader.CreateInput("ior", Sdf.ValueTypeNames.Float).Set(1.52) # Glass IOR
        
        mat.CreateSurfaceOutput().ConnectToSource(pbr_shader.ConnectableAPI(), "surface")

    # Bind material
    UsdShade.MaterialBindingAPI(prim_schema.GetPrim()).Bind(mat)
