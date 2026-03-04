"""
Volute / Scroll Solver — Step 3 of 7 in the physics-first fan engineering system.

Consumes the ImpellerAeroResult from Step 2 and derives the volute (scroll
housing) geometry from conservation of angular momentum. The volute collects
the swirling discharge from the impeller, converts kinetic energy to static
pressure, and directs flow to the discharge duct.

Design method: constant-angular-momentum (free-vortex) volute per
Stepanoff / Bleier / ASHRAE. The radius at each azimuthal station θ is
sized so that r·Vθ = constant.

No USD geometry is produced here; this solver outputs a typed dataclass
of cross-section dimensions at discrete azimuthal stations that downstream
geometry generators consume.

References:
    - Bleier, "Fan Handbook", McGraw-Hill, Ch. 6
    - Stepanoff, "Centrifugal and Axial Flow Pumps", Wiley, Ch. 7
    - Eck, "Fans", Pergamon Press 1973, Ch. 6
    - ASHRAE Handbook — HVAC Systems and Equipment, Ch. 20
    - Aungier, "Centrifugal Compressors", ASME Press, Ch. 8
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional, List

from .base_solver import BaseSolver
from .fan_classifier import FanType, FanClassification, INWG_TO_PSF
from .impeller_aero import (
    ImpellerAeroResult, VelocityTriangle, PassageGeometry,
    RHO_AIR_STD, G_FT,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_NUM_STATIONS = 8        # Azimuthal stations (every 45°)
CUTOFF_GAP_RATIO = 0.08        # Cutoff-to-impeller radial gap / D₂ (Bleier §6.3)
VOLUTE_CLEARANCE_RATIO = 0.05  # Radial clearance / D₂ between impeller tip and tongue
DISCHARGE_AREA_FACTOR = {       # A_discharge / A_360 area ratio by fan type
    FanType.RADIAL_BLADE:      1.10,   # Slightly oversize for pressure recovery
    FanType.BACKWARD_INCLINED: 1.05,
    FanType.BACKWARD_CURVED:   1.05,
    FanType.FORWARD_CURVED:    1.15,   # FC needs more diffusion
}
WIDTH_EXPANSION_RATIO = {       # Volute width / impeller outlet width (Bleier Table 6-1)
    FanType.RADIAL_BLADE:      1.6,
    FanType.BACKWARD_INCLINED: 1.5,
    FanType.BACKWARD_CURVED:   1.5,
    FanType.FORWARD_CURVED:    1.3,
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VoluteStation:
    """Cross-section at one azimuthal station."""
    theta_deg: float            # Azimuthal angle from tongue (0–360°)
    radius_in: float            # Outer radius of volute at this station
    width_in: float             # Axial width of the passage
    area_in2: float             # Cross-sectional area of the passage
    velocity_fts: float         # Mean velocity through this section


@dataclass
class VoluteTongue:
    """Cutoff / tongue geometry."""
    radius_in: float            # Tongue tip radius
    gap_in: float               # Radial gap between impeller tip and tongue
    angle_deg: float            # Tongue angle (from tangent line), typically 5–15°


@dataclass
class DischargeGeometry:
    """Rectangular discharge duct (outlet flange)."""
    width_in: float             # Horizontal dimension
    height_in: float            # Vertical dimension (radial direction)
    area_in2: float             # Discharge area
    velocity_fts: float         # Discharge velocity
    equivalent_diameter_in: float  # Hydraulic equivalent diameter


@dataclass
class VoluteResult:
    """Output contract — passed to Step 4 (structural) and geometry generators."""
    stations: List[VoluteStation]
    tongue: VoluteTongue
    discharge: DischargeGeometry
    max_radius_in: float        # Outermost volute radius (at θ=360°)
    min_radius_in: float        # Innermost volute radius (at tongue)
    volute_width_in: float      # Axial width of volute housing
    impeller_tip_radius_in: float  # For reference — impeller outer radius
    angular_momentum: float     # r·Vθ constant (ft²/s)
    pressure_recovery_coeff: float  # Cp estimate for volute diffusion
    aero: ImpellerAeroResult    # Echo Step 2 for traceability


# ---------------------------------------------------------------------------
# Pure Math Functions
# ---------------------------------------------------------------------------

def calc_angular_momentum(Cu2: float, tip_radius_ft: float) -> float:
    """
    K = r₂ · Cu₂  (ft²/s)

    The free-vortex constant: angular momentum is conserved in the volute.
    Ref: Stepanoff Ch. 7, Bleier §6.2
    """
    return tip_radius_ft * Cu2


def calc_volute_area_at_theta(theta_deg: float, cfm: float,
                              Cu2: float, tip_radius_ft: float) -> float:
    """
    A(θ) = (θ/360) · Q / Cu₂  — progressive area collection.

    At angle θ from the tongue, the volute has collected (θ/360) of the
    total impeller discharge. The mean tangential velocity is Cu₂ (at
    the impeller tip), so A = Q_collected / V.

    Q in ft³/s, Cu₂ in ft/s → A in ft².
    Ref: Bleier Eq. 6.1, Stepanoff Eq. 7.3
    """
    if Cu2 <= 0:
        raise ValueError(f"Cu₂ must be positive, got {Cu2}")
    q_cfs = cfm / 60.0
    fraction = theta_deg / 360.0
    return fraction * q_cfs / Cu2


def calc_volute_radius(area_ft2: float, width_ft: float,
                       tip_radius_ft: float) -> float:
    """
    Outer radius from rectangular cross-section assumption.

    A = width · (R_outer − R_tip)
    R_outer = R_tip + A / width

    All in feet.
    """
    if width_ft <= 0:
        raise ValueError(f"Volute width must be positive, got {width_ft}")
    radial_depth = area_ft2 / width_ft
    return tip_radius_ft + radial_depth


def calc_mean_velocity_at_station(cfm: float, theta_deg: float,
                                  area_ft2: float) -> float:
    """
    V = Q_collected / A  (ft/s)

    Q_collected = (θ/360) · Q_total
    """
    if area_ft2 <= 0:
        return 0.0
    q_cfs = cfm / 60.0
    q_collected = (theta_deg / 360.0) * q_cfs
    return q_collected / area_ft2


def calc_tongue_geometry(tip_diameter_in: float,
                         fan_type: FanType) -> VoluteTongue:
    """
    Tongue (cutoff) placement.

    Gap = CUTOFF_GAP_RATIO × D₂ (typically 5–10% of impeller diameter).
    Tongue angle: 5–15° depending on fan type.
    Ref: Bleier §6.3, ASHRAE Ch. 20
    """
    gap = tip_diameter_in * CUTOFF_GAP_RATIO
    tongue_radius = tip_diameter_in / 2.0 + gap

    tongue_angles = {
        FanType.RADIAL_BLADE:      10.0,
        FanType.BACKWARD_INCLINED: 7.0,
        FanType.BACKWARD_CURVED:   8.0,
        FanType.FORWARD_CURVED:    12.0,
    }
    angle = tongue_angles.get(fan_type, 8.0)

    return VoluteTongue(
        radius_in=tongue_radius,
        gap_in=gap,
        angle_deg=angle,
    )


def calc_discharge_geometry(area_360_ft2: float, volute_width_in: float,
                            cfm: float, fan_type: FanType) -> DischargeGeometry:
    """
    Discharge (outlet) duct sizing.

    Discharge area = A_360 × area_factor (slight oversize for diffusion).
    Width matches volute width; height derived from area.
    Ref: Bleier §6.5
    """
    factor = DISCHARGE_AREA_FACTOR.get(fan_type, 1.05)
    discharge_area_ft2 = area_360_ft2 * factor
    discharge_area_in2 = discharge_area_ft2 * 144.0

    width = volute_width_in
    height = discharge_area_in2 / width if width > 0 else 0.0

    q_cfs = cfm / 60.0
    velocity = q_cfs / discharge_area_ft2 if discharge_area_ft2 > 0 else 0.0

    # Hydraulic equivalent diameter: 4·A / P
    perimeter = 2.0 * (width + height)
    d_eq = 4.0 * discharge_area_in2 / perimeter if perimeter > 0 else 0.0

    return DischargeGeometry(
        width_in=width,
        height_in=height,
        area_in2=discharge_area_in2,
        velocity_fts=velocity,
        equivalent_diameter_in=d_eq,
    )


def estimate_pressure_recovery(C2: float, C_discharge: float) -> float:
    """
    Pressure recovery coefficient for the volute.

    Cp = (C₂² − C_discharge²) / C₂²
    Ideally 0.3–0.6 for a well-designed volute.
    Ref: Aungier Ch. 8, Eck §6.4
    """
    if C2 <= 0:
        return 0.0
    Cp = (C2 ** 2 - C_discharge ** 2) / (C2 ** 2)
    return max(Cp, 0.0)


# ---------------------------------------------------------------------------
# Solver Class
# ---------------------------------------------------------------------------

class VoluteSolver(BaseSolver):
    """
    Step 3: Volute / Scroll Housing Solver.

    Takes an ImpellerAeroResult (from Step 2) and derives the volute
    cross-section profile at discrete azimuthal stations using the
    constant-angular-momentum (free-vortex) method.

    Inputs dict:
        'aero': ImpellerAeroResult       (required)
        'num_stations': int              (optional, default 8)
        'width_expansion': float         (optional override for volute width ratio)

    Returns standard solver dict with:
        parts: {}  (no geometry at Step 3)
        metadata.volute: VoluteResult dataclass
    """

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        aero = inputs.get('aero')
        if aero is None:
            raise ValueError("Missing 'aero' in inputs")
        if not isinstance(aero, ImpellerAeroResult):
            raise ValueError("'aero' must be an ImpellerAeroResult instance")
        if aero.outlet_triangle.Cu <= 0:
            raise ValueError(
                f"Outlet whirl velocity Cu₂ must be positive, got "
                f"{aero.outlet_triangle.Cu}"
            )
        return True

    def solve(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_inputs(inputs)

        aero: ImpellerAeroResult = inputs['aero']
        cls = aero.classification
        fan_type = cls.fan_type
        dp = cls.design_point
        cfm, inwg = dp.to_us()

        # --- Key dimensions from Step 2 ---
        tip_d_in = aero.passage.tip_diameter_in
        tip_r_in = tip_d_in / 2.0
        tip_r_ft = tip_r_in / 12.0
        outlet_width_in = aero.passage.outlet_width_in
        Cu2 = aero.outlet_triangle.Cu
        C2 = aero.outlet_triangle.C

        # --- Volute width ---
        # Aerodynamic minimum from Bleier expansion ratio
        width_ratio = inputs.get(
            'width_expansion',
            WIDTH_EXPANSION_RATIO.get(fan_type, 1.5)
        )
        aero_width = outlet_width_in * width_ratio
        # Industrial fan housings are wider than the aerodynamic minimum
        # for structural integrity and impeller clearance. Floor at 50% of D₂.
        min_width = tip_d_in * 0.50
        volute_width_in = max(aero_width, min_width)
        volute_width_ft = volute_width_in / 12.0

        # --- Angular momentum constant ---
        K = calc_angular_momentum(Cu2, tip_r_ft)

        # --- Azimuthal stations ---
        num_stations = inputs.get('num_stations', DEFAULT_NUM_STATIONS)
        if num_stations < 4:
            num_stations = 4

        stations = []
        theta_step = 360.0 / num_stations

        for i in range(1, num_stations + 1):
            theta = i * theta_step

            area_ft2 = calc_volute_area_at_theta(theta, cfm, Cu2, tip_r_ft)
            radius_in = calc_volute_radius(area_ft2, volute_width_ft, tip_r_ft) * 12.0
            area_in2 = area_ft2 * 144.0
            velocity = calc_mean_velocity_at_station(cfm, theta, area_ft2)

            stations.append(VoluteStation(
                theta_deg=theta,
                radius_in=radius_in,
                width_in=volute_width_in,
                area_in2=area_in2,
                velocity_fts=velocity,
            ))

        # --- Tongue ---
        tongue = calc_tongue_geometry(tip_d_in, fan_type)

        # --- Discharge ---
        area_360_ft2 = calc_volute_area_at_theta(360, cfm, Cu2, tip_r_ft)
        discharge = calc_discharge_geometry(
            area_360_ft2, volute_width_in, cfm, fan_type,
        )

        # --- Pressure recovery ---
        Cp = estimate_pressure_recovery(C2, discharge.velocity_fts)

        # --- Envelope ---
        max_radius = stations[-1].radius_in if stations else tip_r_in
        min_radius = tongue.radius_in

        result = VoluteResult(
            stations=stations,
            tongue=tongue,
            discharge=discharge,
            max_radius_in=max_radius,
            min_radius_in=min_radius,
            volute_width_in=volute_width_in,
            impeller_tip_radius_in=tip_r_in,
            angular_momentum=K,
            pressure_recovery_coeff=Cp,
            aero=aero,
        )

        return {
            'parts': {},
            'transforms': {},
            'anchors': {},
            'metadata': {
                'volute': result,
                'max_radius_in': max_radius,
                'min_radius_in': min_radius,
                'volute_width_in': volute_width_in,
                'discharge_width_in': discharge.width_in,
                'discharge_height_in': discharge.height_in,
                'discharge_area_in2': discharge.area_in2,
                'discharge_velocity_fts': discharge.velocity_fts,
                'tongue_radius_in': tongue.radius_in,
                'tongue_gap_in': tongue.gap_in,
                'angular_momentum': K,
                'pressure_recovery_coeff': Cp,
                'num_stations': num_stations,
            },
        }
