"""Automated geometric assertions (Layer 3 — Geometry Guardrails).

Run after geometry creation to catch coordinate, orientation, and positioning
errors before they reach the user or USD stage.

All functions operate on pure build123d Solids — no USD dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import build123d as bd


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Outcome of a single geometric check."""

    name: str
    passed: bool
    message: str
    expected: Any = None
    actual: Any = None


@dataclass
class ValidationResult:
    """Aggregated outcome of all checks on a solid."""

    passed: bool
    checks: List[CheckResult] = field(default_factory=list)

    def summary(self) -> str:
        lines = []
        for c in self.checks:
            status = "PASS" if c.passed else "FAIL"
            lines.append(f"  [{status}] {c.name}: {c.message}")
        return "\n".join(lines)


class GeometryValidationError(Exception):
    """Raised when ``validate(..., strict=True)`` encounters a failure."""

    def __init__(self, result: ValidationResult):
        self.result = result
        super().__init__(f"Geometry validation failed:\n{result.summary()}")


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def validate_bounds(
    solid: bd.Solid,
    expected_x: float,
    expected_y: float,
    expected_z: float,
    tolerance: float = 0.1,
) -> CheckResult:
    """Check that the solid's bounding-box dimensions match expectations.

    Parameters
    ----------
    expected_x, expected_y, expected_z : float
        Expected extents along each axis.
    tolerance : float
        Maximum allowable deviation on any axis.
    """
    bb = solid.bounding_box()
    actual_x = bb.max.X - bb.min.X
    actual_y = bb.max.Y - bb.min.Y
    actual_z = bb.max.Z - bb.min.Z

    dx = abs(actual_x - expected_x)
    dy = abs(actual_y - expected_y)
    dz = abs(actual_z - expected_z)
    ok = dx <= tolerance and dy <= tolerance and dz <= tolerance

    return CheckResult(
        name="bounding_box",
        passed=ok,
        message=(
            f"dims ({actual_x:.3f}, {actual_y:.3f}, {actual_z:.3f}) vs "
            f"expected ({expected_x:.3f}, {expected_y:.3f}, {expected_z:.3f})"
        ),
        expected=(expected_x, expected_y, expected_z),
        actual=(actual_x, actual_y, actual_z),
    )


def validate_orientation(
    solid: bd.Solid,
    expected_tall_axis: str = "y",
) -> CheckResult:
    """Check which axis has the largest extent.

    Catches the common "I rotated around the wrong axis" mistake.
    """
    bb = solid.bounding_box()
    extents = {
        "x": bb.max.X - bb.min.X,
        "y": bb.max.Y - bb.min.Y,
        "z": bb.max.Z - bb.min.Z,
    }
    tallest = max(extents, key=extents.get)
    ok = tallest == expected_tall_axis

    return CheckResult(
        name="orientation",
        passed=ok,
        message=(
            f"tallest axis is '{tallest}' "
            f"({'matches' if ok else 'expected ' + repr(expected_tall_axis)})"
        ),
        expected=expected_tall_axis,
        actual=tallest,
    )


def validate_ground_plane(
    solid: bd.Solid,
    expected_min_y: float = 0.0,
    tolerance: float = 0.01,
) -> CheckResult:
    """Check that the solid's minimum Y matches the expected value.

    Catches "floating above the floor" and "sunk below the floor" errors.
    """
    bb = solid.bounding_box()
    actual_min_y = bb.min.Y
    ok = abs(actual_min_y - expected_min_y) <= tolerance

    return CheckResult(
        name="ground_plane",
        passed=ok,
        message=(
            f"min Y = {actual_min_y:.4f} "
            f"(expected {expected_min_y:.4f} ± {tolerance})"
        ),
        expected=expected_min_y,
        actual=actual_min_y,
    )


def validate_symmetry(
    solid: bd.Solid,
    plane: str = "xz",
    tolerance: float = 0.1,
) -> CheckResult:
    """Check bounding-box symmetry about a cardinal plane.

    Parameters
    ----------
    plane : ``'xz'`` | ``'xy'`` | ``'yz'``
        • ``'xz'`` — symmetric about Y = 0  (equal +Y / −Y extents)
        • ``'xy'`` — symmetric about Z = 0
        • ``'yz'`` — symmetric about X = 0
    """
    bb = solid.bounding_box()
    if plane == "xz":
        diff = abs(bb.max.Y + bb.min.Y)  # should be ~0 if symmetric
        axis_label = "Y"
    elif plane == "xy":
        diff = abs(bb.max.Z + bb.min.Z)
        axis_label = "Z"
    elif plane == "yz":
        diff = abs(bb.max.X + bb.min.X)
        axis_label = "X"
    else:
        return CheckResult(
            name="symmetry",
            passed=False,
            message=f"Unknown symmetry plane '{plane}'",
        )

    ok = diff <= tolerance
    return CheckResult(
        name="symmetry",
        passed=ok,
        message=(
            f"{axis_label}-axis centre offset = {diff:.4f} "
            f"({'symmetric' if ok else 'asymmetric'} about {plane.upper()})"
        ),
        expected=0.0,
        actual=diff,
    )


