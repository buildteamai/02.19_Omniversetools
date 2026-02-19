import sys
import os

# Add extension path to sys.path
ext_path = r"c:\Programming\buildteamai\exts\company.twin.tools"
sys.path.append(ext_path)

from company.twin.tools.antigravity.core.registry import PartRegistry
from company.twin.tools.antigravity.core.discovery import PortDiscoveryWatcher
from company.twin.tools.antigravity.assemblies.heater_box import HeaterBox
from pxr import Usd, UsdGeom, Sdf, Gf

def test_platform():
    print("Testing Antigravity Platform Initialization...")

    # 1. Test Registry (Fuzzy Matching)
    registry = PartRegistry()
    registry.register_part("Industrial Heater Box", HeaterBox)
    
    # Test fuzzy mapping
    gen_class = registry.get_generator("heater")
    if gen_class == HeaterBox:
        print("[PASS] Fuzzy Registry mapping successful ('heater' -> HeaterBox).")
    else:
        print("[FAIL] Fuzzy Registry mapping failed.")

    # 2. Test Metadata Stamping (New Convention)
    stage = Usd.Stage.CreateInMemory()
    prim = stage.DefinePrim("/HeaterBox", "Xform")
    
    from company.twin.tools.antigravity.core.metadata import stamp_inherent_metadata
    stamp_inherent_metadata(prim, {"system:thermal:btu": 250000})
    
    btu_attr = prim.GetAttribute("antigravity:system:thermal:btu")
    if btu_attr and btu_attr.Get() == 250000:
        print("[PASS] Metadata stamping with categories successful.")
    else:
        print("[FAIL] Metadata stamping with categories failed.")

    # 3. Test Dynamic Scaling (Rib Calculation)
    print("Testing Dynamic Scaling Logic...")
    # Small box: 50 units wide -> 2 ribs min
    small_box_range = (Gf.Vec3f(0,0,0), Gf.Vec3f(50, 50, 50))
    small_heater = HeaterBox(small_box_range)
    small_heater.generate_geometry()
    
    # Large box: 500 units wide -> 5 ribs
    large_box_range = (Gf.Vec3f(0,0,0), Gf.Vec3f(500, 500, 500))
    large_heater = HeaterBox(large_box_range)
    large_heater.generate_geometry()
    
    cfm_small = small_heater.metadata["system:thermal:cfm"]
    cfm_large = large_heater.metadata["system:thermal:cfm"]
    
    if cfm_large > cfm_small:
        print(f"[PASS] Dynamic CFM scaling successful: {cfm_small} vs {cfm_large}")
    else:
        print("[FAIL] Dynamic CFM scaling failed.")

if __name__ == "__main__":
    try:
        test_platform()
    except Exception as e:
        print(f"Test encountered error: {e}")
        import traceback
        traceback.print_exc()
