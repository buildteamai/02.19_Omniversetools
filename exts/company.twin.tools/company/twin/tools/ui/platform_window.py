import omni.ui as ui
import omni.usd
from pxr import UsdGeom
from ..objects.components.platform import (
    PlatformGenerator, BASE_NODE_NAMES,
    LEG_PROFILE_NAMES, FRAME_PROFILE_NAMES,
)
from ..utils import usd_utils


class ListItem(ui.AbstractItem):
    def __init__(self, text):
        super().__init__()
        self.model = ui.SimpleStringModel(text)


class ListItemModel(ui.AbstractItemModel):
    def __init__(self, items):
        super().__init__()
        self._items = [ListItem(text) for text in items]
        self._current_index = ui.SimpleIntModel()
        self._current_index.add_value_changed_fn(self._on_index_changed)

    def _on_index_changed(self, model):
        self._item_changed(None)

    def get_item_children(self, item):
        return self._items if item is None else []

    def get_item_value_model(self, item, column_id):
        if item is None:
            return self._current_index
        return item.model


# Short display labels for the 8 base nodes
_NODE_LABELS = {
    "Base_Corner_FR": "Corner FR",
    "Base_Corner_FL": "Corner FL",
    "Base_Corner_BR": "Corner BR",
    "Base_Corner_BL": "Corner BL",
    "Base_Mid_Front": "Mid Front",
    "Base_Mid_Back":  "Mid Back",
    "Base_Mid_Right": "Mid Right",
    "Base_Mid_Left":  "Mid Left",
}


