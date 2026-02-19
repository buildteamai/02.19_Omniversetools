import omni.usd
from pxr import Usd, UsdGeom, Vt, Gf
import build123d as bd

def create_mesh_from_shape(stage: Usd.Stage, path: str, shape: bd.Shape, tolerance: float = 0.001):
    """
    Creates a USD Mesh from a build123d Shape at the specified path.
    """
    # Tessellate the shape
    # build123d/OCP tessellation returns (vertices, triangles)
    # vertices is a list of Vector objects
    # triangles is a list of (i1, i2, i3) tuples
    mesh_data = shape.tessellate(tolerance)
    if not mesh_data:
        print(f"Warning: Tessellation failed for shape at {path}")
        return None
        
    vertices, triangles = mesh_data
    
    # Convert vertices to Gf.Vec3f
    usd_points = [Gf.Vec3f(v.X, v.Y, v.Z) for v in vertices]
    
    # Flatten triangles to faceVertexIndices
    face_vertex_indices = []
    for tri in triangles:
        face_vertex_indices.extend(tri)
        
    # faceVertexCounts is just [3, 3, 3, ...] since we have triangles
    face_vertex_counts = [3] * len(triangles)
    
    # Create the mesh prim
    mesh_prim = UsdGeom.Mesh.Define(stage, path)
    
    # Set attributes
    mesh_prim.GetPointsAttr().Set(usd_points)
    mesh_prim.GetFaceVertexIndicesAttr().Set(face_vertex_indices)
    mesh_prim.GetFaceVertexCountsAttr().Set(face_vertex_counts)
    
    # Optional: Set normals if available, but for now let's rely on auto-normals or add later if needed.
    # extent
    mesh_prim.GetExtentAttr().Set(mesh_prim.ComputeExtent(usd_points))
    
    return mesh_prim

def create_basis_curves_from_edges(stage: Usd.Stage, path: str, edges: list, color: Gf.Vec3f = None, width: float = 0.1):
    """
    Creates a USD BasisCurves prim from a list of build123d Edges.
    Assumes linear curves (degree 1).
    """
    if not edges:
        return None

    # Collect points and curve vertex counts
    points = []
    curve_vertex_counts = []
    
    for edge in edges:
        # Discretize edge to get points
        # For straight lines, we just need endpoints. 
        # For curves, we might need more, but let's start with simple discretization
        # or just endpoints if we know they are lines.
        # Let's use a small discretization to be safe for diverse edge types.
        
        # OCP Edge.discretize returns list of Pnt
        # We can also jsut get start and end if we assume lines.
        # Let's assume linear for "Construction Lines" for now, or simplistic discretization.
        
        try:
            # Check if line
            # geom_type is a property in build123d
            if edge.geom_type.name == 'LINE':
                p0 = edge.start_point()
                p1 = edge.end_point()
                edge_points = [p0, p1]
            else:
                # Discretize
                # This returns a list of vectors (Vector)
                edge_points = edge.discretize(deflection=0.1)
                
            usd_edge_points = [Gf.Vec3f(p.X, p.Y, p.Z) for p in edge_points]
            
            points.extend(usd_edge_points)
            curve_vertex_counts.append(len(usd_edge_points))
            
        except Exception as e:
            print(f"Error processing edge for curves: {e}")
            continue

    if not points:
        return None

    curves = UsdGeom.BasisCurves.Define(stage, path)
    curves.GetTypeAttr().Set(UsdGeom.Tokens.linear)
    # Set Width with correct type
    curves.GetWidthsAttr().Set(Vt.FloatArray([width]))
    curves.SetWidthsInterpolation(UsdGeom.Tokens.constant)
    curves.GetPointsAttr().Set(Vt.Vec3fArray(points))
    curves.GetCurveVertexCountsAttr().Set(Vt.IntArray(curve_vertex_counts))
    
    
    if color:
        curves.GetDisplayColorAttr().Set([color])
        
    # Compute Extent (Bounding Box)
    # Required for proper culling/visibility
    # Create Vt arrays for correctness
    vt_points = Vt.Vec3fArray(points)
    vt_widths = Vt.FloatArray([width])
    
    extent = UsdGeom.BasisCurves.ComputeExtent(vt_points, vt_widths)
    curves.GetExtentAttr().Set(extent)
    
    return curves

