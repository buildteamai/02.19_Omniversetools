"""Golden reference tests for the Geometry Guardrails (Layer 4).

Run from the extension root:
    python -m pytest tests/test_guardrails.py -v

No USD / Omniverse dependencies — pure build123d.
"""

from __future__ import annotations

import math
import sys
import os

import pytest

# Ensure the extension source tree is importable
_EXT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXT_ROOT not in sys.path:
    sys.path.insert(0, _EXT_ROOT)

import build123d as bd

from company.twin.tools.utils.geometry_primitives import (
    circular_array,
    horizontal_extrude,
    mirror_solid,
    revolve_profile,
    vertical_box,
    vertical_cylinder,
    vertical_extrude,
)
from company.twin.tools.utils.geometry_validator import (
    GeometryValidationError,
    validate,
    validate_bounds,
    validate_ground_plane,
    validate_orientation,
    validate_symmetry,
)
from company.twin.tools.utils.anchors import (
    AnchorSet,
    align_to,
    place_at,
    stack_on,
)


# ===================================================================
# Helpers
# ===================================================================

def _bb(solid):
    """Shorthand for bounding box."""
    return solid.bounding_box()


def _dims(solid):
    """Return (size_x, size_y, size_z) of the bounding box."""
    bb = solid.bounding_box()
    return (bb.max.X - bb.min.X, bb.max.Y - bb.min.Y, bb.max.Z - bb.min.Z)


# ===================================================================
# Test: Vertical Primitives
# ===================================================================

class TestVerticalBox:
    def test_bottom_aligned(self):
        s = vertical_box(10, 20, 10)
        bb = _bb(s)
        dx, dy, dz = _dims(s)
        assert dx == pytest.approx(10, abs=0.01)
        assert dy == pytest.approx(20, abs=0.01)
        assert dz == pytest.approx(10, abs=0.01)
        assert bb.min.Y == pytest.approx(0, abs=0.01), "bottom should be at Y=0"

    def test_center_aligned(self):
        s = vertical_box(10, 20, 10, align_y="center")
        bb = _bb(s)
        assert bb.min.Y == pytest.approx(-10, abs=0.01)
        assert bb.max.Y == pytest.approx(10, abs=0.01)

    def test_top_aligned(self):
        s = vertical_box(10, 20, 10, align_y="top")
        bb = _bb(s)
        assert bb.max.Y == pytest.approx(0, abs=0.01)
        assert bb.min.Y == pytest.approx(-20, abs=0.01)

    def test_x_z_centered(self):
        s = vertical_box(10, 20, 8)
        bb = _bb(s)
        assert bb.min.X == pytest.approx(-5, abs=0.01)
        assert bb.max.X == pytest.approx(5, abs=0.01)
        assert bb.min.Z == pytest.approx(-4, abs=0.01)
        assert bb.max.Z == pytest.approx(4, abs=0.01)


class TestVerticalCylinder:
    def test_bottom_aligned(self):
        s = vertical_cylinder(5, 20)
        bb = _bb(s)
        dy = bb.max.Y - bb.min.Y
        assert dy == pytest.approx(20, abs=0.1)
        assert bb.min.Y == pytest.approx(0, abs=0.1)

    def test_center_aligned(self):
        s = vertical_cylinder(5, 20, align_y="center")
        bb = _bb(s)
        assert bb.min.Y == pytest.approx(-10, abs=0.1)
        assert bb.max.Y == pytest.approx(10, abs=0.1)

    def test_radius(self):
        s = vertical_cylinder(5, 20)
        bb = _bb(s)
        # Cylinder of radius 5 → X and Z extent ≈ 10
        dx = bb.max.X - bb.min.X
        dz = bb.max.Z - bb.min.Z
        assert dx == pytest.approx(10, abs=0.2)
        assert dz == pytest.approx(10, abs=0.2)


