import re
import math

def analyze_step(file_path):
    print(f"Analyzing {file_path}...")
    
    with open(file_path, 'r') as f:
        content = f.read()

    # Regex to find CARTESIAN_POINT
    # #14=CARTESIAN_POINT('',(0.,0.,0.)) ;
    # #26=CARTESIAN_POINT('Axis2P3D Location',(0.,87.757,50.038)) ;
    
    pattern = re.compile(r"CARTESIAN_POINT\s*\([^,]*,\s*\(\s*([-\d\.E]+)\s*,\s*([-\d\.E]+)\s*,\s*([-\d\.E]+)\s*\)\s*\)")
    
    matches = pattern.findall(content)
    
    if not matches:
        print("No CARTESIAN_POINTs found.")
        return

    points = []
    for m in matches:
        x, y, z = float(m[0]), float(m[1]), float(m[2])
        points.append((x, y, z))
        
    print(f"Found {len(points)} points.")
    
    if not points:
        return

    # Filter out potential "garbage" or distant origin points if any (naive approach)
    # Just do raw bbox first
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    
    len_x = max_x - min_x
    len_y = max_y - min_y
    len_z = max_z - min_z
    
    print(f"Bounding Box (Raw Units - likely mm):")
    print(f"  X: {min_x:.2f} to {max_x:.2f} (Length: {len_x:.2f})")
    print(f"  Y: {min_y:.2f} to {max_y:.2f} (Length: {len_y:.2f})")
    print(f"  Z: {min_z:.2f} to {max_z:.2f} (Length: {len_z:.2f})")
    
    # Unit conversion guess (STEP is usually mm, but sometimes files are inches)
    # 609.6 mm = 24 inches exactly.
    # 4 inches = 101.6 mm.
    
    print(f"\nInferred Dimensions (assuming mm input):")
    print(f"  Length: {len_x:.2f} mm (~{len_x/25.4:.2f} inches)")
    print(f"  Width:  {len_y:.2f} mm (~{len_y/25.4:.2f} inches)")
    print(f"  Height: {len_z:.2f} mm (~{len_z/25.4:.2f} inches)")

if __name__ == "__main__":
    analyze_step(r"c:\Programming\buildteamai\CAD Objects\sheetmetal\strongback\strongback.step")
