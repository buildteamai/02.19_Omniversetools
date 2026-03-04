"""
Fan Airflow Visualizer — particle streamline visualization using UsdGeom.Points.

Creates ~300 colored point particles that flow through 4 airflow zones:
    Zone 1 — Inlet approach (axial, blue)
    Zone 2 — Impeller passage (radial + swirl onset, cyan->green)
    Zone 3 — Volute scroll (270 deg log spiral, green->orange)
    Zone 4 — Discharge plume (upward jet, orange->red)

Particles are color-coded by velocity: blue(slow) -> red(fast).
"""

import math
import random
from dataclasses import dataclass

from pxr import UsdGeom, Gf, Vt, Sdf


# ── Color palette (6 velocity bands: blue → red) ────────────────────────

COLOR_BANDS = [
    Gf.Vec3f(0.1, 0.2, 0.8),   # 0: blue   (0-20%)
    Gf.Vec3f(0.1, 0.7, 0.8),   # 1: cyan   (20-40%)
    Gf.Vec3f(0.2, 0.8, 0.2),   # 2: green  (40-55%)
    Gf.Vec3f(0.9, 0.9, 0.1),   # 3: yellow (55-70%)
    Gf.Vec3f(0.9, 0.5, 0.1),   # 4: orange (70-85%)
    Gf.Vec3f(0.9, 0.1, 0.1),   # 5: red    (85-100%)
]

# Velocity fraction thresholds for each band
BAND_THRESHOLDS = [0.0, 0.20, 0.40, 0.55, 0.70, 0.85, 1.01]

NUM_PARTICLES = 300
POINT_WIDTH = 0.6  # inches — rendered diameter of each particle


@dataclass
class Particle:
    """Single particle state."""
    zone: int = 1       # 1-4
    t: float = 0.0      # 0->1 progress within zone
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    phi: float = 0.0    # random angle for inlet distribution
    jitter: float = 0.0 # deterministic per-particle offset for spread
    vel_frac: float = 0.0  # velocity as fraction of max (for coloring)