class TestVerticalExtrude:
    def test_l_shape(self):
        """Extrude an L-shaped profile and verify bounding box."""
        # L-shape: 4" wide, 6" deep, with a 2"×2" notch
        pts = [(0, 0), (4, 0), (4, 2), (2, 2), (2, 6), (0, 6)]
        s = vertical_extrude(pts, height=10)
        bb = _bb(s)
        dx = bb.max.X - bb.min.X
        dy = bb.max.Y - bb.min.Y
        dz = bb.max.Z - bb.min.Z
        assert dy == pytest.approx(10, abs=0.1), "height should be 10"
        assert bb.min.Y == pytest.approx(0, abs=0.1), "bottom at Y=0"
        # X span = 4, Z span = 6
        assert dx == pytest.approx(4, abs=0.1)
        assert dz == pytest.approx(6, abs=0.1)

    def test_square(self):
        pts = [(-3, -3), (3, -3), (3, 3), (-3, 3)]
        s = vertical_extrude(pts, height=5)
        dx, dy, dz = _dims(s)
        assert dx == pytest.approx(6, abs=0.1)
        assert dy == pytest.approx(5, abs=0.1)
        assert dz == pytest.approx(6, abs=0.1)


# ===================================================================
# Test: Horizontal Primitives
# ===================================================================

class TestHorizontalExtrude:
    def test_extrude_along_x(self):
        # Rectangle 2×3 on YZ plane, extruded 48" along X
        pts = [(-1, -1.5), (1, -1.5), (1, 1.5), (-1, 1.5)]
        s = horizontal_extrude(pts, 48, direction="x")
        bb = _bb(s)
        dx = bb.max.X - bb.min.X
        assert dx == pytest.approx(48, abs=0.1)
        assert bb.min.X == pytest.approx(0, abs=0.1), "starts at X=0"

    def test_extrude_along_z(self):
        pts = [(-1, -1.5), (1, -1.5), (1, 1.5), (-1, 1.5)]
        s = horizontal_extrude(pts, 48, direction="z")
        bb = _bb(s)
        dz = bb.max.Z - bb.min.Z
        assert dz == pytest.approx(48, abs=0.1)
        assert bb.min.Z == pytest.approx(0, abs=0.1), "starts at Z=0"


# ===================================================================
# Test: Revolve
# ===================================================================

class TestRevolve:
    def test_full_circle_torus(self):
        """Revolve a small circle offset from Y-axis to create a torus-like shape."""
        # Small square profile at distance 10 from axis, height -1..1
        pts = [(9, -1), (11, -1), (11, 1), (9, 1)]
        s = revolve_profile(pts, axis="y", angle=360)
        bb = _bb(s)
        # Outer diameter ≈ 22, height ≈ 2
        dx = bb.max.X - bb.min.X
        dz = bb.max.Z - bb.min.Z
        dy = bb.max.Y - bb.min.Y
        assert dx == pytest.approx(22, abs=0.5)
        assert dz == pytest.approx(22, abs=0.5)
        assert dy == pytest.approx(2, abs=0.5)

    def test_revolve_90_degrees(self):
        """Quarter turn should produce geometry in one quadrant."""
        pts = [(9, -1), (11, -1), (11, 1), (9, 1)]
        s = revolve_profile(pts, axis="y", angle=90)
        bb = _bb(s)
        # Should span ~half the full diameter in X and Z (one quadrant)
        assert bb.max.X > 8  # extends in +X
        assert bb.max.Z > 8  # extends in +Z


# ===================================================================
# Test: Circular Array
# ===================================================================

class TestCircularArray:
    def test_array_6_bolts(self):
        """6 small cylinders arrayed at radius 10 around Y."""
        bolt = vertical_cylinder(0.25, 2)
        arr = circular_array(bolt, count=6, radius=10, axis="y")
        # Compound should contain 6 solids
        solids = arr.solids()
        assert len(solids) == 6

    def test_array_positions(self):
        """Verify copies are at roughly the right radius."""
        bolt = vertical_box(0.5, 2, 0.5)
        arr = circular_array(bolt, count=4, radius=10, axis="y")
        for s in arr.solids():
            bb = s.bounding_box()
            cx = (bb.min.X + bb.max.X) / 2
            cz = (bb.min.Z + bb.max.Z) / 2
            r = math.sqrt(cx**2 + cz**2)
            assert r == pytest.approx(10, abs=0.5)


# ===================================================================
# Test: Mirror
# ===================================================================

