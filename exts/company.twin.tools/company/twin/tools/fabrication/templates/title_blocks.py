"""
Title block templates for fabrication drawings.

Provides standard title block layouts with company info, drawing metadata, and revision block.
"""

from typing import Dict, List, Tuple, Any
from dataclasses import dataclass


@dataclass
class TitleBlockLayout:
    """Defines layout dimensions for a title block"""
    width: float
    height: float
    border_margin: float
    line_spacing: float


class StandardTitleBlock:
    """
    Standard ANSI/AISC compliant title block.

    Layout:
    - Top: Drawing title, number, revision
    - Middle: Project info, engineer, designer
    - Bottom: Company info, date, scale
    """

    # Standard layouts (width × height in inches)
    ANSI_A = TitleBlockLayout(11.0, 8.5, 0.5, 0.25)
    ANSI_B = TitleBlockLayout(17.0, 11.0, 0.5, 0.25)
    ANSI_C = TitleBlockLayout(22.0, 17.0, 0.5, 0.25)
    ANSI_D = TitleBlockLayout(34.0, 22.0, 0.5, 0.25)

    def __init__(self, layout: TitleBlockLayout = ANSI_B):
        self.layout = layout

    def get_border(self) -> List[Tuple[float, float]]:
        """Get border rectangle coordinates"""
        margin = self.layout.border_margin
        return [
            (margin, margin),
            (self.layout.width - margin, margin),
            (self.layout.width - margin, self.layout.height - margin),
            (margin, self.layout.height - margin),
            (margin, margin)
        ]

    def get_title_block_lines(self) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """Get title block dividing lines"""
        lines = []
        margin = self.layout.border_margin
        width = self.layout.width
        height = self.layout.height

        # Title block is in lower right corner
        tb_width = 6.0
        tb_height = 2.5
        tb_x = width - margin - tb_width
        tb_y = margin

        # Outer border of title block
        lines.append(((tb_x, tb_y), (tb_x + tb_width, tb_y)))
        lines.append(((tb_x + tb_width, tb_y), (tb_x + tb_width, tb_y + tb_height)))
        lines.append(((tb_x + tb_width, tb_y + tb_height), (tb_x, tb_y + tb_height)))
        lines.append(((tb_x, tb_y + tb_height), (tb_x, tb_y)))

        # Horizontal dividers
        lines.append(((tb_x, tb_y + 0.5), (tb_x + tb_width, tb_y + 0.5)))
        lines.append(((tb_x, tb_y + 1.0), (tb_x + tb_width, tb_y + 1.0)))
        lines.append(((tb_x, tb_y + 1.5), (tb_x + tb_width, tb_y + 1.5)))
        lines.append(((tb_x, tb_y + 2.0), (tb_x + tb_width, tb_y + 2.0)))

        # Vertical dividers
        lines.append(((tb_x + 3.0, tb_y), (tb_x + 3.0, tb_y + 0.5)))
        lines.append(((tb_x + 4.5, tb_y), (tb_x + 4.5, tb_y + 0.5)))
        lines.append(((tb_x + 3.0, tb_y + 0.5), (tb_x + 3.0, tb_y + 1.0)))
        lines.append(((tb_x + 3.0, tb_y + 1.0), (tb_x + 3.0, tb_y + 1.5)))

        return lines

    def get_text_positions(self, metadata: Dict[str, Any]) -> List[Tuple[str, Tuple[float, float], float]]:
        """
        Get text positions for title block content.

        Returns:
            List of (text, position, height) tuples
        """
        texts = []
        margin = self.layout.border_margin
        width = self.layout.width
        height = self.layout.height

        tb_width = 6.0
        tb_height = 2.5
        tb_x = width - margin - tb_width
        tb_y = margin

        # Company/Project name (top section)
        texts.append((metadata.get('project_name', 'BuildTeamAI Steel'),
                     (tb_x + 0.1, tb_y + tb_height - 0.35), 0.20))

        # Drawing title (large)
        texts.append((metadata.get('drawing_title', 'STEEL FABRICATION DRAWING'),
                     (tb_x + 0.1, tb_y + 2.25), 0.15))

        # Drawing number
        texts.append(("DWG NO:", (tb_x + 0.1, tb_y + 1.75), 0.10))
        texts.append((metadata.get('drawing_number', 'S-001'),
                     (tb_x + 0.7, tb_y + 1.75), 0.12))

        # Revision
        texts.append(("REV:", (tb_x + 3.1, tb_y + 1.75), 0.10))
        texts.append((metadata.get('revision', 'A'),
                     (tb_x + 3.5, tb_y + 1.75), 0.12))

        # Engineer
        texts.append(("ENGINEER:", (tb_x + 0.1, tb_y + 1.25), 0.08))
        texts.append((metadata.get('engineer', ''),
                     (tb_x + 0.9, tb_y + 1.25), 0.10))

        # Designer
        texts.append(("DESIGNER:", (tb_x + 0.1, tb_y + 0.75), 0.08))
        texts.append((metadata.get('designer', 'BuildTeamAI'),
                     (tb_x + 0.9, tb_y + 0.75), 0.10))

        # Checker
        texts.append(("CHECKER:", (tb_x + 3.1, tb_y + 1.25), 0.08))
        texts.append((metadata.get('checker', ''),
                     (tb_x + 3.8, tb_y + 1.25), 0.10))

        # Date
        texts.append(("DATE:", (tb_x + 0.1, tb_y + 0.25), 0.08))
        texts.append((metadata.get('date', ''),
                     (tb_x + 0.5, tb_y + 0.25), 0.10))

        # Scale
        texts.append(("SCALE:", (tb_x + 3.1, tb_y + 0.25), 0.08))
        texts.append((metadata.get('scale', '1:10'),
                     (tb_x + 3.6, tb_y + 0.25), 0.10))

        # Sheet
        texts.append(("SHEET:", (tb_x + 4.6, tb_y + 0.25), 0.08))
        texts.append(("1 OF 1", (tb_x + 5.1, tb_y + 0.25), 0.10))

        return texts

    def get_notes_area(self) -> Tuple[float, float, float, float]:
        """
        Get notes area coordinates (x, y, width, height).

        Returns bottom-left area for general notes.
        """
        margin = self.layout.border_margin
        width = self.layout.width

        # Notes area in lower left
        notes_x = margin + 0.5
        notes_y = margin + 0.5
        notes_width = width - 7.5  # Leave room for title block
        notes_height = 2.0

        return (notes_x, notes_y, notes_width, notes_height)


