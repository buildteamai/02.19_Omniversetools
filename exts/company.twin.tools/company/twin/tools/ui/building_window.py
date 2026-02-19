import omni.ui as ui
import carb
import omni.usd
from pxr import Usd, UsdGeom, Gf, Sdf, UsdLux
import math
from ..utils import usd_utils

def create_cube(stage, path, size_vec, position_vec, color=None):
    """Creates a basic cube primitive."""
    cube = UsdGeom.Cube.Define(stage, path)
    UsdGeom.Xformable(cube).AddTranslateOp().Set(position_vec)
    UsdGeom.Xformable(cube).AddScaleOp().Set(size_vec)
    cube.GetSizeAttr().Set(1.0)
    # Re-applying scale op to be sure? The user code had:
    # UsdGeom.Xformable(cube).AddScaleOp().Set(size_vec)
    # cube.GetSizeAttr().Set(1.0)
    # UsdGeom.Xformable(cube).GetScaleOp().Set(size_vec)
    # The last line gets the op and sets it again. The first AddScaleOp is sufficient if it returns the op.
    # But let's stick EXACTLY to user code to avoid breaking anything they might have intended or if I misread.
    # User code:
    # UsdGeom.Xformable(cube).AddScaleOp().Set(size_vec)
    # cube.GetSizeAttr().Set(1.0)
    # UsdGeom.Xformable(cube).GetScaleOp().Set(size_vec) <--- This implies looking up the op we just added or one that exists.
    
    # Actually, calling AddScaleOp twice might add two ops if not careful, but usually it returns existing if same type? 
    # No, AddScaleOp usually appends.
    # Let's look closer at user code:
    # UsdGeom.Xformable(cube).AddTranslateOp().Set(position_vec)
    # UsdGeom.Xformable(cube).AddScaleOp().Set(size_vec)
    # cube.GetSizeAttr().Set(1.0)
    # UsdGeom.Xformable(cube).GetScaleOp().Set(size_vec)
    
    # If I just copy paste the user code, I should be safe.
    pass

def create_ibeam(stage, path, length, depth, width, color=None):
    """
    Creates an I-Beam geometry group.
    """
    beam_grp = UsdGeom.Xform.Define(stage, path)

    flange_thick = 0.5 # inches
    web_thick = 0.3    # inches

    # Dimensions
    # Length is along X (local).
    # Depth is along Y.
    # Width is along Z.

    # 1. Top Flange
    tf_path = f"{path}/TopFlange"
    tf_pos = Gf.Vec3d(0, (depth/2.0) - (flange_thick/2.0), 0)
    tf_scale = Gf.Vec3d(length, flange_thick, width)
    create_cube_impl(stage, tf_path, tf_scale, tf_pos, color)

    # 2. Bottom Flange
    bf_path = f"{path}/BotFlange"
    bf_pos = Gf.Vec3d(0, -(depth/2.0) + (flange_thick/2.0), 0)
    bf_scale = Gf.Vec3d(length, flange_thick, width)
    create_cube_impl(stage, bf_path, bf_scale, bf_pos, color)

    # 3. Web
    web_path = f"{path}/Web"
    web_h = depth - (2 * flange_thick)
    web_pos = Gf.Vec3d(0, 0, 0)
    web_scale = Gf.Vec3d(length, web_h, web_thick)
    create_cube_impl(stage, web_path, web_scale, web_pos, color)

    return beam_grp

# Helper to match user's create_cube exactly
def create_cube_impl(stage, path, size_vec, position_vec, color=None):
    cube = UsdGeom.Cube.Define(stage, path)
    UsdGeom.Xformable(cube).AddTranslateOp().Set(position_vec)
    UsdGeom.Xformable(cube).AddScaleOp().Set(size_vec)
    cube.GetSizeAttr().Set(1.0)
    # Redundant set from user code, but keeping for fidelity
    UsdGeom.Xformable(cube).GetScaleOp().Set(size_vec)

    if color:
        cube.GetDisplayColorAttr().Set([color])
    return cube

