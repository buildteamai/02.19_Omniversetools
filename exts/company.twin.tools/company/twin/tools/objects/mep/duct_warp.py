import warp as wp
import numpy as np
from pxr import Usd, UsdGeom, UsdShade, Vt, Gf, Sdf
from ..utils.port import Port

# Initialize Warp (safe to call multiple times in Omniverse)
wp.init()

@wp.kernel
def bend_kernel(
    points_in: wp.array(dtype=wp.vec3),
    points_out: wp.array(dtype=wp.vec3),
    radius: float,
    angle_rad: float,
    bend_axis_offset: float
):
    tid = wp.tid()
    p = points_in[tid]
    
    # We assume the input has:
    # - Straight section: t < 0 (before bend)
    # - Bent section: 0 <= t <= 1
    # - Straight section: t > 1 (after bend)
    
    # New Mapping for Y-Up World:
    # p[0] = t (X axis, flow)
    # p[1] = Y (Height/Vertical) -> Pass through (no bending in vertical, unless vertical bend?)
    # p[2] = Z (Width/Horizontal) -> Bend Axis (Turning Left/Right)
    
    t = p[0]
    height_y = p[1]  # Pass through
    width_z = p[2]   # Bending offset
    
    # Handle three regions
    if t < 0.0:
        # Start straight section - keep it straight, just offset in space
        # This section is before the bend starts
        # t is negative distance along X axis
        res_x = t
        # Preserve width! Match bend start at t=0 (-width_z)
        # Let's check logic:
        # If t=0, old logic: res_y = -y_offset.
        # radius + y_offset.
        # We want to match curvature.
        # Let's keep consistent: res_z = -width_z if that matches the bend equation at theta=0?
        # Bend: r = radius + width_z.
        # res_z = radius - r * cos(0) = radius - (radius + width_z) * 1 = -width_z.
        # YES.
        res_z = -width_z
        
    elif t > 1.0:
        # End straight section - keep it straight, positioned after bend
        # Calculate where the bend ends
        r = radius + width_z
        end_x = r * wp.sin(angle_rad)
        end_z = radius - r * wp.cos(angle_rad)
        
        # Extend straight from the end of the bend
        # Direction at end of bend is tangent to the curve
        tang_x = wp.cos(angle_rad)
        tang_z = wp.sin(angle_rad)
        
        straight_dist = (t - 1.0)
        res_x = end_x + tang_x * straight_dist
        res_z = end_z + tang_z * straight_dist
        
    else:
        # Bent section (0 <= t <= 1)
        theta = t * angle_rad
        r = radius + width_z
        
        res_x = r * wp.sin(theta)
        res_z = radius - r * wp.cos(theta)
    
    # Output: X=res_x, Y=height_y (unchanged), Z=res_z
    points_out[tid] = wp.vec3(res_x, height_y, res_z)


