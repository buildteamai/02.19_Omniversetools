"""
Tests for ImpellerAeroSolver — Step 2 of the fan engineering system.

No USD/Omniverse dependencies. Pure math + dataclasses only.
Run: cd exts/company.twin.tools && python -m pytest tests/test_impeller_aero.py -v
"""

import math
import pytest

from company.twin.solvers.fan_classifier import (
    FanType, BladeAngleClass, OperatingRegion, UnitSystem,
    FanDesignPoint, FanClassification, EfficiencyEstimate,
    FanClassificationSolver,
)
from company.twin.solvers.impeller_aero import (
    # Dataclasses
    VelocityTriangle, BladeGeometry, PassageGeometry, ImpellerAeroResult,
    # Pure functions
    calc_blade_speed, calc_meridional_velocity,
    calc_outlet_area, calc_inlet_area,
    calc_whirl_velocity, calc_slip_factor,
    calc_blade_angle_from_triangle, calc_relative_velocity,
    calc_absolute_velocity, calc_absolute_angle,
    calc_de_haller, calc_outlet_width, calc_blade_chord,
    estimate_solidity, estimate_outlet_width_ratio,
    # Constants
    RHO_AIR_STD, G_FT,
    HUB_RATIO_DEFAULT, BLADE_COUNT_DEFAULT, BETA2_TARGETS,
    # Solver
    ImpellerAeroSolver,
)


# ===========================================================================
# Helper: create a FanClassification for testing
# ===========================================================================

def _make_classification(
    cfm=10000, inwg=3.0, rpm=1750,
    fan_type=FanType.BACKWARD_INCLINED,
    diameter_in=36.0,
    eta=0.80,
) -> FanClassification:
    """Create a synthetic FanClassification for unit testing."""
    dp = FanDesignPoint(cfm, inwg, UnitSystem.US, rpm=rpm)
    return FanClassification(
        fan_type=fan_type,
        blade_angle_class=BladeAngleClass.BACKWARD,
        operating_region=OperatingRegion.STABLE,
        specific_speed_ns=2800.0,
        specific_diameter_ds=0.5,
        impeller_diameter_in=diameter_in,
        recommended_rpm_range=(rpm * 0.8, rpm * 1.2),
        tip_speed_fts=math.pi * (diameter_in / 12.0) * rpm / 60.0,
        efficiency=EfficiencyEstimate(total=eta, peak_for_type=0.82, derating_factor=0.975),
        shaft_power_hp=cfm * inwg / (6356 * eta),
        shaft_power_kw=cfm * inwg / (6356 * eta) * 0.7457,
        design_point=dp,
    )


# ===========================================================================
# Blade Speed
# ===========================================================================

class TestBladeSpeed:
    def test_formula(self):
        """U = π·D_ft·RPM/60"""
        d_in, rpm = 36.0, 1750.0
        expected = math.pi * 3.0 * 1750.0 / 60.0  # 3 ft diameter
        assert calc_blade_speed(d_in, rpm) == pytest.approx(expected)

    def test_larger_diameter_faster(self):
        assert calc_blade_speed(48, 1750) > calc_blade_speed(36, 1750)

    def test_larger_rpm_faster(self):
        assert calc_blade_speed(36, 3500) > calc_blade_speed(36, 1750)


# ===========================================================================
# Meridional Velocity
# ===========================================================================

class TestMeridionalVelocity:
    def test_basic(self):
        """Cm = Q_cfs / A"""
        cfm = 10000.0
        area_ft2 = 5.0
        expected = (10000.0 / 60.0) / 5.0
        assert calc_meridional_velocity(cfm, area_ft2) == pytest.approx(expected)

    def test_zero_area_raises(self):
        with pytest.raises(ValueError):
            calc_meridional_velocity(10000, 0.0)


# ===========================================================================
# Flow Areas
# ===========================================================================