class PlatformWindow(ui.Window):
    def __init__(self, title="Platform", **kwargs):
        super().__init__(title, width=420, height=680, **kwargs)

        # Feet + Inches models (internal unit = inches)
        self._w_ft = ui.SimpleFloatModel(10.0)
        self._w_in = ui.SimpleFloatModel(0.0)
        self._h_ft = ui.SimpleFloatModel(10.0)
        self._h_in = ui.SimpleFloatModel(0.0)
        self._d_ft = ui.SimpleFloatModel(10.0)
        self._d_in = ui.SimpleFloatModel(0.0)
        self._elev_ft = ui.SimpleFloatModel(0.0)
        self._elev_in = ui.SimpleFloatModel(0.0)

        # Base plate size models (inches)
        self._bp_width_model = ui.SimpleFloatModel(12.0)
        self._bp_depth_model = ui.SimpleFloatModel(12.0)
        self._bp_thickness_model = ui.SimpleFloatModel(0.5)

        # Node selection checkboxes (all on by default)
        self._node_models = {}
        for name in BASE_NODE_NAMES:
            self._node_models[name] = ui.SimpleBoolModel(True)

        # Leg models
        self._leg_profile_model = ListItemModel(LEG_PROFILE_NAMES)
        self._leg_profile_model._current_index.set_value(1)  # default HSS4x4x1/4

        # Frame models
        self._frame_profile_model = ListItemModel(FRAME_PROFILE_NAMES)
        self._frame_profile_model._current_index.set_value(1)  # default HSS4x4x1/4

        # Deck plate
        self._deck_thickness_model = ui.SimpleFloatModel(0.25)
        self._deck_materials = ["Galvanized", "Wood", "Rubber", "Black", "Yellow", "Blue"]
        self._deck_material_model = ListItemModel(self._deck_materials)

        # Readout labels
        self._w_readout = None
        self._h_readout = None
        self._d_readout = None
        self._elev_readout = None

        self._editing_path = None

        self._build_ui()
        self._update_readouts()

        # Listen for dimension changes
        for m in (self._w_ft, self._w_in, self._h_ft, self._h_in,
                  self._d_ft, self._d_in, self._elev_ft, self._elev_in):
            m.add_value_changed_fn(lambda _: self._update_readouts())

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
        if self._elev_readout:
            self._elev_readout.text = self._fmt_ft_in(self._elev_ft, self._elev_in)

    def _build_ui(self):
        with self.frame:
            with ui.ScrollingFrame():
                with ui.VStack(spacing=8, padding=15):
                    ui.Label("Platform Generator", style={"font_size": 18})
                    ui.Label("Construction Cube Skeleton + Platform Geometry",
                             style={"color": 0xFF888888, "font_size": 12})

                    ui.Spacer(height=3)
                    ui.Separator(height=5)
                    ui.Spacer(height=3)

                    # --- Construction Cube Dimensions ---
                    self._build_dim_row("Width (X)", self._w_ft, self._w_in, "_w_readout")
                    ui.Spacer(height=3)
                    self._build_dim_row("Height (Y)", self._h_ft, self._h_in, "_h_readout")
                    ui.Spacer(height=3)
                    self._build_dim_row("Depth (Z)", self._d_ft, self._d_in, "_d_readout")
                    ui.Spacer(height=3)
                    self._build_dim_row("Elevation (Y offset)", self._elev_ft, self._elev_in, "_elev_readout")

                    ui.Spacer(height=5)

                    # Preset Buttons
                    with ui.HStack(height=25, spacing=5):
                        ui.Label("Presets:", width=55)
                        ui.Button("10'x10'x10'", clicked_fn=lambda: self._set_dim(10, 0, 10, 0, 10, 0))
                        ui.Button("20'x12'x20'", clicked_fn=lambda: self._set_dim(20, 0, 12, 0, 20, 0))
                        ui.Button("40'x16'x40'", clicked_fn=lambda: self._set_dim(40, 0, 16, 0, 40, 0))

                    ui.Separator(height=10)

                    # --- Base Plates ---
                    ui.Label("Base Plates", style={"font_size": 16})
                    ui.Label("Centered on selected nodes, extruded +Y",
                             style={"color": 0xFF888888, "font_size": 11})
                    ui.Spacer(height=3)

                    self._build_float_row("Plate Width (in)", self._bp_width_model)
                    self._build_float_row("Plate Depth (in)", self._bp_depth_model)
                    self._build_float_row("Plate Thickness (in)", self._bp_thickness_model,
                                          min_val=0.125, max_val=2.0, step=0.125)

                    ui.Spacer(height=5)
                    ui.Label("Node Selection", style={"font_size": 13, "color": 0xFFCCCCCC})

                    # Select All / None buttons
                    with ui.HStack(height=22, spacing=5):
                        ui.Button("All", width=60, clicked_fn=self._select_all_nodes)
                        ui.Button("None", width=60, clicked_fn=self._select_no_nodes)
                        ui.Button("Corners", width=80, clicked_fn=self._select_corners)
                        ui.Button("Mids", width=80, clicked_fn=self._select_mids)

                    ui.Spacer(height=3)

                    # Node checkboxes in 2 columns
                    for i in range(0, len(BASE_NODE_NAMES), 2):
                        with ui.HStack(height=22, spacing=5):
                            # Left column
                            name_l = BASE_NODE_NAMES[i]
                            ui.CheckBox(model=self._node_models[name_l], width=20)
                            ui.Label(_NODE_LABELS[name_l], width=120,
                                     style={"color": 0xFFAAAAAA})
                            # Right column
                            if i + 1 < len(BASE_NODE_NAMES):
                                name_r = BASE_NODE_NAMES[i + 1]
                                ui.CheckBox(model=self._node_models[name_r], width=20)
                                ui.Label(_NODE_LABELS[name_r],
                                         style={"color": 0xFFAAAAAA})

                    ui.Separator(height=10)

                    # --- Legs ---
                    ui.Label("Legs", style={"font_size": 16})
                    ui.Label("HSS columns, length = Height (Y)",
                             style={"color": 0xFF888888, "font_size": 11})
                    ui.Spacer(height=3)

                    with ui.HStack(height=24):
                        ui.Label("Profile", width=150, style={"color": 0xFFAAAAAA})
                        ui.ComboBox(self._leg_profile_model)

                    ui.Separator(height=10)

                    # --- Upper Frames ---
                    ui.Label("Upper Frames", style={"font_size": 16})
                    ui.Label("Top collinear with leg top, face-to-face span",
                             style={"color": 0xFF888888, "font_size": 11})
                    ui.Spacer(height=3)

                    with ui.HStack(height=24):
                        ui.Label("Profile", width=150, style={"color": 0xFFAAAAAA})
                        ui.ComboBox(self._frame_profile_model)

                    ui.Separator(height=10)

                    # --- Deck Plate ---
                    ui.Label("Deck Plate", style={"font_size": 16})
                    ui.Label("Covers full Width x Depth, thickness +Y",
                             style={"color": 0xFF888888, "font_size": 11})
                    ui.Spacer(height=3)

                    self._build_float_row("Thickness (in)", self._deck_thickness_model,
                                          min_val=0.125, max_val=2.0, step=0.125)

                    with ui.HStack(height=24):
                        ui.Label("Material", width=150, style={"color": 0xFFAAAAAA})
                        ui.ComboBox(self._deck_material_model)

                    ui.Separator(height=10)

                    # Edit Controls
                    with ui.HStack(height=30, spacing=5):
                        ui.Button("Load Selected", clicked_fn=self._on_load_selected)
                        ui.Button("Clear", clicked_fn=self._on_clear)

                    ui.Spacer(height=5)

                    self._create_btn = ui.Button("Create Platform", clicked_fn=self._on_create,
                                                 height=40, style={"background_color": 0xFF336600})

    def _build_dim_row(self, label, ft_model, in_model, readout_attr):
        ui.Label(label, style={"font_size": 13, "color": 0xFFCCCCCC})
        with ui.HStack(height=22, spacing=5):
            ui.FloatDrag(model=ft_model, min=0.0, max=500.0, step=1.0)
            ui.Label("ft", width=20)
            ui.FloatDrag(model=in_model, min=0.0, max=11.99, step=0.5)
            ui.Label("in", width=20)
        readout = ui.Label("", style={"color": 0xFF88CC00, "font_size": 11})
        setattr(self, readout_attr, readout)

    def _build_float_row(self, label, model, min_val=1.0, max_val=48.0, step=0.5):
        with ui.HStack(height=24):
            ui.Label(label, width=150, style={"color": 0xFFAAAAAA})
            ui.FloatDrag(model=model, min=min_val, max=max_val, step=step)

    def _select_all_nodes(self):
        for m in self._node_models.values():
            m.set_value(True)

    def _select_no_nodes(self):
        for m in self._node_models.values():
            m.set_value(False)

    def _select_corners(self):
        for name, m in self._node_models.items():
            m.set_value("Corner" in name)

    def _select_mids(self):
        for name, m in self._node_models.items():
            m.set_value("Mid" in name)

    def _get_selected_nodes(self):
        return [name for name, m in self._node_models.items() if m.as_bool]

    def _set_dim(self, w_ft, w_in, h_ft, h_in, d_ft, d_in):
        self._w_ft.as_float = float(w_ft)
        self._w_in.as_float = float(w_in)
        self._h_ft.as_float = float(h_ft)
        self._h_in.as_float = float(h_in)
        self._d_ft.as_float = float(d_ft)
        self._d_in.as_float = float(d_in)
        self._update_readouts()

    def _set_from_inches(self, total, ft_model, in_model):
        feet = int(total // 12)
        remaining = total - (feet * 12)
        ft_model.as_float = float(feet)
        in_model.as_float = float(remaining)

    def _on_load_selected(self):
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        selection = ctx.get_selection().get_selected_prim_paths()

        if not selection:
            print("[Platform] No selection")
            return

        prim_path = selection[0]
        prim = stage.GetPrimAtPath(prim_path)

        if prim.GetCustomDataByKey("generatorType") != "platform":
            print(f"[Platform] Selected prim {prim_path} is not a Platform")
            return

        w = prim.GetCustomDataByKey("width")
        h = prim.GetCustomDataByKey("height")
        d = prim.GetCustomDataByKey("depth")
        elev = prim.GetCustomDataByKey("elevation") or 0.0

        if w and h and d:
            self._set_from_inches(float(w), self._w_ft, self._w_in)
            self._set_from_inches(float(h), self._h_ft, self._h_in)
            self._set_from_inches(float(d), self._d_ft, self._d_in)
            self._set_from_inches(float(elev), self._elev_ft, self._elev_in)

            # Load base plate params
            bp_w = prim.GetCustomDataByKey("bp_width")
            bp_d = prim.GetCustomDataByKey("bp_depth")
            bp_t = prim.GetCustomDataByKey("bp_thickness")
            if bp_w:
                self._bp_width_model.set_value(float(bp_w))
            if bp_d:
                self._bp_depth_model.set_value(float(bp_d))
            if bp_t:
                self._bp_thickness_model.set_value(float(bp_t))

            # Load leg params
            leg_prof = prim.GetCustomDataByKey("leg_profile")
            if leg_prof and leg_prof in LEG_PROFILE_NAMES:
                self._leg_profile_model._current_index.set_value(
                    LEG_PROFILE_NAMES.index(leg_prof))

            # Load deck plate params
            deck_t = prim.GetCustomDataByKey("deck_thickness")
            if deck_t:
                self._deck_thickness_model.set_value(float(deck_t))
            deck_mat = prim.GetCustomDataByKey("deck_material")
            if deck_mat and deck_mat in self._deck_materials:
                self._deck_material_model._current_index.set_value(
                    self._deck_materials.index(deck_mat))

            # Load frame profile
            frame_prof = prim.GetCustomDataByKey("frame_profile")
            if frame_prof and frame_prof in FRAME_PROFILE_NAMES:
                self._frame_profile_model._current_index.set_value(
                    FRAME_PROFILE_NAMES.index(frame_prof))

            # Load node selection
            bp_nodes_str = prim.GetCustomDataByKey("bp_nodes")
            if bp_nodes_str:
                bp_nodes = bp_nodes_str.split(",")
                for name, m in self._node_models.items():
                    m.set_value(name in bp_nodes)

            self._update_readouts()
            self._editing_path = prim_path
            self._create_btn.text = "Update Platform"
            print(f"[Platform] Loaded {prim_path}")

    def _on_clear(self):
        self._editing_path = None
        self._create_btn.text = "Create Platform"
        print("[Platform] Cleared selection")

    def _on_create(self):
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        if not stage:
            return

        width = self._total_inches(self._w_ft, self._w_in)
        depth = self._total_inches(self._d_ft, self._d_in)
        height = self._total_inches(self._h_ft, self._h_in)
        elevation = self._total_inches(self._elev_ft, self._elev_in)

        bp_width = self._bp_width_model.as_float
        bp_depth = self._bp_depth_model.as_float
        bp_thickness = self._bp_thickness_model.as_float
        bp_nodes = self._get_selected_nodes()

        leg_idx = self._leg_profile_model._current_index.as_int
        leg_profile = LEG_PROFILE_NAMES[leg_idx]

        frame_idx = self._frame_profile_model._current_index.as_int
        frame_profile = FRAME_PROFILE_NAMES[frame_idx]

        deck_thickness = self._deck_thickness_model.as_float
        deck_mat_idx = self._deck_material_model._current_index.as_int
        deck_material = self._deck_materials[deck_mat_idx]

        if self._editing_path:
            path = self._editing_path
            prim = stage.GetPrimAtPath(path)
            xform_cache = usd_utils.get_local_transform(prim)
            stage.RemovePrim(path)
            is_update = True
        else:
            path_root = "/World/Platform"
            path = path_root
            idx = 1
            while stage.GetPrimAtPath(path):
                path = f"{path_root}_{idx}"
                idx += 1
            is_update = False
            xform_cache = None

        PlatformGenerator.create(
            stage, path,
            width=width,
            depth=depth,
            height=height,
            elevation=elevation,
            bp_width=bp_width,
            bp_depth=bp_depth,
            bp_thickness=bp_thickness,
            bp_nodes=bp_nodes,
            leg_profile=leg_profile,
            leg_nodes=bp_nodes,
            frame_profile=frame_profile,
            deck_thickness=deck_thickness,
            deck_material=deck_material,
        )

        if is_update and xform_cache:
            prim = stage.GetPrimAtPath(path)
            usd_utils.set_local_transform(prim, xform_cache)

        action = "Updated" if is_update else "Created"
        print(f"[Platform] {action} at {path}")
