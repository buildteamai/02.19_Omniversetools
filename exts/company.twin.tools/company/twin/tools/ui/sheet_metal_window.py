import omni.ui as ui
import omni.usd
from ..objects.sheet_metal_panel import SheetMetalPanelGenerator
import json
import os
from pxr import Usd, UsdGeom, Gf, Sdf

DATA_PATH = "c:/Programming/buildteamai/data/sheet_metal_variants.json"

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

class SheetMetalWindow(ui.Window):
    def __init__(self, title: str):
        super().__init__(title, width=400, height=650)
        self._generator = SheetMetalPanelGenerator()
        
        # UI Models
        self._width_model = ui.SimpleFloatModel(48.0)
        self._height_model = ui.SimpleFloatModel(96.0)
        self._thickness_model = ui.SimpleFloatModel(0.125)
        self._break_model = ui.SimpleFloatModel(2.0)
        self._return_model = ui.SimpleFloatModel(0.5)
        
        self._variant_name_model = ui.SimpleStringModel("")
        
        # Load Variants
        self._variants = self._load_variants()
        self._update_variant_model()
        
        self.frame.set_build_fn(self._build_ui)

    def _load_variants(self):
        if os.path.exists(DATA_PATH):
            try:
                with open(DATA_PATH, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading variants: {e}")
        return []

    def _save_variants(self):
        try:
             # Ensure directory exists
            os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
            with open(DATA_PATH, "w") as f:
                json.dump(self._variants, f, indent=4)
        except Exception as e:
            print(f"Error saving variants: {e}")

    def _update_variant_model(self):
        variant_names = [v["name"] for v in self._variants]
        variant_names.insert(0, "- Select Preset -")
        self._variant_list_model = ListItemModel(variant_names)
        self._variant_list_model.get_item_value_model(None, 0).add_value_changed_fn(self._on_variant_changed)

    def _on_variant_changed(self, model):
        index = model.as_int
        if index > 0: # 0 is "- Select Preset -"
            variant = self._variants[index - 1]
            self._width_model.as_float = float(variant.get("width", 48.0))
            self._height_model.as_float = float(variant.get("height", 96.0))
            self._thickness_model.as_float = float(variant.get("thickness", 0.125))
            self._break_model.as_float = float(variant.get("break_len", 2.0))
            self._return_model.as_float = float(variant.get("return_len", 0.5))
            self._variant_name_model.as_string = variant.get("name", "")

    def _build_ui(self):
        with ui.ScrollingFrame():
            with ui.VStack(height=0, spacing=10, style={"margin": 10}):
                ui.Label("Sheet Metal Configurator", style={"font_size": 20, "color": 0xFFDDDDDD})
                ui.Separator(height=10)

                # Variant Selection
                with ui.HStack(height=24):
                    ui.Label("Preset:", width=80)
                    ui.ComboBox(self._variant_list_model)

                ui.Separator(height=10)
                ui.Label("Dimensions", style={"font_size": 16})
                
                with ui.HStack(height=24):
                    ui.Label("Width", width=80)
                    ui.FloatDrag(self._width_model, min=1.0, max=1000.0)
                
                with ui.HStack(height=24):
                    ui.Label("Height", width=80)
                    ui.FloatDrag(self._height_model, min=1.0, max=1000.0)

                with ui.HStack(height=24):
                    ui.Label("Thickness", width=80)
                    ui.FloatDrag(self._thickness_model, min=0.01, max=10.0, step=0.01)

                ui.Spacer(height=5)
                ui.Label("Flanges", style={"font_size": 16})

                with ui.HStack(height=24):
                    ui.Label("Break (Depth)", width=100)
                    ui.FloatDrag(self._break_model, min=0.1, max=50.0)

                with ui.HStack(height=24):
                    ui.Label("Return", width=100)
                    ui.FloatDrag(self._return_model, min=0.0, max=10.0)

                ui.Separator(height=10)
                
                # Save Variant
                with ui.CollapsableFrame("Save Preset", collapsed=True):
                    with ui.VStack(spacing=5, padding=5):
                        with ui.HStack(height=24):
                            ui.Label("Name:", width=50)
                            ui.StringField(self._variant_name_model)
                        ui.Button("Save Preset", clicked_fn=self._on_save_preset)

                ui.Spacer(height=20)
                ui.Button("Create Panel", clicked_fn=self._on_create_panel, height=40)
                
                ui.Spacer(height=10)
                ui.Separator(height=10)
                
                ui.Label("Assembly Tools", style={"font_size": 16})
                ui.Label("Select two panels to mate them.", style={"color": 0xFFAAAAAA, "font_size": 12})
                with ui.HStack(height=30, spacing=10):
                    ui.Button("Mate Selected", clicked_fn=self._on_mate_selected)
                    ui.Button("Toggle Anchor", clicked_fn=self._on_toggle_anchor, tooltip="Locks/Unlocks the selected part so it won't move during mating")


    def _on_save_preset(self):
        name = self._variant_name_model.as_string
        if not name:
            return
            
        new_variant = {
            "name": name,
            "width": self._width_model.as_float,
            "height": self._height_model.as_float,
            "thickness": self._thickness_model.as_float,
            "break_len": self._break_model.as_float,
            "return_len": self._return_model.as_float
        }
        
        # Check if exists and update
        existing_idx = -1
        for i, v in enumerate(self._variants):
            if v["name"] == name:
                existing_idx = i
                break
        
        if existing_idx >= 0:
            self._variants[existing_idx] = new_variant
        else:
            self._variants.append(new_variant)
            
        self._save_variants()
        
        # Rebuild Dropdown
        # We need to refresh the list model
        # Simplest way is to completely rebuild it (or we could just append)
        self._update_variant_model()
        self.frame.rebuild() 

    def _on_create_panel(self):
        width = self._width_model.as_float
        height = self._height_model.as_float
        thickness = self._thickness_model.as_float
        break_len = self._break_model.as_float
        return_len = self._return_model.as_float
        
        # Determine path
        stage = omni.usd.get_context().get_stage()
        if not stage:
            return

        default_prim_path = str(stage.GetDefaultPrim().GetPath()) if stage.GetDefaultPrim() else "/World"
        if default_prim_path == "/":
             default_prim_path = "/World"
             
        # Find unique path
        base_path = f"{default_prim_path}/SheetMetalPanel"
        path = base_path
        i = 1
        while stage.GetPrimAtPath(path):
            path = f"{base_path}_{i}"
            i += 1
        
        self._generator.create_panel(path, width, height, thickness, break_len, return_len)
        
    def _on_mate_selected(self):
        """
        Mates two objects based on selection.
        Supports:
        - Two Panels (finds closest anchors)
        - Two Anchors (mates those specific anchors)
        - Panel + Anchor (mates panel's closest anchor to the specific anchor)
        Respects 'is_anchored' attribute to decide which part moves.
        """
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        selection = ctx.get_selection().get_selected_prim_paths()
        
        if len(selection) != 2:
            print("Please select exactly two items (Panels or Anchors) to mate.")
            return
            
        prim_a = stage.GetPrimAtPath(selection[0])
        prim_b = stage.GetPrimAtPath(selection[1])
        
        if not prim_a or not prim_b:
            return

        # Helper to classify selection
        def analyze_selection(prim):
            # Check if it's an anchor (has "Anchor" in name) or a Panel (has anchors as children)
            if "Anchor" in prim.GetName():
                return {"type": "anchor", "prim": prim, "parent": prim.GetParent()}
            return {"type": "panel", "prim": prim, "parent": prim.GetParent()} # Assuming panel

        info_a = analyze_selection(prim_a)
        info_b = analyze_selection(prim_b)
        
        # Resolve actual anchors to use
        anchor_a = None
        anchor_b = None
        
        # Case 1: Both are specific Anchors - BEST CASE
        if info_a["type"] == "anchor" and info_b["type"] == "anchor":
            anchor_a = prim_a
            anchor_b = prim_b
            
        # Case 2/3: Mixed or Both Panels - Find best match
        else:
            # Gather candidate anchors for A
            cands_a = [prim_a] if info_a["type"] == "anchor" else [c for c in info_a["prim"].GetChildren() if "Anchor" in c.GetName()]
            # Gather candidate anchors for B
            cands_b = [prim_b] if info_b["type"] == "anchor" else [c for c in info_b["prim"].GetChildren() if "Anchor" in c.GetName()]
            
            if not cands_a or not cands_b:
                print("Could not find anchors on selected objects.")
                return
                
            # Find closest pair
            min_dist = float('inf')
            best_pair = (None, None)
            
            for ca in cands_a:
                pos_a = omni.usd.get_world_transform_matrix(ca).ExtractTranslation()
                for cb in cands_b:
                    pos_b = omni.usd.get_world_transform_matrix(cb).ExtractTranslation()
                    dist = (pos_a - pos_b).GetLength()
                    if dist < min_dist:
                        min_dist = dist
                        best_pair = (ca, cb)
            
            anchor_a, anchor_b = best_pair

        if not anchor_a or not anchor_b:
            print("Failed to resolve mating anchors.")
            return

        # Identify Parents (The objects to actually move)
        part_a = anchor_a.GetParent()
        part_b = anchor_b.GetParent()
        
        if part_a == part_b:
            print("Cannot mate a part to itself.")
            return

        # Check Anchored State
        def is_anchored(prim):
            attr = prim.GetAttribute("custom:is_anchored")
            if attr and attr.IsValid():
                return attr.Get()
            return False

        anchored_a = is_anchored(part_a)
        anchored_b = is_anchored(part_b)
        
        # Decide who moves
        # Target = The one staying still
        # Mover = The one moving
        target_anchor = None
        mover_anchor = None
        mover_part = None
        
        if anchored_a and anchored_b:
            print("Both parts are Anchored. Cannot mate.")
            return
        elif anchored_a:
            target_anchor = anchor_a
            mover_anchor = anchor_b
            mover_part = part_b
            print(f"Mating {part_b.GetName()} (Mover) to {part_a.GetName()} (Anchored)")
        elif anchored_b:
            target_anchor = anchor_b
            mover_anchor = anchor_a
            mover_part = part_a
            print(f"Mating {part_a.GetName()} (Mover) to {part_b.GetName()} (Anchored)")
        else:
            # Default: Second selection moves (Standard CAD behavior) -> First is Target
            # selection[0] is prim_a
            # selection[1] is prim_b (Mover)
            # BUT, we might have swapped them in logic above? No, variables are consistent.
            # Let's check which anchor belongs to prim_b
            if anchor_b.GetParent() == prim_b or (info_b["type"]=="anchor" and anchor_b==prim_b):
                 target_anchor = anchor_a
                 mover_anchor = anchor_b
                 mover_part = part_b
            else:
                 target_anchor = anchor_b
                 mover_anchor = anchor_a
                 mover_part = part_a
            print(f"Mating {mover_part.GetName()} to {target_anchor.GetParent().GetName()}")

        # Execute Move
        self._apply_mate_transform(target_anchor, mover_anchor, mover_part)
        
    def _apply_mate_transform(self, target_anchor, mover_anchor, mover_part):
        # 1. Get Target World Transform
        mat_target = omni.usd.get_world_transform_matrix(target_anchor)
        
        # 2. Add Alignment Rotation (Flip 180 Y to face opposite)
        flip_mat = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,1,0), 180))
        target_frame = flip_mat * mat_target
        
        # 3. Get Mover Anchor Local Transform
        # Use UsdGeom.Xformable to ensure we get the API object
        local_transform = UsdGeom.Xformable(mover_anchor).GetLocalTransformation(Usd.TimeCode.Default())
        
        # 4. Calculate New World Transform for Mover Part
        # See previous derivation: Mover_World = Match_Frame * Inverse(Anchor_Local)
        mat_mover_new = local_transform.GetInverse() * target_frame
        
        # 5. Handle Parent Transform of Mover Part (if not World)
        parent = mover_part.GetParent()
        if parent and parent.GetPath() != "/":
            parent_world = omni.usd.get_world_transform_matrix(parent)
            mat_mover_local = mat_mover_new * parent_world.GetInverse()
        else:
            mat_mover_local = mat_mover_new
            
        # 6. Apply
        trans = mat_mover_local.ExtractTranslation()
        
        # Extract rotation carefully
        # Decompose returns (scale, rotation_matrix, ignored...)? No, GfMatrix4d.Factor? 
        # ExtractRotation() returns GfRotation.
        rot = mat_mover_local.ExtractRotation().Decompose(Gf.Vec3d(1,0,0), Gf.Vec3d(0,1,0), Gf.Vec3d(0,0,1))
        
        xform_api = UsdGeom.XformCommonAPI(mover_part)
        xform_api.SetTranslate(trans)
        xform_api.SetRotate(rot)
        
    def _on_toggle_anchor(self):
        """Toggles the anchored state of selected objects"""
        ctx = omni.usd.get_context()
        stage = ctx.get_stage()
        selection = ctx.get_selection().get_selected_prim_paths()
        
        for path in selection:
            prim = stage.GetPrimAtPath(path)
            if not prim: continue
            
            # Use custom attribute
            attr = prim.GetAttribute("custom:is_anchored")
            if not attr:
                attr = prim.CreateAttribute("custom:is_anchored", Sdf.ValueTypeNames.Bool)
                new_state = True
            else:
                new_state = not attr.Get()
                
            attr.Set(new_state)
            print(f"Set Anchored state of {prim.GetName()} to {new_state}")


    def destroy(self):
        super().destroy()
