# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

import omni.ui as ui
import omni.usd
from ..utils.mating import MatingSystem
from ..utils.port import Port

class MatingWindow(ui.Window):
    def __init__(self, title="Object Mating Tool", **kwargs):
        super().__init__(title, width=400, height=540, **kwargs)

        self._source_prim = None
        self._target_prim = None
        self._source_ports = []
        self._target_ports = []
        self._status_label = None

        self.frame.set_build_fn(self._build_ui)

    def _build_ui(self):
        with ui.VStack(spacing=10, style={"margin": 10}):
            ui.Label("Mating Tool", style={"font_size": 18, "color": 0xFF00FF00})

            # Source Selection
            ui.Label("Source Object (Moves)", style={"color": 0xFFAAAAAA})
            with ui.HStack(height=30):
                self._source_label = ui.Label("None Selected", style={"color": 0xFF888888})
                ui.Button("Set from Selection", width=100, clicked_fn=self._on_set_source)

            # Source Port Combo
            self._source_port_combo = ui.ComboBox(0)

            ui.Spacer(height=10)

            # Target Selection
            ui.Label("Target Object (Stationary)", style={"color": 0xFFAAAAAA})
            with ui.HStack(height=30):
                self._target_label = ui.Label("None Selected", style={"color": 0xFF888888})
                ui.Button("Set from Selection", width=100, clicked_fn=self._on_set_target)

            # Target Port Combo
            self._target_port_combo = ui.ComboBox(0)

            ui.Spacer(height=20)

            ui.Button("MATE!", height=40, clicked_fn=self._on_mate_clicked,
                      style={"background_color": 0xFF2B5B2B, "font_size": 16})

            ui.Spacer(height=10)

            # Post-Mate Rotation
            ui.Label("Adjust Rotation (After Mate)", style={"color": 0xFFAAAAAA})
            with ui.HStack(height=30):
                ui.Button("-90\u00b0", clicked_fn=lambda: self._on_rotate(-90))
                ui.Button("+90\u00b0", clicked_fn=lambda: self._on_rotate(90))
                ui.Button("Flip 180\u00b0", clicked_fn=lambda: self._on_rotate(180))

            with ui.HStack(height=30, spacing=4):
                ui.Label("Custom:", width=55, style={"color": 0xFFAAAAAA, "font_size": 12})
                self._custom_angle_model = ui.SimpleFloatModel(45.0)
                ui.FloatDrag(model=self._custom_angle_model, min=-360.0, max=360.0, step=1.0)
                ui.Label("\u00b0", width=14, style={"color": 0xFF888888})
                ui.Button("Rotate", width=60, clicked_fn=self._on_rotate_custom)

            ui.Spacer(height=10)

            # Dimension Inheritance
            ui.Label("Object Intelligence", style={"color": 0xFFAAAAAA})
            ui.Button("Apply Dimensions to Connected", height=30, clicked_fn=self._on_propagate_dims,
                     style={"background_color": 0xFF3B3B5B})

            self._status_label = ui.Label("Ready.", style={"color": 0xFF888888})

    def _on_rotate(self, angle):
        if not self._source_ports:
            self._status_label.text = "No Source Port available!"
            return

        s_idx = self._source_port_combo.model.get_item_value_model().as_int
        if s_idx < 0 or s_idx >= len(self._source_ports):
            return

        s_port = self._source_ports[s_idx]

        # Call Rotate Mated
        if MatingSystem.rotate_mated(s_port, angle):
            self._status_label.text = f"Rotated {angle}\u00b0"
        else:
            self._status_label.text = "Rotation Failed."

    def _on_rotate_custom(self):
        angle = self._custom_angle_model.as_float
        self._on_rotate(angle)

    def _on_propagate_dims(self):
        """Propagates dimensions from source object to all connected objects."""
        if not self._source_prim:
            self._status_label.text = "Set a Source object first!"
            return

        count = MatingSystem.propagate_dimensions(self._source_prim)
        if count > 0:
            self._status_label.text = f"Applied dimensions to {count} connected object(s)."
        else:
            self._status_label.text = "No connected objects found."

    def _find_port_and_object(self, prim):
        """
        Helper to identify if the selection is a Port, a Viz, or a Main Object.
        Returns (main_object_prim, specific_port_name)
        """
        # 1. Is this a Viz? Check parent
        if prim.GetName() == "viz":
            prim = prim.GetParent()

        # 2. Is this a Port? Check attribute
        is_port_attr = prim.GetAttribute("twin:is_port")
        if is_port_attr and is_port_attr.IsValid() and is_port_attr.HasValue() and is_port_attr.Get():
            # This is a Port. Its parent is the Main Object.
            port_name = prim.GetName()
            main_obj = prim.GetParent()
            return main_obj, port_name

        # 3. Otherwise, assume it is the Main Object
        return prim, None

    def _on_set_source(self):
        ctx = omni.usd.get_context()
        selection = ctx.get_selection().get_selected_prim_paths()
        if not selection:
            self._status_label.text = "Select an object first!"
            return

        path = selection[0]
        stage = ctx.get_stage()
        prim = stage.GetPrimAtPath(path)

        # Analyze selection
        main_obj, selected_port_name = self._find_port_and_object(prim)

        self._source_prim = main_obj
        self._source_label.text = main_obj.GetName()

        # Find Ports
        self._source_ports = MatingSystem.find_ports(main_obj)
        names = [p.prim.GetName() for p in self._source_ports]
        self._source_port_combo.model = ui.ComboBox(0, *names).model

        # Auto-select the specific port if one was clicked
        if selected_port_name:
            try:
                idx = names.index(selected_port_name)
                self._source_port_combo.model.get_item_value_model().as_int = idx
            except ValueError:
                pass

        self._status_label.text = f"Source set to {main_obj.GetName()} ({len(names)} ports)"

    def _on_set_target(self):
        ctx = omni.usd.get_context()
        selection = ctx.get_selection().get_selected_prim_paths()
        if not selection:
            self._status_label.text = "Select an object first!"
            return

        path = selection[0]
        stage = ctx.get_stage()
        prim = stage.GetPrimAtPath(path)

        # Analyze selection
        main_obj, selected_port_name = self._find_port_and_object(prim)

        self._target_prim = main_obj
        self._target_label.text = main_obj.GetName()

        # Find Ports
        self._target_ports = MatingSystem.find_ports(main_obj)
        names = [p.prim.GetName() for p in self._target_ports]
        self._target_port_combo.model = ui.ComboBox(0, *names).model

        # Auto-select the specific port if one was clicked
        if selected_port_name:
            try:
                idx = names.index(selected_port_name)
                self._target_port_combo.model.get_item_value_model().as_int = idx
            except ValueError:
                pass

        self._status_label.text = f"Target set to {main_obj.GetName()} ({len(names)} ports)"

    def _on_mate_clicked(self):
        if not self._source_ports or not self._target_ports:
            self._status_label.text = "Ports not found!"
            return

        s_idx = self._source_port_combo.model.get_item_value_model().as_int
        t_idx = self._target_port_combo.model.get_item_value_model().as_int

        if s_idx < 0 or s_idx >= len(self._source_ports):
            return
        if t_idx < 0 or t_idx >= len(self._target_ports):
            return

        s_port = self._source_ports[s_idx]
        t_port = self._target_ports[t_idx]

        success = MatingSystem.snap(s_port, t_port)
        if success:
            self._status_label.text = "MATE SUCCESS!"
        else:
            self._status_label.text = "Mate Failed."
