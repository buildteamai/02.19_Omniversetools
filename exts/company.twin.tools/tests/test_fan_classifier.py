"""
Tests for FanClassificationSolver — 25+ pytest cases.

No USD/Omniverse dependencies. Pure math + dataclasses only.
Run: cd exts/company.twin.tools && python -m pytest tests/test_fan_classifier.py -v
"""

import math
import pytest

from company.twin.solvers.fan_classifier import (
    # Enums
    FanType, BladeAngleClass, OperatingRegion, UnitSystem,
    # Dataclasses
    FanDesignPoint, FanClassification, EfficiencyEstimate,
    # Pure functions
    calc_specific_speed, classify_fan_type, calc_specific_diameter,
    calc_impeller_diameter, estimate_efficiency, calc_shaft_power,
    calc_rpm_range, calc_tip_speed, assess_operating_region,
    # Constants
    INWG_TO_PA, INWG_TO_PSF, M3S_TO_CFM, AIR_HP_CONST, HP_TO_KW,
    # Solver
    FanClassificationSolver,
)


# ===========================================================================
# Specific Speed (Ns) Calculation
# ===========================================================================

class TestSpecificSpeed:
    def test_textbook_case(self):
        """10000 CFM, 3 in.WG, 1750 RPM → Ns ≈ 2879 (ft³/s, lbf/ft² convention)"""
        ns = calc_specific_speed(1750, 10000, 3.0)
        assert 2700 < ns < 3100, f"Expected ~2879, got {ns:.0f}"

    def test_known_value(self):
        """Verify the formula: Ns = RPM × √Q_cfs / ΔP_psf^(3/4)"""
        rpm, cfm, dp_inwg = 1000.0, 10000.0, 1.0
        q_cfs = cfm / 60.0
        dp_psf = dp_inwg * INWG_TO_PSF
        expected = rpm * math.sqrt(q_cfs) / (dp_psf ** 0.75)
        assert calc_specific_speed(rpm, cfm, dp_inwg) == pytest.approx(expected)

    def test_higher_rpm_gives_higher_ns(self):
        ns_low = calc_specific_speed(1000, 5000, 2.0)
        ns_high = calc_specific_speed(2000, 5000, 2.0)
        assert ns_high > ns_low

    def test_higher_pressure_gives_lower_ns(self):
        ns_low_p = calc_specific_speed(1750, 10000, 6.0)
        ns_high_p = calc_specific_speed(1750, 10000, 1.0)
        assert ns_high_p > ns_low_p

    def test_zero_inputs_raise(self):
        with pytest.raises(ValueError):
            calc_specific_speed(0, 10000, 3.0)
        with pytest.raises(ValueError):
            calc_specific_speed(1750, 0, 3.0)
        with pytest.raises(ValueError):
            calc_specific_speed(1750, 10000, 0)

    def test_negative_inputs_raise(self):
        with pytest.raises(ValueError):
            calc_specific_speed(-1750, 10000, 3.0)


# ===========================================================================
# Fan Type Classification
# ===========================================================================

class TestClassification:
    def test_radial_range(self):
        ft, bc, _ = classify_fan_type(1000)
        assert ft == FanType.RADIAL_BLADE
        assert bc == BladeAngleClass.RADIAL

    def test_backward_inclined_range(self):
        ft, bc, _ = classify_fan_type(2500)
        assert ft == FanType.BACKWARD_INCLINED
        assert bc == BladeAngleClass.BACKWARD

    def test_backward_curved_range(self):
        ft, bc, _ = classify_fan_type(3800)
        assert ft == FanType.BACKWARD_CURVED
        assert bc == BladeAngleClass.BACKWARD

    def test_forward_curved_range(self):
        ft, bc, _ = classify_fan_type(6000)
        assert ft == FanType.FORWARD_CURVED
        assert bc == BladeAngleClass.FORWARD

    def test_boundary_2000(self):
        """Ns=2000 is the start of backward inclined."""
        ft, _, _ = classify_fan_type(2000)
        assert ft == FanType.BACKWARD_INCLINED

    def test_beyond_8000(self):
        ft, _, _ = classify_fan_type(9000)
        assert ft == FanType.FORWARD_CURVED

    def test_peak_efficiency_values(self):
        _, _, eta = classify_fan_type(1000)
        assert eta == pytest.approx(0.55)
        _, _, eta = classify_fan_type(2500)
        assert eta == pytest.approx(0.82)


