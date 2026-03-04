"""
Tests for FanAcousticSolver — Step 5 of the fan engineering system.

No USD/Omniverse dependencies. Pure math + dataclasses only.
Run: cd exts/company.twin.tools && python -m pytest tests/test_fan_acoustic.py -v
"""

import math
import pytest

from company.twin.solvers.fan_classifier import (
    FanType, FanDesignPoint, FanClassification, FanClassificationSolver,
    UnitSystem,
)
from company.twin.solvers.impeller_aero import ImpellerAeroSolver
from company.twin.solvers.volute_solver import VoluteSolver
from company.twin.solvers.fan_structural import FanStructuralSolver, FanStructuralResult
from company.twin.solvers.fan_acoustic import (
    # Dataclasses
    OctaveBandSpectrum, ToneInfo, NoiseSourceBreakdown, FanAcousticResult,
    # Pure functions
    calc_tip_mach, calc_blade_passing_freq, find_octave_band,
    calc_specific_sound_power, calc_overall_lw, apply_kw_corrections,
    calc_bpf_tone_penalty, apply_a_weighting, log_sum_db,
    calc_motor_noise, estimate_sones,
    # Constants
    SPEED_OF_SOUND_FTS, REF_POWER_WATTS, OCTAVE_BANDS, A_WEIGHTING,
    KW_BASE, KW_CORRECTIONS,
    # Solver
    FanAcousticSolver,
)


# ===========================================================================
# Helper: run Steps 1–4 to produce a FanStructuralResult
# ===========================================================================

def _make_structural(cfm=10000, inwg=3.0, rpm=None) -> FanStructuralResult:
    dp = FanDesignPoint(cfm, inwg, rpm=rpm)
    r1 = FanClassificationSolver().solve({'design_point': dp})
    cls = r1['metadata']['classification']
    r2 = ImpellerAeroSolver().solve({'classification': cls})
    aero = r2['metadata']['aero']
    r3 = VoluteSolver().solve({'aero': aero})
    vol = r3['metadata']['volute']
    r4 = FanStructuralSolver().solve({'volute': vol})
    return r4['metadata']['structural']


# ===========================================================================
# calc_tip_mach
# ===========================================================================

class TestCalcTipMach:
    def test_known_value(self):
        """300 ft/s → Ma ≈ 0.266"""
        assert calc_tip_mach(300.0) == pytest.approx(300.0 / 1128.0, rel=1e-6)

    def test_zero(self):
        assert calc_tip_mach(0.0) == 0.0

    def test_speed_of_sound(self):
        assert calc_tip_mach(1128.0) == pytest.approx(1.0)

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            calc_tip_mach(-10.0)


# ===========================================================================
# calc_blade_passing_freq
# ===========================================================================

class TestCalcBladePassingFreq:
    def test_known_value(self):
        """12 blades @ 1750 RPM → 350 Hz"""
        assert calc_blade_passing_freq(12, 1750.0) == pytest.approx(350.0)

    def test_single_blade(self):
        assert calc_blade_passing_freq(1, 600.0) == pytest.approx(10.0)

    def test_zero_blades_raises(self):
        with pytest.raises(ValueError):
            calc_blade_passing_freq(0, 1750.0)

    def test_zero_rpm_raises(self):
        with pytest.raises(ValueError):
            calc_blade_passing_freq(12, 0.0)

    def test_negative_rpm_raises(self):
        with pytest.raises(ValueError):
            calc_blade_passing_freq(12, -100.0)


# ===========================================================================
# find_octave_band
# ===========================================================================

class TestFindOctaveBand:
    def test_350hz_in_250_band(self):
        """350 Hz falls in the 250 Hz octave band"""
        assert find_octave_band(350.0) == 250

    def test_1000hz_exact(self):
        """1000 Hz → 1000 band"""
        assert find_octave_band(1000.0) == 1000

    def test_63hz_band(self):
        assert find_octave_band(63.0) == 63

    def test_8000hz_band(self):
        assert find_octave_band(8000.0) == 8000

    def test_low_freq_clamps_to_63(self):
        """Very low frequency → 63 Hz band"""
        assert find_octave_band(20.0) == 63

    def test_high_freq_clamps_to_8000(self):
        """Very high frequency → 8000 Hz band"""
        assert find_octave_band(15000.0) == 8000

    def test_band_edge_lower(self):
        """Just above lower edge of 1000 Hz band: 1000/√2 ≈ 707"""
        edge = 1000.0 / math.sqrt(2.0) + 0.1  # Just inside 1000 band
        assert find_octave_band(edge) == 1000

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            find_octave_band(-100.0)

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            find_octave_band(0.0)