class TestFlowAreas:
    def test_outlet_area(self):
        """A₂ = π·D·b"""
        d, b = 36.0, 5.4  # inches
        expected = math.pi * 3.0 * (5.4 / 12.0)  # ft²
        assert calc_outlet_area(d, b) == pytest.approx(expected)

    def test_inlet_area(self):
        """A₁ = π/4·(D_tip² − D_hub²)"""
        dt, dh = 36.0, 20.0  # inches
        expected = math.pi / 4.0 * ((36 / 12) ** 2 - (20 / 12) ** 2)
        assert calc_inlet_area(dt, dh) == pytest.approx(expected)

    def test_inlet_area_hub_zero(self):
        """No hub → full circle."""
        dt = 36.0
        expected = math.pi / 4.0 * (3.0 ** 2)
        assert calc_inlet_area(dt, 0.0) == pytest.approx(expected)


# ===========================================================================
# Whirl Velocity
# ===========================================================================

class TestWhirlVelocity:
    def test_positive(self):
        """Cu₂ should be positive for positive pressure."""
        Cu2 = calc_whirl_velocity(3.0, 150.0, 0.80)
        assert Cu2 > 0

    def test_higher_pressure_more_whirl(self):
        cu_low = calc_whirl_velocity(2.0, 150.0, 0.80)
        cu_high = calc_whirl_velocity(6.0, 150.0, 0.80)
        assert cu_high > cu_low

    def test_zero_U_raises(self):
        with pytest.raises(ValueError):
            calc_whirl_velocity(3.0, 0.0, 0.80)


# ===========================================================================
# Slip Factor
# ===========================================================================

class TestSlipFactor:
    def test_more_blades_less_slip(self):
        """More blades → higher slip factor (closer to 1.0)."""
        sig_8 = calc_slip_factor(8, 60.0)
        sig_24 = calc_slip_factor(24, 60.0)
        assert sig_24 > sig_8

    def test_range(self):
        """Slip factor should be between 0.5 and 1.0."""
        for z in [6, 8, 12, 24, 36]:
            sig = calc_slip_factor(z, 60.0)
            assert 0.5 <= sig <= 1.0, f"z={z}, sigma={sig:.3f}"

    def test_radial_blade(self):
        """β₂=90° → sin(90°)=1 → σ = 1 − π/Z"""
        sig = calc_slip_factor(8, 90.0)
        expected = 1.0 - math.pi / 8.0
        assert sig == pytest.approx(expected)


# ===========================================================================
# Blade Angle Calculation
# ===========================================================================

class TestBladeAngle:
    def test_pure_radial(self):
        """Cm only, no tangential diff → β = 90°"""
        beta = calc_blade_angle_from_triangle(100.0, 0.0)
        assert beta == pytest.approx(90.0)

    def test_backward(self):
        """U − Cu > 0 with Cm > 0 → 0 < β < 90"""
        beta = calc_blade_angle_from_triangle(50.0, 100.0)
        assert 0 < beta < 90

    def test_forward(self):
        """U − Cu < 0 → β > 90°"""
        beta = calc_blade_angle_from_triangle(50.0, -50.0)
        assert beta > 90


# ===========================================================================
# Velocity Magnitudes
# ===========================================================================

class TestVelocityMagnitudes:
    def test_relative(self):
        """W = √(Cm² + (U−Cu)²)"""
        assert calc_relative_velocity(3, 4) == pytest.approx(5.0)

    def test_absolute(self):
        """C = √(Cm² + Cu²)"""
        assert calc_absolute_velocity(3, 4) == pytest.approx(5.0)


# ===========================================================================
# De Haller Ratio
# ===========================================================================

class TestDeHaller:
    def test_no_diffusion(self):
        """W2 == W1 → ratio = 1.0"""
        assert calc_de_haller(100, 100) == pytest.approx(1.0)

    def test_safe_diffusion(self):
        """W2/W1 > 0.72 is safe."""
        assert calc_de_haller(100, 80) == pytest.approx(0.8)
        assert calc_de_haller(100, 80) > 0.72

    def test_zero_W1(self):
        assert calc_de_haller(0, 50) == 0.0


# ===========================================================================
# Outlet Width
# ===========================================================================

class TestOutletWidth:
    def test_positive(self):
        b = calc_outlet_width(10000, 36.0, 50.0)
        assert b > 0

    def test_zero_Cm_raises(self):
        with pytest.raises(ValueError):
            calc_outlet_width(10000, 36.0, 0.0)


