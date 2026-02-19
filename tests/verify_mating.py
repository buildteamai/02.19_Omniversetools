
import omni.usd
from pxr import Usd, UsdGeom, Gf, Sdf

def test_mating_logic():
    stage = omni.usd.get_context().get_stage()
    if not stage:
        print("No stage")
        return

    # Create two dummy anchors
    # Anchor A: At (0,0,0), facing X (1,0,0)
    # Anchor B: At (10,0,0), facing X (1,0,0) -> Wrong way, needs to flip to face -X to mate
    
    a_path = "/World/Test_A"
    b_path = "/World/Test_B"
    
    stage.DefinePrim(a_path, "Xform")
    stage.DefinePrim(b_path, "Xform")
    
    anchor_a = UsdGeom.Xform.Define(stage, f"{a_path}/Anchor_Start")
    anchor_a.AddTranslateOp().Set((0,0,0))
    # Rotation for facing X? Identity is usually -Z. 
    # Let's say local X is OUTWARD.
    
    anchor_b = UsdGeom.Xform.Define(stage, f"{b_path}/Anchor_Start")
    anchor_b.AddTranslateOp().Set((10,0,0)) # Offset parent B so anchor is at 0 local?
    # Actually let's set parent B at (10,0,0) and anchor B at (0,0,0) local
    # So B is 10 units away.
    
    UsdGeom.XformCommonAPI(stage.GetPrimAtPath(b_path)).SetTranslate((10,10,0))
    
    print("Testing Mating Calculation...")
    
    # 1. Target (Anchor A) World Transform
    # Identity (0,0,0)
    mat_target = Gf.Matrix4d(1.0) 
    
    # 2. Alignment (Flip 180 Z)
    # We want B to face Opposite of A.
    # If A faces X+, B should face X-.
    # 180 deg around Z flips X to -X.
    flip_mat = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,0,1), 180))
    target_frame = flip_mat * mat_target
    
    # 3. Anchor B Local
    local_transform = Gf.Matrix4d(1.0) # Identity
    
    # 4. New B World
    mat_mover_new = local_transform.GetInverse() * target_frame
    
    print(f"Target Pos: {mat_target.ExtractTranslation()}")
    print(f"New B Pos: {mat_mover_new.ExtractTranslation()}")
    
    # Expected: B should move to (0,0,0) and rotate 180
    assert mat_mover_new.ExtractTranslation() == Gf.Vec3d(0,0,0)
    
    print("Verification Passed!")

test_mating_logic()