# ===========================================================================
# log_sum_db
# ===========================================================================

class TestLogSumDb:
    def test_two_equal_sources(self):
        """Two equal sources → +3 dB"""
        result = log_sum_db([80.0, 80.0])
        assert result == pytest.approx(83.01, abs=0.02)

    def test_10db_gap(self):
        """10 dB gap → ≈ higher value"""
        result = log_sum_db([90.0, 80.0])
        assert result == pytest.approx(90.41, abs=0.02)

    def test_single_value(self):
        assert log_sum_db([95.0]) == pytest.approx(95.0)

    def test_three_equal(self):
        """Three equal → +4.77 dB"""
        result = log_sum_db([80.0, 80.0, 80.0])
        assert result == pytest.approx(80.0 + 10 * math.log10(3), abs=0.01)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            log_sum_db([])


# ===========================================================================
# apply_a_weighting
# ===========================================================================

class TestApplyAWeighting:
    def test_63hz_penalty(self):
        """63 Hz gets -26.2 dB"""
        bands = [100.0] * 8
        result = apply_a_weighting(bands)
        assert result[0] == pytest.approx(100.0 - 26.2)

    def test_1khz_no_change(self):
        """1 kHz A-weighting = 0 dB"""
        bands = [100.0] * 8
        result = apply_a_weighting(bands)
        assert result[4] == pytest.approx(100.0)

    def test_2khz_boost(self):
        """2 kHz gets +1.2 dB"""
        bands = [100.0] * 8
        result = apply_a_weighting(bands)
        assert result[5] == pytest.approx(101.2)

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError):
            apply_a_weighting([80.0] * 7)

    def test_all_bands_applied(self):
        bands = [90.0] * 8
        result = apply_a_weighting(bands)
        for i, (lw, a) in enumerate(zip(bands, A_WEIGHTING)):
            assert result[i] == pytest.approx(lw + a)


# ===========================================================================
# calc_motor_noise
# ===========================================================================

class TestCalcMotorNoise:
    def test_10hp(self):
        """10 HP → Lw = 20·log₁₀(10) + 90 = 110 dB"""
        assert calc_motor_noise(10.0) == pytest.approx(110.0)

    def test_1hp(self):
        """1 HP → 90 dB"""
        assert calc_motor_noise(1.0) == pytest.approx(90.0)

    def test_100hp(self):
        """100 HP → 130 dB"""
        assert calc_motor_noise(100.0) == pytest.approx(130.0)

    def test_more_hp_more_noise(self):
        assert calc_motor_noise(50.0) > calc_motor_noise(10.0)

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            calc_motor_noise(0.0)

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            calc_motor_noise(-5.0)


# ===========================================================================
# calc_overall_lw
# ===========================================================================

class TestCalcOverallLw:
    def test_bi_in_range(self):
        """BI fan, 10000 CFM, 3 in.WG → 80–120 dB"""
        lw = calc_overall_lw(10000.0, 3.0, FanType.BACKWARD_INCLINED)
        assert 80 < lw < 120

    def test_bc_in_range(self):
        lw = calc_overall_lw(10000.0, 3.0, FanType.BACKWARD_CURVED)
        assert 80 < lw < 120

    def test_fc_in_range(self):
        lw = calc_overall_lw(10000.0, 3.0, FanType.FORWARD_CURVED)
        assert 80 < lw < 120

    def test_radial_in_range(self):
        lw = calc_overall_lw(5000.0, 10.0, FanType.RADIAL_BLADE)
        assert 80 < lw < 120

    def test_radial_louder_than_bi(self):
        """Radial blade fans are louder than BI at same duty"""
        lw_r = calc_overall_lw(10000.0, 3.0, FanType.RADIAL_BLADE)
        lw_bi = calc_overall_lw(10000.0, 3.0, FanType.BACKWARD_INCLINED)
        assert lw_r > lw_bi

    def test_more_cfm_more_noise(self):
        lw1 = calc_overall_lw(5000.0, 3.0, FanType.BACKWARD_INCLINED)
        lw2 = calc_overall_lw(20000.0, 3.0, FanType.BACKWARD_INCLINED)
        assert lw2 > lw1

    def test_zero_cfm_raises(self):
        with pytest.raises(ValueError):
            calc_overall_lw(0.0, 3.0, FanType.BACKWARD_INCLINED)

    def test_zero_pressure_raises(self):
        with pytest.raises(ValueError):
            calc_overall_lw(10000.0, 0.0, FanType.BACKWARD_INCLINED)


# ===========================================================================
# apply_kw_corrections
# ===========================================================================

