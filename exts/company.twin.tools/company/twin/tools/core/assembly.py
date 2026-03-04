# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Assembly System - Defines and instantiates multi-component assemblies.

An assembly is a composition of registered generators with spatial
relationships, port connections, and parameter linking.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import json
import os

from .equipment_registry import EquipmentRegistry, DetailLevel


@dataclass
class ComponentDef:
    """A single component within an assembly."""
    id: str
    entry_id: str
    params: Dict[str, Any] = field(default_factory=dict)
    detail_level: DetailLevel = DetailLevel.PARAMETRIC
    translate: Tuple[float, float, float] = (0, 0, 0)
    rotate: Tuple[float, float, float] = (0, 0, 0)


@dataclass
class ConnectionDef:
    """Port-to-port connection between two components."""
    source_component: str
    source_port: str
    target_component: str
    target_port: str


@dataclass
class ParamLink:
    """Links a parameter from one component to another."""
    source_component: str
    source_param: str
    target_component: str
    target_param: str
    transform: str = "direct"  # "direct", "add:N", "multiply:N"


@dataclass
class AssemblyDef:
    """Complete definition of an equipment assembly."""
    id: str
    name: str
    category: str
    description: str = ""
    components: List[ComponentDef] = field(default_factory=list)
    connections: List[ConnectionDef] = field(default_factory=list)
    param_links: List[ParamLink] = field(default_factory=list)
    exposed_params: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class AssemblyEngine:
    """Instantiates assemblies on the USD stage."""

    @staticmethod
    def create_assembly(
        stage, path: str, assembly_def: AssemblyDef,
        param_overrides: Dict[str, Any] = None,
        global_detail_level: DetailLevel = None,
    ):
        from pxr import UsdGeom, Gf

        registry = EquipmentRegistry.instance()
        overrides = param_overrides or {}

        # Create root Xform
        root = UsdGeom.Xform.Define(stage, path)
        root_prim = root.GetPrim()
        root_prim.SetCustomDataByKey("ieip:is_assembly", True)
        root_prim.SetCustomDataByKey("ieip:assembly_id", assembly_def.id)
        root_prim.SetCustomDataByKey("ieip:assembly_name", assembly_def.name)

        # Resolve parameter links
        resolved_params = AssemblyEngine._resolve_params(assembly_def, overrides)

        # Identify which components are connection targets (positioned by port snap)
        connection_targets = {c.target_component for c in assembly_def.connections}

        # Create each component
        created_prims = {}
        for comp in assembly_def.components:
            comp_path = f"{path}/{comp.id}"
            comp_params = dict(comp.params)
            if comp.id in resolved_params:
                comp_params.update(resolved_params[comp.id])

            dl = global_detail_level if global_detail_level is not None else comp.detail_level

            result = registry.create_component(
                comp.entry_id, stage, comp_path, comp_params, dl
            )

            if result is None and comp.entry_id != "__placeholder__":
                fallback_params = dict(comp_params)
                fallback_params.setdefault("label", f"{comp.entry_id} (unavailable)")
                fallback_params.setdefault("width", 24.0)
                fallback_params.setdefault("height", 24.0)
                fallback_params.setdefault("depth", 24.0)
                result = registry.create_component(
                    "__placeholder__", stage, comp_path, fallback_params,
                    DetailLevel.PLACEHOLDER
                )
                print(f"[IEIP Assembly] Degraded '{comp.entry_id}' to placeholder at {comp_path}")

            if result:
                created_prims[comp.id] = comp_path
                # Apply static transform if NOT a port-connection target
                if comp.id not in connection_targets:
                    prim = stage.GetPrimAtPath(comp_path)
                    if prim:
                        xform = UsdGeom.Xformable(prim)
                        if comp.translate != (0, 0, 0):
                            xform.AddTranslateOp().Set(Gf.Vec3d(*comp.translate))
                        if comp.rotate != (0, 0, 0):
                            xform.AddRotateXYZOp().Set(Gf.Vec3f(*comp.rotate))

                # Tag as assembly member
                prim = stage.GetPrimAtPath(comp_path)
                if prim:
                    prim.SetCustomDataByKey("ieip:assembly_component_id", comp.id)
                    prim.SetCustomDataByKey("ieip:assembly_path", path)

        # Apply port-to-port connections
        for conn in assembly_def.connections:
            if conn.source_component in created_prims and conn.target_component in created_prims:
                AssemblyEngine._connect_ports(
                    stage,
                    created_prims[conn.source_component], conn.source_port,
                    created_prims[conn.target_component], conn.target_port,
                )

        # Store serialized assembly def for future updates
        root_prim.SetCustomDataByKey(
            "ieip:assembly_json",
            json.dumps(AssemblyEngine._serialize_def(assembly_def))
        )

        count = len(created_prims)
        total = len(assembly_def.components)
        print(f"[IEIP Assembly] Created '{assembly_def.name}' "
              f"({count}/{total} components) at {path}")
        return root

    @staticmethod
    def _resolve_params(assembly_def: AssemblyDef,
                        overrides: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        resolved = {}

        # Apply exposed param overrides
        for assembly_param, target_ref in assembly_def.exposed_params.items():
            if assembly_param in overrides:
                parts = target_ref.split(".", 1)
                if len(parts) == 2:
                    comp_id, param_name = parts
                    if comp_id not in resolved:
                        resolved[comp_id] = {}
                    resolved[comp_id][param_name] = overrides[assembly_param]

        # Apply param links
        for link in assembly_def.param_links:
            src_value = None
            # Check resolved overrides first
            if (link.source_component in resolved
                    and link.source_param in resolved[link.source_component]):
                src_value = resolved[link.source_component][link.source_param]
            else:
                # Fall back to component defaults
                for comp in assembly_def.components:
                    if comp.id == link.source_component:
                        src_value = comp.params.get(link.source_param)
                        break

            if src_value is not None:
                target_value = AssemblyEngine._apply_transform(src_value, link.transform)
                if link.target_component not in resolved:
                    resolved[link.target_component] = {}
                resolved[link.target_component][link.target_param] = target_value

        return resolved

    @staticmethod
    def _apply_transform(value, transform: str):
        if transform == "direct":
            return value
        try:
            if transform.startswith("add:"):
                return value + float(transform.split(":")[1])
            elif transform.startswith("multiply:"):
                return value * float(transform.split(":")[1])
        except (ValueError, IndexError):
            pass
        return value

    @staticmethod
    def _connect_ports(stage, source_path, source_port_name,
                       target_path, target_port_name):
        try:
            from ..utils.mating import MatingSystem
        except ImportError:
            print("[IEIP Assembly] MatingSystem not available, skipping port connection")
            return False

        source_prim = stage.GetPrimAtPath(source_path)
        target_prim = stage.GetPrimAtPath(target_path)
        if not source_prim or not target_prim:
            return False

        source_ports = MatingSystem.find_ports(source_prim)
        target_ports = MatingSystem.find_ports(target_prim)

        s_port = next((p for p in source_ports
                       if p.prim.GetName() == source_port_name), None)
        t_port = next((p for p in target_ports
                       if p.prim.GetName() == target_port_name), None)

        if s_port and t_port:
            return MatingSystem.snap(t_port, s_port)
        else:
            print(f"[IEIP Assembly] Port not found: "
                  f"{source_port_name} or {target_port_name}")
            return False

    @staticmethod
    def upgrade_detail_level(stage, prim_path: str, new_level: DetailLevel):
        """Upgrade or downgrade a component's detail level, preserving transform."""
        registry = EquipmentRegistry.instance()
        try:
            return registry.regenerate_component(stage, prim_path, new_detail_level=new_level)
        except ValueError as e:
            print(f"[IEIP Assembly] {e}")
            return None

    @staticmethod
    def _serialize_def(assembly_def: AssemblyDef) -> dict:
        return {
            "id": assembly_def.id,
            "name": assembly_def.name,
            "category": assembly_def.category,
            "description": assembly_def.description,
            "components": [
                {
                    "id": c.id,
                    "entry_id": c.entry_id,
                    "params": c.params,
                    "detail_level": int(c.detail_level),
                    "translate": list(c.translate),
                    "rotate": list(c.rotate),
                }
                for c in assembly_def.components
            ],
            "connections": [
                {
                    "source_component": c.source_component,
                    "source_port": c.source_port,
                    "target_component": c.target_component,
                    "target_port": c.target_port,
                }
                for c in assembly_def.connections
            ],
            "param_links": [
                {
                    "source_component": l.source_component,
                    "source_param": l.source_param,
                    "target_component": l.target_component,
                    "target_param": l.target_param,
                    "transform": l.transform,
                }
                for l in assembly_def.param_links
            ],
            "exposed_params": assembly_def.exposed_params,
            "tags": assembly_def.tags,
        }

    @staticmethod
    def load_assembly_from_json(data: dict) -> AssemblyDef:
        """Convert JSON dict to AssemblyDef dataclass."""
        components = []
        for c in data.get("components", []):
            components.append(ComponentDef(
                id=c["id"],
                entry_id=c["entry_id"],
                params=c.get("params", {}),
                detail_level=DetailLevel(c.get("detail_level", 2)),
                translate=tuple(c.get("translate", [0, 0, 0])),
                rotate=tuple(c.get("rotate", [0, 0, 0])),
            ))

        connections = []
        for c in data.get("connections", []):
            connections.append(ConnectionDef(
                source_component=c["source_component"],
                source_port=c["source_port"],
                target_component=c["target_component"],
                target_port=c["target_port"],
            ))

        param_links = []
        for l in data.get("param_links", []):
            param_links.append(ParamLink(
                source_component=l["source_component"],
                source_param=l["source_param"],
                target_component=l["target_component"],
                target_param=l["target_param"],
                transform=l.get("transform", "direct"),
            ))

        return AssemblyDef(
            id=data["id"],
            name=data["name"],
            category=data.get("category", "Assemblies"),
            description=data.get("description", ""),
            components=components,
            connections=connections,
            param_links=param_links,
            exposed_params=data.get("exposed_params", {}),
            tags=data.get("tags", []),
        )
