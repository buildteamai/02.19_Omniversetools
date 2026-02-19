from pxr import Usd, UsdGeom, UsdLux, Gf, Sdf

def create_template():
    stage_path = "c:/Programming/buildteamai/templates/ANSI_Grey_Studio.usd"
    print(f"Creating template at {stage_path}...")
    
    stage = Usd.Stage.CreateNew(stage_path)
    if not stage:
        print("Error: Could not create stage. It might already exist.")
        stage = Usd.Stage.Open(stage_path)
        
    # 1. Set Units to Inches (ANSI)
    UsdGeom.SetStageMetersPerUnit(stage, 0.0254)
    
    # 2. Set Up Axis to Y (Standard Project Axis)
    # Changed from Z to Y to match Enclosure Configurator.
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    
    # 3. Create Default Prim
    root = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(root.GetPrim())
    
    # 4. Create "Grey Studio" Lighting
    # A Dome Light with a grey color
    light_path = "/World/Environment/GreyStudio"
    dome = UsdLux.DomeLight.Define(stage, light_path)
    
    # Grey Color (Linear Space)
    # 0.18 is middle grey in linear, but for "Studio" look might be brighter.
    # Let's go with a soft white-grey.
    dome.GetColorAttr().Set(Gf.Vec3f(0.8, 0.8, 0.8)) 
    dome.GetIntensityAttr().Set(1000.0) # Standard intensity
    
    # Ensure Environment Scope exists
    env = UsdGeom.Scope.Define(stage, "/World/Environment")
    
    stage.GetRootLayer().Save()
    print(f"Success! Template saved to {stage_path}")

try:
    create_template()
except Exception as e:
    print(f"Error: {e}")
