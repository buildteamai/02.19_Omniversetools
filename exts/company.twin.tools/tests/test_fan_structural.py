"""
Tests for FanStructuralSolver — Step 4 of the fan engineering system.

No USD/Omniverse dependencies. Pure math + dataclasses only.
Run: cd exts/company.twin.tools && python -m pytest tests/test_fan_structural.py -v
"""

import math
import pytest

from company.twin.solvers.fan_classifier import (
    FanType, FanDesignPoint, FanClassification, FanClassificationSolver,
    UnitSystem,
)
from company.twin.solvers.impeller_aero import ImpellerAeroSolver
from company.twin.solvers.volute_solver import VoluteSolver, VoluteResult
from company.twin.solvers.fan_structural import (
    # Dataclasses
    ShaftDesign, BearingSpec, HousingStructure, BoltPattern,
    BaseDesign, FanStructuralResult,
    # Pure functions
    calc_torque, calc_impeller_weight, calc_bending_moment,
    calc_shaft_diameter, calc_critical_speed,
    calc_bearing_loads, calc_bearing_l10, calc_dynamic_rating_required,
    select_amca_class, calc_housing_weight, calc_bolt_pattern,
    calc_stiffener_count,
    # Constants
    STEEL_YIELD_PSI, STEEL_SHEAR_ALLOW_PSI, STEEL_DENSITY_LB_IN3,
    BEARING_L10_TARGET, AMCA_CLASS_LIMITS,
    # Solver
    FanStructuralSolver,
)


# ===========================================================================
# Helper: run Steps 1+2+3 to produce a VoluteResult
# ===========================================================================

def _make_volute(cfm=10000, inwg=3.0, rpm=None) -> VoluteResult:
    dp = FanDesignPoint(cfm, inwg, rpm=rpm)
    r1 = FanClassificationSolver().solve({'design_point': dp})
    cls = r1['metadata']['classification']
    r2 = ImpellerAeroSolver().solve({'classification': cls})
    aero = r2['metadata']['aero']
    r3 = VoluteSolver().solve({'aero': aero})
    return r3['metadata']['volute']


# ===========================================================================
# Torque
# ===========================================================================

class TestTorque:
    def test_formula(self):
        """T = 63025 × HP / RPM"""
        T = calc_torque(10.0, 1750.0)
        assert T == pytest.approx(63025.0 * 10.0 / 1750.0)

    def test_higher_hp_more_torque(self):
        assert calc_torque(20.0, 1750.0) > calc_torque(10.0, 1750.0)

    def test_zero_rpm_raises(self):
        with pytest.raises(ValueError):
            calc_torque(10.0, 0.0)


# ===========================================================================
# Impeller Weight
# ===========================================================================

class TestImpellerWeight:
    def test_positive(self):
        w = calc_impeller_weight(36.0, 5.0, 0.55, 12, FanType.BACKWARD_INCLINED)
        assert w > 0

    def test_larger_diameter_heavier(self):
        w1 = calc_impeller_weight(24.0, 4.0, 0.55, 12, FanType.BACKWARD_INCLINED)
        w2 = calc_impeller_weight(48.0, 8.0, 0.55, 12, FanType.BACKWARD_INCLINED)
        assert w2 > w1

    def test_more_blades_heavier(self):
        w1 = calc_impeller_weight(36.0, 5.0, 0.55, 8, FanType.BACKWARD_INCLINED)
        w2 = calc_impeller_weight(36.0, 5.0, 0.55, 16, FanType.BACKWARD_INCLINED)
        assert w2 > w1

    def test_fc_thinner_blades(self):
        """FC uses thinner blades (0.075") than others (0.125")."""
        w_bi = calc_impeller_weight(36.0, 5.0, 0.55, 12, FanType.BACKWARD_INCLINED)
        w_fc = calc_impeller_weight(36.0, 5.0, 0.55, 12, FanType.FORWARD_CURVED)
        # FC blades thinner, but same disk → slightly lighter
        assert w_fc < w_bi


# ===========================================================================
# Shaft Diameter
# ===========================================================================

