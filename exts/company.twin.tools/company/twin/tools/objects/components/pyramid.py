import build123d as bd
import math
from typing import List, Dict, Any

class PyramidGenerator:
    """
    Generator for Pyramid (or Tapered Extrusion) shapes with feature support.
    """

    @staticmethod
    def create(base: float, height: float, taper_angle: float, features: List[Dict[str, Any]] = None) -> bd.Solid:
        """
        Creates a pyramid-like shape by extruding a square base with a taper angle.

        Args:
            base (float): Length of the square base side.
            height (float): Extrusion height.
            taper_angle (float): Taper angle in degrees.
                                 Positive values might flare out, negative flare in,
                                 depending on build123d version.
                                 Typically negative for pyramid.
            features (List[Dict]): Optional list of features to apply.
                                   Each feature is a dict like:
                                   {'type': 'fillet', 'edges': 'vertical', 'radius': 5.0, 'enabled': True}

        Returns:
            bd.Solid: The generated solid.
        """
        # Calculate top dimension
        delta = height * math.tan(math.radians(taper_angle))
        top_base = base + (2.0 * delta)

        # Clamp top base to be at least a point (0.0) to avoid invalid geometry if it crosses
        if top_base < 0.001:
            top_base = 0.001 # Practically a point

        # Create geometric objects
        plane_xz = bd.Plane(origin=(0,0,0), z_dir=(0,1,0))
        rect_base = plane_xz * bd.Rectangle(base, base)

        plane_top = bd.Plane(origin=(0,height,0), z_dir=(0,1,0))
        rect_top = plane_top * bd.Rectangle(top_base, top_base)

        # Loft
        solid = bd.loft([rect_base, rect_top])

        # Apply features if provided
        if features:
            for feature in features:
                if feature.get('enabled', True):
                    solid = PyramidGenerator._apply_feature(solid, feature, base, height, top_base)

        return solid

    @staticmethod
    def _apply_feature(solid: bd.Solid, feature: Dict[str, Any], base: float, height: float, top_base: float) -> bd.Solid:
        """
        Applies a single feature to the solid.

        Args:
            solid: The solid to modify
            feature: Feature definition dict
            base: Base dimension (for edge identification)
            height: Height (for edge identification)
            top_base: Top dimension (for edge identification)

        Returns:
            Modified solid
        """
        feature_type = feature.get('type')

        if feature_type == 'fillet':
            edge_group = feature.get('edges', 'vertical')
            radius = feature.get('radius', 1.0)

            # Get edges for the semantic group
            edges_to_fillet = PyramidGenerator._get_semantic_edges(solid, edge_group, base, height, top_base)

            print(f"[Pyramid Feature] Applying fillet: {edge_group} edges, radius={radius}")
            print(f"[Pyramid Feature] Found {len(edges_to_fillet)} edges to fillet")

            if edges_to_fillet:
                try:
                    # build123d fillet syntax: fillet(radius, edge_list)
                    solid = solid.fillet(radius, edges_to_fillet)
                    print(f"[Pyramid Feature] Successfully applied fillet")
                except Exception as e:
                    print(f"[Pyramid Feature] Error: Could not apply fillet to {edge_group} edges: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[Pyramid Feature] Warning: No {edge_group} edges found to fillet")

        elif feature_type == 'sketch':
            solid = PyramidGenerator._apply_sketch(solid, feature)
            
        return solid

    @staticmethod
    def _apply_sketch(solid: bd.Solid, feature: Dict[str, Any]) -> bd.Solid:
        """
        Applies a sketch-based operation (cut/extrude) to a face.
        """
        face_name = feature.get('face', 'front')
        profile_type = feature.get('profile', 'circle')
        operation = feature.get('operation', 'cut')
        amount = feature.get('amount', 10.0)
        
        # Dimensions
        dims = feature.get('dimensions', {})
        if isinstance(dims, (int, float)): 
            dims = {'radius': dims} # fallback
            
        # Center offset (u, v) on the face plane
        center = feature.get('center', [0, 0])
        
        # 1. Get the Target Face
        target_face = PyramidGenerator._get_semantic_face(solid, face_name)
        if target_face is None:
            print(f"[Pyramid Feature] Error: Could not find face '{face_name}'")
            return solid
            
        # 2. Define Workplane from Face
        workplane = bd.Plane(target_face)
        
        # 3. Create Sketch on Plane
        with bd.BuildSketch(workplane) as sketch:
            with bd.Locations((center[0], center[1])):
                if profile_type == 'circle':
                    r = dims.get('radius', 10.0)
                    bd.Circle(radius=r)
                elif profile_type == 'rectangle':
                    w = dims.get('width', 20.0)
                    h = dims.get('height', 20.0)
                    bd.Rectangle(width=w, height=h)
        
        # 4. Extrude the sketch
        print(f"[Pyramid Feature] Applying {operation} on {face_name} face. Amount={amount}")
        
        if operation == 'cut':
            # Cut requires extruding INTO the solid.
            # Normal points OUT. So extrude matches Normal.
            # To cut, we extrude in -Normal direction (Negative amount)
            # Ensure amount is positive for input, so -amount cuts in.
            tool = bd.extrude(sketch.sketch, amount=-abs(amount))
            solid = solid - tool
            
        elif operation == 'extrude':
            # Add material outwards
            tool = bd.extrude(sketch.sketch, amount=abs(amount))
            solid = solid + tool
            
        return solid

    @staticmethod
    def _get_semantic_face(solid: bd.Solid, face_name: str) -> bd.Face:
        """
        Finds a face based on semantic name.
        """
        all_faces = solid.faces()
        
        best_face = None
        max_score = -999.0
        
        for face in all_faces:
            n = face.normal_at(face.center())
            score = -999.0
            
            if face_name == 'base':
                score = -n.Y # Normal Down
            elif face_name == 'top':
                score = n.Y # Normal Up
            elif face_name == 'front':
                 score = n.Z # Normal +Z
            elif face_name == 'back':
                 score = -n.Z # Normal -Z
            elif face_name == 'right':
                 score = n.X # Normal +X
            elif face_name == 'left':
                 score = -n.X # Normal -X
            
            if score > max_score:
                max_score = score
                best_face = face
                
        if max_score < 0.5: # Tolerance
             print(f"[Pyramid Feature] Warning: Could not find good candidate for '{face_name}' (Best Score: {max_score})")
             if face_name == 'top' and max_score < 0.1:
                 return None
                 
        return best_face

    @staticmethod
    def _get_semantic_edges(solid: bd.Solid, edge_group: str, base: float, height: float, top_base: float) -> List:
        """
        Identifies edges based on semantic grouping.

        Args:
            solid: The solid to get edges from
            edge_group: One of 'vertical', 'base', 'top', or 'all'
            base: Base dimension
            height: Height
            top_base: Top dimension

        Returns:
            List of edges matching the semantic group
        """
        all_edges = solid.edges()
        selected_edges = []

        print(f"[Edge Selection] Looking for '{edge_group}' edges from {len(all_edges)} total edges")

        tolerance = 0.1

        if edge_group == 'vertical':
            # Vertical edges connect base to top (edges that are approximately vertical)
            for edge in all_edges:
                try:
                    # Get edge bounding box center
                    bbox = edge.bounding_box()
                    center_y = (bbox.min.Y + bbox.max.Y) / 2

                    # Get edge length components
                    dx = abs(bbox.max.X - bbox.min.X)
                    dy = abs(bbox.max.Y - bbox.min.Y)
                    dz = abs(bbox.max.Z - bbox.min.Z)

                    # Vertical edges have large Y component, small X and Z
                    # And center Y should be around mid-height
                    if dy > height * 0.5 and dx < base * 0.3 and dz < base * 0.3:
                        selected_edges.append(edge)
                except Exception as e:
                    print(f"[Edge Selection] Error checking vertical edge: {e}")
                    pass

        elif edge_group == 'base':
            # Base edges are at Y ≈ 0
            for edge in all_edges:
                try:
                    bbox = edge.bounding_box()
                    center_y = (bbox.min.Y + bbox.max.Y) / 2
                    if abs(center_y) < tolerance:
                        selected_edges.append(edge)
                except Exception as e:
                    print(f"[Edge Selection] Error checking base edge: {e}")
                    pass

        elif edge_group == 'top':
            # Top edges are at Y ≈ height
            for edge in all_edges:
                try:
                    bbox = edge.bounding_box()
                    center_y = (bbox.min.Y + bbox.max.Y) / 2
                    if abs(center_y - height) < tolerance:
                        selected_edges.append(edge)
                except Exception as e:
                    print(f"[Edge Selection] Error checking top edge: {e}")
                    pass

        elif edge_group == 'all':
            selected_edges = list(all_edges)

        print(f"[Edge Selection] Selected {len(selected_edges)} {edge_group} edges")
        return selected_edges
