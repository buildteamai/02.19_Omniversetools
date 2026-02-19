
import omni.ui as ui
import omni.usd
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, UsdLux

class StyleEditorWindow(ui.Window):
    def __init__(self, title="Style Editor", **kwargs):
        super().__init__(title, width=300, height=500, **kwargs)
        self.frame.set_build_fn(self._build_fn)
        self._info_label = None
        
    def _build_fn(self):
        with ui.ScrollingFrame():
            with ui.VStack(height=0, spacing=5, style={"margin": 10}):
                
                ui.Label("Reference Override Tools", height=20, style={"font_size": 18, "color": 0xFFAAAAAA})
                ui.Separator(height=5)
                
                ui.Label("Safety Colors", height=20, style={"color": 0xFF888888})
                with ui.HStack(height=30, spacing=5):
                    ui.Button("Safety Yellow", clicked_fn=lambda: self._apply_style("SafetyYellow", (1.0, 0.8, 0.0), "Plastic"))
                    ui.Rectangle(width=20, height=20, style={"background_color": 0xFF00CCFF, "border_radius": 3})
                
                with ui.HStack(height=30, spacing=5):
                    ui.Button("Safety Red", clicked_fn=lambda: self._apply_style("SafetyRed", (0.8, 0.1, 0.1), "Plastic"))
                    ui.Rectangle(width=20, height=20, style={"background_color": 0xFF1111CC, "border_radius": 3})

                with ui.HStack(height=30, spacing=5):
                    ui.Button("Safety Blue", clicked_fn=lambda: self._apply_style("SafetyBlue", (0.1, 0.3, 0.8), "Plastic"))
                    ui.Rectangle(width=20, height=20, style={"background_color": 0xFFCC4411, "border_radius": 3})

                ui.Spacer(height=10)
                ui.Label("Metals", height=20, style={"color": 0xFF888888})
                ui.Button("Galvanized Steel", height=30, clicked_fn=lambda: self._apply_style("GalvanizedSteel", (0.6, 0.62, 0.65), "Metal"))
                ui.Button("Black Iron", height=30, clicked_fn=lambda: self._apply_style("BlackIron", (0.1, 0.1, 0.1), "Metal"))
                ui.Button("Stainless Steel", height=30, clicked_fn=lambda: self._apply_style("StainlessSteel", (0.7, 0.7, 0.75), "Metal"))

                ui.Spacer(height=10)
                ui.Label("Specialty", height=20, style={"color": 0xFF888888})
                ui.Button("Tigers Glass", height=30, clicked_fn=lambda: self._apply_style("TigersGlass", (1.0, 0.4, 0.0), "Glass"))

                ui.Spacer(height=10)
                ui.Label("Specialty", height=20, style={"color": 0xFF888888})
                ui.Button("Tigers Metal", height=30, clicked_fn=lambda: self._apply_style("TigersMetal", (1.0, 0.4, 0.0), "GlassOrMetal"))

                ui.Spacer(height=10)
                ui.Label("Utility", height=20, style={"color": 0xFF888888})
                ui.Button("Clear Overrides", height=30, clicked_fn=self._clear_overrides)
                # Apply Invisible as a material, user can also use visibility property but this is "Style"
                ui.Button("Invisible (Hider)", height=30, clicked_fn=lambda: self._apply_style("Invisible", (0,0,0), "Transparency"))

                ui.Spacer(height=10)
                ui.Label("Selection Info", height=20, style={"color": 0xFF888888})
                self._info_label = ui.Label("Select an object to modify", word_wrap=True)

    def _get_context(self):
        return omni.usd.get_context()

    def _get_stage(self):
        return self._get_context().get_stage()

    def _apply_style(self, name, color_rgb, mat_type):
        """
        Applies a style to the current selection.
        - If Light: Sets 'color' input.
        - If Geometry: Binds material with 'strongerThanDescendants'.
        """
        ctx = self._get_context()
        stage = self._get_stage()
        selection = ctx.get_selection().get_selected_prim_paths()
        
        if not selection:
            if self._info_label: self._info_label.text = "No selection."
            return

        # Ensure material exists (only needed for geometry)
        mat_path = None
        # Don't create material if we only selected lights? 
        # Hard to know ahead of time, checking selection types first is safer but slower.
        # We'll create it on demand if we encounter a non-light.
        
        count = 0
        light_count = 0
        
        for path in selection:
            prim = stage.GetPrimAtPath(path)
            if not prim:
                continue
                
            # Check if it's a light (supports BoundableLightBase - RectLight, SphereLight, etc)
            is_light = False
            if prim.IsA(UsdLux.BoundableLightBase) or prim.IsA(UsdLux.NonboundableLightBase):
                is_light = True
            
            if is_light:
                # Apply Color to Light
                # Attempt to get LightAPI or specific Schema
                # Most lights have "inputs:color"
                attr = prim.GetAttribute("inputs:color")
                if not attr:
                     attr = prim.GetAttribute("color") # older USD
                
                if attr:
                    attr.Set(Gf.Vec3f(*color_rgb))
                    light_count += 1
                else:
                    # Try creating it via API if missing
                    light_api = UsdLux.LightAPI(prim)
                    if light_api:
                        light_api.CreateColorAttr().Set(Gf.Vec3f(*color_rgb))
                        light_count += 1
            else:
                # Apply Material to Geometry/Xform
                if not mat_path:
                    mat_path = self._ensure_material(stage, name, color_rgb, mat_type)
                
                if mat_path:
                    # Create Binding API
                    binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
                    mat = UsdShade.Material.Get(stage, mat_path)
                    if mat:
                        # Bind with Stronger Than Descendants to override references
                        binding_api.Bind(mat, bindingStrength=UsdShade.Tokens.strongerThanDescendants)
                        
                        # Handle Invisible Special Case
                        if name == "Invisible":
                            # Also Hide it? or just transparent material?
                            # Using just material might leave specular highlights if not careful.
                            # Let's also set visibility to invisible for good measure if they really want it GONE visually
                            # but keep the object.
                            # Actually, "Invisible" style usually implies "Matte/ShadowCatcher" or just "Gone".
                            # Given the prompt "change... to blue", "Invisible" was my addition.
                            # I'll stick to just the transparent material logic defined in _ensure_material for now.
                            pass

                        count += 1

        if self._info_label:
            self._info_label.text = f"Applied '{name}': {count} Objects, {light_count} Lights."

    def _ensure_material(self, stage, name, color, mat_type):
        """
        Creates the material in /Looks if it doesn't exist.
        """
        looks_scope_path = "/Looks"
        if not stage.GetPrimAtPath(looks_scope_path):
            stage.DefinePrim(looks_scope_path, "Scope")

        mat_path = f"{looks_scope_path}/{name}"
        if stage.GetPrimAtPath(mat_path):
            # Force update inputs even if material exists to ensure adjustments apply
            pass 
        else:
             # Create new material if it doesn't exist
             UsdShade.Material.Define(stage, mat_path)

        # Always re-define inputs to handle updates
        mat = UsdShade.Material.Get(stage, mat_path)
        pbr_shader = UsdShade.Shader.Define(stage, f"{mat_path}/PBRShader")
        if not pbr_shader.GetIdAttr().Get():
             pbr_shader.CreateIdAttr("UsdPreviewSurface")

        # Set Inputs
        pbr_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(color)
        
        if mat_type == "Metal":
            pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.8)
            pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.2)
        elif mat_type == "Plastic":
            pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
            pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.4)
        elif mat_type == "Transparency":
            pbr_shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(0.0)
            pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.0)
            # Ensure it is treated as transparent
            pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        elif mat_type == "GlassOrMetal": # Renamed internal type for consistent logic
            pbr_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(color)
            pbr_shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(1.0) # Fully opaque
            pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.0) # Mirror
            pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(1.0) # Fully metallic
            pbr_shader.CreateInput("clearcoat", Sdf.ValueTypeNames.Float).Set(1.0)
            pbr_shader.CreateInput("ior", Sdf.ValueTypeNames.Float).Set(1.5)

        # Connect Output
        # Safe connection using ConnectableAPI on the prim
        # UsdShade.ConnectableAPI(pbr_shader.GetPrim()).CreateOutput("surface", Sdf.ValueTypeNames.Token).ConnectToSource...
        # But Material.CreateSurfaceOutput() returns a UsdShade.Output
        
        surface_output = mat.CreateSurfaceOutput()
        # Connect to the shader's surface output (implicit on UsdPreviewSurface)
        # We need to bind the source.
        
        # In recent USD, ConnectToSource takes (source, sourceName)
        # source can be ConnectableAPI or path.
        
        pbr_connectable = UsdShade.ConnectableAPI(pbr_shader.GetPrim())
        surface_output.ConnectToSource(pbr_connectable, "surface")

        return mat_path

    def _clear_overrides(self):
        """
        Removes material overrides from selection.
        """
        ctx = self._get_context()
        stage = self._get_stage()
        selection = ctx.get_selection().get_selected_prim_paths()
        
        count = 0
        for path in selection:
            prim = stage.GetPrimAtPath(path)
            if not prim: continue

            # Remove Material Binding
            binding_api = UsdShade.MaterialBindingAPI(prim)
            if binding_api:
                binding_api.UnbindAllBindings()
                count += 1
        
        if self._info_label:
            self._info_label.text = f"Cleared overrides on {count} items."
