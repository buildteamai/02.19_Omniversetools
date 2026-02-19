import omni.ui as ui
import omni.usd
from pxr import UsdGeom, Gf, Sdf, Usd
import traceback
from ..utils import usd_utils

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

class CreateObjectWindow(ui.Window):
    """
    A simple window to create and edit parametric objects (Box, Cylinder).
    """
    def __init__(self, title="Create Object", **kwargs):
        super().__init__(title, width=400, height=500, **kwargs)
        
        self._current_path = None # Path of object being edited
        self._is_editing = False

        # Object Types
        self._object_types = ["Box", "Cylinder"]
        self._object_type_model = ListItemModel(self._object_types)
        self._object_type_model.get_item_value_model(None, 0).set_value(0) # Default to Box
        self._object_type_model.get_item_value_model(None, 0).add_value_changed_fn(self._on_object_type_changed)

        # Box Dimensions
        self._length_ft = ui.SimpleIntModel(10)
        self._length_in = ui.SimpleFloatModel(0.0)
        
        self._width_ft = ui.SimpleIntModel(10)
        self._width_in = ui.SimpleFloatModel(0.0)
        
        self._height_ft = ui.SimpleIntModel(10)
        self._height_in = ui.SimpleFloatModel(0.0)
        
        # Cylinder Dimensions
        self._radius_ft = ui.SimpleIntModel(2)
        self._radius_in = ui.SimpleFloatModel(0.0)
        
        self._cyl_height_ft = ui.SimpleIntModel(10)
        self._cyl_height_in = ui.SimpleFloatModel(0.0)

        self._axis_options = ["X", "Y", "Z"]
        self._axis_model = ListItemModel(self._axis_options)
        self._axis_model.get_item_value_model(None, 0).set_value(1) # Default to Y axis

        self._materials = [
            "Concrete", 
            "Black Iron", 
            "Sheet Metal", 
            "Painted Blue", 
            "Painted Yellow", 
            "Painted Grey"
        ]
        
        self._material_colors = {
            "Concrete": (0.6, 0.6, 0.6),
            "Black Iron": (0.15, 0.15, 0.15),
            "Sheet Metal": (0.75, 0.75, 0.75),
            "Painted Blue": (0.1, 0.3, 0.8),
            "Painted Yellow": (0.9, 0.8, 0.1),
            "Painted Grey": (0.4, 0.4, 0.4)
        }
        
        self._material_model = ListItemModel(self._materials)
        # Set default to Concrete (index 0)
        self._material_model.get_item_value_model(None, 0).set_value(0)
        
        self._create_btn = None

        self._build_ui()
    
    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=10, padding=15):
                # Header
                ui.Label("Create Object", style={"font_size": 18, "color": 0xFFDDDDDD})
                ui.Separator(height=5)
                ui.Spacer(height=5)

                # --- Main Properties ---
                with ui.HStack(height=24):
                    ui.Label("Object Type:", width=100, style={"color": 0xFFAAAAAA})
                    ui.ComboBox(self._object_type_model)
                
                with ui.HStack(height=24):
                    ui.Label("Material:", width=100, style={"color": 0xFFAAAAAA})
                    ui.ComboBox(self._material_model)

                ui.Spacer(height=10)
                ui.Separator(height=5)
                ui.Spacer(height=10)

                # --- Dimensions ---
                ui.Label("Dimensions", style={"font_size": 16, "color": 0xFFCCCCCC})
                ui.Spacer(height=5)

                # Box Inputs
                self._box_container = ui.VStack(spacing=5)
                with self._box_container:
                    self._build_dim_row("Length (X)", self._length_ft, self._length_in)
                    self._build_dim_row("Height (Y)", self._height_ft, self._height_in)
                    self._build_dim_row("Width (Z)", self._width_ft, self._width_in)

                # Cylinder Inputs
                self._cylinder_container = ui.VStack(spacing=5, visible=False)
                with self._cylinder_container:
                     self._build_dim_row("Radius", self._radius_ft, self._radius_in)
                     self._build_dim_row("Height", self._cyl_height_ft, self._cyl_height_in)
                     with ui.HStack(height=24):
                        ui.Label("Axis:", width=100, style={"color": 0xFFAAAAAA})
                        ui.ComboBox(self._axis_model)

                ui.Spacer(height=20)
                ui.Separator(height=5)
                ui.Spacer(height=10)

                # --- Actions ---
                with ui.HStack(height=40, spacing=10):
                    self._create_btn = ui.Button("Create Object", clicked_fn=self._on_create, height=40, 
                                               style={"background_color": 0xFF2B5B2B, "font_size": 16})
                
                with ui.HStack(height=30, spacing=10):
                    ui.Button("Load From Selection", clicked_fn=self._on_load_selection, height=30)
                    ui.Button("Reset", clicked_fn=self._on_clear_selection, height=30, width=80)
        
        # Initial State
        self._on_object_type_changed(self._object_type_model.get_item_value_model(None, 0))

    def _build_dim_row(self, label, ft_model, in_model):
        """Builds a dimension row with Drag controls for Feet and Inches."""
        with ui.HStack(height=24, spacing=5):
            ui.Label(label, width=100, style={"color": 0xFFAAAAAA})
            
            # Feet
            ui.IntDrag(model=ft_model, min=0, max=100, width=ui.Fraction(1), style={"color": 0xFFEEEEEE})
            ui.Label("ft", width=20, style={"color": 0xFF888888})
            
            ui.Spacer(width=10)
            
            # Inches
            ui.FloatDrag(model=in_model, min=0.0, max=12.0, step=0.125, width=ui.Fraction(1), style={"color": 0xFFEEEEEE})
            ui.Label("in", width=20, style={"color": 0xFF888888})
    
    def _on_object_type_changed(self, model):
        idx = model.as_int
        is_box = (idx == 0)
        self._box_container.visible = is_box
        self._cylinder_container.visible = not is_box
    
    def _on_clear_selection(self):
        self._is_editing = False
        self._current_path = None
        if self._create_btn:
            self._create_btn.text = "Create Object"
        print("[CreateObject] Cleared selection using 'New' button.")

    def _on_load_selection(self):
        """Loads selected object properties into UI."""
        context = omni.usd.get_context()
        selection = context.get_selection().get_selected_prim_paths()
        if not selection:
            print("[CreateObject] No selection found.")
            return
        
        path = selection[0]
        stage = context.get_stage()
        prim = stage.GetPrimAtPath(path)
        
        if not prim.IsValid():
            return
            
        print(f"[CreateObject] Loading selection: {path}")

        # Try to detect type
        is_cylinder = prim.IsA(UsdGeom.Cylinder)
        is_mesh = prim.IsA(UsdGeom.Mesh)
        
        # Check custom attributes to confirm it's our parametric object
        # Box has: custom:length, custom:height, custom:width
        # Cylinder has: custom:radius, custom:height, custom:axis
        
        found_type = False

        if is_cylinder and prim.HasAttribute("custom:radius"):
            self._object_type_model.get_item_value_model(None, 0).set_value(1) # Cylinder
            
            radius_attr = prim.GetAttribute("custom:radius")
            height_attr = prim.GetAttribute("custom:height")
            axis_attr = prim.GetAttribute("custom:axis")
            
            radius = radius_attr.Get() if radius_attr and radius_attr.IsValid() and radius_attr.HasValue() else 2.0
            height = height_attr.Get() if height_attr and height_attr.IsValid() and height_attr.HasValue() else 10.0
            axis = axis_attr.Get() if axis_attr and axis_attr.IsValid() and axis_attr.HasValue() else "Y"
            
            self._set_ui_values_cylinder(radius, height, axis)
            self._is_editing = True
            self._current_path = path
            if self._create_btn:
                self._create_btn.text = "Update Object"
            found_type = True
            
        elif is_mesh and prim.HasAttribute("custom:length"):
            self._object_type_model.get_item_value_model(None, 0).set_value(0) # Box
            
            length_attr = prim.GetAttribute("custom:length")
            height_attr = prim.GetAttribute("custom:height")
            width_attr = prim.GetAttribute("custom:width")
            
            length = length_attr.Get() if length_attr and length_attr.IsValid() and length_attr.HasValue() else 10.0
            height = height_attr.Get() if height_attr and height_attr.IsValid() and height_attr.HasValue() else 10.0
            width = width_attr.Get() if width_attr and width_attr.IsValid() and width_attr.HasValue() else 10.0
            
            self._set_ui_values_box(length, height, width)
            self._is_editing = True
            self._current_path = path
            if self._create_btn:
                self._create_btn.text = "Update Object"
            found_type = True
            
        if not found_type:
            print("[CreateObject] Selected object is not a parametric object created by this tool.")
            self._on_clear_selection()

    def _set_ui_values_box(self, length, height, width):
        # Convert total inches back to Ft/In
        self._length_ft.set_value(int(length // 12))
        self._length_in.set_value(length % 12)
        
        self._height_ft.set_value(int(height // 12))
        self._height_in.set_value(height % 12)
        
        self._width_ft.set_value(int(width // 12))
        self._width_in.set_value(width % 12)

    def _set_ui_values_cylinder(self, radius, height, axis):
        self._radius_ft.set_value(int(radius // 12))
        self._radius_in.set_value(radius % 12)
        
        self._cyl_height_ft.set_value(int(height // 12))
        self._cyl_height_in.set_value(height % 12)
        
        if axis in self._axis_options:
            idx = self._axis_options.index(axis)
            self._axis_model.get_item_value_model(None, 0).set_value(idx)

    def _on_create(self):
        """Creates or Updates the object."""
        try:
            print(f"[CreateObject] {'Updating' if self._is_editing else 'Creating'} object...")
            
            # Get Material
            mat_idx = self._material_model.get_item_value_model(None, 0).as_int
            if 0 <= mat_idx < len(self._materials):
                material_name = self._materials[mat_idx]
                color = self._material_colors.get(material_name, (0.5, 0.5, 0.5))
            else:
                material_name = "Default"
                color = (0.5, 0.5, 0.5)

            # Get stage
            context = omni.usd.get_context()
            stage = context.get_stage()
            if not stage: return

            # Enforce Units
            usd_utils.setup_stage_units(stage)

            # Determine Object Type
            type_idx = self._object_type_model.get_item_value_model(None, 0).as_int
            object_type = self._object_types[type_idx]
            
            # Determine Path
            is_new = True
            current_transform = []
            
            if self._is_editing and self._current_path:
                path = self._current_path
                # Verify path still exists
                prim = stage.GetPrimAtPath(path)
                if not prim:
                    print(f"[CreateObject] Error: Object at {path} no longer exists.")
                    self._on_clear_selection()
                    return
                # Capture current transform before recreating
                current_transform = usd_utils.get_local_transform(prim)
                is_new = False
            else:
                # New Object Placement Logic
                # Check for selection
                selection = context.get_selection().get_selected_prim_paths()
                if selection:
                    # Place relative to first selection
                    ref_path = selection[0]
                    ref_prim = stage.GetPrimAtPath(ref_path)
                    if ref_prim:
                        # For now, just copy transform of selection
                        # Ideally we'd stack it, but copying is a good start to be "near"
                        current_transform = usd_utils.get_local_transform(ref_prim)
                
                # Create a unique path
                base_name = f"{object_type}_{material_name.replace(' ', '_')}"
                base_path = f"/World/{base_name}"
                path = base_path
                counter = 1
                while stage.GetPrimAtPath(path):
                    path = f"{base_path}_{counter}"
                    counter += 1
            
            if object_type == "Box":
                # Convert Ft/In to Total Inches
                dim_x = (self._length_ft.get_value_as_int() * 12.0) + self._length_in.get_value_as_float()
                dim_y = (self._height_ft.get_value_as_int() * 12.0) + self._height_in.get_value_as_float()
                dim_z = (self._width_ft.get_value_as_int() * 12.0) + self._width_in.get_value_as_float()
                
                self._create_generic_box(stage, path, dim_x, dim_y, dim_z, color, is_new)
                print(f"[CreateObject] {'Updated' if self._is_editing else 'Created'} {material_name} Box.")

            elif object_type == "Cylinder":
                radius = (self._radius_ft.get_value_as_int() * 12.0) + self._radius_in.get_value_as_float()
                height = (self._cyl_height_ft.get_value_as_int() * 12.0) + self._cyl_height_in.get_value_as_float()
                axis_idx = self._axis_model.get_item_value_model(None, 0).as_int
                axis = self._axis_options[axis_idx]
                
                self._create_cylinder(stage, path, radius, height, axis, color, is_new)
                print(f"[CreateObject] {'Updated' if self._is_editing else 'Created'} {material_name} Cylinder.")

            # Restore Transform if we captured one
            if current_transform:
                new_prim = stage.GetPrimAtPath(path)
                if new_prim:
                    usd_utils.set_local_transform(new_prim, current_transform)

            context.get_selection().set_selected_prim_paths([path], True)
            
            # If creating new, maybe reset UI? Or keep it for dupes. Keeping it is fine.
            # If updating, stay in update mode.
            
        except Exception as e:
            print(f"[CreateObject] Error: {e}")
            traceback.print_exc()

    def _create_generic_box(self, stage, path, size_x, size_y, size_z, color, is_new=True):
        mesh = UsdGeom.Mesh.Define(stage, path)
        
        # Ensure we start fresh if new, or overwrite if existing
        # mesh.ClearXformOpOrder() # Keep existing transform if updating? 
        # For now, let's allow moving properites but maybe reset geometry transforms if they mess up geometry.
        # But if user moved the box, we don't want to reset position.
        # However, our geometry generation assumes local space.
        
        if is_new:
            # Use XformCommonAPI for proper transform widget support
            xform_api = UsdGeom.XformCommonAPI(mesh)
            xform_api.SetTranslate((0, 0, 0))
            xform_api.SetRotate((0, 0, 0))
            xform_api.SetScale((1, 1, 1))
        
        # Define Half-Sizes
        hx = size_x / 2.0
        hz = size_z / 2.0
        hy = size_y # Y is full height from 0
        
        # Vertices (8 points)
        points = [
            Gf.Vec3f(-hx, 0, -hz),
            Gf.Vec3f(hx, 0, -hz),
            Gf.Vec3f(hx, 0, hz),
            Gf.Vec3f(-hx, 0, hz),
            Gf.Vec3f(-hx, hy, -hz),
            Gf.Vec3f(hx, hy, -hz),
            Gf.Vec3f(hx, hy, hz),
            Gf.Vec3f(-hx, hy, hz),
        ]
        
        # Face Vertex Counts (6 faces, 4 verts each)
        face_counts = [4] * 6
        
        # Face Indices (CCW winding)
        face_indices = [
            7, 6, 5, 4, # Top (+Y)
            0, 1, 2, 3, # Bottom (-Y)
            3, 2, 6, 7, # Front (+Z)
            1, 0, 4, 5, # Back (-Z)
            2, 1, 5, 6, # Right (+X)
            0, 3, 7, 4, # Left (-X)
        ]
        
        # Set Attributes
        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexCountsAttr(face_counts)
        mesh.CreateFaceVertexIndicesAttr(face_indices)
        
        # Set Extent
        extent = [Gf.Vec3f(-hx, 0, -hz), Gf.Vec3f(hx, hy, hz)]
        mesh.CreateExtentAttr(extent)
        
        # Display Color
        mesh.CreateDisplayColorAttr([color])
        
        # Metadata
        prim = mesh.GetPrim()
        prim.CreateAttribute("custom:length", Sdf.ValueTypeNames.Double).Set(size_x)
        prim.CreateAttribute("custom:height", Sdf.ValueTypeNames.Double).Set(size_y)
        prim.CreateAttribute("custom:width", Sdf.ValueTypeNames.Double).Set(size_z)

    def _create_cylinder(self, stage, path, radius, height, axis, color, is_new=True):
        cyl = UsdGeom.Cylinder.Define(stage, path)
        
        if is_new:
            # Use XformCommonAPI for proper transform widget support
            xform_api = UsdGeom.XformCommonAPI(cyl)
            xform_api.SetTranslate((0, 0, 0))
            xform_api.SetRotate((0, 0, 0))
            xform_api.SetScale((1, 1, 1))
        
        # Set Attributes
        cyl.GetRadiusAttr().Set(radius)
        cyl.GetHeightAttr().Set(height)
        
        # Apply Axis & Grounding only if new
        if is_new:
            if axis == "X":
                cyl.GetAxisAttr().Set(UsdGeom.Tokens.x)
            elif axis == "Y":
                 cyl.GetAxisAttr().Set(UsdGeom.Tokens.y)
                 # Ground at Y=0
                 UsdGeom.XformCommonAPI(cyl).SetTranslate((0, height / 2.0, 0))
            elif axis == "Z":
                 cyl.GetAxisAttr().Set(UsdGeom.Tokens.z)
        
        # Display Color
        cyl.CreateDisplayColorAttr([color])
        
        # Metadata
        prim = cyl.GetPrim()
        prim.CreateAttribute("custom:radius", Sdf.ValueTypeNames.Double).Set(radius)
        prim.CreateAttribute("custom:height", Sdf.ValueTypeNames.Double).Set(height)
        prim.CreateAttribute("custom:axis", Sdf.ValueTypeNames.String).Set(axis)


