
from typing import Dict, Any, Tuple, List
import build123d as bd
from company.twin.tools.objects.wide_flange import WideFlangeGenerator
from company.twin.tools.objects.hss_tube import HSSGenerator
from .base_solver import BaseSolver

class FrameSolver(BaseSolver):
    """
    Solver for Structural Steel Frames.
    Calculates exact member lengths and positions based on reactive constraints.
    Handles column rotation and profile changes automatically.
    """
    
    
    def calculate_section_properties(self, profile: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate Section Properties (Ix, Sx, A, r) from dimensions.
        Approximates based on shape (I-Beam or Box).
        """
        # Extract Dimensions
        d = profile.get('depth_d') or profile.get('outer_height', 10.0)
        bf = profile.get('flange_width_bf') or profile.get('outer_width', 10.0)
        tf = profile.get('flange_thickness_tf') or profile.get('wall_thickness', 0.5)
        tw = profile.get('web_thickness_tw') or profile.get('wall_thickness', 0.5)
        name = profile.get('designation', '')
        
        # Area
        # Simplified: Box or I-Beam area
        if 'HSS' in name or 'Tube' in name:
            # Box Area
            outer_area = d * bf
            inner_d = d - 2*tf
            inner_b = bf - 2*tw
            inner_area = inner_d * inner_b
            area = outer_area - inner_area
            
            # Moment of Inertia (Ix) - Strong Axis
            # (b h^3 - bi hi^3) / 12
            ix = (bf * d**3 - inner_b * inner_d**3) / 12.0
            
            # Radius of Gyration (r) approx
            # r = sqrt(I/A)
            r = (ix / area)**0.5 if area > 0 else 1.0
            
        else:
            # I-Beam Approximation (Flanges + Web)
            # Area = 2*bf*tf + (d-2*tf)*tw
            area = 2 * bf * tf + (d - 2*tf) * tw
            
            # Ix = (b h^3 - (b-tw)(h-2tf)^3) / 12
            ix = (bf * d**3 - (bf - tw) * (d - 2*tf)**3) / 12.0
            
            # r approx
            r = (ix / area)**0.5 if area > 0 else 1.0
            
        # Section Modulus (Sx) = Ix / (d/2)
        sx = ix / (d / 2.0)
        
        return {
            'A': area,
            'Ix': ix,
            'Sx': sx,
            'r': r,
            'd': d # Depth
        }

    def _create_member(self, profile: Dict[str, Any], length: float) -> bd.Solid:
        """
        Creates a member solid based on profile type (W-Shape or HSS).
        """
        designation = profile.get('designation', '')
        if designation.startswith('HSS') or 'Tube' in designation:
            return HSSGenerator.create_from_aisc(profile, length=length)
        else:
            return WideFlangeGenerator.create_from_aisc(profile, length=length)

    def solve(self, inputs: Dict[str, Any]) -> Dict[str, Any]:

        """
        Execute the frame solver logic.
        
        Args:
            inputs: Dictionary containing:
                - width (float): Center-to-Center span
                - height (float): Total height (Top of Steel)
                - col_profile (Dict): AISC data for columns
                - header_profile (Dict): AISC data for header
                - col_orientation (float): Rotation in degrees (0 or 90)
                - gap (float): Clearance gap (default 0.5)
                - bp_size (Tuple): (L, W, T) for base plate
                - num_frames (int): Number of frames to array
                - frame_spacing (float): Spacing between frames
                - conn_beam_profile (Dict): AISC data for connecting beams
                
        Returns:
            Dictionary with 'parts', 'transforms', 'anchors', 'metadata'.
        """
        # Validate / Extract Inputs
        width = inputs.get('width', 144.0)
        height = inputs.get('height', 120.0)
        col_profile = inputs.get('col_profile')
        header_profile = inputs.get('header_profile')
        col_orientation = inputs.get('col_orientation', 0.0)
        gap = inputs.get('gap', 0.5)
        bp_size = inputs.get('bp_size', (14.0, 14.0, 0.75))
        point_load_lbs = inputs.get('point_load_lbs', 1000.0) # Center Point Load in lbs
        
        num_frames = inputs.get('num_frames', 1)
        frame_spacing = inputs.get('frame_spacing', 144.0)
        conn_beam_profile = inputs.get('conn_beam_profile')
        
        if not col_profile or not header_profile:
            raise ValueError("Missing profile data for FrameSolver")

        # ---------------------------------------------------------
        # 1. TEMPORARY CONTEXT: Measure Columns
        # ---------------------------------------------------------
        
        # Create a temp column to measure its bounding box in the rotated state
        temp_col = self._create_member(col_profile, length=height)
        
        # Apply orientation (local rotation around Z)
        temp_col = temp_col.rotate(bd.Axis.Z, col_orientation)
        
        # Measure X-extent (Half Width) & Y-extent (for connecting beams)
        bbox = temp_col.bounding_box()
        max_x = bbox.max.X
        min_x = bbox.min.X
        col_half_width = max(abs(max_x), abs(min_x))
        
        # Depth for connecting beams (Local Y, Global Z when upright? No, Column is vertical Z)
        # When column is vertical (Z-up in build123d temp), its "Depth" in the array direction
        # depends on orientation.
        # Orientation 0: Web along X. Flanges along Y. Depth is bounding box Y.
        # Orientation 90: Web along Y. Flanges along X. Depth is bounding box X (relative to original).
        # In the temp_col (Z-up), we rotated by col_orientation.
        # Array direction will be Global Z (in Omniverse/Result) -> which corresponds to build123d Y?
        # Wait, let's check coordinate mapping.
        # "rotate(bd.Axis.X, -90)" creates the upright column in output.
        # build123d Z -> Global Y (Up).
        # build123d X -> Global X (Right).
        # build123d Y -> Global Z (Back/Depth).
        
        # So we need the extent of temp_col along Y axis.
        max_y = bbox.max.Y
        min_y = bbox.min.Y
        col_half_depth = max(abs(max_y), abs(min_y))
        
        # ---------------------------------------------------------
        # 2. CALCULATE HEADER GEOMETRY
        # ---------------------------------------------------------
        header_length = width - (2 * col_half_width) - (2 * gap)
        
        if header_length <= 0:
            raise ValueError(f"Frame width {width} is too narrow for columns with half-width {col_half_width}")
            
        # ---------------------------------------------------------
        # 3. GENERATE GEOMETRY (Y-UP)
        # ---------------------------------------------------------
        parts = {}
        transforms = {}
        anchors = {}
        
        bp_len, bp_wid, bp_thk = bp_size
        
        # -- BASE PLATE GEOMETRY --
        base_plate = bd.Box(
            bp_len, bp_wid, bp_thk,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
        )
        bp_rot = bd.Rotation(-90, 0, 0)
        
        # -- COLUMN GEOMETRY --
        col_length = height - bp_thk
        if col_length <= 0: col_length = 1.0
        col_solid = self._create_member(col_profile, length=col_length)
        if col_orientation != 0:
            col_solid = col_solid.rotate(bd.Axis.Z, col_orientation)
        col_solid = col_solid.rotate(bd.Axis.X, -90)
        
        # -- HEADER GEOMETRY --
        header_depth = header_profile.get("depth_d") or header_profile.get("outer_height", 10.0)
        header_top_y = height
        header_center_y = header_top_y - (header_depth / 2)
        
        h_solid = self._create_member(header_profile, length=header_length)
        h_solid = h_solid.move(bd.Location((0, 0, -header_length/2))) # Center Z
        h_solid = h_solid.rotate(bd.Axis.Y, 90) # Orient along X
        
        # -- CONNECTING BEAM GEOMETRY --
        conn_beam_solid = None
        conn_beam_length = 0.0
        
        if num_frames > 1 and conn_beam_profile:
            # Calculate Length
            # Spacing - (2 * col_half_depth_along_array_axis?)
            # Usually connecting beams frame into the web or flange.
            # We will use "Clear Span": Spacing - Column Depth (2 * half_depth)
            # Assuming flush condition.
            
            conn_beam_length = frame_spacing - (2 * col_half_depth)
            
            # If extremely short or negative, just use spacing (center-to-center) and let them clash?
            # Or clamp to 0?
            if conn_beam_length < 1.0:
                conn_beam_length = frame_spacing # Fallback
            
            conn_beam_solid = self._create_member(conn_beam_profile, length=conn_beam_length)
            
            # Default orientation: Along Z (Array Axis).
            # build123d Extrude is along Z.
            # We need it along Global Z (Depth).
            # Global Y is Up. Global X is Right.
            # So beam should allow Z axis.
            # But create_member usually creates along Z.
            # So it is already along Z!
            
            # Center it?
            conn_beam_solid = conn_beam_solid.move(bd.Location((0, 0, -conn_beam_length/2)))
            
            # Move to location:
            # We need it at Top of Steel? Or flush with Header Top?
            # Align Top of Beam with Top of Column (Height).
            cb_depth = conn_beam_profile.get("depth_d") or conn_beam_profile.get("outer_height", 10.0)
            
            # Align Top:
            # Current Center Z (Global) is 0. Length is along Z.
            # Cross section in XY plane.
            # We want Top of Beam at Height.
            # Current Top Y is cb_depth/2 (if centered).
            # So move Y by Height - cb_depth/2.
            # Actually create_member creates centered on XY?
            # Yes, usually.
            
            cb_center_y = height - (cb_depth / 2)
            conn_beam_solid = conn_beam_solid.move(bd.Location((0, cb_center_y, 0)))


        # ---------------------------------------------------------
        # LOOP FRAMES
        # ---------------------------------------------------------
        
        skip_left = inputs.get('skip_start_col_left', False)
        skip_right = inputs.get('skip_start_col_right', False)
        
        for i in range(num_frames):
            
            z_offset = -i * frame_spacing # Negative Z is usually "into" the screen/scene in some conventions, or positive?
            # USD: Z is forward/back. Let's use negative Z to go "back"? 
            # Or positive? frame_spacing is positive.
            # Let's use NEGATIVE Z for "Depth" (standard "back" direction in some Right Handed systems? No, usually -Z is forward in OpenGL, +Z back).
            # In USD, +Z is usually "Front" or "Back" depending on setup.
            # Let's use -Z for subsequent frames to march "backwards" effectively.
            
            # Suffix for keys
            sfx = f"_{i}" if num_frames > 1 else ""
            
            # -- BASE PLATES --
            # Left
            if not (i == 0 and skip_left):
                loc_bp_left = bd.Location((-width/2, 0, z_offset)) * bp_rot
                parts[f'base_plate_left{sfx}'] = base_plate
                transforms[f'base_plate_left{sfx}'] = loc_bp_left
            
            # Right
            if not (i == 0 and skip_right):
                loc_bp_right = bd.Location((width/2, 0, z_offset)) * bp_rot
                parts[f'base_plate_right{sfx}'] = base_plate
                transforms[f'base_plate_right{sfx}'] = loc_bp_right
            
            # -- COLUMNS --
            # Left
            if not (i == 0 and skip_left):
                loc_col_left = bd.Location((-width/2, bp_thk, z_offset))
                parts[f"column_left{sfx}"] = col_solid
                transforms[f"column_left{sfx}"] = loc_col_left
            
            # Right
            if not (i == 0 and skip_right):
                loc_col_right = bd.Location((width/2, bp_thk, z_offset))
                parts[f"column_right{sfx}"] = col_solid
                transforms[f"column_right{sfx}"] = loc_col_right
            
            # -- HEADER --
            loc_header = bd.Location((0, header_center_y, z_offset))
            parts[f'header{sfx}'] = h_solid
            transforms[f'header{sfx}'] = loc_header
            
            # -- CONNECTING BEAMS --
            # Create beams pointing to the NEXT frame (if not last frame)
            if conn_beam_solid and i < num_frames - 1:
                
                # Center of this span in Z
                # Current Frame Z: z_offset
                # Next Frame Z: z_offset - frame_spacing
                # Midpoint Z: z_offset - (frame_spacing / 2)
                
                mid_z = z_offset - (frame_spacing / 2.0)
                
                # Left Side Beam
                # X = -width/2
                loc_cb_left = bd.Location((-width/2, 0, mid_z))
                parts[f'conn_beam_left_{i}'] = conn_beam_solid
                transforms[f'conn_beam_left_{i}'] = loc_cb_left
                
                # Right Side Beam
                # X = width/2
                loc_cb_right = bd.Location((width/2, 0, mid_z))
                parts[f'conn_beam_right_{i}'] = conn_beam_solid
                transforms[f'conn_beam_right_{i}'] = loc_cb_right
                
        
        # ---------------------------------------------------------
        # 4. ENGINEERING VALIDATION (First Frame Only for now)
        # ---------------------------------------------------------
        
        # Constants
        E = 29000.0 # ksi (Steel)
        Fy = 50.0   # ksi
        
        # Header Properties
        h_props = self.calculate_section_properties(header_profile)
        Ix = h_props['Ix']
        Sx = h_props['Sx']
        
        # Load P (kips)
        P = point_load_lbs / 1000.0
        L = header_length
        
        # Deflection Delta (Center Point Load - Simply Supported)
        # P L^3 / 48 E I
        if Ix > 0:
            delta = (P * L**3) / (48 * E * Ix)
        else:
            delta = 999.0
            
        # Max Moment M (Center Point Load)
        # P L / 4
        M = (P * L) / 4.0
        
        # Bending Stress fb
        # M / Sx
        if Sx > 0:
            fb = M / Sx
        else:
            fb = 999.0
            
        # Allowable Limits
        # Deflection: L/360 (Stricter standard for live loads/finishes)
        limit_delta = L / 360.0
        
        # Stress: 0.66 Fy (ASD approx)
        limit_stress = 0.66 * Fy
        
        # Status
        status = "PASS"
        if delta > limit_delta or fb > limit_stress:
            status = "FAIL"
            
        validation_data = {
            'point_load_lbs': point_load_lbs,
            'deflection': delta,
            'limit_deflection': limit_delta,
            'stress': fb,
            'limit_stress': limit_stress,
            'status': status
        }

        return {
            'parts': parts,
            'transforms': transforms,
            'anchors': anchors,
            'metadata': {
                'header_length': header_length,
                'col_orientation': col_orientation,
                'gap': gap,
                'col_length': col_length,
                'header_center_y': header_center_y,
                'validation': validation_data,
                'conn_beam_length': conn_beam_length,
                'num_frames': num_frames
            }
        }
