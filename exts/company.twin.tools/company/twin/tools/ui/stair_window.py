import omni.ui as ui
import omni.usd
from ..objects.components.stair import Stair
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


EXIT_SIDE_OPTIONS = ["End", "Left", "Right"]
EXIT_SIDE_VALUES = ["end", "left", "right"]


class StairWindow(ui.Window):
    def __init__(self, title="Create Industrial Stair", **kwargs):
        super().__init__(title, width=400, height=480,
                         dockPreference=ui.DockPreference.LEFT_BOTTOM, **kwargs)

        self._total_rise_model = ui.SimpleFloatModel(120.0)
        self._width_model = ui.SimpleFloatModel(48.0)
        self._angle_model = ui.SimpleFloatModel(43.5)
        self._plat_length_model = ui.SimpleFloatModel(48.0)
        self._plat_width_model = ui.SimpleFloatModel(48.0)
        self._exit_side_model = ListItemModel(EXIT_SIDE_OPTIONS)
        self._include_platform_model = ui.SimpleBoolModel(True)

        self._status_model = ui.SimpleStringModel("Ready")
        self._build_ui()

    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Industrial Stair Generator", style={"font_size": 18})
                ui.Label("OSHA 1910.25 — C10x20 Stringers", style={"color": 0xFF888888, "font_size": 12})

                ui.Separator(height=10)

                self._build_row("Total Rise (in)", self._total_rise_model)
                self._build_row("Clear Width (in)", self._width_model)
                self._build_row("Angle (degrees)", self._angle_model)

                ui.Separator(height=10)
                with ui.HStack(height=24):
                    ui.Label("Platform", style={"font_size": 14}, width=150)
                    ui.CheckBox(model=self._include_platform_model, width=24)
                    ui.Label("Include", style={"color": 0xFFAAAAAA})
                self._build_row("Platform Length (in)", self._plat_length_model)
                self._build_row("Platform Width (in)", self._plat_width_model)

                with ui.HStack(height=24):
                    ui.Label("Exit Side", width=150, style={"color": 0xFFAAAAAA})
                    ui.ComboBox(self._exit_side_model)

                ui.Separator(height=10)

                ui.Button("Create Stair", clicked_fn=self._on_create, height=40)

                ui.Separator(height=10)
                ui.Label("Status:", style={"color": 0xFFAAAAAA})
                ui.Label("", model=self._status_model, style={"color": 0xFFEEEEEE})

    def _build_row(self, label, model):
        with ui.HStack(height=24):
            ui.Label(label, width=150, style={"color": 0xFFAAAAAA})
            ui.FloatDrag(model=model, min=1.0, max=10000.0, step=0.5)

    def set_params(self, params: dict):
        if "total_rise" in params:
            self._total_rise_model.set_value(float(params["total_rise"]))
        if "width" in params:
            self._width_model.set_value(float(params["width"]))
        if "angle_deg" in params:
            self._angle_model.set_value(float(params["angle_deg"]))
        if "platform_length" in params:
            self._plat_length_model.set_value(float(params["platform_length"]))
        if "platform_width" in params:
            self._plat_width_model.set_value(float(params["platform_width"]))
        if "exit_side" in params:
            val = str(params["exit_side"]).lower()
            if val in EXIT_SIDE_VALUES:
                idx = EXIT_SIDE_VALUES.index(val)
                self._exit_side_model._current_index.set_value(idx)
        if "include_platform" in params:
            self._include_platform_model.set_value(bool(params["include_platform"]))

    def _on_create(self):
        rise = self._total_rise_model.as_float
        width = self._width_model.as_float
        angle_deg = self._angle_model.as_float
        plat_length = self._plat_length_model.as_float
        plat_width = self._plat_width_model.as_float
        exit_idx = self._exit_side_model._current_index.as_int
        exit_side = EXIT_SIDE_VALUES[exit_idx]

        if rise < 10:
            self._status_model.set_value("Error: Rise too small")
            return

        stage = omni.usd.get_context().get_stage()
        usd_utils.setup_stage_units(stage)

        base_path = "/World/Stair"
        path = base_path
        counter = 1
        while stage.GetPrimAtPath(path):
            path = f"{base_path}_{counter}"
            counter += 1

        self._status_model.set_value(f"Generating at {path}...")

        include_platform = self._include_platform_model.as_bool

        try:
            result = Stair.create(
                stage, path,
                total_rise=rise,
                width=width,
                angle_deg=angle_deg,
                platform_length=plat_length,
                platform_width=plat_width,
                exit_side=exit_side,
                include_platform=include_platform,
            )
            if result:
                self._status_model.set_value(f"Success: Created {path}")
            else:
                self._status_model.set_value("Error: Generation Failed")
        except Exception as e:
            self._status_model.set_value(f"Exception: {str(e)}")
