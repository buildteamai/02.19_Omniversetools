# OHPF Configurator Window (PENDING UPDATE)
import omni.ui as ui

class OHPFWindow(ui.Window):
    def __init__(self, title="OHPF Conveyor", **kwargs):
        super().__init__(title, width=300, height=200, **kwargs)
        self.frame.set_build_fn(self._build_ui)
        
    def _build_ui(self):
        with ui.ScrollingFrame():
            with ui.VStack(height=0, spacing=10, padding=20):
                ui.Label("OHPF Configurator", style={"font_size": 18, "color": 0xFF00AAFF})
                ui.Label("Logic removed pending update.", style={"color": 0xFF888888})
