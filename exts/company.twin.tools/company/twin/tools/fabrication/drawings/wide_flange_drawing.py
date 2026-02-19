"""
Wide Flange beam fabrication drawing generator.

Generates AISC-compliant shop drawings for W-shape beams.
"""

from typing import Dict, List, Tuple, Any, Optional
from .base_drawing import (
    BaseDrawing, DrawingMetadata, ViewConfig, Dimension,
    GDTCallout, CutListItem, Line2D, Circle2D, Text2D
)


class WideFlangeDrawing(BaseDrawing):
    """
    Fabrication drawing generator for wide flange beams.

    Generates multi-view drawings with dimensions, GD&T, and cut list.
    """

    def __init__(self, component_data: Dict[str, Any], metadata: Optional[DrawingMetadata] = None):
        super().__init__(component_data, metadata)

        # Extract beam parameters
        self.designation = component_data.get('designation', 'W8x24')
        self.length = component_data.get('length', 120.0)
        self.aisc_data = component_data.get('aisc_data', {})
        self.features = component_data.get('features', [])

        # AISC dimensions
        self.depth = self.aisc_data.get('depth_d', 8.0)
        self.flange_width = self.aisc_data.get('flange_width_bf', 6.5)
        self.flange_thickness = self.aisc_data.get('flange_thickness_tf', 0.4)
        self.web_thickness = self.aisc_data.get('web_thickness_tw', 0.25)
        self.weight = self.aisc_data.get('weight_lb_ft', 24)

        # Update metadata title
        if self.metadata.drawing_title == "Steel Fabrication Drawing":
            self.metadata.drawing_title = f"{self.designation} × {self.length/12:.1f}'-0\" Beam"

    def generate_views(self) -> List[ViewConfig]:
        """Generate view configurations"""
        views = [
            ViewConfig(
                name="front",
                position=(2.0, 8.0),
                scale=1.0,
                show_dimensions=True
            ),
            ViewConfig(
                name="side",
                position=(2.0, 4.0),
                scale=0.5,  # Side view often smaller scale due to length
                show_dimensions=True
            ),
            ViewConfig(
                name="end_detail",
                position=(10.0, 8.0),
                scale=2.0,  # Enlarged for detail
                show_dimensions=True
            )
        ]
        return views

    def generate_dimensions(self) -> List[Dimension]:
        """Generate dimension annotations"""
        dimensions = []

        # Front view dimensions (beam profile)
        # Overall depth
        dimensions.append(Dimension(
            start_point=(0, -self.depth/2),
            end_point=(0, self.depth/2),
            value=self.depth,
            label=f"{self.depth:.2f}\" DEPTH"
        ))

        # Flange width
        dimensions.append(Dimension(
            start_point=(-self.flange_width/2, self.depth/2),
            end_point=(self.flange_width/2, self.depth/2),
            value=self.flange_width,
            label=f"{self.flange_width:.3f}\" FLANGE"
        ))

        # Flange thickness
        dimensions.append(Dimension(
            start_point=(-self.flange_width/2 - 0.5, self.depth/2),
            end_point=(-self.flange_width/2 - 0.5, self.depth/2 - self.flange_thickness),
            value=self.flange_thickness,
            label=f"tf={self.flange_thickness:.3f}\""
        ))

        # Web thickness
        dimensions.append(Dimension(
            start_point=(-self.web_thickness/2, 0),
            end_point=(self.web_thickness/2, 0),
            value=self.web_thickness,
            label=f"tw={self.web_thickness:.3f}\""
        ))

        # Side view dimensions (beam length)
        # Overall length
        dimensions.append(Dimension(
            start_point=(0, 0),
            end_point=(self.length, 0),
            value=self.length,
            label=f"{self.length/12:.1f}'-{self.length%12:.0f}\" LENGTH"
        ))

        # Feature dimensions (bolt holes, copes, etc.)
        dimensions.extend(self._generate_feature_dimensions())

        return dimensions

    def _generate_feature_dimensions(self) -> List[Dimension]:
        """Generate dimensions for features (holes, copes, etc.)"""
        dimensions = []

        for feature in self.features:
            if not feature.get('enabled', True):
                continue

            feature_type = feature.get('type')

            if feature_type == 'bolt_holes':
                # Dimension hole spacing and edge distances
                count = feature.get('count', 2)
                spacing = feature.get('spacing', 3.0)
                position = feature.get('position', 'end')

                # Add spacing dimensions
                if count > 1:
                    dimensions.append(Dimension(
                        start_point=(0, 0),
                        end_point=(0, spacing),
                        value=spacing,
                        label=f"{spacing:.2f}\" SPACING (TYP)"
                    ))

            elif feature_type == 'cope':
                cope_depth = feature.get('depth', 2.0)
                cope_height = feature.get('height', 1.5)

                dimensions.append(Dimension(
                    start_point=(0, 0),
                    end_point=(cope_depth, 0),
                    value=cope_depth,
                    label=f"{cope_depth:.2f}\" COPE DEPTH"
                ))

                dimensions.append(Dimension(
                    start_point=(0, 0),
                    end_point=(0, cope_height),
                    value=cope_height,
                    label=f"{cope_height:.2f}\" COPE HEIGHT"
                ))

            elif feature_type == 'end_plate':
                plate_thickness = feature.get('thickness', 0.5)
                dimensions.append(Dimension(
                    start_point=(0, 0),
                    end_point=(plate_thickness, 0),
                    value=plate_thickness,
                    label=f"{plate_thickness:.2f}\" PL"
                ))

        return dimensions

    def generate_gdt_callouts(self) -> List[GDTCallout]:
        """Generate GD&T callouts"""
        callouts = []

        # Perpendicularity of web to flanges
        callouts.append(GDTCallout(
            position=(self.web_thickness/2 + 1.0, 0),
            symbol="⊥",  # Perpendicularity
            tolerance=0.010,
            datum="A",
            feature="Web to Flange"
        ))

        # Flatness of flanges
        callouts.append(GDTCallout(
            position=(0, self.depth/2 + 0.5),
            symbol="⌭",  # Flatness
            tolerance=0.020,
            datum=None,
            feature="Top Flange"
        ))

        callouts.append(GDTCallout(
            position=(0, -self.depth/2 - 0.5),
            symbol="⌭",  # Flatness
            tolerance=0.020,
            datum=None,
            feature="Bottom Flange"
        ))

        # Perpendicularity of end cuts
        callouts.append(GDTCallout(
            position=(0, -self.depth/2 - 1.0),
            symbol="⊥",
            tolerance=0.030,
            datum="B",
            feature="End Cut"
        ))

        return callouts

    def generate_cut_list(self) -> List[CutListItem]:
        """Generate cut list / BOM"""
        cut_list = []

        # Main beam member
        weight_total = (self.weight * self.length) / 12  # Convert to total weight
        cut_list.append(CutListItem(
            mark="B1",
            quantity=1,
            description=f"{self.designation} Wide Flange Beam",
            material="ASTM A992",
            length=self.length,
            weight=weight_total,
            notes=f"{self.length/12:.1f}'-{self.length%12:.0f}\" long"
        ))

        # Features in cut list
        item_number = 2
        for feature in self.features:
            if not feature.get('enabled', True):
                continue

            feature_type = feature.get('type')

            if feature_type == 'end_plate':
                thickness = feature.get('thickness', 0.5)
                height = feature.get('height', self.depth + 2)
                width = feature.get('width', self.flange_width)

                # Estimate weight (steel = 490 lb/ft³ = 0.2836 lb/in³)
                volume = thickness * height * width
                weight = volume * 0.2836

                cut_list.append(CutListItem(
                    mark=f"PL{item_number}",
                    quantity=1,
                    description=f"End Plate {thickness}\" × {height:.2f}\" × {width:.2f}\"",
                    material="ASTM A36",
                    weight=weight,
                    notes=f"Welded to beam end"
                ))
                item_number += 1

            elif feature_type == 'bolt_holes':
                count = feature.get('count', 2)
                diameter = feature.get('diameter', 0.875)
                location = feature.get('location', 'web')

                cut_list.append(CutListItem(
                    mark=f"H{item_number}",
                    quantity=count,
                    description=f"{diameter:.3f}\" Diameter Holes",
                    material="N/A",
                    notes=f"In {location}, see detail"
                ))
                item_number += 1

        return cut_list

    def get_main_view_geometry(self, view_name: str) -> List[Any]:
        """Get geometry for a specific view"""
        geometry = []

        if view_name == "front":
            # Front view: I-beam profile
            geometry.extend(self._generate_front_view())

        elif view_name == "side":
            # Side view: Beam length with features
            geometry.extend(self._generate_side_view())

        elif view_name == "end_detail":
            # Enlarged end detail
            geometry.extend(self._generate_end_detail())

        return geometry

    def _generate_front_view(self) -> List[Any]:
        """Generate front view (I-beam profile)"""
        geometry = []

        half_depth = self.depth / 2
        half_flange = self.flange_width / 2
        half_web = self.web_thickness / 2

        # Bottom flange outline
        geometry.append(Line2D((-half_flange, -half_depth),
                              (half_flange, -half_depth)))
        geometry.append(Line2D((-half_flange, -half_depth + self.flange_thickness),
                              (half_flange, -half_depth + self.flange_thickness)))
        geometry.append(Line2D((-half_flange, -half_depth),
                              (-half_flange, -half_depth + self.flange_thickness)))
        geometry.append(Line2D((half_flange, -half_depth),
                              (half_flange, -half_depth + self.flange_thickness)))

        # Web outline
        geometry.append(Line2D((-half_web, -half_depth + self.flange_thickness),
                              (-half_web, half_depth - self.flange_thickness)))
        geometry.append(Line2D((half_web, -half_depth + self.flange_thickness),
                              (half_web, half_depth - self.flange_thickness)))

        # Top flange outline
        geometry.append(Line2D((-half_flange, half_depth - self.flange_thickness),
                              (half_flange, half_depth - self.flange_thickness)))
        geometry.append(Line2D((-half_flange, half_depth),
                              (half_flange, half_depth)))
        geometry.append(Line2D((-half_flange, half_depth - self.flange_thickness),
                              (-half_flange, half_depth)))
        geometry.append(Line2D((half_flange, half_depth - self.flange_thickness),
                              (half_flange, half_depth)))

        # Add bolt holes in front view if in web
        for feature in self.features:
            if feature.get('type') == 'bolt_holes' and feature.get('location') == 'web':
                if feature.get('enabled', True):
                    count = feature.get('count', 2)
                    spacing = feature.get('spacing', 3.0)
                    diameter = feature.get('diameter', 0.875)

                    for i in range(count):
                        y_pos = (i - (count - 1) / 2) * spacing
                        geometry.append(Circle2D((0, y_pos), diameter / 2))

        return geometry

    def _generate_side_view(self) -> List[Any]:
        """Generate side view (beam length)"""
        geometry = []

        half_depth = self.depth / 2

        # Beam outline
        geometry.append(Line2D((0, -half_depth), (self.length, -half_depth)))
        geometry.append(Line2D((0, half_depth), (self.length, half_depth)))
        geometry.append(Line2D((0, -half_depth), (0, half_depth)))
        geometry.append(Line2D((self.length, -half_depth), (self.length, half_depth)))

        # Centerline
        geometry.append(Line2D((0, 0), (self.length, 0), line_type="center"))

        # Add features to side view
        for feature in self.features:
            if not feature.get('enabled', True):
                continue

            feature_type = feature.get('type')

            if feature_type == 'cope':
                end = feature.get('end', 'start')
                flange = feature.get('flange', 'top')
                depth = feature.get('depth', 2.0)
                height = feature.get('height', 1.5)

                x_start = 0 if end == 'start' else self.length - depth
                y_start = half_depth if flange == 'top' else -half_depth
                y_end = y_start - height if flange == 'top' else y_start + height

                # Draw cope
                geometry.append(Line2D((x_start, y_start), (x_start + depth, y_start)))
                geometry.append(Line2D((x_start + depth, y_start), (x_start + depth, y_end)))
                geometry.append(Line2D((x_start + depth, y_end), (x_start, y_end)))

            elif feature_type == 'end_plate':
                end = feature.get('end', 'start')
                thickness = feature.get('thickness', 0.5)
                height = feature.get('height', self.depth + 2)

                x_pos = -thickness if end == 'start' else self.length
                half_height = height / 2

                # Draw end plate
                geometry.append(Line2D((x_pos, -half_height), (x_pos + thickness, -half_height)))
                geometry.append(Line2D((x_pos + thickness, -half_height),
                                      (x_pos + thickness, half_height)))
                geometry.append(Line2D((x_pos + thickness, half_height), (x_pos, half_height)))
                geometry.append(Line2D((x_pos, half_height), (x_pos, -half_height)))

        return geometry

    def _generate_end_detail(self) -> List[Any]:
        """Generate enlarged end detail"""
        # Similar to front view but enlarged and with more detail
        return self._generate_front_view()

    def add_standard_notes(self):
        """Add standard notes for wide flange beams"""
        super().add_standard_notes()

        # Add W-beam specific notes
        self.add_note(f"MATERIAL: {self.designation} WIDE FLANGE, ASTM A992")
        self.add_note(f"WEIGHT: {self.weight} LB/FT")

        # Feature-specific notes
        has_bolt_holes = any(f.get('type') == 'bolt_holes' for f in self.features)
        has_end_plate = any(f.get('type') == 'end_plate' for f in self.features)
        has_cope = any(f.get('type') == 'cope' for f in self.features)

        if has_bolt_holes:
            self.add_note("BOLT HOLES: STD HOLES PER AISC, DEBURR ALL HOLES")
        if has_end_plate:
            self.add_note("END PLATE: FILLET WELD ALL AROUND, TYP")
        if has_cope:
            self.add_note("COPE: CUT SQUARE, GRIND SMOOTH")
