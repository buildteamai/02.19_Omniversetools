import omni.ui as ui
import omni.usd
# from .fan_window_base import FanWindowBase # Optional, if we want to share base
from ..mechanical.fan import FanGenerator

class FanWindow(ui.Window):
    def __init__(self, title="Create Fan", **kwargs):
        super().__init__(title, width=400, height=300, **kwargs)
        self.frame.set_build_fn(self._build_ui)
        self._generator = FanGenerator()

    def _build_ui(self):
        with ui.ScrollingFrame():
            with ui.VStack(height=0, spacing=10, padding=20):
                ui.Label("Industrial Fan Generator", 
                        style={"font_size": 18, "color": 0xFF00AAFF})
                
                ui.Separator(height=10)

                with ui.HStack(height=24):
                    ui.Label("Root Path:", width=100)
                    self._root_path_field = ui.StringField()
                    self._root_path_field.model.set_value("/World/Mechanical/Fan_01")

                with ui.HStack(height=24):
                    ui.Label("Position (X, Y, Z):", width=100)
                    self._pos_x = ui.FloatDrag(min=-10000, max=10000)
                    self._pos_y = ui.FloatDrag(min=-10000, max=10000)
                    self._pos_z = ui.FloatDrag(min=-10000, max=10000)

                ui.Spacer(height=10)

                ui.Button("Create Fan", clicked_fn=self._on_create, height=40)
                
                ui.Spacer(height=10)
                self._status_label = ui.Label("", style={"color": 0xFF888888})

    def _on_create(self):
        stage = omni.usd.get_context().get_stage()
        if not stage:
            self._status_label.text = "Error: No stage open"
            return

        path = self._root_path_field.model.get_value_as_string()
        pos = (
            self._pos_x.model.get_value_as_float(),
            self._pos_y.model.get_value_as_float(),
            self._pos_z.model.get_value_as_float()
        )
        
        try:
            self._generator.create_fan(stage, path, position=pos)
            self._status_label.text = f"Created fan at {path}"
            print(f"[Fan] Created fan at {path}")
        except Exception as e:
            self._status_label.text = f"Error: {str(e)}"
            print(f"[Fan] Error: {e}")