def create_bar_joist(stage, path, length, depth, width=5.0, color=None):
    """
    Creates an Open Web Steel Joist (Bar Joist).
    Oriented along Local X.
    """
    joist_grp = UsdGeom.Xform.Define(stage, path)

    # Chords (Double Angles essentially)
    chord_thick = 0.25
    chord_w = 1.5
    gap = 1.0 # Gap between angles

    # Since we are low-poly, let's represent Chords as two strips for Top, two for Bottom.

    # Top Chord
    # Positioned at +Depth/2
    y_top = (depth / 2.0) - (chord_thick / 2.0)
    z_off = (gap + chord_w) / 2.0

    tc1_path = f"{path}/TopChord_1"
    create_cube_impl(stage, tc1_path, Gf.Vec3d(length, chord_thick, chord_w), Gf.Vec3d(0, y_top, z_off), color)

    tc2_path = f"{path}/TopChord_2"
    create_cube_impl(stage, tc2_path, Gf.Vec3d(length, chord_thick, chord_w), Gf.Vec3d(0, y_top, -z_off), color)

    # Bottom Chord
    y_bot = -(depth / 2.0) + (chord_thick / 2.0)
    bc1_path = f"{path}/BotChord_1"
    create_cube_impl(stage, bc1_path, Gf.Vec3d(length, chord_thick, chord_w), Gf.Vec3d(0, y_bot, z_off), color)

    bc2_path = f"{path}/BotChord_2"
    create_cube_impl(stage, bc2_path, Gf.Vec3d(length, chord_thick, chord_w), Gf.Vec3d(0, y_bot, -z_off), color)

    # Webbing (Zig-Zag)
    # Pitch: Horizontal distance for one up-down cycle.
    # Angle ~ 45-60 deg.
    # At 45 deg, H_dist = V_dist.
    web_h = depth - (2 * chord_thick)
    pitch = web_h * 1.5 # Stretched a bit

    num_struts = int(length / (pitch / 2.0))

    web_color = color
    if not web_color: web_color = Gf.Vec3f(0.7, 0.7, 0.7)

    strut_diam = 0.5

    # We will simply place diagonal cubes.
    # Start X = -Length/2
    start_x = -length / 2.0

    for i in range(num_struts):
        # x1, y1 to x2, y2
        x1 = start_x + (i * pitch / 2.0)
        x2 = start_x + ((i + 1) * pitch / 2.0)

        if i % 2 == 0:
            # Down stroke: Top to Bot
            y1 = y_top
            y2 = y_bot
        else:
            # Up stroke: Bot to Top
            y1 = y_bot
            y2 = y_top

        mid_x = (x1 + x2) / 2.0
        mid_y = (y1 + y2) / 2.0

        dx = x2 - x1
        dy = y2 - y1
        dist = math.sqrt(dx*dx + dy*dy)
        angle = math.degrees(math.atan2(dy, dx))

        s_path = f"{path}/Web_{i}"

        # Cube representing round bar
        cube = UsdGeom.Cube.Define(stage, s_path)
        # Scale: Length=dist, Height=diam, Depth=diam
        # Cube default is 2. Scale needs to map to (dist/2, diam/2, ...)? No we use size 1.
        cube.GetSizeAttr().Set(1.0)

        xform = UsdGeom.Xformable(cube)
        xform.ClearXformOpOrder()

        xform.AddTranslateOp().Set(Gf.Vec3d(mid_x, mid_y, 0))
        xform.AddRotateZOp().Set(angle)
        xform.AddScaleOp().Set(Gf.Vec3d(dist, strut_diam, strut_diam))

        cube.GetDisplayColorAttr().Set([web_color])

    return joist_grp