# ===========================================================================
# Blade Chord & Solidity
# ===========================================================================

class TestBladeChord:
    def test_positive(self):
        c = calc_blade_chord(36.0, 20.0, 12, solidity_target=1.0)
        assert c > 0

    def test_higher_solidity_longer_chord(self):
        c_lo = calc_blade_chord(36.0, 20.0, 12, solidity_target=0.8)
        c_hi = calc_blade_chord(36.0, 20.0, 12, solidity_target=1.5)
        assert c_hi > c_lo

    def test_more_blades_shorter_chord(self):
        """More blades → smaller pitch → shorter chord at same solidity."""
        c_few = calc_blade_chord(36.0, 20.0, 8, 1.0)
        c_many = calc_blade_chord(36.0, 20.0, 24, 1.0)
        assert c_many < c_few


# ===========================================================================
# Solver Validation
# ===========================================================================

class TestSolverValidation:
    def test_missing_classification(self):
        solver = ImpellerAeroSolver()
        with pytest.raises(ValueError, match="Missing"):
            solver.solve({})

    def test_wrong_type(self):
        solver = ImpellerAeroSolver()
        with pytest.raises(ValueError, match="must be"):
            solver.solve({'classification': "not a classification"})

    def test_zero_diameter(self):
        solver = ImpellerAeroSolver()
        cls = _make_classification(diameter_in=0.0)
        with pytest.raises(ValueError, match="positive"):
            solver.solve({'classification': cls})


# ===========================================================================
# Integration — Full Step 1 → Step 2 Pipeline
# ===========================================================================

