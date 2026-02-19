import omni.ui as ui
import omni.usd
from pxr import UsdGeom, Sdf
from ..objects.strongback import Strongback
from ..utils import usd_utils

class StrongbackWindow(ui.Window):
    def __init__(self, title="Create Strongback", **kwargs):
        super().__init__(title, width=400, height=550, **kwargs)

        self._length_model = ui.SimpleFloatModel(24.0)
        self._width_model = ui.SimpleFloatModel(8.0)
        self._height_model = ui.SimpleFloatModel(4.0)

        # Strongback-variant specific
        self._left_height_model = ui.SimpleFloatModel(2.0)
        self._flange_width_model = ui.SimpleFloatModel(1.0)

        # Stiffener Post specific
        self._leg_depth_model = ui.SimpleFloatModel(2.0)
        self._return_flange_model = ui.SimpleFloatModel(1.0)
        self._end_cap_model = ui.SimpleFloatModel(0.125)

        self._status_model = ui.SimpleStringModel("Ready")
        self._variant_index = 0
        self._strongback_frame = None
        self._stiffener_frame = None
        self._height_row = None
        self._gauge_combo = None

        self._build_ui()

    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Configure Strongback", style={"font_size": 18})
                ui.Separator(height=5)

                # --- Variant selector ---
                with ui.HStack(height=24):
                    ui.Label("Variant", width=150, style={"color": 0xFFAAAAAA})
                    combo = ui.ComboBox(0, *Strongback.VARIANTS, width=ui.Fraction(1))
                    combo.model.add_item_changed_fn(self._on_variant_changed)

                ui.Separator(height=2)

                # --- Common parameters ---
                self._build_row("Length / Y (in)", self._length_model)
                self._build_row("Width / X (in)", self._width_model)
                self._height_row = ui.VStack(height=24)
                with self._height_row:
                    self._build_row("Height / Z (in)", self._height_model)

                # --- Strongback-variant parameters ---
                self._strongback_frame = ui.CollapsableFrame(
                    "Strongback Parameters",
                    collapsed=False, height=0, visible=False,
                )
                with self._strongback_frame:
                    with ui.VStack(spacing=6):
                        self._build_row("Left Height (in)", self._left_height_model)
                        self._build_row("Flange Width (in)", self._flange_width_model)

                # --- Stiffener Post parameters ---
                self._stiffener_frame = ui.CollapsableFrame(
                    "Stiffener Post Parameters",
                    collapsed=False, height=0, visible=False,
                )
                with self._stiffener_frame:
                    with ui.VStack(spacing=6):
                        self._build_row("Leg Depth (in)", self._leg_depth_model)
                        self._build_row("Return Flange (in)", self._return_flange_model)
                        self._build_row("End Cap Thickness (in)", self._end_cap_model)
                        with ui.HStack(height=24):
                            ui.Label("Gauge", width=150, style={"color": 0xFFAAAAAA})
                            self._gauge_combo = ui.ComboBox(
                                1, *Strongback.GAUGE_OPTIONS, width=ui.Fraction(1),
                            )

                ui.Spacer(height=20)

                ui.Button("Create Strongback", clicked_fn=self._on_create, height=40)
                ui.Label("", model=self._status_model, style={"color": 0xFF888888})

    def _build_row(self, label, model):
        with ui.HStack(height=24):
            ui.Label(label, width=150, style={"color": 0xFFAAAAAA})
            ui.FloatDrag(model=model, min=0.0625, max=1000.0, step=0.125)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_variant_changed(self, model, item):
        self._variant_index = model.get_item_value_model().as_int
        if self._strongback_frame:
            self._strongback_frame.visible = (self._variant_index == 1)
        if self._stiffener_frame:
            self._stiffener_frame.visible = (self._variant_index == 2)
        if self._height_row:
            self._height_row.visible = (self._variant_index != 2)

    def _on_create(self):
        length = self._length_model.as_float
        width = self._width_model.as_float
        height = self._height_model.as_float
        variant = Strongback.VARIANTS[self._variant_index]

        stage = omni.usd.get_context().get_stage()
        usd_utils.setup_stage_units(stage)

        # Unique Path
        base_path = "/World/Strongback"
        path = base_path
        counter = 1
        while stage.GetPrimAtPath(path):
            path = f"{base_path}_{counter}"
            counter += 1

        self._status_model.set_value(f"Generating {variant} at {path}...")

        kwargs = dict(
            length=length,
            width=width,
            height=height,
            variant=variant,
        )

        if variant == "Strongback":
            kwargs["left_height"] = self._left_height_model.as_float
            kwargs["flange_width"] = self._flange_width_model.as_float

        elif variant == "Stiffener Post":
            kwargs["leg_depth"] = self._leg_depth_model.as_float
            kwargs["return_flange"] = self._return_flange_model.as_float
            kwargs["end_cap_thickness"] = self._end_cap_model.as_float
            gauge_idx = self._gauge_combo.model.get_item_value_model().as_int
            kwargs["gauge"] = Strongback.GAUGE_OPTIONS[gauge_idx]

        result = Strongback.create(stage, path, **kwargs)

        if result:
            self._status_model.set_value(f"Created: {path}")
            omni.usd.get_context().get_selection().set_selected_prim_paths([path], True)
        else:
            self._status_model.set_value("Error generating geometry")
