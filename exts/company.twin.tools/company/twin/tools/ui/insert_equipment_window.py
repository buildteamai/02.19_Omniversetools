# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Insert Equipment Window - Insert pre-built USD assets into the current scene as References.
"""

import omni.ui as ui
import omni.usd
from pxr import Usd, UsdGeom, Sdf
import os

from ..utils.mating import MatingSystem


class InsertEquipmentWindow(ui.Window):
    def __init__(self, title="Insert Equipment", **kwargs):
        super().__init__(title, width=500, height=300, **kwargs)
        
        self._file_path = ""
        self._status_label = None
        
        self.frame.set_build_fn(self._build_ui)
        
    def _build_ui(self):
        with ui.VStack(spacing=10, style={"margin": 10}):
            ui.Label("Insert Equipment from USD File", style={"font_size": 18, "color": 0xFF00B4FF})
            ui.Line(height=2, style={"color": 0xFF333333})
            
            ui.Spacer(height=10)
            
            # File Path Input
            ui.Label("USD File Path:", style={"color": 0xFFAAAAAA})
            with ui.HStack(height=30):
                self._path_field = ui.StringField(height=25)
                self._path_field.model.set_value("")
                ui.Button("Browse...", width=80, clicked_fn=self._on_browse)
            
            ui.Spacer(height=10)
            
            # Asset Name (optional override)
            ui.Label("Asset Name (optional):", style={"color": 0xFFAAAAAA})
            self._name_field = ui.StringField(height=25)
            self._name_field.model.set_value("")
            
            ui.Spacer(height=10)
            
            # Insert Location Option
            with ui.HStack(height=25):
                ui.Label("Insert at Selection:", width=150, style={"color": 0xFFAAAAAA})
                self._insert_at_selection = ui.CheckBox(width=25)
                self._insert_at_selection.model.set_value(False)
                ui.Label("(If unchecked, inserts under /World)", style={"color": 0xFF666666, "font_size": 11})
            
            # Copy vs Reference mode
            with ui.HStack(height=25):
                ui.Label("Copy Mode:", width=150, style={"color": 0xFFAAAAAA})
                self._copy_mode = ui.CheckBox(width=25)
                self._copy_mode.model.set_value(False)
                ui.Label("(Unchecked = Reference/live link)", style={"color": 0xFF666666, "font_size": 11})
            
            ui.Spacer(height=15)
            
            # Insert Button
            ui.Button("INSERT", height=40, clicked_fn=self._on_insert,
                     style={"background_color": 0xFF2B5B2B, "font_size": 14})
            
            ui.Spacer(height=10)
            self._status_label = ui.Label("Ready. Select a USD file to insert.", style={"color": 0xFF888888})

    def _on_browse(self):
        """Opens a file dialog to select a USD file."""
        try:
            from omni.kit.window.filepicker import FilePickerDialog
            
            def on_file_selected(filename, dirname):
                if filename and dirname:
                    import os
                    full_path = os.path.join(dirname, filename)
                    self._path_field.model.set_value(full_path)
                    self._status_label.text = f"Selected: {filename}"
                self._file_picker.hide()
            
            self._file_picker = FilePickerDialog(
                "Select USD File",
                apply_button_label="Select",
                click_apply_handler=on_file_selected,
                item_filter_fn=lambda item: item.is_folder or item.path.endswith(('.usd', '.usda', '.usdc', '.usdz')),
            )
            self._file_picker.show()
        except ImportError:
            # Fallback: Just use the text field directly
            self._status_label.text = "File picker not available. Enter path manually."

    def _on_insert(self):
        """Inserts the selected USD file as a Reference."""
        file_path = self._path_field.model.get_value_as_string()
        
        if not file_path:
            self._status_label.text = "Error: No file selected!"
            return
            
        if not os.path.exists(file_path):
            self._status_label.text = f"Error: File not found: {file_path}"
            return
            
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        
        if not stage:
            self._status_label.text = "Error: No stage available!"
            return
        
        # Determine asset name
        custom_name = self._name_field.model.get_value_as_string()
        if custom_name:
            asset_name = custom_name.replace(" ", "_")
        else:
            # Use filename without extension
            asset_name = os.path.splitext(os.path.basename(file_path))[0]
            asset_name = asset_name.replace(" ", "_").replace("-", "_")
        
        # Determine parent path
        parent_path = "/World"
        insert_at_selection = self._insert_at_selection.model.get_value_as_bool()
        
        if insert_at_selection:
            selection = ctx.get_selection().get_selected_prim_paths()
            if selection:
                parent_path = selection[0]
            else:
                self._status_label.text = "No selection! Inserting under /World."
        
        # Create unique prim path
        base_path = f"{parent_path}/{asset_name}"
        prim_path = base_path
        counter = 1
        while stage.GetPrimAtPath(prim_path).IsValid():
            prim_path = f"{base_path}_{counter}"
            counter += 1
        
        # Create Xform container for the imported content
        container = stage.DefinePrim(prim_path, "Xform")
        
        # Open source stage to discover its structure
        source_stage = Usd.Stage.Open(file_path)
        if not source_stage:
            self._status_label.text = f"Error: Could not open {file_path}"
            return
        
        # Check which mode we're using
        use_copy_mode = self._copy_mode.model.get_value_as_bool()
        
        root = source_stage.GetPseudoRoot()
        item_count = 0
        
        if use_copy_mode:
            # COPY MODE: Copy prims directly (snapshot, no live link)
            source_layer = source_stage.GetRootLayer()
            dest_layer = stage.GetRootLayer()
            
            for child in root.GetChildren():
                child_name = child.GetName()
                src_path = child.GetPath()
                dst_path = Sdf.Path(f"{prim_path}/{child_name}")
                
                success = Sdf.CopySpec(source_layer, src_path, dest_layer, dst_path)
                if success:
                    item_count += 1
            mode_str = "Copied"
        else:
            # REFERENCE MODE: Add references (live link to source file)
            for child in root.GetChildren():
                child_name = child.GetName()
                child_container_path = f"{prim_path}/{child_name}"
                child_prim = stage.DefinePrim(child_container_path, "Xform")
                
                ref = Sdf.Reference(file_path, child.GetPath())
                child_prim.GetReferences().AddReference(ref)
                item_count += 1
            mode_str = "Referenced"
        
        # Discover Ports on the container
        ports = MatingSystem.find_ports(container)
        port_count = len(ports)
        
        self._status_label.text = f"{mode_str} {item_count} objects to {prim_path} ({port_count} Ports)"
        
        # Select the new prim
        ctx.get_selection().set_selected_prim_paths([prim_path], False)
