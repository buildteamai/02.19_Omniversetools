"""Validated geometry build operations (Layer 1 — Geometry Guardrails).

Every function returns a build123d Solid that is **Y-up and origin-anchored
by convention**.  The caller never thinks about axis rotation — it is handled
internally once, tested once, correct forever.

Coordinate contract (unless docstring says otherwise):
    • Height runs along **+Y**
    • Width runs along **X** (centered)
    • Depth runs along **Z** (centered)
    • ``align_y='bottom'`` → min-Y face sits at Y = 0
"""

from __future__ import annotations

import math
from typing import List, Literal, Sequence, Tuple, Union

import build123d as bd

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
AlignY = Literal["bottom", "center", "top"]
ProfilePts = Sequence[Tuple[float, float]]

# ---------------------------------------------------------------------------
# Vertical primitives (height along +Y)
# ---------------------------------------------------------------------------


def vertical_box(
    width_x: float,
    height_y: float,
    depth_z: float,
    align_y: AlignY = "bottom",
) -> bd.Solid:
    """Axis-aligned box with height along +Y.

    Parameters
    ----------
    width_x : float
        Extent along X.
    height_y : float
        Extent along Y (vertical).
    depth_z : float
        Extent along Z.
    align_y : ``'bottom'`` | ``'center'`` | ``'top'``
        • ``'bottom'`` — min-Y at 0, grows upward  (default)
        • ``'center'`` — centred on Y = 0
        • ``'top'``    — max-Y at 0, grows downward
    """
    y_align = {"bottom": bd.Align.MIN, "center": bd.Align.CENTER, "top": bd.Align.MAX}[
        align_y
    ]
    with bd.BuildPart() as bp:
        bd.Box(
            width_x,
            height_y,
            depth_z,
            align=(bd.Align.CENTER, y_align, bd.Align.CENTER),
        )
    return bp.part.solid()


def vertical_cylinder(
    radius: float,
    height: float,
    align_y: AlignY = "bottom",
) -> bd.Solid:
    """Cylinder with axis along +Y.

    Uses the ``rotation=(-90, 0, 0)`` constructor convention (build123d default
    cylinder axis is +Z; rotating −90° around X maps +Z → +Y).

    Parameters
    ----------
    radius : float
        Cylinder radius.
    height : float
        Extent along +Y.
    align_y : ``'bottom'`` | ``'center'`` | ``'top'``
        Vertical alignment (same semantics as *vertical_box*).
    """
    y_align = {"bottom": bd.Align.MIN, "center": bd.Align.CENTER, "top": bd.Align.MAX}[
        align_y
    ]
    with bd.BuildPart() as bp:
        bd.Cylinder(
            radius,
            height,
            rotation=(90, 0, 0),
            align=(bd.Align.CENTER, y_align, bd.Align.CENTER),
        )
    return bp.part.solid()


def vertical_extrude(
    profile_pts: ProfilePts,
    height: float,
    align_y: AlignY = "bottom",
) -> bd.Solid:
    """Extrude a closed polygon upward along +Y.

    Parameters
    ----------
    profile_pts : sequence of (x, z) tuples
        Vertices of a closed polygon lying in the XZ plane.  The polygon is
        automatically closed (last point → first point).
    height : float
        Extrusion distance along +Y.
    align_y : ``'bottom'`` | ``'center'`` | ``'top'``
        Vertical alignment.

    Implementation
    --------------
    The profile is drawn on ``Plane.XZ`` whose normal is +Y, so ``extrude``
    pushes geometry in the +Y direction — no post-rotation needed.
    """
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane.XZ):
            bd.Polygon(profile_pts, align=None)
        bd.extrude(amount=height)
    solid = bp.part.solid()

    if align_y == "bottom":
        bb = solid.bounding_box()
        if abs(bb.min.Y) > 1e-6:
            solid = solid.moved(bd.Location((0, -bb.min.Y, 0)))
    elif align_y == "center":
        bb = solid.bounding_box()
        mid_y = (bb.min.Y + bb.max.Y) / 2
        if abs(mid_y) > 1e-6:
            solid = solid.moved(bd.Location((0, -mid_y, 0)))
    elif align_y == "top":
        bb = solid.bounding_box()
        if abs(bb.max.Y) > 1e-6:
            solid = solid.moved(bd.Location((0, -bb.max.Y, 0)))

    return solid


# ---------------------------------------------------------------------------
# Horizontal primitives
# ---------------------------------------------------------------------------


