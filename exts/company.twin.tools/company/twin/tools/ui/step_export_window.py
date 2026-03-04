import omni.ui as ui
import omni.usd
import os
import threading
from ..exporters.step_exporter import StepExporter


class StepExportWindow(ui.Window):
    def __init__(self, title="Export STEP File", **kwargs):
        super().__init__(title, width=520, height=320, **kwargs)
        self._exporter = StepExporter()
        self._path_model = ui.SimpleStringModel("")
        self._status_model = ui.SimpleStringModel("Ready")
        self._scope_index = 0  # 0 = Whole Scene, 1 = Selected Prims
        self._build_ui()

    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=8, padding=15):
                ui.Label("Export to STEP (ISO 10303)", style={"font_size": 18, "color": 0xFFDDDDDD})
                ui.Separator(height=5)

                # Scope selection
                with ui.HStack(height=24):
                    ui.Label("Scope:", width=100, style={"color": 0xFFAAAAAA})
                    scope_collection = ui.RadioCollection()
                    ui.RadioButton(
                        radio_collection=scope_collection,
                        text="Whole Scene",
                        width=130,
                    )
                    ui.RadioButton(
                        radio_collection=scope_collection,
                        text="Selected Prims",
                        width=130,
                    )
                    self._scope_collection = scope_collection

                ui.Spacer(height=2)

                # Output path
                with ui.HStack(height=24):
                    ui.Label("Output Path:", width=100, style={"color": 0xFFAAAAAA})
                    ui.StringField(model=self._path_model, style={"color": 0xFFEEEEEE})

                ui.Label(
                    "Enter absolute path for the .step output file.",
                    style={"font_size": 12, "color": 0xFF888888},
                )

                ui.Spacer(height=8)

                # Info box
                with ui.CollapsableFrame("How it works", collapsed=True, height=0):
                    with ui.VStack(spacing=4, padding=8):
                        ui.Label(
                            "Prims with generator metadata (wide_flange, channel, hss_tube, pyramid) "
                            "are regenerated as exact B-Rep solids.",
                            style={"font_size": 12, "color": 0xFF999999},
                            word_wrap=True,
                        )
                        ui.Label(
                            "All other meshes are reconstructed from triangulated geometry "
                            "(faithful to mesh but not analytically exact).",
                            style={"font_size": 12, "color": 0xFF999999},
                            word_wrap=True,
                        )
                        ui.Label(
                            "Units are converted to millimeters (STEP standard).",
                            style={"font_size": 12, "color": 0xFF999999},
                            word_wrap=True,
                        )

                ui.Spacer(height=4)

                # Export button
                self._export_btn = ui.Button(
                    "Export to STEP",
                    clicked_fn=self._on_export,
                    height=40,
                    style={"background_color": 0xFF2D6A4F, "font_size": 16},
                )

                # Status
                ui.Spacer(height=4)
                self._status_label = ui.Label(
                    model=self._status_model,
                    style={"color": 0xFFCCCCCC},
                    word_wrap=True,
                )

    def _on_export(self):
        output_path = self._path_model.as_string.strip().strip('"').strip("'")

        if not output_path:
            self._status_model.set_value("Please enter an output file path.")
            return

        # Ensure .step extension
        if not output_path.lower().endswith((".step", ".stp")):
            output_path += ".step"

        # Check output directory is writable
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.isdir(out_dir):
            self._status_model.set_value(f"Directory does not exist: {out_dir}")
            return

        stage = omni.usd.get_context().get_stage()
        if not stage:
            self._status_model.set_value("No USD stage is open.")
            return

        # Determine scope
        selected_paths = None
        scope_idx = self._scope_collection.model.as_int
        if scope_idx == 1:
            sel = omni.usd.get_context().get_selection()
            selected_paths = sel.get_selected_prim_paths() if sel else []
            if not selected_paths:
                self._status_model.set_value("No prims selected. Select prims in the viewport first.")
                return

        self._status_model.set_value("Exporting... this may take a moment for large scenes.")
        self._export_btn.enabled = False

        # Run export in a thread to avoid blocking the UI
        def _run():
            try:
                success = self._exporter.export(
                    stage=stage,
                    output_path=output_path,
                    selected_paths=selected_paths,
                )
                stats = self._exporter.get_stats()
                if success:
                    msg = (
                        f"Export complete: {output_path}\n"
                        f"({stats['regenerated']} regenerated, {stats['meshed']} from mesh, "
                        f"{stats['skipped']} skipped, {stats['errors']} errors)"
                    )
                else:
                    msg = f"Export failed. {stats['errors']} errors. Check console for details."
                self._status_model.set_value(msg)
            except Exception as e:
                self._status_model.set_value(f"Export error: {e}")
            finally:
                self._export_btn.enabled = True

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