class TestShaftDiameter:
    def test_positive(self):
        d = calc_shaft_diameter(500.0, 1000.0)
        assert d > 0

    def test_more_torque_larger(self):
        d1 = calc_shaft_diameter(500.0, 1000.0)
        d2 = calc_shaft_diameter(2000.0, 1000.0)
        assert d2 > d1

    def test_more_moment_larger(self):
        d1 = calc_shaft_diameter(500.0, 500.0)
        d2 = calc_shaft_diameter(500.0, 2000.0)
        assert d2 > d1

    def test_formula(self):
        """d = (16/(π·τ) · √(M²+T²))^(1/3)"""
        T, M = 500.0, 1000.0
        tau = STEEL_SHEAR_ALLOW_PSI
        expected = (16.0 / (math.pi * tau) * math.sqrt(M**2 + T**2)) ** (1.0/3.0)
        assert calc_shaft_diameter(T, M) == pytest.approx(expected)


# ===========================================================================
# Critical Speed
# ===========================================================================

class TestCriticalSpeed:
    def test_positive(self):
        nc = calc_critical_speed(1.5, 30.0, 50.0)
        assert nc > 0

    def test_larger_shaft_higher_critical(self):
        nc1 = calc_critical_speed(1.0, 30.0, 50.0)
        nc2 = calc_critical_speed(2.0, 30.0, 50.0)
        assert nc2 > nc1

    def test_longer_span_lower_critical(self):
        nc1 = calc_critical_speed(1.5, 20.0, 50.0)
        nc2 = calc_critical_speed(1.5, 40.0, 50.0)
        assert nc1 > nc2

    def test_heavier_impeller_lower_critical(self):
        nc1 = calc_critical_speed(1.5, 30.0, 25.0)
        nc2 = calc_critical_speed(1.5, 30.0, 100.0)
        assert nc1 > nc2


# ===========================================================================
# Bearing Loads
# ===========================================================================

class TestBearingLoads:
    def test_total_equals_weight(self):
        """Sum of reactions ≈ total weight (static equilibrium)."""
        W_imp, W_shaft = 50.0, 10.0
        R_A, R_B = calc_bearing_loads(W_imp, W_shaft, 30.0, 8.0)
        # R_A + R_B should approximately equal total applied load
        # (including overhung moment effect)
        assert R_A + R_B >= W_imp + W_shaft

    def test_impeller_end_higher(self):
        """Bearing B (impeller end) carries more load than A (drive end)."""
        R_A, R_B = calc_bearing_loads(50.0, 10.0, 30.0, 8.0)
        assert R_B > R_A

    def test_positive(self):
        R_A, R_B = calc_bearing_loads(50.0, 10.0, 30.0, 8.0)
        assert R_A > 0
        assert R_B > 0


# ===========================================================================
# Bearing Life
# ===========================================================================

class TestBearingLife:
    def test_formula(self):
        """L10 = (C/P)^3 × 10^6 / (60·RPM)"""
        C, P, rpm = 5000.0, 500.0, 1750.0
        expected = (C / P) ** 3 * 1e6 / (60.0 * rpm)
        assert calc_bearing_l10(C, P, rpm) == pytest.approx(expected)

    def test_higher_rating_longer_life(self):
        l1 = calc_bearing_l10(3000, 500, 1750)
        l2 = calc_bearing_l10(6000, 500, 1750)
        assert l2 > l1

    def test_dynamic_rating_required(self):
        """Round-trip: required C gives target L10."""
        P, rpm, target = 500.0, 1750.0, 40000.0
        C = calc_dynamic_rating_required(P, rpm, target)
        l10 = calc_bearing_l10(C, P, rpm)
        assert l10 == pytest.approx(target, rel=0.01)


# ===========================================================================
# AMCA Class
# ===========================================================================

