from pxr import Usd, UsdGeom

stage_path = r"c:\Programming\buildteamai\CAD Objects\OHPF\ohpf_strt.usd"
print(f"Inspecting: {stage_path}")
try:
    stage = Usd.Stage.Open(stage_path)
    if not stage:
        print(f"Failed to open stage at {stage_path}")
    else:
        print(f"Opened stage: {stage_path}")
        print(f"MetersPerUnit: {UsdGeom.GetStageMetersPerUnit(stage)}")
        print(f"UpAxis: {UsdGeom.GetStageUpAxis(stage)}")
        
        root = stage.GetPseudoRoot()
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Xformable):
                xform = UsdGeom.Xformable(prim)
                stack = xform.GetResetXformStack()
                if stack:
                    print(f"{prim.GetPath()} ResetXformStack: {stack}")
                
                # Check for explicit scale ops
                for op in xform.GetOrderedXformOps():
                    if op.GetOpType() == UsdGeom.XformOp.TypeScale:
                        print(f"{prim.GetPath()} Scale: {op.Get()}")

except Exception as e:
    print(f"Error: {e}")
