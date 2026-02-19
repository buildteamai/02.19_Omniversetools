"""
Base drawing class for fabrication shop drawings.

Provides abstract interface for generating multi-view drawings with dimensions,
GD&T callouts, and cut lists.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DrawingMetadata:
    """Metadata for a fabrication drawing"""
    project_name: str = "Untitled Project"
    drawing_title: str = "Steel Fabrication Drawing"
    drawing_number: str = "S-001"
    engineer: str = ""
    designer: str = "BuildTeamAI"
    checker: str = ""
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    revision: str = "A"
    scale: str = "1:10"
    units: str = "inches"
    notes: List[str] = field(default_factory=list)


@dataclass
class ViewConfig:
    """Configuration for a drawing view"""
    name: str
    position: Tuple[float, float]  # (x, y) in drawing space
    scale: float
    show_dimensions: bool = True
    show_hidden_lines: bool = False


@dataclass
class Dimension:
    """Represents a dimension on a drawing"""
    start_point: Tuple[float, float]
    end_point: Tuple[float, float]
    value: float
    label: Optional[str] = None
    extension_line_offset: float = 0.5
    text_offset: float = 0.25


@dataclass
class GDTCallout:
    """Geometric Dimensioning and Tolerancing callout"""
    position: Tuple[float, float]
    symbol: str  # e.g., "⊥", "⌭", "○", etc.
    tolerance: float
    datum: Optional[str] = None
    feature: str = ""


@dataclass
class CutListItem:
    """Item in the cut list / bill of materials"""
    mark: str
    quantity: int
    description: str
    material: str
    length: Optional[float] = None
    weight: Optional[float] = None
    notes: str = ""


class BaseDrawing(ABC):
    """
    Abstract base class for fabrication drawings.

    Subclasses implement specific component types (wide flange, channel, etc.)
    """

    def __init__(self, component_data: Dict[str, Any], metadata: Optional[DrawingMetadata] = None):
        """
        Initialize drawing.

        Args:
            component_data: Dictionary containing component geometry and parameters
            metadata: Drawing metadata (title block info)
        """
        self.component_data = component_data
        self.metadata = metadata or DrawingMetadata()

        self.views: List[ViewConfig] = []
        self.dimensions: List[Dimension] = []
        self.gdt_callouts: List[GDTCallout] = []
        self.cut_list: List[CutListItem] = []
        self.notes: List[str] = []

    @abstractmethod
    def generate_views(self) -> List[ViewConfig]:
        """
        Generate view configurations for this component.

        Returns:
            List of ViewConfig objects defining drawing views
        """
        pass

    @abstractmethod
    def generate_dimensions(self) -> List[Dimension]:
        """
        Generate dimension annotations for this component.

        Returns:
            List of Dimension objects
        """
        pass

    @abstractmethod
    def generate_gdt_callouts(self) -> List[GDTCallout]:
        """
        Generate GD&T callouts for this component.

        Returns:
            List of GDTCallout objects
        """
        pass

    @abstractmethod
    def generate_cut_list(self) -> List[CutListItem]:
        """
        Generate cut list / bill of materials.

        Returns:
            List of CutListItem objects
        """
        pass

    @abstractmethod
    def get_main_view_geometry(self, view_name: str) -> List[Any]:
        """
        Get geometry (lines, arcs, etc.) for a specific view.

        Args:
            view_name: Name of the view (e.g., "front", "side", "top")

        Returns:
            List of geometry primitives for the view
        """
        pass

    def prepare_drawing(self) -> Dict[str, Any]:
        """
        Prepare complete drawing data for export.

        Returns:
            Dictionary containing all drawing data
        """
        self.views = self.generate_views()
        self.dimensions = self.generate_dimensions()
        self.gdt_callouts = self.generate_gdt_callouts()
        self.cut_list = self.generate_cut_list()

        return {
            'metadata': self.metadata,
            'views': self.views,
            'dimensions': self.dimensions,
            'gdt_callouts': self.gdt_callouts,
            'cut_list': self.cut_list,
            'notes': self.notes
        }

    def add_note(self, note: str):
        """Add a note to the drawing"""
        self.notes.append(note)

    def add_standard_notes(self):
        """Add standard fabrication notes"""
        standard_notes = [
            "ALL DIMENSIONS IN INCHES UNLESS OTHERWISE NOTED",
            "MATERIAL: ASTM A992 STEEL UNLESS OTHERWISE NOTED",
            "WELDING: AWS D1.1 STRUCTURAL WELDING CODE",
            "BOLT HOLES: STD HOLES UNLESS OTHERWISE NOTED",
            "PAINT: ONE COAT SHOP PRIMER AFTER FABRICATION",
            "FABRICATOR TO VERIFY ALL DIMENSIONS IN FIELD"
        ]
        self.notes.extend(standard_notes)


class Line2D:
    """Simple 2D line for drawing"""
    def __init__(self, start: Tuple[float, float], end: Tuple[float, float],
                 line_type: str = "continuous"):
        self.start = start
        self.end = end
        self.line_type = line_type  # "continuous", "hidden", "center"


class Arc2D:
    """Simple 2D arc for drawing"""
    def __init__(self, center: Tuple[float, float], radius: float,
                 start_angle: float, end_angle: float):
        self.center = center
        self.radius = radius
        self.start_angle = start_angle
        self.end_angle = end_angle


class Circle2D:
    """Simple 2D circle for drawing"""
    def __init__(self, center: Tuple[float, float], radius: float):
        self.center = center
        self.radius = radius


class Text2D:
    """Simple 2D text for drawing"""
    def __init__(self, position: Tuple[float, float], text: str,
                 height: float = 0.125, rotation: float = 0.0):
        self.position = position
        self.text = text
        self.height = height
        self.rotation = rotation