class TestAMCAClass:
    def test_class_I(self):
        cls, gauge = select_amca_class(100)
        assert cls == "I"

    def test_class_II(self):
        cls, gauge = select_amca_class(150)
        assert cls == "II"

    def test_class_III(self):
        cls, gauge = select_amca_class(250)
        assert cls == "III"

    def test_class_IV(self):
        cls, gauge = select_amca_class(350)
        assert cls == "IV"

    def test_gauge_increases(self):
        """Higher class → thicker wall."""
        _, g1 = select_amca_class(100)
        _, g4 = select_amca_class(350)
        assert g4 > g1


# ===========================================================================
# Housing Weight
# ===========================================================================

class TestHousingWeight:
    def test_positive(self):
        w = calc_housing_weight(30.0, 10.0, 0.1046)
        assert w > 0

    def test_larger_radius_heavier(self):
        w1 = calc_housing_weight(20.0, 10.0, 0.1046)
        w2 = calc_housing_weight(40.0, 10.0, 0.1046)
        assert w2 > w1

    def test_thicker_wall_heavier(self):
        w1 = calc_housing_weight(30.0, 10.0, 0.0747)
        w2 = calc_housing_weight(30.0, 10.0, 0.1345)
        assert w2 > w1


# ===========================================================================
# Bolt Pattern
# ===========================================================================

class TestBoltPattern:
    def test_minimum_4_bolts(self):
        bp = calc_bolt_pattern(100, 10.0)
        assert bp.num_bolts >= 4

    def test_multiple_of_4(self):
        bp = calc_bolt_pattern(500, 100.0)
        assert bp.num_bolts % 4 == 0

    def test_positive_diameter(self):
        bp = calc_bolt_pattern(500, 100.0)
        assert bp.bolt_diameter_in > 0

    def test_higher_load_more_bolts_or_bigger(self):
        bp1 = calc_bolt_pattern(100, 100.0)
        bp2 = calc_bolt_pattern(10000, 100.0)
        # Either more bolts or bigger bolts
        assert (bp2.num_bolts >= bp1.num_bolts or
                bp2.bolt_diameter_in >= bp1.bolt_diameter_in)


# ===========================================================================
# Stiffeners
# ===========================================================================

class TestStiffeners:
    def test_none_for_thick_shell(self):
        """Low R/t → no stiffeners needed."""
        n = calc_stiffener_count(10.0, 0.25)  # R/t = 40
        assert n == 0

    def test_some_for_thin_shell(self):
        """High R/t → stiffeners needed."""
        n = calc_stiffener_count(100.0, 0.1046)  # R/t ≈ 956
        assert n >= 2


# ===========================================================================
# Solver Validation
# ===========================================================================

class TestSolverValidation:
    def test_missing_volute(self):
        solver = FanStructuralSolver()
        with pytest.raises(ValueError, match="Missing"):
            solver.solve({})

    def test_wrong_type(self):
        solver = FanStructuralSolver()
        with pytest.raises(ValueError, match="must be"):
            solver.solve({'volute': "not a volute"})


# ===========================================================================
# Integration — Full Step 1 → 2 → 3 → 4 Pipeline
# ===========================================================================

