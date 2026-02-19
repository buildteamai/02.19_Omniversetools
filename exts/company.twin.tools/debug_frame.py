import sys
# Add extension root to path to allow imports
sys.path.append("c:/Programming/buildteamai/exts/company.twin.tools")

from company.twin.tools.objects.frame import FrameGenerator
import build123d as bd

# Mock Data
col_section = {
    "designation": "W10x33",
    "depth_d": 9.73,
    "flange_width_bf": 7.96,
    "flange_thickness_tf": 0.435,
    "web_thickness_tw": 0.29
}
header_section = {
    "designation": "W12x26",
    "depth_d": 12.2,
    "flange_width_bf": 6.49,
    "flange_thickness_tf": 0.380,
    "web_thickness_tw": 0.230
}

width = 144.0
height = 120.0
bp_size = (12.0, 12.0, 0.75)

print(f"Generating Frame: W={width}, H={height}")

frame_data = FrameGenerator.create_simple_frame(
    col_section,
    header_section,
    width,
    height,
    bp_size
)

transforms = frame_data['transforms']

print("\n--- Transforms ---")
for name, loc in transforms.items():
    pos = loc.position
    rot = loc.to_tuple()[1] # Euler angles
    print(f"{name}:")
    print(f"  Pos: ({pos.X:.2f}, {pos.Y:.2f}, {pos.Z:.2f})")
    print(f"  Rot: {rot}")
    
# Specific check for Header Y
header_loc = transforms['header']
print(f"\nHeader Y: {header_loc.position.Y:.2f}")
expected_y = height - (header_section['depth_d']/2)
print(f"Expected Y: {expected_y:.2f}")

# Check Column Rotation logic
col_loc = transforms['column_left']
print(f"\nColumn Rotation: {col_loc.to_tuple()[1]}")
# We expect (-90, 90, 0) or equivalent.
# Rot(-90, X) -> ( -90, 0, 0 )
# Rot(0, 90, 0) -> (0, 90, 0)
# Compound? 
# Let's see what build123d output is.