class TestApplyKwCorrections:
    def test_returns_8_bands(self):
        bands = apply_kw_corrections(100.0, FanType.BACKWARD_INCLINED)
        assert len(bands) == 8

    def test_all_below_overall(self):
        """All bands should be below the overall level"""
        bands = apply_kw_corrections(100.0, FanType.BACKWARD_INCLINED)
        for b in bands:
            assert b < 100.0

    def test_log_sum_approx_overall(self):
        """Log-sum of bands ≈ overall ±1 dB"""
        overall = 100.0
        bands = apply_kw_corrections(overall, FanType.BACKWARD_INCLINED)
        resum = log_sum_db(bands)
        assert resum == pytest.approx(overall, abs=1.5)

    def test_fc_corrections(self):
        bands = apply_kw_corrections(100.0, FanType.FORWARD_CURVED)
        assert len(bands) == 8
        # FC low-freq correction is -1 at 63 Hz
        assert bands[0] == pytest.approx(99.0)

    def test_radial_corrections(self):
        bands = apply_kw_corrections(100.0, FanType.RADIAL_BLADE)
        # Radial 63 Hz correction is -5
        assert bands[0] == pytest.approx(95.0)


# ===========================================================================
# calc_bpf_tone_penalty
# ===========================================================================

class TestCalcBpfTonePenalty:
    def test_range(self):
        """Penalty should be 2–10 dB"""
        p = calc_bpf_tone_penalty(12, 0.3, FanType.BACKWARD_INCLINED)
        assert 2.0 <= p <= 10.0

    def test_higher_mach_higher_penalty(self):
        p_lo = calc_bpf_tone_penalty(12, 0.15, FanType.BACKWARD_INCLINED)
        p_hi = calc_bpf_tone_penalty(12, 0.45, FanType.BACKWARD_INCLINED)
        assert p_hi > p_lo

    def test_radial_higher_than_bc(self):
        p_r = calc_bpf_tone_penalty(12, 0.3, FanType.RADIAL_BLADE)
        p_bc = calc_bpf_tone_penalty(12, 0.3, FanType.BACKWARD_CURVED)
        assert p_r > p_bc

    def test_few_blades_higher(self):
        """Fewer blades → stronger wakes → higher penalty"""
        p_few = calc_bpf_tone_penalty(6, 0.3, FanType.BACKWARD_INCLINED)
        p_many = calc_bpf_tone_penalty(20, 0.3, FanType.BACKWARD_INCLINED)
        assert p_few > p_many


# ===========================================================================
# calc_specific_sound_power
# ===========================================================================

class TestCalcSpecificSoundPower:
    def test_known(self):
        """Kw = Lw - 10·log₁₀(CFM × in.WG)"""
        lw = 100.0
        cfm = 10000.0
        inwg = 3.0
        kw = calc_specific_sound_power(lw, cfm, inwg)
        expected = lw - 10.0 * math.log10(cfm * inwg)
        assert kw == pytest.approx(expected)

    def test_in_range(self):
        """Kw should be 30–55 for typical fans"""
        lw = calc_overall_lw(10000.0, 3.0, FanType.BACKWARD_INCLINED)
        kw = calc_specific_sound_power(lw, 10000.0, 3.0)
        assert 30 <= kw <= 55

    def test_zero_cfm_raises(self):
        with pytest.raises(ValueError):
            calc_specific_sound_power(100.0, 0.0, 3.0)


# ===========================================================================
# estimate_sones
# ===========================================================================

class TestEstimateSones:
    def test_positive(self):
        lwa = [70.0, 75.0, 80.0, 85.0, 85.0, 82.0, 78.0, 72.0]
        s = estimate_sones(lwa)
        assert s > 0

    def test_all_quiet(self):
        """All bands at or below 40 dBA → 0 sones"""
        lwa = [30.0] * 8
        assert estimate_sones(lwa) == 0.0

    def test_louder_more_sones(self):
        lwa_quiet = [60.0] * 8
        lwa_loud = [80.0] * 8
        assert estimate_sones(lwa_loud) > estimate_sones(lwa_quiet)

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError):
            estimate_sones([80.0] * 5)


# ===========================================================================
# Validation / Error handling
# ===========================================================================

class TestValidation:
    def test_missing_structural_raises(self):
        solver = FanAcousticSolver()
        with pytest.raises(ValueError, match="Missing"):
            solver.solve({})

    def test_wrong_type_raises(self):
        solver = FanAcousticSolver()
        with pytest.raises(ValueError, match="must be"):
            solver.solve({'structural': "not a result"})


# ===========================================================================
# Integration: HVAC duty
# ===========================================================================

