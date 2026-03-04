# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Equipment Catalog Browser - Unified equipment browsing, placement, and assembly.

Provides tree-based browsing of all registered generators and assembly templates,
with search, parameter editing, detail level control, and LOD upgrade/downgrade.
"""

import omni.ui as ui
import omni.usd
import json
import os

from ..core.equipment_registry import (
    EquipmentRegistry, DetailLevel, EquipmentEntry, ParamType
)
from ..core.assembly import AssemblyEngine, AssemblyDef


# ---------------------------------------------------------------------------
# Shared ListItemModel (consistent with all other windows)
# ---------------------------------------------------------------------------

class ListItem(ui.AbstractItem):
    def __init__(self, text):
        super().__init__()
        self.model = ui.SimpleStringModel(text)


class ListItemModel(ui.AbstractItemModel):
    def __init__(self, items):
        super().__init__()
        self._items = [ListItem(text) for text in items]
        self._current_index = ui.SimpleIntModel()
        self._current_index.add_value_changed_fn(self._on_index_changed)

    def _on_index_changed(self, model):
        self._item_changed(None)

    def get_item_children(self, item):
        return self._items if item is None else []

    def get_item_value_model(self, item, column_id):
        if item is None:
            return self._current_index
        return item.model

    def get_item_value_model_count(self, item):
        return 1


# ---------------------------------------------------------------------------
# Tree model for category/equipment browsing
# ---------------------------------------------------------------------------

class CatalogTreeItem(ui.AbstractItem):
    def __init__(self, text, children=None, entry=None,
                 is_assembly=False, assembly_data=None):
        super().__init__()
        self.name_model = ui.SimpleStringModel(text)
        self.children = children or []
        self.entry = entry
        self.is_assembly = is_assembly
        self.assembly_data = assembly_data


class CatalogTreeDelegate(ui.AbstractItemDelegate):
    def build_widget(self, model, item, column_id, level, expanded):
        if item is None:
            return
        text = item.name_model.as_string
        is_leaf = item.entry is not None or item.is_assembly

        if item.is_assembly:
            color = 0xFFFFAA00
        elif is_leaf:
            color = 0xFFCCEECC
        else:
            color = 0xFFDDDDDD

        with ui.HStack(height=22):
            ui.Spacer(width=level * 12)
            if not is_leaf:
                ui.Label("+" if not expanded else "-", width=14,
                         style={"color": 0xFF888888, "font_size": 12})
            else:
                ui.Spacer(width=14)
            ui.Label(text, style={"color": color, "font_size": 13})


class CatalogTreeModel(ui.AbstractItemModel):
    def __init__(self, root_items):
        super().__init__()
        self._root_items = root_items

    def get_item_children(self, item):
        if item is None:
            return self._root_items
        return item.children

    def get_item_value_model(self, item, column_id):
        if item is None:
            return None
        return item.name_model

    def get_item_value_model_count(self, item):
        return 1


# ---------------------------------------------------------------------------
# Catalog Window
# ---------------------------------------------------------------------------

class CatalogWindow(ui.Window):

    DETAIL_LABELS = ["Placeholder", "Schematic", "Parametric", "Detailed"]

    def __init__(self, title="Equipment Catalog", **kwargs):
        super().__init__(title, width=480, height=720, **kwargs)

        self._registry = EquipmentRegistry.instance()
        self._assemblies = self._load_assemblies()

        self._selected_entry = None
        self._selected_assembly_data = None
        self._detail_level = DetailLevel.PARAMETRIC

        # Edit mode state
        self._edit_mode = False
        self._edit_prim_path = None
        self._action_button = None
        self._stage_event_sub = None

        # UI model references
        self._search_model = ui.SimpleStringModel("")
        self._param_models = {}
        self._detail_panel = None
        self._status_label = None
        self._tree_container = None
        self._extraction_panel = None

        self.frame.set_build_fn(self._build_ui)

        # Subscribe to stage selection changes
        try:
            usd_context = omni.usd.get_context()
            stage_event_stream = usd_context.get_stage_event_stream()
            self._stage_event_sub = stage_event_stream.create_subscription_to_pop(
                self._on_stage_event
            )
        except Exception:
            pass

    def destroy(self):
        self._stage_event_sub = None
        super().destroy()

    def _load_assemblies(self):
        assemblies = []
        asm_dir = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', '..', '..', '..', '..', 'data', 'assemblies'
        ))
        if os.path.isdir(asm_dir):
            for fn in sorted(os.listdir(asm_dir)):
                if fn.endswith('.json'):
                    try:
                        with open(os.path.join(asm_dir, fn)) as f:
                            assemblies.append(json.load(f))
                    except Exception as e:
                        print(f"[IEIP Catalog] Error loading {fn}: {e}")
        return assemblies

    # ----- Tree building -----

    def _build_tree_items(self, filter_text=""):
        """Build a flat-then-hierarchical tree from registry + assemblies."""
        q = filter_text.lower().strip()

        # Collect all leaf items grouped by category path
        cat_leaves = {}  # "MEP Systems/Fan" -> [CatalogTreeItem, ...]

        for entry in self._registry.all_entries().values():
            if q and q not in entry.name.lower() and not any(q in t.lower() for t in entry.tags):
                continue
            cat = entry.category
            if cat not in cat_leaves:
                cat_leaves[cat] = []
            cat_leaves[cat].append(
                CatalogTreeItem(entry.name, entry=entry)
            )

        for asm in self._assemblies:
            name = asm.get("name", "Unknown Assembly")
            if q and q not in name.lower():
                continue
            cat = asm.get("category", "Assemblies")
            if cat not in cat_leaves:
                cat_leaves[cat] = []
            cat_leaves[cat].append(
                CatalogTreeItem(f"[ASM] {name}", is_assembly=True, assembly_data=asm)
            )

        # Build tree hierarchy from category paths
        root_nodes = {}  # top-level name -> CatalogTreeItem

        for cat_path, leaves in sorted(cat_leaves.items()):
            parts = cat_path.split("/")
            # Ensure all ancestor nodes exist
            current_dict = root_nodes
            parent_item = None
            for i, part in enumerate(parts):
                if part not in current_dict:
                    new_item = CatalogTreeItem(part)
                    current_dict[part] = {"__item__": new_item, "__children__": {}}
                    if parent_item:
                        parent_item.children.append(new_item)

                node = current_dict[part]
                parent_item = node["__item__"]
                current_dict = node["__children__"]

            # Attach leaves to deepest category
            parent_item.children.extend(leaves)

        return [v["__item__"] for v in root_nodes.values()]

    # ----- UI building -----

    def _build_ui(self):
        with ui.VStack(spacing=6, padding=10):
            # Header
            ui.Label("Equipment Catalog",
                     style={"font_size": 20, "color": 0xFF00AAFF},
                     height=28)
            ui.Label("Browse, place, and assemble equipment",
                     style={"color": 0xFF888888, "font_size": 11},
                     height=16)

            ui.Separator(height=2)

            # Search bar
            with ui.HStack(height=28, spacing=4):
                ui.Label("Search:", width=50)
                field = ui.StringField(model=self._search_model, height=24)
                self._search_model.add_value_changed_fn(
                    lambda m: self._rebuild_tree()
                )

            # Detail level selector
            with ui.HStack(height=28, spacing=4):
                ui.Label("Place as:", width=50)
                self._detail_model = ListItemModel(self.DETAIL_LABELS)
                self._detail_model.get_item_value_model(None, 0).set_value(2)
                self._detail_model.get_item_value_model(None, 0).add_value_changed_fn(
                    lambda m: setattr(self, '_detail_level', DetailLevel(m.as_int))
                )
                ui.ComboBox(self._detail_model, height=24)

            ui.Separator(height=2)

            # Equipment tree
            ui.Label("Equipment & Assemblies",
                     style={"font_size": 14, "color": 0xFFCCCCCC}, height=20)

            self._tree_container = ui.ScrollingFrame(height=220)
            self._rebuild_tree()

            ui.Separator(height=2)

            # Parameters panel
            ui.Label("Parameters",
                     style={"font_size": 14, "color": 0xFFCCCCCC}, height=20)
            with ui.ScrollingFrame(height=200):
                self._detail_panel = ui.VStack(spacing=4, height=0)
                with self._detail_panel:
                    ui.Label("Select an item above",
                             style={"color": 0xFF888888, "font_size": 12})

            ui.Separator(height=2)

            # Import spec JSON (offline — generated by tools/extract_spec.py)
            ui.Button("Import Spec JSON",
                      clicked_fn=self._on_import_spec_json,
                      height=28,
                      style={"Button": {"background_color": 0xFF553388,
                                        "font_size": 12}},
                      tooltip="Import a .spec.json file generated by extract_spec.py")

            # Extraction result panel (hidden until extraction runs)
            self._extraction_panel = ui.VStack(spacing=2, visible=False)

            ui.Separator(height=2)

            # Action buttons
            with ui.HStack(height=38, spacing=6):
                self._action_button = ui.Button(
                          "Place at Origin",
                          clicked_fn=self._on_primary_action,
                          height=36,
                          style={"Button": {"background_color": 0xFF2D5A27,
                                            "font_size": 14}})
                ui.Button("Place at Selection",
                          clicked_fn=self._on_place_at_selection,
                          height=36)

            # LOD controls
            with ui.HStack(height=30, spacing=6):
                ui.Button("Upgrade Selected",
                          clicked_fn=self._on_upgrade_selected,
                          height=28,
                          style={"Button": {"background_color": 0xFF335577}})
                ui.Button("Downgrade Selected",
                          clicked_fn=self._on_downgrade_selected,
                          height=28)

            # Status bar
            self._status_label = ui.Label("Ready",
                                          style={"color": 0xFF888888,
                                                 "font_size": 11},
                                          height=18)

    def _rebuild_tree(self):
        if not self._tree_container:
            return

        self._tree_container.clear()
        filter_text = self._search_model.as_string
        root_items = self._build_tree_items(filter_text)
        tree_model = CatalogTreeModel(root_items)

        with self._tree_container:
            tree = ui.TreeView(
                tree_model,
                root_visible=False,
                header_visible=False,
                style={"TreeView.Item": {"margin": 1},
                       "TreeView": {"background_color": 0xFF1A1A1A}},
            )
            tree.set_selection_changed_fn(self._on_tree_selection)

    def _on_tree_selection(self, items):
        if not items:
            return
        self._exit_edit_mode()
        item = items[0]
        if item.entry:
            self._selected_entry = item.entry
            self._selected_assembly_data = None
            self._build_param_panel(item.entry)
        elif item.is_assembly and item.assembly_data:
            self._selected_entry = None
            self._selected_assembly_data = item.assembly_data
            self._build_assembly_panel(item.assembly_data)

    # ----- Parameter panel -----

    def _build_param_panel(self, entry: EquipmentEntry):
        if not self._detail_panel:
            return
        self._detail_panel.clear()
        self._param_models = {}

        with self._detail_panel:
            ui.Label(entry.name,
                     style={"font_size": 14, "color": 0xFF00FF88}, height=22)
            if entry.description:
                ui.Label(entry.description, word_wrap=True,
                         style={"color": 0xFFAAAAAA, "font_size": 11}, height=0)
            ui.Spacer(height=4)

            for pdef in entry.params:
                with ui.HStack(height=24, spacing=4):
                    label = pdef.label or pdef.name
                    ui.Label(f"{label}:", width=130,
                             style={"font_size": 12})

                    if pdef.param_type == ParamType.FLOAT:
                        model = ui.SimpleFloatModel(float(pdef.default))
                        ui.FloatDrag(model=model,
                                     min=pdef.min_val if pdef.min_val is not None else 0.0,
                                     max=pdef.max_val if pdef.max_val is not None else 9999.0,
                                     step=0.25)
                        self._param_models[pdef.name] = model

                    elif pdef.param_type == ParamType.INT:
                        model = ui.SimpleIntModel(int(pdef.default))
                        ui.IntDrag(model=model)
                        self._param_models[pdef.name] = model

                    elif pdef.param_type == ParamType.BOOL:
                        model = ui.SimpleBoolModel(bool(pdef.default))
                        ui.CheckBox(model=model)
                        self._param_models[pdef.name] = model

                    elif pdef.param_type in (ParamType.ENUM, ParamType.DATA_LOOKUP):
                        choices = pdef.choices
                        if pdef.param_type == ParamType.DATA_LOOKUP and not choices:
                            choices = self._load_data_lookup_choices(pdef)
                        if choices:
                            list_model = ListItemModel(
                                [str(c) for c in choices])
                            default_str = str(pdef.default)
                            str_choices = [str(c) for c in choices]
                            idx = str_choices.index(default_str) if default_str in str_choices else 0
                            list_model.get_item_value_model(None, 0).set_value(idx)
                            ui.ComboBox(list_model)
                            self._param_models[pdef.name] = (list_model, choices)
                        else:
                            model = ui.SimpleStringModel(str(pdef.default))
                            ui.StringField(model=model)
                            self._param_models[pdef.name] = model

                    elif pdef.param_type == ParamType.STRING:
                        model = ui.SimpleStringModel(str(pdef.default))
                        ui.StringField(model=model)
                        self._param_models[pdef.name] = model

                    if pdef.unit:
                        ui.Label(pdef.unit, width=30,
                                 style={"color": 0xFF888888, "font_size": 11})

    def _build_assembly_panel(self, asm_data: dict):
        if not self._detail_panel:
            return
        self._detail_panel.clear()
        self._param_models = {}

        with self._detail_panel:
            name = asm_data.get("name", "Assembly")
            ui.Label(f"ASSEMBLY: {name}",
                     style={"font_size": 14, "color": 0xFFFFAA00}, height=22)
            desc = asm_data.get("description", "")
            if desc:
                ui.Label(desc, word_wrap=True,
                         style={"color": 0xFFAAAAAA, "font_size": 11}, height=0)
            ui.Spacer(height=6)

            components = asm_data.get("components", [])
            ui.Label(f"Components ({len(components)}):",
                     style={"color": 0xFF88FF88, "font_size": 12}, height=18)
            for comp in components:
                eid = comp.get("entry_id", "?")
                cid = comp.get("id", "?")
                dl = comp.get("detail_level", 2)
                dl_label = self.DETAIL_LABELS[dl] if 0 <= dl < 4 else "?"
                ui.Label(f"  {cid}: {eid} [{dl_label}]",
                         style={"color": 0xFFCCCCCC, "font_size": 11}, height=16)

            # Exposed params as editable fields
            exposed = asm_data.get("exposed_params", {})
            if exposed:
                ui.Spacer(height=6)
                ui.Label("Assembly Parameters:",
                         style={"color": 0xFF88FF88, "font_size": 12}, height=18)
                for param_label, target_ref in exposed.items():
                    # Find the param definition from the target component
                    pdef = self._find_exposed_param_def(asm_data, target_ref)
                    with ui.HStack(height=24, spacing=4):
                        ui.Label(f"{param_label}:", width=130,
                                 style={"font_size": 12})
                        if pdef and pdef.param_type in (ParamType.ENUM, ParamType.DATA_LOOKUP):
                            choices = pdef.choices
                            if pdef.param_type == ParamType.DATA_LOOKUP and not choices:
                                choices = self._load_data_lookup_choices(pdef)
                            if choices:
                                list_model = ListItemModel([str(c) for c in choices])
                                default_str = str(pdef.default)
                                str_choices = [str(c) for c in choices]
                                idx = str_choices.index(default_str) if default_str in str_choices else 0
                                list_model.get_item_value_model(None, 0).set_value(idx)
                                ui.ComboBox(list_model)
                                self._param_models[param_label] = (list_model, choices)
                        elif pdef and pdef.param_type == ParamType.BOOL:
                            model = ui.SimpleBoolModel(bool(pdef.default))
                            ui.CheckBox(model=model)
                            self._param_models[param_label] = model
                        else:
                            default_val = pdef.default if pdef else 0.0
                            model = ui.SimpleFloatModel(float(default_val))
                            ui.FloatDrag(model=model)
                            self._param_models[param_label] = model

    def _find_exposed_param_def(self, asm_data, target_ref):
        """Look up a ParamDef for an exposed assembly parameter."""
        parts = target_ref.split(".", 1)
        if len(parts) != 2:
            return None
        comp_id, param_name = parts
        # Find the component's entry_id
        for comp in asm_data.get("components", []):
            if comp["id"] == comp_id:
                entry = self._registry.get(comp["entry_id"])
                if entry:
                    for pdef in entry.params:
                        if pdef.name == param_name:
                            return pdef
        return None

    def _load_data_lookup_choices(self, pdef):
        """Load choices from a data file for DATA_LOOKUP params."""
        if not pdef.data_file:
            return []
        data_dir = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', '..', '..', '..', '..', 'data'
        ))
        fpath = os.path.join(data_dir, pdef.data_file)
        if not os.path.exists(fpath):
            return []
        try:
            with open(fpath) as f:
                data = json.load(f)
            if isinstance(data, list) and pdef.data_key:
                return [item[pdef.data_key] for item in data if pdef.data_key in item]
        except Exception:
            pass
        return []

    # ----- Parameter collection -----

    def _collect_params(self):
        params = {}
        for name, model in self._param_models.items():
            if isinstance(model, tuple):
                list_model, choices = model
                idx = list_model.get_item_value_model(None, 0).as_int
                params[name] = choices[idx] if idx < len(choices) else choices[0]
            elif isinstance(model, ui.SimpleFloatModel):
                params[name] = model.as_float
            elif isinstance(model, ui.SimpleIntModel):
                params[name] = model.as_int
            elif isinstance(model, ui.SimpleBoolModel):
                params[name] = model.as_bool
            elif isinstance(model, ui.SimpleStringModel):
                params[name] = model.as_string
        return params

    # ----- Stage event / edit mode -----

    def _on_stage_event(self, event):
        import carb
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            self._check_selection_for_edit_mode()

    def _check_selection_for_edit_mode(self):
        """Enter edit mode if exactly 1 IEIP prim is selected."""
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        if not stage:
            return

        selected = ctx.get_selection().get_selected_prim_paths()
        if len(selected) != 1:
            self._exit_edit_mode()
            return

        prim = stage.GetPrimAtPath(selected[0])
        if not prim or not prim.IsValid():
            self._exit_edit_mode()
            return

        cd = prim.GetCustomData()
        entry_id = cd.get("ieip:entry_id")
        if not entry_id:
            self._exit_edit_mode()
            return

        entry = self._registry.get(entry_id)
        if not entry:
            self._exit_edit_mode()
            return

        # Read stored params
        stored_params = {}
        for key, value in cd.items():
            if key.startswith("ieip:param:"):
                stored_params[key[len("ieip:param:"):]] = value

        # Build param panel and fill with stored values
        self._selected_entry = entry
        self._selected_assembly_data = None
        self._build_param_panel(entry)
        self._apply_extracted_params(stored_params, entry)

        # Enter edit mode
        self._edit_mode = True
        self._edit_prim_path = selected[0]
        if self._action_button:
            self._action_button.text = "Apply Changes"
        self._set_status(f"Editing: {selected[0]}")

    def _exit_edit_mode(self):
        if not self._edit_mode:
            return
        self._edit_mode = False
        self._edit_prim_path = None
        if self._action_button:
            self._action_button.text = "Place at Origin"

    def _on_primary_action(self):
        if self._edit_mode:
            self._on_apply_changes()
        else:
            self._on_place()

    def _on_apply_changes(self):
        """Regenerate the selected IEIP prim with current UI params."""
        if not self._edit_prim_path:
            self._set_status("No prim to update")
            return

        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        if not stage:
            return

        params = self._collect_params()
        try:
            result = self._registry.regenerate_component(
                stage, self._edit_prim_path, new_params=params
            )
            if result:
                self._set_status(f"Regenerated: {self._edit_prim_path}")
                ctx.get_selection().set_selected_prim_paths(
                    [self._edit_prim_path], False
                )
            else:
                self._set_status("Regeneration failed")
        except ValueError as e:
            self._set_status(f"Error: {e}")

    # ----- Placement actions -----

    def _on_place(self):
        stage = omni.usd.get_context().get_stage()
        if not stage:
            self._set_status("No stage open")
            return

        if self._selected_entry:
            self._place_single(stage, self._selected_entry)
        elif self._selected_assembly_data:
            self._place_assembly(stage, self._selected_assembly_data)
        elif self._param_models and "width" in self._param_models:
            # Placeholder from unknown extraction
            self._place_placeholder(stage)
        else:
            self._set_status("Nothing selected")

    def _place_single(self, stage, entry: EquipmentEntry):
        path = self._unique_path(stage, f"/World/{entry.id}")
        params = self._collect_params()

        try:
            result = self._registry.create_component(
                entry.id, stage, path, params, self._detail_level
            )
            if result:
                self._set_status(f"Placed {entry.name} at {path}")
                omni.usd.get_context().get_selection().set_selected_prim_paths(
                    [path], False
                )
            else:
                self._set_status(f"Failed to create {entry.name}")
        except Exception as e:
            self._set_status(f"Error: {e}")
            import traceback
            traceback.print_exc()

    def _place_assembly(self, stage, asm_data: dict):
        asm_def = AssemblyEngine.load_assembly_from_json(asm_data)
        path = self._unique_path(stage, f"/World/{asm_def.id}")
        params = self._collect_params()

        try:
            result = AssemblyEngine.create_assembly(
                stage, path, asm_def,
                param_overrides=params,
                global_detail_level=self._detail_level,
            )
            if result:
                self._set_status(f"Placed assembly '{asm_def.name}' at {path}")
                omni.usd.get_context().get_selection().set_selected_prim_paths(
                    [path], False
                )
            else:
                self._set_status("Failed to create assembly")
        except Exception as e:
            self._set_status(f"Error: {e}")
            import traceback
            traceback.print_exc()

    def _place_placeholder(self, stage):
        """Place an unknown-equipment placeholder from extracted dimensions."""
        params = self._collect_params()
        label = params.pop("label", "Unknown Equipment")
        params["label"] = label
        path = self._unique_path(stage, "/World/placeholder")
        try:
            result = self._registry.create_component(
                "__placeholder__", stage, path, params, DetailLevel.PLACEHOLDER
            )
            if result:
                self._set_status(f"Placed placeholder '{label}' at {path}")
                omni.usd.get_context().get_selection().set_selected_prim_paths(
                    [path], False
                )
            else:
                self._set_status("Failed to create placeholder")
        except Exception as e:
            self._set_status(f"Error: {e}")
            import traceback
            traceback.print_exc()

    def _on_place_at_selection(self):
        """Place at currently selected prim's location."""
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        if not stage:
            self._set_status("No stage open")
            return

        selected = ctx.get_selection().get_selected_prim_paths()
        if not selected:
            # Fall back to origin
            self._on_place()
            return

        from pxr import UsdGeom, Gf
        sel_prim = stage.GetPrimAtPath(selected[0])
        if not sel_prim:
            self._on_place()
            return

        # Get position of selection
        xform_cache = UsdGeom.XformCache()
        world_xform = xform_cache.GetLocalToWorldTransform(sel_prim)
        position = world_xform.ExtractTranslation()

        # Place the component/assembly
        self._on_place()

        # Move the just-created prim to selection position
        new_selected = ctx.get_selection().get_selected_prim_paths()
        if new_selected:
            new_prim = stage.GetPrimAtPath(new_selected[0])
            if new_prim:
                xform = UsdGeom.Xformable(new_prim)
                xform.AddTranslateOp().Set(position)

    # ----- LOD controls -----

    def _on_upgrade_selected(self):
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        selected = ctx.get_selection().get_selected_prim_paths()
        if not stage or not selected:
            self._set_status("No prim selected")
            return

        for path in selected:
            prim = stage.GetPrimAtPath(path)
            if not prim:
                continue
            cd = prim.GetCustomData()
            current = cd.get("ieip:detail_level", -1)
            if current < 0:
                self._set_status(f"{path} is not an IEIP component")
                continue
            if current >= int(DetailLevel.DETAILED):
                self._set_status(f"{path} already at max detail")
                continue
            new_level = DetailLevel(current + 1)
            # Skip schematic (not implemented), go straight to parametric
            if new_level == DetailLevel.SCHEMATIC:
                new_level = DetailLevel.PARAMETRIC
            AssemblyEngine.upgrade_detail_level(stage, path, new_level)
            self._set_status(
                f"Upgraded {path} to {self.DETAIL_LABELS[int(new_level)]}")

    def _on_downgrade_selected(self):
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        selected = ctx.get_selection().get_selected_prim_paths()
        if not stage or not selected:
            self._set_status("No prim selected")
            return

        for path in selected:
            prim = stage.GetPrimAtPath(path)
            if not prim:
                continue
            cd = prim.GetCustomData()
            current = cd.get("ieip:detail_level", -1)
            if current < 0:
                self._set_status(f"{path} is not an IEIP component")
                continue
            if current <= int(DetailLevel.PLACEHOLDER):
                self._set_status(f"{path} already at minimum detail")
                continue
            AssemblyEngine.upgrade_detail_level(
                stage, path, DetailLevel.PLACEHOLDER)
            self._set_status(f"Downgraded {path} to Placeholder")

    # ----- Helpers -----

    def _unique_path(self, stage, base_path: str) -> str:
        path = base_path
        idx = 1
        while stage.GetPrimAtPath(path):
            path = f"{base_path}_{idx}"
            idx += 1
        return path

    def _set_status(self, text: str):
        if self._status_label:
            self._status_label.text = text
        print(f"[IEIP Catalog] {text}")

    # ----- Spec JSON import (air-gapped workflow) -----

    def _open_json_file_dialog(self, callback):
        """Open FilePickerDialog filtered to .json files."""
        try:
            from omni.kit.window.filepicker import FilePickerDialog

            def _on_apply(filename, dirname):
                if filename and dirname:
                    full_path = os.path.join(dirname, filename)
                    self._file_picker.hide()
                    callback(full_path)
                else:
                    self._file_picker.hide()

            def _on_cancel(filename, dirname):
                self._file_picker.hide()

            def _filter(item):
                if item.is_folder:
                    return True
                return item.path.lower().endswith(".json")

            self._file_picker = FilePickerDialog(
                "Import Spec JSON",
                apply_button_label="Import",
                click_apply_handler=_on_apply,
                click_cancel_handler=_on_cancel,
                item_filter_fn=_filter,
            )
            self._file_picker.show()
        except ImportError:
            self._set_status(
                "File picker not available — enter path in Kit console"
            )

    def _on_import_spec_json(self):
        """Import a .spec.json file produced by tools/extract_spec.py."""
        def _on_file(path):
            self._import_spec_json(path)

        self._open_json_file_dialog(_on_file)

    def _import_spec_json(self, json_path: str):
        """Read a JSON file, auto-detect format, and route accordingly."""
        try:
            with open(json_path) as f:
                data = json.load(f)
        except Exception as e:
            self._set_status(f"Failed to read JSON: {e}")
            return

        if "entry_id" in data or "params" in data:
            self._import_spec_params(data, json_path)
        else:
            self._set_status("Unrecognized JSON format")

    def _import_spec_params(self, data, json_path):
        """Import a .spec.json file with entry_id + params (existing flow)."""
        entry_id = data.get("entry_id", "")
        params = data.get("params", {})
        confidence = float(data.get("confidence", 0.0))
        source = data.get("source", "")
        notes = data.get("notes", "")
        pct = int(confidence * 100)

        if not params:
            self._set_status("JSON file contains no parameters")
            return

        # Show import info panel
        if self._extraction_panel:
            self._extraction_panel.clear()
            self._extraction_panel.visible = True
            with self._extraction_panel:
                color = 0xFF00FF88 if confidence > 0.6 else (
                    0xFFFFAA00 if confidence > 0.3 else 0xFFFF4444
                )
                ui.Label(
                    f"Imported: {os.path.basename(json_path)} ({pct}% confidence)",
                    style={"color": color, "font_size": 12}, height=18,
                )
                if source:
                    ui.Label(f"  Source: {source}",
                             style={"color": 0xFFAAAAAA, "font_size": 11},
                             height=16)
                if notes:
                    ui.Label(f"  {notes}",
                             style={"color": 0xFFAAAAAA, "font_size": 11},
                             height=16)

        # If entry_id matches a registry entry, select it and fill params
        if entry_id:
            entry = self._registry.get(entry_id)
            if entry:
                self._selected_entry = entry
                self._selected_assembly_data = None
                self._build_param_panel(entry)
                self._apply_extracted_params(params, entry)
                self._set_status(
                    f"Loaded {entry.name} from {os.path.basename(json_path)} "
                    f"({pct}% confidence)"
                )
                return

        # Unknown equipment — build placeholder panel
        self._selected_entry = None
        self._selected_assembly_data = None
        self._build_placeholder_panel(params)
        self._set_status(
            f"Loaded placeholder from {os.path.basename(json_path)} "
            f"({pct}% confidence)"
        )

    def _apply_extracted_params(self, params: dict, entry):
        """Pre-fill parameter panel models with extracted values."""
        for pdef in entry.params:
            if pdef.name not in params:
                continue
            value = params[pdef.name]
            model = self._param_models.get(pdef.name)
            if model is None:
                continue

            try:
                if isinstance(model, tuple):
                    # ComboBox (list_model, choices)
                    list_model, choices = model
                    str_choices = [str(c) for c in choices]
                    str_val = str(value)
                    if str_val in str_choices:
                        list_model.get_item_value_model(None, 0).set_value(
                            str_choices.index(str_val)
                        )
                elif isinstance(model, ui.SimpleFloatModel):
                    model.set_value(float(value))
                elif isinstance(model, ui.SimpleIntModel):
                    model.set_value(int(value))
                elif isinstance(model, ui.SimpleBoolModel):
                    model.set_value(bool(value))
                elif isinstance(model, ui.SimpleStringModel):
                    model.set_value(str(value))
            except Exception:
                pass

    def _build_placeholder_panel(self, params: dict):
        """Build a simple param panel for unknown/placeholder equipment."""
        if not self._detail_panel:
            return
        self._detail_panel.clear()
        self._param_models = {}

        with self._detail_panel:
            label = params.get("label", "Unknown Equipment")
            ui.Label(label,
                     style={"font_size": 14, "color": 0xFFFF8800}, height=22)
            ui.Label("Extracted as placeholder — review dimensions below",
                     style={"color": 0xFFAAAAAA, "font_size": 11}, height=0)
            ui.Spacer(height=4)

            for name in ("width", "height", "depth"):
                if name in params:
                    with ui.HStack(height=24, spacing=4):
                        ui.Label(f"{name.title()}:", width=130,
                                 style={"font_size": 12})
                        model = ui.SimpleFloatModel(float(params[name]))
                        ui.FloatDrag(model=model, min=0.1, max=9999.0, step=0.5)
                        self._param_models[name] = model
                        ui.Label("in", width=30,
                                 style={"color": 0xFF888888, "font_size": 11})

            if "label" in params:
                with ui.HStack(height=24, spacing=4):
                    ui.Label("Label:", width=130, style={"font_size": 12})
                    model = ui.SimpleStringModel(str(params["label"]))
                    ui.StringField(model=model)
                    self._param_models["label"] = model
