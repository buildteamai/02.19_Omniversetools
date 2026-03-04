"""
USD → STEP Exporter

Exports USD scene geometry to STEP (ISO 10303) format.

Supports all USD geometry types used in the project:
  - UsdGeom.Mesh     → sew triangles into OCC shell (or regenerate from metadata)
  - UsdGeom.Cube     → OCC box solid
  - UsdGeom.Cylinder  → OCC cylinder solid
  - UsdGeom.Sphere    → OCC sphere solid
  - UsdGeom.Cone      → OCC cone solid

Traverses the ENTIRE stage (not just /World) so enclosures, buildings,
and other root-level assemblies are captured.

Two strategies for Mesh prims:
  1. Generator regeneration: If metadata exists, regenerate exact B-Rep.
  2. Mesh reconstruction: Sew triangulated faces via OCP (lossy but faithful).
"""

import os
import math
import traceback
from typing import List, Dict, Any, Optional, Tuple

import build123d as bd
from OCP.gp import gp_Pnt, gp_Vec, gp_Trsf, gp_Ax2, gp_Dir, gp_XYZ
from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeCone
from OCP.TopoDS import TopoDS_Compound, TopoDS_Shape
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static

from pxr import Usd, UsdGeom, Gf


# ---------------------------------------------------------------------------
# Generator registry for lossless B-Rep regeneration (Type B generators only)
# ---------------------------------------------------------------------------

_GENERATOR_MAP = {
    "wide_flange": {
        "import": "..objects.structural.wide_flange",
        "class": "WideFlangeGenerator",
        "method": "create",
        "params": ["depth", "flange_width", "flange_thickness", "web_thickness", "fillet_radius", "length"],
        "param_types": [float, float, float, float, float, float],
    },
    "channel": {
        "import": "..objects.structural.channel",
        "class": "ChannelGenerator",
        "method": "create",
        "params": ["depth", "flange_width", "flange_thickness", "web_thickness", "length", "fillet_radius"],
        "param_types": [float, float, float, float, float, float],
    },
    "hss_tube": {
        "import": "..objects.structural.hss_tube",
        "class": "HSSGenerator",
        "method": "create_rectangular",
        "params": ["outer_width", "outer_height", "wall_thickness", "length"],
        "param_types": [float, float, float, float],
    },
    "pyramid": {
        "import": "..objects.components.pyramid",
        "class": "PyramidGenerator",
        "method": "create",
        "params": ["base", "height", "taper_angle"],
        "param_types": [float, float, float],
    },
}

# Prim names to skip — visualization-only geometry (anchors, port markers)
_SKIP_NAMES = {"viz", "Anchor_Start", "Anchor_End", "Anchors"}
_SKIP_PREFIXES = ("Anchor_",)
_SKIP_ATTRS = ("twin:is_port",)