# ===========================================================================
# Cordier Specific Diameter
# ===========================================================================

class TestCordier:
    def test_ds_decreases_with_ns(self):
        ds_low = calc_specific_diameter(1000)
        ds_high = calc_specific_diameter(5000)
        assert ds_low > ds_high

    def test_ns_2500(self):
        """Ns=2500 → Ds in reasonable Cordier band"""
        ds = calc_specific_diameter(2500)
        # 10^1.137 / 2500^0.424 ≈ 13.71 / 36.4 ≈ 0.377
        # Cordier Ds decreases rapidly at high Ns
        assert 0.2 < ds < 1.5, f"Ds={ds:.3f} outside expected Cordier band"

    def test_zero_ns_raises(self):
        with pytest.raises(ValueError):
            calc_specific_diameter(0)


# ===========================================================================
# Impeller Diameter
# ===========================================================================

class TestImpellerDiameter:
    def test_reasonable_diameter(self):
        """10000 CFM, 3 in.WG → 20–60" impeller"""
        ds = calc_specific_diameter(2500)
        d = calc_impeller_diameter(ds, 10000, 3.0)
        assert 20 < d < 60, f"Diameter {d:.1f}\" outside expected range"

    def test_larger_flow_gives_larger_diameter(self):
        ds = calc_specific_diameter(2500)
        d_small = calc_impeller_diameter(ds, 5000, 3.0)
        d_large = calc_impeller_diameter(ds, 20000, 3.0)
        assert d_large > d_small


# ===========================================================================
# Shaft Power
# ===========================================================================

class TestShaftPower:
    def test_arithmetic(self):
        """10000 × 3 / (6356 × 0.80) = 5.899 HP"""
        hp, kw = calc_shaft_power(10000, 3.0, 0.80)
        expected_hp = 10000 * 3.0 / (6356 * 0.80)
        assert hp == pytest.approx(expected_hp, rel=1e-6)
        assert kw == pytest.approx(expected_hp * HP_TO_KW, rel=1e-6)

    def test_zero_efficiency_raises(self):
        with pytest.raises(ValueError):
            calc_shaft_power(10000, 3.0, 0.0)

    def test_higher_pressure_needs_more_power(self):
        hp_low, _ = calc_shaft_power(10000, 2.0, 0.80)
        hp_high, _ = calc_shaft_power(10000, 6.0, 0.80)
        assert hp_high > hp_low


# ===========================================================================
# Efficiency Estimate
# ===========================================================================

class TestEfficiency:
    def test_bi_higher_than_fc(self):
        eff_bi = estimate_efficiency(FanType.BACKWARD_INCLINED, 2600)
        eff_fc = estimate_efficiency(FanType.FORWARD_CURVED, 6000)
        assert eff_bi.total > eff_fc.total

    def test_within_published_ranges(self):
        eff = estimate_efficiency(FanType.BACKWARD_INCLINED, 2600)
        assert 0.50 < eff.total <= 0.82

    def test_peak_at_center(self):
        """At center of range, derating should be near 1.0."""
        eff = estimate_efficiency(FanType.BACKWARD_INCLINED, 2600)
        assert eff.derating_factor > 0.9

    def test_derating_at_edges(self):
        """At edge of range, efficiency drops."""
        eff_center = estimate_efficiency(FanType.BACKWARD_INCLINED, 2600)
        eff_edge = estimate_efficiency(FanType.BACKWARD_INCLINED, 2050)
        assert eff_edge.total < eff_center.total