class RevisionBlock:
    """
    Revision history block for tracking drawing changes.
    """

    def __init__(self, position: Tuple[float, float], width: float = 4.0):
        self.position = position
        self.width = width
        self.row_height = 0.3
        self.header_height = 0.4

    def get_geometry(self, revisions: List[Dict[str, str]]) -> List[Any]:
        """
        Get geometry for revision block.

        Args:
            revisions: List of revision dicts with keys: rev, date, description, by

        Returns:
            List of lines and text for drawing
        """
        from ..drawings.base_drawing import Line2D, Text2D

        geometry = []
        x, y = self.position

        # Determine height based on number of revisions
        num_rows = len(revisions) + 1  # +1 for header
        total_height = self.header_height + (num_rows - 1) * self.row_height

        # Border
        geometry.append(Line2D((x, y), (x + self.width, y)))
        geometry.append(Line2D((x + self.width, y), (x + self.width, y + total_height)))
        geometry.append(Line2D((x + self.width, y + total_height), (x, y + total_height)))
        geometry.append(Line2D((x, y + total_height), (x, y)))

        # Column dividers (Rev | Date | Description | By)
        col1_width = 0.5  # Rev
        col2_width = 1.0  # Date
        col3_width = 1.8  # Description
        col4_width = 0.7  # By

        x1 = x + col1_width
        x2 = x1 + col2_width
        x3 = x2 + col3_width

        geometry.append(Line2D((x1, y), (x1, y + total_height)))
        geometry.append(Line2D((x2, y), (x2, y + total_height)))
        geometry.append(Line2D((x3, y), (x3, y + total_height)))

        # Header row
        y_header = y + total_height - self.header_height
        geometry.append(Line2D((x, y_header), (x + self.width, y_header)))

        # Header text
        geometry.append(Text2D((x + 0.1, y_header + 0.25), "REV", height=0.10))
        geometry.append(Text2D((x1 + 0.1, y_header + 0.25), "DATE", height=0.10))
        geometry.append(Text2D((x2 + 0.1, y_header + 0.25), "DESCRIPTION", height=0.10))
        geometry.append(Text2D((x3 + 0.1, y_header + 0.25), "BY", height=0.10))

        # Revision rows
        for i, rev in enumerate(revisions):
            y_row = y_header - (i + 1) * self.row_height
            geometry.append(Line2D((x, y_row), (x + self.width, y_row)))

            # Row data
            geometry.append(Text2D((x + 0.1, y_row + 0.15),
                                  rev.get('rev', ''), height=0.10))
            geometry.append(Text2D((x1 + 0.1, y_row + 0.15),
                                  rev.get('date', ''), height=0.08))
            geometry.append(Text2D((x2 + 0.1, y_row + 0.15),
                                  rev.get('description', ''), height=0.08))
            geometry.append(Text2D((x3 + 0.1, y_row + 0.15),
                                  rev.get('by', ''), height=0.08))

        return geometry