class StepExporter:
    """Exports USD scene geometry to STEP files."""

    def __init__(self):
        self._stats = {"regenerated": 0, "meshed": 0, "gprim": 0, "skipped": 0, "errors": 0}
        self._log_lines: List[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(
        self,
        stage: Usd.Stage,
        output_path: str,
        selected_paths: Optional[List[str]] = None,
    ) -> bool:
        """
        Export USD geometry to a STEP file.

        Args:
            stage: The USD stage to export from.
            output_path: Destination .step file path.
            selected_paths: If provided, only export these prim paths (and children).

        Returns:
            True on success, False on failure.
        """
        self._stats = {"regenerated": 0, "meshed": 0, "gprim": 0, "skipped": 0, "errors": 0}
        self._log_lines = []

        if not stage:
            self._log("ERROR: No USD stage provided.")
            return False

        # Collect geometry prims from entire stage
        geo_prims = self._collect_geo_prims(stage, selected_paths)
        if not geo_prims:
            self._log("No geometry found to export.")
            return False

        self._log(f"Found {len(geo_prims)} geometry prims to export.")

        # Stage units → mm for STEP
        meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage)
        scale_to_mm = meters_per_unit * 1000.0

        # Convert each prim to an OCC shape
        shapes: List[TopoDS_Shape] = []
        for prim in geo_prims:
            path = str(prim.GetPath())
            try:
                shape = self._process_prim(prim, stage, scale_to_mm)
                if shape:
                    shapes.append(shape)
            except Exception as e:
                self._stats["errors"] += 1
                self._log(f"  ERROR {path}: {e}")
                traceback.print_exc()

        if not shapes:
            self._log("No geometry could be converted. Export aborted.")
            return False

        # Combine and write
        compound = self._make_compound(shapes)
        success = self._write_step(compound, output_path)

        self._log(
            f"Export complete: {self._stats['regenerated']} regenerated, "
            f"{self._stats['meshed']} from mesh, "
            f"{self._stats['gprim']} primitives, "
            f"{self._stats['skipped']} skipped, "
            f"{self._stats['errors']} errors."
        )
        return success

    def get_log(self) -> str:
        return "\n".join(self._log_lines)

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Prim collection — traverses ENTIRE stage
    # ------------------------------------------------------------------

    def _collect_geo_prims(
        self, stage: Usd.Stage, selected_paths: Optional[List[str]]
    ) -> List[Usd.Prim]:
        """Collect all exportable geometry prims from the stage."""
        geo_prims = []

        if selected_paths:
            for p in selected_paths:
                prim = stage.GetPrimAtPath(p)
                if not prim:
                    continue
                if self._is_exportable_geo(prim):
                    geo_prims.append(prim)
                # Always traverse children for Xform groups
                for child in Usd.PrimRange(prim):
                    if child == prim:
                        continue
                    if self._is_exportable_geo(child):
                        geo_prims.append(child)
        else:
            # Traverse entire stage with instance proxy support
            for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
                if self._is_exportable_geo(prim):
                    geo_prims.append(prim)

        return geo_prims

    def _is_exportable_geo(self, prim: Usd.Prim) -> bool:
        """Check if a prim is exportable geometry (not a viz/anchor helper)."""
        if not prim.IsA(UsdGeom.Gprim):
            return False

        name = prim.GetName()

        # Skip visualization-only prims
        if name in _SKIP_NAMES:
            return False
        for prefix in _SKIP_PREFIXES:
            if name.startswith(prefix):
                return False

        # Skip port markers
        for attr_name in _SKIP_ATTRS:
            attr = prim.GetAttribute(attr_name)
            if attr and attr.Get():
                return False

        # Skip prims whose parent is a port/anchor
        parent = prim.GetParent()
        if parent:
            parent_name = parent.GetName()
            if parent_name in _SKIP_NAMES:
                return False
            for prefix in _SKIP_PREFIXES:
                if parent_name.startswith(prefix):
                    return False
            # Check parent for port attribute
            for attr_name in _SKIP_ATTRS:
                p_attr = parent.GetAttribute(attr_name)
                if p_attr and p_attr.Get():
                    return False

        return True

    # ------------------------------------------------------------------
    # Per-prim processing — dispatches by geometry type
    # ------------------------------------------------------------------

    def _process_prim(
        self, prim: Usd.Prim, stage: Usd.Stage, scale_to_mm: float
    ) -> Optional[TopoDS_Shape]:
        """Convert a USD geometry prim into an OCC shape."""
        path = str(prim.GetPath())
        shape = None

        if prim.IsA(UsdGeom.Mesh):
            shape = self._process_mesh(prim, path)
        elif prim.IsA(UsdGeom.Cube):
            shape = self._process_cube(prim, path)
        elif prim.IsA(UsdGeom.Cylinder):
            shape = self._process_cylinder(prim, path)
        elif prim.IsA(UsdGeom.Sphere):
            shape = self._process_sphere(prim, path)
        elif prim.IsA(UsdGeom.Cone):
            shape = self._process_cone(prim, path)

        if shape is None:
            self._stats["skipped"] += 1
            return None

        # Apply world transform + unit scaling
        world_mtx = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        shape = self._apply_transform(shape, world_mtx, scale_to_mm)

        return shape

    # ------------------------------------------------------------------
    # Mesh processing (Strategy 1: regen, Strategy 2: sew)
    # ------------------------------------------------------------------

    def _process_mesh(self, prim: Usd.Prim, prim_path: str) -> Optional[TopoDS_Shape]:
        """Process a UsdGeom.Mesh prim."""
        custom_data = prim.GetCustomData() or {}
        generator_type = custom_data.get("generatorType")

        # Strategy 1: regenerate from metadata
        if generator_type and generator_type in _GENERATOR_MAP:
            shape = self._regenerate_from_metadata(generator_type, custom_data, prim_path)
            if shape:
                return shape

        # Strategy 2: reconstruct from mesh data
        return self._reconstruct_from_mesh(prim, prim_path)

    def _regenerate_from_metadata(
        self, gen_type: str, custom_data: Dict[str, Any], prim_path: str
    ) -> Optional[TopoDS_Shape]:
        """Regenerate exact B-Rep solid from stored generator parameters."""
        spec = _GENERATOR_MAP[gen_type]

        params = []
        for key, ptype in zip(spec["params"], spec["param_types"]):
            val = custom_data.get(key)
            if val is None:
                # Check inside aisc_data for structural members
                aisc_raw = custom_data.get("aisc_data")
                if aisc_raw:
                    if isinstance(aisc_raw, str):
                        import json
                        try:
                            aisc = json.loads(aisc_raw)
                        except Exception:
                            aisc = {}
                    else:
                        aisc = aisc_raw
                    val = aisc.get(key)

            if val is None:
                self._log(f"  REGEN SKIP {prim_path}: missing param '{key}'")
                return None
            try:
                params.append(ptype(val))
            except (ValueError, TypeError):
                self._log(f"  REGEN SKIP {prim_path}: bad value for '{key}': {val}")
                return None

        try:
            import importlib
            mod = importlib.import_module(spec["import"], package=__package__)
            cls = getattr(mod, spec["class"])
            method = getattr(cls, spec["method"])
            solid = method(*params)

            if solid is not None:
                self._stats["regenerated"] += 1
                self._log(f"  REGEN OK {prim_path} ({gen_type})")
                return solid.wrapped
        except Exception as e:
            self._log(f"  REGEN FAIL {prim_path}: {e}")

        return None

    def _reconstruct_from_mesh(self, prim: Usd.Prim, prim_path: str) -> Optional[TopoDS_Shape]:
        """Reconstruct OCC shape from USD mesh vertices and face indices."""
        mesh = UsdGeom.Mesh(prim)
        points_attr = mesh.GetPointsAttr().Get()
        indices_attr = mesh.GetFaceVertexIndicesAttr().Get()
        counts_attr = mesh.GetFaceVertexCountsAttr().Get()

        if not points_attr or not indices_attr or not counts_attr:
            self._log(f"  MESH SKIP {prim_path}: missing mesh data")
            return None

        points = list(points_attr)
        indices = list(indices_attr)
        counts = list(counts_attr)

        occ_points = [gp_Pnt(float(p[0]), float(p[1]), float(p[2])) for p in points]

        sewer = BRepBuilderAPI_Sewing(1e-4)

        idx = 0
        for face_vcount in counts:
            face_indices = indices[idx : idx + face_vcount]
            idx += face_vcount

            if face_vcount == 3:
                self._add_triangle_face(sewer, occ_points, face_indices)
            elif face_vcount == 4:
                self._add_triangle_face(sewer, occ_points, [face_indices[0], face_indices[1], face_indices[2]])
                self._add_triangle_face(sewer, occ_points, [face_indices[0], face_indices[2], face_indices[3]])
            elif face_vcount > 4:
                for i in range(1, face_vcount - 1):
                    self._add_triangle_face(
                        sewer, occ_points, [face_indices[0], face_indices[i], face_indices[i + 1]]
                    )

        sewer.Perform()
        sewn = sewer.SewedShape()

        if sewn is None or sewn.IsNull():
            self._log(f"  MESH SKIP {prim_path}: sewing produced null shape")
            return None

        self._stats["meshed"] += 1
        self._log(f"  MESH OK {prim_path} ({len(points)} verts, {len(counts)} faces)")
        return sewn

    @staticmethod
    def _add_triangle_face(
        sewer: BRepBuilderAPI_Sewing,
        points: List[gp_Pnt],
        tri_indices: List[int],
    ):
        """Create a triangular BRep face and add to sewer."""
        i0, i1, i2 = tri_indices
        p0, p1, p2 = points[i0], points[i1], points[i2]

        v1 = gp_Vec(p0, p1)
        v2 = gp_Vec(p0, p2)
        if v1.Magnitude() < 1e-8 or v2.Magnitude() < 1e-8:
            return
        cross = v1.Crossed(v2)
        if cross.Magnitude() < 1e-12:
            return

        try:
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace as MF

            polygon = BRepBuilderAPI_MakePolygon(p0, p1, p2, True)
            if polygon.IsDone():
                wire = polygon.Wire()
                face = MF(wire, True)
                if face.IsDone():
                    sewer.Add(face.Face())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # USD Gprim → OCC solid converters
    # ------------------------------------------------------------------

    def _process_cube(self, prim: Usd.Prim, prim_path: str) -> Optional[TopoDS_Shape]:
        """Convert UsdGeom.Cube to OCC box.

        USD Cube has 'size' attribute (default 2.0) centered at origin.
        Actual dimensions come from size * xformOp:scale.
        """
        cube = UsdGeom.Cube(prim)
        size = cube.GetSizeAttr().Get() or 2.0

        # Half-size: cube is centered at origin, OCC MakeBox starts from corner
        hs = float(size) / 2.0
        try:
            box = BRepPrimAPI_MakeBox(gp_Pnt(-hs, -hs, -hs), hs * 2, hs * 2, hs * 2)
            if box.IsDone():
                self._stats["gprim"] += 1
                self._log(f"  CUBE OK {prim_path} (size={size})")
                return box.Shape()
        except Exception as e:
            self._log(f"  CUBE FAIL {prim_path}: {e}")
        return None

    def _process_cylinder(self, prim: Usd.Prim, prim_path: str) -> Optional[TopoDS_Shape]:
        """Convert UsdGeom.Cylinder to OCC cylinder.

        USD Cylinder: radius, height, centered at origin, axis along Y (scene up axis)
        or along the 'axis' attribute.
        """
        cyl = UsdGeom.Cylinder(prim)
        radius = float(cyl.GetRadiusAttr().Get() or 1.0)
        height = float(cyl.GetHeightAttr().Get() or 2.0)

        # USD cylinder is centered at origin along its axis
        # Determine axis direction
        axis_attr = cyl.GetAxisAttr().Get()
        axis_str = str(axis_attr) if axis_attr else "Y"

        if "Z" in axis_str:
            ax = gp_Ax2(gp_Pnt(0, 0, -height / 2.0), gp_Dir(0, 0, 1))
        elif "X" in axis_str:
            ax = gp_Ax2(gp_Pnt(-height / 2.0, 0, 0), gp_Dir(1, 0, 0))
        else:  # Y (default for Y-up scenes)
            ax = gp_Ax2(gp_Pnt(0, -height / 2.0, 0), gp_Dir(0, 1, 0))

        try:
            shape = BRepPrimAPI_MakeCylinder(ax, radius, height)
            if shape.IsDone():
                self._stats["gprim"] += 1
                self._log(f"  CYL OK {prim_path} (r={radius}, h={height})")
                return shape.Shape()
        except Exception as e:
            self._log(f"  CYL FAIL {prim_path}: {e}")
        return None

    def _process_sphere(self, prim: Usd.Prim, prim_path: str) -> Optional[TopoDS_Shape]:
        """Convert UsdGeom.Sphere to OCC sphere."""
        sphere = UsdGeom.Sphere(prim)
        radius = float(sphere.GetRadiusAttr().Get() or 1.0)

        try:
            shape = BRepPrimAPI_MakeSphere(radius)
            if shape.IsDone():
                self._stats["gprim"] += 1
                self._log(f"  SPHERE OK {prim_path} (r={radius})")
                return shape.Shape()
        except Exception as e:
            self._log(f"  SPHERE FAIL {prim_path}: {e}")
        return None

    def _process_cone(self, prim: Usd.Prim, prim_path: str) -> Optional[TopoDS_Shape]:
        """Convert UsdGeom.Cone to OCC cone."""
        cone = UsdGeom.Cone(prim)
        radius = float(cone.GetRadiusAttr().Get() or 1.0)
        height = float(cone.GetHeightAttr().Get() or 2.0)

        # USD cone centered at origin along axis
        axis_attr = cone.GetAxisAttr().Get()
        axis_str = str(axis_attr) if axis_attr else "Y"

        if "Z" in axis_str:
            ax = gp_Ax2(gp_Pnt(0, 0, -height / 2.0), gp_Dir(0, 0, 1))
        elif "X" in axis_str:
            ax = gp_Ax2(gp_Pnt(-height / 2.0, 0, 0), gp_Dir(1, 0, 0))
        else:
            ax = gp_Ax2(gp_Pnt(0, -height / 2.0, 0), gp_Dir(0, 1, 0))

        try:
            shape = BRepPrimAPI_MakeCone(ax, radius, 0.0, height)
            if shape.IsDone():
                self._stats["gprim"] += 1
                self._log(f"  CONE OK {prim_path} (r={radius}, h={height})")
                return shape.Shape()
        except Exception as e:
            self._log(f"  CONE FAIL {prim_path}: {e}")
        return None

    # ------------------------------------------------------------------
    # Transform helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_transform(
        shape: TopoDS_Shape, usd_matrix: Gf.Matrix4d, scale_to_mm: float
    ) -> TopoDS_Shape:
        """Apply USD world transform + unit scaling to an OCC shape."""
        trsf = gp_Trsf()
        m = usd_matrix
        s = scale_to_mm

        # USD Matrix4d: row[i][j], translation in row[3][0..2]
        # OCC gp_Trsf.SetValues: (a11,a12,a13,a14, a21,a22,a23,a24, a31,a32,a33,a34)
        # where a14,a24,a34 are translations
        trsf.SetValues(
            m[0][0] * s, m[0][1] * s, m[0][2] * s, m[3][0] * s,
            m[1][0] * s, m[1][1] * s, m[1][2] * s, m[3][1] * s,
            m[2][0] * s, m[2][1] * s, m[2][2] * s, m[3][2] * s,
        )

        transformer = BRepBuilderAPI_Transform(shape, trsf, True)
        if transformer.IsDone():
            return transformer.Shape()
        return shape

    # ------------------------------------------------------------------
    # Compound assembly + STEP write
    # ------------------------------------------------------------------

    @staticmethod
    def _make_compound(shapes: List[TopoDS_Shape]) -> TopoDS_Compound:
        """Combine multiple shapes into an OCC compound."""
        compound = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(compound)
        for s in shapes:
            builder.Add(compound, s)
        return compound

    @staticmethod
    def _write_step(shape: TopoDS_Shape, filepath: str) -> bool:
        """Write an OCC shape to a STEP file."""
        out_dir = os.path.dirname(filepath)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        writer = STEPControl_Writer()
        Interface_Static.SetCVal_s("write.step.schema", "AP214")
        Interface_Static.SetCVal_s("write.step.product.name", "USD Export")

        writer.Transfer(shape, STEPControl_AsIs)
        status = writer.Write(filepath)

        if status == IFSelect_RetDone:
            print(f"[StepExporter] STEP file written: {filepath}")
            return True
        else:
            print(f"[StepExporter] STEP write failed with status: {status}")
            return False

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, msg: str):
        print(f"[StepExporter] {msg}")
        self._log_lines.append(msg)
