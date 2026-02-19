import omni.usd
from pxr import UsdGeom, Gf, Sdf
import os

class FanGenerator:
    """
    Generates a Fan object by referencing a CAD file.
    """
    def __init__(self):
        pass

    def create_fan(self, stage, path, position):
        """
        Creates a Fan at the specified path and position.
        """
        if not path:
            return

        # Define the Xform reference
        ref_prim = UsdGeom.Xform.Define(stage, path)
        ref_prim.AddTranslateOp().Set(Gf.Vec3d(*position))

        # Absolute path to the DWG
        # Assuming this file is in .../tools/mechanical/fan.py
        # And DWG is in .../tools/CAD/VAB-3D.dwg
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tools_dir = os.path.dirname(current_dir) # Go up to .../tools
        cad_path = os.path.join(tools_dir, "CAD", "VAB-3D.dwg")
        
        # Normalize path for USD
        cad_path = cad_path.replace("\\", "/")

        print(f"[Fan] Generating VAB Fan at {path}")

        # VAB Fan Parameters (Approximate based on image)
        radius = 24.0
        length = 48.0
        housing_thickness = 1.0
        motor_size = 12.0
        
        # Root Xform
        fan_root = UsdGeom.Xform.Define(stage, path)
        fan_root.ClearXformOpOrder() # Reset transforms
        fan_root.AddTranslateOp().Set(Gf.Vec3d(*position))

        # 1. Housing (Cylinder)
        housing_path = f"{path}/housing"
        housing = UsdGeom.Cylinder.Define(stage, housing_path)
        housing.GetRadiusAttr().Set(radius)
        housing.GetHeightAttr().Set(length)
        housing.GetAxisAttr().Set(UsdGeom.Tokens.x) # Flow direction X
        housing.GetDisplayColorAttr().Set([(0.5, 0.5, 0.55)]) # Industrial Grey
        
        # 2. Motor Mount (Top)
        mount_path = f"{path}/mount"
        mount = UsdGeom.Cube.Define(stage, mount_path)
        mount.AddScaleOp().Set(Gf.Vec3d(8.0, 6.0, 1.0)) # Flat plate
        mount.AddTranslateOp().Set(Gf.Vec3d(0, radius + 2.0, 0)) # On top
        mount.GetDisplayColorAttr().Set([(0.3, 0.3, 0.3)])
        
        # 3. Motor (Blue)
        motor_path = f"{path}/motor"
        motor = UsdGeom.Cylinder.Define(stage, motor_path)
        motor.GetRadiusAttr().Set(motor_size/2.0)
        motor.GetHeightAttr().Set(motor_size * 1.5)
        motor.GetAxisAttr().Set(UsdGeom.Tokens.x)
        motor.AddTranslateOp().Set(Gf.Vec3d(0, radius + 2.0 + motor_size/1.5, 0))
        motor.GetDisplayColorAttr().Set([(0.1, 0.2, 0.6)]) # Industrial Blue
        
        # 4. Fan Blades (Internal Disc)
        blades_path = f"{path}/blades_hub"
        blades = UsdGeom.Cylinder.Define(stage, blades_path)
        blades.GetRadiusAttr().Set(radius * 0.9)
        blades.GetHeightAttr().Set(2.0)
        blades.GetAxisAttr().Set(UsdGeom.Tokens.x)
        blades.GetDisplayColorAttr().Set([(0.8, 0.8, 0.8)]) # Aluminum
        # Rotate blades to look dynamic
        # blades.AddRotateXOp().Set(15.0) 

        # 5. Base Legs (Front and Back)
        input_flange_x = -length/2.0 + 4.0
        output_flange_x = length/2.0 - 4.0
        
        for name, x_pos in [("leg_front", input_flange_x), ("leg_rear", output_flange_x)]:
            leg_path = f"{path}/{name}"
            leg = UsdGeom.Cube.Define(stage, leg_path)
            # Legs go from housing bottom to ground? 
            # Assuming center is at Y=Radius (so ground is Y=0 if pos is 0,0,0?? No usually pos is center)
            # Let's assume legs stick out bottom.
            # Dimensions: Thick plate
            leg.AddScaleOp().Set(Gf.Vec3d(2.0, radius + 4.0, radius + 4.0)) 
            leg.AddTranslateOp().Set(Gf.Vec3d(x_pos, -radius/2.0, 0)) # Shift down
            leg.GetDisplayColorAttr().Set([(0.4, 0.4, 0.4)])

        # Metadata
        prim = fan_root.GetPrim()
        custom = prim.GetCustomData()
        custom['asset_path'] = cad_path
        prim.SetCustomData(custom)
        
        return fan_root
