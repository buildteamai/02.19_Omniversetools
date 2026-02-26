from build123d import *
from ..utils import usd_utils
import omni.usd
from pxr import UsdGeom, Sdf, Gf
import math

class Stair:
    """
    Industrial Stair Generator (OSHA 1910.25 Compliant).
    """

    @staticmethod
    def create(
        stage,
        path,
        total_rise=120.0,
        width=36.0,
        run=10.0,
        landing_depth=30.0,
        stringer_size="C10",
        material="Steel"
    ):
        """
        Generates an industrial stair system.

        Args:
            stage: USD stage
            path: Prim path
            total_rise: Total vertical height (in)
            width: Clear width between stringers (in)
            run: Horizontal tread depth (in) - excludes nosing overlap
            landing_depth: Depth of the top landing platform (in)
            stringer_size: C-Channel size (e.g., "C10")
            material: "Steel" or "Aluminum" (affects visuals/density if implemented)
        """
        
        # --- OSHA Calculation Logic ---
        # Target rise is 7"
        ideal_rise = 7.0
        num_steps = round(total_rise / ideal_rise)
        if num_steps == 0:
            num_steps = 1
        
        actual_rise = total_rise / num_steps
        
        # Calculate angle
        slope_angle_rad = math.atan(actual_rise / run)
        slope_angle_deg = math.degrees(slope_angle_rad)
        
        # Total horizontal run for the stair flight
        total_run = run * (num_steps - 1) 
        
        # --- Parameters ---
        # Stringer (C10x15.3 approx dimensions)
        stringer_depth = 10.0
        stringer_flange_width = 2.6
        stringer_thickness = 0.24
        stringer_flange_thickness = 0.44
        
        # Tread
        tread_thickness = 1.5 # Grating thickness
        nosing_overlap = 1.0
        tread_depth_total = run + nosing_overlap
        
        # Handrail
        rail_height = 34.0 # OSHA 30-38"
        rail_diameter = 1.9 # 1.5" Pipe OD is ~1.9"
        mid_rail_height = rail_height / 2
        
        try:
            with BuildPart() as bp:
                
                pass
                
                # --- Treads ---
                # Place treads at each step
                treads = []
                for i in range(num_steps):
                    if i == num_steps - 1:
                        continue
                    x_pos = run * i
                    z_pos = actual_rise * (i + 1)
                    
                    with BuildPart() as tread:
                         Box(run + nosing_overlap, width, tread_thickness, align=(Align.MIN, Align.CENTER, Align.MAX))
                    
                    treads.append(tread.part.move(Location((x_pos, 0, z_pos))))
                    
                # --- Landing ---
                with BuildPart() as landing:
                    Box(landing_depth, width, tread_thickness, align=(Align.MIN, Align.CENTER, Align.MAX))
                
                landing_pos = Location((total_run, 0, total_rise))
                treads.append(landing.part.move(landing_pos))

                s1 = Stair._create_stringer_side(
                    total_rise, total_run, landing_depth, stringer_depth, slope_angle_deg,
                    stringer_flange_thickness=stringer_flange_thickness,
                    stringer_thickness=stringer_thickness,
                    section="left"
                )
                s1 = s1.move(Location((0, -width/2 - stringer_thickness, 0)))
                
                # Right Stringer
                s2 = Stair._create_stringer_side(
                    total_rise, total_run, landing_depth, stringer_depth, slope_angle_deg,
                    stringer_flange_thickness=stringer_flange_thickness,
                    stringer_thickness=stringer_thickness,
                    section="right"
                )
                # Mirror or just move? Right side faces inward.
                # If generated logic assumes "Inward" is +Y for left, then -Y for right...
                # Let's just create generic and move/mirror.
                s2 = s2.rotate(Axis.X, 180) # Flip
                s2 = s2.move(Location((0, width/2 + stringer_thickness, 0)))
                
                # --- Handrails ---
                # Posts every ~4-6 feet (optimum 4 steps?).
                # Let's place posts at start, end, and every 4th step.
                
                posts = []
                rails = []
                
                # Rail Height logic
                # Height is 34" above Tread Nosing.
                # Nosing line Z = tan(a) * X
                # Rail line Z = tan(a) * X + 34
                
                # Post locations (X coordinates)
                post_x_locs = [0.0] # Start (approx) at first riser?
                # Actually start post usually at X=Run/2 or X=0.
                if num_steps > 1:
                    max_x = total_run + landing_depth/2
                    # Distribute posts max spacing 48"
                    # Flight length
                    flight_len = total_run
                    # Spacing
                    spacing = 48.0
                    num_posts = int(flight_len / spacing) + 2
                    
                    for i in range(num_posts):
                        # Interpolate X
                        px = (flight_len / (num_posts-1)) * i
                        post_x_locs.append(px)
                        
                    # Add landing post
                    post_x_locs.append(total_run + landing_depth - 2.0)
                else:
                    post_x_locs = [0, total_run + landing_depth/2]

                # Make unique and sort
                post_x_locs = sorted(list(set(post_x_locs)))

                # Create Post Geometry (1.5" pipe -> 1.9" OD)
                # Tube: OD 1.9, ID 1.6
                post_od = 1.9
                post_id = 1.61
                
                for px in post_x_locs:
                    # Determine Z of the "floor/tread" at this X
                    # If X <= total_run: On slope. Z_nosing = tan(a) * px + ??
                    # Actually, usually posts are attached to stringer.
                    # Stringer top is at Z = tan(a)*px + web_top_offset.
                    # Post base is at stringer top? Or bolted to side?
                    # Industrial: Bolted to outside of channel or top of channel.
                    # Let's put them on top of Stringer axis.
                    
                    if px <= total_run:
                        pz_base = px * math.tan(math.radians(slope_angle_deg)) + 1.0 # On top of stringer
                        pz_top = pz_base + rail_height
                    else:
                        # On landing
                        pz_base = total_rise + 1.0
                        pz_top = pz_base + rail_height
                    
                    # Post length
                    p_len = pz_top - pz_base
                    
                    if p_len > 0:
                        with BuildPart() as post_bp:
                             Cylinder(radius=post_od/2, height=p_len, align=(Align.CENTER, Align.CENTER, Align.MIN))
                             # Cylinder(radius=post_id/2, height=p_len, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                        
                        # Move to location
                        # Left Post
                        pl = post_bp.part.move(Location((px, -width/2 - stringer_thickness - post_od/2, pz_base)))
                        posts.append(pl)
                        # Right Post
                        pr = post_bp.part.move(Location((px, width/2 + stringer_thickness + post_od/2, pz_base)))
                        posts.append(pr)

                # Create Rails (Top and Mid)
                # Sweep along a path
                # Path follows logic:
                # Start: (0, 34) relative to nose
                # End: (total_run, total_rise + 34)
                # Landing: (total_run + landing, total_rise + 34)
                
                # Z_rail = Z_nose + 34
                z_offset = rail_height
                mid_offset = mid_rail_height
                
                rail_pts = [
                    ( -12.0, -12.0 * math.tan(math.radians(slope_angle_deg)) + z_offset + 1.0), # Extended start
                    ( total_run, total_rise + z_offset + 1.0), # Knee
                    ( total_run + landing_depth, total_rise + z_offset + 1.0) # End
                ]
                
                with BuildPart() as rail_bp:
                    with BuildLine() as rl:
                        Polyline(rail_pts)
                        # Fillet knee?
                        # fillet(rl.vertices(), radius=4.0) # Build123d 1.0 syntax might allow this
                    
                    # Sweep profile
                    with BuildSketch(Plane.YZ): # Normal to start? No, simplistic
                         Circle(post_od/2)
                         
                    sweep()
                
                # This sweep is tricky because start viewing plane is not normal to path.
                # Build123d `sweep` usually creates profile at start of path.
                # My path starts at a slope.
                # Simplification: Create separate cylinders for slope and landing rails.
                
                # Slope Rail
                slope_len = math.sqrt((rail_pts[1][0]-rail_pts[0][0])**2 + (rail_pts[1][1]-rail_pts[0][1])**2)
                with BuildPart() as s_rail:
                    Cylinder(radius=post_od/2, height=slope_len, align=(Align.CENTER, Align.CENTER, Align.MIN))
                
                # Rotate slope rail
                s_rail_part = s_rail.part.rotate(Axis.Y, -slope_angle_deg)
                # Position
                s_rail_part = s_rail_part.move(Location((rail_pts[0][0], 0, rail_pts[0][1])))
                # Actually rotation is around origin.
                # Center of cylinder base is at (0,0,0). Rotation pivots there. 
                # Move to start point. Correct.
                
                # Landing Rail
                land_len = rail_pts[2][0] - rail_pts[1][0]
                with BuildPart() as l_rail:
                     # Horizontal cylinder along X
                     Cylinder(radius=post_od/2, height=land_len, align=(Align.CENTER, Align.CENTER, Align.MIN))
                     # Default cylinder is along Z. Rotate to X.
                
                l_rail_part = l_rail.part.rotate(Axis.Y, 90)
                l_rail_part = l_rail_part.move(Location((rail_pts[1][0], 0, rail_pts[1][1])))
                
                # Add rails to list
                # Top Rail Left
                original_y = 0
                left_y = -width/2 - stringer_thickness - post_od/2
                right_y = width/2 + stringer_thickness + post_od/2
                
                rails.append(s_rail_part.move(Location((0, left_y, 0))))
                rails.append(l_rail_part.move(Location((0, left_y, 0))))
                
                rails.append(s_rail_part.move(Location((0, right_y, 0))))
                rails.append(l_rail_part.move(Location((0, right_y, 0))))
                
                # Mid Rails (Offset down by 17")
                # Simple translation of top rails
                dz_mid = -(rail_height - mid_rail_height)
                rails.append(s_rail_part.move(Location((0, left_y, dz_mid))))
                rails.append(l_rail_part.move(Location((0, left_y, dz_mid))))
                rails.append(s_rail_part.move(Location((0, right_y, dz_mid))))
                rails.append(l_rail_part.move(Location((0, right_y, dz_mid))))


                # Add Treads
                all_parts = [s1, s2] + treads + posts + rails
                
                add(all_parts)
                
            # Convert to USD
            # Create a Xform to hold everything
            root_prim = UsdGeom.Xform.Define(stage, path)
            
            # Mesh
            mesh_prim = usd_utils.create_mesh_from_shape(stage, f"{path}/Geometry", bp.part)
            
            # Store Metadata
            custom_data = root_prim.GetPrim().GetCustomData()
            custom_data['stair_params'] = {
                'rise': total_rise,
                'width': width,
                'run': run
            }
            root_prim.GetPrim().SetCustomData(custom_data)
            
            return root_prim

        except Exception as e:
            print(f"[Stair] Error: {e}")
            import traceback; traceback.print_exc()
            return None

    @staticmethod
    def _create_stringer_side(rise, run, landing, depth, angle, stringer_flange_thickness=0.44, stringer_thickness=0.24, section="left"):
        """
        Creates a single stringer solid (C-Channel).
        Origin is at bottom nose line start (0,0,0).
        """
        # Create the side profile (2D) in XZ plane
        # Then extrude Y.
        
        # Points for the profile
        # Sloped section top/bottom
        # Landing section top/bottom
        
        # Angle in radians
        a = math.radians(angle)
        cosa = math.cos(a)
        sina = math.sin(a)
        
        # Flight length (horizontal projection)
        L = run
        
        # Thicknesses
        flange_w = 2.6
        web_t = 0.24
        
        # We build a solid polygon extrude for the web + flanges
        # But simpler: Extrude a profile along a path.
        
        # Let's just build the solid shape using Constructive Solid Geometry (CSG)
        
        # 1. The main body (Web)
        # Defined by a path: (0,0) -> (run, rise) for nose line
        # Offset path down by some amount to clear treads
        offset_down = 2.0 
        
        path_pts = [
            (-10.0, -10.0 * math.tan(a)), # Start extended down
            (run, rise), # Top of slope
            (run + landing, rise) # Landing end
        ]
        
        # Create a wire? No, simpler.
        # Make a large block and cut it.
        
        with BuildPart() as sp:
            # Draw the side profile valid for extrusion
            with BuildSketch(Plane.XZ):
                with BuildLine():
                    # Geometry construction
                    # Top line of slope (shifted down from nose)
                    # y = tan(a)*x - offset
                    pass
                
                # Simpler: Make the profile of the stringer in XZ
                # 1. Slope Top
                # 2. Landing Top
                # 3. Landing End (Vertical)
                # 4. Landing Bottom
                # 5. Slope Bottom
                # 6. Floor Cut (Horizontal)
                
                # Nose line: z = x * tan(a)
                # Top Stringer Edge: z = x * tan(a) - 2.0 (approx)
                # Bottom Stringer Edge: z = x * tan(a) - 2.0 - 10.0 (depth)
                
                p0 = (-12, 0) # Floor start (approx)
                
                # Vertices
                # Using simple logic to ensure valid shape
                pts = []
                
                # Top edge
                pts.append((-12.0, 0.0)) # Floor toe
                
                # Intersection of Slope Top and Landing Top
                # Slope Top: Z = X*tan(a) - 2.0
                # Landing Top: Z = Rise - 2.0 (Level with landing?)
                # Actually landing stringer usually continues the slope top until it hits horizontal?
                # Usually: Stringer makes a knee.
                
                # Values
                web_top_offset = 1.0 # Top of web relative to nose line
                web_height = 10.0
                
                # Slope Line functions
                # Z = tan(a) * X
                # Top Edge Line: Z' = tan(a) * X + web_top_offset
                # Bot Edge Line: Z'' = tan(a) * X + web_top_offset - web_height
                
                # Intersection with Landing (Z = Rise)
                # Landing Top Edge: Z = Rise + web_top_offset ?? No, flat.
                # At top, stringer becomes horizontal.
                # So Z = Rise + web_top_offset is the flat part level? 
                
                # Knee Point (Top)
                # Rise + off = tan(a) * X_knee + off -> X_knee = Rise / tan(a) = TotalRun
                # Correct.
                
                # Points:
                # 1. Floor Bot (X=?, Z=0)
                # Intersection Bot Edge with Z=0
                # 0 = tan(a)*X + off - h -> X = (h-off)/tan(a)
                x_floor_bot = (web_height - web_top_offset) / math.tan(a)
                pt_floor_bot = (x_floor_bot, 0)
                
                # 2. Floor Top (X=?, Z=web_height?? No)
                # Cut is horizontal at Z=0 usually? Or vertical?
                # Usually rests on floor. Vertical cut at X=?. Horizontal cut at Z=0.
                # Let's do horizontal cut at Z=0.
                # Intersection Top Edge with Z=0 ? 
                # 0 = tan(a)*X + off -> X = -off/tan(a)
                x_floor_top = -web_top_offset / math.tan(a)
                pt_floor_top = (x_floor_top, 0)
                
                # 3. Knee Top (Join Slope to Landing)
                pt_knee_top = (run, rise + web_top_offset)
                
                # 4. Landing End Top
                pt_land_top = (run + landing, rise + web_top_offset)
                
                # 5. Landing End Bot
                pt_land_bot = (run + landing, rise + web_top_offset - web_height)
                
                # 6. Knee Bot
                # Parallel to knee top?
                # Usually the bottom curve is radiused or sharp. Sharp for now.
                pt_knee_bot = (run, rise + web_top_offset - web_height) # Just go straight down?
                # Wait, angle change.
                # Bot Edge Slope intersection with Bot Edge Horizontal.
                # Horizontal Bot Z = Rise + off - h
                # Slope Bot Z = tan(a)*X + off - h
                # They meet at X=Run.
                
                # Polygon
                Polygon([
                    pt_floor_top,
                    pt_knee_top,
                    pt_land_top,
                    pt_land_bot,
                    pt_knee_bot,
                    pt_floor_bot
                ])
                
            # Extrude Width (Web + Flanges)
            # Actually just extrude the C-shape?
            # We drew the side profile. Extruding this gives a solid plate. 
            # We want a C-channel. 
            # We need to subtract the "inner" profile.
            
            # Extrude full width
            extrude(amount=flange_w)
            
            # Now cut the "C"
            # Inner profile is same as outer, but offset by thickness? 
            # No, C-channel walls are constant thickness.
            # We cut from the "Face" (XY plane? No, side is XZ).
            # We extruded along Y. One face is at Y=0, one at Y=flange_w.
            # We want to pocket from Y=web_t to Y=flange_w.
            
            # Identification of face to cut?
            # It's the face at Y=flange_w (max Y).
            
            with BuildSketch(Plane.XZ.offset(flange_w)):
                # Re-draw profile but offset inward by thickness?
                # Valid for top/bot edges.
                # Use offset tool?
                # Offset usually rounds corners. 
                # Let's manually reconstruct inner polygon.
                
                t = web_t # Thickness
                
                # Offset pts
                # Top edge moves down by t.
                # Bot edge moves up by t.
                # Verticals move in by t? No, ends are open or capped?
                # Ends usually open (saw cut).
                # So we only offset Top and Bottom lines.
                
                # Inner Top Line: Z = tan(a)X + off - T_flange
                # Inner Bot Line: Z = tan(a)X + off - h + T_flange
                # Landing Inner Top: Z = Rise + off - T_flange
                # Landing Inner Bot: Z = Rise + off - h + T_flange
                
                ft = stringer_flange_thickness # Flange thickness (not web)
                
                # New Points
                # Knee Top Inner
                pt_kt_i = (run, rise + web_top_offset - ft)
                # Landing Top Inner
                pt_lt_i = (run + landing, rise + web_top_offset - ft)
                
                # Knee Bot Inner
                pt_kb_i = (run, rise + web_top_offset - web_height + ft)
                # Landing Bot Inner
                pt_lb_i = (run + landing, rise + web_top_offset - web_height + ft)
                
                # Floor Top Inner
                # Intersect Inner Top with Z=0? No, cut is physical saw cut at 0.
                # So polygon clip at Z=0.
                # Z=0 line.
                # x = -(off - ft)/tan(a)
                x_fti = -(web_top_offset - ft) / math.tan(a)
                pt_fti = (x_fti, 0)
                
                # Floor Bot Inner
                x_fbi = (web_height - web_top_offset - ft) / math.tan(a) # Check sign
                # Bot line: Z = tanX + off - h + ft
                # 0 = tanX + off - h + ft -> X = -(off - h + ft)/tan = (h - off - ft)/tan
                x_fbi = (web_height - web_top_offset - ft) / math.tan(a)
                pt_fbi = (x_fbi, 0)
                
                Polygon([
                    pt_fti, pt_kt_i, pt_lt_i, pt_lb_i, pt_kb_i, pt_fbi
                ])
                
            # Cut
            # Depth of cut = flange_w - web_t
            extrude(amount=-(flange_w - web_t), mode=Mode.SUBTRACT)
        
        return sp.part

