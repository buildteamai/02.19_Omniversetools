
import unittest
import sys
import os
import math

# Add the extension root to sys.path
EXT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(EXT_ROOT)

from company.twin.solvers.frame_solver import FrameSolver

class TestFrameSolver(unittest.TestCase):
    
    def setUp(self):
        self.solver = FrameSolver()
        
        self.w10x49 = {
            'depth_d': 10.0,
            'flange_width_bf': 10.0,
            'flange_thickness_tf': 0.56,
            'web_thickness_tw': 0.34
        }
        
        self.w12x14 = {
            'depth_d': 11.9,
            'flange_width_bf': 3.97,
            'flange_thickness_tf': 0.225, 
            'web_thickness_tw': 0.2
        }
    
    def test_standard_orientation(self):
        """Test Standard Orientation (Web Perp to Frame Line)"""
        # Half Width = 5.0
        # Header Len = 100 - 5 - 5 - 1 = 89.0
        
        inputs = {
            'width': 100.0,
            'height': 100.0,
            'col_profile': self.w10x49,
            'header_profile': self.w10x49,
            'col_orientation': 0.0,
            'gap': 0.5,
            'bp_size': (14.0, 14.0, 0.75)
        }
        
        result = self.solver.solve(inputs)
        
        self.assertAlmostEqual(result['metadata']['header_length'], 89.0, places=3)
        print("Test Standard (0 deg) Passed: Header Length 89.0")

    def test_rotated_90(self):
        """Test Rotated 90 degrees"""
        # W12x14 Depth=11.9. Half Width = 5.95.
        
        inputs = {
            'width': 100.0,
            'height': 100.0,
            'col_profile': self.w12x14,
            'header_profile': self.w12x14,
            'col_orientation': 90.0,
            'gap': 0.5
        }
        
        result = self.solver.solve(inputs)
        
        expected = 100 - 11.9 - 1.0
        self.assertAlmostEqual(result['metadata']['header_length'], expected, places=3)
        print(f"Test Rotated 90 Passed: Header Length {result['metadata']['header_length']:.4f}")

    def test_engineering_validation(self):
        """Test Engineering Calcs (Deflection/Stress)"""
        inputs = {
            'width': 240.0, # 20 ft
            'height': 120.0,
            'col_profile': self.w10x49,
            'header_profile': self.w10x49,
            'load_plf': 1000.0 # High Load (1 kip/ft)
        }
        
        result = self.solver.solve(inputs)
        
        val = result['metadata'].get('validation')
        self.assertIsNotNone(val)
        
        print(f"Validation: {val}")
        
        # Check that we have values
        self.assertGreater(val['deflection'], 0)
        self.assertGreater(val['stress'], 0)
        
        # With 1000 plf on 20ft W10x49, it might deflect significantly.
        # Ix=272 in4 (approx). W10x49.
        # L=240. w=1/12 kips/in = 0.0833.
        # Delta = 5*0.0833*240^4 / (384*29000*272)
        # = 5*0.0833*3317760000 / 3031296000 ~= 0.45 in.
        # Limit L/240 = 1.0. 
        # So it should PASS deflection.
        
        self.assertEqual(val['status'], 'PASS')
        
        # Try insane load to make it FAIL
        inputs['load_plf'] = 10000.0
        result_fail = self.solver.solve(inputs)
        self.assertEqual(result_fail['metadata']['validation']['status'], 'FAIL')
        print("Test Engineering Checks Passed (Pass/Fail)")

if __name__ == '__main__':
    unittest.main()
