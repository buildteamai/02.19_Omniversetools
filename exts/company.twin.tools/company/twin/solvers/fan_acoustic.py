"""
Fan Acoustic Solver — Step 5 of 7 in the physics-first fan engineering system.

Predicts sound power levels (Lw) in octave bands using AMCA 300/301 methods
and empirical correlations. Consumes FanStructuralResult (which chains all
upstream data). No geometry — pure acoustics math.

References:
    - AMCA 300-14: Reverberant Room Method for Sound Testing of Fans
    - AMCA 301-14: Methods for Calculating Fan Sound Ratings
    - Graham (1972): Specific-speed Kw correlation
    - Bleier, "Fan Handbook", Ch. 10 (sound)
    - ASHRAE Handbook — HVAC Systems and Equipment, Ch. 48 (sound)
    - Madison (1949): BPF analysis
    - IEC 61672: A-weighting
    - ISO 266: Preferred octave bands
    - ISO 3740: Reference sound power
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple

from .base_solver import BaseSolver
from .fan_classifier import FanType, FanClassification
from .fan_structural import FanStructuralResult


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPEED_OF_SOUND_FTS = 1128.0       # Speed of sound in air at 68°F (ft/s)
REF_POWER_WATTS = 1e-12           # ISO 3740 reference sound power (W)

# ISO 266 preferred octave band center frequencies (Hz)
OCTAVE_BANDS = [63, 125, 250, 500, 1000, 2000, 4000, 8000]

# IEC 61672 A-weighting corrections (dB) at each octave band
A_WEIGHTING = [-26.2, -16.1, -8.6, -3.2, 0.0, 1.2, 1.0, -1.1]

# Graham (1972) base specific sound power level (Kw) by fan type
KW_BASE: Dict[FanType, float] = {
    FanType.BACKWARD_INCLINED: 36.0,
    FanType.BACKWARD_CURVED:   38.0,
    FanType.FORWARD_CURVED:    42.0,
    FanType.RADIAL_BLADE:      50.0,
}

# AMCA 301 Table 1 — Kw corrections per octave band (dB below overall)
# Applied as deltas: Lw_band = Lw_overall + correction
KW_CORRECTIONS: Dict[FanType, List[float]] = {
    FanType.BACKWARD_INCLINED: [-2, -5, -8, -11, -14, -17, -20, -24],
    FanType.BACKWARD_CURVED:   [-2, -5, -8, -11, -14, -17, -20, -24],
    FanType.FORWARD_CURVED:    [-1, -3, -6,  -8, -11, -14, -17, -21],
    FanType.RADIAL_BLADE:      [-5, -2, -5,  -8, -11, -14, -17, -21],
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class OctaveBandSpectrum:
    """Sound power spectrum in octave bands."""
    center_frequencies: List[int]       # 8 octave band center freqs (Hz)
    lw_db: List[float]                  # Sound power level per band (dB re 1e-12 W)
    lw_a_db: List[float]               # A-weighted sound power per band (dBA)
    overall_lw_db: float                # Overall (log-sum) sound power (dB)
    overall_lw_a_db: float              # Overall A-weighted sound power (dBA)


@dataclass
class ToneInfo:
    """Blade passing frequency and tone analysis."""
    blade_passing_freq_hz: float        # BPF = Z × N / 60
    bpf_harmonic_2_hz: float            # 2nd harmonic of BPF
    bpf_octave_band: int                # Octave band containing BPF (Hz)
    tone_penalty_db: float              # Discrete tone penalty added to BPF band


@dataclass
class NoiseSourceBreakdown:
    """Breakdown of noise sources."""
    broadband_lw_db: float              # Broadband (aerodynamic) noise
    discrete_tone_lw_db: float          # BPF discrete tone contribution
    motor_lw_db: float                  # Motor noise estimate
    total_lw_db: float                  # Total (log-sum of all sources)


@dataclass
class FanAcousticResult:
    """Output contract — passed to Step 6 (geometry) and downstream."""
    spectrum: OctaveBandSpectrum
    tones: ToneInfo
    breakdown: NoiseSourceBreakdown
    tip_mach: float                     # Tip Mach number
    specific_sound_power: float         # Kw (dB)
    sones: float                        # AMCA sone estimate
    structural: FanStructuralResult     # Echo upstream chain


# ---------------------------------------------------------------------------
# Pure Math Functions
# ---------------------------------------------------------------------------

def calc_tip_mach(tip_speed_fts: float) -> float:
    """
    Tip Mach number.

    Ma = V_tip / c

    Ref: Bleier §10.2
    """
    if tip_speed_fts < 0:
        raise ValueError(f"Tip speed must be non-negative, got {tip_speed_fts}")
    return tip_speed_fts / SPEED_OF_SOUND_FTS


def calc_blade_passing_freq(num_blades: int, rpm: float) -> float:
    """
    Blade passing frequency.

    BPF = Z × N / 60  (Hz)

    Where Z = number of blades, N = rotational speed (RPM).
    Ref: Madison 1949
    """
    if num_blades <= 0:
        raise ValueError(f"Number of blades must be positive, got {num_blades}")
    if rpm <= 0:
        raise ValueError(f"RPM must be positive, got {rpm}")
    return num_blades * rpm / 60.0


def find_octave_band(freq_hz: float) -> int:
    """
    Find the octave band center frequency that contains the given frequency.

    Each octave band spans from f_c / √2 to f_c × √2.
    Ref: ISO 266
    """
    if freq_hz <= 0:
        raise ValueError(f"Frequency must be positive, got {freq_hz}")
    sqrt2 = math.sqrt(2.0)
    for fc in OCTAVE_BANDS:
        if fc / sqrt2 <= freq_hz < fc * sqrt2:
            return fc
    # If above 8 kHz band, assign to 8 kHz
    if freq_hz >= OCTAVE_BANDS[-1] / sqrt2:
        return OCTAVE_BANDS[-1]
    # If below 63 Hz band, assign to 63 Hz
    return OCTAVE_BANDS[0]


def calc_specific_sound_power(lw_db: float, cfm: float, dp_inwg: float) -> float:
    """
    Specific sound power level.

    Kw = Lw − 10·log₁₀(CFM × in.WG)

    Ref: AMCA 301 §7
    """
    if cfm <= 0 or dp_inwg <= 0:
        raise ValueError(f"CFM ({cfm}) and pressure ({dp_inwg}) must be positive")
    return lw_db - 10.0 * math.log10(cfm * dp_inwg)


def calc_overall_lw(cfm: float, dp_inwg: float, fan_type: FanType) -> float:
    """
    Overall sound power level from specific sound power.

    Lw = Kw + 10·log₁₀(CFM × in.WG)

    Ref: Graham 1972, AMCA 301
    """
    if cfm <= 0 or dp_inwg <= 0:
        raise ValueError(f"CFM ({cfm}) and pressure ({dp_inwg}) must be positive")
    kw = KW_BASE.get(fan_type)
    if kw is None:
        raise ValueError(f"Unknown fan type: {fan_type}")
    return kw + 10.0 * math.log10(cfm * dp_inwg)


def apply_kw_corrections(overall_lw: float, fan_type: FanType) -> List[float]:
    """
    Distribute overall Lw into 8 octave bands using Kw corrections.

    Lw_band(i) = Lw_overall + correction(i)

    Corrections are negative dB values (bands are quieter than overall).
    Ref: AMCA 301 Table 1
    """
    corrections = KW_CORRECTIONS.get(fan_type)
    if corrections is None:
        raise ValueError(f"Unknown fan type: {fan_type}")
    return [overall_lw + c for c in corrections]


def calc_bpf_tone_penalty(num_blades: int, tip_mach: float,
                          fan_type: FanType) -> float:
    """
    Discrete tone penalty at blade passing frequency.

    Higher tip Mach → stronger BPF tone. Radial blades produce the
    strongest BPF tones; backward-curved the weakest.

    Penalty range: 2–10 dB.
    Ref: Bleier Fig. 10-2
    """
    # Base penalty by fan type
    base_penalty = {
        FanType.BACKWARD_CURVED:   3.0,
        FanType.BACKWARD_INCLINED: 4.0,
        FanType.FORWARD_CURVED:    5.0,
        FanType.RADIAL_BLADE:      7.0,
    }
    base = base_penalty.get(fan_type, 5.0)

    # Mach number amplification: +3 dB per 0.1 Ma above 0.2
    mach_bonus = max(0.0, (tip_mach - 0.2) / 0.1) * 3.0

    # Blade count effect: fewer blades → stronger individual wakes
    blade_factor = 1.0
    if num_blades < 8:
        blade_factor = 1.5
    elif num_blades > 16:
        blade_factor = 0.7

    penalty = base * blade_factor + mach_bonus
    # Clamp to physical range
    return max(2.0, min(penalty, 10.0))


def apply_a_weighting(lw_per_band: List[float]) -> List[float]:
    """
    Apply A-weighting to octave band sound power levels.

    LwA(i) = Lw(i) + A(i)

    Ref: IEC 61672
    """
    if len(lw_per_band) != 8:
        raise ValueError(f"Expected 8 octave bands, got {len(lw_per_band)}")
    return [lw + a for lw, a in zip(lw_per_band, A_WEIGHTING)]


def log_sum_db(levels: List[float]) -> float:
    """
    Logarithmic sum of decibel levels.

    L_total = 10·log₁₀(Σ 10^(Li/10))

    Fundamental acoustic power addition.
    """
    if not levels:
        raise ValueError("Cannot sum empty list of levels")
    total = sum(10.0 ** (L / 10.0) for L in levels)
    if total <= 0:
        return -999.0
    return 10.0 * math.log10(total)


def calc_motor_noise(hp: float) -> float:
    """
    Estimate motor sound power level.

    Lw ≈ 20·log₁₀(HP) + 90  (dB)

    Ref: ASHRAE Handbook Ch. 48, Table 6
    """
    if hp <= 0:
        raise ValueError(f"HP must be positive, got {hp}")
    return 20.0 * math.log10(hp) + 90.0


def estimate_sones(lw_a_per_band: List[float]) -> float:
    """
    Simplified AMCA sone estimate from A-weighted octave band levels.

    Uses the loudest-band method:
        S = S_max + 0.3 × (Σ S_i − S_max)

    Where S_i = 2^((LwA_i − 40) / 10) for each band.

    Ref: AMCA 301 Annex D (simplified)
    """
    if len(lw_a_per_band) != 8:
        raise ValueError(f"Expected 8 octave bands, got {len(lw_a_per_band)}")

    sones_per_band = []
    for lwa in lw_a_per_band:
        if lwa <= 40.0:
            sones_per_band.append(0.0)
        else:
            sones_per_band.append(2.0 ** ((lwa - 40.0) / 10.0))

    if not any(s > 0 for s in sones_per_band):
        return 0.0

    s_max = max(sones_per_band)
    s_sum = sum(sones_per_band)
    return s_max + 0.3 * (s_sum - s_max)


# ---------------------------------------------------------------------------
# Solver Class
# ---------------------------------------------------------------------------

class FanAcousticSolver(BaseSolver):
    """
    Step 5: Fan Acoustic Solver.

    Takes a FanStructuralResult (from Step 4) and predicts sound power
    levels in octave bands using AMCA 300/301 methods.

    Inputs dict:
        'structural': FanStructuralResult   (required)

    Returns standard solver dict with:
        parts: {}  (no geometry at Step 5)
        metadata.acoustic: FanAcousticResult dataclass
    """

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        struct = inputs.get('structural')
        if struct is None:
            raise ValueError("Missing 'structural' in inputs")
        if not isinstance(struct, FanStructuralResult):
            raise ValueError("'structural' must be a FanStructuralResult instance")
        return True

    def solve(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_inputs(inputs)

        struct: FanStructuralResult = inputs['structural']
        vol = struct.volute
        aero = vol.aero
        cls = aero.classification
        fan_type = cls.fan_type
        dp = cls.design_point
        cfm, inwg = dp.to_us()

        # --- Key values from upstream ---
        rpm = aero.rpm
        hp = cls.shaft_power_hp
        tip_speed = cls.tip_speed_fts
        num_blades = aero.blade.num_blades

        # --- Tip Mach ---
        tip_mach = calc_tip_mach(tip_speed)

        # --- Overall sound power ---
        overall_lw = calc_overall_lw(cfm, inwg, fan_type)

        # --- Distribute to octave bands ---
        lw_bands = apply_kw_corrections(overall_lw, fan_type)

        # --- BPF tone analysis ---
        bpf = calc_blade_passing_freq(num_blades, rpm)
        bpf_band = find_octave_band(bpf)
        tone_penalty = calc_bpf_tone_penalty(num_blades, tip_mach, fan_type)

        # Add tone penalty to the BPF octave band
        bpf_band_idx = OCTAVE_BANDS.index(bpf_band)
        lw_bands_with_tone = list(lw_bands)
        lw_bands_with_tone[bpf_band_idx] = log_sum_db([
            lw_bands[bpf_band_idx],
            lw_bands[bpf_band_idx] + tone_penalty,
        ])

        # --- Motor noise (added to all bands equally) ---
        motor_lw = calc_motor_noise(hp)
        # Motor noise distributed: subtract 10·log₁₀(8) from overall
        motor_per_band = motor_lw - 10.0 * math.log10(8.0)

        # Combine broadband + tone + motor for each band
        final_bands = []
        for i in range(8):
            combined = log_sum_db([lw_bands_with_tone[i], motor_per_band])
            final_bands.append(combined)

        # --- A-weighting ---
        lw_a_bands = apply_a_weighting(final_bands)

        # --- Overall levels ---
        overall_final = log_sum_db(final_bands)
        overall_a = log_sum_db(lw_a_bands)

        # --- Specific sound power ---
        kw = calc_specific_sound_power(overall_final, cfm, inwg)

        # --- Sones ---
        sones = estimate_sones(lw_a_bands)

        # --- Broadband (without tone penalty) overall ---
        broadband_bands_with_motor = []
        for i in range(8):
            combined = log_sum_db([lw_bands[i], motor_per_band])
            broadband_bands_with_motor.append(combined)
        broadband_overall = log_sum_db(broadband_bands_with_motor)

        # Discrete tone contribution: energy in BPF band tone penalty only
        discrete_tone_lw = lw_bands[bpf_band_idx] + tone_penalty

        # --- Build results ---
        spectrum = OctaveBandSpectrum(
            center_frequencies=list(OCTAVE_BANDS),
            lw_db=final_bands,
            lw_a_db=lw_a_bands,
            overall_lw_db=overall_final,
            overall_lw_a_db=overall_a,
        )

        tones = ToneInfo(
            blade_passing_freq_hz=bpf,
            bpf_harmonic_2_hz=bpf * 2.0,
            bpf_octave_band=bpf_band,
            tone_penalty_db=tone_penalty,
        )

        breakdown = NoiseSourceBreakdown(
            broadband_lw_db=broadband_overall,
            discrete_tone_lw_db=discrete_tone_lw,
            motor_lw_db=motor_lw,
            total_lw_db=overall_final,
        )

        result = FanAcousticResult(
            spectrum=spectrum,
            tones=tones,
            breakdown=breakdown,
            tip_mach=tip_mach,
            specific_sound_power=kw,
            sones=sones,
            structural=struct,
        )

        return {
            'parts': {},
            'transforms': {},
            'anchors': {},
            'metadata': {
                'acoustic': result,
                'overall_lw_db': overall_final,
                'overall_lw_a_db': overall_a,
                'tip_mach': tip_mach,
                'specific_sound_power_kw': kw,
                'sones': sones,
                'bpf_hz': bpf,
                'bpf_octave_band': bpf_band,
                'tone_penalty_db': tone_penalty,
                'motor_lw_db': motor_lw,
            },
        }
