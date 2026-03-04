"""
Tests for VoluteSolver — Step 3 of the fan engineering system.

No USD/Omniverse dependencies. Pure math + dataclasses only.
Run: cd exts/company.twin.tools && python -m pytest tests/test_volute_solver.py -v
"""

import math
import pytest

from company.twin.solvers.fan_classifier import (
    FanType, BladeAngleClass, OperatingRegion, UnitSystem,
    FanDesignPoint, FanClassification, EfficiencyEstimate,
    FanClassificationSolver,
)
from company.twin.solvers.impeller_aero import (
    ImpellerAeroSolver, ImpellerAeroResult,
    VelocityTriangle, BladeGeometry, PassageGeometry,
)
from company.twin.solvers.volute_solver import (
    # Dataclasses
    VoluteStation, VoluteTongue, DischargeGeometry, VoluteResult,
    # Pure functions
    calc_angular_momentum, calc_volute_area_at_theta,
    calc_volute_radius, calc_mean_velocity_at_station,
    calc_tongue_geometry, calc_discharge_geometry,
    estimate_pressure_recovery,
    # Constants
    DEFAULT_NUM_STATIONS, CUTOFF_GAP_RATIO,
    WIDTH_EXPANSION_RATIO, DISCHARGE_AREA_FACTOR,
    # Solver
    VoluteSolver,
)


# ===========================================================================
# Helper: run Steps 1+2 to produce an ImpellerAeroResult
# ===========================================================================

def _make_aero(cfm=10000, inwg=3.0, rpm=None) -> ImpellerAeroResult:
    """Run Step 1 → Step 2 and return the aero result."""
    dp = FanDesignPoint(cfm, inwg, rpm=rpm)
    r1 = FanClassificationSolver().solve({'design_point': dp})
    cls = r1['metadata']['classification']
    r2 = ImpellerAeroSolver().solve({'classification': cls})
    return r2['metadata']['aero']


# ===========================================================================
# Angular Momentum
# ===========================================================================

class TestAngularMomentum:
    def test_formula(self):
        """K = r · Cu"""
        K = calc_angular_momentum(100.0, 1.5)
        assert K == pytest.approx(150.0)

    def test_proportional_to_Cu(self):
        K1 = calc_angular_momentum(50.0, 1.5)
        K2 = calc_angular_momentum(100.0, 1.5)
        assert K2 == pytest.approx(2.0 * K1)


# ===========================================================================
# Volute Area at θ
# ===========================================================================

class TestVoluteArea:
    def test_zero_at_origin(self):
        """At θ=0 (tongue), collected area is zero."""
        a = calc_volute_area_at_theta(0, 10000, 50.0, 1.5)
        assert a == pytest.approx(0.0)

    def test_full_at_360(self):
        """At θ=360°, all flow is collected: A = Q_cfs / Cu₂."""
        cfm, Cu2, r_ft = 10000, 50.0, 1.5
        a = calc_volute_area_at_theta(360, cfm, Cu2, r_ft)
        expected = (cfm / 60.0) / Cu2
        assert a == pytest.approx(expected)

    def test_linear_growth(self):
        """Area grows linearly with θ."""
        a_90 = calc_volute_area_at_theta(90, 10000, 50.0, 1.5)
        a_180 = calc_volute_area_at_theta(180, 10000, 50.0, 1.5)
        a_360 = calc_volute_area_at_theta(360, 10000, 50.0, 1.5)
        assert a_180 == pytest.approx(2.0 * a_90)
        assert a_360 == pytest.approx(4.0 * a_90)

    def test_zero_Cu_raises(self):
        with pytest.raises(ValueError):
            calc_volute_area_at_theta(180, 10000, 0.0, 1.5)


# ===========================================================================
# Volute Radius
# ===========================================================================

class TestVoluteRadius:
    def test_grows_with_area(self):
        """Larger area → larger radius."""
        r1 = calc_volute_radius(0.5, 0.5, 1.5)
        r2 = calc_volute_radius(1.0, 0.5, 1.5)
        assert r2 > r1

    def test_minimum_is_tip_radius(self):
        """At zero area, R_outer = R_tip."""
        r = calc_volute_radius(0.0, 0.5, 1.5)
        assert r == pytest.approx(1.5)

    def test_formula(self):
        """R = R_tip + A/width"""
        area, width, r_tip = 1.0, 0.5, 1.5
        expected = 1.5 + 1.0 / 0.5
        assert calc_volute_radius(area, width, r_tip) == pytest.approx(expected)

    def test_zero_width_raises(self):
        with pytest.raises(ValueError):
            calc_volute_radius(1.0, 0.0, 1.5)


# ===========================================================================
# Mean Velocity at Station
# ===========================================================================