class TestMirror:
    def test_mirror_xz(self):
        """Mirror across XZ (Y=0) flips a box from +Y to −Y."""
        s = vertical_box(4, 10, 4, align_y="bottom")
        m = mirror_solid(s, plane="xz")
        bb = _bb(m)
        # Original: Y [0, 10].  Mirrored across Y=0 → Y [-10, 0]
        assert bb.min.Y == pytest.approx(-10, abs=0.1)
        assert bb.max.Y == pytest.approx(0, abs=0.1)

    def test_mirror_yz(self):
        """Mirror across YZ (X=0) flips X extent."""
        s = vertical_box(4, 10, 4, align_y="bottom")
        # Original is centered on X, so mirror should be identical
        m = mirror_solid(s, plane="yz")
        bb_orig = _bb(s)
        bb_m = _bb(m)
        assert bb_m.min.X == pytest.approx(bb_orig.min.X, abs=0.1)
        assert bb_m.max.X == pytest.approx(bb_orig.max.X, abs=0.1)


# ===================================================================
# Test: Anchors
# ===================================================================

class TestAnchors:
    def test_from_bounding_box(self):
        s = vertical_box(10, 20, 8)
        anchors = AnchorSet.from_bounding_box(s)

        tc = anchors["top_center"]
        assert tc.position[1] == pytest.approx(20, abs=0.1), "top at Y=20"
        bc = anchors["bottom_center"]
        assert bc.position[1] == pytest.approx(0, abs=0.1), "bottom at Y=0"

        # Corners
        tfl = anchors["top_front_left"]
        assert tfl.position[0] == pytest.approx(-5, abs=0.1)   # left = -X
        assert tfl.position[1] == pytest.approx(20, abs=0.1)   # top = max Y
        assert tfl.position[2] == pytest.approx(4, abs=0.1)    # front = +Z

    def test_from_cylinder(self):
        anchors = AnchorSet.from_cylinder(5, 20, align_y="bottom")
        assert anchors["top_center"].position[1] == pytest.approx(20, abs=0.01)
        assert anchors["bottom_center"].position[1] == pytest.approx(0, abs=0.01)
        assert anchors["mid_east"].position[0] == pytest.approx(5, abs=0.01)

    def test_place_at(self):
        s = vertical_box(4, 8, 4)
        anchors = AnchorSet.from_bounding_box(s)
        target = (10, 0, 20)
        moved, loc = place_at(s, "bottom_center", anchors, target)
        bb = _bb(moved)
        # Bottom centre should now be at (10, 0, 20)
        cx = (bb.min.X + bb.max.X) / 2
        assert cx == pytest.approx(10, abs=0.1)
        assert bb.min.Y == pytest.approx(0, abs=0.1)
        cz = (bb.min.Z + bb.max.Z) / 2
        assert cz == pytest.approx(20, abs=0.1)

    def test_align_to(self):
        """Align the bottom of component A to the top of component B."""
        base = vertical_box(10, 5, 10)
        base_anchors = AnchorSet.from_bounding_box(base)

        col = vertical_box(2, 20, 2)
        col_anchors = AnchorSet.from_bounding_box(col)

        moved_col, _ = align_to(
            col, "bottom_center", col_anchors,
            base, "top_center", base_anchors,
        )
        bb = _bb(moved_col)
        # Column bottom should be at base top (Y=5)
        assert bb.min.Y == pytest.approx(5, abs=0.1)

    def test_stack_on(self):
        base = vertical_box(10, 5, 10)
        base_anchors = AnchorSet.from_bounding_box(base)
        top = vertical_box(8, 3, 8)
        top_anchors = AnchorSet.from_bounding_box(top)

        moved_top, _ = stack_on(
            top, "bottom_center", top_anchors,
            base, "top_center", base_anchors,
        )
        bb = _bb(moved_top)
        assert bb.min.Y == pytest.approx(5, abs=0.1)
        assert bb.max.Y == pytest.approx(8, abs=0.1)

    def test_chainable_add(self):
        a = AnchorSet("test").add("a", (0, 0, 0)).add("b", (1, 1, 1))
        assert "a" in a
        assert "b" in a


# ===================================================================
# Test: Validator
# ===================================================================

