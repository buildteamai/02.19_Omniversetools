import unittest
import sys
import os

# Add extension root to path to allow imports
sys.path.append("c:/Programming/buildteamai/exts/company.twin.tools")

from company.twin.tools.objects.frame import FrameGenerator
import build123d as bd

class TestFrameGenerator(unittest.TestCase):
    def setUp(self):
        # Mock AISC data
        self.col_section = {
            "designation": "W10x33",
            "depth_d": 9.73,
            "flange_width_bf": 7.96,
            "flange_thickness_tf": 0.435,
            "web_thickness_tw": 0.29,
            "fillet_radius_k": 0.5
        }
        self.header_section = {
            "designation": "W12x26",
            "depth_d": 12.2,
            "flange_width_bf": 6.49,
            "flange_thickness_tf": 0.380,
            "web_thickness_tw": 0.230,
            "fillet_radius_k": 0.5
        }

    def test_frame_generation(self):
        width = 120.0  # 10 ft
        height = 120.0  # 10 ft
        bp_size = (12.0, 12.0, 0.75)

        frame_data = FrameGenerator.create_simple_frame(
            self.col_section,
            self.header_section,
            width,
            height,
            bp_size
        )

        parts = frame_data['parts']
        transforms = frame_data['transforms']

        # 1. Parts existence (simplified frame: base plates, columns, header)
        expected_parts = ['base_plate_left', 'base_plate_right',
                          'column_left', 'column_right', 'header']
        for part in expected_parts:
            self.assertIn(part, parts, f"Missing part: {part}")

        # 2. Header Y: sits on top of columns
        # col_length = height - bp_thk - header_depth = 120 - 0.75 - 12.2 = 107.05
        # header_center_y = bp_thk + col_length + header_depth/2
        #                 = 0.75 + 107.05 + 6.1 = 113.9
        header_loc = transforms['header']
        self.assertAlmostEqual(header_loc.position.Y, 113.9, delta=0.01)

        # 3. Header X start: header_length = width - col_depth - 1.0
        #    = 120 - 9.73 - 1.0 = 109.27
        #    start X = -109.27 / 2 = -54.635
        expected_header_len = 120.0 - 9.73 - 1.0  # 109.27
        self.assertAlmostEqual(
            header_loc.position.X, -expected_header_len / 2, delta=0.01
        )

        # 4. Verify metadata records correct header_length
        self.assertAlmostEqual(
            frame_data['metadata']['header_length'], expected_header_len, delta=0.01
        )

        print("Frame Generation Test Passed!")

    def test_rotated_columns_stay_vertical(self):
        """Rotated columns should still be vertical (Y-up), just profile spun 90°."""
        width = 120.0
        height = 120.0
        bp_size = (12.0, 12.0, 0.75)

        frame_data = FrameGenerator.create_simple_frame(
            self.col_section,
            self.header_section,
            width,
            height,
            bp_size,
            rotate_columns=True
        )

        transforms = frame_data['transforms']

        # Column position Y should still start at bp_thk
        col_loc = transforms['column_left']
        self.assertAlmostEqual(col_loc.position.Y, 0.75, delta=0.01)

        # Column X should be at -width/2
        self.assertAlmostEqual(col_loc.position.X, -60.0, delta=0.01)

        print("Rotated Column Orientation Test Passed!")


if __name__ == '__main__':
    unittest.main()