class TestIntegration:
    def _run_pipeline(self, cfm=10000, inwg=3.0, rpm=None):
        """Run Step 1 → Step 2 and return the aero result."""
        dp = FanDesignPoint(cfm, inwg, rpm=rpm)
        step1 = FanClassificationSolver().solve({'design_point': dp})
        cls = step1['metadata']['classification']
        step2 = ImpellerAeroSolver().solve({'classification': cls})
        return step2['metadata']['aero']

    def test_hvac_backward_inclined(self):
        """15000 CFM, 4 in.WG → BI fan with reasonable blade angles."""
        aero = self._run_pipeline(15000, 4.0)
        assert aero.classification.fan_type == FanType.BACKWARD_INCLINED
        # BI metal beta2 should be ~60° (design target)
        assert 50 < aero.blade.beta2_metal_deg < 70
        # Flow beta2 is smaller (U >> Cu for modest pressure rise)
        assert aero.blade.beta2_flow_deg < aero.blade.beta2_metal_deg
        # Reasonable blade count
        assert 8 <= aero.blade.num_blades <= 16
        # De Haller should be physically reasonable
        assert aero.de_haller_ratio > 0.1

    def test_dust_collection_radial(self):
        """3000 CFM, 15 in.WG, 3500 RPM → radial fan."""
        aero = self._run_pipeline(3000, 15.0, 3500)
        assert aero.classification.fan_type == FanType.RADIAL_BLADE
        # Radial metal β₂ = 90° (design target)
        assert aero.blade.beta2_metal_deg == pytest.approx(90.0)
        assert aero.blade.num_blades == 8

    def test_velocity_triangle_closure(self):
        """C² = Cm² + Cu² must hold at both inlet and outlet."""
        aero = self._run_pipeline(10000, 3.0)
        for tri in [aero.inlet_triangle, aero.outlet_triangle]:
            C_check = math.sqrt(tri.Cm ** 2 + tri.Cu ** 2)
            assert tri.C == pytest.approx(C_check, rel=1e-6)

    def test_relative_velocity_closure(self):
        """W² = Cm² + (U−Cu)² must hold at both stations."""
        aero = self._run_pipeline(10000, 3.0)
        for tri in [aero.inlet_triangle, aero.outlet_triangle]:
            W_check = math.sqrt(tri.Cm ** 2 + (tri.U - tri.Cu) ** 2)
            assert tri.W == pytest.approx(W_check, rel=1e-6)

    def test_blade_geometry_consistency(self):
        """Camber = β₂_metal − β₁_metal, stagger = (β₁_metal+β₂_metal)/2."""
        aero = self._run_pipeline(10000, 3.0)
        b = aero.blade
        assert b.camber_deg == pytest.approx(b.beta2_metal_deg - b.beta1_metal_deg)
        assert b.stagger_deg == pytest.approx(
            (b.beta1_metal_deg + b.beta2_metal_deg) / 2.0
        )
        # Incidence and deviation are consistent
        assert b.incidence_deg == pytest.approx(b.beta1_metal_deg - b.beta1_flow_deg)
        assert b.deviation_deg == pytest.approx(b.beta2_metal_deg - b.beta2_flow_deg)

    def test_passage_hub_ratio(self):
        """Hub ratio = D_hub / D_tip."""
        aero = self._run_pipeline(10000, 3.0)
        p = aero.passage
        assert p.hub_ratio == pytest.approx(p.hub_diameter_in / p.tip_diameter_in)

    def test_flow_coefficient_range(self):
        """φ = Cm₂/U₂ typically 0.1–0.6 for centrifugal fans."""
        aero = self._run_pipeline(10000, 3.0)
        assert 0.01 < aero.flow_coefficient < 1.0

    def test_work_coefficient_positive(self):
        """ψ should be positive (fan does work on air)."""
        aero = self._run_pipeline(10000, 3.0)
        assert aero.work_coefficient > 0

    def test_slip_factor_range(self):
        """Slip factor between 0.5 and 1.0."""
        aero = self._run_pipeline(10000, 3.0)
        assert 0.5 <= aero.slip_factor <= 1.0

    def test_standard_solver_keys(self):
        """Result dict has all BaseSolver standard keys."""
        dp = FanDesignPoint(10000, 3.0)
        step1 = FanClassificationSolver().solve({'design_point': dp})
        cls = step1['metadata']['classification']
        result = ImpellerAeroSolver().solve({'classification': cls})
        assert 'parts' in result
        assert 'transforms' in result
        assert 'anchors' in result
        assert 'metadata' in result
        assert result['parts'] == {}

    def test_rpm_override(self):
        """When design_point has rpm, solver uses it instead of midpoint."""
        cls = _make_classification(rpm=2000)
        result = ImpellerAeroSolver().solve({'classification': cls})
        assert result['metadata']['rpm'] == 2000.0

    def test_blade_count_override(self):
        """Can override blade count via inputs."""
        cls = _make_classification()
        result = ImpellerAeroSolver().solve({
            'classification': cls,
            'num_blades': 16,
        })
        assert result['metadata']['num_blades'] == 16

    def test_forward_curved(self):
        """FC fan: high Ns → β₂ > 90°, many blades."""
        # Use a known FC classification
        cls = _make_classification(
            cfm=20000, inwg=1.0, rpm=1200,
            fan_type=FanType.FORWARD_CURVED,
            diameter_in=24.0, eta=0.60,
        )
        result = ImpellerAeroSolver().solve({'classification': cls})
        aero = result['metadata']['aero']
        assert aero.blade.num_blades == 36
        # FC outlet width ratio is large
        assert aero.passage.outlet_width_in > 5

    def test_metadata_flat_fields(self):
        """Check flat metadata keys are present."""
        cls = _make_classification()
        result = ImpellerAeroSolver().solve({'classification': cls})
        meta = result['metadata']
        for key in ('rpm', 'beta1_metal_deg', 'beta2_metal_deg',
                    'beta1_flow_deg', 'beta2_flow_deg', 'num_blades',
                    'hub_diameter_in', 'tip_diameter_in', 'outlet_width_in',
                    'slip_factor', 'de_haller_ratio', 'flow_coefficient',
                    'work_coefficient', 'reaction_degree',
                    'inlet_Cm', 'outlet_Cm', 'outlet_Cu',
                    'blade_chord_in', 'blade_solidity'):
            assert key in meta, f"Missing metadata key: {key}"

    def test_echo_classification(self):
        """ImpellerAeroResult echoes the input classification."""
        cls = _make_classification()
        result = ImpellerAeroSolver().solve({'classification': cls})
        aero = result['metadata']['aero']
        assert aero.classification is cls
