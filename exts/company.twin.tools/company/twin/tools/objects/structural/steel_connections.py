from typing import Dict, Any, List, Tuple, Optional
import build123d as bd

class ConnectionRecipe:
    """
    Defines the parameters and logic for a specific connection type.
    """
    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.data = data

    @property
    def setback(self) -> float:
        return self.data.get('constraints', {}).get('setback', 0.5)

    def get_angle_size(self, beam_depth: float) -> Tuple[str, float, float, float]:
        """
        Returns (Name, Leg1, Leg2, Thickness) based on beam depth rules.
        """
        # Simplistic rule engine implementation
        rules = self.data.get('details', [])
        for rule in rules:
            condition = rule.get('condition')
            # Evaluate condition (e.g. "depth < 12")
            # For now, hardcoded safe evaluation
            limit = rule.get('max_depth')
            if limit and beam_depth < limit:
                return rule['angle']
            if not limit: # Default/Catch-all
                return rule['angle']
        return ("L4x4x1/4", 4.0, 4.0, 0.25) # Fallback

class ConnectionSolver:
    """
    Solves geometry for connections.
    """
    
    # Standard Recipes Library
    RECIPES = {
        "double_angle_shear": {
            "constraints": {
                "setback": 0.5,
                "coping": {"top": "flush", "bottom": "flush"}
            },
            "details": [
                {"max_depth": 12.0, "angle": ("L3x3x1/4", 3.0, 3.0, 0.25)},
                {"angle": ("L4x4x3/8", 4.0, 4.0, 0.375)}
            ]
        },
        "seated_shear": {
            "constraints": {
                "setback": 0.75,
                "coping": {"top": "flush"}
            },
            "details": [
                 {"angle": ("L4x4x3/8", 4.0, 4.0, 0.375)}
            ]
        }
    }

    @staticmethod
    def solve(
        support_profile: Dict[str, Any], 
        beam_profile: Dict[str, Any], 
        recipe_name: str = "double_angle_shear"
    ) -> Dict[str, Any]:
        """
        Generates connection parts and cuts.
        
        Args:
            support_profile: AISC data for support (Column)
            beam_profile: AISC data for beam (Header)
            recipe_name: Type of connection
            
        Returns:
            Dict with:
            - 'parts': List of (name, solid, loc) tuples
            - 'cuts': List of (solid, loc) to subtract from beam
            - 'setback': The applied setback distance
        """
        recipe_data = ConnectionSolver.RECIPES.get(recipe_name, ConnectionSolver.RECIPES['double_angle_shear'])
        recipe = ConnectionRecipe(recipe_name, recipe_data)
        
        results = {
            'parts': [],
            'cuts': [],
            'setback': recipe.setback
        }
        
        beam_depth = beam_profile['depth_d']
        beam_web_thk = beam_profile['web_thickness_tw']
        
        # 1. Determine Angle Size
        angle_name, leg1, leg2, thk = recipe.get_angle_size(beam_depth)
        
        # 2. Generate Parts (Double Angle)
        if recipe_name == "double_angle_shear":
            # Length of angle usually depends on T (distance between fillets)
            # T = d - 2*k.
            # Angle length usually T / 3-ish inches increments?
            # Let's approximate: Length = Beam Depth / 2 (min) or Depth - 3"
            angle_len = beam_depth - 3.0
            if angle_len < 3.0: angle_len = 3.0
            
            # Create Angle Solid
            angle_solid = ConnectionSolver._create_angle_solid(leg1, leg2, thk, angle_len)
            
            # Position relative to Beam End
            # Double Angle: One on each side of Web.
            # Back of angle (Leg1 outer face) aligns with Beam End ( + setback? No, usually flush with beam end, setback is gap to column).
            # If Setback is 0.5, Beam End is at X=0.5 relative to Col Face.
            # Angles are usually bolted to Web.
            # Leg2 (outstanding) bolts to Column.
            # So Leg2 Back Face must be at X=0 (Column Face).
            # Beam Web starts at X=Setback.
            # So Angle Position:
            # X = 0 (against Support)
            # Y = Usually centered on Beam Web? Or Top-Down?
            # Let's Center vertically on Beam.
            
            # Left Angle (Z > 0 side of web)
            # Leg2 aligns with X=0. Leg1 aligns with Web Face (Z = tw/2).
            # Angle geometry: Leg1 along X, Leg2 along Y... wait, _create_angle_solid needs to be known.
            # Let's assume standard L extrusion Z+
            
            # We construct angles in place.
            # Angle 1:
            #   Leg against Support (Outstanding leg)
            #   Leg against Beam Web
            
            # Left Angle:
            #   Z-pos: beam_web_thk/2
            #   X-pos: 0 (Support Face)
            #   Y-pos: centered? -angle_len/2 relative to beam center.
            
            results['parts'].append({
                'name': f'angle_left_{angle_name}',
                'solid': angle_solid,
                'location': 'left' # Solver just returns generic "left/right", caller places
            })
            results['parts'].append({
                'name': f'angle_right_{angle_name}',
                'solid': angle_solid,
                'location': 'right' 
            })
            
            # Define specific transform data for the caller to specific usage
            results['angle_params'] = {
                'leg1': leg1,
                'leg2': leg2,
                'thickness': thk,
                'length': angle_len,
                'width_offset': beam_web_thk/2
            }

        elif recipe_name == "seated_shear":
            # Seat Angle (Bottom) + Top Stabilizer
            
            # Seat
            angle_name, leg_v, leg_h, thk = recipe.get_angle_size(beam_depth)
            # Seat width = Beam Flange Width + ??
            seat_width = beam_profile['flange_width_bf'] + 1.0
            
            seat_solid = ConnectionSolver._create_angle_solid(leg_h, leg_v, thk, seat_width)
            
            results['parts'].append({
                'name': 'seat_angle',
                'solid': seat_solid,
                'type': 'seat',
                'params': {'leg_v': leg_v, 'leg_h': leg_h, 'thk': thk, 'width': seat_width}
            })
            
            # Top Clip (Stabilizer)
            # Usually smaller angle. L4x4x1/4?
            clip_solid = ConnectionSolver._create_angle_solid(4.0, 4.0, 0.25, 4.0) # usually 4" wide strip
            results['parts'].append({
                'name': 'top_clip',
                'solid': clip_solid,
                'type': 'clip',
                'params': {'leg_v': 4.0, 'leg_h': 4.0, 'thk': 0.25, 'width': 4.0}
            })

            # Coping?
            # If Seated, beam sits on seat.
            # Setback applies.
            
        return results

    @staticmethod
    def _create_angle_solid(leg1: float, leg2: float, thk: float, length: float) -> bd.Solid:
        """
        Creates L-shape.
        Leg1: Horizontal (X)
        Leg2: Vertical (Y)
        Length: Extrusion (Z)
        Origin: Outer Corner.
        """
        with bd.BuildSketch() as sketch:
            with bd.Locations((leg1/2, leg2/2)):
                bd.Rectangle(leg1, leg2)
            
            # Subtract inner 
            # Inner corner is at (thk, thk).
            # Rect size: (leg1-thk, leg2-thk)
            # Center of that rect: thk + (leg1-thk)/2 = (leg1+thk)/2
            with bd.Locations(((leg1+thk)/2, (leg2+thk)/2)):
                bd.Rectangle(leg1-thk, leg2-thk, mode=bd.Mode.SUBTRACT)
        
        solid = bd.extrude(sketch.sketch, amount=length)
        # Verify orientation:
        # Sketch is XY. Extrude Z.
        # Leg1 is X axis. Leg2 is Y axis.
        return solid
