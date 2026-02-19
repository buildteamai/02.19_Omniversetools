import omni.ui as ui
import omni.usd
from pxr import Usd, UsdGeom, Gf
import math

class MeasureToolWindow(ui.Window):
    """
    Simple tool to measure distance between two selected prims.
    """
    def __init__(self, title="Measure Distance", **kwargs):
        super().__init__(title, width=300, height=200, **kwargs)
        self.frame.set_build_fn(self._build_ui)
        
        # Subscribe to selection updates via Stage Event Stream
        self._stage_event_sub = omni.usd.get_context().get_stage_event_stream().create_subscription_to_pop(
            self._on_stage_event, name="MeasureTool Stage Events"
        )
        
    def _on_stage_event(self, event):
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            self._on_selection_changed(event)

        
    def _build_ui(self):
        with ui.ScrollingFrame():
            with ui.VStack(spacing=10, padding=15):
                ui.Label("Distance Measure", style={"font_size": 18, "color": 0xFF00AAFF})
                ui.Label("Select exactly 2 objects to measure.", style={"color": 0xFF888888, "font_size": 12})
                
                ui.Separator(height=10)
                
                with ui.HStack(height=30):
                    ui.Label("Distance:", width=80, style={"font_size": 14})
                    self.lbl_dist = ui.Label("---", style={"font_size": 18, "color": 0xFFFFFFFF})
                
                with ui.HStack(height=20):
                    ui.Label("In Feet:", width=80)
                    self.lbl_feet = ui.Label("---")
                    
                with ui.HStack(height=20):
                    ui.Label("In Meters:", width=80)
                    self.lbl_metric = ui.Label("---")

                ui.Spacer(height=10)
                ui.Button("Force Refresh", clicked_fn=lambda: self._on_selection_changed(None))

    def _on_selection_changed(self, event):
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        if not stage: return
        
        paths = ctx.get_selection().get_selected_prim_paths()
        if len(paths) != 2:
            self.lbl_dist.text = "Select 2 items"
            self.lbl_feet.text = "---"
            self.lbl_metric.text = "---"
            return
            
        p1 = stage.GetPrimAtPath(paths[0])
        p2 = stage.GetPrimAtPath(paths[1])
        
        if not p1 or not p2: return
        
        # Get World Transforms
        cache = UsdGeom.XformCache()
        t1 = cache.GetLocalToWorldTransform(p1).ExtractTranslation()
        t2 = cache.GetLocalToWorldTransform(p2).ExtractTranslation()
        
        # Distance
        dist = (t1 - t2).GetLength()
        
        # Formatting based on stage units
        mpu = UsdGeom.GetStageMetersPerUnit(stage)
        units = "units"
        
        # Guess units
        if abs(mpu - 0.01) < 0.0001: units = "cm"
        elif abs(mpu - 0.0254) < 0.0001: units = "in"
        elif abs(mpu - 1.0) < 0.0001: units = "m"
        
        self.lbl_dist.text = f"{dist:.4f} {units}"
        
        # Convert
        dist_meters = dist * mpu
        dist_feet = dist_meters * 3.28084
        
        self.lbl_feet.text = f"{dist_feet:.4f} ft"
        self.lbl_metric.text = f"{dist_meters:.4f} m"
        
    def destroy(self):
        self._stage_event_sub = None
        super().destroy()
