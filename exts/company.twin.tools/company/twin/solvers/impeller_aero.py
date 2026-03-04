"""
Impeller Aerodynamics Solver — Step 2 of 7 in the physics-first fan engineering system.

Consumes the FanClassification from Step 1 and derives velocity triangles,
blade angles (β₁, β₂), blade count, and passage geometry from first principles.
No geometry is produced here; this solver outputs a typed dataclass that
downstream solvers (volute, scroll, structural) consume.

Velocity triangle convention (Euler turbomachinery):
    U  = blade tip speed (tangential)
    Cm = meridional (axial/radial) velocity component
    Cu = whirl (tangential) velocity component
    W  = relative velocity (blade frame)
    C  = absolute velocity (lab frame)

    Subscripts: 1 = inlet (eye), 2 = outlet (tip)

References:
    - Bleier, "Fan Handbook", McGraw-Hill, Ch. 3–5
    - Eck, "Fans", Pergamon Press 1973, Ch. 4
    - Osborne, "Fans", Pergamon 1977
    - ASHRAE Handbook — HVAC Systems and Equipment, Ch. 20
    - Dixon & Hall, "Fluid Mechanics and Thermodynamics of Turbomachinery", 7th ed.
    - Pfleiderer, "Die Kreiselpumpen", Springer (slip factor)
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional, List

from .base_solver import BaseSolver
from .fan_classifier import (
    FanType, BladeAngleClass, FanClassification, FanDesignPoint,
    INWG_TO_PA, INWG_TO_PSF, M3S_TO_CFM, HP_TO_KW, AIR_HP_CONST,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RHO_AIR_STD = 0.075        # lb/ft³ at standard conditions (70°F, sea level)
RHO_AIR_SI = 1.2           # kg/m³ at standard conditions
G_FT = 32.174              # ft/s² gravitational acceleration
HUB_RATIO_DEFAULT = {       # D_hub / D_tip ratio by fan type (Bleier Ch. 4)
    FanType.RADIAL_BLADE:      0.50,
    FanType.BACKWARD_INCLINED: 0.55,
    FanType.BACKWARD_CURVED:   0.60,
    FanType.FORWARD_CURVED:    0.70,
}
BLADE_COUNT_DEFAULT = {     # Typical blade count by fan type (Bleier Table 4-1)
    FanType.RADIAL_BLADE:      8,
    FanType.BACKWARD_INCLINED: 12,
    FanType.BACKWARD_CURVED:   10,
    FanType.FORWARD_CURVED:    36,
}
# Beta2 design targets in degrees (blade exit angle, measured from tangential)
BETA2_TARGETS = {
    FanType.RADIAL_BLADE:      90.0,
    FanType.BACKWARD_INCLINED: 60.0,
    FanType.BACKWARD_CURVED:   45.0,
    FanType.FORWARD_CURVED:    135.0,
}
# Beta1 nominal targets (blade inlet angle)
BETA1_NOMINAL = {
    FanType.RADIAL_BLADE:      30.0,
    FanType.BACKWARD_INCLINED: 25.0,
    FanType.BACKWARD_CURVED:   30.0,
    FanType.FORWARD_CURVED:    35.0,
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VelocityTriangle:
    """Velocity components at a single station (inlet or outlet)."""
    U: float        # Blade speed (tangential), ft/s
    Cm: float       # Meridional velocity, ft/s
    Cu: float       # Whirl velocity, ft/s
    W: float        # Relative velocity (blade frame), ft/s
    C: float        # Absolute velocity (lab frame), ft/s
    beta: float     # Blade angle (from tangential), degrees
    alpha: float    # Absolute flow angle (from tangential), degrees


@dataclass
class BladeGeometry:
    """Blade dimensional parameters."""
    num_blades: int
    beta1_metal_deg: float    # Inlet blade metal angle (design target)
    beta2_metal_deg: float    # Exit blade metal angle (design target)
    beta1_flow_deg: float     # Inlet flow angle (from velocity triangle)
    beta2_flow_deg: float     # Exit flow angle (from velocity triangle)
    incidence_deg: float      # β1_metal − β1_flow (blade leading-edge offset)
    deviation_deg: float      # β2_metal − β2_flow (blade trailing-edge offset)
    chord_in: float           # Blade chord length (inches)
    pitch_in: float           # Blade pitch at tip (inches)
    solidity: float           # chord / pitch ratio
    camber_deg: float         # β2_metal − β1_metal (total blade turning)
    stagger_deg: float        # (β1_metal + β2_metal) / 2 (blade setting angle)


@dataclass
class PassageGeometry:
    """Impeller passage dimensions."""
    hub_diameter_in: float
    tip_diameter_in: float
    hub_ratio: float          # D_hub / D_tip
    inlet_width_in: float     # b₁ — axial width at eye
    outlet_width_in: float    # b₂ — radial width at tip
    passage_area_in2: float   # Exit passage area


@dataclass
class ImpellerAeroResult:
    """Output contract — passed to Step 3 (volute/scroll) and Step 4 (structural)."""
    inlet_triangle: VelocityTriangle
    outlet_triangle: VelocityTriangle
    blade: BladeGeometry
    passage: PassageGeometry
    slip_factor: float        # Stodola/Pfleiderer slip correction
    de_haller_ratio: float    # W₂/W₁ — diffusion check (>0.72 safe)
    flow_coefficient: float   # φ = Cm₂/U₂
    work_coefficient: float   # ψ = ΔCu·U / U²
    reaction_degree: float    # R = 1 − Cu₂/(2·U₂)
    rpm: float                # Operating RPM used
    classification: FanClassification  # Echo Step 1 for traceability


# ---------------------------------------------------------------------------
# Pure Math Functions
# ---------------------------------------------------------------------------

def calc_blade_speed(diameter_in: float, rpm: float) -> float:
    """U = π·D·RPM / 60 (ft/s). D in inches, converted internally."""
    d_ft = diameter_in / 12.0
    return math.pi * d_ft * rpm / 60.0


def calc_meridional_velocity(cfm: float, area_ft2: float) -> float:
    """Cm = Q / A (ft/s). Q in ft³/s from CFM."""
    q_cfs = cfm / 60.0
    if area_ft2 <= 0:
        raise ValueError(f"Flow area must be positive, got {area_ft2}")
    return q_cfs / area_ft2


def calc_outlet_area(tip_diameter_in: float, outlet_width_in: float) -> float:
    """Annular exit area A₂ = π·D₂·b₂ (ft²). Inputs in inches."""
    d_ft = tip_diameter_in / 12.0
    b_ft = outlet_width_in / 12.0
    return math.pi * d_ft * b_ft


def calc_inlet_area(tip_diameter_in: float, hub_diameter_in: float) -> float:
    """Eye annular area A₁ = π/4·(D_tip² − D_hub²) (ft²). Inputs in inches."""
    dt_ft = tip_diameter_in / 12.0
    dh_ft = hub_diameter_in / 12.0
    return math.pi / 4.0 * (dt_ft ** 2 - dh_ft ** 2)


def calc_whirl_velocity(dp_inwg: float, U2: float, eta: float) -> float:
    """
    Cu₂ from Euler equation: ΔP = ρ·U₂·Cu₂·η
    Rearranged: Cu₂ = ΔP / (ρ·U₂·η)

    ΔP in lbf/ft², U₂ in ft/s, ρ in slug/ft³.
    """
    dp_psf = dp_inwg * INWG_TO_PSF
    # ρ in slugs/ft³ = lb/ft³ / g
    rho_slug = RHO_AIR_STD / G_FT
    if U2 <= 0 or eta <= 0:
        raise ValueError(f"U2 and eta must be positive: U2={U2}, eta={eta}")
    return dp_psf / (rho_slug * U2 * eta)


def calc_slip_factor(num_blades: int, beta2_deg: float) -> float:
    """
    Stodola slip factor: σ = 1 − (π·sin(β₂)) / Z
    Where Z = number of blades, β₂ in radians.

    Ref: Pfleiderer, Dixon & Hall Ch. 7
    """
    beta2_rad = math.radians(beta2_deg)
    z = max(num_blades, 1)
    sigma = 1.0 - (math.pi * math.sin(beta2_rad)) / z
    return max(sigma, 0.5)  # Clamp — below 0.5 is unphysical


def calc_blade_angle_from_triangle(Cm: float, U_minus_Cu: float) -> float:
    """
    β = atan(Cm / (U − Cu))  — measured from tangential direction.
    Returns degrees.
    """
    if abs(U_minus_Cu) < 1e-9:
        return 90.0
    return math.degrees(math.atan2(Cm, U_minus_Cu))


def calc_relative_velocity(Cm: float, U_minus_Cu: float) -> float:
    """W = √(Cm² + (U−Cu)²)"""
    return math.sqrt(Cm ** 2 + U_minus_Cu ** 2)


def calc_absolute_velocity(Cm: float, Cu: float) -> float:
    """C = √(Cm² + Cu²)"""
    return math.sqrt(Cm ** 2 + Cu ** 2)


def calc_absolute_angle(Cm: float, Cu: float) -> float:
    """α = atan(Cm / Cu) — angle from tangential. Returns degrees."""
    if abs(Cu) < 1e-9:
        return 90.0
    return math.degrees(math.atan2(Cm, Cu))


def calc_de_haller(W1: float, W2: float) -> float:
    """De Haller ratio W₂/W₁. Should be > 0.72 for safe diffusion."""
    if W1 <= 0:
        return 0.0
    return W2 / W1


def calc_outlet_width(cfm: float, tip_diameter_in: float,
                      Cm2: float) -> float:
    """
    b₂ = Q / (π·D₂·Cm₂) in inches.
    Q in ft³/s, D₂ in ft, Cm₂ in ft/s → b₂ in ft → inches.
    """
    q_cfs = cfm / 60.0
    d_ft = tip_diameter_in / 12.0
    if Cm2 <= 0:
        raise ValueError(f"Cm2 must be positive, got {Cm2}")
    b_ft = q_cfs / (math.pi * d_ft * Cm2)
    return b_ft * 12.0


def calc_blade_chord(tip_diameter_in: float, hub_diameter_in: float,
                     num_blades: int, solidity_target: float = 1.0) -> float:
    """
    Chord from solidity: σ = c/s, where s = pitch = π·D_mean / Z.
    c = σ · π · D_mean / Z.  Returns inches.
    """
    d_mean = (tip_diameter_in + hub_diameter_in) / 2.0
    z = max(num_blades, 1)
    pitch = math.pi * d_mean / z
    chord = solidity_target * pitch
    return chord


def estimate_solidity(fan_type: FanType) -> float:
    """Target solidity by fan type. Ref: Bleier Ch. 4, Eck Ch. 5."""
    return {
        FanType.RADIAL_BLADE:      0.8,
        FanType.BACKWARD_INCLINED: 1.2,
        FanType.BACKWARD_CURVED:   1.0,
        FanType.FORWARD_CURVED:    0.6,
    }.get(fan_type, 1.0)


def estimate_outlet_width_ratio(fan_type: FanType) -> float:
    """b₂/D₂ ratio by fan type. Ref: Bleier Table 4-2."""
    return {
        FanType.RADIAL_BLADE:      0.20,
        FanType.BACKWARD_INCLINED: 0.15,
        FanType.BACKWARD_CURVED:   0.12,
        FanType.FORWARD_CURVED:    0.40,
    }.get(fan_type, 0.15)


# ---------------------------------------------------------------------------
# Solver Class
# ---------------------------------------------------------------------------

class ImpellerAeroSolver(BaseSolver):
    """
    Step 2: Impeller Aerodynamics Solver.

    Takes a FanClassification (from Step 1) and derives velocity triangles,
    blade angles, blade count, and passage geometry.

    Inputs dict:
        'classification': FanClassification  (required)
        'num_blades': int                    (optional override)
        'hub_ratio': float                   (optional override)
        'beta2_deg': float                   (optional override)

    Returns standard solver dict with:
        parts: {}  (no geometry at Step 2)
        metadata.aero: ImpellerAeroResult dataclass
    """

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        cls = inputs.get('classification')
        if cls is None:
            raise ValueError("Missing 'classification' in inputs")
        if not isinstance(cls, FanClassification):
            raise ValueError("'classification' must be a FanClassification instance")
        if cls.impeller_diameter_in <= 0:
            raise ValueError(
                f"Impeller diameter must be positive, got {cls.impeller_diameter_in}"
            )
        return True

    def solve(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_inputs(inputs)

        cls: FanClassification = inputs['classification']
        dp = cls.design_point
        cfm, inwg = dp.to_us()
        eta = cls.efficiency.total

        # --- Operating RPM ---
        # Use midpoint of recommended range from Step 1
        rpm_lo, rpm_hi = cls.recommended_rpm_range
        rpm = (rpm_lo + rpm_hi) / 2.0

        # Allow override
        if dp.rpm is not None:
            rpm = dp.rpm

        # --- Impeller dimensions ---
        fan_type = cls.fan_type
        tip_d = cls.impeller_diameter_in
        hub_ratio = inputs.get('hub_ratio', HUB_RATIO_DEFAULT.get(fan_type, 0.55))
        hub_d = tip_d * hub_ratio

        # Outlet width
        b2_ratio = estimate_outlet_width_ratio(fan_type)
        outlet_width = tip_d * b2_ratio

        # --- Blade speed ---
        U2 = calc_blade_speed(tip_d, rpm)
        U1 = calc_blade_speed(hub_d, rpm)
        # Use mean eye diameter for inlet blade speed
        eye_mean_d = (tip_d + hub_d) / 2.0
        U1_mean = calc_blade_speed(eye_mean_d, rpm)

        # --- Flow areas ---
        inlet_area = calc_inlet_area(tip_d, hub_d)
        outlet_area = calc_outlet_area(tip_d, outlet_width)

        # --- Meridional velocities ---
        Cm1 = calc_meridional_velocity(cfm, inlet_area)
        Cm2 = calc_meridional_velocity(cfm, outlet_area)

        # Recalculate outlet width to be consistent with Cm2
        # (use the initial estimate, then refine)
        outlet_width = calc_outlet_width(cfm, tip_d, Cm2)

        # --- Outlet whirl velocity (from Euler) ---
        Cu2_ideal = calc_whirl_velocity(inwg, U2, eta)

        # --- Slip correction ---
        num_blades = inputs.get(
            'num_blades',
            BLADE_COUNT_DEFAULT.get(fan_type, 12)
        )
        beta2_target = inputs.get(
            'beta2_deg',
            BETA2_TARGETS.get(fan_type, 60.0)
        )
        slip = calc_slip_factor(num_blades, beta2_target)
        Cu2 = Cu2_ideal / slip  # Actual Cu₂ needed to overcome slip

        # Clamp Cu2 to physical limits (can't exceed blade speed)
        if fan_type != FanType.FORWARD_CURVED:
            Cu2 = min(Cu2, U2 * 0.95)
        # For forward curved, Cu2 can exceed U2

        # --- Inlet triangle (assume no pre-swirl: Cu₁ = 0) ---
        Cu1 = 0.0
        W1 = calc_relative_velocity(Cm1, U1_mean - Cu1)
        C1 = calc_absolute_velocity(Cm1, Cu1)
        beta1_calc = calc_blade_angle_from_triangle(Cm1, U1_mean - Cu1)
        alpha1 = 90.0  # No pre-swirl → purely axial entry

        inlet_triangle = VelocityTriangle(
            U=U1_mean, Cm=Cm1, Cu=Cu1,
            W=W1, C=C1,
            beta=beta1_calc, alpha=alpha1,
        )

        # --- Outlet triangle ---
        W2 = calc_relative_velocity(Cm2, U2 - Cu2)
        C2 = calc_absolute_velocity(Cm2, Cu2)
        beta2_calc = calc_blade_angle_from_triangle(Cm2, U2 - Cu2)
        alpha2 = calc_absolute_angle(Cm2, Cu2)

        outlet_triangle = VelocityTriangle(
            U=U2, Cm=Cm2, Cu=Cu2,
            W=W2, C=C2,
            beta=beta2_calc, alpha=alpha2,
        )

        # --- Blade geometry ---
        # Metal angles are design targets; flow angles come from velocity triangles
        beta1_metal = inputs.get(
            'beta1_deg',
            BETA1_NOMINAL.get(fan_type, 30.0)
        )
        beta2_metal = beta2_target  # Already resolved from inputs or defaults

        solidity_target = estimate_solidity(fan_type)
        chord = calc_blade_chord(tip_d, hub_d, num_blades, solidity_target)
        pitch = math.pi * (tip_d + hub_d) / 2.0 / max(num_blades, 1)
        solidity_actual = chord / pitch if pitch > 0 else 1.0
        camber = beta2_metal - beta1_metal
        stagger = (beta1_metal + beta2_metal) / 2.0

        blade = BladeGeometry(
            num_blades=num_blades,
            beta1_metal_deg=beta1_metal,
            beta2_metal_deg=beta2_metal,
            beta1_flow_deg=beta1_calc,
            beta2_flow_deg=beta2_calc,
            incidence_deg=beta1_metal - beta1_calc,
            deviation_deg=beta2_metal - beta2_calc,
            chord_in=chord,
            pitch_in=pitch,
            solidity=solidity_actual,
            camber_deg=camber,
            stagger_deg=stagger,
        )

        # --- Passage geometry ---
        inlet_width = tip_d * (1 - hub_ratio) / 2.0  # Approximate axial eye depth
        passage_area = outlet_area * 144.0  # ft² → in²

        passage = PassageGeometry(
            hub_diameter_in=hub_d,
            tip_diameter_in=tip_d,
            hub_ratio=hub_ratio,
            inlet_width_in=inlet_width,
            outlet_width_in=outlet_width,
            passage_area_in2=passage_area,
        )

        # --- Performance checks ---
        de_haller = calc_de_haller(W1, W2)
        flow_coeff = Cm2 / U2 if U2 > 0 else 0.0
        work_coeff = (Cu2 * U2) / (U2 ** 2) if U2 > 0 else 0.0
        reaction = 1.0 - Cu2 / (2.0 * U2) if U2 > 0 else 0.5

        aero_result = ImpellerAeroResult(
            inlet_triangle=inlet_triangle,
            outlet_triangle=outlet_triangle,
            blade=blade,
            passage=passage,
            slip_factor=slip,
            de_haller_ratio=de_haller,
            flow_coefficient=flow_coeff,
            work_coefficient=work_coeff,
            reaction_degree=reaction,
            rpm=rpm,
            classification=cls,
        )

        return {
            'parts': {},
            'transforms': {},
            'anchors': {},
            'metadata': {
                'aero': aero_result,
                'rpm': rpm,
                'beta1_metal_deg': beta1_metal,
                'beta2_metal_deg': beta2_metal,
                'beta1_flow_deg': beta1_calc,
                'beta2_flow_deg': beta2_calc,
                'num_blades': num_blades,
                'hub_diameter_in': hub_d,
                'tip_diameter_in': tip_d,
                'outlet_width_in': outlet_width,
                'slip_factor': slip,
                'de_haller_ratio': de_haller,
                'flow_coefficient': flow_coeff,
                'work_coefficient': work_coeff,
                'reaction_degree': reaction,
                'inlet_Cm': Cm1,
                'outlet_Cm': Cm2,
                'outlet_Cu': Cu2,
                'blade_chord_in': chord,
                'blade_solidity': solidity_actual,
            },
        }
