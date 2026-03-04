"""
Tests for Fan Assembly Generator — Step 6 of the fan engineering system.

Pure build123d geometry tests. No USD/Omniverse dependencies.
Run: cd exts/company.twin.tools && python -m pytest tests/test_fan_geometry.py -v
"""

import math
import pytest

bd = pytest.importorskip("build123d")

from company.twin.solvers.fan_classifier import (
    FanDesignPoint, FanClassificationSolver, UnitSystem,
)
from company.twin.solvers.impeller_aero import ImpellerAeroSolver
from company.twin.solvers.volute_solver import VoluteSolver
from company.twin.solvers.fan_structural import FanStructuralSolver
from company.twin.solvers.fan_acoustic import FanAcousticSolver, FanAcousticResult

from company.twin.tools.objects.mep.fan_assembly import (
    create_hub_disk,
    create_shroud_disk,
    create_blade,
    create_blades,
    create_impeller_disks,
    create_impeller,
    create_scroll_housing,
    create_outlet_duct,
    create_inlet_flange,
    create_outlet_flange,
    create_shaft,
    create_base_frame,
    create_inlet_cone,
)


# ===========================================================================
# Fixture: run full solver chain (Steps 1-5) for 15000 CFM / 4 in.WG
# ===========================================================================

def _make_acoustic(cfm=15000, inwg=4.0, rpm=None) -> FanAcousticResult:
    """Run Steps 1-5 to produce a FanAcousticResult."""
    dp = FanDesignPoint(cfm, inwg, rpm=rpm)
    r1 = FanClassificationSolver().solve({'design_point': dp})
    cls = r1['metadata']['classification']
    r2 = ImpellerAeroSolver().solve({'classification': cls})
    aero = r2['metadata']['aero']
    r3 = VoluteSolver().solve({'aero': aero})
    vol = r3['metadata']['volute']
    r4 = FanStructuralSolver().solve({'volute': vol})
    struct = r4['metadata']['structural']
    r5 = FanAcousticSolver().solve({'structural': struct})
    return r5['metadata']['acoustic']


@pytest.fixture(scope="module")
def fan_result():
    """Shared FanAcousticResult for all geometry tests."""
    return _make_acoustic()


@pytest.fixture(scope="module")
def fan_params(fan_result):
    """Extracted geometry parameters from solver chain."""
    acou = fan_result
    struct = acou.structural
    vol = struct.volute
    aero = vol.aero
    return {
        "tip_d": aero.passage.tip_diameter_in,
        "hub_d": aero.passage.hub_diameter_in,
        "outlet_width": aero.passage.outlet_width_in,
        "num_blades": aero.blade.num_blades,
        "stagger": aero.blade.stagger_deg,
        "tip_r": aero.passage.tip_diameter_in / 2.0,
        "hub_r": aero.passage.hub_diameter_in / 2.0,
        "max_r": aero.passage.tip_diameter_in / 2.0 * 1.55,
        "volute_width": vol.volute_width_in,
        "shaft_d": struct.shaft.diameter_in,
        "shaft_len": struct.shaft.length_in,
        "wall_t": struct.housing.wall_thickness_in,
    }


# ===========================================================================
# Hub Disk Tests
# ===========================================================================

class TestHubDisk:
    def test_volume_positive(self, fan_params):
        hub = create_hub_disk(fan_params["tip_d"], fan_params["hub_d"])
        assert hub.volume > 0

    def test_bounding_box_matches_diameter(self, fan_params):
        hub = create_hub_disk(fan_params["tip_d"], fan_params["hub_d"])
        bb = hub.bounding_box()
        x_extent = bb.max.X - bb.min.X
        assert x_extent == pytest.approx(fan_params["tip_d"], rel=0.05)

    def test_has_eye_opening(self, fan_params):
        """Volume should be less than a solid disk (hole subtracted)."""
        tip_r = fan_params["tip_r"]
        thickness = 0.1875
        solid_disk_vol = math.pi * tip_r**2 * thickness
        hub = create_hub_disk(fan_params["tip_d"], fan_params["hub_d"])
        assert hub.volume < solid_disk_vol

    def test_z_extent(self, fan_params):
        hub = create_hub_disk(fan_params["tip_d"], fan_params["hub_d"])
        bb = hub.bounding_box()
        z_extent = bb.max.Z - bb.min.Z
        assert z_extent == pytest.approx(0.1875, rel=0.01)


