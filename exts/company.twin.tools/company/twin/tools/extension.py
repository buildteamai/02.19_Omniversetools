import omni.ui
import omni.ext
import omni.kit.menu.utils
from omni.kit.menu.utils import MenuItemDescription

class Extension(omni.ext.IExt):
    def on_startup(self, ext_id):
        print("[company.twin.tools] startup")
        self._pyramid_window = None
        self._trapeze_window = None
        self._wide_flange_window = None
        self._sheet_metal_window = None
        self._create_object_window = None
        self._enclosure_configurator_window = None
        self._mating_window = None
        self._insert_equipment_window = None
        self._snap_tool_window = None
        self._pipe_window = None
        self._channel_window = None
        self._hss_window = None
        self._steel_connection_window = None
        self._ohpf_window = None
        self._bom_window = None
        self._duct_window = None
        self._fan_window = None
        self._building_window = None
        self._style_editor_window = None
        self._strongback_window = None
        self._screen_guard_window = None
        self._frame_window = None
        self._tap_window = None
        self._step_import_window = None
        self._stair_window = None

        # Force cleanup of old menu to ensure update
        if hasattr(self, "_menu_list"):
            omni.kit.menu.utils.remove_menu_items(self._menu_list, "Tools")
        
        print("[company.twin.tools] Building Tools menu...")
        self._menu_list = [
            MenuItemDescription(name="Tools", sub_menu=[
                
                # --- STEEL ---
                MenuItemDescription(name="Steel", sub_menu=[
                    MenuItemDescription(name="Frame Generator", onclick_fn=self._show_frame_window),
                    MenuItemDescription(name="Wide Flange", onclick_fn=self._show_wide_flange_window),
                    MenuItemDescription(name="Channel", onclick_fn=self._show_channel_window),
                    MenuItemDescription(name="HSS Tube", onclick_fn=self._show_hss_window),
                    MenuItemDescription(name="Create Connection", onclick_fn=self._show_steel_connection_window),
                ]),
                
                # --- MEP ---
                MenuItemDescription(name="MEP", sub_menu=[
                    MenuItemDescription(name="Ductwork", onclick_fn=self._show_duct_window),
                    MenuItemDescription(name="Piping", onclick_fn=self._show_pipe_window),
                    MenuItemDescription(name="Fan", onclick_fn=self._show_fan_window),
                    MenuItemDescription(name="Trapeze Hanger", onclick_fn=self._show_trapeze_window),
                ]),
                
                # --- ARCHITECTURE ---
                MenuItemDescription(name="Architecture", sub_menu=[
                    MenuItemDescription(name="Enclosure Configurator", onclick_fn=self._show_enclosure_configurator),
                    MenuItemDescription(name="Building Configurator", onclick_fn=self._show_building_window),
                    MenuItemDescription(name="Construction Cube", onclick_fn=self._show_construction_cube_window),
                    MenuItemDescription(name="Add Exhaust Tap", onclick_fn=self._show_tap_window),
                ]),
                
                # --- CONVEYOR ---
                MenuItemDescription(name="Conveyor", sub_menu=[
                    MenuItemDescription(name="OHPF 10k", onclick_fn=self._show_ohpf_window),
                ]),
                
                # --- IMPORTERS ---
                MenuItemDescription(name="Importers", sub_menu=[
                    MenuItemDescription(name="STEP File", onclick_fn=self._show_step_import_window),
                ]),
                
                # --- OBJECTS & PARTS ---
                MenuItemDescription(name="Objects", sub_menu=[
                    MenuItemDescription(name="Create Object", onclick_fn=self._show_create_object_window),
                    MenuItemDescription(name="Strongback", onclick_fn=self._show_strongback_window),
                    MenuItemDescription(name="Safety Fence", onclick_fn=self._show_screen_guard_window),
                    MenuItemDescription(name="Insert Equipment", onclick_fn=self._show_insert_equipment_window),
                    MenuItemDescription(name="Sheet Metal Panel", onclick_fn=self._show_sheet_metal_window),
                    MenuItemDescription(name="Pyramid", onclick_fn=self._show_pyramid_window),
                    MenuItemDescription(name="Industrial Stair", onclick_fn=self._show_stair_window),
                ]),
                
                # --- UTILITIES ---
                MenuItemDescription(name="Utilities", sub_menu=[
                    MenuItemDescription(name="Snap Tool", onclick_fn=self._show_snap_tool_window),
                    MenuItemDescription(name="Mate Objects", onclick_fn=self._show_mating_window),
                    MenuItemDescription(name="Verify Mating", onclick_fn=self._verify_mating),
                    MenuItemDescription(name="Measurement", onclick_fn=self._show_measure_window),
                    MenuItemDescription(name="BOM Export", onclick_fn=self._show_bom_window),
                    MenuItemDescription(name="New Scene (ANSI)", onclick_fn=self._new_ansi_scene),
                ]),
                
                # --- MODIFICATION ---
                MenuItemDescription(name="Modification", sub_menu=[
                    MenuItemDescription(name="Style Editor", onclick_fn=self._show_style_editor_window),
                ]),

                MenuItemDescription(),  # Separator
            ]),
        ]

        
        omni.kit.menu.utils.add_menu_items(self._menu_list, "Tools")
        
        
        print("[company.twin.tools] startup complete - no errors.")



    def _show_create_object_window(self, *args):
        from .ui.create_object_window import CreateObjectWindow
        if not self._create_object_window:
            self._create_object_window = CreateObjectWindow()
        self._create_object_window.visible = True

    def _show_enclosure_configurator(self, *args):
        from .enclosure.enclosure_configurator import EnclosureConfiguratorWindow
        if not hasattr(self, "_enclosure_configurator_window"):
            self._enclosure_configurator_window = None
        if not self._enclosure_configurator_window:
            self._enclosure_configurator_window = EnclosureConfiguratorWindow()
        self._enclosure_configurator_window.visible = True

    def _show_strongback_window(self, *args):
        from .ui.strongback_window import StrongbackWindow
        if not hasattr(self, "_strongback_window"):
            self._strongback_window = None
        if not self._strongback_window:
            self._strongback_window = StrongbackWindow()
        self._strongback_window.visible = True

    def _show_screen_guard_window(self, *args):
        from .ui.screen_guard_window import ScreenGuardWindow
        if not hasattr(self, "_screen_guard_window"):
            self._screen_guard_window = None
        if not self._screen_guard_window:
            self._screen_guard_window = ScreenGuardWindow()
        self._screen_guard_window.visible = True

    def _show_pyramid_window(self, *args):
        from .ui.pyramid_window import PyramidWindow
        if not hasattr(self, "_pyramid_window"):
            self._pyramid_window = None
        if not self._pyramid_window:
            self._pyramid_window = PyramidWindow()
        self._pyramid_window.visible = True

    def _show_wide_flange_window(self, *args):
        from .ui.wide_flange_window import WideFlangeWindow
        if not hasattr(self, "_wide_flange_window"):
            self._wide_flange_window = None
        if not self._wide_flange_window:
            self._wide_flange_window = WideFlangeWindow()
        self._wide_flange_window.visible = True

    def _show_frame_window(self, *args):
        from .ui.frame_window import FrameWindow
        if not hasattr(self, "_frame_window"):
            self._frame_window = None
        if not self._frame_window:
            self._frame_window = FrameWindow()
        self._frame_window.visible = True

    def _show_sheet_metal_window(self, *args):
        from .ui.sheet_metal_window import SheetMetalWindow
        if not hasattr(self, "_sheet_metal_window"):
            self._sheet_metal_window = None
        if not self._sheet_metal_window:
            self._sheet_metal_window = SheetMetalWindow("Sheet Metal Configurator")
        self._sheet_metal_window.visible = True

    def _show_duct_window(self, *args):
        from .ui.duct_window import DuctWindow
        if not hasattr(self, "_duct_window"):
            self._duct_window = None
        if not self._duct_window:
            self._duct_window = DuctWindow()
        self._duct_window.visible = True

    def _show_mating_window(self, *args):
        from .ui.mating_window import MatingWindow
        if not hasattr(self, "_mating_window"):
            self._mating_window = None
        if not self._mating_window:
            self._mating_window = MatingWindow()
        self._mating_window.visible = True

    def _show_insert_equipment_window(self, *args):
        from .ui.insert_equipment_window import InsertEquipmentWindow
        if not hasattr(self, "_insert_equipment_window"):
            self._insert_equipment_window = None
        if not self._insert_equipment_window:
            self._insert_equipment_window = InsertEquipmentWindow()
        self._insert_equipment_window.visible = True

    def _show_snap_tool_window(self, *args):
        from .ui.snap_tool_window import SnapToolWindow
        if not hasattr(self, "_snap_tool_window"):
            self._snap_tool_window = None
        if not self._snap_tool_window:
            self._snap_tool_window = SnapToolWindow()
        self._snap_tool_window.visible = True

    def _show_pipe_window(self, *args):
        from .ui.pipe_window import PipeWindow
        if not hasattr(self, "_pipe_window"):
            self._pipe_window = None
        if not self._pipe_window:
            self._pipe_window = PipeWindow()
        self._pipe_window.visible = True

    def _show_channel_window(self, *args):
        from .ui.channel_window import ChannelWindow
        if not hasattr(self, "_channel_window"):
            self._channel_window = None
        if not self._channel_window:
            self._channel_window = ChannelWindow()
        self._channel_window.visible = True

    def _show_hss_window(self, *args):
        from .ui.hss_window import HSSWindow
        if not hasattr(self, "_hss_window"):
            self._hss_window = None
        if not self._hss_window:
            self._hss_window = HSSWindow()
        self._hss_window.visible = True

    def _show_steel_connection_window(self, *args):
        from .ui.steel_connection_window import SteelConnectionWindow
        if not hasattr(self, "_steel_connection_window"):
            self._steel_connection_window = None
        if not self._steel_connection_window:
            self._steel_connection_window = SteelConnectionWindow()
        self._steel_connection_window.visible = True



    def _show_bom_window(self, *args):
        from .ui.bom_window import BOMWindow
        if not hasattr(self, "_bom_window"):
            self._bom_window = None
        if not self._bom_window:
            self._bom_window = BOMWindow()
        self._bom_window.visible = True

    def _show_ohpf_window(self, *args):
        from .ui.ohpf_window import OHPFWindow
        if not hasattr(self, "_ohpf_window"):
            self._ohpf_window = None
        if not self._ohpf_window:
            self._ohpf_window = OHPFWindow()
        self._ohpf_window.visible = True

    def _show_fan_window(self, *args):
        from .ui.fan_window import FanWindow
        if not hasattr(self, "_fan_window"):
            self._fan_window = None
        if not self._fan_window:
            self._fan_window = FanWindow()
        self._fan_window.visible = True

    def _show_trapeze_window(self, *args):
        from .ui.trapeze_window import TrapezeWindow
        if not hasattr(self, "_trapeze_window"):
            self._trapeze_window = None
        if not self._trapeze_window:
            self._trapeze_window = TrapezeWindow()
        self._trapeze_window.visible = True

    def _show_building_window(self, *args):
        from .ui.building_window import OmniPaintBuildingWindow
        if not hasattr(self, "_building_window"):
            self._building_window = None
        if not self._building_window:
            self._building_window = OmniPaintBuildingWindow()
        self._building_window.visible = True

    def _show_measure_window(self, *args):
        from .utils.measure_tool import MeasureToolWindow
        if not hasattr(self, "_measure_window"):
            self._measure_window = None
        if not self._measure_window:
            self._measure_window = MeasureToolWindow()
        self._measure_window.visible = True

    def _verify_mating(self, *args):
        from .verify_mating import run_verification
        # Run verification logic
        run_verification()

    def _new_ansi_scene(self, *args):
        """
        Creates a new stage with ANSI standards (Inches, Y-Up).
        """
        import omni.usd
        from pxr import UsdGeom, UsdLux, Gf, Sdf
        
        # Create new stage
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()
        
        # Set Units (Inches) and Axis (Y-Up)
        UsdGeom.SetStageMetersPerUnit(stage, 0.0254)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        
        # Create Default Prim /World
        root = UsdGeom.Xform.Define(stage, "/World")
        stage.SetDefaultPrim(root.GetPrim())
        
        # Create Environment Scope
        UsdGeom.Scope.Define(stage, "/World/Environment")
        
        # Add Grey Studio Light
        light_path = "/World/Environment/GreyStudio"
        dome = UsdLux.DomeLight.Define(stage, light_path)
        dome.GetColorAttr().Set(Gf.Vec3f(0.8, 0.8, 0.8)) 
        dome.GetIntensityAttr().Set(1000.0)
        
        print("[company.twin.tools] Created New ANSI Scene (Inches, Y-Up)")

    def _show_style_editor_window(self, *args):
        from .ui.style_editor_window import StyleEditorWindow
        if not hasattr(self, "_style_editor_window"):
            self._style_editor_window = None
        if not self._style_editor_window:
            self._style_editor_window = StyleEditorWindow()
        self._style_editor_window.visible = True

    def _show_construction_cube_window(self, *args):
        from .ui.construction_cube_window import ConstructionCubeWindow
        if not hasattr(self, "_construction_cube_window"):
            self._construction_cube_window = None
        if not self._construction_cube_window:
            self._construction_cube_window = ConstructionCubeWindow()
        self._construction_cube_window.visible = True

    def _show_tap_window(self, *args):
        from .enclosure.tap_window import TapWindow
        if not hasattr(self, "_tap_window"):
            self._tap_window = None
        if not self._tap_window:
            self._tap_window = TapWindow()
        self._tap_window.visible = True

    def _show_step_import_window(self, *args):
        from .ui.step_import_window import StepImportWindow
        if not hasattr(self, "_step_import_window"):
            self._step_import_window = None
        if not self._step_import_window:
            self._step_import_window = StepImportWindow()
        self._step_import_window.visible = True

    def on_shutdown(self):
        print("[company.twin.tools] shutdown")
        pyramid_window = getattr(self, "_pyramid_window", None)
        if pyramid_window:
            pyramid_window.destroy()
            self._pyramid_window = None
            
        wide_flange_window = getattr(self, "_wide_flange_window", None)
        if wide_flange_window:
            wide_flange_window.destroy()
            self._wide_flange_window = None
            
        sheet_metal_window = getattr(self, "_sheet_metal_window", None)
        if sheet_metal_window:
            sheet_metal_window.destroy()
            self._sheet_metal_window = None
            
        duct_window = getattr(self, "_duct_window", None)
        if duct_window:
            duct_window.destroy()
            self._duct_window = None
        
        create_object_window = getattr(self, "_create_object_window", None)
        if create_object_window:
            create_object_window.destroy()
            self._create_object_window = None
        
        enclosure_configurator_window = getattr(self, "_enclosure_configurator_window", None)
        if enclosure_configurator_window:
            enclosure_configurator_window.destroy()
            self._enclosure_configurator_window = None
            
        mating_window = getattr(self, "_mating_window", None)
        if mating_window:
            mating_window.destroy()
            self._mating_window = None

        insert_equipment_window = getattr(self, "_insert_equipment_window", None)
        if insert_equipment_window:
            insert_equipment_window.destroy()
            self._insert_equipment_window = None

        snap_tool_window = getattr(self, "_snap_tool_window", None)
        if snap_tool_window:
            snap_tool_window.destroy()
            self._snap_tool_window = None

        pipe_window = getattr(self, "_pipe_window", None)
        if pipe_window:
            pipe_window.destroy()
            self._pipe_window = None

        bom_window = getattr(self, "_bom_window", None)
        if bom_window:
            bom_window.destroy()
            self._bom_window = None

        ohpf_window = getattr(self, "_ohpf_window", None)
        if ohpf_window:
            ohpf_window.destroy()
            self._ohpf_window = None

        fan_window = getattr(self, "_fan_window", None)
        if fan_window:
            fan_window.destroy()
            self._fan_window = None

        building_window = getattr(self, "_building_window", None)
        if building_window:
            building_window.destroy()
            self._building_window = None

        measure_window = getattr(self, "_measure_window", None)
        if measure_window:
            measure_window.destroy()
            self._measure_window = None

        style_editor_window = getattr(self, "_style_editor_window", None)
        if style_editor_window:
            style_editor_window.destroy()
            self._style_editor_window = None

        frame_window = getattr(self, "_frame_window", None)
        if frame_window:
            frame_window.destroy()
            self._frame_window = None

        construction_cube_window = getattr(self, "_construction_cube_window", None)
        if construction_cube_window:
            construction_cube_window.destroy()
            self._construction_cube_window = None
            
        tap_window = getattr(self, "_tap_window", None)
        if tap_window:
            tap_window.destroy()
            self._tap_window = None

        strongback_window = getattr(self, "_strongback_window", None)
        if strongback_window:
            strongback_window.destroy()
            self._strongback_window = None

        step_import_window = getattr(self, "_step_import_window", None)
        if step_import_window:
            step_import_window.destroy()
            self._step_import_window = None

        screen_guard_window = getattr(self, "_screen_guard_window", None)
        if screen_guard_window:
            screen_guard_window.destroy()
            self._screen_guard_window = None

        trapeze_window = getattr(self, "_trapeze_window", None)
        if trapeze_window:
            trapeze_window.destroy()
            self._trapeze_window = None

        stair_window = getattr(self, "_stair_window", None)
        if stair_window:
            stair_window.destroy()
            self._stair_window = None

        if hasattr(self, "_menu_list"):
            omni.kit.menu.utils.remove_menu_items(self._menu_list, "Tools")

    def _show_stair_window(self, *args):
        try:
            from .ui.stair_window import StairWindow
            if not hasattr(self, "_stair_window"):
                self._stair_window = None
            if not self._stair_window:
                self._stair_window = StairWindow()
            self._stair_window.visible = True
        except Exception as e:
            print(f"[company.twin.tools] ERROR showing Stair Window: {e}")
            import traceback
            traceback.print_exc()
            

