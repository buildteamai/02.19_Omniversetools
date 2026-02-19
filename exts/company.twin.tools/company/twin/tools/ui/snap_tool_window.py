# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Point-to-Point Snap Tool - Snap objects by picking points on them.
No pre-defined Ports required. Works on any object.
"""

import omni.ui as ui
import omni.usd
from pxr import Usd, UsdGeom, Gf, Sdf
import omni.kit.commands


class SnapToolWindow(ui.Window):
    def __init__(self, title="Point-to-Point Snap", **kwargs):
        super().__init__(title, width=450, height=400, **kwargs)
        
        self._source_prim = None
        self._source_point = None  # World-space point on source
        self._target_point = None  # World-space point on target
        
        self.frame.set_build_fn(self._build_ui)
        
    def _build_ui(self):
        with ui.VStack(spacing=8, style={"margin": 10}):
            ui.Label("Point-to-Point Snap Tool", style={"font_size": 18, "color": 0xFF00B4FF})
            ui.Line(height=2, style={"color": 0xFF333333})
            
            # Instructions
            ui.Label("Works on ANY object - no Ports required.", style={"color": 0xFF888888, "font_size": 11})
            
            ui.Spacer(height=10)
            
            # Step 1: Source Object
            ui.Label("Step 1: Source Object (will be moved)", style={"color": 0xFFFFFFFF})
            with ui.HStack(height=30):
                self._source_label = ui.Label("None", style={"color": 0xFF666666})
                ui.Button("Set from Selection", width=120, clicked_fn=self._on_set_source)
            
            ui.Spacer(height=5)
            
            # Step 2: Source Point
            ui.Label("Step 2: Source Point (grab point)", style={"color": 0xFFFFFFFF})
            with ui.HStack(height=30, spacing=5):
                ui.Label("X:", width=15, style={"color": 0xFFAAAAAA})
                self._src_x = ui.FloatField(width=60)
                self._src_x.model.set_value(0.0)
                ui.Label("Y:", width=15, style={"color": 0xFFAAAAAA})
                self._src_y = ui.FloatField(width=60)
                self._src_y.model.set_value(0.0)
                ui.Label("Z:", width=15, style={"color": 0xFFAAAAAA})
                self._src_z = ui.FloatField(width=60)
                self._src_z.model.set_value(0.0)
                ui.Button("Get Pos", width=60, clicked_fn=self._on_get_source_pos)
            
            ui.Spacer(height=10)
            
            # Step 3: Target Point
            ui.Label("Step 3: Target Point (snap to)", style={"color": 0xFFFFFFFF})
            with ui.HStack(height=30, spacing=5):
                ui.Label("X:", width=15, style={"color": 0xFFAAAAAA})
                self._tgt_x = ui.FloatField(width=60)
                self._tgt_x.model.set_value(0.0)
                ui.Label("Y:", width=15, style={"color": 0xFFAAAAAA})
                self._tgt_y = ui.FloatField(width=60)
                self._tgt_y.model.set_value(0.0)
                ui.Label("Z:", width=15, style={"color": 0xFFAAAAAA})
                self._tgt_z = ui.FloatField(width=60)
                self._tgt_z.model.set_value(0.0)
                ui.Button("Get Pos", width=60, clicked_fn=self._on_get_target_pos)
            
            ui.Spacer(height=15)
            
            # Snap Button
            ui.Button("SNAP!", height=45, clicked_fn=self._on_snap,
                     style={"background_color": 0xFF2B5B2B, "font_size": 16})
            
            ui.Spacer(height=10)
            self._status = ui.Label("Ready. Set source object, then enter/get points.", 
                                    style={"color": 0xFF888888}, word_wrap=True)
            
            ui.Spacer(height=5)
            
            # Helper buttons
            with ui.HStack(height=25):
                ui.Button("Use Origin (0,0,0) as Target", clicked_fn=self._set_target_origin,
                         style={"font_size": 11})
                ui.Button("Use Bounding Box Center", clicked_fn=self._use_bbox_center,
                         style={"font_size": 11})

    def _on_set_source(self):
        ctx = omni.usd.get_context()
        selection = ctx.get_selection().get_selected_prim_paths()
        if not selection:
            self._status.text = "Select an object first!"
            return
        
        path = selection[0]
        stage = ctx.get_stage()
        prim = stage.GetPrimAtPath(path)
        
        if not prim.IsValid():
            self._status.text = "Invalid selection!"
            return
        
        self._source_prim = prim
        self._source_label.text = prim.GetName()
        self._status.text = f"Source set to '{prim.GetName()}'. Now set source/target points."
        
        # Auto-fill source point with current position
        xformable = UsdGeom.Xformable(prim)
        if xformable:
            xform_cache = UsdGeom.XformCache()
            world_mat = xform_cache.GetLocalToWorldTransform(prim)
            pos = world_mat.ExtractTranslation()
            self._src_x.model.set_value(pos[0])
            self._src_y.model.set_value(pos[1])
            self._src_z.model.set_value(pos[2])

    def _on_get_source_pos(self):
        """Get position from current selection as source point."""
        ctx = omni.usd.get_context()
        selection = ctx.get_selection().get_selected_prim_paths()
        if not selection:
            self._status.text = "Select an object to get its position!"
            return
        
        stage = ctx.get_stage()
        prim = stage.GetPrimAtPath(selection[0])
        xformable = UsdGeom.Xformable(prim)
        if xformable:
            xform_cache = UsdGeom.XformCache()
            world_mat = xform_cache.GetLocalToWorldTransform(prim)
            pos = world_mat.ExtractTranslation()
            self._src_x.model.set_value(pos[0])
            self._src_y.model.set_value(pos[1])
            self._src_z.model.set_value(pos[2])
            self._status.text = f"Source point set to ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})"

    def _on_get_target_pos(self):
        """Get position from current selection as target point."""
        ctx = omni.usd.get_context()
        selection = ctx.get_selection().get_selected_prim_paths()
        if not selection:
            self._status.text = "Select an object to get its position!"
            return
        
        stage = ctx.get_stage()
        prim = stage.GetPrimAtPath(selection[0])
        xformable = UsdGeom.Xformable(prim)
        if xformable:
            xform_cache = UsdGeom.XformCache()
            world_mat = xform_cache.GetLocalToWorldTransform(prim)
            pos = world_mat.ExtractTranslation()
            self._tgt_x.model.set_value(pos[0])
            self._tgt_y.model.set_value(pos[1])
            self._tgt_z.model.set_value(pos[2])
            self._status.text = f"Target point set to ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})"

    def _set_target_origin(self):
        """Set target point to world origin."""
        self._tgt_x.model.set_value(0.0)
        self._tgt_y.model.set_value(0.0)
        self._tgt_z.model.set_value(0.0)
        self._status.text = "Target point set to origin (0, 0, 0)"

    def _use_bbox_center(self):
        """Set source point to bounding box center of source object."""
        if not self._source_prim:
            self._status.text = "Set source object first!"
            return
        
        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default"])
        bbox = bbox_cache.ComputeWorldBound(self._source_prim)
        center = bbox.ComputeCentroid()
        
        self._src_x.model.set_value(center[0])
        self._src_y.model.set_value(center[1])
        self._src_z.model.set_value(center[2])
        self._status.text = f"Source point set to bbox center ({center[0]:.2f}, {center[1]:.2f}, {center[2]:.2f})"

    def _on_snap(self):
        """Execute the snap - move source object so source point aligns with target point."""
        if not self._source_prim:
            self._status.text = "Error: No source object set!"
            return
        
        # Get points from UI
        src_point = Gf.Vec3d(
            self._src_x.model.get_value_as_float(),
            self._src_y.model.get_value_as_float(),
            self._src_z.model.get_value_as_float()
        )
        tgt_point = Gf.Vec3d(
            self._tgt_x.model.get_value_as_float(),
            self._tgt_y.model.get_value_as_float(),
            self._tgt_z.model.get_value_as_float()
        )
        
        # Calculate the delta
        delta = tgt_point - src_point
        
        # Get current transform
        xformable = UsdGeom.Xformable(self._source_prim)
        if not xformable:
            self._status.text = "Error: Source object is not transformable!"
            return
        
        xform_cache = UsdGeom.XformCache()
        current_transform = xform_cache.GetLocalToWorldTransform(self._source_prim)
        current_pos = current_transform.ExtractTranslation()
        
        # New position
        new_pos = current_pos + delta
        
        # Apply the transform
        # Use the translate op if it exists, otherwise add one
        translate_op = None
        for op in xformable.GetOrderedXformOps():
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                translate_op = op
                break
        
        if translate_op:
            translate_op.Set(Gf.Vec3d(new_pos))
        else:
            xformable.AddTranslateOp().Set(Gf.Vec3d(new_pos))
        
        self._status.text = f"Snapped! Moved by ({delta[0]:.2f}, {delta[1]:.2f}, {delta[2]:.2f})"