def export_solid_to_usd(stage: Usd.Stage, solid: bd.Solid, path: str, tolerance: float = 0.001):
    """
    Wrapper for create_mesh_from_shape to maintain consistent API naming.
    Exports a build123d solid to a USD Mesh at the specified path.
    """
    return create_mesh_from_shape(stage, path, solid, tolerance)

def setup_stage_units(stage: Usd.Stage):
    """
    Sets the stage units to Inches and Up Axis to Y.
    Also ensures TimeCodesPerSecond is set (default 24).
    """
    # TimeCodesPerSecond
    # Older USD versions might not have HasAuthoredTimeCodesPerSecond
    # Just set it if it's default (24.0) or check manually
    try:
        if not stage.HasAuthoredTimeCodesPerSecond():
            stage.SetTimeCodesPerSecond(24.0)
    except AttributeError:
        # Fallback for older USD
        # If we can't check, just set it to be safe, or check the value
        if stage.GetTimeCodesPerSecond() == 24.0:
             stage.SetTimeCodesPerSecond(24.0)

    # Set Units to Inches (0.0254 meters per unit)
    UsdGeom.SetStageMetersPerUnit(stage, 0.0254)

    # Set Up Axis to Y (Standard for current Enclosure Configurator)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

def get_local_transform(prim: Usd.Prim):
    """
    Captures the local transform (translate, rotate, scale, transform) of a prim.
    Returns a list of xformOps that can be re-applied.
    """
    xformable = UsdGeom.Xformable(prim)
    if not xformable:
        return []
    
    ops = xformable.GetOrderedXformOps()
    transform_data = []
    for op in ops:
        op_name = op.GetName()
        op_type = op.GetOpType()
        op_value = op.Get()
        transform_data.append((op_name, op_type, op_value))
    
    return transform_data

def set_local_transform(prim: Usd.Prim, transform_data: list):
    """
    Applies a captured transform list to a prim.
    Handles operations with precision and suffixes (e.g., xformOp:translate:pivot).
    """
    xformable = UsdGeom.Xformable(prim)
    xformable.ClearXformOpOrder()
    
    for name, op_type, value in transform_data:
        # name is full attribute name like "xformOp:translate" or "xformOp:rotateXYZ:pivot"
        # We need to extract the suffix if it exists.
        # Format: xformOp:<opType>[:<suffix>]
        
        parts = name.split(':')
        suffix = ""
        if len(parts) > 2:
            suffix = ":".join(parts[2:]) # Join everything after opType
            
        try:
            # AddXformOp(opType, precision, opSuffix, inverse)
            # We don't know precision easily, but default is usually fine (Double).
            # If value is present, we can infer.
            
            # UsdGeom.XformOp.Type is the enum op_type
            new_op = xformable.AddXformOp(op_type, UsdGeom.XformOp.PrecisionDouble, suffix)
            
            if value is not None:
                new_op.Set(value)
                
        except Exception as e:
            print(f"[usd_utils] Error restoring xformOp {name}: {e}")

def get_world_transform_matrix(prim: Usd.Prim, time: Usd.TimeCode = Usd.TimeCode.Default()):
    """
    Computes the world transform matrix for a given prim using UsdGeom.Xformable.
    Returns: Gf.Matrix4d
    """
    xform = UsdGeom.Xformable(prim)
    if not xform:
        return Gf.Matrix4d().SetIdentity()
        
    return xform.ComputeLocalToWorldTransform(time)


