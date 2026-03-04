"""
Fan Classification Solver — Step 1 of 7 in the physics-first fan engineering system.

Takes performance requirements (CFM, static pressure) and derives the fan type,
impeller size, efficiency, and power from first principles. No geometry is produced;
this solver classifies and sizes, then passes a typed dataclass to downstream solvers.

References:
    - AMCA 201-02: Fans and Systems
    - AMCA 203-90: Field Performance Measurement
    - Bleier, "Fan Handbook", McGraw-Hill
    - Balje, "Turbomachines", Wiley 1981
    - Cordier, "Similarity Considerations in Turbomachines", VDI 1953
    - ASHRAE Handbook — HVAC Systems and Equipment, Ch. 20
"""

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, Tuple, Optional

from .base_solver import BaseSolver


# ---------------------------------------------------------------------------
# Engineering Constants
# ---------------------------------------------------------------------------

INWG_TO_PA = 248.84          # 1 in.WG = 248.84 Pa
INWG_TO_PSF = 5.2023         # 1 in.WG = 5.2023 lbf/ft²
M3S_TO_CFM = 2118.88         # 1 m³/s = 2118.88 CFM
AIR_HP_CONST = 6356.0        # CFM × in.WG / 6356 = Air HP
HP_TO_KW = 0.7457            # 1 HP = 0.7457 kW
CORDIER_A = 1.137            # Cordier diagram constant
CORDIER_B = 0.424            # Cordier diagram exponent


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FanType(Enum):
    RADIAL_BLADE = auto()
    BACKWARD_INCLINED = auto()
    BACKWARD_CURVED = auto()
    FORWARD_CURVED = auto()


class BladeAngleClass(Enum):
    RADIAL = auto()       # β₂ ≈ 90°
    BACKWARD = auto()     # β₂ < 90°
    FORWARD = auto()      # β₂ > 90°


class OperatingRegion(Enum):
    STABLE = auto()
    NEAR_STALL = auto()
    UNSTABLE = auto()
    BEYOND_RANGE = auto()


class UnitSystem(Enum):
    US = auto()   # CFM, in.WG
    SI = auto()   # m³/s, Pa


# ---------------------------------------------------------------------------
# Ns Classification Ranges
# ---------------------------------------------------------------------------

# (ns_min, ns_max, FanType, BladeAngleClass, peak_efficiency)
NS_RANGES = [
    (0,    2000, FanType.RADIAL_BLADE,       BladeAngleClass.RADIAL,   0.55),
    (2000, 3200, FanType.BACKWARD_INCLINED,  BladeAngleClass.BACKWARD, 0.82),
    (3200, 4500, FanType.BACKWARD_CURVED,    BladeAngleClass.BACKWARD, 0.80),
    (4500, 8000, FanType.FORWARD_CURVED,     BladeAngleClass.FORWARD,  0.63),
]