def validate_assembly(
    parts: Dict[str, bd.Solid],
    transforms: Optional[Dict[str, bd.Location]] = None,
    max_envelope: float = 10000.0,
    rules: Optional[List[Tuple[str, str, str]]] = None,
) -> List[CheckResult]:
    """Run assembly-level sanity checks.

    Parameters
    ----------
    parts : dict
        name → bd.Solid
    transforms : dict, optional
        name → bd.Location to apply before checking.
    max_envelope : float
        Maximum allowed distance between any two part centres.
    rules : list of (subject, relation, reference), optional
        Constraint rules.  Supported relations:
        ``'above'`` — subject's min-Y > reference's max-Y (− tolerance)

    Returns
    -------
    list of CheckResult
    """
    results: list[CheckResult] = []
    transforms = transforms or {}

    # Apply transforms
    positioned: Dict[str, bd.Solid] = {}
    for name, solid in parts.items():
        loc = transforms.get(name)
        positioned[name] = solid.moved(loc) if loc else solid

    # --- Overlap check (axis-aligned bounding boxes) ---
    names = list(positioned.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = positioned[names[i]].bounding_box()
            b = positioned[names[j]].bounding_box()
            overlap = (
                a.min.X < b.max.X
                and a.max.X > b.min.X
                and a.min.Y < b.max.Y
                and a.max.Y > b.min.Y
                and a.min.Z < b.max.Z
                and a.max.Z > b.min.Z
            )
            if overlap:
                results.append(
                    CheckResult(
                        name="no_overlap",
                        passed=False,
                        message=f"'{names[i]}' and '{names[j]}' bounding boxes overlap",
                    )
                )

    # --- Envelope check ---
    centres = {}
    for name, solid in positioned.items():
        bb = solid.bounding_box()
        centres[name] = (
            (bb.min.X + bb.max.X) / 2,
            (bb.min.Y + bb.max.Y) / 2,
            (bb.min.Z + bb.max.Z) / 2,
        )
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ci, cj = centres[names[i]], centres[names[j]]
            dist = sum((a - b) ** 2 for a, b in zip(ci, cj)) ** 0.5
            if dist > max_envelope:
                results.append(
                    CheckResult(
                        name="envelope",
                        passed=False,
                        message=(
                            f"'{names[i]}' and '{names[j]}' are {dist:.1f} apart "
                            f"(max {max_envelope})"
                        ),
                    )
                )

    # --- Custom rules ---
    if rules:
        for subject, relation, reference in rules:
            s_bb = positioned[subject].bounding_box()
            r_bb = positioned[reference].bounding_box()
            if relation == "above":
                ok = s_bb.min.Y >= r_bb.max.Y - 0.01
                results.append(
                    CheckResult(
                        name="rule",
                        passed=ok,
                        message=(
                            f"'{subject}' {'is' if ok else 'is NOT'} above "
                            f"'{reference}' (min_Y={s_bb.min.Y:.3f} vs "
                            f"ref max_Y={r_bb.max.Y:.3f})"
                        ),
                    )
                )

    if not results:
        results.append(
            CheckResult(
                name="assembly",
                passed=True,
                message="All assembly checks passed",
            )
        )

    return results


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------


def validate(
    solid: bd.Solid,
    bounds: Optional[Tuple[float, float, float]] = None,
    orientation: Optional[str] = None,
    ground_plane: Optional[float] = None,
    symmetry: Optional[str] = None,
    tolerance: float = 0.1,
    strict: bool = False,
) -> ValidationResult:
    """Run multiple checks in one call.

    Parameters
    ----------
    solid : bd.Solid
        The geometry to validate.
    bounds : (x, y, z), optional
        Expected bounding-box dimensions.
    orientation : ``'x'`` | ``'y'`` | ``'z'``, optional
        Expected tallest axis.
    ground_plane : float, optional
        Expected minimum Y value.
    symmetry : ``'xz'`` | ``'xy'`` | ``'yz'``, optional
        Plane about which the solid should be symmetric.
    tolerance : float
        Tolerance for bounds and symmetry checks.
    strict : bool
        If True, raise :class:`GeometryValidationError` on any failure.

    Returns
    -------
    ValidationResult
    """
    checks: list[CheckResult] = []

    if bounds is not None:
        checks.append(validate_bounds(solid, *bounds, tolerance=tolerance))
    if orientation is not None:
        checks.append(validate_orientation(solid, orientation))
    if ground_plane is not None:
        checks.append(validate_ground_plane(solid, ground_plane))
    if symmetry is not None:
        checks.append(validate_symmetry(solid, symmetry, tolerance=tolerance))

    all_passed = all(c.passed for c in checks)
    result = ValidationResult(passed=all_passed, checks=checks)

    if strict and not all_passed:
        raise GeometryValidationError(result)

    return result