class TestMeanVelocity:
    def test_zero_theta(self):
        """No collected flow at θ=0 → velocity = 0."""
        v = calc_mean_velocity_at_station(10000, 0, 1.0)
        assert v == pytest.approx(0.0)

    def test_positive(self):
        v = calc_mean_velocity_at_station(10000, 180, 1.0)
        assert v > 0

    def test_zero_area_returns_zero(self):
        v = calc_mean_velocity_at_station(10000, 180, 0.0)
        assert v == pytest.approx(0.0)


# ===========================================================================
# Tongue Geometry
# ===========================================================================

class TestTongueGeometry:
    def test_gap_proportional_to_diameter(self):
        """Gap = CUTOFF_GAP_RATIO × D₂."""
        t = calc_tongue_geometry(36.0, FanType.BACKWARD_INCLINED)
        assert t.gap_in == pytest.approx(36.0 * CUTOFF_GAP_RATIO)

    def test_radius_outside_impeller(self):
        """Tongue radius > impeller tip radius."""
        t = calc_tongue_geometry(36.0, FanType.BACKWARD_INCLINED)
        assert t.radius_in > 36.0 / 2.0

    def test_angle_varies_by_type(self):
        t_bi = calc_tongue_geometry(36.0, FanType.BACKWARD_INCLINED)
        t_fc = calc_tongue_geometry(36.0, FanType.FORWARD_CURVED)
        assert t_bi.angle_deg != t_fc.angle_deg


# ===========================================================================
# Discharge Geometry
# ===========================================================================

class TestDischargeGeometry:
    def test_positive_dimensions(self):
        d = calc_discharge_geometry(2.0, 20.0, 10000, FanType.BACKWARD_INCLINED)
        assert d.width_in > 0
        assert d.height_in > 0
        assert d.area_in2 > 0
        assert d.velocity_fts > 0
        assert d.equivalent_diameter_in > 0

    def test_area_oversized(self):
        """Discharge area > A_360 (oversize factor)."""
        a360 = 2.0  # ft²
        d = calc_discharge_geometry(a360, 20.0, 10000, FanType.BACKWARD_INCLINED)
        factor = DISCHARGE_AREA_FACTOR[FanType.BACKWARD_INCLINED]
        assert d.area_in2 == pytest.approx(a360 * factor * 144.0)

    def test_width_matches_volute(self):
        d = calc_discharge_geometry(2.0, 25.0, 10000, FanType.BACKWARD_INCLINED)
        assert d.width_in == pytest.approx(25.0)


# ===========================================================================
# Pressure Recovery
# ===========================================================================

class TestPressureRecovery:
    def test_positive_deceleration(self):
        """If discharge slower than C₂, Cp is positive."""
        Cp = estimate_pressure_recovery(100.0, 60.0)
        assert 0 < Cp < 1

    def test_no_deceleration(self):
        """If C_discharge == C₂, Cp = 0."""
        assert estimate_pressure_recovery(100.0, 100.0) == pytest.approx(0.0)

    def test_acceleration_clamped(self):
        """If discharge faster than C₂, Cp is clamped to 0."""
        assert estimate_pressure_recovery(100.0, 120.0) == pytest.approx(0.0)

    def test_zero_C2(self):
        assert estimate_pressure_recovery(0.0, 50.0) == pytest.approx(0.0)


# ===========================================================================
# Solver Validation
# ===========================================================================

class TestSolverValidation:
    def test_missing_aero(self):
        solver = VoluteSolver()
        with pytest.raises(ValueError, match="Missing"):
            solver.solve({})

    def test_wrong_type(self):
        solver = VoluteSolver()
        with pytest.raises(ValueError, match="must be"):
            solver.solve({'aero': "not an aero result"})


# ===========================================================================
# Integration — Full Step 1 → 2 → 3 Pipeline
# ===========================================================================