def horizontal_extrude(
    profile_pts: ProfilePts,
    length: float,
    direction: Literal["x", "-x", "z", "-z"] = "x",
) -> bd.Solid:
    """Extrude a 2-D profile along a horizontal axis.

    Parameters
    ----------
    profile_pts : sequence of 2-D tuples
        Cross-section vertices.
        • ``direction='x'``  / ``'-x'`` → profile on YZ plane (tuples are ``(z, y)``)
        • ``direction='z'``  / ``'-z'`` → profile on XY plane (tuples are ``(x, y)``)
    length : float
        Extrusion distance (always positive; sign comes from *direction*).
    direction : ``'x'`` | ``'-x'`` | ``'z'`` | ``'-z'``
        Axis along which to extrude.
    """
    plane_map = {
        "x": bd.Plane.YZ,
        "-x": bd.Plane.YZ,
        "z": bd.Plane.XY,
        "-z": bd.Plane.XY,
    }
    plane = plane_map[direction]
    amount = length if direction in ("x", "z") else -length

    with bd.BuildPart() as bp:
        with bd.BuildSketch(plane):
            bd.Polygon(profile_pts, align=None)
        bd.extrude(amount=amount)

    solid = bp.part.solid()

    # Normalise: start at 0 on the extrusion axis, positive direction
    bb = solid.bounding_box()
    if direction in ("x", "-x"):
        solid = solid.moved(bd.Location((-bb.min.X, 0, 0)))
    else:
        solid = solid.moved(bd.Location((0, 0, -bb.min.Z)))

    return solid


# ---------------------------------------------------------------------------
# Revolve
# ---------------------------------------------------------------------------


def revolve_profile(
    profile_pts: ProfilePts,
    axis: Literal["x", "y", "z"] = "y",
    angle: float = 360.0,
) -> bd.Solid:
    """Revolve a half-profile around an axis.

    Parameters
    ----------
    profile_pts : sequence of (distance_from_axis, height) tuples
        Half-profile in the positive-distance quadrant.  First coordinate is
        the distance from the revolution axis; second is position along the
        axis.  Points should form a closed polygon (or will be auto-closed).
    axis : ``'x'`` | ``'y'`` | ``'z'``
        Revolution axis.  Default ``'y'`` (vertical).
    angle : float
        Arc of revolution in degrees (default 360 — full turn).

    Returns
    -------
    bd.Solid
        Revolved solid centred on the revolution axis.
    """
    # Map (dist, along_axis) to sketch coordinates based on axis
    if axis == "y":
        sketch_plane = bd.Plane.XY
        sketch_pts = [(d, h) for d, h in profile_pts]  # x=dist, y=height
        revolve_axis = bd.Axis.Y
    elif axis == "x":
        sketch_plane = bd.Plane.XY
        sketch_pts = [(h, d) for d, h in profile_pts]  # x=along, y=dist
        revolve_axis = bd.Axis.X
    else:  # z
        sketch_plane = bd.Plane.XZ
        sketch_pts = [(d, h) for d, h in profile_pts]  # x=dist, z=height
        revolve_axis = bd.Axis.Z

    with bd.BuildPart() as bp:
        with bd.BuildSketch(sketch_plane):
            bd.Polygon(sketch_pts, align=None)
        bd.revolve(axis=revolve_axis, revolution_arc=angle)

    return bp.part.solid()


# ---------------------------------------------------------------------------
# Array operations
# ---------------------------------------------------------------------------


def circular_array(
    solid: bd.Solid,
    count: int,
    radius: float,
    axis: Literal["x", "y", "z"] = "y",
) -> bd.Compound:
    """Arrange *count* copies of *solid* in a circle at *radius*.

    Parameters
    ----------
    solid : bd.Solid
        The component to replicate.
    count : int
        Number of copies (evenly spaced).
    radius : float
        Distance from the axis to the copy centre.
    axis : ``'x'`` | ``'y'`` | ``'z'``
        Axis about which to array (default ``'y'`` — vertical).

    Returns
    -------
    bd.Compound
        All copies combined into one compound.
    """
    copies: list[bd.Solid] = []
    for i in range(count):
        angle_rad = 2 * math.pi * i / count
        if axis == "y":
            dx = radius * math.cos(angle_rad)
            dz = radius * math.sin(angle_rad)
            loc = bd.Location((dx, 0, dz))
            rot = bd.Location((0, 0, 0), (0, math.degrees(angle_rad), 0))
        elif axis == "x":
            dy = radius * math.cos(angle_rad)
            dz = radius * math.sin(angle_rad)
            loc = bd.Location((0, dy, dz))
            rot = bd.Location((0, 0, 0), (math.degrees(angle_rad), 0, 0))
        else:  # z
            dx = radius * math.cos(angle_rad)
            dy = radius * math.sin(angle_rad)
            loc = bd.Location((dx, dy, 0))
            rot = bd.Location((0, 0, 0), (0, 0, math.degrees(angle_rad)))
        copies.append(solid.moved(loc * rot))

    return bd.Compound(copies)


# ---------------------------------------------------------------------------
# Mirror
# ---------------------------------------------------------------------------


def mirror_solid(
    solid: bd.Solid,
    plane: Literal["xz", "xy", "yz"] = "xz",
) -> bd.Solid:
    """Mirror *solid* across a cardinal plane through the origin.

    Parameters
    ----------
    plane : ``'xz'`` | ``'xy'`` | ``'yz'``
        • ``'xz'`` — mirror across Y = 0
        • ``'xy'`` — mirror across Z = 0
        • ``'yz'`` — mirror across X = 0

    Returns
    -------
    bd.Solid
        The mirrored copy (not fused with original).
    """
    plane_map = {
        "xz": bd.Plane.XZ,
        "xy": bd.Plane.XY,
        "yz": bd.Plane.YZ,
    }
    return solid.mirror(plane_map[plane])
