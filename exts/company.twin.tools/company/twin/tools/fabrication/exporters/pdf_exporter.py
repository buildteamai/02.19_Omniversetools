"""
PDF exporter for fabrication drawings.

Creates professional PDF drawings with title block for engineering review.
"""

import os
from typing import Dict, Any, List
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4, ARCH_B
    from reportlab.lib.units import inch
    from reportlab.lib import colors as pdf_colors
    HAS_REPORTLAB = True
except ImportError as e:
    print(f"[PDF Exporter] ReportLab import failed: {e}. Attempting to install via pipapi...")
    try:
        import omni.kit.pipapi
        omni.kit.pipapi.install("reportlab")
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter, A4, ARCH_B
        from reportlab.lib.units import inch
        from reportlab.lib import colors as pdf_colors
        HAS_REPORTLAB = True
        print("[PDF Exporter] generic pipapi install successful.")
    except Exception as install_err:
        HAS_REPORTLAB = False
        print(f"[PDF Exporter] Critical: Failed to install reportlab: {install_err}")
        import sys
        print(f"[PDF Exporter] sys.path: {sys.path}")

from ..drawings.base_drawing import BaseDrawing, Line2D, Circle2D, Text2D
from ..templates.title_blocks import StandardTitleBlock


class PDFExporter:
    """
    Exports fabrication drawings to PDF format.

    Uses reportlab to create professional engineering drawings.
    """

    def __init__(self, page_size=ARCH_B if HAS_REPORTLAB else None):
        if not HAS_REPORTLAB:
            raise ImportError("reportlab library is required. Install with: pip install reportlab")

        self.page_size = page_size
        self.canvas = None

        # Drawing scale (pixels per inch)
        self.scale = 72  # 72 points = 1 inch in PDF

    def export(self, drawing: BaseDrawing, output_path: str) -> bool:
        """
        Export drawing to PDF file.

        Args:
            drawing: BaseDrawing object with prepared data
            output_path: Path to save PDF file

        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"[PDF Export] Generating PDF for {drawing.metadata.drawing_title}")

            # Prepare drawing data
            drawing_data = drawing.prepare_drawing()

            # Create PDF canvas
            self.canvas = canvas.Canvas(output_path, pagesize=self.page_size)

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
            self._draw_cut_list(drawing_data['cut_list'])

            # Draw notes
            self._draw_notes(drawing_data['notes'], title_block)

            # Save PDF
            self.canvas.save()
            print(f"[PDF Export] Successfully exported to {output_path}")

            return True

        except Exception as e:
            print(f"[PDF Export] Error exporting PDF: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _to_pdf_coords(self, x: float, y: float) -> tuple:
        """Convert drawing coordinates to PDF coordinates"""
        # PDF origin is bottom-left, drawing origin is top-left
        return (x * self.scale, y * self.scale)

    def _draw_title_block(self, title_block: StandardTitleBlock, metadata: Any):
        """Draw title block and border"""
        # Draw border
        self.canvas.setStrokeColor(pdf_colors.black)
        self.canvas.setLineWidth(2)

        border_points = title_block.get_border()
        for i in range(len(border_points) - 1):
            x1, y1 = self._to_pdf_coords(*border_points[i])
            x2, y2 = self._to_pdf_coords(*border_points[i + 1])
            self.canvas.line(x1, y1, x2, y2)

        # Draw title block lines
        self.canvas.setLineWidth(1)
        tb_lines = title_block.get_title_block_lines()
        for start, end in tb_lines:
            x1, y1 = self._to_pdf_coords(*start)
            x2, y2 = self._to_pdf_coords(*end)
            self.canvas.line(x1, y1, x2, y2)

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
            x, y = self._to_pdf_coords(*position)
            self.canvas.setFont("Helvetica", height * self.scale)
            self.canvas.drawString(x, y, str(text))

    def _draw_views(self, drawing: BaseDrawing, views: List[Any]):
        """Draw all views"""
        self.canvas.setStrokeColor(pdf_colors.black)
        self.canvas.setLineWidth(1)

        for view in views:
            print(f"[PDF Export] Drawing view: {view.name}")

            # Get geometry for this view
            geometry = drawing.get_main_view_geometry(view.name)

            # Offset all geometry by view position
            offset_x, offset_y = view.position
            scale = view.scale

            for geom in geometry:
                if isinstance(geom, Line2D):
                    # Set line style based on type
                    if geom.line_type == 'hidden':
                        self.canvas.setDash([3, 3])
                        self.canvas.setStrokeColor(pdf_colors.grey)
                    elif geom.line_type == 'center':
                        self.canvas.setDash([10, 3, 2, 3])
                        self.canvas.setStrokeColor(pdf_colors.red)
                    else:
                        self.canvas.setDash()
                        self.canvas.setStrokeColor(pdf_colors.black)

                    x1, y1 = self._to_pdf_coords(
                        geom.start[0] * scale + offset_x,
                        geom.start[1] * scale + offset_y
                    )
                    x2, y2 = self._to_pdf_coords(
                        geom.end[0] * scale + offset_x,
                        geom.end[1] * scale + offset_y
                    )
                    self.canvas.line(x1, y1, x2, y2)

                    # Reset to solid line
                    self.canvas.setDash()

                elif isinstance(geom, Circle2D):
                    self.canvas.setStrokeColor(pdf_colors.black)
                    center_x, center_y = self._to_pdf_coords(
                        geom.center[0] * scale + offset_x,
                        geom.center[1] * scale + offset_y
                    )
                    radius = geom.radius * scale * self.scale

                    self.canvas.circle(center_x, center_y, radius, stroke=1, fill=0)

                elif isinstance(geom, Text2D):
                    x, y = self._to_pdf_coords(
                        geom.position[0] * scale + offset_x,
                        geom.position[1] * scale + offset_y
                    )
                    self.canvas.setFont("Helvetica", geom.height * scale * self.scale)
                    self.canvas.drawString(x, y, geom.text)

            # Add view label
            label_x, label_y = self._to_pdf_coords(offset_x, offset_y - 0.5)
            self.canvas.setFont("Helvetica-Bold", 11)
            self.canvas.drawString(label_x, label_y, f"{view.name.upper()} VIEW")

    def _draw_dimensions(self, dimensions: List[Any]):
        """Draw dimension annotations"""
        self.canvas.setStrokeColor(pdf_colors.blue)
        self.canvas.setLineWidth(0.5)

        for dim in dimensions:
            # Draw extension lines
            x1, y1 = self._to_pdf_coords(dim.start_point[0],
                                        dim.start_point[1] - dim.extension_line_offset)
            x2, y2 = self._to_pdf_coords(*dim.start_point)
            self.canvas.line(x1, y1, x2, y2)

            x1, y1 = self._to_pdf_coords(dim.end_point[0],
                                        dim.end_point[1] - dim.extension_line_offset)
            x2, y2 = self._to_pdf_coords(*dim.end_point)
            self.canvas.line(x1, y1, x2, y2)

            # Draw dimension line
            x1, y1 = self._to_pdf_coords(dim.start_point[0],
                                        dim.start_point[1] - dim.extension_line_offset)
            x2, y2 = self._to_pdf_coords(dim.end_point[0],
                                        dim.end_point[1] - dim.extension_line_offset)
            self.canvas.line(x1, y1, x2, y2)

            # Add dimension text
            mid_x = (dim.start_point[0] + dim.end_point[0]) / 2
            mid_y = (dim.start_point[1] + dim.end_point[1]) / 2 - dim.extension_line_offset - dim.text_offset

            label_text = dim.label if dim.label else f"{dim.value:.3f}\""
            text_x, text_y = self._to_pdf_coords(mid_x, mid_y)

            self.canvas.setFont("Helvetica", 7)
            self.canvas.drawCentredString(text_x, text_y, label_text)

    def _draw_gdt_callouts(self, callouts: List[Any]):
        """Draw GD&T feature control frames"""
        self.canvas.setStrokeColor(pdf_colors.darkblue)
        self.canvas.setFont("Helvetica", 8)

        for callout in callouts:
            text = f"{callout.symbol} {callout.tolerance:.3f}\""
            if callout.datum:
                text += f" [{callout.datum}]"

            x, y = self._to_pdf_coords(*callout.position)
            self.canvas.drawString(x, y, text)

    def _draw_cut_list(self, cut_list: List[Any]):
        """Draw cut list table"""
        if not cut_list:
            return

        # Table position (upper right area)
        table_x = 11.0
        table_y = 9.0
        row_height = 0.25
        col_widths = [0.5, 0.5, 3.0, 1.0, 1.0, 0.75]

        headers = ["MRK", "QTY", "DESCRIPTION", "MATERIAL", "LENGTH", "WEIGHT"]

        # Calculate table dimensions
        table_width = sum(col_widths)
        table_height = (len(cut_list) + 1) * row_height

        # Draw table border
        self.canvas.setStrokeColor(pdf_colors.darkgreen)
        self.canvas.setLineWidth(1)

        x1, y1 = self._to_pdf_coords(table_x, table_y)
        x2, y2 = self._to_pdf_coords(table_x + table_width, table_y + table_height)

        self.canvas.rect(x1, y1, x2 - x1, y2 - y1)

        # Draw column dividers
        x_pos = table_x
        for width in col_widths[:-1]:
            x_pos += width
            line_x1, line_y1 = self._to_pdf_coords(x_pos, table_y)
            line_x2, line_y2 = self._to_pdf_coords(x_pos, table_y + table_height)
            self.canvas.line(line_x1, line_y1, line_x2, line_y2)

        # Draw header row separator
        sep_x1, sep_y1 = self._to_pdf_coords(table_x, table_y + row_height)
        sep_x2, sep_y2 = self._to_pdf_coords(table_x + table_width, table_y + row_height)
        self.canvas.line(sep_x1, sep_y1, sep_x2, sep_y2)

        # Draw headers
        self.canvas.setFont("Helvetica-Bold", 7)
        x_pos = table_x + 0.05
        for i, header in enumerate(headers):
            text_x, text_y = self._to_pdf_coords(x_pos, table_y + table_height - 0.15)
            self.canvas.drawString(text_x, text_y, header)
            x_pos += col_widths[i]

        # Draw cut list items
        self.canvas.setFont("Helvetica", 6)
        for row_idx, item in enumerate(cut_list):
            y_pos = table_y + table_height - (row_idx + 2) * row_height + 0.10

            row_data = [
                item.mark,
                str(item.quantity),
                item.description[:35],
                item.material,
                f"{item.length:.1f}\"" if item.length else "",
                f"{item.weight:.1f}#" if item.weight else ""
            ]

            x_pos = table_x + 0.05
            for i, data in enumerate(row_data):
                text_x, text_y = self._to_pdf_coords(x_pos, y_pos)
                self.canvas.drawString(text_x, text_y, str(data))
                x_pos += col_widths[i]

        # Table title
        title_x, title_y = self._to_pdf_coords(table_x, table_y + table_height + 0.2)
        self.canvas.setFont("Helvetica-Bold", 11)
        self.canvas.drawString(title_x, title_y, "CUT LIST")

    def _draw_notes(self, notes: List[str], title_block: StandardTitleBlock):
        """Draw general notes"""
        if not notes:
            return

        notes_area = title_block.get_notes_area()
        x, y, width, height = notes_area

        # Notes title
        title_x, title_y = self._to_pdf_coords(x, y + height - 0.15)
        self.canvas.setFont("Helvetica-Bold", 9)
        self.canvas.drawString(title_x, title_y, "GENERAL NOTES:")

        # Draw notes
        line_spacing = 0.15
        current_y = y + height - 0.35

        self.canvas.setFont("Helvetica", 6)
        for i, note in enumerate(notes):
            if current_y < y:
                break

            note_text = f"{i + 1}. {note}"
            text_x, text_y = self._to_pdf_coords(x, current_y)
            self.canvas.drawString(text_x, text_y, note_text)
            current_y -= line_spacing


def export_to_pdf(drawing: BaseDrawing, output_path: str) -> bool:
    """
    Convenience function to export a drawing to PDF.

    Args:
        drawing: BaseDrawing object
        output_path: Path to save PDF file

    Returns:
        True if successful, False otherwise
    """
    exporter = PDFExporter()
    return exporter.export(drawing, output_path)
