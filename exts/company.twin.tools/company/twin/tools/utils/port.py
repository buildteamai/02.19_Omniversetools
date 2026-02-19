# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

from pxr import Usd, UsdGeom, Gf, Sdf

class Port:
    """
    Represents a semantic connection point (Port) in the USD stage.
    Wraps UsdGeom.Xform with specific metadata for mating.
    """
    
    def __init__(self, prim):
        self.prim = prim
        self.xform = UsdGeom.Xform(prim)
        
    @classmethod
    def define(cls, stage, parent_path, name, position, direction, port_type="HVAC", shape="Rectangular", width=0.0, height=0.0, diameter=None):
        """
        Defines a new Port prim.
        
        Args:
            stage: USD Stage
            parent_path: Path to parent object
            name: Name of the port prim (e.g., 'Port_Start')
            position: Gf.Vec3d position (relative to parent)
            direction: Gf.Vec3d direction (Outward normal)
            port_type: "HVAC", "Electrical", etc.
            shape: "Rectangular", "Round"
            width: Width (Rectangular) or Diameter (if diameter arg not used)
            height: Height (Rectangular)
            diameter: Optional explicit diameter for Round ports
        """
        port_path = f"{parent_path}/{name}"
        xform = UsdGeom.Xform.Define(stage, port_path)
        
        # 1. Set Transform
        # Position
        xform.AddTranslateOp().Set(position)
        
        # Orientation (LookAt)
        # Z-axis must point in 'direction' (Outward)
        # Standard USD/OpenGL: Z is typically 'Up' or 'Forward' depending on convention.
        # Logic: We want Local Z to align with World Direction.
        
        xaxis = Gf.Vec3d(1, 0, 0) # Arbitrary reference
        if abs(Gf.Dot(direction, xaxis)) > 0.99:
            xaxis = Gf.Vec3d(0, 1, 0)
            
        zaxis = direction.GetNormalized()
        yaxis = Gf.Cross(zaxis, xaxis).GetNormalized()
        xaxis = Gf.Cross(yaxis, zaxis).GetNormalized()
        
        # Create Matrix: X, Y, Z basis vectors
        mat = Gf.Matrix4d()
        mat.SetRow(0, Gf.Vec4d(xaxis[0], xaxis[1], xaxis[2], 0))
        mat.SetRow(1, Gf.Vec4d(yaxis[0], yaxis[1], yaxis[2], 0))
        mat.SetRow(2, Gf.Vec4d(zaxis[0], zaxis[1], zaxis[2], 0))
        mat.SetRow(3, Gf.Vec4d(0, 0, 0, 1))
        
        quatd = mat.ExtractRotation().GetQuat()
        quatf = Gf.Quatf(quatd.GetReal(), Gf.Vec3f(quatd.GetImaginary()))
        xform.AddOrientOp().Set(quatf)
        
        # 2. Set Metadata (Custom Attributes)
        prim = xform.GetPrim()
        cls._set_attr(prim, "twin:is_port", True, Sdf.ValueTypeNames.Bool)
        cls._set_attr(prim, "twin:port_type", port_type, Sdf.ValueTypeNames.String)
        cls._set_attr(prim, "twin:port_shape", shape, Sdf.ValueTypeNames.String)
        
        # Handle Round vs Rectangular dimensions
        if shape.lower() == "round" or shape.lower() == "circular":
            curr_diameter = diameter if diameter is not None else width
            cls._set_attr(prim, "twin:port_diameter", float(curr_diameter), Sdf.ValueTypeNames.Double)
        else:
            cls._set_attr(prim, "twin:port_width", float(width), Sdf.ValueTypeNames.Double)
            cls._set_attr(prim, "twin:port_height", float(height), Sdf.ValueTypeNames.Double)
        
        # Visualization (Selectable Proxy)
        # Create a small cube to make the port selectable
        viz_path = f"{port_path}/viz"
        viz = UsdGeom.Cube.Define(stage, viz_path)
        viz.GetSizeAttr().Set(2.0)  # 2 inch cube
        
        # Color it based on name (Green for start, Red for end if applicable, or generic Blue)
        color = Gf.Vec3f(0, 0.5, 1) # Default Blue
        if "start" in name.lower():
            color = Gf.Vec3f(0, 1, 0) # Green
        elif "end" in name.lower():
            color = Gf.Vec3f(1, 0, 0) # Red
            
        viz.GetDisplayColorAttr().Set([color])
        
        return cls(prim)

    @staticmethod
    def _set_attr(prim, name, value, type_name):
        attr = prim.CreateAttribute(name, type_name)
        attr.Set(value)
        return attr

    def connect_to(self, target_port_prim):
        """
        Establishes a logical connection to another port.
        """
        rel = self.prim.CreateRelationship("twin:connected_to", custom=False)
        rel.SetTargets([target_port_prim.GetPath()])