class TestIntegration:
    def _run_pipeline(self, cfm=10000, inwg=3.0, rpm=None, **kwargs):
        """Run Steps 1→2→3 and return the volute result."""
        aero = _make_aero(cfm, inwg, rpm)
        inputs = {'aero': aero}
        inputs.update(kwargs)
        r3 = VoluteSolver().solve(inputs)
        return r3['metadata']['volute']

    def test_stations_count(self):
        """Default 8 stations."""
        vol = self._run_pipeline()
        assert len(vol.stations) == DEFAULT_NUM_STATIONS

    def test_stations_custom_count(self):
        vol = self._run_pipeline(num_stations=12)
        assert len(vol.stations) == 12

    def test_stations_monotonic_radius(self):
        """Volute radius grows monotonically from θ=0 to θ=360."""
        vol = self._run_pipeline()
        radii = [s.radius_in for s in vol.stations]
        for i in range(1, len(radii)):
            assert radii[i] >= radii[i - 1], (
                f"Radius not monotonic at station {i}: "
                f"{radii[i-1]:.2f} → {radii[i]:.2f}"
            )

    def test_stations_monotonic_area(self):
        """Cross-sectional area grows monotonically."""
        vol = self._run_pipeline()
        areas = [s.area_in2 for s in vol.stations]
        for i in range(1, len(areas)):
            assert areas[i] >= areas[i - 1]

    def test_stations_cover_360(self):
        """Last station is at 360°."""
        vol = self._run_pipeline()
        assert vol.stations[-1].theta_deg == pytest.approx(360.0)

    def test_max_radius_at_360(self):
        """Max radius equals the last station radius."""
        vol = self._run_pipeline()
        assert vol.max_radius_in == pytest.approx(vol.stations[-1].radius_in)

    def test_max_radius_exceeds_impeller(self):
        """Volute must be larger than the impeller."""
        vol = self._run_pipeline()
        assert vol.max_radius_in > vol.impeller_tip_radius_in

    def test_tongue_inside_first_station(self):
        """Tongue radius < first station outer radius."""
        vol = self._run_pipeline()
        assert vol.tongue.radius_in < vol.stations[0].radius_in

    def test_tongue_outside_impeller(self):
        """Tongue must clear the impeller."""
        vol = self._run_pipeline()
        assert vol.tongue.radius_in > vol.impeller_tip_radius_in

    def test_discharge_positive(self):
        vol = self._run_pipeline()
        assert vol.discharge.width_in > 0
        assert vol.discharge.height_in > 0
        assert vol.discharge.area_in2 > 0
        assert vol.discharge.velocity_fts > 0

    def test_discharge_width_matches_volute(self):
        vol = self._run_pipeline()
        assert vol.discharge.width_in == pytest.approx(vol.volute_width_in)

    def test_angular_momentum_positive(self):
        vol = self._run_pipeline()
        assert vol.angular_momentum > 0

    def test_pressure_recovery_reasonable(self):
        """Cp should be non-negative."""
        vol = self._run_pipeline()
        assert vol.pressure_recovery_coeff >= 0

    def test_hvac_backward_inclined(self):
        """15000 CFM, 4 in.WG → reasonable volute dimensions."""
        vol = self._run_pipeline(15000, 4.0)
        # Max radius should be bigger than impeller; BI fans with low Cu₂
        # produce large volutes (ratio up to ~5–6×) which is physically correct
        assert vol.max_radius_in > vol.impeller_tip_radius_in
        assert vol.max_radius_in < vol.impeller_tip_radius_in * 8
        assert vol.volute_width_in > 0
        assert len(vol.stations) == DEFAULT_NUM_STATIONS

    def test_dust_collection_radial(self):
        """3000 CFM, 15 in.WG, 3500 RPM → tighter volute."""
        vol = self._run_pipeline(3000, 15.0, 3500)
        # Radial fans have high Cu₂, so volute is smaller relative to impeller
        assert vol.max_radius_in > vol.impeller_tip_radius_in

    def test_width_expansion_override(self):
        """Can override width expansion ratio."""
        vol_default = self._run_pipeline()
        vol_wide = self._run_pipeline(width_expansion=2.0)
        assert vol_wide.volute_width_in > vol_default.volute_width_in

    def test_standard_solver_keys(self):
        """Result dict has all BaseSolver standard keys."""
        aero = _make_aero()
        result = VoluteSolver().solve({'aero': aero})
        assert 'parts' in result
        assert 'transforms' in result
        assert 'anchors' in result
        assert 'metadata' in result
        assert result['parts'] == {}

    def test_metadata_flat_fields(self):
        """Check flat metadata keys are present."""
        aero = _make_aero()
        result = VoluteSolver().solve({'aero': aero})
        meta = result['metadata']
        for key in ('max_radius_in', 'min_radius_in', 'volute_width_in',
                    'discharge_width_in', 'discharge_height_in',
                    'discharge_area_in2', 'discharge_velocity_fts',
                    'tongue_radius_in', 'tongue_gap_in',
                    'angular_momentum', 'pressure_recovery_coeff',
                    'num_stations'):
            assert key in meta, f"Missing metadata key: {key}"

    def test_echo_aero(self):
        """VoluteResult echoes the input aero result."""
        aero = _make_aero()
        result = VoluteSolver().solve({'aero': aero})
        vol = result['metadata']['volute']
        assert vol.aero is aero

    def test_velocity_decreases_with_area(self):
        """As area grows, velocity at later stations should be roughly constant
        (since flow and area both grow linearly), not increasing wildly."""
        vol = self._run_pipeline()
        velocities = [s.velocity_fts for s in vol.stations]
        # All stations should have similar velocity (constant Cu₂ design)
        mean_v = sum(velocities) / len(velocities)
        for v in velocities:
            assert abs(v - mean_v) / mean_v < 0.05, (
                f"Velocity {v:.1f} deviates >5% from mean {mean_v:.1f}"
            )
