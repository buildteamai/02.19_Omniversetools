# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

import unittest
from pxr import Usd, UsdGeom, Gf, Sdf
from .utils.port import Port
from .utils.mating import MatingSystem

class TestMatingSystem(unittest.TestCase):
    def setUp(self):
        self.stage = Usd.Stage.CreateInMemory()
        
        # Create Target Object (Fixed)
        self.target_path = "/Target"
        self.target_xform = UsdGeom.Xform.Define(self.stage, self.target_path)
        self.target_xform.AddTranslateOp().Set(Gf.Vec3d(10, 0, 0)) # Located at 10,0,0
        
        # Create Source Object (To be Moved)
        self.source_path = "/Source"
        self.source_xform = UsdGeom.Xform.Define(self.stage, self.source_path)
        self.source_xform.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0)) # Start at origin
        
        # Define Ports
        # Target Port: At (0, 5, 0) relative to Target. Facing +Y (Up).
        # World Pos: (10, 5, 0). Normal: (0, 1, 0).
        self.t_port = Port.define(self.stage, self.target_path, "Port_T", 
            Gf.Vec3d(0, 5, 0), Gf.Vec3d(0, 1, 0))
            
        # Source Port: At (0, 0, 5) relative to Source. Facing +Z.
        # We want to snap Source Port to Target Port.
        # Result: Source Port World should be (10, 5, 0).
        # And Source Port Z should face -Y (0, -1, 0).
        self.s_port = Port.define(self.stage, self.source_path, "Port_S", 
            Gf.Vec3d(0, 0, 5), Gf.Vec3d(0, 0, 1))
            
    def test_snap(self):
        print("Running Snap Test...")
        
        success = MatingSystem.snap(self.s_port, self.t_port)
        self.assertTrue(success)
        
        # Verify Source Object moved
        # We need to calculate where Source Origin should be.
        # Source Port Local: 0, 0, 5. RotIdentity.
        # Target Port World: 10, 5, 0. Rot X=-90 (Up).
        
        # New Source Port Orientation: Down (-Y).
        # Source Port Local Z (+Z) becomes World -Y.
        # This implies Source Rigid Body Rotation.
        # If Local Z -> World -Y, then Rotation is -90 around X.
        
        # Check Source Port World Position
        t_s_world = UsdGeom.XformCache(Usd.TimeCode.Default()).GetLocalToWorldTransform(self.s_port.prim)
        pos = t_s_world.ExtractTranslation()
        print(f"Source Port World Pos: {pos}")
        
        # Should be at (10, 5, 0)
        self.assertTrue(Gf.IsClose(pos, Gf.Vec3d(10, 5, 0), 1e-4))
        
        # Check Source Port Orientation
        # Z-axis should be (0, -1, 0)
        mat = t_s_world
        z_axis = Gf.Vec3d(mat[0][2], mat[1][2], mat[2][2])
        print(f"Source Port World Z: {z_axis}")
        
        self.assertTrue(Gf.IsClose(z_axis, Gf.Vec3d(0, -1, 0), 1e-4))
        print("Test Passed!")

def run_verification():
    print("[VerifyMating] Running Verification Tests...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMatingSystem)
    unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == '__main__':
    unittest.main()