# ===========================================================================
# Shroud Disk Tests
# ===========================================================================

class TestShroudDisk:
    def test_positioned_at_outlet_width(self, fan_params):
        shroud = create_shroud_disk(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"])
        bb = shroud.bounding_box()
        assert bb.min.Z == pytest.approx(fan_params["outlet_width"], rel=0.05)

    def test_same_od_as_hub(self, fan_params):
        hub = create_hub_disk(fan_params["tip_d"], fan_params["hub_d"])
        shroud = create_shroud_disk(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"])
        hub_bb = hub.bounding_box()
        shroud_bb = shroud.bounding_box()
        hub_x = hub_bb.max.X - hub_bb.min.X
        shroud_x = shroud_bb.max.X - shroud_bb.min.X
        assert hub_x == pytest.approx(shroud_x, rel=0.01)

    def test_volume_positive(self, fan_params):
        shroud = create_shroud_disk(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"])
        assert shroud.volume > 0


# ===========================================================================
# Single Blade Tests
# ===========================================================================

class TestBlade:
    def test_volume_positive(self, fan_params):
        blade = create_blade(
            fan_params["hub_r"], fan_params["tip_r"],
            fan_params["outlet_width"], fan_params["stagger"])
        assert blade.volume > 0

    def test_bounding_box_nonzero(self, fan_params):
        blade = create_blade(
            fan_params["hub_r"], fan_params["tip_r"],
            fan_params["outlet_width"], fan_params["stagger"])
        bb = blade.bounding_box()
        assert (bb.max.X - bb.min.X) > 0
        assert (bb.max.Z - bb.min.Z) > 0

    def test_z_extent_matches_outlet_width(self, fan_params):
        blade = create_blade(
            fan_params["hub_r"], fan_params["tip_r"],
            fan_params["outlet_width"], 0)  # Zero stagger
        bb = blade.bounding_box()
        z_extent = bb.max.Z - bb.min.Z
        assert z_extent == pytest.approx(fan_params["outlet_width"], rel=0.05)


# ===========================================================================
# Blades (circular array) Tests
# ===========================================================================

class TestBlades:
    def test_compound_not_none(self, fan_params):
        blades = create_blades(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"], fan_params["num_blades"],
            fan_params["stagger"])
        assert blades is not None

    def test_volume_positive(self, fan_params):
        blades = create_blades(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"], fan_params["num_blades"],
            fan_params["stagger"])
        assert blades.volume > 0

    def test_volume_scales_with_blade_count(self, fan_params):
        blades_6 = create_blades(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"], 6, fan_params["stagger"])
        blades_12 = create_blades(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"], 12, fan_params["stagger"])
        assert blades_12.volume > blades_6.volume


# ===========================================================================
# Impeller Tests
# ===========================================================================

class TestImpeller:
    def test_compound_not_none(self, fan_params):
        imp = create_impeller(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"], fan_params["num_blades"],
            fan_params["stagger"])
        assert imp is not None

    def test_volume_positive(self, fan_params):
        imp = create_impeller(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"], fan_params["num_blades"],
            fan_params["stagger"])
        assert imp.volume > 0


# ===========================================================================
# Scroll Housing Tests (solid-then-hollow construction)
# ===========================================================================

class TestScrollHousing:
    def test_not_none(self, fan_params):
        housing = create_scroll_housing(
            fan_params["tip_r"], fan_params["volute_width"],
            fan_params["wall_t"], fan_params["hub_d"])
        assert housing is not None

    def test_volume_positive(self, fan_params):
        housing = create_scroll_housing(
            fan_params["tip_r"], fan_params["volute_width"],
            fan_params["wall_t"], fan_params["hub_d"])
        assert housing.volume > 0

    def test_housing_larger_than_impeller(self, fan_params):
        """Housing bounding box should enclose impeller."""
        housing = create_scroll_housing(
            fan_params["tip_r"], fan_params["volute_width"],
            fan_params["wall_t"], fan_params["hub_d"])
        imp = create_impeller(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"], fan_params["num_blades"],
            fan_params["stagger"])
        housing_bb = housing.bounding_box()
        imp_bb = imp.bounding_box()
        housing_x = housing_bb.max.X - housing_bb.min.X
        imp_x = imp_bb.max.X - imp_bb.min.X
        assert housing_x > imp_x

    def test_housing_is_hollow(self, fan_params):
        """Housing volume should be less than a solid cylinder of same radius."""
        housing = create_scroll_housing(
            fan_params["tip_r"], fan_params["volute_width"],
            fan_params["wall_t"], fan_params["hub_d"])
        D = fan_params["tip_r"] * 2.0
        R_end = 0.540 * D * (1.0017 ** 270.0)
        solid_cyl_vol = math.pi * R_end**2 * fan_params["volute_width"]
        assert housing.volume < solid_cyl_vol

    def test_tongue_at_90(self, fan_params):
        """Housing BB extends furthest in +Y (tongue at 90° upblast)."""
        housing = create_scroll_housing(
            fan_params["tip_r"], fan_params["volute_width"],
            fan_params["wall_t"], fan_params["hub_d"])
        bb = housing.bounding_box()
        # Spiral grows from tongue at 90° (top). The flat closing wall
        # at the 270° scroll end extends furthest in +Y direction.
        assert bb.max.Y > abs(bb.min.Y) * 0.5  # extends further into +Y
        assert bb.max.Y > bb.max.X              # +Y > +X (tongue is at top)


# ===========================================================================
# Outlet Duct Tests
# ===========================================================================

class TestOutletDuct:
    def test_volume_positive(self):
        duct = create_outlet_duct(10.0, 8.0, 20.0)
        assert duct.volume > 0

    def test_bb_length_matches(self):
        length = 12.0
        duct = create_outlet_duct(10.0, 8.0, length)
        bb = duct.bounding_box()
        x_extent = bb.max.X - bb.min.X
        assert x_extent == pytest.approx(length, rel=0.01)

    def test_bb_starts_at_zero_x(self):
        duct = create_outlet_duct(10.0, 8.0, 20.0)
        bb = duct.bounding_box()
        assert bb.min.X == pytest.approx(0.0, abs=0.01)


# ===========================================================================
# Inlet Flange Tests
# ===========================================================================

class TestInletFlange:
    def test_volume_positive(self):
        flange = create_inlet_flange(24.0)
        assert flange.volume > 0

    def test_has_center_hole(self):
        """Volume should be less than a solid square plate."""
        D = 24.0
        side = 0.920 * D
        thickness = 0.016 * D
        solid_vol = side * side * thickness
        flange = create_inlet_flange(D)
        assert flange.volume < solid_vol

    def test_has_bolt_holes(self):
        """Volume with bolt holes should be less than plate with only center hole."""
        D = 24.0
        flange = create_inlet_flange(D)
        # Plate with center hole only (no bolt holes) would be larger
        side = 0.920 * D
        thickness = 0.016 * D
        opening_r = 0.720 * D / 2.0
        plate_with_hole_vol = side * side * thickness - math.pi * opening_r**2 * thickness
        assert flange.volume < plate_with_hole_vol

    def test_bb_matches_square(self):
        D = 24.0
        flange = create_inlet_flange(D)
        bb = flange.bounding_box()
        expected_side = 0.920 * D
        x_extent = bb.max.X - bb.min.X
        y_extent = bb.max.Y - bb.min.Y
        assert x_extent == pytest.approx(expected_side, rel=0.02)
        assert y_extent == pytest.approx(expected_side, rel=0.02)


# ===========================================================================
# Outlet Flange Tests
# ===========================================================================

class TestOutletFlange:
    def test_volume_positive(self):
        flange = create_outlet_flange(24.0)
        assert flange.volume > 0

    def test_has_cutouts(self):
        """Volume should be less than solid outer rectangle."""
        D = 24.0
        outer_w = 0.540 * D
        outer_h = 0.588 * D
        thickness = 0.016 * D
        solid_vol = outer_w * outer_h * thickness
        flange = create_outlet_flange(D)
        assert flange.volume < solid_vol

    def test_bb_matches_outer_dims(self):
        D = 24.0
        flange = create_outlet_flange(D)
        bb = flange.bounding_box()
        x_extent = bb.max.X - bb.min.X
        y_extent = bb.max.Y - bb.min.Y
        assert x_extent == pytest.approx(0.540 * D, rel=0.02)
        assert y_extent == pytest.approx(0.588 * D, rel=0.02)


# ===========================================================================
# Shaft Tests
# ===========================================================================

class TestShaft:
    def test_volume_positive(self, fan_params):
        shaft = create_shaft(fan_params["shaft_d"], fan_params["shaft_len"])
        assert shaft.volume > 0

    def test_length_matches(self, fan_params):
        shaft = create_shaft(fan_params["shaft_d"], fan_params["shaft_len"])
        bb = shaft.bounding_box()
        z_extent = bb.max.Z - bb.min.Z
        assert z_extent == pytest.approx(fan_params["shaft_len"], rel=0.01)

    def test_diameter_matches(self, fan_params):
        shaft = create_shaft(fan_params["shaft_d"], fan_params["shaft_len"])
        bb = shaft.bounding_box()
        x_extent = bb.max.X - bb.min.X
        assert x_extent == pytest.approx(fan_params["shaft_d"], rel=0.05)


# ===========================================================================
# Base Frame Tests (open structural frame)
# ===========================================================================

class TestBaseFrame:
    def test_bottom_at_y_zero(self):
        base = create_base_frame(30.0, 40.0, 10.0)
        bb = base.bounding_box()
        assert bb.min.Y == pytest.approx(0.0, abs=0.01)

    def test_height_matches(self):
        height = 10.0
        base = create_base_frame(30.0, 40.0, height)
        bb = base.bounding_box()
        y_extent = bb.max.Y - bb.min.Y
        assert y_extent == pytest.approx(height, rel=0.01)

    def test_volume_less_than_solid_box(self):
        """Open frame volume should be less than a solid box."""
        length, width, height = 30.0, 40.0, 10.0
        base = create_base_frame(length, width, height)
        solid_vol = length * width * height
        assert base.volume < solid_vol

    def test_volume_positive(self):
        base = create_base_frame(30.0, 40.0, 10.0)
        assert base.volume > 0


# ===========================================================================
# Inlet Cone Tests
# ===========================================================================

class TestInletCone:
    def test_volume_positive(self, fan_params):
        cone = create_inlet_cone(fan_params["hub_d"], fan_params["hub_d"] * 0.4)
        assert cone.volume > 0

    def test_cone_extends_negative_z(self, fan_params):
        cone_len = fan_params["hub_d"] * 0.4
        cone = create_inlet_cone(fan_params["hub_d"], cone_len)
        bb = cone.bounding_box()
        assert bb.min.Z < 0


# ===========================================================================
# Full Assembly Tests (pure geometry, no USD)
# ===========================================================================

class TestFullAssembly:
    def test_all_components_generate(self, fan_params):
        """Every component produces non-None geometry with positive volume."""
        D = fan_params["tip_d"]

        disks = create_impeller_disks(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"])
        assert disks.volume > 0

        blades = create_blades(
            fan_params["tip_d"], fan_params["hub_d"],
            fan_params["outlet_width"], fan_params["num_blades"],
            fan_params["stagger"])
        assert blades.volume > 0

        housing = create_scroll_housing(
            fan_params["tip_r"], fan_params["volute_width"],
            fan_params["wall_t"], fan_params["hub_d"])
        assert housing.volume > 0

        R_cutoff = 0.540 * D
        R_end = R_cutoff * (1.0017 ** 270.0)
        duct = create_outlet_duct(0.42 * D, R_end - R_cutoff, 12.0)
        assert duct.volume > 0

        inlet_fl = create_inlet_flange(D)
        assert inlet_fl.volume > 0

        outlet_fl = create_outlet_flange(D)
        assert outlet_fl.volume > 0

        shaft = create_shaft(fan_params["shaft_d"], fan_params["shaft_len"])
        assert shaft.volume > 0

        base = create_base_frame(
            fan_params["volute_width"] * 1.5,
            fan_params["max_r"] * 2.2,
            fan_params["max_r"] * 0.15)
        assert base.volume > 0

    def test_different_design_point(self):
        """Verify geometry works for a different CFM/pressure design point."""
        acou = _make_acoustic(cfm=5000, inwg=2.0)
        struct = acou.structural
        vol = struct.volute
        aero = vol.aero

        impeller = create_impeller(
            aero.passage.tip_diameter_in,
            aero.passage.hub_diameter_in,
            aero.passage.outlet_width_in,
            aero.blade.num_blades,
            aero.blade.stagger_deg)
        assert impeller.volume > 0

        tip_r = aero.passage.tip_diameter_in / 2.0
        housing = create_scroll_housing(
            tip_r, vol.volute_width_in,
            struct.housing.wall_thickness_in,
            aero.passage.hub_diameter_in)
        assert housing.volume > 0

        base = create_base_frame(
            vol.volute_width_in * 1.5,
            tip_r * 1.55 * 2.2,
            tip_r * 1.55 * 0.15)
        assert base.volume > 0