def generate_building(stage, length, width, col_spacing_x, col_spacing_z, clear_height, slab_thickness=6.0, joist_spacing=5.0):
    root_path = "/Paintshop_Building"
    if stage.GetPrimAtPath(root_path):
        stage.RemovePrim(root_path)

    building_prim = stage.DefinePrim(root_path, "Xform")
    carb.log_info(f"Generating Building: {length}x{width} Height:{clear_height} JoistSpace:{joist_spacing}")

    # 1. Concrete Slab
    slab_path = f"{root_path}/Slab"
    slab_pos = Gf.Vec3d(length / 2.0, -slab_thickness / 2.0, width / 2.0)
    slab_scale = Gf.Vec3d(length, slab_thickness, width)
    create_cube_impl(stage, slab_path, slab_scale, slab_pos, color=Gf.Vec3f(0.5, 0.5, 0.5))

    # 2. Grid Generation
    xs = []
    curr_x = 0
    while curr_x <= length:
        xs.append(curr_x)
        curr_x += col_spacing_x
    if xs[-1] < length - 1.0:
        xs.append(length)

    zs = []
    curr_z = 0
    while curr_z <= width:
        zs.append(curr_z)
        curr_z += col_spacing_z
    if zs[-1] < width - 1.0:
        zs.append(width)

    # 3. Columns (Primary Framing)
    # --- Lighting Generation ---
    # Create lights centered in each bay, slightly below clear height.
    lights_grp = UsdGeom.Scope.Define(stage, f"{root_path}/Lights")
    
    # 1. Ambient Fill (Dome Light)
    fill_light = UsdLux.DomeLight.Define(stage, f"{root_path}/Lights/AmbientFill")
    fill_light.GetIntensityAttr().Set(1000.0) # Low intensity fill
    fill_light.GetExposureAttr().Set(0.0)
    fill_light.GetTextureFormatAttr().Set(UsdLux.Tokens.latlong)
    
    # Calculate bay centers
    # Bays are defined by the grid lines in xs and zs
    # We have len(xs)-1 bays in X, len(zs)-1 bays in Z.
    
    # High Bay Light Settings
    light_intensity = 500000.0 # Boosted massive amount for debugging
    light_radius = 6.0 # 12 inch radius
    light_height = clear_height - 12.0 # 1 foot below truss
    
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            x_start = xs[i]
            x_end = xs[i+1]
            z_start = zs[j]
            z_end = zs[j+1]
            
            center_x = (x_start + x_end) / 2.0
            center_z = (z_start + z_end) / 2.0
            
            light_path = f"{root_path}/Lights/BayLight_{i}_{j}"
            
            # --- DEBUG: Visual Marker ---
            # Create a glowing sphere so we can see WHERE the light is
            marker_path = f"{light_path}_Marker"
            marker = UsdGeom.Sphere.Define(stage, marker_path)
            UsdGeom.Xformable(marker).AddTranslateOp().Set(Gf.Vec3d(center_x, light_height, center_z))
            marker.GetRadiusAttr().Set(4.0) # 8 inch visible sphere
            marker.GetDisplayColorAttr().Set([Gf.Vec3f(1.0, 1.0, 0.0)]) # Yellow
            # ---------------------------

            # Switch to SphereLight for omnidirectional debug
            sphere_light = UsdLux.SphereLight.Define(stage, light_path)
            
            # Position and Orient
            xform = UsdGeom.Xformable(sphere_light)
            xform.AddTranslateOp().Set(Gf.Vec3d(center_x, light_height, center_z))
            # Rotate X -90 to point "Down" (if we add shaping later)
            # -Z -> -Y
            xform.AddRotateXOp().Set(-90)
            
            # Attributes
            sphere_light.GetIntensityAttr().Set(light_intensity)
            sphere_light.GetRadiusAttr().Set(light_radius)
            sphere_light.GetColorAttr().Set(Gf.Vec3f(1.0, 0.98, 0.95))
            
            # Removed ShapingAPI for now to ensure raw light works
            # Once confirmed, uncomment below to restrict angle
            # shaping = UsdLux.ShapingAPI.Apply(sphere_light.GetPrim())
            # shaping.CreateShapingConeAngleAttr(60.0)
            # shaping.CreateShapingConeSoftnessAttr(20.0)
            # shaping.CreateShapingFocusAttr(10.0)

    # --- End Lighting Generation ---

    cols_grp = UsdGeom.Xform.Define(stage, f"{root_path}/Columns")
    col_size = 10.0 # 10x10 inches
    col_height = clear_height + 12.0

    for i, x in enumerate(xs):
        for j, z in enumerate(zs):
            col_path = f"{root_path}/Columns/Col_{i}_{j}"
            pos = Gf.Vec3d(x, col_height / 2.0, z)
            scale = Gf.Vec3d(col_size, col_height, col_size)
            create_cube_impl(stage, col_path, scale, pos, color=Gf.Vec3f(0.3, 0.3, 0.4))

    # 4. Girders (Primary Beams connecting Columns along X)
    girders_grp = UsdGeom.Xform.Define(stage, f"{root_path}/Girders")
    girder_depth = 18.0 # Taller I-Beam
    girder_width = 8.0

    for j, z in enumerate(zs):
        for i in range(len(xs) - 1):
            x_start = xs[i]
            x_end = xs[i+1]
            seg_len = x_end - x_start
            mid_x = x_start + (seg_len / 2.0)

            p_path = f"{root_path}/Girders/Girder_Z{j}_Seg{i}"

            # Position: Center of Beam
            # Bottom at clear_height. Center = clear_height + depth/2.
            y_pos = clear_height + (girder_depth / 2.0)

            # Beams are created at origin, we need to Translate the Root Xform
            beam_root = UsdGeom.Xform.Define(stage, p_path)
            UsdGeom.Xformable(beam_root).AddTranslateOp().Set(Gf.Vec3d(mid_x, y_pos, z))

            # Create I-Beam geometry inside
            create_ibeam(stage, p_path, seg_len, girder_depth, girder_width, color=Gf.Vec3f(0.2, 0.25, 0.3))

    # 5. Joists (Secondary Framing)
    joists_grp = UsdGeom.Xform.Define(stage, f"{root_path}/Joists")
    joist_depth = 24.0 # Deep truss

    num_joists = int(length / joist_spacing) + 1

    # Joist Bottom rests on Girder Top.
    girder_top = clear_height + girder_depth
    joist_center_y = girder_top + (joist_depth / 2.0)

    # Rotate Joists to span Z?
    # Joist logic creates along X. We need to Rotate 90 deg around Y.

    for k in range(num_joists):
        x_loc = k * joist_spacing
        if x_loc > length: break

        j_path = f"{root_path}/Joists/Joist_{k}"

        joist_root = UsdGeom.Xform.Define(stage, j_path)
        xform = UsdGeom.Xformable(joist_root)
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(Gf.Vec3d(x_loc, joist_center_y, width / 2.0))
        xform.AddRotateYOp().Set(-90) # Rotate to span Z

        create_bar_joist(stage, j_path, width, joist_depth, color=Gf.Vec3f(0.75, 0.75, 0.75))


