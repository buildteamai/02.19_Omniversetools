"""
Fan Controls — real-time blade rotation driven by a discharge-velocity slider.

Reads design-point RPM and discharge velocity from prim metadata, computes
the linear rpm-per-ft/s ratio, and spins Blades + ImpellerDisks prims each
frame via a RotateZ xform op.
"""

import omni.ui as ui
import omni.usd
import omni.kit.app
from pxr import UsdGeom


class FanControlsWindow(ui.Window):

    WINDOW_TITLE = "Fan Controls"
    WINDOW_WIDTH = 340
    WINDOW_HEIGHT = 370

    def __init__(self):
        super().__init__(self.WINDOW_TITLE, width=self.WINDOW_WIDTH, height=self.WINDOW_HEIGHT)

        # State
        self._fan_root_path = None
        self._design_rpm = 0.0
        self._design_velocity_fts = 0.0
        self._rpm_per_fts = 0.0
        self._cumulative_angle = 0.0
        self._running = False
        self._update_sub = None

        # Airflow visualization
        self._airflow_viz = None
        self._airflow_model = ui.SimpleBoolModel(False)

        # UI models / labels (set in _build_ui)
        self._velocity_model = ui.SimpleFloatModel(0.0)
        self._selected_label = None
        self._rpm_label = None
        self._vp_label = None
        self._design_label = None
        self._slider = None

        self._build_ui()

        # Subscribe to stage selection changes
        usd_ctx = omni.usd.get_context()
        self._sel_sub = usd_ctx.get_stage_event_stream().create_subscription_to_pop(
            self._on_stage_event
        )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=6, style={"margin": 8}):
                # Selected fan
                with ui.HStack(height=20):
                    ui.Label("Selected Fan:", width=100)
                    self._selected_label = ui.Label("(none)", style={"color": 0xFFAAAAFF})

                ui.Spacer(height=4)

                # Velocity slider
                ui.Label("Discharge Velocity (ft/s)")
                with ui.HStack(height=24, spacing=4):
                    self._slider = ui.FloatSlider(
                        model=self._velocity_model,
                        min=0.0,
                        max=100.0,
                        step=0.1,
                    )
                self._velocity_model.add_value_changed_fn(self._on_velocity_changed)

                ui.Spacer(height=4)

                # Computed readouts
                ui.Label("Computed", style={"color": 0xFF888888, "font_size": 12})
                ui.Separator(height=2)
                with ui.VStack(spacing=4):
                    with ui.HStack(height=18):
                        ui.Label("RPM:", width=140)
                        self._rpm_label = ui.Label("—")
                    with ui.HStack(height=18):
                        ui.Label("Velocity Pressure:", width=140)
                        self._vp_label = ui.Label("—")
                    with ui.HStack(height=18):
                        ui.Label("Design Point:", width=140)
                        self._design_label = ui.Label("—")

                ui.Spacer(height=8)

                # Start / Stop
                with ui.HStack(height=28, spacing=8):
                    ui.Button("Start", clicked_fn=self._start, width=80)
                    ui.Button("Stop", clicked_fn=self._stop, width=80)

                ui.Spacer(height=4)

                # Visualization
                ui.Label("Visualization", style={"color": 0xFF888888, "font_size": 12})
                ui.Separator(height=2)
                with ui.HStack(height=22, spacing=4):
                    cb = ui.CheckBox(model=self._airflow_model, width=20)
                    ui.Label("Show Airflow")
                self._airflow_model.add_value_changed_fn(self._on_airflow_toggled)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_stage_event(self, event):
        import carb
        if event.type != int(omni.usd.StageEventType.SELECTION_CHANGED):
            return
        self._try_select_fan()

    def _try_select_fan(self):
        usd_ctx = omni.usd.get_context()
        sel = usd_ctx.get_selection().get_selected_prim_paths()
        if not sel:
            return

        stage = usd_ctx.get_stage()
        if not stage:
            return

        for prim_path in sel:
            prim = stage.GetPrimAtPath(prim_path)
            if not prim.IsValid():
                continue
            # Check the prim itself and its parent
            for candidate in (prim, prim.GetParent()):
                if not candidate or not candidate.IsValid():
                    continue
                gen = candidate.GetCustomDataByKey("twin:generator")
                if gen == "fan_assembly":
                    self._load_fan(candidate)
                    return

        # Nothing matched
        self._clear_fan()

    def _load_fan(self, prim):
        # Detach existing airflow viz on fan change
        if self._airflow_viz and self._airflow_viz.is_attached:
            self._airflow_viz.detach()
        self._airflow_model.set_value(False)

        self._fan_root_path = str(prim.GetPath())
        self._design_rpm = float(prim.GetCustomDataByKey("twin:rpm") or 0.0)
        self._design_velocity_fts = float(prim.GetCustomDataByKey("twin:discharge_velocity_fts") or 0.0)

        if self._design_velocity_fts > 0:
            self._rpm_per_fts = self._design_rpm / self._design_velocity_fts
        else:
            self._rpm_per_fts = 0.0

        # Set slider range to 0 – 1.5× design velocity
        max_v = self._design_velocity_fts * 1.5 if self._design_velocity_fts > 0 else 100.0
        self._slider.min = 0.0
        self._slider.max = max_v

        # Default slider to design velocity
        self._velocity_model.set_value(self._design_velocity_fts)

        self._selected_label.text = self._fan_root_path
        self._design_label.text = f"{self._design_velocity_fts:,.1f} ft/s  |  {self._design_rpm:,.0f} RPM"
        self._on_velocity_changed(self._velocity_model)

    def _clear_fan(self):
        # Detach airflow viz
        if self._airflow_viz and self._airflow_viz.is_attached:
            self._airflow_viz.detach()
        self._airflow_model.set_value(False)

        self._fan_root_path = None
        self._design_rpm = 0.0
        self._design_velocity_fts = 0.0
        self._rpm_per_fts = 0.0
        self._selected_label.text = "(none)"
        self._rpm_label.text = "—"
        self._vp_label.text = "—"
        self._design_label.text = "—"

    # ------------------------------------------------------------------
    # Airflow visualization
    # ------------------------------------------------------------------

    def _on_airflow_toggled(self, model):
        checked = model.as_bool
        if checked:
            if not self._fan_root_path:
                self._airflow_model.set_value(False)
                return
            from ..utils.fan_airflow import FanAirflowVisualizer
            if self._airflow_viz is None:
                self._airflow_viz = FanAirflowVisualizer()
            stage = omni.usd.get_context().get_stage()
            prim = stage.GetPrimAtPath(self._fan_root_path)
            if prim.IsValid():
                self._airflow_viz.attach(stage, self._fan_root_path, prim)
        else:
            if self._airflow_viz and self._airflow_viz.is_attached:
                self._airflow_viz.detach()

    # ------------------------------------------------------------------
    # Slider callback
    # ------------------------------------------------------------------

    def _on_velocity_changed(self, model):
        v = model.as_float
        rpm = v * self._rpm_per_fts
        vp = (v / 4005.0) ** 2
        self._rpm_label.text = f"{rpm:,.0f}"
        self._vp_label.text = f"{vp:.4f} in.WG"

    # ------------------------------------------------------------------
    # Start / Stop animation
    # ------------------------------------------------------------------

    def _start(self):
        if self._running or not self._fan_root_path:
            return
        self._running = True
        app = omni.kit.app.get_app()
        self._update_sub = app.get_update_event_stream().create_subscription_to_pop(
            self._on_update
        )

    def _stop(self):
        self._running = False
        if self._update_sub:
            self._update_sub = None
        self._cumulative_angle = 0.0
        # Reset blade rotation to 0
        self._set_blade_rotation(0.0)

    # ------------------------------------------------------------------
    # Per-frame tick
    # ------------------------------------------------------------------

    def _on_update(self, event):
        if not self._running or not self._fan_root_path:
            return

        dt = event.payload.get("dt", 1.0 / 60.0)
        v = self._velocity_model.as_float
        rpm = v * self._rpm_per_fts
        deg_per_sec = (rpm / 60.0) * 360.0
        self._cumulative_angle += deg_per_sec * dt

        self._set_blade_rotation(self._cumulative_angle)

        # Update airflow particles
        if self._airflow_viz and self._airflow_viz.is_attached:
            v_ratio = v / self._design_velocity_fts if self._design_velocity_fts > 0 else 0.0
            self._airflow_viz.update(dt, v_ratio)

    def _set_blade_rotation(self, angle_deg: float):
        stage = omni.usd.get_context().get_stage()
        if not stage:
            return
        for child_name in ("Blades", "ImpellerDisks"):
            prim = stage.GetPrimAtPath(f"{self._fan_root_path}/{child_name}")
            if not prim.IsValid():
                continue
            xf = UsdGeom.Xformable(prim)
            ops = xf.GetOrderedXformOps()
            rot_op = None
            for op in ops:
                if op.GetOpType() == UsdGeom.XformOp.TypeRotateZ:
                    rot_op = op
                    break
            if rot_op is None:
                # Append RotateZ after Translate — in USD column-vector
                # convention the last op applies first, so geometry is
                # rotated locally then translated into position.
                rot_op = xf.AddRotateZOp()
            rot_op.Set(float(angle_deg))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def destroy(self):
        self._stop()
        if self._airflow_viz and self._airflow_viz.is_attached:
            self._airflow_viz.detach()
        self._sel_sub = None
        super().destroy()