# Stable Ns sub-ranges per fan type (fraction of full range where operation is stable)
STABLE_RANGES = {
    FanType.RADIAL_BLADE:      (200,  1800),
    FanType.BACKWARD_INCLINED: (2200, 3000),
    FanType.BACKWARD_CURVED:   (3400, 4200),
    FanType.FORWARD_CURVED:    (5000, 7000),
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FanDesignPoint:
    """Input operating point for fan classification."""
    flow_rate: float          # CFM (US) or m³/s (SI)
    total_pressure: float     # in.WG (US) or Pa (SI)
    units: UnitSystem = UnitSystem.US
    rpm: Optional[float] = None
    altitude_ft: float = 0.0
    temperature_f: float = 70.0

    def to_us(self) -> Tuple[float, float]:
        """Return (CFM, in.WG) regardless of input units."""
        if self.units == UnitSystem.US:
            return self.flow_rate, self.total_pressure
        return self.flow_rate * M3S_TO_CFM, self.total_pressure / INWG_TO_PA

    def to_si(self) -> Tuple[float, float]:
        """Return (m³/s, Pa) regardless of input units."""
        if self.units == UnitSystem.SI:
            return self.flow_rate, self.total_pressure
        return self.flow_rate / M3S_TO_CFM, self.total_pressure * INWG_TO_PA


@dataclass
class EfficiencyEstimate:
    """Efficiency breakdown."""
    total: float              # Overall fan efficiency (0-1)
    peak_for_type: float      # Published peak for this fan type
    derating_factor: float    # How far from peak Ns (1.0 = at peak)


@dataclass
class FanClassification:
    """Output contract — passed to Step 2 (impeller aerodynamics)."""
    fan_type: FanType
    blade_angle_class: BladeAngleClass
    operating_region: OperatingRegion
    specific_speed_ns: float
    specific_diameter_ds: float
    impeller_diameter_in: float
    recommended_rpm_range: Tuple[float, float]
    tip_speed_fts: float
    efficiency: EfficiencyEstimate
    shaft_power_hp: float
    shaft_power_kw: float
    design_point: FanDesignPoint


# ---------------------------------------------------------------------------
# Pure Math Functions
# ---------------------------------------------------------------------------

def calc_specific_speed(rpm: float, cfm: float, dp_inwg: float) -> float:
    """
    Ns = RPM × √Q / ΔP^(3/4)

    Accepts CFM and in.WG, converts internally to ft³/s and lbf/ft²
    so that Ns falls in the standard 0-8000 fan classification range.
    Ref: AMCA 201-02 §6.2, Bleier Eq. 2.3, Balje Ch. 3
    """
    if dp_inwg <= 0 or cfm <= 0 or rpm <= 0:
        raise ValueError(f"All inputs must be positive: rpm={rpm}, cfm={cfm}, dp={dp_inwg}")
    q_cfs = cfm / 60.0            # ft³/min → ft³/s
    dp_psf = dp_inwg * INWG_TO_PSF  # in.WG → lbf/ft²
    return rpm * math.sqrt(q_cfs) / (dp_psf ** 0.75)


def classify_fan_type(ns: float) -> Tuple[FanType, BladeAngleClass, float]:
    """
    Map specific speed to fan type, blade angle class, and peak efficiency.
    Ref: Bleier Table 2-1
    """
    for ns_min, ns_max, fan_type, blade_class, peak_eta in NS_RANGES:
        if ns_min <= ns < ns_max:
            return fan_type, blade_class, peak_eta
    # Beyond 8000 — still forward curved but beyond normal range
    if ns >= 8000:
        return FanType.FORWARD_CURVED, BladeAngleClass.FORWARD, 0.63
    raise ValueError(f"Specific speed Ns={ns:.0f} is below minimum range")


def calc_specific_diameter(ns: float) -> float:
    """
    Ds = 10^A / Ns^B  (Cordier correlation)

    Ref: Cordier 1953, Balje 1981 Ch. 3
    """
    if ns <= 0:
        raise ValueError(f"Ns must be positive, got {ns}")
    return (10 ** CORDIER_A) / (ns ** CORDIER_B)


def calc_impeller_diameter(ds: float, cfm: float, dp_inwg: float) -> float:
    """
    D = Ds × √(Q_cfs) / (ΔP_psf)^(1/4)  → result in feet, converted to inches.

    Q_cfs = CFM / 60
    ΔP_psf = in.WG × 5.2023
    Ref: Balje Eq. 3.1
    """
    q_cfs = cfm / 60.0
    dp_psf = dp_inwg * INWG_TO_PSF
    d_ft = ds * math.sqrt(q_cfs) / (dp_psf ** 0.25)
    return d_ft * 12.0  # feet → inches


def estimate_efficiency(fan_type: FanType, ns: float) -> EfficiencyEstimate:
    """
    Parabolic derating from optimal Ns for each fan type.
    Ref: Bleier Fig. 2-3, ASHRAE Ch. 20
    """
    for ns_min, ns_max, ft, _, peak_eta in NS_RANGES:
        if ft == fan_type:
            ns_mid = (ns_min + ns_max) / 2.0
            ns_span = (ns_max - ns_min) / 2.0
            if ns_span == 0:
                derating = 1.0
            else:
                # Parabolic: 1 at center, drops to ~0.7 at edges
                x = min(abs(ns - ns_mid) / ns_span, 1.5)
                derating = max(1.0 - 0.3 * x * x, 0.3)
            return EfficiencyEstimate(
                total=peak_eta * derating,
                peak_for_type=peak_eta,
                derating_factor=derating,
            )
    # Fallback for beyond-range
    return EfficiencyEstimate(total=0.50, peak_for_type=0.63, derating_factor=0.79)


def calc_shaft_power(cfm: float, dp_inwg: float, eta: float) -> Tuple[float, float]:
    """
    HP = Q × ΔP / (6356 × η)

    Returns (hp, kw).
    Ref: AMCA 203-90 §7
    """
    if eta <= 0:
        raise ValueError(f"Efficiency must be positive, got {eta}")
    hp = (cfm * dp_inwg) / (AIR_HP_CONST * eta)
    return hp, hp * HP_TO_KW


def calc_rpm_range(cfm: float, dp_inwg: float, ns_target: float) -> Tuple[float, float]:
    """
    Derive RPM range from ±20% Ns band.
    RPM = Ns × ΔP_psf^(3/4) / √Q_cfs  (consistent with calc_specific_speed)
    """
    if cfm <= 0 or dp_inwg <= 0:
        raise ValueError("CFM and pressure must be positive")
    q_cfs = cfm / 60.0
    dp_psf = dp_inwg * INWG_TO_PSF
    denom = math.sqrt(q_cfs)
    numer_factor = dp_psf ** 0.75
    rpm_center = ns_target * numer_factor / denom
    return (rpm_center * 0.8, rpm_center * 1.2)


def calc_tip_speed(d_in: float, rpm: float) -> float:
    """
    V = π × D_ft × RPM / 60  (ft/s)
    Ref: Bleier Ch. 3
    """
    d_ft = d_in / 12.0
    return math.pi * d_ft * rpm / 60.0


def assess_operating_region(ns: float, fan_type: FanType) -> OperatingRegion:
    """
    Assess whether operating point is in the stable region for the given fan type.
    Ref: AMCA 201-02 §8
    """
    stable = STABLE_RANGES.get(fan_type)
    if stable is None:
        return OperatingRegion.BEYOND_RANGE

    ns_low, ns_high = stable
    # Find full range for this type
    full_min, full_max = 0, 8000
    for rng_min, rng_max, ft, _, _ in NS_RANGES:
        if ft == fan_type:
            full_min, full_max = rng_min, rng_max
            break

    if ns_low <= ns <= ns_high:
        return OperatingRegion.STABLE
    elif full_min <= ns < full_max:
        # Within type range but outside stable sub-range
        margin = (ns_high - ns_low) * 0.15
        if (ns_low - margin) <= ns < ns_low or ns_high < ns <= (ns_high + margin):
            return OperatingRegion.NEAR_STALL
        return OperatingRegion.UNSTABLE
    else:
        return OperatingRegion.BEYOND_RANGE


# ---------------------------------------------------------------------------
# Solver Class
# ---------------------------------------------------------------------------

class FanClassificationSolver(BaseSolver):
    """
    Step 1: Fan Classification & Sizing Solver.

    Takes a FanDesignPoint and returns a FanClassification dataclass
    with fan type, impeller size, efficiency, and power estimates.
    No geometry is produced — that is downstream.
    """

    # Validation limits
    CFM_MIN, CFM_MAX = 50.0, 500_000.0
    INWG_MIN, INWG_MAX = 0.1, 80.0
    RPM_MIN, RPM_MAX = 100.0, 10_000.0

    # Default target Ns for auto-RPM (backward-inclined sweet spot)
    DEFAULT_NS_TARGET = 2800.0
    AUTO_RPM_MIN, AUTO_RPM_MAX = 300.0, 5000.0

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        dp: FanDesignPoint = inputs.get('design_point')
        if dp is None:
            raise ValueError("Missing 'design_point' in inputs")
        if not isinstance(dp, FanDesignPoint):
            raise ValueError("'design_point' must be a FanDesignPoint instance")

        cfm, inwg = dp.to_us()

        if not (self.CFM_MIN <= cfm <= self.CFM_MAX):
            raise ValueError(
                f"Flow rate {cfm:.0f} CFM outside valid range "
                f"[{self.CFM_MIN}-{self.CFM_MAX}]"
            )
        if not (self.INWG_MIN <= inwg <= self.INWG_MAX):
            raise ValueError(
                f"Pressure {inwg:.2f} in.WG outside valid range "
                f"[{self.INWG_MIN}-{self.INWG_MAX}]"
            )
        if dp.rpm is not None and not (self.RPM_MIN <= dp.rpm <= self.RPM_MAX):
            raise ValueError(
                f"RPM {dp.rpm:.0f} outside valid range "
                f"[{self.RPM_MIN}-{self.RPM_MAX}]"
            )
        return True

    def solve(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify and size a fan from its design point.

        Args:
            inputs: {'design_point': FanDesignPoint, ...}

        Returns:
            Standard solver dict with:
            - parts: {} (empty — no geometry at Step 1)
            - metadata.classification: FanClassification dataclass
        """
        self.validate_inputs(inputs)

        dp: FanDesignPoint = inputs['design_point']
        cfm, inwg = dp.to_us()

        # --- Determine RPM ---
        if dp.rpm is not None:
            rpm = dp.rpm
        else:
            # Auto-RPM: target Ns ≈ 2800 (BI sweet spot)
            rpm_low, rpm_high = calc_rpm_range(cfm, inwg, self.DEFAULT_NS_TARGET)
            rpm = (rpm_low + rpm_high) / 2.0
            rpm = max(self.AUTO_RPM_MIN, min(rpm, self.AUTO_RPM_MAX))

        # --- Core calculations ---
        ns = calc_specific_speed(rpm, cfm, inwg)
        fan_type, blade_class, _ = classify_fan_type(ns)
        ds = calc_specific_diameter(ns)
        diameter_in = calc_impeller_diameter(ds, cfm, inwg)
        eff = estimate_efficiency(fan_type, ns)
        hp, kw = calc_shaft_power(cfm, inwg, eff.total)
        rpm_range = calc_rpm_range(cfm, inwg, ns)
        tip_speed = calc_tip_speed(diameter_in, rpm)
        region = assess_operating_region(ns, fan_type)

        classification = FanClassification(
            fan_type=fan_type,
            blade_angle_class=blade_class,
            operating_region=region,
            specific_speed_ns=ns,
            specific_diameter_ds=ds,
            impeller_diameter_in=diameter_in,
            recommended_rpm_range=rpm_range,
            tip_speed_fts=tip_speed,
            efficiency=eff,
            shaft_power_hp=hp,
            shaft_power_kw=kw,
            design_point=dp,
        )

        return {
            'parts': {},
            'transforms': {},
            'anchors': {},
            'metadata': {
                'classification': classification,
                'specific_speed_ns': ns,
                'fan_type': fan_type.name,
                'impeller_diameter_in': diameter_in,
                'shaft_power_hp': hp,
                'shaft_power_kw': kw,
                'efficiency': eff.total,
                'operating_region': region.name,
                'rpm_used': rpm,
            },
        }
