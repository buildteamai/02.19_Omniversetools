# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

from pxr import Usd, UsdGeom, Gf, Sdf
from .port import Port

class MatingSystem:
    """
    Logic for mating objects via their Ports.
    """
    
    @staticmethod
    def find_ports(prim):
        """
        Recursively finds all Ports on a Prim (and its children).
        Returns a list of Port objects.
        """
        ports = []
        if not prim or not prim.IsValid():
            return ports
            
        # Check if this prim is a port
        if prim.HasAttribute("twin:is_port"):
            is_port_attr = prim.GetAttribute("twin:is_port")
            if is_port_attr and is_port_attr.IsValid() and is_port_attr.HasValue() and is_port_attr.Get():
                ports.append(Port(prim))
            
        # Recurse children
        for child in prim.GetChildren():
            ports.extend(MatingSystem.find_ports(child))
            
        return ports

    @staticmethod
    def snap(source_port: Port, target_port: Port):
        """
        Snaps the Source Object (parent of source_port) to the Target Port.
        Aligns source_port to be anti-parallel to target_port (flanges touching, facing each other).
        """
        stage = source_port.prim.GetStage()
        
        # 1. Get World Transforms
        time = Usd.TimeCode.Default()
        xform_cache = UsdGeom.XformCache(time)
        
        # Target World Transform
        t_target_world = xform_cache.GetLocalToWorldTransform(target_port.prim)
        
        # Source Port Local Transform (Relative to Source Object Root)
        source_object_prim = source_port.prim.GetParent()
        t_source_local = source_port.xform.GetLocalTransformation(time)
        
        # 2. Extract Target Basis Vectors (World Space)
        # USD Matrix is Row-Major: Row 0 = X axis, Row 1 = Y axis, Row 2 = Z axis
        target_x = Gf.Vec3d(t_target_world.GetRow(0)[:3]).GetNormalized()  # Flow direction (outward)
        target_y = Gf.Vec3d(t_target_world.GetRow(1)[:3]).GetNormalized()  # Right
        target_z = Gf.Vec3d(t_target_world.GetRow(2)[:3]).GetNormalized()  # Up
        target_pos = t_target_world.ExtractTranslation()
        
        # 3. Construct Goal Basis for Source Port (World Space)
        # We want flanges to FACE each other:
        # - Source X (flow) should point OPPOSITE to Target X (anti-parallel)
        # - Source Z (up) should match Target Z (same orientation)
        # - Source Y is computed via cross product
        goal_x = -target_x  # Anti-parallel flow
        goal_z = target_z   # Up stays up
        goal_y = Gf.Cross(goal_z, goal_x).GetNormalized()  # Recompute right
        # Re-orthogonalize Z just in case
        goal_z = Gf.Cross(goal_x, goal_y).GetNormalized()
        
        # 4. Construct Goal Transform Matrix for Source Port
        t_goal_port_world = Gf.Matrix4d()
        t_goal_port_world.SetRow(0, Gf.Vec4d(goal_x[0], goal_x[1], goal_x[2], 0))
        t_goal_port_world.SetRow(1, Gf.Vec4d(goal_y[0], goal_y[1], goal_y[2], 0))
        t_goal_port_world.SetRow(2, Gf.Vec4d(goal_z[0], goal_z[1], goal_z[2], 0))
        t_goal_port_world.SetRow(3, Gf.Vec4d(target_pos[0], target_pos[1], target_pos[2], 1))
        
        # 5. Solve for Object Root Transform
        # v_world = v_port_local * M_port_local * M_obj_world
        # M_port_local * M_obj_world = T_goal_port_world
        # M_obj_world = Inverse(M_port_local) * T_goal_port_world
        t_source_local_inv = t_source_local.GetInverse()
        t_new_object_world = t_source_local_inv * t_goal_port_world
        
        # 6. Apply to Source Object
        source_xform = UsdGeom.Xformable(source_object_prim)
        source_xform.ClearXformOpOrder()
        op = source_xform.AddTransformOp()
        op.Set(t_new_object_world)
        
        # 7. Connect
        source_port.connect_to(target_port.prim)
        target_port.connect_to(source_port.prim)
        
        return True

    @staticmethod
    def rotate_mated(source_port: Port, angle_deg: float):
        """
        Rotates the Source Object around the Source Port's local X-axis (Flow Axis).
        Useful for adjusting clocking after mating (e.g., rotating flange bolt holes).
        
        Args:
            source_port: The Port on the object to rotate.
            angle_deg: Rotation angle in degrees.
        """
        source_object_prim = source_port.prim.GetParent()
        if not source_object_prim:
            return False
            
        stage = source_port.prim.GetStage()
        time = Usd.TimeCode.Default()
        
        # We want to apply a rotation R around the local X-axis of the Source Port.
        # But we must apply this to the Source Object Transform.
        
        # T_port_world = T_port_local * T_obj_world
        # We want T_port_world_new = R_local_x * T_port_world (Rotate in Port Frame?)
        # No, we want to rotate the object around the Port Axis.
        # This is equivalent to rotating the PORT frame around its X axis, and having the object follow.
        # T_port_world_new = T_port_world * R_local_x ?
        # If we act in World Frame:
        # Axis = Port X World Axis.
        # Pivot = Port World Position.
        
        xform_cache = UsdGeom.XformCache(time)
        t_port_world = xform_cache.GetLocalToWorldTransform(source_port.prim)
        
        # Extract Axis and Pivot
        pivot = t_port_world.ExtractTranslation()
        
        # Port X axis is the first row of the matrix (if Row-Major and no scale)
        # Gf Matrix is Row-Major.
        xaxis = Gf.Vec3d(t_port_world.GetRow(0)[:3]).GetNormalized()
        
        # Construct Rotation Transform around this axis/pivot
        # Translate(-Pivot) * Rotate(Axis, Angle) * Translate(Pivot)
        m_rot = Gf.Matrix4d().SetRotate(Gf.Rotation(xaxis, angle_deg))
        
        # Since we want to rotate around a PIVOT, not origin:
        m_trans_inv = Gf.Matrix4d().SetTranslate(-pivot)
        m_trans = Gf.Matrix4d().SetTranslate(pivot)
        
        target_transform = m_trans_inv * m_rot * m_trans
        
        # Now apply this Delta Transform to the Object's existing World Transform
        # T_obj_new = T_obj_old * target_transform
        
        t_obj_world = xform_cache.GetLocalToWorldTransform(source_object_prim)
        t_obj_new = t_obj_world * target_transform
        
        # Apply to Object
        source_xform = UsdGeom.Xformable(source_object_prim)
        source_xform.ClearXformOpOrder()
        op = source_xform.AddTransformOp()
        op.Set(t_obj_new)
        
        return True

    @staticmethod
    def propagate_dimensions(source_prim):
        """
        Propagates dimensions from source_prim to all connected prims.
        Reads source's diameter/width/height and applies to connected ports' parent objects.
        
        Args:
            source_prim: The prim whose dimensions should be propagated.
            
        Returns:
            Number of objects updated.
        """
        stage = source_prim.GetStage()
        updated_count = 0
        
        # 1. Find all ports on source
        source_ports = MatingSystem.find_ports(source_prim)
        
        # 2. Read source dimensions from customData or attributes
        source_diameter = source_prim.GetCustomDataByKey('diameter')
        source_width = source_prim.GetCustomDataByKey('width')
        source_height = source_prim.GetCustomDataByKey('height')
        source_shape = "Circular" if source_diameter else "Rectangular"
        
        print(f"[MatingSystem] Propagating: D={source_diameter}, W={source_width}, H={source_height}")
        
        # 3. For each port, check for connections
        for port in source_ports:
            # Get connection relationship
            rel = port.prim.GetRelationship("twin:connected_to")
            if not rel:
                continue
                
            targets = rel.GetTargets()
            for target_path in targets:
                target_prim = stage.GetPrimAtPath(target_path)
                if not target_prim.IsValid():
                    continue
                    
                # Get parent object of target port
                target_object = target_prim.GetParent()
                if not target_object.IsValid():
                    continue
                
                print(f"[MatingSystem] Updating connected object: {target_object.GetPath()}")
                
                # 4. Update target object's dimensions
                # Check if it has matching customData keys
                if source_diameter is not None:
                    target_object.SetCustomDataByKey('diameter', source_diameter)
                    # Also update port attributes
                    target_prim.GetAttribute("twin:port_diameter").Set(source_diameter) if target_prim.HasAttribute("twin:port_diameter") else None
                    
                if source_width is not None:
                    target_object.SetCustomDataByKey('width', source_width)
                    target_prim.GetAttribute("twin:port_width").Set(source_width) if target_prim.HasAttribute("twin:port_width") else None
                    
                if source_height is not None:
                    target_object.SetCustomDataByKey('height', source_height)
                    target_prim.GetAttribute("twin:port_height").Set(source_height) if target_prim.HasAttribute("twin:port_height") else None
                
                # 5. Regenerate geometry
                MatingSystem._regenerate_object(stage, target_object)
                
                updated_count += 1
        
        return updated_count
    
    @staticmethod
    def _regenerate_object(stage, prim):
        """
        Helper to regenerate geometry for a prim based on its generatorType.
        """
        gen_type = prim.GetCustomDataByKey('generatorType')
        if not gen_type:
            print(f"[MatingSystem] No generatorType on {prim.GetPath()}, cannot regenerate")
            return
        
        # Import here to avoid circular imports
        from ..objects.duct_warp import DuctWarpGenerator
        
        if gen_type.startswith('duct_') or gen_type.startswith('pipe_'):
            DuctWarpGenerator.regenerate(stage, prim)
        else:
            print(f"[MatingSystem] Unknown generatorType: {gen_type}")

    @staticmethod
    def get_connected_objects(source_prim):
        """
        Returns a list of all prims connected to source_prim via port relationships.
        """
        stage = source_prim.GetStage()
        connected = []
        
        source_ports = MatingSystem.find_ports(source_prim)
        for port in source_ports:
            rel = port.prim.GetRelationship("twin:connected_to")
            if not rel:
                continue
            for target_path in rel.GetTargets():
                target_prim = stage.GetPrimAtPath(target_path)
                if target_prim.IsValid():
                    parent = target_prim.GetParent()
                    if parent.IsValid() and parent not in connected:
                        connected.append(parent)
        
        return connected
