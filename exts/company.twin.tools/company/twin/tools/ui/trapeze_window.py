import omni.ui as ui
import omni.usd
from pxr import UsdGeom, Sdf
from ..objects.trapeze import Trapeze
from ..utils import usd_utils

class TrapezeWindow(ui.Window):
    def __init__(self, title="Create Trapeze", **kwargs):
        super().__init__(title, width=400, height=450, **kwargs)

        self._width_model = ui.SimpleFloatModel(24.0) # Duct Width
        self._span_model = ui.SimpleFloatModel(28.0)  # Width + 4"
        self._cantilever_model = ui.SimpleFloatModel(2.0)
        self._drop_length_model = ui.SimpleFloatModel(36.0)
        self._rod_diameter_model = ui.SimpleFloatModel(0.5)
        
        self._status_model = ui.SimpleStringModel("Ready")
        self._gauge_combo = None
        
        # Link width to span
        self._width_model.add_value_changed_fn(self._on_width_changed)

        self._build_ui()

    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Configure Trapeze Hanger", style={"font_size": 18})
                ui.Separator(height=5)

                # --- Input Parameters ---
                self._build_row("Duct/Pipe Width (in)", self._width_model)
                self._build_row("Span (L) (in)", self._span_model)
                self._build_row("Cantilever (C) (in)", self._cantilever_model)
                self._build_row("Drop Length (Y) (in)", self._drop_length_model)
                self._build_row("Rod Diameter (in)", self._rod_diameter_model)
                
                with ui.HStack(height=24):
                    ui.Label("Strut Gauge", width=150, style={"color": 0xFFAAAAAA})
                    self._gauge_combo = ui.ComboBox(
                        2, "16 Ga", "14 Ga", "12 Ga", "10 Ga", width=ui.Fraction(1)
                    )

                ui.Spacer(height=20)

                ui.Button("Create Trapeze", clicked_fn=self._on_create, height=40)
                ui.Label("", model=self._status_model, style={"color": 0xFF888888})
                
    def _build_row(self, label, model):
        with ui.HStack(height=24):
            ui.Label(label, width=150, style={"color": 0xFFAAAAAA})
            ui.FloatDrag(model=model, min=0.0, max=1000.0, step=0.125)

    def _on_width_changed(self, model):
        # Auto-update span: Width + 4" (2" each side clearance)
        width = model.as_float
        current_span = self._span_model.as_float
        # Only auto-update if it seems like we are in a default state or user wants it?
        # Let's just update it for convenience as per spec "Length = Pipe/Duct Width + 4""
        # Wait, Strut Length = Width + 4".
        # Span = Width + Clearance?
        # Spec: "Span (L) Distance between center of rods".
        # Usually rods are slightly wider than the duct.
        # Let's say Rod Spacing = Width + 2".
        self._span_model.set_value(width + 4.0) # Matches spec "Length = Width + 4" if rods are at ends?
        # No, Strut Length = Span + 2*Cantilever.
        # If Strut Length = Width + 4, and Cantilever = 2 (default), then Span = Width.
        # This means rods are tight against the duct.
        # Let's set Span = Width + 4.

    def _on_create(self):
        span = self._span_model.as_float
        cantilever = self._cantilever_model.as_float
        drop_length = self._drop_length_model.as_float
        rod_diameter = self._rod_diameter_model.as_float
        
        gauges = ["16 Ga", "14 Ga", "12 Ga", "10 Ga"]
        gauge_idx = self._gauge_combo.model.get_item_value_model().as_int
        gauge = gauges[gauge_idx]

        stage = omni.usd.get_context().get_stage()
        usd_utils.setup_stage_units(stage)

        # Unique Path
        base_path = "/World/Trapeze"
        path = base_path
        counter = 1
        while stage.GetPrimAtPath(path):
            path = f"{base_path}_{counter}"
            counter += 1

        self._status_model.set_value(f"Generating Trapeze at {path}...")

        result = Trapeze.create(
            stage, path,
            span=span,
            cantilever=cantilever,
            drop_length=drop_length,
            rod_diameter=rod_diameter,
            strut_gauge=gauge
        )

        if result:
            self._status_model.set_value(f"Created: {path}")
            omni.usd.get_context().get_selection().set_selected_prim_paths([path], True)
        else:
            self._status_model.set_value("Error generating geometry")
