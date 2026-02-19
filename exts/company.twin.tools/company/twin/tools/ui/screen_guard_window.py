import omni.ui as ui
import omni.usd
from pxr import Sdf
from ..objects.screen_guard import ScreenGuard
from ..utils import usd_utils

class ScreenGuardWindow(ui.Window):
    def __init__(self, title="Safety Fence Configurator", **kwargs):
        super().__init__(title, width=400, height=500, **kwargs)

        self._length_options = ["4'", "5'", "8'", "10'"]
        self._length_values = [48.0, 60.0, 96.0, 120.0]
        
        self._corner_options = ["None", "Left", "Right"]
        self._finish_options = list(ScreenGuard.FINISHES.keys())

        # Model Init
        self._length_idx_model = ui.SimpleIntModel(2) # Default 8'
        self._height_model = ui.SimpleFloatModel(96.0)
        self._corner_idx_model = ui.SimpleIntModel(0)
        self._finish_idx_model = ui.SimpleIntModel(0) # Safety Yellow
        self._end_post_model = ui.SimpleBoolModel(True)
        
        self._status_model = ui.SimpleStringModel("Ready")

        self._build_ui()

    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Configure Safety Fence", style={"font_size": 18})
                ui.Separator(height=5)

                # --- Parameters ---
                self._build_dropdown_row("Length", self._length_idx_model, self._length_options)
                self._build_float_row("Height (in)", self._height_model)
                self._build_dropdown_row("Corner Type", self._corner_idx_model, self._corner_options)
                self._build_dropdown_row("Finish", self._finish_idx_model, self._finish_options)
                
                # Checkbox Row
                with ui.HStack(height=24):
                    ui.Label("Include End Post", width=120)
                    ui.CheckBox(model=self._end_post_model)

                ui.Spacer(height=20)

                ui.Button("Create Safety Fence", clicked_fn=self._on_create, height=40)
                ui.Label("", model=self._status_model, style={"color": 0xFF888888})

    def _build_float_row(self, label, model):
        with ui.HStack(height=24):
            ui.Label(label, width=120)
            ui.FloatDrag(model=model, min=12, max=240, step=1.0)

    def _build_dropdown_row(self, label, model, items):
        with ui.HStack(height=24):
            ui.Label(label, width=120)
            ui.ComboBox(model.as_int, *items).model.add_item_changed_fn(
                lambda m, i: model.set_value(m.get_item_value_model().as_int)
            )

    def _on_create(self):
        length_idx = self._length_idx_model.as_int
        length_val = self._length_values[length_idx]
        
        height_val = self._height_model.as_float
        
        corner_idx = self._corner_idx_model.as_int
        corner_val = self._corner_options[corner_idx]
        
        finish_idx = self._finish_idx_model.as_int
        finish_val = self._finish_options[finish_idx]
        
        include_end_post = self._end_post_model.as_bool
        
        self._status_model.as_string = f"Generating {finish_val} fence..."
        
        # Call Generator
        stage = omni.usd.get_context().get_stage()
        
        # Unique Path
        base_path = "/World/SafetyFence"
        path = base_path
        counter = 1
        while stage.GetPrimAtPath(path):
            path = f"{base_path}_{counter}"
            counter += 1
        
        prim = ScreenGuard.create(
            stage, 
            path, 
            length=length_val, 
            height=height_val, 
            corner_type=corner_val, 
            finish=finish_val,
            include_end_post=include_end_post
        )
        
        if prim:
            self._status_model.as_string = f"Created: {path}"
        else:
            self._status_model.as_string = "Error generating fence."
