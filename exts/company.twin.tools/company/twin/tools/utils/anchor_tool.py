# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Anchor Tool Window

Provides a UI context for interacting with Anchor Prims.
Specifically allows for 6-DOF rotation manipulation.
"""

import omni.ui as ui
import omni.usd
from pxr import Usd, UsdGeom, Gf

class AnchorToolWindow(ui.Window):
    """
    Context-aware window for Anchor manipulation.
    Should be invoked when an Anchor is selected.
    """
    
    def __init__(self, title: str = "Anchor Tool"):
        super().__init__(title, width=250, height=200)
        self.frame.set_build_fn(self._build_ui)
        self._selection = omni.usd.get_context().get_selection()
        self._selected_path = None
        
        # Subscribe to selection updates (if needed, or just refresh on open)
        # For a context menu tool, it usually opens with the current selection.
        self._on_selection_changed()
        
    def _on_selection_changed(self):
        """Updates internal state based on current selection."""
        paths = self._selection.get_selected_prim_paths()
        if paths:
            self._selected_path = paths[0]
            # Verify if it's an anchor
            stage = omni.usd.get_context().get_stage()
            prim = stage.GetPrimAtPath(self._selected_path)
            if not prim.HasAttribute("twin:is_anchor"):
                self._selected_path = None
        else:
            self._selected_path = None
            
        self.frame.rebuild()
            
    def _build_ui(self):
        """Builds the UI."""
        with self.frame:
            with ui.VStack(spacing=5):
                ui.Label("Anchor Rotation", height=20, alignment=ui.Alignment.CENTER)
                
                if not self._selected_path:
                    ui.Label("No Anchor Selected", style={"color": 0xFF888888}, alignment=ui.Alignment.CENTER)
                    ui.Button("Refresh Selection", clicked_fn=self._on_selection_changed)
                    return

                # Show Anchor Info
                stage = omni.usd.get_context().get_stage()
                prim = stage.GetPrimAtPath(self._selected_path)
                anchor_type_attr = prim.GetAttribute("twin:anchor_type")
                anchor_type = anchor_type_attr.Get() if anchor_type_attr and anchor_type_attr.IsValid() and anchor_type_attr.HasValue() else "Unknown"
                ui.Label(f"Selected: {anchor_type}", style={"color": 0xFF88FF88}, alignment=ui.Alignment.CENTER)
                
                ui.Spacer(height=5)
                
                # Rotation Controls
                # X Axis
                with ui.HStack(height=30):
                    ui.Label("X:", width=30)
                    ui.Button("-90°", clicked_fn=lambda: self._rotate_anchor(0, -90))
                    ui.Button("+90°", clicked_fn=lambda: self._rotate_anchor(0, 90))
                    
                # Y Axis
                with ui.HStack(height=30):
                    ui.Label("Y:", width=30)
                    ui.Button("-90°", clicked_fn=lambda: self._rotate_anchor(1, -90))
                    ui.Button("+90°", clicked_fn=lambda: self._rotate_anchor(1, 90))
                    
                # Z Axis
                with ui.HStack(height=30):
                    ui.Label("Z:", width=30)
                    ui.Button("-90°", clicked_fn=lambda: self._rotate_anchor(2, -90))
                    ui.Button("+90°", clicked_fn=lambda: self._rotate_anchor(2, 90))

    def _rotate_anchor(self, axis_idx, angle_deg):
        """
        Rotates the selected anchor by angle_deg around axis_idx (0=X, 1=Y, 2=Z).
        Uses Local Rotation.
        """
        if not self._selected_path:
            return
            
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(self._selected_path)
        
        xform_api = UsdGeom.XformCommonAPI(prim)
        
        # Get current rotation
        # Note: GetXformVectors returns (translation, rotation, scale, pivot, shear)
        # rotation is Gf.Vec3f (Euler XYZ usually)
        # But wait, SetRotate takes Vec3f, GetRotate depends on API version
        # Let's use ops if possible, or XformCommonAPI helpers
        
        # Warning: GetXformVectors expects a specific timecode
        current_trans, current_rot, current_scale, _, _ = xform_api.GetXformVectors(Usd.TimeCode.Default())
        
        # Construct rotation delta
        # We want to append a rotation in LOCAL space.
        # Simple addition of Euler angles works IF the rotation order matches and we are just tweaking.
        # But for 6-DOF, we should use Matrices to be robust.
        
        # 1. Convert current transform to Matrix
        current_mat = xform_api.GetLocalTransformation(Usd.TimeCode.Default())
        
        # 2. Construct Delta Matrix
        delta_vec = Gf.Vec3d(0, 0, 0)
        if axis_idx == 0: delta_vec = Gf.Vec3d.XAxis()
        elif axis_idx == 1: delta_vec = Gf.Vec3d.YAxis()
        elif axis_idx == 2: delta_vec = Gf.Vec3d.ZAxis()
        
        # Gf.Rotation(axis, angle)
        delta_rot = Gf.Rotation(delta_vec, angle_deg)
        delta_mat = Gf.Matrix4d()
        delta_mat.SetRotate(delta_rot)
        
        # 3. Apply: New = Delta * Old (Pre-multiply for global? Post-multiply for local?)
        # If we want to rotate around the anchor's OWN axes (Intrinsic), we multiply: Old * Delta
        new_mat = delta_mat * current_mat # Wait, verify order for USD matrices (Row vs Column major)
        # USD uses Row-Major interaction but Stores Row-Major? 
        # Actually GfMatrix4d is standard.
        # Usually: Global = Local * Parent
        # We want to rotate the Local frame.
        # Is it "Rotate THEN Translate" or "Translate THEN Rotate"?
        # XformCommonAPI enforces Translate, Rotate, Scale order usually.
        
        # If we use XformCommonAPI, we must stick to setting T, R, S values.
        # So we can't easily just multiply matrices and put it back unless we decompose.
        # AND XformCommonAPI only supports a single rotate op (usually Euler XYZ).
        
        # Alternative: Just add to the rotation value if axis aligned?
        # If current is (0, 90, 0) and we rotate X by 90...
        # Result might be gimbal lock prone if we just add.
        
        # Let's try decomposing the NEW matrix back into Euler angles.
        # new_mat = current_mat * delta_mat # Post-multiply for local axis rotation
        # Wait, if I have a transform T, and I want to rotate it locally by R...
        # T_new = T * R? No.
        # If T = Translate * Rotate
        # We want T_new = Translate * Rotate * DeltaRot
        # So yes, we modify the Rotation component.
        
        # Deconstruct current rotation
        base_rot = Gf.Rotation(Gf.Vec3d.XAxis(), current_rot[0]) * \
                   Gf.Rotation(Gf.Vec3d.YAxis(), current_rot[1]) * \
                   Gf.Rotation(Gf.Vec3d.ZAxis(), current_rot[2])
                   
        # Apply delta
        new_rot_combined = base_rot * delta_rot # base first, then delta? Use * operator logic for GfRotation.
        # GfRotation composition: r1 * r2 applies r1, then r2.
        
        # Extract Euler Angles (XYZ)
        new_euler = new_rot_combined.Decompose(Gf.Vec3d.XAxis(), Gf.Vec3d.YAxis(), Gf.Vec3d.ZAxis())
        
        # Apply back to API
        xform_api.SetRotate(Gf.Vec3f(new_euler[0], new_euler[1], new_euler[2]))
        
        # Reload status
        self.frame.rebuild()