class TestValidator:
    def test_correct_box_passes(self):
        s = vertical_box(10, 20, 10)
        r = validate(s, bounds=(10, 20, 10), orientation="y", ground_plane=0.0)
        assert r.passed

    def test_wrong_orientation_fails(self):
        """A flat box (wider than tall) should fail vertical orientation check."""
        s = vertical_box(20, 5, 20)
        r = validate(s, orientation="y")
        assert not r.passed

    def test_below_ground_fails(self):
        s = vertical_box(10, 20, 10, align_y="center")
        r = validate(s, ground_plane=0.0)
        assert not r.passed, "centred box has min_Y = -10, not 0"

    def test_wrong_bounds_fails(self):
        s = vertical_box(10, 20, 10)
        r = validate(s, bounds=(10, 10, 10))  # Y is 20, not 10
        assert not r.passed

    def test_symmetry_centered_box(self):
        s = vertical_box(10, 20, 10, align_y="center")
        r = validate(s, symmetry="yz")
        assert r.passed, "box centred on X should be symmetric about YZ"

    def test_symmetry_offset_fails(self):
        s = vertical_box(10, 20, 10, align_y="bottom")
        r = validate(s, symmetry="xz")
        # Bottom at Y=0, top at Y=20 → not symmetric about XZ (Y=0)
        assert not r.passed

    def test_strict_raises(self):
        s = vertical_box(10, 20, 10)
        with pytest.raises(GeometryValidationError):
            validate(s, bounds=(5, 5, 5), strict=True)

    def test_validate_bounds_directly(self):
        s = vertical_box(10, 20, 10)
        cr = validate_bounds(s, 10, 20, 10)
        assert cr.passed
        assert cr.name == "bounding_box"

    def test_validate_ground_plane_directly(self):
        s = vertical_box(10, 20, 10)
        cr = validate_ground_plane(s, expected_min_y=0.0)
        assert cr.passed


# ===================================================================
# Test: Golden References — known-correct geometry by dimension
# ===================================================================

class TestGoldenReferences:
    """Regression-proof specific shapes with known bounding-box dimensions."""

    def test_golden_vertical_leg(self):
        """A 3×3 HSS tube used as a 36" vertical leg."""
        leg = vertical_box(3, 36, 3, align_y="bottom")
        r = validate(leg, bounds=(3, 36, 3), orientation="y", ground_plane=0.0)
        assert r.passed, r.summary()

    def test_golden_horizontal_beam(self):
        """A 6×4 beam running 120" along Z."""
        pts = [(-3, -2), (3, -2), (3, 2), (-3, 2)]
        beam = horizontal_extrude(pts, 120, direction="z")
        dx, dy, dz = _dims(beam)
        assert dx == pytest.approx(4, abs=0.1)
        assert dy == pytest.approx(6, abs=0.1)
        assert dz == pytest.approx(120, abs=0.1)

    def test_golden_cylinder_tank(self):
        """A 24" radius, 48" tall vertical cylinder (tank)."""
        tank = vertical_cylinder(24, 48, align_y="bottom")
        r = validate(
            tank,
            bounds=(48, 48, 48),
            orientation=None,  # square-ish, skip
            ground_plane=0.0,
            tolerance=0.5,
        )
        assert r.passed, r.summary()

    def test_golden_assembly_two_legs_and_beam(self):
        """Two vertical legs with a horizontal beam across the top."""
        leg_h = 36
        leg = vertical_box(3, leg_h, 3)
        beam = vertical_box(48, 3, 3)

        leg_a = AnchorSet.from_bounding_box(leg)
        beam_a = AnchorSet.from_bounding_box(beam)

        # Place left leg at origin
        left_leg = leg

        # Place right leg 48" to the right
        right_leg, _ = place_at(leg, "bottom_center", leg_a, (24, 0, 0))

        # Place beam on top of left leg (its bottom_center at left leg top_center)
        left_leg_a = AnchorSet.from_bounding_box(left_leg)
        moved_beam, _ = place_at(beam, "bottom_center", beam_a, (0, leg_h, 0))

        # Verify beam is at the right height
        bb = _bb(moved_beam)
        assert bb.min.Y == pytest.approx(leg_h, abs=0.1)
        assert bb.max.Y == pytest.approx(leg_h + 3, abs=0.1)