# ===========================================================================
# Operating Region
# ===========================================================================

class TestOperatingRegion:
    def test_stable(self):
        region = assess_operating_region(2600, FanType.BACKWARD_INCLINED)
        assert region == OperatingRegion.STABLE

    def test_near_stall(self):
        """Just outside stable range but within near-stall margin."""
        region = assess_operating_region(2100, FanType.BACKWARD_INCLINED)
        assert region in (OperatingRegion.NEAR_STALL, OperatingRegion.UNSTABLE)

    def test_unstable(self):
        """Well within type range but outside stable sub-range."""
        region = assess_operating_region(3100, FanType.BACKWARD_INCLINED)
        assert region in (OperatingRegion.UNSTABLE, OperatingRegion.NEAR_STALL)

    def test_beyond_range(self):
        region = assess_operating_region(500, FanType.FORWARD_CURVED)
        assert region == OperatingRegion.BEYOND_RANGE


# ===========================================================================
# Tip Speed
# ===========================================================================

class TestTipSpeed:
    def test_formula(self):
        """V = π × D_ft × RPM / 60"""
        d_in, rpm = 36.0, 1750.0
        expected = math.pi * (36.0 / 12.0) * 1750.0 / 60.0
        assert calc_tip_speed(d_in, rpm) == pytest.approx(expected)


# ===========================================================================
# RPM Range
# ===========================================================================

class TestRpmRange:
    def test_range_is_symmetric_around_center(self):
        rpm_lo, rpm_hi = calc_rpm_range(10000, 3.0, 2600)
        center = (rpm_lo + rpm_hi) / 2.0
        # The range is ±20%, so center × 0.8 and center × 1.2
        assert rpm_lo == pytest.approx(center * 0.8 / 1.0, rel=0.01)

    def test_positive_values(self):
        rpm_lo, rpm_hi = calc_rpm_range(10000, 3.0, 2600)
        assert rpm_lo > 0
        assert rpm_hi > rpm_lo


# ===========================================================================
# Unit Conversions
# ===========================================================================

class TestUnitConversions:
    def test_si_to_us_roundtrip(self):
        dp = FanDesignPoint(4.72, 746.52, units=UnitSystem.SI)
        cfm, inwg = dp.to_us()
        m3s, pa = dp.to_si()
        assert cfm == pytest.approx(4.72 * M3S_TO_CFM, rel=1e-4)
        assert inwg == pytest.approx(746.52 / INWG_TO_PA, rel=1e-4)
        assert m3s == pytest.approx(4.72)
        assert pa == pytest.approx(746.52)

    def test_us_to_si_roundtrip(self):
        dp = FanDesignPoint(10000, 3.0, units=UnitSystem.US)
        cfm, inwg = dp.to_us()
        m3s, pa = dp.to_si()
        assert cfm == pytest.approx(10000)
        assert inwg == pytest.approx(3.0)
        assert m3s == pytest.approx(10000 / M3S_TO_CFM, rel=1e-4)
        assert pa == pytest.approx(3.0 * INWG_TO_PA, rel=1e-4)


# ===========================================================================
# Solver Validation
# ===========================================================================

class TestSolverValidation:
    def test_missing_design_point(self):
        solver = FanClassificationSolver()
        with pytest.raises(ValueError, match="Missing"):
            solver.solve({})

    def test_cfm_too_low(self):
        solver = FanClassificationSolver()
        dp = FanDesignPoint(10, 3.0)
        with pytest.raises(ValueError, match="Flow rate"):
            solver.solve({'design_point': dp})

    def test_cfm_too_high(self):
        solver = FanClassificationSolver()
        dp = FanDesignPoint(600_000, 3.0)
        with pytest.raises(ValueError, match="Flow rate"):
            solver.solve({'design_point': dp})

    def test_pressure_too_low(self):
        solver = FanClassificationSolver()
        dp = FanDesignPoint(10000, 0.01)
        with pytest.raises(ValueError, match="Pressure"):
            solver.solve({'design_point': dp})

    def test_rpm_out_of_range(self):
        solver = FanClassificationSolver()
        dp = FanDesignPoint(10000, 3.0, rpm=50)
        with pytest.raises(ValueError, match="RPM"):
            solver.solve({'design_point': dp})


