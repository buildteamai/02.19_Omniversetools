import build123d as bd
from typing import List, Dict, Any

class WideFlangeGenerator:
    """
    Generator for AISC Wide Flange (W-shape) steel beams.
    """

    @staticmethod
    def create(
        depth: float,
        flange_width: float,
        flange_thickness: float,
        web_thickness: float,
        fillet_radius: float,
        length: float,
        features: List[Dict[str, Any]] = None
    ) -> bd.Solid:
        """
        Creates a wide flange I-beam with specified dimensions.

        Args:
            depth (float): Overall beam depth (d) in inches
            flange_width (float): Flange width (bf) in inches
            flange_thickness (float): Flange thickness (tf) in inches
            web_thickness (float): Web thickness (tw) in inches
            fillet_radius (float): Fillet radius between web and flange (k) in inches
            length (float): Beam length in inches
            features (List[Dict]): Optional list of features (connectors, holes, etc.)

        Returns:
            bd.Solid: The generated wide flange beam
        """

        print(f"[WideFlange] Creating beam: d={depth}\", bf={flange_width}\", L={length}\"")

        # Create the I-beam profile in XY plane
        # Origin at center of web
        with bd.BuildSketch() as profile:
            # Bottom flange
            with bd.Locations((0, -depth/2 + flange_thickness/2)):
                bd.Rectangle(flange_width, flange_thickness)

            # Web
            bd.Rectangle(web_thickness, depth - 2*flange_thickness)

            # Top flange
            with bd.Locations((0, depth/2 - flange_thickness/2)):
                bd.Rectangle(flange_width, flange_thickness)

        # Extrude along Z-axis to create beam length
        solid = bd.extrude(profile.sketch, amount=length)

        # Apply fillets to web-flange intersections
        if fillet_radius > 0:
            try:
                # Get edges at web-flange junctions
                edges_to_fillet = WideFlangeGenerator._get_fillet_edges(solid, depth, web_thickness, length)
                if edges_to_fillet:
                    solid = solid.fillet(fillet_radius, edges_to_fillet)
                    print(f"[WideFlange] Applied {len(edges_to_fillet)} fillets (r={fillet_radius}\")")
            except Exception as e:
                print(f"[WideFlange] Warning: Could not apply fillets: {e}")

        # Apply features if provided
        if features:
            for feature in features:
                if feature.get('enabled', True):
                    solid = WideFlangeGenerator._apply_feature(solid, feature, depth, flange_width, length)

        return solid

    @staticmethod
    def _get_fillet_edges(solid: bd.Solid, depth: float, web_thickness: float, length: float) -> List:
        """
        Identifies edges at web-flange junctions for filleting.

        These are the longitudinal edges where web meets flanges.
        """
        all_edges = solid.edges()
        fillet_edges = []

        tolerance = 0.1
        half_web = web_thickness / 2

        # Look for edges that:
        # 1. Run along the length (Z-axis)
        # 2. Are at the web-flange junction (X ≈ ±web_thickness/2, Y ≈ specific height)

        for edge in all_edges:
            try:
                bbox = edge.bounding_box()

                # Check if edge runs along length (large Z extent)
                dz = abs(bbox.max.Z - bbox.min.Z)
                dx = abs(bbox.max.X - bbox.min.X)
                dy = abs(bbox.max.Y - bbox.min.Y)

                # Edge should be mostly along Z axis
                if dz > length * 0.8 and dx < tolerance and dy < tolerance:
                    center_x = (bbox.min.X + bbox.max.X) / 2
                    center_y = (bbox.min.Y + bbox.max.Y) / 2

                    # Check if at web edge (X ≈ ±half_web)
                    if abs(abs(center_x) - half_web) < tolerance:
                        fillet_edges.append(edge)

            except Exception as e:
                pass

        print(f"[WideFlange] Found {len(fillet_edges)} fillet edges")
        return fillet_edges

    @staticmethod
    def _apply_feature(solid: bd.Solid, feature: Dict[str, Any], depth: float, flange_width: float, length: float) -> bd.Solid:
        """
        Applies a feature (connector, hole, etc.) to the beam.

        Args:
            solid: The beam solid to modify
            feature: Feature definition dict
            depth: Beam depth
            flange_width: Beam flange width
            length: Beam length

        Returns:
            Modified solid
        """
        feature_type = feature.get('type')

        if feature_type == 'bolt_holes':
            solid = WideFlangeGenerator._apply_bolt_holes(solid, feature, depth, flange_width, length)
        elif feature_type == 'end_plate':
            solid = WideFlangeGenerator._apply_end_plate(solid, feature, depth, flange_width, length)
        elif feature_type == 'cope':
            solid = WideFlangeGenerator._apply_cope(solid, feature, depth, flange_width, length)

        return solid

    @staticmethod
    def _apply_bolt_holes(solid: bd.Solid, feature: Dict[str, Any], depth: float, flange_width: float, length: float) -> bd.Solid:
        """
        Adds bolt holes to the beam (web or flange).
        """
        location = feature.get('location', 'web')  # 'web', 'top_flange', 'bottom_flange'
        hole_diameter = feature.get('diameter', 0.875)  # 7/8" for 3/4" bolt
        position = feature.get('position', 'end')  # 'end', 'center', or distance from start
        spacing = feature.get('spacing', 3.0)  # Vertical spacing for multiple holes
        count = feature.get('count', 2)  # Number of holes

        print(f"[WideFlange Feature] Adding {count} bolt holes: location={location}, d={hole_diameter}\"")

        try:
            # Determine Z position along beam
            if position == 'end':
                z_pos = length - 2.0  # 2" from end
            elif position == 'start':
                z_pos = 2.0
            elif position == 'center':
                z_pos = length / 2
            else:
                z_pos = float(position)

            # Create holes based on location
            for i in range(count):
                if location == 'web':
                    # Holes in web, vertically spaced
                    y_offset = (i - (count - 1) / 2) * spacing
                    hole_center = (0, y_offset, z_pos)

                    # Create cylinder along X-axis (through web thickness)
                    with bd.BuildSketch(bd.Plane.YZ.offset(hole_diameter)) as hole_sketch:
                        with bd.Locations((y_offset, z_pos)):
                            bd.Circle(hole_diameter / 2)

                    hole = bd.extrude(hole_sketch.sketch, amount=hole_diameter * 2, dir=(-1, 0, 0))
                    solid = solid - hole

                elif location == 'top_flange':
                    # Holes in top flange
                    x_offset = (i - (count - 1) / 2) * spacing
                    hole_center = (x_offset, depth / 2, z_pos)

                    with bd.BuildSketch(bd.Plane.XZ.offset(depth / 2 + hole_diameter)) as hole_sketch:
                        with bd.Locations((x_offset, z_pos)):
                            bd.Circle(hole_diameter / 2)

                    hole = bd.extrude(hole_sketch.sketch, amount=hole_diameter * 2, dir=(0, -1, 0))
                    solid = solid - hole

            print(f"[WideFlange Feature] Applied {count} bolt holes successfully")

        except Exception as e:
            print(f"[WideFlange Feature] Error adding bolt holes: {e}")
            import traceback
            traceback.print_exc()

        return solid

    @staticmethod
    def _apply_end_plate(solid: bd.Solid, feature: Dict[str, Any], depth: float, flange_width: float, length: float) -> bd.Solid:
        """
        Adds an end plate connection to the beam.
        """
        end = feature.get('end', 'start')  # 'start' or 'end'
        plate_thickness = feature.get('thickness', 0.5)  # 1/2" plate
        plate_height = feature.get('height', depth + 2)  # Extends beyond beam
        plate_width = feature.get('width', flange_width)

        print(f"[WideFlange Feature] Adding end plate: {end}, t={plate_thickness}\"")

        try:
            # Determine Z position
            if end == 'start':
                z_pos = -plate_thickness / 2
            else:
                z_pos = length + plate_thickness / 2

            # Create end plate
            with bd.BuildSketch(bd.Plane.XY.offset(z_pos)) as plate_sketch:
                bd.Rectangle(plate_width, plate_height)

            plate = bd.extrude(plate_sketch.sketch, amount=plate_thickness)
            solid = solid + plate

            print(f"[WideFlange Feature] Applied end plate successfully")

        except Exception as e:
            print(f"[WideFlange Feature] Error adding end plate: {e}")
            import traceback
            traceback.print_exc()

        return solid

    @staticmethod
    def _apply_cope(solid: bd.Solid, feature: Dict[str, Any], depth: float, flange_width: float, length: float) -> bd.Solid:
        """
        Adds a cope cut (notch in flange) for beam-to-beam connections.
        """
        end = feature.get('end', 'start')
        flange = feature.get('flange', 'top')  # 'top' or 'bottom'
        cope_depth = feature.get('depth', 2.0)  # How far into beam
        cope_height = feature.get('height', 1.5)  # How much of flange to remove

        print(f"[WideFlange Feature] Adding cope: {flange} flange, {end} end")

        try:
            # Determine position
            if end == 'start':
                z_start = 0
            else:
                z_start = length - cope_depth

            if flange == 'top':
                y_start = depth / 2 - cope_height
                cope_box = bd.Box(flange_width, cope_height, cope_depth,
                                 align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN))
                cope_box = cope_box.translate((0, y_start, z_start))
            else:
                y_start = -depth / 2
                cope_box = bd.Box(flange_width, cope_height, cope_depth,
                                 align=(bd.Align.CENTER, bd.Align.MIN, bd.Align.MIN))
                cope_box = cope_box.translate((0, y_start, z_start))

            solid = solid - cope_box
            print(f"[WideFlange Feature] Applied cope successfully")

        except Exception as e:
            print(f"[WideFlange Feature] Error adding cope: {e}")
            import traceback
            traceback.print_exc()

        return solid

    @staticmethod
    def create_from_aisc(aisc_data: Dict[str, Any], length: float, features: List[Dict[str, Any]] = None) -> bd.Solid:
        """
        Creates a wide flange beam from AISC data dictionary.

        Args:
            aisc_data: Dictionary with AISC dimensions
            length: Beam length in inches
            features: Optional features list

        Returns:
            bd.Solid: The generated beam
        """
        return WideFlangeGenerator.create(
            depth=aisc_data['depth_d'],
            flange_width=aisc_data['flange_width_bf'],
            flange_thickness=aisc_data['flange_thickness_tf'],
            web_thickness=aisc_data['web_thickness_tw'],
            fillet_radius=aisc_data.get('fillet_radius_k', 0.5),
            length=length,
            features=features
        )
