# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Equipment Registry - Central catalog of all parametric generators.

Provides a uniform interface over both Type A (stage-aware) and Type B
(geometry-only) generators without modifying them.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum, IntEnum


class DetailLevel(IntEnum):
    PLACEHOLDER = 0   # Bounding box with label + ports
    SCHEMATIC = 1     # Simplified recognizable shape
    PARAMETRIC = 2    # Full build123d geometry (current quality)
    DETAILED = 3      # Parametric + bolt holes, stiffeners, welds


class ParamType(Enum):
    FLOAT = "float"
    INT = "int"
    STRING = "string"
    BOOL = "bool"
    ENUM = "enum"
    DATA_LOOKUP = "data_lookup"


@dataclass
class ParamDef:
    name: str
    param_type: ParamType
    default: Any
    label: str = ""
    unit: str = "in"
    min_val: Any = None
    max_val: Any = None
    choices: List[str] = field(default_factory=list)
    data_file: str = ""
    data_key: str = ""
    description: str = ""
    group: str = "General"


@dataclass
class PortDef:
    name: str
    port_type: str = "HVAC"
    shape: str = "Rectangular"


class GeneratorAdapter:
    """Wraps a generator class to provide uniform create(stage, path, params)."""

    STAGE_AWARE = "stage_aware"
    GEOMETRY_ONLY = "geometry_only"

    def __init__(self, generator_class, adapter_type: str,
                 create_method: str = "create",
                 param_mapping: Dict[str, str] = None):
        self.generator_class = generator_class
        self.adapter_type = adapter_type
        self.create_method = create_method
        self.param_mapping = param_mapping or {}

    def create(self, stage, path, params: Dict[str, Any], tolerance=0.001):
        mapped = {}
        for k, v in params.items():
            mapped_name = self.param_mapping.get(k, k)
            mapped[mapped_name] = v

        create_fn = getattr(self.generator_class, self.create_method)

        if self.adapter_type == self.STAGE_AWARE:
            return create_fn(stage, path, **mapped)
        else:
            from ..utils import usd_utils
            solid = create_fn(**mapped)
            if solid is None:
                return None
            return usd_utils.create_mesh_from_shape(stage, path, solid, tolerance)


@dataclass
class EquipmentEntry:
    id: str
    name: str
    category: str
    adapter: GeneratorAdapter
    params: List[ParamDef] = field(default_factory=list)
    ports: List[PortDef] = field(default_factory=list)
    detail_levels: List[DetailLevel] = field(default_factory=lambda: [DetailLevel.PARAMETRIC])
    generator_type_key: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)


