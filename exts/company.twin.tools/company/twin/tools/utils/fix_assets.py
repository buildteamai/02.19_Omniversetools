import os
from pxr import Usd, UsdGeom

def fix_assets(root_dir, target_mpu=0.01):
    """
    Recursively fixes metersPerUnit metadata on USD files.
    Default target_mpu = 0.01 (Centimeters).
    """
    with open("c:/Programming/buildteamai/exts/company.twin.tools/company/twin/tools/utils/fix_units.log", "w") as log:
        log.write(f"Scanning {root_dir}...\n")
        
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if not file.endswith(".usd") and not file.endswith(".usda"):
                    continue
                    
                file_path = os.path.join(root, file)
                scanned_count += 1
                
                try:
                    stage = Usd.Stage.Open(file_path)
                    if not stage:
                        log.write(f"Failed to open: {file_path}\n")
                        continue
                        
                    current_mpu = UsdGeom.GetStageMetersPerUnit(stage)
                    
                    if abs(current_mpu - target_mpu) > 0.0001:
                        log.write(f"Fixing {file}: {current_mpu} -> {target_mpu}\n")
                        UsdGeom.SetStageMetersPerUnit(stage, target_mpu)
                        stage.GetRootLayer().Save()
                        fixed_count += 1
                    else:
                        log.write(f"Skipping {file}: Already {current_mpu}\n")
                        
                except Exception as e:
                    log.write(f"Error processing {file_path}: {e}\n")

        log.write(f"Done. Scanned {scanned_count} files. Fixed {fixed_count} files.\n")
        print(f"Log written to c:/Programming/buildteamai/exts/company.twin.tools/company/twin/tools/utils/fix_units.log")

if __name__ == "__main__":
    # Target the OHPF directory specifically
    target_dir = r"c:\Programming\buildteamai\CAD Objects\OHPF"
    if os.path.exists(target_dir):
        fix_assets(target_dir, target_mpu=0.01) # Force to CM
    else:
        print(f"Directory not found: {target_dir}")
