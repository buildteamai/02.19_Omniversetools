"""
DXF file exporter for fabrication drawings.

Exports shop drawings to DXF format for use in CAD/CAM systems.
"""

import os
from typing import Dict, Any, List
try:
    import ezdxf
    from ezdxf import colors
    from ezdxf.enums import TextEntityAlignment
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False
    print("[DXF Exporter] Warning: ezdxf not installed. Install with: pip install ezdxf")

from ..drawings.base_drawing import BaseDrawing, Line2D, Circle2D, Text2D
from ..templates.title_blocks import StandardTitleBlock


class DXFExporter:
    """
    Exports fabrication drawings to DXF format.

    Uses ezdxf library to create multi-layer, properly scaled DXF files.
    """

    def __init__(self):
        if not HAS_EZDXF:
            raise ImportError("ezdxf library is required. Install with: pip install ezdxf")

        self.doc = None
        self.msp = None

        # Layer definitions
        self.layers = {
            'BORDER': {'color': colors.WHITE, 'lineweight': 50},
            'TITLEBLOCK': {'color': colors.WHITE, 'lineweight': 25},
            'GEOMETRY': {'color': colors.WHITE, 'lineweight': 35},
            'HIDDEN': {'color': colors.GRAY, 'lineweight': 18, 'linetype': 'DASHED'},
            'CENTER': {'color': colors.RED, 'lineweight': 18, 'linetype': 'CENTER'},
            'DIMENSIONS': {'color': colors.CYAN, 'lineweight': 18},
            'TEXT': {'color': colors.WHITE, 'lineweight': 18},
            'NOTES': {'color': colors.YELLOW, 'lineweight': 18},
            'TABLES': {'color': colors.GREEN, 'lineweight': 25}
        }

    def export(self, drawing: BaseDrawing, output_path: str) -> bool:
        """
        Export drawing to DXF file.

        Args:
            drawing: BaseDrawing object with prepared data
            output_path: Path to save DXF file

        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"[DXF Export] Generating DXF for {drawing.metadata.drawing_title}")

            # Prepare drawing data
            drawing_data = drawing.prepare_drawing()

            # Create new DXF document
            self.doc = ezdxf.new('R2010')
            self.msp = self.doc.modelspace()

            # Setup layers
            self._setup_layers()

            # Create title block
            title_block = StandardTitleBlock(StandardTitleBlock.ANSI_B)
            self._draw_title_block(title_block, drawing.metadata)

            # Draw views
            self._draw_views(drawing, drawing_data['views'])

            # Draw dimensions
            self._draw_dimensions(drawing_data['dimensions'])

            # Draw GD&T callouts
            self._draw_gdt_callouts(drawing_data['gdt_callouts'])

            # Draw cut list table
            self._draw_cut_list(drawing_data['cut_list'], title_block)

            # Draw notes
            self._draw_notes(drawing_data['notes'], title_block)

            # Save DXF file
            self.doc.saveas(output_path)
            print(f"[DXF Export] Successfully exported to {output_path}")

            return True

        except Exception as e:
            print(f"[DXF Export] Error exporting DXF: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _setup_layers(self):
        """Create drawing layers with proper colors and line weights"""
        for layer_name, properties in self.layers.items():
            layer = self.doc.layers.add(layer_name)
            layer.color = properties['color']

            if 'lineweight' in properties:
                layer.lineweight = properties['lineweight']

            if 'linetype' in properties:
                # Ensure linetype exists
                linetype = properties['linetype']
                if linetype not in self.doc.linetypes:
                    if linetype == 'DASHED':
                        self.doc.linetypes.add('DASHED', [0.5, 0.25, -0.25])
                    elif linetype == 'CENTER':
                        self.doc.linetypes.add('CENTER', [0.75, 0.5, -0.25, 0.125, -0.25])
                layer.dxf.linetype = linetype

    def _draw_title_block(self, title_block: StandardTitleBlock, metadata: Any):
        """Draw title block and border"""
        # Draw border
        border_points = title_block.get_border()
        for i in range(len(border_points) - 1):
            self.msp.add_line(border_points[i], border_points[i + 1],
                            dxfattribs={'layer': 'BORDER'})

        # Draw title block lines
        tb_lines = title_block.get_title_block_lines()
        for start, end in tb_lines:
            self.msp.add_line(start, end, dxfattribs={'layer': 'TITLEBLOCK'})

        # Draw title block text
        metadata_dict = {
            'project_name': metadata.project_name,
            'drawing_title': metadata.drawing_title,
            'drawing_number': metadata.drawing_number,
            'revision': metadata.revision,
            'engineer': metadata.engineer,
            'designer': metadata.designer,
            'checker': metadata.checker,
            'date': metadata.date,
            'scale': metadata.scale
        }

        text_items = title_block.get_text_positions(metadata_dict)
        for text, position, height in text_items:
            self.msp.add_text(text, dxfattribs={
                'layer': 'TITLEBLOCK',
                'height': height,
                'insert': position
            })

    def _draw_views(self, drawing: BaseDrawing, views: List[Any]):
        """Draw all views"""
        for view in views:
            print(f"[DXF Export] Drawing view: {view.name}")

            # Get geometry for this view
            geometry = drawing.get_main_view_geometry(view.name)

            # Offset all geometry by view position
            offset_x, offset_y = view.position
            scale = view.scale

            for geom in geometry:
                if isinstance(geom, Line2D):
                    layer = 'GEOMETRY'
                    if geom.line_type == 'hidden':
                        layer = 'HIDDEN'
                    elif geom.line_type == 'center':
                        layer = 'CENTER'

                    start = (geom.start[0] * scale + offset_x,
                           geom.start[1] * scale + offset_y)
                    end = (geom.end[0] * scale + offset_x,
                         geom.end[1] * scale + offset_y)

                    self.msp.add_line(start, end, dxfattribs={'layer': layer})

                elif isinstance(geom, Circle2D):
                    center = (geom.center[0] * scale + offset_x,
                            geom.center[1] * scale + offset_y)
                    radius = geom.radius * scale

                    self.msp.add_circle(center, radius, dxfattribs={'layer': 'GEOMETRY'})

                elif isinstance(geom, Text2D):
                    position = (geom.position[0] * scale + offset_x,
                              geom.position[1] * scale + offset_y)
                    height = geom.height * scale

                    self.msp.add_text(geom.text, dxfattribs={
                        'layer': 'TEXT',
                        'height': height,
                        'insert': position,
                        'rotation': geom.rotation
                    })

            # Add view label
            label_pos = (offset_x, offset_y - 0.5)
            self.msp.add_text(f"{view.name.upper()} VIEW", dxfattribs={
                'layer': 'TEXT',
                'height': 0.15,
                'insert': label_pos
            })

    def _draw_dimensions(self, dimensions: List[Any]):
        """Draw dimension annotations"""
        for dim in dimensions:
            # Simple dimension representation (full DXF dimensions are complex)
            # Draw extension lines
            self.msp.add_line(
                (dim.start_point[0], dim.start_point[1] - dim.extension_line_offset),
                dim.start_point,
                dxfattribs={'layer': 'DIMENSIONS'}
            )
            self.msp.add_line(
                (dim.end_point[0], dim.end_point[1] - dim.extension_line_offset),
                dim.end_point,
                dxfattribs={'layer': 'DIMENSIONS'}
            )

            # Draw dimension line
            self.msp.add_line(
                (dim.start_point[0], dim.start_point[1] - dim.extension_line_offset),
                (dim.end_point[0], dim.end_point[1] - dim.extension_line_offset),
                dxfattribs={'layer': 'DIMENSIONS'}
            )

            # Add dimension text
            mid_x = (dim.start_point[0] + dim.end_point[0]) / 2
            mid_y = (dim.start_point[1] + dim.end_point[1]) / 2 - dim.extension_line_offset - dim.text_offset

            label_text = dim.label if dim.label else f"{dim.value:.3f}\""
            self.msp.add_text(label_text, dxfattribs={
                'layer': 'DIMENSIONS',
                'height': 0.10,
                'insert': (mid_x, mid_y)
            })

    def _draw_gdt_callouts(self, callouts: List[Any]):
        """Draw GD&T feature control frames"""
        for callout in callouts:
            # Simplified GD&T representation
            # Full GD&T frames require complex formatting

            text = f"{callout.symbol} {callout.tolerance:.3f}\""
            if callout.datum:
                text += f" [{callout.datum}]"

            self.msp.add_text(text, dxfattribs={
                'layer': 'DIMENSIONS',
                'height': 0.10,
                'insert': callout.position
            })

            # Add leader line to feature (simplified)
            # In production, would draw proper feature control frame

    def _draw_cut_list(self, cut_list: List[Any], title_block: StandardTitleBlock):
        """Draw cut list table"""
        if not cut_list:
            return

        # Table position (upper right area)
        table_x = 11.0
        table_y = 9.0
        row_height = 0.25
        col_widths = [0.5, 0.5, 3.0, 1.0, 1.0, 0.75]  # Mark, Qty, Description, Material, Length, Weight

        # Table header
        headers = ["MRK", "QTY", "DESCRIPTION", "MATERIAL", "LENGTH", "WEIGHT"]

        # Draw table border
        table_width = sum(col_widths)
        table_height = (len(cut_list) + 1) * row_height

        self.msp.add_line((table_x, table_y), (table_x + table_width, table_y),
                         dxfattribs={'layer': 'TABLES'})
        self.msp.add_line((table_x + table_width, table_y),
                         (table_x + table_width, table_y + table_height),
                         dxfattribs={'layer': 'TABLES'})
        self.msp.add_line((table_x + table_width, table_y + table_height),
                         (table_x, table_y + table_height),
                         dxfattribs={'layer': 'TABLES'})
        self.msp.add_line((table_x, table_y + table_height), (table_x, table_y),
                         dxfattribs={'layer': 'TABLES'})

        # Draw column dividers
        x_pos = table_x
        for width in col_widths[:-1]:
            x_pos += width
            self.msp.add_line((x_pos, table_y), (x_pos, table_y + table_height),
                            dxfattribs={'layer': 'TABLES'})

        # Draw header row separator
        self.msp.add_line((table_x, table_y + row_height),
                         (table_x + table_width, table_y + row_height),
                         dxfattribs={'layer': 'TABLES'})

        # Draw headers
        x_pos = table_x + 0.05
        for i, header in enumerate(headers):
            self.msp.add_text(header, dxfattribs={
                'layer': 'TABLES',
                'height': 0.10,
                'insert': (x_pos, table_y + table_height - 0.15)
            })
            x_pos += col_widths[i]

        # Draw cut list items
        for row_idx, item in enumerate(cut_list):
            y_pos = table_y + table_height - (row_idx + 2) * row_height + 0.10

            row_data = [
                item.mark,
                str(item.quantity),
                item.description[:35],  # Truncate if too long
                item.material,
                f"{item.length:.1f}\"" if item.length else "",
                f"{item.weight:.1f}#" if item.weight else ""
            ]

            x_pos = table_x + 0.05
            for i, data in enumerate(row_data):
                self.msp.add_text(str(data), dxfattribs={
                    'layer': 'TABLES',
                    'height': 0.08,
                    'insert': (x_pos, y_pos)
                })
                x_pos += col_widths[i]

        # Table title
        self.msp.add_text("CUT LIST", dxfattribs={
            'layer': 'TABLES',
            'height': 0.15,
            'insert': (table_x, table_y + table_height + 0.2)
        })

    def _draw_notes(self, notes: List[str], title_block: StandardTitleBlock):
        """Draw general notes"""
        if not notes:
            return

        notes_area = title_block.get_notes_area()
        x, y, width, height = notes_area

        # Notes title
        self.msp.add_text("GENERAL NOTES:", dxfattribs={
            'layer': 'NOTES',
            'height': 0.12,
            'insert': (x, y + height - 0.15)
        })

        # Draw notes
        line_spacing = 0.15
        current_y = y + height - 0.35

        for i, note in enumerate(notes):
            if current_y < y:  # Stop if running out of space
                break

            note_text = f"{i + 1}. {note}"
            self.msp.add_text(note_text, dxfattribs={
                'layer': 'NOTES',
                'height': 0.08,
                'insert': (x, current_y)
            })
            current_y -= line_spacing


def export_to_dxf(drawing: BaseDrawing, output_path: str) -> bool:
    """
    Convenience function to export a drawing to DXF.

    Args:
        drawing: BaseDrawing object
        output_path: Path to save DXF file

    Returns:
        True if successful, False otherwise
    """
    exporter = DXFExporter()
    return exporter.export(drawing, output_path)
