import os
from pathlib import Path
from build123d import *
from ..utils import usd_utils
import omni.usd
from pxr import UsdGeom, Sdf

class StepImporter:
    def __init__(self):
        pass

    def import_to_stage(self, file_path: str, target_path: str = "/World/Imported") -> bool:
        """
        Imports a STEP file, explodes it into solids, and creates USD meshes.
        
        Args:
            file_path: Absolute path to the .step/.stp file.
            target_path: USD path where the imported geometry group will be created.
            
        Returns:
            True if successful, False otherwise.
        """
        if not os.path.exists(file_path):
            print(f"[StepImporter] File not found: {file_path}")
            return False

        file_name = Path(file_path).stem
        # Sanitize name for USD (ensure it starts with a letter or underscore, no spaces)
        safe_name = "".join(c if c.isalnum() else "_" for c in file_name)
        if safe_name and safe_name[0].isdigit():
            safe_name = "_" + safe_name
            
        # Create a unique root path to avoid collisions
        base_root_path = f"{target_path}/{safe_name}"
        root_prim_path = base_root_path
        stage = omni.usd.get_context().get_stage()
        
        # Simple incrementer if path exists
        counter = 1
        while stage.GetPrimAtPath(root_prim_path):
            root_prim_path = f"{base_root_path}_{counter}"
            counter += 1

        # Create a Xform for the root
        UsdGeom.Xform.Define(stage, root_prim_path)

        try:
            print(f"[StepImporter] Loading STEP file: {file_path}")
            # Import STEP using build123d
            imported = import_step(file_path)
            
            # Explode into solids
            solids = []
            if isinstance(imported, Compound):
                # .solids() returns a list of Solid objects
                solids = list(imported.solids())
                if not solids:
                    # Might be a shell or just faces?
                    print("[StepImporter] Warning: No solids found in Compound, attempting to use raw shape.")
                    solids = [imported]
            elif isinstance(imported, Solid):
                solids = [imported]
            else:
                # Shape, Face, etc.
                solids = [imported] 

            print(f"[StepImporter] Found {len(solids)} solids. Converting to USD...")

            # Create meshes for each solid
            for i, solid in enumerate(solids):
                # TODO: In the future, we might want to carry over names from STEP if available.
                # standard OCP import might not preserve names easily without lower level access.
                solid_prim_name = f"Solid_{i}"
                solid_path = f"{root_prim_path}/{solid_prim_name}"
                
                mesh_prim = usd_utils.create_mesh_from_shape(stage, solid_path, solid)
                
                if mesh_prim:
                    # Add TwinImportAPI schema concept (custom attribute for now)
                    # We'll use this later for tagging.
                    prim = mesh_prim.GetPrim()
                    # Example metadata
                    prim.CreateAttribute("twin:original_file", Sdf.ValueTypeNames.String).Set(file_path)
                    prim.CreateAttribute("twin:import_index", Sdf.ValueTypeNames.Int).Set(i)

            print(f"[StepImporter] Import complete: {root_prim_path}")
            return True

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[StepImporter] Error importing STEP: {e}")
            return False