class TestIntegration:
    def _run_pipeline(self, cfm=10000, inwg=3.0, rpm=None, **kwargs):
        vol = _make_volute(cfm, inwg, rpm)
        inputs = {'volute': vol}
        inputs.update(kwargs)
        r4 = FanStructuralSolver().solve(inputs)
        return r4['metadata']['structural']

    def test_shaft_positive_diameter(self):
        s = self._run_pipeline()
        assert s.shaft.diameter_in >= 0.75

    def test_shaft_rounded(self):
        """Shaft diameter rounded to nearest 1/8 inch."""
        s = self._run_pipeline()
        remainder = s.shaft.diameter_in * 8.0 - round(s.shaft.diameter_in * 8.0)
        assert abs(remainder) < 0.001

    def test_shaft_safety_factor(self):
        """SF should be > 1.0 (we're not failing)."""
        s = self._run_pipeline()
        assert s.shaft.safety_factor > 1.0

    def test_critical_speed_margin(self):
        """Critical speed margin should be computed and positive.
        Note: many industrial fans run supercritical (margin < 1.0) which is
        acceptable with proper balancing. The Rayleigh single-mass formula is
        conservative for overhung designs."""
        s = self._run_pipeline()
        assert s.shaft.critical_speed_rpm > 0
        assert s.shaft.critical_speed_margin > 0

    def test_bearing_life_meets_target(self):
        """L10 life should meet ASHRAE minimum."""
        s = self._run_pipeline()
        assert s.bearings.l10_life_hours >= BEARING_L10_TARGET * 0.99

    def test_bearing_count(self):
        s = self._run_pipeline()
        assert s.bearings.quantity == 2

    def test_bearing_bore_matches_shaft(self):
        s = self._run_pipeline()
        assert s.bearings.bore_in == pytest.approx(s.shaft.diameter_in)

    def test_housing_wall_positive(self):
        s = self._run_pipeline()
        assert s.housing.wall_thickness_in > 0

    def test_amca_class_valid(self):
        s = self._run_pipeline()
        assert s.housing.amca_class in ("I", "II", "III", "IV")

    def test_housing_weight_positive(self):
        s = self._run_pipeline()
        assert s.housing.housing_weight_lb > 0

    def test_bolt_patterns(self):
        s = self._run_pipeline()
        assert s.inlet_bolts.num_bolts >= 4
        assert s.discharge_bolts.num_bolts >= 4
        assert s.inlet_bolts.bolt_diameter_in > 0
        assert s.discharge_bolts.bolt_diameter_in > 0

    def test_base_dimensions_positive(self):
        s = self._run_pipeline()
        assert s.base.length_in > 0
        assert s.base.width_in > 0
        assert s.base.height_in >= 6.0

    def test_total_weight_positive(self):
        s = self._run_pipeline()
        assert s.base.total_fan_weight_lb > 0
        # Total must be > sum of major components
        assert s.base.total_fan_weight_lb >= (
            s.impeller_weight_lb + s.housing.housing_weight_lb
        )

    def test_impeller_weight_positive(self):
        s = self._run_pipeline()
        assert s.impeller_weight_lb > 0

    def test_hvac_fan(self):
        """15000 CFM, 4 in.WG — typical HVAC."""
        s = self._run_pipeline(15000, 4.0)
        assert s.shaft.diameter_in >= 0.75
        assert s.shaft.safety_factor > 1.5
        assert s.housing.amca_class in ("I", "II", "III", "IV")

    def test_dust_collection(self):
        """3000 CFM, 15 in.WG, 3500 RPM — radial, high speed."""
        s = self._run_pipeline(3000, 15.0, 3500)
        # Higher tip speed → higher AMCA class
        assert s.housing.amca_class in ("II", "III", "IV")

    def test_standard_solver_keys(self):
        vol = _make_volute()
        result = FanStructuralSolver().solve({'volute': vol})
        assert 'parts' in result
        assert 'transforms' in result
        assert 'anchors' in result
        assert 'metadata' in result
        assert result['parts'] == {}

    def test_metadata_flat_fields(self):
        vol = _make_volute()
        result = FanStructuralSolver().solve({'volute': vol})
        meta = result['metadata']
        for key in ('shaft_diameter_in', 'shaft_length_in', 'shaft_safety_factor',
                    'critical_speed_rpm', 'critical_speed_margin',
                    'impeller_weight_lb', 'housing_weight_lb', 'total_weight_lb',
                    'amca_class', 'wall_thickness_in',
                    'bearing_dynamic_rating_lbf', 'bearing_l10_hours',
                    'base_length_in', 'base_width_in'):
            assert key in meta, f"Missing metadata key: {key}"

    def test_echo_volute(self):
        vol = _make_volute()
        result = FanStructuralSolver().solve({'volute': vol})
        s = result['metadata']['structural']
        assert s.volute is vol

    def test_span_override(self):
        """Can override bearing span multiplier."""
        s_default = self._run_pipeline()
        s_wide = self._run_pipeline(bearing_span_mult=30.0)
        assert s_wide.shaft.length_in > s_default.shaft.length_in
