"""Fan Design Window — parametric UI for the physics-first fan solver pipeline.

Exposes Steps 1-6 (classify → aero → volute → structural → acoustic → geometry)
through a single scrollable form. Engineers enter CFM + pressure, optionally
classify first, then generate a complete fan assembly.
"""

import omni.ui as ui
import omni.usd


# ---------------------------------------------------------------------------
# ComboBox helpers (same pattern as duct_window)
# ---------------------------------------------------------------------------

class _ListItem(ui.AbstractItem):
    def __init__(self, text):
        super().__init__()
        self.model = ui.SimpleStringModel(text)


class _ListItemModel(ui.AbstractItemModel):
    def __init__(self, items):
        super().__init__()
        self._items = [_ListItem(t) for t in items]
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


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

class FanDesignWindow(ui.Window):

    WINDOW_TITLE = "Fan Design"
    WINDOW_WIDTH = 400
    WINDOW_HEIGHT = 700

    def __init__(self):
        super().__init__(self.WINDOW_TITLE, width=self.WINDOW_WIDTH, height=self.WINDOW_HEIGHT)

        # --- Input models ---
        self._cfm_model = ui.SimpleFloatModel(5000.0)
        self._pressure_model = ui.SimpleFloatModel(4.0)
        self._rpm_model = ui.SimpleFloatModel(0.0)
        self._altitude_model = ui.SimpleFloatModel(0.0)
        self._temperature_model = ui.SimpleFloatModel(70.0)

        # Unit system: 0=US, 1=SI
        self._unit_items = ["US (CFM / in.WG)", "SI (m\u00b3/s / Pa)"]
        self._unit_model = _ListItemModel(self._unit_items)

        # Discharge direction: 0=Right, 1=Left, 2=Top
        self._discharge_items = ["Right", "Left", "Top"]
        self._discharge_model = _ListItemModel(self._discharge_items)

        # --- State ---
        self._editing_prim_path = None
        self._classification = None  # cached after Classify

        # --- UI refs (assigned during build) ---
        self._classify_summary = None
        self._results_summary = None
        self._status_label = None
        self._create_button = None
        self._warning_label = None

        self._build_ui()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        with self.frame:
            with ui.ScrollingFrame():
                with ui.VStack(height=0, spacing=8, padding=15):

                    # === DESIGN POINT ===
                    ui.Label("Design Point", style={"font_size": 18})
                    ui.Label("Enter performance requirements", style={"color": 0xFF888888, "font_size": 12})

                    with ui.HStack(height=22):
                        ui.Label("Flow Rate:", width=110)
                        ui.FloatDrag(model=self._cfm_model, min=50.0, max=500000.0, step=100)
                        self._flow_unit_label = ui.Label("CFM", width=50, style={"color": 0xFF888888})

                    with ui.HStack(height=22):
                        ui.Label("Total Pressure:", width=110)
                        ui.FloatDrag(model=self._pressure_model, min=0.1, max=80.0, step=0.1)
                        self._pressure_unit_label = ui.Label("in.WG", width=50, style={"color": 0xFF888888})

                    with ui.HStack(height=22):
                        ui.Label("Unit System:", width=110)
                        ui.ComboBox(self._unit_model)

                    self._unit_model.get_item_value_model(None, 0).add_value_changed_fn(
                        lambda m: self._on_unit_changed(m.as_int)
                    )

                    with ui.HStack(height=22):
                        ui.Label("RPM:", width=110)
                        ui.FloatDrag(model=self._rpm_model, min=0.0, max=10000.0, step=10)
                        ui.Label("(0 = auto)", width=60, style={"color": 0xFF888888})

                    # === ADVANCED ===
                    with ui.CollapsableFrame("Advanced", collapsed=True):
                        with ui.VStack(spacing=4):
                            with ui.HStack(height=22):
                                ui.Label("Altitude:", width=110)
                                ui.FloatDrag(model=self._altitude_model, min=0.0, max=15000.0, step=100)
                                ui.Label("ft", width=30, style={"color": 0xFF888888})
                            with ui.HStack(height=22):
                                ui.Label("Temperature:", width=110)
                                ui.FloatDrag(model=self._temperature_model, min=-40.0, max=500.0, step=1)
                                ui.Label("\u00b0F", width=30, style={"color": 0xFF888888})

                    ui.Spacer(height=5)

                    # === CLASSIFY BUTTON ===
                    ui.Button("Classify", clicked_fn=self._on_classify, height=30,
                              style={"background_color": 0xFF2D5A27})

                    # === CLASSIFICATION SUMMARY (hidden until classify runs) ===
                    self._classify_summary = ui.VStack(spacing=2, visible=False)
                    with self._classify_summary:
                        ui.Label("Classification", style={"font_size": 16})
                        self._cls_type_label = ui.Label("", style={"color": 0xFF00FF88})
                        self._cls_diameter_label = ui.Label("", style={"color": 0xFF00FF88})
                        self._cls_efficiency_label = ui.Label("", style={"color": 0xFF00FF88})
                        self._cls_power_label = ui.Label("", style={"color": 0xFF00FF88})
                        self._cls_rpm_label = ui.Label("", style={"color": 0xFF00FF88})
                        self._cls_region_label = ui.Label("", style={"color": 0xFF00FF88})
                        self._warning_label = ui.Label("", style={"color": 0xFFFF4444}, visible=False)

                    ui.Spacer(height=5)
                    ui.Separator(height=2)
                    ui.Spacer(height=5)

                    # === DISCHARGE DIRECTION ===
                    with ui.HStack(height=22):
                        ui.Label("Discharge:", width=110)
                        ui.ComboBox(self._discharge_model)

                    ui.Spacer(height=5)

                    # === LOAD / CLEAR ===
                    with ui.HStack(height=35, spacing=5):
                        ui.Button("Load Selected", clicked_fn=self._on_load_selected, height=35)
                        ui.Button("Clear", clicked_fn=self._on_clear, height=35)

                    ui.Spacer(height=5)

                    # === GENERATE BUTTON ===
                    self._create_button = ui.Button("Generate Fan", clicked_fn=self._on_generate, height=40)

                    # === STATUS ===
                    self._status_label = ui.Label("", style={"color": 0xFF888888})

                    # === RESULTS SUMMARY (hidden until generation completes) ===
                    self._results_summary = ui.VStack(spacing=2, visible=False)
                    with self._results_summary:
                        ui.Separator(height=2)
                        ui.Label("Results", style={"font_size": 16})
                        self._res_type_label = ui.Label("", style={"color": 0xFF00FF88})
                        self._res_diameter_label = ui.Label("", style={"color": 0xFF00FF88})
                        self._res_rpm_label = ui.Label("", style={"color": 0xFF00FF88})
                        self._res_power_label = ui.Label("", style={"color": 0xFF00FF88})
                        self._res_noise_label = ui.Label("", style={"color": 0xFF00FF88})

                    ui.Spacer(height=10)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _get_unit_system(self):
        from company.twin.solvers.fan_classifier import UnitSystem
        idx = self._unit_model.get_item_value_model(None, 0).as_int
        return UnitSystem.SI if idx == 1 else UnitSystem.US

    def _get_discharge(self):
        idx = self._discharge_model.get_item_value_model(None, 0).as_int
        return self._discharge_items[idx].lower()

    def _on_unit_changed(self, index):
        if index == 1:  # SI
            self._flow_unit_label.text = "m\u00b3/s"
            self._pressure_unit_label.text = "Pa"
        else:
            self._flow_unit_label.text = "CFM"
            self._pressure_unit_label.text = "in.WG"

    def _make_design_point(self):
        from company.twin.solvers.fan_classifier import FanDesignPoint
        rpm_val = self._rpm_model.as_float
        return FanDesignPoint(
            flow_rate=self._cfm_model.as_float,
            total_pressure=self._pressure_model.as_float,
            units=self._get_unit_system(),
            rpm=rpm_val if rpm_val > 0 else None,
            altitude_ft=self._altitude_model.as_float,
            temperature_f=self._temperature_model.as_float,
        )

    # -----------------------------------------------------------------------
    # Classify (Step 1 only)
    # -----------------------------------------------------------------------

    def _on_classify(self):
        try:
            from company.twin.solvers import FanClassificationSolver
            from company.twin.solvers.fan_classifier import OperatingRegion

            dp = self._make_design_point()
            self._status_label.text = "Classifying..."

            result = FanClassificationSolver().solve({'design_point': dp})
            cls = result['metadata']['classification']
            self._classification = cls

            # Populate summary
            fan_name = cls.fan_type.name.replace("_", " ").title()
            self._cls_type_label.text = f"Type: {fan_name}"
            self._cls_diameter_label.text = f"Impeller: {cls.impeller_diameter_in:.1f}\" diameter"
            self._cls_efficiency_label.text = f"Efficiency: {cls.efficiency.total:.1%}"
            self._cls_power_label.text = f"Shaft Power: {cls.shaft_power_hp:.2f} HP ({cls.shaft_power_kw:.2f} kW)"
            rpm_lo, rpm_hi = cls.recommended_rpm_range
            self._cls_rpm_label.text = f"RPM Range: {rpm_lo:.0f} - {rpm_hi:.0f}"
            self._cls_region_label.text = f"Operating Region: {cls.operating_region.name}"

            # Warning for unstable regions
            if cls.operating_region in (OperatingRegion.NEAR_STALL, OperatingRegion.UNSTABLE):
                self._warning_label.text = f"WARNING: {cls.operating_region.name} — consider adjusting RPM or design point"
                self._warning_label.visible = True
            else:
                self._warning_label.visible = False

            self._classify_summary.visible = True
            self._status_label.text = "Classification complete"

        except ValueError as e:
            self._status_label.text = f"Error: {e}"
        except Exception as e:
            self._status_label.text = f"Error: {e}"
            import traceback
            traceback.print_exc()

    # -----------------------------------------------------------------------
    # Generate (Steps 1-6)
    # -----------------------------------------------------------------------

    def _on_generate(self):
        try:
            from company.twin.solvers import (
                FanClassificationSolver,
                ImpellerAeroSolver,
                VoluteSolver,
                FanStructuralSolver,
                FanAcousticSolver,
            )
            from company.twin.tools.objects.mep.fan_assembly import FanAssembly

            stage = omni.usd.get_context().get_stage()
            if not stage:
                self._status_label.text = "Error: No USD stage open"
                return

            dp = self._make_design_point()
            discharge = self._get_discharge()

            # Step 1: Classify
            self._status_label.text = "Step 1/6: Classifying..."
            cls_result = FanClassificationSolver().solve({'design_point': dp})
            cls = cls_result['metadata']['classification']

            # Step 2: Impeller aero
            self._status_label.text = "Step 2/6: Impeller aerodynamics..."
            aero_result = ImpellerAeroSolver().solve({'classification': cls})
            aero = aero_result['metadata']['aero']

            # Step 3: Volute
            self._status_label.text = "Step 3/6: Volute sizing..."
            volute_result = VoluteSolver().solve({'aero': aero})
            volute = volute_result['metadata']['volute']

            # Step 4: Structural
            self._status_label.text = "Step 4/6: Structural analysis..."
            struct_result = FanStructuralSolver().solve({'volute': volute})
            struct = struct_result['metadata']['structural']

            # Step 5: Acoustics
            self._status_label.text = "Step 5/6: Acoustic analysis..."
            acou_result = FanAcousticSolver().solve({'structural': struct})
            acou = acou_result['metadata']['acoustic']

            # Step 6: Generate geometry
            self._status_label.text = "Step 6/6: Generating geometry..."

            if self._editing_prim_path:
                path = self._editing_prim_path
                # Remove old prim before regenerating
                if stage.GetPrimAtPath(path):
                    stage.RemovePrim(path)
            else:
                path_root = "/World/Fan"
                path = path_root
                idx = 1
                while stage.GetPrimAtPath(path):
                    path = f"{path_root}_{idx}"
                    idx += 1

            FanAssembly.create(stage, path, acou, discharge=discharge)

            # Store metadata for Load Selected regeneration
            prim = stage.GetPrimAtPath(path)
            if prim:
                cfm_us, pressure_us = dp.to_us()
                prim.SetCustomDataByKey("generatorType", "fan_assembly")
                prim.SetCustomDataByKey("cfm", cfm_us)
                prim.SetCustomDataByKey("total_pressure", pressure_us)
                prim.SetCustomDataByKey("rpm", dp.rpm if dp.rpm else 0.0)
                prim.SetCustomDataByKey("discharge", discharge)
                prim.SetCustomDataByKey("unit_system", "SI" if dp.units.name == "SI" else "US")
                prim.SetCustomDataByKey("altitude_ft", dp.altitude_ft)
                prim.SetCustomDataByKey("temperature_f", dp.temperature_f)

            # Populate results summary
            fan_name = cls.fan_type.name.replace("_", " ").title()
            self._res_type_label.text = f"Type: {fan_name}"
            self._res_diameter_label.text = f"Impeller: {cls.impeller_diameter_in:.1f}\" diameter"
            rpm_lo, rpm_hi = cls.recommended_rpm_range
            self._res_rpm_label.text = f"RPM: {(rpm_lo + rpm_hi) / 2:.0f}"
            self._res_power_label.text = f"Power: {cls.shaft_power_hp:.2f} HP"
            self._res_noise_label.text = f"Noise: {acou.overall_spl_dba:.1f} dBA"

            self._results_summary.visible = True
            self._status_label.text = f"Fan created at {path}"
            print(f"[FanDesign] Generated fan assembly at {path}")

        except ValueError as e:
            self._status_label.text = f"Error: {e}"
        except Exception as e:
            self._status_label.text = f"Error: {e}"
            import traceback
            traceback.print_exc()

    # -----------------------------------------------------------------------
    # Load Selected / Clear
    # -----------------------------------------------------------------------

    def _on_load_selected(self):
        try:
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            if not stage:
                self._status_label.text = "Error: No USD stage open"
                return

            selected = ctx.get_selection().get_selected_prim_paths()
            if not selected:
                self._status_label.text = "No prim selected"
                return

            prim = stage.GetPrimAtPath(selected[0])
            if not prim:
                self._status_label.text = "Invalid selection"
                return

            cd = prim.GetCustomData()
            if cd.get("generatorType") != "fan_assembly":
                self._status_label.text = "Selected prim is not a fan assembly"
                return

            # Populate fields from metadata
            self._cfm_model.as_float = float(cd.get("cfm", 5000.0))
            self._pressure_model.as_float = float(cd.get("total_pressure", 4.0))
            self._rpm_model.as_float = float(cd.get("rpm", 0.0))
            self._altitude_model.as_float = float(cd.get("altitude_ft", 0.0))
            self._temperature_model.as_float = float(cd.get("temperature_f", 70.0))

            # Unit system
            unit_str = cd.get("unit_system", "US")
            self._unit_model.get_item_value_model(None, 0).as_int = 1 if unit_str == "SI" else 0
            self._on_unit_changed(1 if unit_str == "SI" else 0)

            # Discharge direction
            discharge_str = cd.get("discharge", "right")
            discharge_map = {"right": 0, "left": 1, "top": 2}
            self._discharge_model.get_item_value_model(None, 0).as_int = discharge_map.get(discharge_str, 0)

            self._editing_prim_path = selected[0]
            if self._create_button:
                self._create_button.text = "Update Fan"
            self._status_label.text = f"Loaded {prim.GetName()}"

        except Exception as e:
            self._status_label.text = f"Error: {e}"
            import traceback
            traceback.print_exc()

    def _on_clear(self):
        self._editing_prim_path = None
        self._classification = None
        if self._create_button:
            self._create_button.text = "Generate Fan"
        if self._classify_summary:
            self._classify_summary.visible = False
        if self._results_summary:
            self._results_summary.visible = False
        if self._warning_label:
            self._warning_label.visible = False
        self._status_label.text = "Ready to create new fan"

    def destroy(self):
        super().destroy()