class DuctWarpGenerator:
    @staticmethod
    def regenerate(stage, prim):
        """
        Regenerates geometry for an existing duct/pipe by reading its stored metadata.
        Preserves world transform.
        
        Args:
            stage: USD stage
            prim: The existing prim to regenerate
            
        Returns:
            The regenerated mesh prim
        """
        path = str(prim.GetPath())
        gen_type = prim.GetCustomDataByKey('generatorType')
        
        if not gen_type:
            print(f"[DuctWarpGenerator] No generatorType on {path}")
            return None
        
        print(f"[DuctWarpGenerator] Regenerating {path} as {gen_type}")
        
        # Preserve world transform
        xform_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
        old_world_xform = xform_cache.GetLocalToWorldTransform(prim)
        
        # Read common metadata
        diameter = prim.GetCustomDataByKey('diameter')
        width = prim.GetCustomDataByKey('width')
        height = prim.GetCustomDataByKey('height')
        length = prim.GetCustomDataByKey('length')
        radius = prim.GetCustomDataByKey('radius')
        angle = prim.GetCustomDataByKey('angle')
        segments = prim.GetCustomDataByKey('segments') or 20
        add_flanges = prim.GetCustomDataByKey('add_flanges')
        if add_flanges is None:
            add_flanges = True
            
        # Delete old prim
        stage.RemovePrim(prim.GetPath())
        
        # Regenerate based on type
        if gen_type == 'duct_straight':
            new_mesh = DuctWarpGenerator._create_straight_duct(
                stage, path, width, height, length, add_flanges
            )
        elif gen_type == 'duct_bent':
            new_mesh = DuctWarpGenerator._create_rect_bent(
                stage, path, width, height, radius, angle, segments, add_flanges
            )
        elif gen_type in ['duct_round_straight', 'pipe_straight']:
            # Route both duct and pipe to the round generator, passing the type back in
            new_mesh = DuctWarpGenerator._create_round_duct_straight(
                stage, path, diameter, length, segments, add_flanges, gen_type_override=gen_type
            )
        elif gen_type in ['duct_round_bent', 'pipe_bent']:
            # Route both duct and pipe to the round bent generator
            new_mesh = DuctWarpGenerator._create_round_duct_bent(
                stage, path, diameter, radius, angle, segments, add_flanges, gen_type_override=gen_type
            )
        else:
            print(f"[DuctWarpGenerator] Unknown generatorType: {gen_type}")
            return None
        
        # Restore world transform
        new_prim = stage.GetPrimAtPath(path)
        if new_prim.IsValid():
            xform = UsdGeom.Xformable(new_prim)
            xform.ClearXformOpOrder()
            op = xform.AddTransformOp()
            op.Set(old_world_xform)
        
        return new_mesh
    
    @staticmethod
    def create(stage, path, width, height, radius, angle_deg, segments=20, add_flanges=True, length=None, shape="rectangular", diameter=None, system_type="duct"):
        """
        Create a duct (bent or straight) with optional flanges.
        
        Args:
            stage: USD stage
            path: Prim path for the mesh
            width: Duct width (rectangular only)
            height: Duct height (rectangular only)
            radius: Bend radius (ignored for straight duct)
            angle_deg: Bend angle in degrees (0 = straight duct)
            segments: Number of segments for the bend
            add_flanges: Whether to add flanges (angle iron for rect, companion for round)
            length: Total length for straight duct (ignored for bent)
            shape: "rectangular" or "round"
            diameter: Duct diameter (round only)
        """
        # Validate system_type
        if system_type not in ['duct', 'pipe']:
            system_type = 'duct'
            
        print(f"[DuctWarpGenerator] Creating {shape} {system_type}...")

        # Route ROUND duct/pipe to separate generator
        if shape == "round":
            if diameter is None:
                diameter = 12.0  # Default 12" round duct
            
            # Determine correct generator type based on system
            prefix = "pipe" if system_type == "pipe" else "duct_round"
            
            if angle_deg == 0 or angle_deg is None:
                gen_type = f"{prefix}_straight"
                return DuctWarpGenerator._create_round_duct_straight(
                    stage, path, diameter, length or 24.0, segments, add_flanges, gen_type_override=gen_type
                )
            else:
                gen_type = f"{prefix}_bent"
                return DuctWarpGenerator._create_round_duct_bent(
                    stage, path, diameter, radius, angle_deg, segments, add_flanges, gen_type_override=gen_type
                )
        
        # RECTANGULAR duct (original logic)
        angle_rad = float(np.radians(angle_deg))
        
        # Handle straight duct (0 degree) as a special case
        if angle_deg == 0 or angle_deg is None:
            return DuctWarpGenerator._create_straight_duct(
                stage, path, width, height, length or 24.0, add_flanges
            )
        
        # Add straight sections at both ends for flange welding
        straight_length = 2.0  # 2" straight section at each end
        
        # We will build a list of "rings". Each ring has 4 vertices (TL, TR, BR, BL).
        # Ring structure:
        # - Rings 0-2: Straight section at start (3 rings for 2" length)
        # - Rings 3 to (segments+2): Bent section
        # - Rings (segments+3) to (segments+5): Straight section at end (3 rings for 2" length)
        
        straight_rings = 3  # Number of rings for each straight section
        total_rings = straight_rings + segments + 1 + straight_rings
        
        points_per_ring = 4
        num_points = total_rings * points_per_ring
        points_host = []
        
        # Construct "Straight" space points (normalized t in X, physical Y, physical Z)
        # Y-UP Mapping:
        # Width -> Z axis (+/- half_w)
        # Height -> Y axis (+/- half_h)
        half_w = width / 2.0
        half_h = height / 2.0
        
        # Start straight section (before bend)
        for i in range(straight_rings):
            # t goes from -straight_length to 0 (in "unbent" space, this is just offset)
            t = -straight_length * (1.0 - i / (straight_rings - 1))
            
            # Order: TL, TR, BR, BL
            # Top = +Y, Bottom = -Y
            # Left = -Z, Right = +Z (Facing Forward X)
            # Let's Stick to Right-Hand Rule:
            # X = Forward. Y = Up. Z = Right.
            
            # TL: Top (+Y), Left (-Z)
            points_host.append([t,  half_h, -half_w]) # TL
            points_host.append([t,  half_h,  half_w]) # TR
            points_host.append([t, -half_h,  half_w]) # BR
            points_host.append([t, -half_h, -half_w]) # BL
        
        # Bent section
        num_rings_bend = segments + 1
        for i in range(num_rings_bend):
            t = float(i) / segments  # 0 to 1 for the bend
            
            points_host.append([t,  half_h, -half_w])
            points_host.append([t,  half_h,  half_w])
            points_host.append([t, -half_h,  half_w])
            points_host.append([t, -half_h, -half_w])
        
        # End straight section (after bend)
        for i in range(straight_rings):
            # t goes from 1 to 1+straight_length
            t = 1.0 + straight_length * (i / (straight_rings - 1))
            
            points_host.append([t,  half_h, -half_w])
            points_host.append([t,  half_h,  half_w])
            points_host.append([t, -half_h,  half_w])
            points_host.append([t, -half_h, -half_w])
            
        points_np = np.array(points_host, dtype=np.float32)
        
        # 2. Run Warp Kernel
        device = "cuda" if wp.get_cuda_device_count() > 0 else "cpu"
        
        in_points = wp.from_numpy(points_np, dtype=wp.vec3, device=device)
        out_points = wp.zeros_like(in_points)
        
        wp.launch(
            kernel=bend_kernel,
            dim=num_points,
            inputs=[in_points, out_points, radius, angle_rad, 0.0],
            device=device
        )
        
        # Sync and retrieve
        final_points = out_points.numpy()
        
        # 3. Create Topology (Quads)
        # Connect ring i to ring i+1
        face_indices = []
        face_counts = []
        
        for i in range(total_rings - 1):  # Connect all consecutive rings
            base = i * 4
            next_base = (i + 1) * 4
            
            # Side 1 (Top): 0 -> 1 -> 1' -> 0'
            face_indices.extend([base+0, next_base+0, next_base+1, base+1])
            face_counts.append(4)
            
            # Side 2 (Right): 1 -> 2 -> 2' -> 1'
            face_indices.extend([base+1, next_base+1, next_base+2, base+2])
            face_counts.append(4)
            
            # Side 3 (Bottom): 2 -> 3 -> 3' -> 2'
            face_indices.extend([base+2, next_base+2, next_base+3, base+3])
            face_counts.append(4)
            
            # Side 4 (Left): 3 -> 0 -> 0' -> 3'
            face_indices.extend([base+3, next_base+3, next_base+0, base+0])
            face_counts.append(4)
        
        # 4. Add Angle Flanges if requested
        if add_flanges:
            print("[Duct] Generating flanges...")
            flange_leg = 1.5  # 1.5" legs
            flange_thickness = 0.125  # 1/8" thick
            
            # Get the VERY first and VERY last ring positions (the straight sections)
            # These are the flat faces where the flange will be welded
            first_ring = final_points[0:4]  # Very first ring (start of first straight section)
            last_ring = final_points[-4:]   # Very last ring (end of last straight section)
            
            print(f"[Duct] First ring: {first_ring.shape}")
            print(f"[Duct] Last ring: {last_ring.shape}")
            
            # Add flanges at both ends
            try:
                flange_points, flange_faces, flange_counts = DuctWarpGenerator._create_angle_flange(
                    first_ring, width, height, flange_leg, flange_thickness, is_start=True
                )
                
                print(f"[Duct] Start flange: {len(flange_points)} points, {len(flange_faces)} face indices")
                
                start_flange_offset = len(final_points)
                final_points = np.vstack([final_points, flange_points])
                face_indices.extend([idx + start_flange_offset for idx in flange_faces])
                face_counts.extend(flange_counts)
                
                # End flange
                flange_points, flange_faces, flange_counts = DuctWarpGenerator._create_angle_flange(
                    last_ring, width, height, flange_leg, flange_thickness, is_start=False
                )
                
                print(f"[Duct] End flange: {len(flange_points)} points, {len(flange_faces)} face indices")
                
                end_flange_offset = len(final_points)
                final_points = np.vstack([final_points, flange_points])
                face_indices.extend([idx + end_flange_offset for idx in flange_faces])
                face_counts.extend(flange_counts)
                
                print(f"[Duct] Total points after flanges: {len(final_points)}")
                print(f"[Duct] Total faces: {len(face_counts)}")
            except Exception as e:
                print(f"[Duct] Error generating flanges: {e}")
                import traceback
                traceback.print_exc()
            
        # 5. Write to USD
        mesh = UsdGeom.Mesh.Define(stage, path)
        
        # Set Points
        mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(final_points))
        
        # Set Topo
        mesh.GetFaceVertexCountsAttr().Set(face_counts)
        mesh.GetFaceVertexIndicesAttr().Set(face_indices)
        
        # Set orientation (optional, but good practice)
        mesh.GetOrientationAttr().Set(UsdGeom.Tokens.rightHanded)
        
        # Store metadata for editability
        prim = mesh.GetPrim()
        prim.SetCustomDataByKey('generatorType', 'duct_bent')
        prim.SetCustomDataByKey('width', float(width))
        prim.SetCustomDataByKey('height', float(height))
        prim.SetCustomDataByKey('radius', float(radius))
        prim.SetCustomDataByKey('angle', float(angle_deg))
        prim.SetCustomDataByKey('segments', int(segments))
        prim.SetCustomDataByKey('add_flanges', bool(add_flanges))
        
        # Create Anchors for BENT duct
        # Start: Straight section along -X. Mating face is at X = -straight_length (t < 0)
        # However, our geometry generation puts the Mating Face at t = -straight_length
        # Wait, let's check the bend_kernel:
        # t < 0: res_x = t, res_z = -width_z
        # So at t = -straight_length, x = -straight_length.
        # Direction: Outward is -X
        DuctWarpGenerator._create_anchor(stage, path, "Anchor_Start", 
            Gf.Vec3d(-2.0, 0, 0),  # straight_length is hardcoded to 2.0
            Gf.Vec3d(-1, 0, 0),     # Direction: -X
            port_type="HVAC", shape="Rectangular", width=width, height=height
        )
        
        # End: After bend and straight section
        # We need to calculate the position at the end of the straight section
        # t = 1.0 + straight_length
        # From bend_kernel:
        # r = radius
        # end_x = r * sin(angle)
        # end_z = radius - r * cos(angle)
        # tang_x = cos(angle)
        # tang_z = sin(angle)
        # straight_dist = t - 1.0 = straight_length
        # res_x = end_x + tang_x * straight_dist
        # res_z = end_z + tang_z * straight_dist
        
        # Careful: width_z is 0 for the center line!
        
        r = float(radius)
        ang_rad = float(np.radians(angle_deg))
        straight_len = 2.0
        
        # End of bend (centerline)
        bend_end_x = r * np.sin(ang_rad)
        bend_end_z = r - r * np.cos(ang_rad)
        
        # Tangent vector at end
        tang_x = np.cos(ang_rad)
        tang_z = np.sin(ang_rad)
        
        # End of straight section
        final_x = bend_end_x + tang_x * straight_len
        final_z = bend_end_z + tang_z * straight_len
        
        DuctWarpGenerator._create_anchor(stage, path, "Anchor_End", 
            Gf.Vec3d(final_x, 0, final_z), 
            Gf.Vec3d(tang_x, 0, tang_z),
            port_type="HVAC", shape="Rectangular", width=width, height=height
        )
        
        # Apply galvanized material
        DuctWarpGenerator._create_galvanized_material(stage, path)
        
        return mesh
    
    @staticmethod
    def _create_angle_flange(ring_points, width, height, leg_length, thickness, is_start):
        """
        Creates a standard HVAC Angle Iron Flange.
        Matches the look of a solid angle frame slide onto the duct end.
        
        Geometry:
        - Face Leg: Flat frame at the duct opening, extending OUTWARD.
        - Web Leg: Flat plate on the duct surface, extending BACKWARD.
        
        Args:
            ring_points: 4 corner points of the opening [TL, TR, BR, BL]
            width: Duct width
            height: Duct height
            leg_length: Length of each leg of the angle (e.g., 1.5")
            thickness: Thickness of the angle material (e.g., 0.125")
            is_start: True for start flange, False for end flange
        
        Returns:
            (points, face_indices, face_counts)
        """
        # Extract corner positions
        tl, tr, br, bl = ring_points
        
        # Calculate normal vector (outward from duct)
        right_vec = tr - tl
        down_vec = bl - tl
        
        # Normal is perpendicular to the opening plane
        normal = np.cross(right_vec, down_vec)
        normal = normal / np.linalg.norm(normal)
        
        if not is_start:
            normal = -normal  # Flip for end flange
        
        print(f"[Duct] Creating Standard Angle Flange (is_start={is_start})")
        
        points = []
        faces = []
        
        # Helper to compute perpendicular vectors for expansion
        # We use the vector from the Centroid to the Edge Midpoint to guarantee OUTWARD direction
        center = (tl + tr + br + bl) / 4.0
        
        def get_outward_perp(p_start, p_end):
            mid = (p_start + p_end) / 2.0
            vec = mid - center
            return vec / np.linalg.norm(vec)

        # Calculate edge perpendiculars (Radial directions)
        perp_top = get_outward_perp(tl, tr)
        perp_right = get_outward_perp(tr, br)
        perp_bottom = get_outward_perp(br, bl)
        perp_left = get_outward_perp(bl, tl)
        
        # Calculate Outer Corners for the Face Frame
        # We extend each corner by combining the two adjacent perpendiculars
        tl_outer = tl + (perp_top + perp_left) * leg_length
        tr_outer = tr + (perp_top + perp_right) * leg_length
        br_outer = br + (perp_bottom + perp_right) * leg_length
        bl_outer = bl + (perp_bottom + perp_left) * leg_length
        
        # --- PART 1: FACE PLATE (The flat frame at the opening) ---
        # It has thickness, extending BACKWARDS from the opening plane
        # This ensures the 'front' of the flange is flush with the duct end
        
        # Front vertices (at duct opening plane)
        f_idx = len(points)
        points.extend([tl, tr, br, bl])           # Inner 0-3
        points.extend([tl_outer, tr_outer, br_outer, bl_outer]) # Outer 4-7
        
        # Back vertices (offset by thickness FORWARD)
        # Face plate extends forward from duct end
        back_offset = normal * thickness
        points.extend([p + back_offset for p in points[f_idx:f_idx+8]]) # 8-15
        
        # Create Face Plate Faces
        # Front Face (The mating surface)
        faces.extend([f_idx+0, f_idx+4, f_idx+5, f_idx+1]) # Top
        faces.extend([f_idx+1, f_idx+5, f_idx+6, f_idx+2]) # Right
        faces.extend([f_idx+2, f_idx+6, f_idx+7, f_idx+3]) # Bottom
        faces.extend([f_idx+3, f_idx+7, f_idx+4, f_idx+0]) # Left
        
        # Back Face (ordering reversed for normal)
        faces.extend([f_idx+8, f_idx+9, f_idx+13, f_idx+12]) # Top
        faces.extend([f_idx+9, f_idx+10, f_idx+14, f_idx+13]) # Right
        faces.extend([f_idx+10, f_idx+11, f_idx+15, f_idx+14]) # Bottom
        faces.extend([f_idx+11, f_idx+8, f_idx+12, f_idx+15]) # Left
        
        # Outer Rim
        faces.extend([f_idx+4, f_idx+12, f_idx+13, f_idx+5]) # Top Rim
        faces.extend([f_idx+5, f_idx+13, f_idx+14, f_idx+6]) # Right Rim
        faces.extend([f_idx+6, f_idx+14, f_idx+15, f_idx+7]) # Bottom Rim
        faces.extend([f_idx+7, f_idx+15, f_idx+12, f_idx+4]) # Left Rim
        
        # Inner Rim (against duct - theoretically hidden but good for solidity)
        faces.extend([f_idx+0, f_idx+1, f_idx+9, f_idx+8])
        faces.extend([f_idx+1, f_idx+2, f_idx+10, f_idx+9])
        faces.extend([f_idx+2, f_idx+3, f_idx+11, f_idx+10])
        faces.extend([f_idx+3, f_idx+0, f_idx+8, f_idx+11])
        
        # --- PART 2: WEB LEGS (The part welded to the duct surface) ---
        # Instead of 4 separate boxes, we create a continuous "Frame" for the web too
        # This ensures the corners are solid (mitered) and match the face plate
        
        # Web Frame Dimensions:
        # Inner: Ring points (on duct wall)
        # Outer: Ring points + thickness (expanded outward)
        # Depth: From -thickness (back of face plate) to -leg_length (tail)
        
        tl_web_outer = tl + (perp_top + perp_left) * thickness
        tr_web_outer = tr + (perp_top + perp_right) * thickness
        br_web_outer = br + (perp_bottom + perp_right) * thickness
        bl_web_outer = bl + (perp_bottom + perp_left) * thickness
        
        # Web extends FORWARD (outward from duct opening) - this is the mating surface direction
        start_depth = normal * thickness
        end_depth = normal * leg_length
        
        w_idx = len(points)
        
        # Web Start Vertices (connects to back of face plate)
        # Inner 0-3
        points.extend([p + start_depth for p in [tl, tr, br, bl]])
        # Outer 4-7
        points.extend([p + start_depth for p in [tl_web_outer, tr_web_outer, br_web_outer, bl_web_outer]])
        
        # Web End Vertices (tail of flange)
        # Inner 8-11
        points.extend([p + end_depth for p in [tl, tr, br, bl]])
        # Outer 12-15
        points.extend([p + end_depth for p in [tl_web_outer, tr_web_outer, br_web_outer, bl_web_outer]])
        
        # Create Web Frame Faces
        
        # Outer Surface (Visible from side)
        faces.extend([w_idx+4, w_idx+12, w_idx+13, w_idx+5]) # Top
        faces.extend([w_idx+5, w_idx+13, w_idx+14, w_idx+6]) # Right
        faces.extend([w_idx+6, w_idx+14, w_idx+15, w_idx+7]) # Bottom
        faces.extend([w_idx+7, w_idx+15, w_idx+12, w_idx+4]) # Left
        
        # Inner Surface (Hidden against duct - keeping for solidity)
        faces.extend([w_idx+0, w_idx+1, w_idx+9, w_idx+8])
        faces.extend([w_idx+1, w_idx+2, w_idx+10, w_idx+9])
        faces.extend([w_idx+2, w_idx+3, w_idx+11, w_idx+10])
        faces.extend([w_idx+3, w_idx+0, w_idx+8, w_idx+11])
        
        # End Cap (Tail of flange)
        faces.extend([w_idx+8, w_idx+9, w_idx+13, w_idx+12])
        faces.extend([w_idx+9, w_idx+10, w_idx+14, w_idx+13])
        faces.extend([w_idx+10, w_idx+11, w_idx+15, w_idx+14])
        faces.extend([w_idx+11, w_idx+8, w_idx+12, w_idx+15])

        points_array = np.array(points, dtype=np.float32)
        face_counts = [4] * (len(faces) // 4)
        
        print(f"[Duct] Created Standard Flange: {len(points)} points, {len(face_counts)} faces")
        
        
        return points_array, faces, face_counts

    @staticmethod
    def _create_straight_duct(stage, path, width, height, length, add_flanges):
        """
        Creates a straight rectangular duct with optional flanges.
        
        Args:
            stage: USD stage
            path: Prim path
            width: Duct width
            height: Duct height
            length: Total duct length
            add_flanges: Whether to add angle iron flanges
        
        Returns:
            UsdGeom.Mesh
        """
        print(f"[Duct] Creating STRAIGHT duct: {width}x{height}x{length}")
        
        # Y-UP Mapping:
        # Width -> Z
        # Height -> Y
        half_w = width / 2.0
        half_h = height / 2.0
        
        # Create a simple rectangular tube with 2 rings (start and end)
        num_rings = 2
        points = []
        
        # Ring 0: Start (at origin)
        # TL: +Y, -Z
        points.append([0.0,  half_h, -half_w])  # TL
        points.append([0.0,  half_h,  half_w])  # TR
        points.append([0.0, -half_h,  half_w])  # BR
        points.append([0.0, -half_h, -half_w])  # BL
        
        # Ring 1: End (at length along X axis)
        points.append([length,  half_h, -half_w])  # TL
        points.append([length,  half_h,  half_w])  # TR
        points.append([length, -half_h,  half_w])  # BR
        points.append([length, -half_h, -half_w])  # BL
        
        final_points = np.array(points, dtype=np.float32)
        
        # Create faces (4 sides of the rectangular tube)
        face_indices = []
        face_counts = []
        
        base = 0
        next_base = 4
        
        # Top face
        face_indices.extend([base+0, next_base+0, next_base+1, base+1])
        face_counts.append(4)
        
        # Right face
        face_indices.extend([base+1, next_base+1, next_base+2, base+2])
        face_counts.append(4)
        
        # Bottom face
        face_indices.extend([base+2, next_base+2, next_base+3, base+3])
        face_counts.append(4)
        
        # Left face
        face_indices.extend([base+3, next_base+3, next_base+0, base+0])
        face_counts.append(4)
        
        # Add flanges if requested
        if add_flanges:
            print("[Duct] Adding flanges to straight duct...")
            flange_leg = 1.5
            flange_thickness = 0.125
            
            # For straight duct along X axis:
            # - Start flange (X=0): should face -X direction (is_start=False makes normal flip)
            # - End flange (X=length): should face +X direction (is_start=True keeps normal)
            
            # Start flange (ring 0) - faces outward from start
            first_ring = final_points[0:4]
            flange_points, flange_faces, flange_counts = DuctWarpGenerator._create_angle_flange(
                first_ring, width, height, flange_leg, flange_thickness, is_start=True  # Normal is +X, so is_start=True means normal is -X (outward)
            )
            
            start_offset = len(final_points)
            final_points = np.vstack([final_points, flange_points])
            face_indices.extend([idx + start_offset for idx in flange_faces])
            face_counts.extend(flange_counts)
            
            # End flange (ring 1) - faces outward from end
            flange_points, flange_faces, flange_counts = DuctWarpGenerator._create_angle_flange(
                np.array(points[4:8], dtype=np.float32), width, height, flange_leg, flange_thickness, is_start=False  # Normal is -X, so is_start=False means normal is +X (outward)
            )
            
            end_offset = len(final_points)
            final_points = np.vstack([final_points, flange_points])
            face_indices.extend([idx + end_offset for idx in flange_faces])
            face_counts.extend(flange_counts)

        # ---------------------------------------------------------
        # STIFFENERS (for ducts > 48")
        # ---------------------------------------------------------
        if length > 48.0:
            print(f"[Duct] Length {length} > 48.0: Adding mid-point stiffener...")
            stiffener_leg = 1.5
            stiffener_thick = 0.125
            
            # Use the start ring (X=0) as base
            base_ring = final_points[0:4]
            
            # Generate flange geometry at X=0
            # is_start=True means Normal is -X (Outward from start).
            # "Backward" (Web Leg direction) is therefore +X (Along the duct).
            # This places the stiffener's web leg on the duct surface, extending towards +X.
            stiff_points, stiff_faces, stiff_counts = DuctWarpGenerator._create_angle_flange(
                base_ring, width, height, stiffener_leg, stiffener_thick, is_start=False # Normal is +X, so is_start=False means normal is -X (outward)
            )
            
            # Shift points to Midpoint
            mid_x = length / 2.0
            # Shift back by half the web leg? usually stiffener is centered.
            # But our flange has the Face Plate at 0 and Web extending +X.
            # Let's just place the Face Plate at Midpoint.
            
            # Offset calculation: Add (mid_x, 0, 0) to all points
            offset_vec = np.array([mid_x, 0, 0], dtype=np.float32)
            stiff_points = stiff_points + offset_vec
            
            # Append to mesh
            stiff_offset = len(final_points)
            final_points = np.vstack([final_points, stiff_points])
            face_indices.extend([idx + stiff_offset for idx in stiff_faces])
            face_counts.extend(stiff_counts)
            
            print(f"[Duct] Added stiffener at X={mid_x}")
        
        # Write to USD
        mesh = UsdGeom.Mesh.Define(stage, path)
        mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(final_points))
        mesh.GetFaceVertexCountsAttr().Set(face_counts)
        mesh.GetFaceVertexIndicesAttr().Set(face_indices)
        mesh.GetOrientationAttr().Set(UsdGeom.Tokens.rightHanded)
        
        # Store metadata
        prim = mesh.GetPrim()
        prim.SetCustomDataByKey('generatorType', 'duct_straight')
        prim.SetCustomDataByKey('width', float(width))
        prim.SetCustomDataByKey('height', float(height))
        prim.SetCustomDataByKey('length', float(length))
        prim.SetCustomDataByKey('add_flanges', bool(add_flanges))
        
        # Create Anchors (Acting as Ports)
        # Start: At (0,0,0), facing -X (Outward)
        DuctWarpGenerator._create_anchor(stage, path, "Anchor_Start", 
            Gf.Vec3d(0, 0, 0), 
            Gf.Vec3d(-1, 0, 0),
            port_type="HVAC", shape="Rectangular", width=width, height=height
        )
        
        # End: At (Length,0,0), facing +X (Outward)
        DuctWarpGenerator._create_anchor(stage, path, "Anchor_End", 
            Gf.Vec3d(length, 0, 0), 
            Gf.Vec3d(1, 0, 0),
            port_type="HVAC", shape="Rectangular", width=width, height=height
        )
        
        # Apply galvanized material
        DuctWarpGenerator._create_galvanized_material(stage, path)
        
        print(f"[Duct] Straight duct created with {len(final_points)} points")
        return mesh

    @staticmethod
    def _create_anchor(stage, parent_path, name, position, direction, port_type="HVAC", shape="Rectangular", width=0.0, height=0.0, diameter=None):
        """Creates an Xform anchor as a child of the duct, serving as a Mating Port"""
        anchor_path = f"{parent_path}/{name}"
        xform = UsdGeom.Xform.Define(stage, anchor_path)
        
        # Set Position
        xform.AddTranslateOp().Set(position)
        
        # Set Rotation to align -Z with direction (Standard USD look-at)
        # Or align X with direction? Let's stick to:
        # X-axis = Airflow direction (Outward)
        # Y-axis = Horizontal
        # Z-axis = Vertical
        
        # Construct rotation matrix
        # forward (X) = direction
        # up (Z) = (0,0,1)
        # right (Y) = cross(Z, X)
        
        xaxis = direction.GetNormalized()
        zaxis = Gf.Vec3d(0, 0, 1)
        # Check for collinearity
        if abs(Gf.Dot(xaxis, zaxis)) > 0.99:
            zaxis = Gf.Vec3d(0, 1, 0) # Fallback if direction is vertical
            
        yaxis = Gf.Cross(zaxis, xaxis).GetNormalized()
        
        # Re-orthogonalize Z
        zaxis = Gf.Cross(xaxis, yaxis).GetNormalized()
        
        # Create Matrix: Right(Y), Up(Z), Forward(-X)? 
        # Standard basis: X, Y, Z rows
        mat = Gf.Matrix4d()
        mat.SetRow(0, Gf.Vec4d(xaxis[0], xaxis[1], xaxis[2], 0))
        mat.SetRow(1, Gf.Vec4d(yaxis[0], yaxis[1], yaxis[2], 0))
        mat.SetRow(2, Gf.Vec4d(zaxis[0], zaxis[1], zaxis[2], 0))
        mat.SetRow(3, Gf.Vec4d(0, 0, 0, 1))
        
        # Extract rotation and convert to float quaternion
        rot = mat.ExtractRotation()
        quatd = rot.GetQuat()
        quatf = Gf.Quatf(quatd.GetReal(), Gf.Vec3f(quatd.GetImaginary()))
        xform.AddOrientOp().Set(quatf)
        
        # Add visualizer (Wireframe sphere or axes)
        # For now just an empty Xform, visible in stage
        prim = xform.GetPrim()
        prim.CreateAttribute("custom:is_anchor", Sdf.ValueTypeNames.Bool).Set(True)
        # Mark as Port so MatingSystem finds it
        prim.CreateAttribute("twin:is_port", Sdf.ValueTypeNames.Bool).Set(True)
        prim.CreateAttribute("twin:port_type", Sdf.ValueTypeNames.String).Set(port_type)
        prim.CreateAttribute("twin:port_shape", Sdf.ValueTypeNames.String).Set(shape)
        
        # Handle Round vs Rectangular dimensions
        if shape.lower() == "round" or shape.lower() == "circular":
            curr_diameter = diameter if diameter is not None else width
            prim.CreateAttribute("twin:port_diameter", Sdf.ValueTypeNames.Double).Set(float(curr_diameter))
        else:
            prim.CreateAttribute("twin:port_width", Sdf.ValueTypeNames.Double).Set(float(width))
            prim.CreateAttribute("twin:port_height", Sdf.ValueTypeNames.Double).Set(float(height))
        
        # Add Visualization (Selectable Proxy)
        viz_path = f"{anchor_path}/viz"
        viz = UsdGeom.Sphere.Define(stage, viz_path)
        viz.GetRadiusAttr().Set(1.0)  # 1 inch radius sphere
        
        # Color it (Yellow for anchors to distinguish from Ports)
        viz.GetDisplayColorAttr().Set([Gf.Vec3f(1, 1, 0)])

    # ========== ROUND DUCT SUPPORT ==========
    
    @staticmethod
    def _create_round_duct_straight(stage, path, diameter, length, segments=24, add_flanges=True, gen_type_override=None):
        """
        Creates a straight round (circular) duct with optional companion flanges.
        
        Args:
            stage: USD stage
            path: Prim path
            diameter: Outer diameter of the duct
            length: Total duct length
            segments: Number of segments around the circumference
            add_flanges: Whether to add companion flanges
        
        Returns:
            UsdGeom.Mesh
        """
        print(f"[Duct] Creating ROUND STRAIGHT duct: D={diameter}, L={length}")
        
        radius = diameter / 2.0
        
        # Create circular cross-section points
        # Ring at X=0 (start) and X=length (end)
        points = []
        
        for ring_x in [0.0, length]:
            for i in range(segments):
                angle = 2.0 * np.pi * i / segments
                y = radius * np.cos(angle)
                z = radius * np.sin(angle)
                points.append([ring_x, y, z])
        
        final_points = np.array(points, dtype=np.float32)
        
        # Create faces (quads connecting consecutive segments)
        face_indices = []
        face_counts = []
        
        for i in range(segments):
            i_next = (i + 1) % segments
            # Start ring = indices 0 to segments-1
            # End ring = indices segments to 2*segments-1
            
            v0 = i
            v1 = i_next
            v2 = segments + i_next
            v3 = segments + i
            
            face_indices.extend([v0, v3, v2, v1])
            face_counts.append(4)
        
        # Add companion flanges if requested
        if add_flanges:
            print("[Duct] Adding companion flanges to round duct...")
            
            # Start flange (at X=0, facing -X)
            start_ring = final_points[0:segments]
            flange_pts, flange_faces, flange_counts = DuctWarpGenerator._create_companion_flange(
                start_ring, diameter, segments, is_start=True
            )
            
            start_offset = len(final_points)
            final_points = np.vstack([final_points, flange_pts])
            face_indices.extend([idx + start_offset for idx in flange_faces])
            face_counts.extend(flange_counts)
            
            # End flange (at X=length, facing +X)
            end_ring = final_points[segments:2*segments]  # Original end ring indices
            flange_pts, flange_faces, flange_counts = DuctWarpGenerator._create_companion_flange(
                np.array(points[segments:2*segments], dtype=np.float32), diameter, segments, is_start=False
            )
            
            end_offset = len(final_points)
            final_points = np.vstack([final_points, flange_pts])
            face_indices.extend([idx + end_offset for idx in flange_faces])
            face_counts.extend(flange_counts)
        
        # Write to USD
        mesh = UsdGeom.Mesh.Define(stage, path)
        mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(final_points))
        mesh.GetFaceVertexCountsAttr().Set(face_counts)
        mesh.GetFaceVertexIndicesAttr().Set(face_indices)
        mesh.GetOrientationAttr().Set(UsdGeom.Tokens.rightHanded)
        
        # Store metadata
        prim = mesh.GetPrim()
        gen_type = gen_type_override if gen_type_override else 'duct_round_straight'
        prim.SetCustomDataByKey('generatorType', gen_type)
        prim.SetCustomDataByKey('diameter', float(diameter))
        prim.SetCustomDataByKey('length', float(length))
        prim.SetCustomDataByKey('segments', int(segments))
        prim.SetCustomDataByKey('add_flanges', bool(add_flanges))
        prim.SetCustomDataByKey('shape', 'round')
        
        # Create Anchors
        # Start: At (0,0,0), facing -X (Outward)
        DuctWarpGenerator._create_anchor(stage, path, "Anchor_Start", 
            Gf.Vec3d(0, 0, 0), 
            Gf.Vec3d(-1, 0, 0),
            port_type="HVAC", shape="Circular", diameter=diameter
        )
        
        # End: At (Length,0,0), facing +X (Outward)
        DuctWarpGenerator._create_anchor(stage, path, "Anchor_End", 
            Gf.Vec3d(length, 0, 0), 
            Gf.Vec3d(1, 0, 0),
            port_type="HVAC", shape="Circular", diameter=diameter
        )
        
        # Apply material
        DuctWarpGenerator._create_galvanized_material(stage, path)
        
        print(f"[Duct] Round straight duct created with {len(final_points)} points")
        return mesh
    
    @staticmethod
    def _create_round_duct_bent(stage, path, diameter, bend_radius, angle_deg, segments=24, add_flanges=True, gen_type_override=None):
        """
        Creates a bent round (circular) duct with optional companion flanges.
        
        Args:
            stage: USD stage
            path: Prim path
            diameter: Outer diameter of the duct
            bend_radius: Radius of the bend centerline
            angle_deg: Bend angle in degrees
            segments: Number of segments around the circumference
            add_flanges: Whether to add companion flanges
        
        Returns:
            UsdGeom.Mesh
        """
        print(f"[Duct] Creating ROUND BENT duct: D={diameter}, R={bend_radius}, Angle={angle_deg}°")
        
        duct_radius = diameter / 2.0
        angle_rad = np.radians(angle_deg)
        
        # Straight section length at each end
        straight_length = 2.0
        
        # Number of rings along the bend
        bend_segments = max(int(segments * angle_deg / 90), 8)
        straight_rings = 3
        total_rings = straight_rings + bend_segments + 1 + straight_rings
        
        points_host = []
        
        # Helper to generate a circular ring at a given position/orientation
        def make_ring(center, forward, up):
            """Generate ring points at center, oriented with forward as normal"""
            right = np.cross(forward, up)
            right = right / np.linalg.norm(right)
            actual_up = np.cross(right, forward)
            
            ring_pts = []
            for i in range(segments):
                angle = 2.0 * np.pi * i / segments
                offset = duct_radius * (np.cos(angle) * actual_up + np.sin(angle) * right)
                ring_pts.append(center + offset)
            return ring_pts
        
        # Start straight section (before bend) - along -X
        for i in range(straight_rings):
            t = -straight_length * (1.0 - i / (straight_rings - 1))
            center = np.array([t, 0, 0])
            forward = np.array([1, 0, 0])
            up = np.array([0, 0, 1])
            points_host.extend(make_ring(center, forward, up))
        
        # Bent section
        for i in range(bend_segments + 1):
            theta = angle_rad * i / bend_segments
            
            # Center of ring on bend
            cx = bend_radius * np.sin(theta)
            cy = bend_radius - bend_radius * np.cos(theta)
            center = np.array([cx, cy, 0])
            
            # Tangent direction (forward)
            forward = np.array([np.cos(theta), np.sin(theta), 0])
            up = np.array([0, 0, 1])
            
            points_host.extend(make_ring(center, forward, up))
        
        # End straight section (after bend)
        # End position and direction of bend
        bend_end_x = bend_radius * np.sin(angle_rad)
        bend_end_y = bend_radius - bend_radius * np.cos(angle_rad)
        tang_x = np.cos(angle_rad)
        tang_y = np.sin(angle_rad)
        
        for i in range(straight_rings):
            t = straight_length * i / (straight_rings - 1)
            center = np.array([
                bend_end_x + tang_x * t,
                bend_end_y + tang_y * t,
                0
            ])
            forward = np.array([tang_x, tang_y, 0])
            up = np.array([0, 0, 1])
            points_host.extend(make_ring(center, forward, up))
        
        final_points = np.array(points_host, dtype=np.float32)
        
        # Create faces connecting rings
        face_indices = []
        face_counts = []
        
        for ring_idx in range(total_rings - 1):
            base = ring_idx * segments
            next_base = (ring_idx + 1) * segments
            
            for i in range(segments):
                i_next = (i + 1) % segments
                
                v0 = base + i
                v1 = base + i_next
                v2 = next_base + i_next
                v3 = next_base + i
                
                face_indices.extend([v0, v3, v2, v1])
                face_counts.append(4)
        
        # Add companion flanges if requested
        if add_flanges:
            print("[Duct] Adding companion flanges to bent round duct...")
            
            # Start flange
            start_ring = final_points[0:segments]
            flange_pts, flange_faces, flange_counts = DuctWarpGenerator._create_companion_flange(
                start_ring, diameter, segments, is_start=True
            )
            
            start_offset = len(final_points)
            final_points = np.vstack([final_points, flange_pts])
            face_indices.extend([idx + start_offset for idx in flange_faces])
            face_counts.extend(flange_counts)
            
            # End flange
            end_ring = final_points[(total_rings-1)*segments : total_rings*segments]
            # Need to get the original end ring before adding start flange
            orig_end_ring = np.array(points_host[(total_rings-1)*segments : total_rings*segments], dtype=np.float32)
            
            flange_pts, flange_faces, flange_counts = DuctWarpGenerator._create_companion_flange(
                orig_end_ring, diameter, segments, is_start=False
            )
            
            end_offset = len(final_points)
            final_points = np.vstack([final_points, flange_pts])
            face_indices.extend([idx + end_offset for idx in flange_faces])
            face_counts.extend(flange_counts)
        
        # Write to USD
        mesh = UsdGeom.Mesh.Define(stage, path)
        mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(final_points))
        mesh.GetFaceVertexCountsAttr().Set(face_counts)
        mesh.GetFaceVertexIndicesAttr().Set(face_indices)
        mesh.GetOrientationAttr().Set(UsdGeom.Tokens.rightHanded)
        
        # Store metadata
        prim = mesh.GetPrim()
        gen_type = gen_type_override if gen_type_override else 'duct_round_bent'
        prim.SetCustomDataByKey('generatorType', gen_type)
        prim.SetCustomDataByKey('diameter', float(diameter))
        prim.SetCustomDataByKey('radius', float(bend_radius))
        prim.SetCustomDataByKey('angle', float(angle_deg))
        prim.SetCustomDataByKey('segments', int(segments))
        prim.SetCustomDataByKey('add_flanges', bool(add_flanges))
        prim.SetCustomDataByKey('shape', 'round')
        
        # Create Anchors
        # Start: Straight section along -X
        DuctWarpGenerator._create_anchor(stage, path, "Anchor_Start", 
            Gf.Vec3d(-straight_length, 0, 0), 
            Gf.Vec3d(-1, 0, 0),
            port_type="HVAC", shape="Circular", diameter=diameter
        )
        
        # End: After bend and straight section
        final_x = bend_end_x + tang_x * straight_length
        final_y = bend_end_y + tang_y * straight_length
        
        DuctWarpGenerator._create_anchor(stage, path, "Anchor_End", 
            Gf.Vec3d(final_x, final_y, 0), 
            Gf.Vec3d(tang_x, tang_y, 0),
            port_type="HVAC", shape="Circular", diameter=diameter
        )
        
        # Apply material
        DuctWarpGenerator._create_galvanized_material(stage, path)
        
        print(f"[Duct] Round bent duct created with {len(final_points)} points")
        return mesh
    
    @staticmethod
    def _create_companion_flange(ring_points, diameter, segments, is_start):
        """
        Creates a companion flange for round duct.
        
        HVAC Companion Flanges:
        - Circular ring with bolt holes
        - Extends radially outward from duct diameter
        - Standard thickness
        
        Args:
            ring_points: Circular ring of points at duct end (segments x 3)
            diameter: Duct diameter
            segments: Number of segments in the circle
            is_start: True for start flange (normal faces -X), False for end
        
        Returns:
            (points, face_indices, face_counts)
        """
        duct_radius = diameter / 2.0
        flange_width = 1.5  # 1.5" radial extension
        flange_thickness = 0.125  # 1/8" thick
        
        # Determine flange outer radius
        flange_outer_radius = duct_radius + flange_width
        
        # Calculate center and normal from ring points
        center = np.mean(ring_points, axis=0)
        
        # Get normal direction from first two segments
        v1 = ring_points[1] - ring_points[0]
        v2 = ring_points[2] - ring_points[1]
        normal = np.cross(v1, v2)
        normal = normal / np.linalg.norm(normal)
        
        if is_start:
            normal = -normal  # Face outward from start
        
        print(f"[Duct] Creating companion flange: D={diameter}, is_start={is_start}")
        
        points = []
        faces = []
        
        # Create outer ring (at same plane as duct end)
        outer_ring = []
        for i in range(segments):
            # Direction from center to this point
            direction = ring_points[i] - center
            direction = direction / np.linalg.norm(direction)
            outer_pt = center + direction * flange_outer_radius
            outer_ring.append(outer_pt)
        
        outer_ring = np.array(outer_ring)
        
        # Front face vertices (at duct opening plane)
        # Inner ring = ring_points
        # Outer ring = outer_ring
        f_idx = len(points)
        points.extend(ring_points.tolist())  # Inner front: 0 to segments-1
        points.extend(outer_ring.tolist())   # Outer front: segments to 2*segments-1
        
        # Back face vertices (offset by thickness)
        back_offset = normal * flange_thickness
        points.extend((ring_points + back_offset).tolist())  # Inner back: 2*segments to 3*segments-1
        points.extend((outer_ring + back_offset).tolist())   # Outer back: 3*segments to 4*segments-1
        
        # Create faces
        for i in range(segments):
            i_next = (i + 1) % segments
            
            # Front face (ring between inner and outer)
            inner_f = f_idx + i
            inner_f_next = f_idx + i_next
            outer_f = f_idx + segments + i
            outer_f_next = f_idx + segments + i_next
            
            faces.extend([inner_f, outer_f, outer_f_next, inner_f_next])
            
            # Back face (reversed winding)
            inner_b = f_idx + 2*segments + i
            inner_b_next = f_idx + 2*segments + i_next
            outer_b = f_idx + 3*segments + i
            outer_b_next = f_idx + 3*segments + i_next
            
            faces.extend([inner_b, inner_b_next, outer_b_next, outer_b])
            
            # Outer rim (connects front outer to back outer)
            faces.extend([outer_f, outer_b, outer_b_next, outer_f_next])
            
            # Inner rim (connects back inner to front inner - against duct)
            faces.extend([inner_f, inner_f_next, inner_b_next, inner_b])
        
        points_array = np.array(points, dtype=np.float32)
        face_counts = [4] * (len(faces) // 4)
        
        print(f"[Duct] Companion flange: {len(points)} points, {len(face_counts)} faces")
        
        return points_array, faces, face_counts

    @staticmethod
    def _create_galvanized_material(stage, duct_path):
        """
        Creates and binds a galvanized steel material to the duct mesh.
        
        Galvanized steel properties:
        - Slightly blue-gray metallic color
        - High metallic value (0.9)
        - Low roughness (0.3-0.4) for slight sheen
        """
        mat_path = f"{duct_path}/GalvanizedSteel"
        
        # Create Material
        material = UsdShade.Material.Define(stage, mat_path)
        
        # Create PBR Shader
        shader_path = f"{mat_path}/PBRShader"
        shader = UsdShade.Shader.Define(stage, shader_path)
        shader.CreateIdAttr("UsdPreviewSurface")
        
        # Galvanized steel color (dark gray)
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.25, 0.25, 0.27))
        
        # Metallic properties
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.9)
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.35)
        
        # Slight reflectance
        shader.CreateInput("ior", Sdf.ValueTypeNames.Float).Set(2.5)
        
        # Connect shader to material surface output
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        
        # Bind material to mesh
        mesh_prim = stage.GetPrimAtPath(duct_path)
        if mesh_prim:
            UsdShade.MaterialBindingAPI(mesh_prim).Bind(material)
            print(f"[Duct] Applied galvanized steel material to {duct_path}")
        
        return material