class TestIntegrationHVAC:
    """HVAC fan: 15000 CFM, 4 in.WG"""

    @pytest.fixture
    def result(self):
        struct = _make_structural(cfm=15000, inwg=4.0)
        solver = FanAcousticSolver()
        r = solver.solve({'structural': struct})
        return r['metadata']['acoustic']

    def test_spectrum_has_8_bands(self, result):
        assert len(result.spectrum.lw_db) == 8
        assert len(result.spectrum.lw_a_db) == 8
        assert len(result.spectrum.center_frequencies) == 8

    def test_a_weighted_le_unweighted_at_low_freq(self, result):
        """A-weighted ≤ unweighted at 63 Hz (heavy penalty)"""
        assert result.spectrum.lw_a_db[0] < result.spectrum.lw_db[0]

    def test_overall_is_log_sum(self, result):
        """Overall Lw = log-sum of bands (consistency check)"""
        resum = log_sum_db(result.spectrum.lw_db)
        assert resum == pytest.approx(result.spectrum.overall_lw_db, abs=0.1)

    def test_overall_a_is_log_sum(self, result):
        resum = log_sum_db(result.spectrum.lw_a_db)
        assert resum == pytest.approx(result.spectrum.overall_lw_a_db, abs=0.1)

    def test_kw_in_range(self, result):
        """Specific sound power in 30–70 dB range (includes motor + tone contributions)"""
        assert 30 <= result.specific_sound_power <= 70

    def test_sones_positive(self, result):
        assert result.sones > 0

    def test_tip_mach_reasonable(self, result):
        assert 0.05 < result.tip_mach < 0.8

    def test_bpf_positive(self, result):
        assert result.tones.blade_passing_freq_hz > 0

    def test_bpf_harmonic_2(self, result):
        assert result.tones.bpf_harmonic_2_hz == pytest.approx(
            result.tones.blade_passing_freq_hz * 2.0)

    def test_bpf_in_valid_band(self, result):
        assert result.tones.bpf_octave_band in OCTAVE_BANDS

    def test_tone_penalty_applied(self, result):
        assert result.tones.tone_penalty_db >= 2.0

    def test_echoes_structural(self, result):
        assert isinstance(result.structural, FanStructuralResult)

    def test_solver_keys(self):
        struct = _make_structural(cfm=15000, inwg=4.0)
        solver = FanAcousticSolver()
        r = solver.solve({'structural': struct})
        assert 'parts' in r
        assert 'metadata' in r
        assert 'acoustic' in r['metadata']
        assert 'overall_lw_db' in r['metadata']
        assert 'sones' in r['metadata']
        assert 'bpf_hz' in r['metadata']


# ===========================================================================
# Integration: Dust collector duty (high pressure)
# ===========================================================================

class TestIntegrationDustCollector:
    """Dust collector: 3000 CFM, 15 in.WG, 3500 RPM"""

    @pytest.fixture
    def result(self):
        struct = _make_structural(cfm=3000, inwg=15.0, rpm=3500)
        solver = FanAcousticSolver()
        r = solver.solve({'structural': struct})
        return r['metadata']['acoustic']

    def test_spectrum_has_8_bands(self, result):
        assert len(result.spectrum.lw_db) == 8

    def test_overall_reasonable(self, result):
        """High-pressure fan should be 80–130 dB"""
        assert 80 < result.spectrum.overall_lw_db < 130

    def test_higher_tip_mach(self, result):
        """High-RPM fan → higher tip Mach"""
        assert result.tip_mach > 0.1

    def test_bpf_in_correct_band(self, result):
        """BPF should fall in a valid octave band"""
        bpf = result.tones.blade_passing_freq_hz
        expected_band = find_octave_band(bpf)
        assert result.tones.bpf_octave_band == expected_band


# ===========================================================================
# BI quieter than radial at same duty
# ===========================================================================

class TestFanTypeComparison:
    def test_bi_quieter_than_radial(self):
        """BI fan should be quieter than radial at same operating point"""
        lw_bi = calc_overall_lw(10000.0, 3.0, FanType.BACKWARD_INCLINED)
        lw_rad = calc_overall_lw(10000.0, 3.0, FanType.RADIAL_BLADE)
        assert lw_bi < lw_rad

    def test_bc_quieter_than_fc(self):
        """BC fan should be quieter than FC"""
        lw_bc = calc_overall_lw(10000.0, 3.0, FanType.BACKWARD_CURVED)
        lw_fc = calc_overall_lw(10000.0, 3.0, FanType.FORWARD_CURVED)
        assert lw_bc < lw_fc