class FanAirflowVisualizer:
    """Particle streamline engine using UsdGeom.Points (simple point cloud)."""

    def __init__(self):
        self._stage = None
        self._fan_root_path = None
        self._viz_path = None
        self._points_prim = None
        self._particles: list[Particle] = []
        self._attached = False

        # Fan geometry metadata
        self._center_y = 0.0
        self._tip_r = 0.0
        self._eye_r = 0.0
        self._half_w = 0.0
        self._R_end = 0.0
        self._R_cutoff = 0.0
        self._imp_z = 0.0
        self._inlet_Cm = 0.0
        self._outlet_Cm = 0.0
        self._outlet_Cu = 0.0

    @property
    def is_attached(self) -> bool:
        return self._attached

    # ── Public API ───────────────────────────────────────────────────

    def attach(self, stage, fan_root_path: str, prim):
        """Read metadata, build Points prim, initialize particles."""
        self._stage = stage
        self._fan_root_path = fan_root_path
        self._viz_path = f"{fan_root_path}/AirflowViz"

        # Read geometry metadata
        self._center_y = float(prim.GetCustomDataByKey("twin:center_y") or 0)
        self._tip_r    = float(prim.GetCustomDataByKey("twin:tip_r") or 1)
        self._eye_r    = float(prim.GetCustomDataByKey("twin:eye_r") or 0.5)
        self._half_w   = float(prim.GetCustomDataByKey("twin:half_w") or 1)
        self._R_end    = float(prim.GetCustomDataByKey("twin:R_end") or 1)
        self._R_cutoff = float(prim.GetCustomDataByKey("twin:R_cutoff") or 0.5)
        self._imp_z    = float(prim.GetCustomDataByKey("twin:imp_z") or 0)
        self._inlet_Cm = float(prim.GetCustomDataByKey("twin:inlet_Cm") or 10)
        self._outlet_Cm = float(prim.GetCustomDataByKey("twin:outlet_Cm") or 20)
        self._outlet_Cu = float(prim.GetCustomDataByKey("twin:outlet_Cu") or 30)

        # Compute max velocity for color scaling (discharge is fastest)
        self._max_vel = math.sqrt(self._outlet_Cm**2 + self._outlet_Cu**2) * 1.1

        self._build_points()
        self._init_particles()
        self._flush()
        self._attached = True

    def detach(self):
        """Remove AirflowViz prim from stage."""
        if self._stage and self._viz_path:
            self._stage.RemovePrim(self._viz_path)
        self._attached = False
        self._points_prim = None
        self._particles.clear()

    def update(self, dt: float, velocity_ratio: float):
        """Advance all particles one frame and flush to USD."""
        if not self._attached or not self._points_prim:
            return
        if velocity_ratio <= 0.001:
            return

        for p in self._particles:
            self._advance_particle(p, dt, velocity_ratio)

        self._flush()

    # ── USD Points prim ───────────────────────────────────────────────

    def _build_points(self):
        """Create a single UsdGeom.Points prim with per-vertex color."""
        self._points_prim = UsdGeom.Points.Define(self._stage, self._viz_path)

        # Uniform widths (rendered diameter of each point)
        self._points_prim.GetWidthsAttr().Set(
            Vt.FloatArray([POINT_WIDTH] * NUM_PARTICLES))

        # Initialize positions to origin (overwritten immediately by _flush)
        self._points_prim.GetPointsAttr().Set(
            Vt.Vec3fArray([Gf.Vec3f(0, 0, 0)] * NUM_PARTICLES))

        # Per-vertex display color primvar
        color_pv = UsdGeom.PrimvarsAPI(self._points_prim).CreatePrimvar(
            "displayColor", Sdf.ValueTypeNames.Color3fArray,
            UsdGeom.Tokens.vertex)
        color_pv.Set(Vt.Vec3fArray([COLOR_BANDS[0]] * NUM_PARTICLES))

    def _flush(self):
        """Write current particle positions and colors to the Points prim."""
        positions = Vt.Vec3fArray(
            [Gf.Vec3f(float(p.x), float(p.y), float(p.z))
             for p in self._particles])
        colors = Vt.Vec3fArray(
            [COLOR_BANDS[self._velocity_to_band(p.vel_frac)]
             for p in self._particles])

        self._points_prim.GetPointsAttr().Set(positions)
        UsdGeom.PrimvarsAPI(self._points_prim).GetPrimvar(
            "displayColor").Set(colors)

    # ── Particle initialization ──────────────────────────────────────

    def _init_particles(self):
        """Spread particles across all 4 zones with random progress."""
        self._particles.clear()
        # Distribute: 20% inlet, 30% impeller, 35% volute, 15% discharge
        zone_counts = [
            int(NUM_PARTICLES * 0.20),
            int(NUM_PARTICLES * 0.30),
            int(NUM_PARTICLES * 0.35),
        ]
        zone_counts.append(NUM_PARTICLES - sum(zone_counts))  # remainder -> discharge

        for zone_idx, count in enumerate(zone_counts, start=1):
            for _ in range(count):
                p = Particle(
                    zone=zone_idx,
                    t=random.random(),
                    phi=random.uniform(0, 2 * math.pi),
                    jitter=random.uniform(-1.0, 1.0),
                )
                self._compute_position(p)
                self._particles.append(p)

    # ── Per-particle advance ─────────────────────────────────────────

    def _advance_particle(self, p: Particle, dt: float, velocity_ratio: float):
        """Move particle forward in its zone; respawn if exiting zone 4."""
        transit = self._zone_transit_time(p.zone)
        if transit <= 0:
            transit = 0.5

        # Scale speed by velocity ratio
        p.t += (dt * velocity_ratio) / transit

        if p.t >= 1.0:
            # Advance to next zone
            p.t -= 1.0
            if p.t > 1.0:
                p.t = random.random() * 0.1
            p.zone += 1
            if p.zone > 4:
                # Respawn at inlet
                p.zone = 1
                p.t = 0.0
                p.phi = random.uniform(0, 2 * math.pi)
                p.jitter = random.uniform(-1.0, 1.0)

        self._compute_position(p)

    def _zone_transit_time(self, zone: int) -> float:
        """Approximate transit time (seconds) for each zone at design speed."""
        if zone == 1:
            # Inlet approach: 8 inches at inlet_Cm ft/s
            length_in = 8.0
            vel_fps = max(self._inlet_Cm, 1.0)
            return (length_in / 12.0) / vel_fps
        elif zone == 2:
            # Impeller radial: eye_r to tip_r at avg meridional vel
            length_in = self._tip_r - self._eye_r
            vel_fps = max((self._inlet_Cm + self._outlet_Cm) / 2.0, 1.0)
            return (length_in / 12.0) / vel_fps
        elif zone == 3:
            # Volute: ~270 deg arc at average R, at avg volute velocity
            avg_r = (self._R_cutoff + self._R_end) / 2.0
            arc_in = avg_r * math.radians(270)
            vel_fps = max(math.sqrt(self._outlet_Cm**2 + self._outlet_Cu**2) * 0.8, 1.0)
            return (arc_in / 12.0) / vel_fps
        else:
            # Discharge plume: 12 inches at discharge velocity
            length_in = 12.0
            vel_fps = max(math.sqrt(self._outlet_Cm**2 + self._outlet_Cu**2), 1.0)
            return (length_in / 12.0) / vel_fps

    # ── Position computation per zone ────────────────────────────────

    def _compute_position(self, p: Particle):
        """Set p.x, p.y, p.z and p.vel_frac from zone + t."""
        cy = self._center_y

        if p.zone == 1:
            self._zone1_inlet(p, cy)
        elif p.zone == 2:
            self._zone2_impeller(p, cy)
        elif p.zone == 3:
            self._zone3_volute(p, cy)
        else:
            self._zone4_discharge(p, cy)

    def _zone1_inlet(self, p: Particle, cy: float):
        """Axial approach into inlet eye — particles travel +Z toward impeller face."""
        # Z goes from -(half_w + 8) to -half_w
        z_start = -(self._half_w + 8.0)
        z_end = -self._half_w
        p.z = z_start + p.t * (z_end - z_start)

        # Distributed within eye annulus (random radius, fixed angle)
        r = self._eye_r * (0.3 + 0.7 * abs(math.sin(p.phi * 3.7)))
        p.x = r * math.cos(p.phi)
        p.y = cy + r * math.sin(p.phi)

        # Velocity: inlet meridional
        p.vel_frac = self._inlet_Cm / max(self._max_vel, 1.0)

    def _zone2_impeller(self, p: Particle, cy: float):
        """Radial outward through impeller — r increases, phi rotates ~180 deg."""
        r = self._eye_r + p.t * (self._tip_r - self._eye_r)
        # Swirl: phi rotates ~180 deg through impeller passage
        phi = p.phi + p.t * math.pi
        p.x = r * math.cos(phi)
        p.y = cy + r * math.sin(phi)
        # Z stays near impeller midplane
        p.z = self._imp_z + p.jitter * 0.2

        # Velocity: blend from inlet_Cm to sqrt(outlet_Cm^2 + outlet_Cu^2 * t)
        cu_component = self._outlet_Cu * p.t
        cm_blend = self._inlet_Cm + p.t * (self._outlet_Cm - self._inlet_Cm)
        vel = math.sqrt(cm_blend**2 + cu_component**2)
        p.vel_frac = vel / max(self._max_vel, 1.0)

    def _zone3_volute(self, p: Particle, cy: float):
        """Follow 270 deg log spiral CW from tongue (at 90 deg = top).

        Scroll angle convention:
            theta_scroll = 0 deg at tongue (top, 90 deg math angle)
            theta_scroll = 270 deg at discharge
            R(theta) = R_cutoff * 1.0017^theta_scroll
            math_angle = (90 - theta_scroll) mod 360  -> maps to housing geometry
        """
        theta_scroll = p.t * 270.0  # 0->270 degrees
        R = self._R_cutoff * (1.0017 ** theta_scroll)

        # Convert to math angle (radians)
        theta_math = math.radians((90.0 - theta_scroll) % 360.0)

        p.x = R * math.cos(theta_math)
        p.y = cy + R * math.sin(theta_math)
        # Z near midplane with slight spread
        p.z = self._imp_z + p.jitter * 0.3

        # Velocity: increases along volute as area decreases
        vel_start = math.sqrt(self._outlet_Cm**2 + self._outlet_Cu**2) * 0.6
        vel_end = math.sqrt(self._outlet_Cm**2 + self._outlet_Cu**2)
        vel = vel_start + p.t * (vel_end - vel_start)
        p.vel_frac = vel / max(self._max_vel, 1.0)

    def _zone4_discharge(self, p: Particle, cy: float):
        """Upward discharge plume — +Y from scroll top, 12 inch extent."""
        # Discharge exits upward (+Y) from top of scroll
        base_x = 0.0
        base_y = cy + self._R_end
        plume_height = 12.0

        spread = 0.5 * (1.0 + p.t)
        p.x = base_x + p.jitter * spread
        p.y = base_y + p.t * plume_height
        p.z = self._imp_z + p.jitter * spread * 0.7

        # Velocity: discharge jet (fastest)
        vel = math.sqrt(self._outlet_Cm**2 + self._outlet_Cu**2)
        # Slight deceleration in plume
        vel *= (1.0 - 0.3 * p.t)
        p.vel_frac = vel / max(self._max_vel, 1.0)

    # ── Color mapping ────────────────────────────────────────────────

    @staticmethod
    def _velocity_to_band(vel_frac: float) -> int:
        """Map velocity fraction (0-1) to color band index (0-5)."""
        frac = max(0.0, min(1.0, vel_frac))
        for i in range(len(BAND_THRESHOLDS) - 1):
            if frac < BAND_THRESHOLDS[i + 1]:
                return i
        return len(COLOR_BANDS) - 1
