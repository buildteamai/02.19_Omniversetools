import omni.ui as ui
import omni.usd
from ..objects.stair import Stair
from ..utils import usd_utils

class StairWindow(ui.Window):
    def __init__(self, title="Create Industrial Stair", **kwargs):
        print(f"[StairWindow] Initializing {title}...")
        super().__init__(title, width=400, height=500, dockPreference=ui.DockPreference.LEFT_BOTTOM, **kwargs)
        
        self._total_rise_model = ui.SimpleFloatModel(120.0)
        self._width_model = ui.SimpleFloatModel(36.0)
        self._run_model = ui.SimpleFloatModel(10.0)
        self._landing_model = ui.SimpleFloatModel(30.0)
        
        self._status_model = ui.SimpleStringModel("Ready")
        
        print("[StairWindow] Models initialized. Building UI...")
        self._build_ui()
        
    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Industrial Stair Generator", style={"font_size": 18})
                ui.Label("OSHA 1910.25 Compliant", style={"color": 0xFF888888, "font_size": 12})
                
                ui.Separator(height=10)
                
                # Key Parameters
                self._build_row("Total Vertical Rise (in)", self._total_rise_model)
                self._build_row("Stair Width (in)", self._width_model)
                self._build_row("Tread Run (in)", self._run_model)
                self._build_row("Available Landing (in)", self._landing_model)
                
                ui.Separator(height=10)
                
                # Calculated Info / Feedback (Could be dynamic, for now static on create)
                # But let's verify inputs
                
                ui.Button("Create Stair", clicked_fn=self._on_create, height=40)
                
                ui.Separator(height=10)
                ui.Label("Status:", style={"color": 0xFFAAAAAA})
                ui.Label("", model=self._status_model, style={"color": 0xFFEEEEEE})
                
    def _build_row(self, label, model):
        with ui.HStack(height=24):
            ui.Label(label, width=150, style={"color": 0xFFAAAAAA})
            ui.FloatDrag(model=model, min=1.0, max=10000.0, step=1.0)

    def _on_create(self):
        rise = self._total_rise_model.as_float
        width = self._width_model.as_float
        run = self._run_model.as_float
        landing = self._landing_model.as_float
        
        # Validation
        if rise < 10:
            self._status_model.set_value("Error: Rise too small")
            return
            
        stage = omni.usd.get_context().get_stage()
        usd_utils.setup_stage_units(stage)
        
        # Unique Path
        base_path = "/World/Stair"
        path = base_path
        counter = 1
        while stage.GetPrimAtPath(path):
            path = f"{base_path}_{counter}"
            counter += 1
            
        self._status_model.set_value(f"Generating at {path}...")
        
        try:
            result = Stair.create(
                stage, 
                path,
                total_rise=rise,
                width=width,
                run=run,
                landing_depth=landing
            )
            
            if result:
                self._status_model.set_value(f"Success: Created {path}")
            else:
                self._status_model.set_value("Error: Generation Failed")
                
        except Exception as e:
            self._status_model.set_value(f"Exception: {str(e)}")
