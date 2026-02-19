import omni.ui as ui
import omni.usd
from pxr import Usd, UsdGeom, Gf, Sdf
from ..objects.construction_cube import ConstructionCubeGenerator
from ..utils import usd_utils

class ConstructionCubeWindow(ui.Window):
    def __init__(self, title="Construction Cube", **kwargs):
        super().__init__(title, width=420, height=420, **kwargs)
        
        # Feet + Inches models (internal unit = inches)
        self._w_ft = ui.SimpleFloatModel(10.0)
        self._w_in = ui.SimpleFloatModel(0.0)
        self._h_ft = ui.SimpleFloatModel(10.0)
        self._h_in = ui.SimpleFloatModel(0.0)
        self._d_ft = ui.SimpleFloatModel(10.0)
        self._d_in = ui.SimpleFloatModel(0.0)
        
        # Readout labels (set after build)
        self._w_readout = None
        self._h_readout = None
        self._d_readout = None
        
        self._build_ui()
        self._update_readouts()
        
        # Listen for changes
        self._w_ft.add_value_changed_fn(lambda m: self._update_readouts())
        self._w_in.add_value_changed_fn(lambda m: self._update_readouts())
        self._h_ft.add_value_changed_fn(lambda m: self._update_readouts())
        self._h_in.add_value_changed_fn(lambda m: self._update_readouts())
        self._d_ft.add_value_changed_fn(lambda m: self._update_readouts())
        self._d_in.add_value_changed_fn(lambda m: self._update_readouts())

    def _total_inches(self, ft_model, in_model):
        return (ft_model.as_float * 12.0) + in_model.as_float

    def _fmt_ft_in(self, ft_model, in_model):
        total = self._total_inches(ft_model, in_model)
        ft = int(ft_model.as_float)
        inches = in_model.as_float
        return f"{ft}'-{inches:.1f}\"  ({total:.1f} in)"

    def _update_readouts(self):
        if self._w_readout:
            self._w_readout.text = self._fmt_ft_in(self._w_ft, self._w_in)
        if self._h_readout:
            self._h_readout.text = self._fmt_ft_in(self._h_ft, self._h_in)
        if self._d_readout:
            self._d_readout.text = self._fmt_ft_in(self._d_ft, self._d_in)

    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=8, padding=15):
                ui.Label("Construction Line Cube", style={"highlight_color": 0xFF00AAFF, "font_size": 18})
                ui.Label("Master skeleton — Dimensions in Feet & Inches", style={"color": 0xFFAAAAAA, "font_size": 12})
                
                ui.Spacer(height=3)
                ui.Separator(height=5)
                ui.Spacer(height=3)
                
                # --- Width ---
                ui.Label("Width (X)", style={"font_size": 13, "color": 0xFFCCCCCC})
                with ui.HStack(height=22, spacing=5):
                    ui.FloatDrag(model=self._w_ft, min=0.0, max=500.0, step=1.0)
                    ui.Label("ft", width=20)
                    ui.FloatDrag(model=self._w_in, min=0.0, max=11.99, step=0.5)
                    ui.Label("in", width=20)
                self._w_readout = ui.Label("", style={"color": 0xFF88CC00, "font_size": 11})
                
                ui.Spacer(height=3)
                
                # --- Height ---
                ui.Label("Height (Y)", style={"font_size": 13, "color": 0xFFCCCCCC})
                with ui.HStack(height=22, spacing=5):
                    ui.FloatDrag(model=self._h_ft, min=0.0, max=500.0, step=1.0)
                    ui.Label("ft", width=20)
                    ui.FloatDrag(model=self._h_in, min=0.0, max=11.99, step=0.5)
                    ui.Label("in", width=20)
                self._h_readout = ui.Label("", style={"color": 0xFF88CC00, "font_size": 11})
                
                ui.Spacer(height=3)
                
                # --- Depth ---
                ui.Label("Depth (Z)", style={"font_size": 13, "color": 0xFFCCCCCC})
                with ui.HStack(height=22, spacing=5):
                    ui.FloatDrag(model=self._d_ft, min=0.0, max=500.0, step=1.0)
                    ui.Label("ft", width=20)
                    ui.FloatDrag(model=self._d_in, min=0.0, max=11.99, step=0.5)
                    ui.Label("in", width=20)
                self._d_readout = ui.Label("", style={"color": 0xFF88CC00, "font_size": 11})
                
                ui.Spacer(height=5)
                
                # Preset Buttons (in feet)
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Presets:", width=55)
                    ui.Button("10'x10'x10'", clicked_fn=lambda: self._set_dim(10, 0, 10, 0, 10, 0))
                    ui.Button("20'x12'x20'", clicked_fn=lambda: self._set_dim(20, 0, 12, 0, 20, 0))
                    ui.Button("40'x16'x40'", clicked_fn=lambda: self._set_dim(40, 0, 16, 0, 40, 0))
                
                ui.Spacer(height=5)
                ui.Separator(height=5)

                # Edit Controls
                with ui.HStack(height=30, spacing=5):
                    ui.Button("Load Selected", clicked_fn=self._on_load_selected)
                    ui.Button("Clear", clicked_fn=self._on_clear)
                
                ui.Spacer(height=5)
                
                # Create/Update Button
                self._create_btn = ui.Button("Create Cube", clicked_fn=self._on_create, height=40, style={"background_color": 0xFF336600})
                
    def _set_dim(self, w_ft, w_in, h_ft, h_in, d_ft, d_in):
        self._w_ft.as_float = float(w_ft)
        self._w_in.as_float = float(w_in)
        self._h_ft.as_float = float(h_ft)
        self._h_in.as_float = float(h_in)
        self._d_ft.as_float = float(d_ft)
        self._d_in.as_float = float(d_in)
        self._update_readouts()

    def _set_from_inches(self, total, ft_model, in_model):
        """Decompose total inches into feet + remaining inches."""
        feet = int(total // 12)
        remaining = total - (feet * 12)
        ft_model.as_float = float(feet)
        in_model.as_float = float(remaining)

    def _on_load_selected(self):
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        selection = ctx.get_selection().get_selected_prim_paths()
        
        if not selection:
            print("[ConstructionCube] No selection")
            return
            
        prim_path = selection[0]
        prim = stage.GetPrimAtPath(prim_path)
        
        # Check type
        if not prim.GetCustomDataByKey("generatorType") == "construction_cube":
            print(f"[ConstructionCube] Selected prim {prim_path} is not a Construction Cube")
            return
            
        # Load Data (stored in inches)
        w = prim.GetCustomDataByKey("width")
        h = prim.GetCustomDataByKey("height")
        d = prim.GetCustomDataByKey("depth")
        
        if w and h and d:
            self._set_from_inches(float(w), self._w_ft, self._w_in)
            self._set_from_inches(float(h), self._h_ft, self._h_in)
            self._set_from_inches(float(d), self._d_ft, self._d_in)
            self._update_readouts()
            
            self._editing_path = prim_path
            self._create_btn.text = "Update Cube"
            print(f"[ConstructionCube] Loaded {prim_path}: {w}x{h}x{d} inches")

    def _on_clear(self):
        self._editing_path = None
        self._create_btn.text = "Create Cube"
        print("[ConstructionCube] Cleared selection")

    def _on_create(self):
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        if not stage:
            return
            
        # Compute total inches from feet + inches
        width = self._total_inches(self._w_ft, self._w_in)
        height = self._total_inches(self._h_ft, self._h_in)
        depth = self._total_inches(self._d_ft, self._d_in)
        
        # Determine Path
        if hasattr(self, "_editing_path") and self._editing_path:
            path = self._editing_path
            # Clear existing children (lines, anchors)
            prim = stage.GetPrimAtPath(path)
            # We can just delete the whole prim and recreate it, 
            # BUT we want to keep the transform!
            xform_cache = usd_utils.get_local_transform(prim)
            stage.RemovePrim(path)
            
            # Re-define logic below will handle creation
            is_update = True
        else:
             # 1. Create unique root path
            path_root = "/World/ConstructionCube"
            path = path_root
            idx = 1
            while stage.GetPrimAtPath(path):
                path = f"{path_root}_{idx}"
                idx += 1
            is_update = False
            xform_cache = None

        # 2. Define Root Xform
        root_xform = UsdGeom.Xform.Define(stage, path)
        usd_utils.setup_stage_units(stage)
        
        # Store Metadata
        prim = root_xform.GetPrim()
        prim.SetCustomDataByKey("generatorType", "construction_cube")
        prim.SetCustomDataByKey("width", float(width))
        prim.SetCustomDataByKey("height", float(height))
        prim.SetCustomDataByKey("depth", float(depth))

        # Restore/Set Transform
        if is_update and xform_cache:
             usd_utils.set_local_transform(prim, xform_cache)
        elif not is_update:
            # Place near selection if any
            selection = ctx.get_selection().get_selected_prim_paths()
            if selection:
                ref_prim = stage.GetPrimAtPath(selection[0])
                if ref_prim:
                    tf = usd_utils.get_local_transform(ref_prim)
                    if tf:
                        usd_utils.set_local_transform(root_xform.GetPrim(), tf)
        
        # 3. Generate Edges (Lines)
        edges = ConstructionCubeGenerator.create_edges(width, depth, height)
        lines_path = f"{path}/lines"
        
        
        # Determine color (construction blue/cyan)
        color = Gf.Vec3f(0.0, 0.8, 1.0)
        
        # Pass width=0.5 for physical visibility
        curves = usd_utils.create_basis_curves_from_edges(stage, lines_path, edges, color, width=0.5)
        
        # 4. Generate Anchors
        anchors_grp_path = f"{path}/anchors"
        UsdGeom.Scope.Define(stage, anchors_grp_path)
        
        anchor_defs = ConstructionCubeGenerator.get_anchor_definitions(width, depth, height)
        
        for ad in anchor_defs:
            name = ad['name']
            t = ad['translate']
            r = ad['rotate']
            c = ad['color']
            
            anchor_path = f"{anchors_grp_path}/{name}"
            
            xform = UsdGeom.Xform.Define(stage, anchor_path)
            xform.AddTranslateOp().Set(t)
            # Order: RotateXYZ
            xform.AddRotateXYZOp().Set(r)
            
            prim = xform.GetPrim()
            prim.CreateAttribute("twin:is_port", Sdf.ValueTypeNames.Bool).Set(True)
            prim.CreateAttribute("twin:port_type", Sdf.ValueTypeNames.String).Set("Construction_Anchor")
            prim.CreateAttribute("custom:is_anchor", Sdf.ValueTypeNames.Bool).Set(True)
            
            # Visual sphere (small)
            viz = UsdGeom.Sphere.Define(stage, f"{anchor_path}/viz")
            viz.GetRadiusAttr().Set(0.5) # Small viz
            viz.GetDisplayColorAttr().Set([c])
            
        action = "Updated" if is_update else "Created"
        print(f"[ConstructionCube] {action} at {path}")