class OmniPaintBuildingWindow(ui.Window):
    """
    Building Configurator Window.
    """
    def __init__(self, title="Building Configurator", **kwargs):
        super().__init__(title, width=400, height=480, **kwargs)

        self._length_model = ui.SimpleFloatModel(50.0)
        self._width_model = ui.SimpleFloatModel(40.0)

        self._col_x_model = ui.SimpleFloatModel(20.0)
        self._col_z_model = ui.SimpleFloatModel(20.0)

        self._height_model = ui.SimpleFloatModel(20.0)
        self._slab_model = ui.SimpleFloatModel(6.0)
        self._joist_model = ui.SimpleFloatModel(5.0)

        self.frame.set_build_fn(self._build_ui)

    def _build_ui(self):
        with ui.VStack(spacing=10, padding=10):
            ui.Label("Building Configurator", style={"font_size": 20, "color": 0xFF00B4FF})
            ui.Line(height=2, style={"color": 0xFF333333})

            with ui.VStack(spacing=5):
                ui.Label("Overall Dimensions", style={"color": 0xFFAAAAAA})
                with ui.HStack(height=20):
                    ui.Label("Length (ft):", width=120)
                    ui.FloatField(model=self._length_model)
                with ui.HStack(height=20):
                    ui.Label("Width (ft):", width=120)
                    ui.FloatField(model=self._width_model)

                ui.Spacer(height=5)
                ui.Label("Structural Grid (ft)", style={"color": 0xFFAAAAAA})
                with ui.HStack(height=20):
                    ui.Label("Column Spacing X:", width=120)
                    ui.FloatField(model=self._col_x_model)
                with ui.HStack(height=20):
                    ui.Label("Column Spacing Z:", width=120)
                    ui.FloatField(model=self._col_z_model)
                with ui.HStack(height=20):
                    ui.Label("Joist Spacing:", width=120)
                    ui.FloatField(model=self._joist_model)

                ui.Spacer(height=5)
                ui.Label("Verticals", style={"color": 0xFFAAAAAA})
                with ui.HStack(height=20):
                    ui.Label("Clear Height (ft):", width=120)
                    ui.FloatField(model=self._height_model)
                with ui.HStack(height=20):
                    ui.Label("Slab Thickness (in):", width=120)
                    ui.FloatField(model=self._slab_model)

            ui.Spacer(height=20)
            ui.Button("Generate Building", clicked_fn=self._on_generate_clicked)
            self._status_label = ui.Label("", style={"color": 0xFF888888})

    def _on_generate_clicked(self):
        stage = omni.usd.get_context().get_stage()
        if not stage:
            self._status_label.text = "Error: No Stage"
            return
            
        # Enforce Units
        usd_utils.setup_stage_units(stage)

        # Convert Feet to Inches for system units
        l = self._length_model.as_float * 12.0
        w = self._width_model.as_float * 12.0
        cx = self._col_x_model.as_float * 12.0
        cz = self._col_z_model.as_float * 12.0
        h = self._height_model.as_float * 12.0
        js = self._joist_model.as_float * 12.0

        # Slab thickness remains in inches
        st = self._slab_model.as_float

        generate_building(stage, l, w, cx, cz, h, st, js)
        self._status_label.text = "Building Generated"
