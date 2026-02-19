import omni.ui as ui
import os
from ..importers.step_importer import StepImporter

class StepImportWindow(ui.Window):
    def __init__(self, title="Import STEP File", **kwargs):
        super().__init__(title, width=500, height=200, **kwargs)
        self._importer = StepImporter()
        self._path_model = ui.SimpleStringModel("")
        self._status_model = ui.SimpleStringModel("Ready")
        self._build_ui()

    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=10, padding=15):
                # Header
                ui.Label("Import STEP File", style={"font_size": 18, "color": 0xFFDDDDDD})
                ui.Separator(height=5)
                ui.Spacer(height=5)

                # Input Path
                with ui.HStack(height=24):
                    ui.Label("File Path:", width=80, style={"color": 0xFFAAAAAA})
                    ui.StringField(model=self._path_model, style={"color": 0xFFEEEEEE})
                
                # Helper note
                ui.Label("Paste the absolute path to a .step or .stp file.", 
                         style={"font_size": 12, "color": 0xFF888888})

                ui.Spacer(height=10)

                # Import Button
                ui.Button("Import Geometry", clicked_fn=self._on_import, height=40,
                          style={"background_color": 0xFF4A4A4A, "font_size": 16})
                
                # Status
                ui.Spacer(height=5)
                ui.Label(model=self._status_model, style={"color": 0xFFCCCCCC})

    def _on_import(self):
        path = self._path_model.as_string
        # Remove quotes if user copied as path
        path = path.strip().strip('"').strip("'")
        
        if not path:
            self._status_model.set_value("Please enter a valid file path.")
            return

        if not os.path.exists(path):
            self._status_model.set_value(f"File not found: {path}")
            return

        self._status_model.set_value("Importing... separate solids are being generated...")
        
        # Run import
        # Note: This is blocking. For large files, we'd want an async task.
        success = self._importer.import_to_stage(path)
        
        if success:
             self._status_model.set_value(f"Successfully imported: {os.path.basename(path)}")
        else:
             self._status_model.set_value("Import failed. Check console for details.")
