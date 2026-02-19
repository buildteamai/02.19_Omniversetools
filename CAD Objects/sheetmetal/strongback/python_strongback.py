from build123d import *
import os

def create_strongback(length=24.0, width=8.0, height=4.0, thickness=0.125, hole_spacing=6.0, hole_dia=0.5):
    """
    Creates a C-Channel Strongback with mounting holes.
    Dimensions in inches. 
    Based on STEP file analysis:
    - X-Range: 24" (609.6mm)
    - Y-Range: 4" (101.6mm)
    - Z-Range: 8" (203.2mm)
    """
    with BuildPart() as bp:
        # Create C-Channel Profile
        # Orientation matches typical structural usage
        with BuildSketch() as sk:
            with BuildLine() as ln:
                # C-Channel profile
                l1 = Polyline(
                    (0, height), 
                    (0, 0), 
                    (width, 0), 
                    (width, height)
                )
                offset(l1, amount=thickness, side=Side.RIGHT, closed=True)
            make_face()
        
        # Extrude to length
        extrude(amount=length)
        
        # Add Holes
        # Web face is the bottom (Y=0, spanning X=0..width)
        # We need to find the correct face.
        web_face = bp.faces().sort_by(Axis.Y)[0]
        
        with BuildSketch(web_face) as sk2:
             # Grid of holes along length (Z axis of part)
            with GridLocations(x_spacing=0, y_spacing=hole_spacing, count_x=1, count_y=int(length // hole_spacing)):
                 Circle(radius=hole_dia/2)
        
        extrude(amount=-thickness*2, mode=Mode.SUBTRACT)

    return bp.part

if __name__ == "__main__":
    print("Generating Verified Strongback...")
    part = create_strongback(length=24.0, width=8.0, height=4.0)
    
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "verified_strongback.step")
    
    export_step(part, out_path)
    print(f"Exported to: {out_path}")