class EquipmentRegistry:
    """Singleton registry of all available equipment generators."""

    _instance = None

    def __init__(self):
        self._entries: Dict[str, EquipmentEntry] = {}

    @classmethod
    def instance(cls) -> "EquipmentRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, entry: EquipmentEntry):
        self._entries[entry.id] = entry

    def get(self, entry_id: str) -> Optional[EquipmentEntry]:
        return self._entries.get(entry_id)

    def all_entries(self) -> Dict[str, EquipmentEntry]:
        return dict(self._entries)

    def by_category(self) -> Dict[str, List[EquipmentEntry]]:
        from collections import defaultdict
        grouped = defaultdict(list)
        for entry in self._entries.values():
            grouped[entry.category].append(entry)
        return dict(grouped)

    def search(self, query: str) -> List[EquipmentEntry]:
        q = query.lower()
        results = []
        for entry in self._entries.values():
            if (q in entry.name.lower()
                    or q in entry.description.lower()
                    or any(q in tag.lower() for tag in entry.tags)):
                results.append(entry)
        return results

    def create_component(self, entry_id: str, stage, path: str,
                         params: Dict[str, Any] = None,
                         detail_level: DetailLevel = DetailLevel.PARAMETRIC):
        entry = self.get(entry_id)
        if not entry and entry_id != "__placeholder__":
            print(f"[IEIP Registry] Unknown entry: {entry_id}")
            return None

        resolved = self._resolve_defaults(entry, params or {}) if entry else (params or {})

        if detail_level == DetailLevel.PLACEHOLDER or entry_id == "__placeholder__":
            return self._create_placeholder(stage, path, entry, resolved, entry_id)
        elif detail_level == DetailLevel.SCHEMATIC:
            # Phase 1: schematic falls back to placeholder
            return self._create_placeholder(stage, path, entry, resolved, entry_id)
        else:
            if entry_id == "__placeholder__":
                return self._create_placeholder(stage, path, entry, resolved, entry_id)
            result = entry.adapter.create(stage, path, resolved)
            if result:
                prim = result.GetPrim() if hasattr(result, 'GetPrim') else result
                prim.SetCustomDataByKey("ieip:entry_id", entry.id)
                prim.SetCustomDataByKey("ieip:detail_level", int(detail_level))
                for k, v in resolved.items():
                    self._store_param(prim, k, v)
            return result

    def _resolve_defaults(self, entry: EquipmentEntry,
                          params: Dict[str, Any]) -> Dict[str, Any]:
        resolved = {}
        for pdef in entry.params:
            if pdef.name in params:
                resolved[pdef.name] = params[pdef.name]
            else:
                resolved[pdef.name] = pdef.default
        return resolved

    def _store_param(self, prim, key: str, value):
        """Store a parameter value in ieip: namespace custom data."""
        if isinstance(value, (int, float, str, bool)):
            prim.SetCustomDataByKey(f"ieip:param:{key}", value)

    def _create_placeholder(self, stage, path, entry, params, entry_id):
        from pxr import UsdGeom, Gf, Sdf

        bbox = self._estimate_bounding_box(entry, params)
        w, h, d = bbox

        xform = UsdGeom.Xform.Define(stage, path)
        cube_path = f"{path}/Placeholder"
        cube = UsdGeom.Cube.Define(stage, cube_path)
        cube.GetSizeAttr().Set(1.0)

        xformable = UsdGeom.Xformable(cube)
        xformable.AddScaleOp().Set(Gf.Vec3f(w, h, d))
        # Translate so bottom of box sits at Y=0
        xformable.AddTranslateOp().Set(Gf.Vec3d(0, h / 2.0, 0))

        CATEGORY_COLORS = {
            "MEP Systems": Gf.Vec3f(0.2, 0.6, 0.2),
            "Structural": Gf.Vec3f(0.6, 0.3, 0.1),
            "Components": Gf.Vec3f(0.3, 0.3, 0.7),
            "Buildings & Enclosures": Gf.Vec3f(0.5, 0.4, 0.2),
        }

        top_category = ""
        if entry:
            top_category = entry.category.split("/")[0]
        color = CATEGORY_COLORS.get(top_category, Gf.Vec3f(0.5, 0.5, 0.5))
        cube.GetDisplayColorAttr().Set([color])
        cube.GetDisplayOpacityAttr().Set([0.4])

        prim = xform.GetPrim()
        actual_id = entry.id if entry else entry_id
        prim.SetCustomDataByKey("ieip:entry_id", actual_id)
        prim.SetCustomDataByKey("ieip:detail_level", int(DetailLevel.PLACEHOLDER))
        if entry:
            prim.SetCustomDataByKey("ieip:display_name", entry.name)
        else:
            prim.SetCustomDataByKey("ieip:display_name", params.get("label", "Placeholder"))

        for k, v in params.items():
            self._store_param(prim, k, v)

        return xform

    def regenerate_component(self, stage, prim_path: str,
                             new_params: Dict[str, Any] = None,
                             new_detail_level: "DetailLevel" = None):
        """Delete and recreate an IEIP component in place, preserving transform and connections."""
        from ..utils import usd_utils

        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            raise ValueError(f"No prim at {prim_path}")

        cd = prim.GetCustomData()
        entry_id = cd.get("ieip:entry_id")
        if not entry_id:
            raise ValueError(f"Not an IEIP component: {prim_path}")

        # Read stored params
        stored_params = {}
        for key, value in cd.items():
            if key.startswith("ieip:param:"):
                stored_params[key[len("ieip:param:"):]] = value

        # Merge with overrides
        if new_params:
            stored_params.update(new_params)

        detail_level = new_detail_level
        if detail_level is None:
            detail_level = DetailLevel(cd.get("ieip:detail_level", int(DetailLevel.PARAMETRIC)))

        # Preserve transform
        current_transform = usd_utils.get_local_transform(prim)

        # Preserve assembly membership
        assembly_component_id = cd.get("ieip:assembly_component_id")
        assembly_path = cd.get("ieip:assembly_path")

        # Capture port connections
        connections = self._capture_port_connections(stage, prim)

        # Delete and recreate
        stage.RemovePrim(prim_path)
        result = self.create_component(entry_id, stage, prim_path, stored_params, detail_level)

        if result:
            new_prim = stage.GetPrimAtPath(prim_path)
            if new_prim:
                # Restore transform
                if current_transform:
                    usd_utils.set_local_transform(new_prim, current_transform)
                # Restore assembly metadata
                if assembly_component_id:
                    new_prim.SetCustomDataByKey("ieip:assembly_component_id", assembly_component_id)
                if assembly_path:
                    new_prim.SetCustomDataByKey("ieip:assembly_path", assembly_path)
                # Restore port connections
                if connections:
                    self._restore_port_connections(stage, new_prim, connections)

        return result

    def _capture_port_connections(self, stage, prim) -> Dict[str, list]:
        """Capture twin:connected_to relationships by port name."""
        connections = {}
        for child in prim.GetAllChildren():
            if child.HasAttribute("twin:is_port"):
                is_port = child.GetAttribute("twin:is_port")
                if is_port and is_port.IsValid() and is_port.HasValue() and is_port.Get():
                    rel = child.GetRelationship("twin:connected_to")
                    if rel:
                        targets = rel.GetTargets()
                        if targets:
                            connections[child.GetName()] = [str(t) for t in targets]
        return connections

    def _restore_port_connections(self, stage, new_prim, connections: Dict[str, list]):
        """Restore twin:connected_to relationships by matching port names."""
        from pxr import Sdf
        for child in new_prim.GetAllChildren():
            if child.HasAttribute("twin:is_port"):
                is_port = child.GetAttribute("twin:is_port")
                if is_port and is_port.IsValid() and is_port.HasValue() and is_port.Get():
                    port_name = child.GetName()
                    if port_name in connections:
                        rel = child.CreateRelationship("twin:connected_to", custom=False)
                        target_paths = [Sdf.Path(p) for p in connections[port_name]]
                        rel.SetTargets(target_paths)

    def _estimate_bounding_box(self, entry, params) -> Tuple[float, float, float]:
        if entry is None:
            w = params.get("width", 24.0)
            h = params.get("height", 24.0)
            d = params.get("depth", 24.0)
            return (float(w), float(h), float(d))

        cat = entry.category.lower()
        if "fan" in cat:
            size = float(params.get("fan_size", 36))
            return (size * 1.3, size * 1.5, size * 0.9)
        elif "duct" in cat:
            w = float(params.get("width", 20))
            h = float(params.get("height", 10))
            l = float(params.get("length", 24))
            return (w, h, l)
        elif "flange" in entry.id or "beam" in entry.id:
            d = float(params.get("depth", 12))
            bf = float(params.get("flange_width", 6))
            l = float(params.get("length", 120))
            return (bf, d, l)
        elif "trapeze" in entry.id:
            span = float(params.get("span", 24))
            drop = float(params.get("drop_length", 36))
            return (span + 4, drop, 2.0)
        elif "stair" in entry.id:
            rise = float(params.get("total_rise", 120))
            width = float(params.get("width", 36))
            run = float(params.get("run", 10))
            num_treads = int(rise / 7.5)
            return (width, rise, run * num_treads)

        return (24.0, 24.0, 24.0)
