"""
Fan Structural Solver — Step 4 of 7 in the physics-first fan engineering system.

Consumes VoluteResult (Step 3) which chains back through ImpellerAeroResult
(Step 2) and FanClassification (Step 1). Derives shaft sizing, bearing
selection, critical speed, housing wall thickness, bolt pattern, and
base/pedestal from first principles.

No geometry is produced here; this solver outputs a typed dataclass of
structural parameters that downstream geometry generators consume.

References:
    - Shigley, "Mechanical Engineering Design", 11th ed., Ch. 7 (shafts)
    - SKF Bearing Catalog — static/dynamic load ratings
    - Bleier, "Fan Handbook", Ch. 7–8 (shaft, bearing, housing)
    - AMCA 99-16 — Standards Handbook (fan construction classes)
    - ASHRAE Handbook — HVAC Systems and Equipment, Ch. 20
    - Roark, "Formulas for Stress and Strain" (housing, bolts)
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional, List

from .base_solver import BaseSolver
from .fan_classifier import FanType, FanClassification, HP_TO_KW
from .impeller_aero import ImpellerAeroResult, PassageGeometry
from .volute_solver import VoluteResult


# ---------------------------------------------------------------------------
# Material & Engineering Constants
# ---------------------------------------------------------------------------

STEEL_DENSITY_LB_IN3 = 0.284       # Carbon steel density (lb/in³)
STEEL_YIELD_PSI = 36_000           # A36 yield strength (psi)
STEEL_SHEAR_ALLOW_PSI = 14_400     # 0.4 × Sy for shaft shear (AISC ASD)
STEEL_BENDING_ALLOW_PSI = 21_600   # 0.6 × Sy for bending (AISC ASD)
STEEL_E_PSI = 29_000_000           # Young's modulus (psi)
ALUMINUM_DENSITY_LB_IN3 = 0.098    # 6061-T6 aluminum
CAST_IRON_DENSITY_LB_IN3 = 0.260   # Gray cast iron

# Bolt constants
BOLT_SHEAR_ALLOW_PSI = 21_600      # A325 bolt allowable shear (psi)
BOLT_CLAMP_FACTOR = 1.5            # Clamping force / applied force

# Housing gauge table: fan type → nominal wall thickness (inches)
HOUSING_GAUGE = {
    FanType.RADIAL_BLADE:      0.1345,   # 10 gauge (high pressure)
    FanType.BACKWARD_INCLINED: 0.1046,   # 12 gauge
    FanType.BACKWARD_CURVED:   0.1046,   # 12 gauge
    FanType.FORWARD_CURVED:    0.0747,   # 14 gauge (low pressure)
}

# AMCA construction class thresholds (tip speed ft/s)
AMCA_CLASS_LIMITS = [
    (0,   125, "I",   0.0747),   # Class I  — 14 gauge
    (125, 200, "II",  0.1046),   # Class II — 12 gauge
    (200, 300, "III", 0.1345),   # Class III — 10 gauge
    (300, 999, "IV",  0.1644),   # Class IV — 8 gauge
]

# Bearing L10 life target (hours)
BEARING_L10_TARGET = 40_000        # ASHRAE minimum for HVAC fans


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ShaftDesign:
    """Shaft sizing results."""
    diameter_in: float          # Minimum required shaft diameter
    length_in: float            # Total shaft length (bearing span + overhang)
    material: str               # e.g. "1045 Steel"
    torque_in_lb: float         # Steady-state torque
    bending_moment_in_lb: float # Max bending moment (impeller weight)
    combined_stress_psi: float  # Von Mises equivalent
    safety_factor: float        # Sy / σ_combined
    critical_speed_rpm: float   # First lateral critical speed
    critical_speed_margin: float  # N_critical / N_operating
    bearing_span_in: float       # Distance between bearing centers
    overhang_in: float           # Impeller overhang beyond bearing B


@dataclass
class BearingSpec:
    """Bearing selection results."""
    bore_in: float              # Shaft diameter at bearing seat
    dynamic_load_lbf: float     # Required dynamic load rating (C)
    static_load_lbf: float      # Required static load rating (C0)
    radial_load_lbf: float      # Applied radial load per bearing
    axial_load_lbf: float       # Applied axial (thrust) load
    l10_life_hours: float       # Calculated L10 life at operating speed
    quantity: int               # Number of bearings (typically 2)
    arrangement: str            # e.g. "2x deep groove" or "1x angular contact + 1x deep groove"


@dataclass
class HousingStructure:
    """Scroll housing structural parameters."""
    wall_thickness_in: float    # Sheet metal gauge thickness
    amca_class: str             # Construction class (I–IV)
    material: str               # Housing material
    housing_weight_lb: float    # Estimated housing weight
    flange_thickness_in: float  # Inlet/discharge flange thickness
    stiffener_count: int        # Number of circumferential stiffeners


@dataclass
class BoltPattern:
    """Bolt circle / mounting pattern."""
    num_bolts: int              # Number of mounting bolts
    bolt_diameter_in: float     # Bolt nominal diameter
    bolt_circle_in: float       # Bolt circle diameter (for flanges)
    required_clamp_lbf: float   # Total clamping force needed
    bolt_shear_lbf: float       # Shear per bolt


@dataclass
class BaseDesign:
    """Pedestal / base frame."""
    length_in: float            # Along shaft axis
    width_in: float             # Perpendicular to shaft
    height_in: float            # Pedestal height
    weight_lb: float            # Base weight estimate
    total_fan_weight_lb: float  # Complete assembly weight


@dataclass
class FanStructuralResult:
    """Output contract — passed to Step 5 (geometry) and downstream."""
    shaft: ShaftDesign
    bearings: BearingSpec
    housing: HousingStructure
    inlet_bolts: BoltPattern
    discharge_bolts: BoltPattern
    base: BaseDesign
    impeller_weight_lb: float
    volute: VoluteResult        # Echo Step 3 for traceability


# ---------------------------------------------------------------------------
# Pure Math Functions
# ---------------------------------------------------------------------------

def calc_torque(hp: float, rpm: float) -> float:
    """
    T = 63025 × HP / RPM  (in·lbf)

    Standard shaft torque formula.
    Ref: Shigley Eq. 7-1
    """
    if rpm <= 0:
        raise ValueError(f"RPM must be positive, got {rpm}")
    return 63025.0 * hp / rpm


def calc_impeller_weight(tip_diameter_in: float, outlet_width_in: float,
                         hub_ratio: float, num_blades: int,
                         fan_type: FanType) -> float:
    """
    Estimate impeller weight from geometry.

    Approximation: hub disk + shroud disk + blades.
    Uses steel density. FC impellers use thinner blades.
    Ref: Bleier Ch. 7
    """
    tip_r = tip_diameter_in / 2.0
    hub_r = tip_r * hub_ratio

    # Hub disk (backplate): full disk, typical 3/16" thick
    hub_thick = 0.1875
    hub_area = math.pi * tip_r ** 2
    hub_vol = hub_area * hub_thick

    # Shroud (front plate with eye opening): annular ring, 1/8" thick
    shroud_thick = 0.125
    eye_r = hub_r  # Approximate eye = hub diameter
    shroud_area = math.pi * (tip_r ** 2 - eye_r ** 2)
    shroud_vol = shroud_area * shroud_thick

    # Blades: simplified as flat plates
    blade_height = tip_r - hub_r
    blade_width = outlet_width_in
    blade_thick = 0.125 if fan_type != FanType.FORWARD_CURVED else 0.075
    blade_vol = blade_height * blade_width * blade_thick * num_blades

    total_vol = hub_vol + shroud_vol + blade_vol
    return total_vol * STEEL_DENSITY_LB_IN3


def calc_bending_moment(weight_lb: float, overhang_in: float) -> float:
    """
    M = W × L  (in·lbf)

    Cantilevered impeller weight at overhang distance from nearest bearing.
    Ref: Shigley §7-4
    """
    return weight_lb * overhang_in


def calc_shaft_diameter(torque: float, moment: float,
                        shear_allow: float = STEEL_SHEAR_ALLOW_PSI) -> float:
    """
    Minimum shaft diameter from combined torsion + bending (ASME code).

    d = (16 / (π·τ_allow) × √(M² + T²))^(1/3)

    Ref: Shigley Eq. 7-8 (DE-Goodman), simplified static version
    """
    combined = math.sqrt(moment ** 2 + torque ** 2)
    if shear_allow <= 0:
        raise ValueError(f"Allowable shear must be positive, got {shear_allow}")
    d_cubed = 16.0 / (math.pi * shear_allow) * combined
    return d_cubed ** (1.0 / 3.0)


def calc_critical_speed(shaft_diameter_in: float, bearing_span_in: float,
                        impeller_weight_lb: float) -> float:
    """
    First lateral critical speed (Rayleigh single-mass approximation).

    N_c = 187.7 × √(E·I / (W·L³))  (RPM)

    Where:
        E = modulus (psi), I = π·d⁴/64 (in⁴)
        W = impeller weight (lbf), L = bearing span (in)

    Ref: Shigley §7-5, Bleier §7.4
    """
    if bearing_span_in <= 0 or impeller_weight_lb <= 0:
        return 999_999.0  # Effectively infinite
    I = math.pi * shaft_diameter_in ** 4 / 64.0
    # Deflection of simply-supported beam with center load
    delta = (impeller_weight_lb * bearing_span_in ** 3) / (48.0 * STEEL_E_PSI * I)
    if delta <= 0:
        return 999_999.0
    # N_c = 187.7 / √δ  (δ in inches, N_c in RPM)
    return 187.7 / math.sqrt(delta)


def calc_bearing_loads(impeller_weight_lb: float, shaft_weight_lb: float,
                       bearing_span_in: float, overhang_in: float) -> Tuple[float, float]:
    """
    Radial bearing loads from static equilibrium (cantilevered impeller).

    Bearing A (drive end) and Bearing B (impeller end).
    Impeller at overhang distance beyond Bearing B.

    Returns (load_A, load_B) in lbf.
    Ref: Bleier §7.5
    """
    W_total = impeller_weight_lb + shaft_weight_lb
    # Impeller overhung at distance 'overhang' from bearing B
    # Taking moments about A: R_B × span = W_impeller × (span + overhang) + W_shaft × span/2
    R_B = (impeller_weight_lb * (bearing_span_in + overhang_in)
           + shaft_weight_lb * bearing_span_in / 2.0) / bearing_span_in
    R_A = W_total + impeller_weight_lb * overhang_in / bearing_span_in - R_B
    # Ensure non-negative
    R_A = abs(R_A)
    R_B = abs(R_B)
    return R_A, R_B


def calc_bearing_l10(dynamic_rating_lbf: float, radial_load_lbf: float,
                     rpm: float) -> float:
    """
    L10 bearing life in hours.

    L10 = (C/P)^3 × 10^6 / (60 × RPM)

    C = dynamic load rating, P = equivalent radial load.
    Exponent 3 for ball bearings.
    Ref: SKF General Catalog, ISO 281
    """
    if radial_load_lbf <= 0 or rpm <= 0:
        return 999_999.0
    L10_rev = (dynamic_rating_lbf / radial_load_lbf) ** 3 * 1_000_000
    return L10_rev / (60.0 * rpm)


def calc_dynamic_rating_required(radial_load_lbf: float, rpm: float,
                                 l10_hours: float) -> float:
    """
    Required dynamic load rating C for target L10 life.

    C = P × (60 × RPM × L10_hours / 10^6)^(1/3)

    Ref: ISO 281
    """
    if rpm <= 0 or l10_hours <= 0:
        return radial_load_lbf
    L10_rev = 60.0 * rpm * l10_hours
    return radial_load_lbf * (L10_rev / 1_000_000) ** (1.0 / 3.0)


def select_amca_class(tip_speed_fts: float) -> Tuple[str, float]:
    """
    AMCA construction class from tip speed.

    Returns (class_name, wall_thickness_in).
    Ref: AMCA 99-16
    """
    for lo, hi, name, gauge in AMCA_CLASS_LIMITS:
        if lo <= tip_speed_fts < hi:
            return name, gauge
    return "IV", 0.1644


def calc_housing_weight(max_radius_in: float, volute_width_in: float,
                        wall_thickness_in: float) -> float:
    """
    Estimate scroll housing weight as a cylindrical shell + two side plates.

    Shell: π × D × W × t × ρ
    Sides: 2 × π × R² × t × ρ (approximate — actual is spiral, not circular)

    Ref: Bleier §8.2
    """
    D = 2.0 * max_radius_in
    # Shell
    shell_area = math.pi * D * volute_width_in
    shell_vol = shell_area * wall_thickness_in
    # Side plates (two, full circle approximation)
    side_area = 2.0 * math.pi * max_radius_in ** 2
    side_vol = side_area * wall_thickness_in
    total_vol = shell_vol + side_vol
    return total_vol * STEEL_DENSITY_LB_IN3


def calc_bolt_pattern(load_lbf: float, opening_perimeter_in: float,
                      bolt_allow_shear: float = BOLT_SHEAR_ALLOW_PSI) -> BoltPattern:
    """
    Size bolt pattern for an inlet or discharge flange.

    Bolt spacing ≈ 6–8 inches around the perimeter.
    Bolt diameter chosen from standard sizes to carry shear + clamp.
    Ref: Roark, AISC bolt tables
    """
    # Target spacing ~6" around perimeter
    spacing = 6.0
    num_bolts = max(4, int(math.ceil(opening_perimeter_in / spacing)))
    # Round to multiple of 4
    num_bolts = ((num_bolts + 3) // 4) * 4

    clamp_force = load_lbf * BOLT_CLAMP_FACTOR
    shear_per_bolt = load_lbf / num_bolts

    # Select bolt diameter: A_bolt = shear / τ_allow, d = √(4·A/π)
    a_bolt = shear_per_bolt / bolt_allow_shear
    d_bolt_min = math.sqrt(4.0 * a_bolt / math.pi) if a_bolt > 0 else 0.25

    # Snap to standard sizes
    standard_bolts = [0.25, 0.3125, 0.375, 0.4375, 0.5, 0.625, 0.75, 0.875, 1.0]
    d_bolt = 0.375  # default
    for sb in standard_bolts:
        if sb >= d_bolt_min:
            d_bolt = sb
            break

    bolt_circle = opening_perimeter_in / math.pi  # approximate diameter

    return BoltPattern(
        num_bolts=num_bolts,
        bolt_diameter_in=d_bolt,
        bolt_circle_in=bolt_circle,
        required_clamp_lbf=clamp_force,
        bolt_shear_lbf=shear_per_bolt,
    )


def calc_stiffener_count(max_radius_in: float, wall_thickness_in: float) -> int:
    """
    Number of circumferential stiffeners based on R/t ratio.

    Rule of thumb: one stiffener per 18–24 inches of housing diameter
    if R/t > 200 (thin shell buckling concern).
    Ref: Bleier §8.3
    """
    D = 2.0 * max_radius_in
    r_over_t = max_radius_in / wall_thickness_in if wall_thickness_in > 0 else 0
    if r_over_t < 200:
        return 0
    return max(2, int(math.ceil(D / 24.0)))


# ---------------------------------------------------------------------------
# Solver Class
# ---------------------------------------------------------------------------

class FanStructuralSolver(BaseSolver):
    """
    Step 4: Fan Structural Solver.

    Takes a VoluteResult (from Step 3) and derives shaft, bearings,
    housing structure, bolt patterns, and base design.

    Inputs dict:
        'volute': VoluteResult           (required)
        'bearing_span_ratio': float      (optional, span/diameter, default 2.5)
        'overhang_ratio': float          (optional, overhang/diameter, default 0.6)

    Returns standard solver dict with:
        parts: {}  (no geometry at Step 4)
        metadata.structural: FanStructuralResult dataclass
    """

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        vol = inputs.get('volute')
        if vol is None:
            raise ValueError("Missing 'volute' in inputs")
        if not isinstance(vol, VoluteResult):
            raise ValueError("'volute' must be a VoluteResult instance")
        return True

    def solve(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_inputs(inputs)

        vol: VoluteResult = inputs['volute']
        aero = vol.aero
        cls = aero.classification
        fan_type = cls.fan_type
        dp = cls.design_point
        cfm, inwg = dp.to_us()

        # --- Key values from upstream ---
        tip_d = aero.passage.tip_diameter_in
        rpm = aero.rpm
        hp = cls.shaft_power_hp
        tip_speed = cls.tip_speed_fts
        num_blades = aero.blade.num_blades
        hub_ratio = aero.passage.hub_ratio
        outlet_width = aero.passage.outlet_width_in
        max_r = vol.max_radius_in

        # --- Impeller weight ---
        W_impeller = calc_impeller_weight(
            tip_d, outlet_width, hub_ratio, num_blades, fan_type,
        )

        # --- Shaft sizing ---
        torque = calc_torque(hp, rpm)

        # Bearing span & overhang — proportional to shaft diameter.
        # Typical centrifugal fan: span = 12–16× shaft_d,
        # overhang = 3–5× shaft_d (Bleier §7.3, practical fan layouts).
        # Shaft_d isn't known yet, so estimate first then refine.
        span_mult = inputs.get('bearing_span_mult', 14.0)
        overhang_mult = inputs.get('overhang_mult', 4.0)

        # Initial overhang estimate (4× minimum shaft 0.75") for sizing
        overhang_est = 0.75 * overhang_mult
        moment = calc_bending_moment(W_impeller, overhang_est)
        shaft_d = calc_shaft_diameter(torque, moment)

        # Round up to nearest 1/8"
        shaft_d = math.ceil(shaft_d * 8.0) / 8.0
        shaft_d = max(shaft_d, 0.75)  # Minimum practical shaft

        # Now compute final bearing span & overhang from actual shaft_d
        bearing_span = shaft_d * span_mult
        overhang = shaft_d * overhang_mult

        shaft_length = bearing_span + overhang + 4.0  # +4" for coupling end

        # Recompute moment with final overhang
        moment = calc_bending_moment(W_impeller, overhang)

        # Shaft weight
        shaft_vol = math.pi / 4.0 * shaft_d ** 2 * shaft_length
        shaft_weight = shaft_vol * STEEL_DENSITY_LB_IN3

        # Von Mises combined stress check
        # τ = 16T/(πd³), σ = 32M/(πd³)
        tau = 16.0 * torque / (math.pi * shaft_d ** 3)
        sigma_b = 32.0 * moment / (math.pi * shaft_d ** 3)
        sigma_vm = math.sqrt(sigma_b ** 2 + 3.0 * tau ** 2)
        sf = STEEL_YIELD_PSI / sigma_vm if sigma_vm > 0 else 99.0

        # Critical speed
        n_crit = calc_critical_speed(shaft_d, bearing_span, W_impeller)
        crit_margin = n_crit / rpm if rpm > 0 else 99.0

        shaft = ShaftDesign(
            diameter_in=shaft_d,
            length_in=shaft_length,
            material="1045 Steel",
            torque_in_lb=torque,
            bending_moment_in_lb=moment,
            combined_stress_psi=sigma_vm,
            safety_factor=sf,
            critical_speed_rpm=n_crit,
            critical_speed_margin=crit_margin,
            bearing_span_in=bearing_span,
            overhang_in=overhang,
        )

        # --- Bearings ---
        R_A, R_B = calc_bearing_loads(
            W_impeller, shaft_weight, bearing_span, overhang,
        )
        max_radial = max(R_A, R_B)

        # Thrust load estimate: 10% of radial for centrifugal fans
        thrust = W_impeller * 0.10

        C_required = calc_dynamic_rating_required(
            max_radial, rpm, BEARING_L10_TARGET,
        )
        l10 = calc_bearing_l10(C_required, max_radial, rpm)

        bearings = BearingSpec(
            bore_in=shaft_d,
            dynamic_load_lbf=C_required,
            static_load_lbf=max_radial * 2.0,
            radial_load_lbf=max_radial,
            axial_load_lbf=thrust,
            l10_life_hours=l10,
            quantity=2,
            arrangement="2x deep groove ball",
        )

        # --- Housing ---
        amca_class, wall_t = select_amca_class(tip_speed)
        # Override with fan-type gauge if thicker
        type_gauge = HOUSING_GAUGE.get(fan_type, 0.1046)
        wall_t = max(wall_t, type_gauge)

        housing_weight = calc_housing_weight(
            max_r, vol.volute_width_in, wall_t,
        )
        stiffeners = calc_stiffener_count(max_r, wall_t)

        housing = HousingStructure(
            wall_thickness_in=wall_t,
            amca_class=amca_class,
            material="A36 Carbon Steel",
            housing_weight_lb=housing_weight,
            flange_thickness_in=wall_t * 2.0,
            stiffener_count=stiffeners,
        )

        # --- Bolt patterns ---
        # Inlet: circular opening at eye
        inlet_perimeter = math.pi * tip_d  # Approximate inlet = impeller diameter
        inlet_load = W_impeller + housing_weight * 0.3  # Portion of weight + vibration
        inlet_bolts = calc_bolt_pattern(inlet_load, inlet_perimeter)

        # Discharge: rectangular opening
        dw = vol.discharge.width_in
        dh = vol.discharge.height_in
        discharge_perimeter = 2.0 * (dw + dh)
        discharge_load = W_impeller + housing_weight * 0.3
        discharge_bolts = calc_bolt_pattern(discharge_load, discharge_perimeter)

        # --- Base ---
        base_length = bearing_span + overhang + 12.0  # Extra for motor mount
        base_width = max(2.0 * max_r, 24.0)  # At least as wide as housing
        base_height = max(6.0, tip_d * 0.15)  # Min 6" pedestal
        base_weight = base_length * base_width * base_height * 0.02  # Rough frame estimate

        total_weight = W_impeller + shaft_weight + housing_weight + base_weight

        base = BaseDesign(
            length_in=base_length,
            width_in=base_width,
            height_in=base_height,
            weight_lb=base_weight,
            total_fan_weight_lb=total_weight,
        )

        result = FanStructuralResult(
            shaft=shaft,
            bearings=bearings,
            housing=housing,
            inlet_bolts=inlet_bolts,
            discharge_bolts=discharge_bolts,
            base=base,
            impeller_weight_lb=W_impeller,
            volute=vol,
        )

        return {
            'parts': {},
            'transforms': {},
            'anchors': {},
            'metadata': {
                'structural': result,
                'shaft_diameter_in': shaft_d,
                'shaft_length_in': shaft_length,
                'shaft_safety_factor': sf,
                'critical_speed_rpm': n_crit,
                'critical_speed_margin': crit_margin,
                'impeller_weight_lb': W_impeller,
                'housing_weight_lb': housing_weight,
                'total_weight_lb': total_weight,
                'amca_class': amca_class,
                'wall_thickness_in': wall_t,
                'bearing_dynamic_rating_lbf': C_required,
                'bearing_l10_hours': l10,
                'base_length_in': base_length,
                'base_width_in': base_width,
            },
        }
