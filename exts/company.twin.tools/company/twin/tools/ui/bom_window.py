# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Bill of Materials (BOM) Window

UI for extracting and exporting BOM data from USD stage.
"""

import omni.ui as ui
import omni.usd
import os
from datetime import datetime

from ..utils.bom_export import BOMExporter, BOMItem


class BOMWindow(ui.Window):
    """Window for Bill of Materials extraction and export."""
    
    def __init__(self, title="Bill of Materials", **kwargs):
        super().__init__(title, width=700, height=550, **kwargs)
        
        # BOM data
        self._bom_items = []
        self._rolled_up = False
        
        # UI models
        self._output_dir_model = ui.SimpleStringModel("C:/Programming/buildteamai/output")
        self._project_name_model = ui.SimpleStringModel("Project BOM")
        self._rollup_model = ui.SimpleBoolModel(True)
        
        # UI references
        self._bom_container = None
        self._stats_label = None
        self._status_label = None
        
        self._build_ui()
    
    def _build_ui(self):
        """Builds the window UI."""
        with self.frame:
            with ui.VStack(spacing=10, padding=15):
                # Header
                ui.Label("Bill of Materials", style={"font_size": 18, "highlight_color": 0xFFFF6600})
                ui.Label("Extract component data from USD stage and export to Excel", 
                        style={"color": 0xFFAAAAAA, "font_size": 12})
                
                ui.Spacer(height=5)
                ui.Separator(height=2)
                ui.Spacer(height=5)
                
                # Extract controls
                with ui.HStack(height=30, spacing=10):
                    ui.Button("Extract BOM from Stage", clicked_fn=self._on_extract_bom, 
                             height=30, width=200, style={"background_color": 0xFF336699})
                    
                    self._rollup_model.add_value_changed_fn(lambda m: self._on_rollup_changed())
                    ui.CheckBox(self._rollup_model, width=20)
                    ui.Label("Roll up by part type", width=150)
                    
                    ui.Spacer()
                    
                    self._stats_label = ui.Label("No items extracted", style={"color": 0xFF88FF88})
                
                ui.Spacer(height=5)
                ui.Separator(height=2)
                ui.Spacer(height=5)
                
                # BOM Preview Table Header
                with ui.HStack(height=25):
                    ui.Label("#", width=30, style={"font_size": 11, "color": 0xFFCCCCCC})
                    ui.Label("Type", width=100, style={"font_size": 11, "color": 0xFFCCCCCC})
                    ui.Label("Description", width=200, style={"font_size": 11, "color": 0xFFCCCCCC})
                    ui.Label("Dimensions", width=150, style={"font_size": 11, "color": 0xFFCCCCCC})
                    ui.Label("Qty", width=50, style={"font_size": 11, "color": 0xFFCCCCCC})
                    ui.Label("Weight (lb)", width=80, style={"font_size": 11, "color": 0xFFCCCCCC})
                
                # BOM Preview Table Content
                with ui.ScrollingFrame(height=250, horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF):
                    self._bom_container = ui.VStack(spacing=2)
                    with self._bom_container:
                        ui.Label("Click 'Extract BOM from Stage' to load items", 
                                style={"color": 0xFF888888, "font_size": 12})
                
                ui.Spacer(height=5)
                ui.Separator(height=2)
                ui.Spacer(height=5)

                # Manual Tagging Section
                ui.Label("Manual Tagging (for imported assets)", style={"font_size": 14, "highlight_color": 0xFF00AAFF})
                
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Type:", width=100)
                    self._tag_type_model = ui.ComboBox(0, "Equipment", "Inline Component", "Structure", "Generic Include").model
                
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Description:", width=100)
                    self._tag_desc_model = ui.StringField().model
                    
                with ui.HStack(height=30, spacing=10):
                    ui.Button("Tag Selected Objects", clicked_fn=self._on_tag_selected, 
                             height=30, style={"background_color": 0xFF555555})
                
                ui.Spacer(height=5)
                ui.Separator(height=2)
                ui.Spacer(height=5)
                
                # Export Settings
                ui.Label("Export Settings", style={"font_size": 14, "highlight_color": 0xFF00AAFF})
                
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Project Name:", width=100)
                    ui.StringField(model=self._project_name_model, width=250)
                
                with ui.HStack(height=25, spacing=5):
                    ui.Label("Output Folder:", width=100)
                    ui.StringField(model=self._output_dir_model)
                
                ui.Spacer(height=10)
                
                # Export Button
                with ui.HStack(height=40, spacing=10):
                    ui.Button("Export to Excel", clicked_fn=self._on_export_excel,
                             height=40, style={"background_color": 0xFF336600})
                    ui.Button("Export to CSV", clicked_fn=self._on_export_csv,
                             height=40, style={"background_color": 0xFF444444})
                
                ui.Spacer(height=5)
                
                # Status
                self._status_label = ui.Label("Ready", style={"color": 0xFF888888, "font_size": 11})
    
    def _on_extract_bom(self):
        """Extracts BOM from current USD stage."""
        try:
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            
            if not stage:
                self._set_status("Error: No USD stage open", error=True)
                return
            
            # Extract items
            self._bom_items = BOMExporter.extract_from_stage(stage)
            
            if not self._bom_items:
                self._set_status("No BOM items found in stage", error=False)
                self._update_bom_display([])
                return
            
            # Apply rollup if enabled
            display_items = self._bom_items
            if self._rollup_model.as_bool:
                display_items = BOMExporter.rollup_bom(self._bom_items)
                self._rolled_up = True
            else:
                self._rolled_up = False
            
            # Update display
            self._update_bom_display(display_items)
            
            # Update stats
            total_qty = sum(item.quantity for item in display_items)
            total_weight = sum(item.total_weight for item in display_items)
            self._stats_label.text = f"{len(display_items)} items | Qty: {total_qty} | Weight: {total_weight:.1f} lb"
            
            self._set_status(f"Extracted {len(self._bom_items)} items from stage")
            
        except Exception as e:
            self._set_status(f"Error extracting BOM: {e}", error=True)
            import traceback
            traceback.print_exc()
    
    def _on_rollup_changed(self):
        """Handles rollup checkbox change."""
        if self._bom_items:
            # Re-display with new rollup setting
            if self._rollup_model.as_bool:
                display_items = BOMExporter.rollup_bom(self._bom_items)
            else:
                display_items = self._bom_items
            
            self._update_bom_display(display_items)
            
            total_qty = sum(item.quantity for item in display_items)
            total_weight = sum(item.total_weight for item in display_items)
            self._stats_label.text = f"{len(display_items)} items | Qty: {total_qty} | Weight: {total_weight:.1f} lb"
    
    def _update_bom_display(self, items):
        """Updates the BOM preview table."""
        if not self._bom_container:
            return
        
        self._bom_container.clear()
        
        with self._bom_container:
            if not items:
                ui.Label("No items to display", style={"color": 0xFF888888})
                return
            
            for idx, item in enumerate(items, 1):
                self._build_bom_row(idx, item)
    
    def _build_bom_row(self, idx: int, item: BOMItem):
        """Builds a single BOM row."""
        config = BOMExporter.GENERATOR_CONFIGS.get(item.generator_type, {})
        category = config.get('category', 'Other')
        
        # Alternate row colors
        bg_color = 0xFF2A2A2A if idx % 2 == 0 else 0xFF333333
        
        with ui.ZStack(height=22):
            ui.Rectangle(style={"background_color": bg_color, "border_radius": 2})
            with ui.HStack(spacing=0):
                ui.Label(str(idx), width=30, style={"font_size": 11})
                ui.Label(category[:15], width=100, style={"font_size": 11, "color": 0xFFAAAAFF})
                
                # Truncate description if needed
                desc = item.description[:30] + "..." if len(item.description) > 30 else item.description
                ui.Label(desc, width=200, style={"font_size": 11})
                
                # Truncate dimensions
                dims = item.dimensions[:20] + "..." if len(item.dimensions) > 20 else item.dimensions
                ui.Label(dims, width=150, style={"font_size": 11, "color": 0xFFAAAAAA})
                
                ui.Label(str(item.quantity), width=50, style={"font_size": 11})
                
                weight_str = f"{item.total_weight:.1f}" if item.total_weight > 0 else "-"
                ui.Label(weight_str, width=80, style={"font_size": 11})
    
    def _on_export_excel(self):
        """Exports BOM to Excel file."""
        self._export_to_file('xlsx')
    
    def _on_export_csv(self):
        """Exports BOM to CSV file."""
        self._export_to_file('csv')
    
    def _export_to_file(self, format_type: str):
        """Exports BOM to specified format."""
        if not self._bom_items:
            self._set_status("No BOM data to export. Extract first.", error=True)
            return
        
        try:
            output_dir = self._output_dir_model.as_string
            if not output_dir:
                output_dir = "C:/Programming/buildteamai/output"
            
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_name = self._project_name_model.as_string or "Project"
            safe_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_name = safe_name.replace(' ', '_')
            
            # Get items to export (rolled up or not)
            if self._rollup_model.as_bool:
                export_items = BOMExporter.rollup_bom(self._bom_items)
            else:
                export_items = self._bom_items
            
            if format_type == 'xlsx':
                filepath = os.path.join(output_dir, f"BOM_{safe_name}_{timestamp}.xlsx")
                stage = omni.usd.get_context().get_stage()
                success = BOMExporter.export_to_excel(export_items, filepath, project_name, stage=stage)
            else:
                filepath = os.path.join(output_dir, f"BOM_{safe_name}_{timestamp}.csv")
                success = BOMExporter.export_to_csv(export_items, filepath)
            
            if success:
                self._set_status(f"✓ Exported to: {filepath}")
            else:
                self._set_status("Export failed - check console for details", error=True)
                
        except Exception as e:
            self._set_status(f"Export error: {e}", error=True)
            import traceback
            traceback.print_exc()
    
    def _on_tag_selected(self):
        """Tags selected prims with BOM metadata."""
        ctx = omni.usd.get_context()
        selection = ctx.get_selection().get_selected_prim_paths()
        
        if not selection:
            self._set_status("No objects selected to tag", error=True)
            return
            
        stage = ctx.get_stage()
        
        # Map UI selection to generatorType
        type_idx = self._tag_type_model.get_item_value_model().as_int
        types = ["equipment", "inline_component", "generic_prim", "generic_mesh"]
        gen_type = types[type_idx] if type_idx < len(types) else "generic_prim"
        
        description = self._tag_desc_model.as_string
        if not description:
            description = "Manual Item"
            
        count = 0
        for path in selection:
            prim = stage.GetPrimAtPath(path)
            if prim:
                custom = prim.GetCustomData() or {}
                custom['generatorType'] = gen_type
                custom['description'] = description
                # Ensure it's not filtered out
                custom['manual_tag'] = True 
                prim.SetCustomData(custom)
                count += 1
                
        self._set_status(f"Tagged {count} items as '{gen_type}'")
        print(f"[BOMWindow] Tagged {count} items: type={gen_type}, desc={description}")

    def _set_status(self, message: str, error: bool = False):
        """Updates status label."""
        if self._status_label:
            self._status_label.text = message
            self._status_label.style = {"color": 0xFFFF4444 if error else 0xFF88FF88, "font_size": 11}
        print(f"[BOMWindow] {message}")
