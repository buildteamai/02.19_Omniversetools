"""Named anchor points for assembly positioning (Layer 2 — Geometry Guardrails).

Replaces absolute coordinate math in generators.  Each component publishes an
``AnchorSet`` describing semantically named connection points; assembly code
uses ``place_at`` / ``align_to`` / ``stack_on`` to position components
relative to each other.

Pure Python + build123d — no USD dependency for the core classes and functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import build123d as bd


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

Vec3 = Tuple[float, float, float]


@dataclass
class AnchorPoint:
    """A named point on a component with an optional outward normal.

    Attributes
    ----------
    name : str
        Semantic label, e.g. ``'top_center'``, ``'inlet_flange'``.
    position : tuple
        ``(x, y, z)`` in the component's **local** coordinate space.
    direction : tuple
        ``(dx, dy, dz)`` unit-ish outward normal.  Used for mating direction
        and USD port direction.  Default ``(0, 1, 0)`` (upward).
    """

    name: str
    position: Vec3
    direction: Vec3 = (0.0, 1.0, 0.0)


class AnchorSet:
    """Collection of named anchor points for one component.

    Supports dict-style access (``anchors['top_center']``), chained
    ``.add()`` calls, and convenience constructors for boxes and cylinders.
    """

    def __init__(self, name: str = ""):
        self.name = name
        self._anchors: Dict[str, AnchorPoint] = {}

    # -- mutators ----------------------------------------------------------

    def add(
        self,
        name: str,
        position: Vec3,
        direction: Vec3 = (0.0, 1.0, 0.0),
    ) -> "AnchorSet":
        """Add an anchor point.  Returns *self* for chaining."""
        self._anchors[name] = AnchorPoint(name, position, direction)
        return self

    # -- accessors ---------------------------------------------------------

    def get(self, name: str) -> AnchorPoint:
        return self._anchors[name]

    def __getitem__(self, name: str) -> AnchorPoint:
        return self._anchors[name]

    def __contains__(self, name: str) -> bool:
        return name in self._anchors

    def names(self):
        return list(self._anchors.keys())

    def __repr__(self) -> str:
        return f"AnchorSet({self.name!r}, {list(self._anchors.keys())})"

    # -- convenience constructors ------------------------------------------

    @staticmethod
    def from_bounding_box(solid: bd.Solid, name: str = "box") -> "AnchorSet":
        """Auto-generate anchors from a solid's axis-aligned bounding box.

        Generated anchor names::

            top_center, bottom_center,
            front_center (+Z), back_center (−Z),
            left_center (−X), right_center (+X),
            top_front_left, top_front_right,
            top_back_left, top_back_right,
            bottom_front_left, bottom_front_right,
            bottom_back_left, bottom_back_right
        """
        bb = solid.bounding_box()
        xmin, xmax = bb.min.X, bb.max.X
        ymin, ymax = bb.min.Y, bb.max.Y
        zmin, zmax = bb.min.Z, bb.max.Z
        xmid = (xmin + xmax) / 2
        ymid = (ymin + ymax) / 2
        zmid = (zmin + zmax) / 2

        a = AnchorSet(name)

        # Face centres
        a.add("top_center", (xmid, ymax, zmid), (0, 1, 0))
        a.add("bottom_center", (xmid, ymin, zmid), (0, -1, 0))
        a.add("front_center", (xmid, ymid, zmax), (0, 0, 1))
        a.add("back_center", (xmid, ymid, zmin), (0, 0, -1))
        a.add("left_center", (xmin, ymid, zmid), (-1, 0, 0))
        a.add("right_center", (xmax, ymid, zmid), (1, 0, 0))

        # 8 corners — naming: {top|bottom}_{front|back}_{left|right}
        for y_label, y_val, y_dir in [("top", ymax, 1), ("bottom", ymin, -1)]:
            for z_label, z_val in [("front", zmax), ("back", zmin)]:
                for x_label, x_val in [("left", xmin), ("right", xmax)]:
                    cname = f"{y_label}_{z_label}_{x_label}"
                    a.add(cname, (x_val, y_val, z_val), (0, y_dir, 0))

        return a

    @staticmethod
    def from_cylinder(
        radius: float,
        height: float,
        name: str = "cyl",
        align_y: str = "bottom",
    ) -> "AnchorSet":
        """Generate anchors for a Y-axis cylinder.

        Generated anchor names::

            top_center, bottom_center,
            mid_north (+Z), mid_south (−Z),
            mid_east (+X), mid_west (−X)
        """
        if align_y == "bottom":
            ymin, ymax = 0.0, height
        elif align_y == "center":
            ymin, ymax = -height / 2, height / 2
        else:  # top
            ymin, ymax = -height, 0.0

        ymid = (ymin + ymax) / 2
        a = AnchorSet(name)
        a.add("top_center", (0, ymax, 0), (0, 1, 0))
        a.add("bottom_center", (0, ymin, 0), (0, -1, 0))
        a.add("mid_north", (0, ymid, radius), (0, 0, 1))
        a.add("mid_south", (0, ymid, -radius), (0, 0, -1))
        a.add("mid_east", (radius, ymid, 0), (1, 0, 0))
        a.add("mid_west", (-radius, ymid, 0), (-1, 0, 0))
        return a


# ---------------------------------------------------------------------------
# Positioning functions
# ---------------------------------------------------------------------------


def place_at(
    solid: bd.Solid,
    anchor_name: str,
    anchor_set: AnchorSet,
    target_point: Vec3,
) -> Tuple[bd.Solid, bd.Location]:
    """Move *solid* so that the named anchor lands on *target_point*.

    Parameters
    ----------
    solid : bd.Solid
        Component to reposition.
    anchor_name : str
        Key into *anchor_set*.
    anchor_set : AnchorSet
        Anchor definitions for *solid*.
    target_point : (x, y, z)
        World-space destination.

    Returns
    -------
    (moved_solid, location)
        The repositioned solid and the translation applied.
    """
    ap = anchor_set[anchor_name].position
    dx = target_point[0] - ap[0]
    dy = target_point[1] - ap[1]
    dz = target_point[2] - ap[2]
    loc = bd.Location((dx, dy, dz))
    return solid.moved(loc), loc


def align_to(
    solid_a: bd.Solid,
    anchor_a: str,
    anchors_a: AnchorSet,
    solid_b: bd.Solid,
    anchor_b: str,
    anchors_b: AnchorSet,
) -> Tuple[bd.Solid, bd.Location]:
    """Move *solid_a* so its *anchor_a* coincides with *solid_b*'s *anchor_b*.

    Returns ``(moved_solid_a, location_applied)``.
    """
    target = anchors_b[anchor_b].position
    return place_at(solid_a, anchor_a, anchors_a, target)


def stack_on(
    solid: bd.Solid,
    anchor_name: str,
    anchor_set: AnchorSet,
    base_solid: bd.Solid,
    base_anchor_name: str,
    base_anchors: AnchorSet,
) -> Tuple[bd.Solid, bd.Location]:
    """Place *solid* on top of *base_solid* by aligning anchor points.

    Convenience wrapper around :func:`align_to` for the very common
    "put this on top of that" operation.
    """
    return align_to(solid, anchor_name, anchor_set, base_solid, base_anchor_name, base_anchors)


# ---------------------------------------------------------------------------
# USD port bridge (optional — only call when stage is available)
# ---------------------------------------------------------------------------


def anchors_to_usd_ports(
    anchor_set: AnchorSet,
    stage,
    parent_path: str,
):
    """Convert an AnchorSet to USD port prims under *parent_path*.

    This bridges build123d-level anchors to the existing USD mating system.
    Only import pxr at call time so the module stays testable without USD.

    Parameters
    ----------
    anchor_set : AnchorSet
        Source anchors.
    stage : Usd.Stage
        Active USD stage.
    parent_path : str
        Prim path under which to create port Xforms.
    """
    from pxr import Gf, Sdf, UsdGeom

    for name in anchor_set.names():
        ap = anchor_set[name]
        port_path = f"{parent_path}/port_{name}"
        xform = UsdGeom.Xform.Define(stage, Sdf.Path(port_path))
        prim = xform.GetPrim()
        prim.SetCustomDataByKey("twin:is_port", True)
        prim.SetCustomDataByKey("twin:port_name", name)

        # Set position
        xform.AddTranslateOp().Set(Gf.Vec3d(*ap.position))

        # Store direction as custom data for the mating system
        prim.SetCustomDataByKey("twin:port_direction", Gf.Vec3d(*ap.direction))