# ===========================================================================
# Integration — Full Solver Pipeline
# ===========================================================================

class TestIntegration:
    def test_hvac_fan(self):
        """HVAC: 15000 CFM, 4 in.WG → backward-inclined."""
        solver = FanClassificationSolver()
        dp = FanDesignPoint(15000, 4.0)
        result = solver.solve({'design_point': dp})

        cls = result['metadata']['classification']
        assert isinstance(cls, FanClassification)
        assert cls.fan_type in (FanType.BACKWARD_INCLINED, FanType.BACKWARD_CURVED)
        assert cls.impeller_diameter_in > 0
        assert cls.shaft_power_hp > 0
        assert cls.efficiency.total > 0.5
        assert result['parts'] == {}

    def test_dust_collection(self):
        """Dust collection: 3000 CFM, 15 in.WG, 3500 RPM → radial."""
        solver = FanClassificationSolver()
        dp = FanDesignPoint(3000, 15.0, rpm=3500)
        result = solver.solve({'design_point': dp})

        cls = result['metadata']['classification']
        assert cls.fan_type == FanType.RADIAL_BLADE
        assert cls.blade_angle_class == BladeAngleClass.RADIAL

    def test_auto_rpm(self):
        """When RPM is not specified, solver picks one automatically."""
        solver = FanClassificationSolver()
        dp = FanDesignPoint(10000, 3.0)
        result = solver.solve({'design_point': dp})

        rpm_used = result['metadata']['rpm_used']
        assert 300 <= rpm_used <= 5000

    def test_si_input(self):
        """SI units should produce the same classification as equivalent US."""
        solver = FanClassificationSolver()
        # 10000 CFM ≈ 4.72 m³/s, 3 in.WG ≈ 746.5 Pa
        dp_si = FanDesignPoint(
            10000 / M3S_TO_CFM,
            3.0 * INWG_TO_PA,
            units=UnitSystem.SI,
        )
        result = solver.solve({'design_point': dp_si})
        cls = result['metadata']['classification']
        assert cls.fan_type in (
            FanType.BACKWARD_INCLINED,
            FanType.BACKWARD_CURVED,
            FanType.RADIAL_BLADE,
        )
        assert cls.impeller_diameter_in > 0

    def test_design_point_echo(self):
        """FanClassification should echo back the original design point."""
        solver = FanClassificationSolver()
        dp = FanDesignPoint(10000, 3.0, rpm=1750)
        result = solver.solve({'design_point': dp})
        cls = result['metadata']['classification']
        assert cls.design_point is dp

    def test_metadata_flat_fields(self):
        """Check that flat metadata keys are present."""
        solver = FanClassificationSolver()
        dp = FanDesignPoint(10000, 3.0)
        result = solver.solve({'design_point': dp})
        meta = result['metadata']
        assert 'specific_speed_ns' in meta
        assert 'fan_type' in meta
        assert 'impeller_diameter_in' in meta
        assert 'shaft_power_hp' in meta
        assert 'efficiency' in meta
        assert 'operating_region' in meta

    def test_standard_solver_keys(self):
        """Result dict has all BaseSolver standard keys."""
        solver = FanClassificationSolver()
        dp = FanDesignPoint(10000, 3.0)
        result = solver.solve({'design_point': dp})
        assert 'parts' in result
        assert 'transforms' in result
        assert 'anchors' in result
        assert 'metadata' in result
