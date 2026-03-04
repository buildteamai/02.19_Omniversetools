"""
Mesh Importer — loads OBJ and GLB files into the USD stage.

Designed for TripoSR output meshes (vertex-colored OBJ/GLB) but works
with any standard OBJ or GLB file.  Zero external dependencies beyond
pxr and the Python stdlib.
"""

import os
import struct
import json
from pathlib import Path

import omni.usd
from pxr import UsdGeom, UsdShade, Sdf, Vt, Gf


# ---------------------------------------------------------------------------
# OBJ parser
# ---------------------------------------------------------------------------
def _parse_obj(file_path: str):
    """
    Parse a Wavefront OBJ file.

    Returns:
        vertices   – list of (x, y, z) tuples
        faces      – list of face tuples; each face is a tuple of 0-based vertex indices
        normals    – list of (nx, ny, nz) tuples  (may be empty)
        colors     – list of (r, g, b) tuples per vertex (may be empty)
        uvs        – list of (u, v) per face-vertex in face order (faceVarying),
                     or empty list if no UVs present
    """
    vertices = []
    normals = []
    colors = []
    texcoords = []  # raw vt entries
    faces = []
    face_uv_indices = []  # per-face list of uv indices

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            key = parts[0]

            if key == "v":
                floats = [float(x) for x in parts[1:]]
                vertices.append(tuple(floats[:3]))
                # Vertex colours encoded as extra r g b on the v line
                if len(floats) >= 6:
                    colors.append(tuple(floats[3:6]))

            elif key == "vt":
                texcoords.append((float(parts[1]), float(parts[2])))

            elif key == "vn":
                normals.append((float(parts[1]), float(parts[2]), float(parts[3])))

            elif key == "f":
                # Faces can be: idx  or  idx/uv  or  idx/uv/n  or  idx//n
                face_verts = []
                face_uvs = []
                for tok in parts[1:]:
                    indices = tok.split("/")
                    vi = int(indices[0])
                    face_verts.append(vi - 1 if vi > 0 else vi)
                    # UV index (second component)
                    if len(indices) >= 2 and indices[1]:
                        uvi = int(indices[1])
                        face_uvs.append(uvi - 1 if uvi > 0 else uvi)
                faces.append(tuple(face_verts))
                if face_uvs:
                    face_uv_indices.append(tuple(face_uvs))

    # Build faceVarying UV array (one UV per face-vertex, in face order)
    uvs = []
    if texcoords and face_uv_indices and len(face_uv_indices) == len(faces):
        for face_uvs in face_uv_indices:
            for uvi in face_uvs:
                uvs.append(texcoords[uvi])

    return vertices, faces, normals, colors, uvs


# ---------------------------------------------------------------------------
# GLB parser (minimal, spec-compliant for mesh data)
# ---------------------------------------------------------------------------
def _parse_glb(file_path: str):
    """
    Parse a binary glTF 2.0 (.glb) file and extract the first mesh primitive.

    Returns: (vertices, faces, normals, colors, uvs, texture_path).
    texture_path is the path to an extracted embedded texture image, or None.
    """
    with open(file_path, "rb") as f:
        # Header: magic(4) version(4) length(4)
        magic, version, length = struct.unpack("<III", f.read(12))
        if magic != 0x46546C67:
            raise ValueError("Not a valid GLB file")

        # Chunk 0: JSON
        chunk_len, chunk_type = struct.unpack("<II", f.read(8))
        json_bytes = f.read(chunk_len)
        gltf = json.loads(json_bytes)

        # Chunk 1: BIN
        bin_data = b""
        if f.tell() < length:
            chunk_len, chunk_type = struct.unpack("<II", f.read(8))
            bin_data = f.read(chunk_len)

    # Helper to read accessor data from the binary buffer
    accessors = gltf.get("accessors", [])
    buffer_views = gltf.get("bufferViews", [])

    def read_accessor(idx):
        acc = accessors[idx]
        bv = buffer_views[acc["bufferView"]]
        offset = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        count = acc["count"]
        comp_type = acc["componentType"]
        acc_type = acc["type"]

        # Component sizes
        comp_sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
        comp_fmts = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
        type_counts = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}

        n_comps = type_counts[acc_type]
        fmt = f"<{n_comps}{comp_fmts[comp_type]}"
        stride = bv.get("byteStride", struct.calcsize(fmt))
        result = []
        for i in range(count):
            pos = offset + i * stride
            vals = struct.unpack_from(fmt, bin_data, pos)
            result.append(vals if n_comps > 1 else vals[0])
        return result

    # Get first mesh primitive
    mesh = gltf["meshes"][0]
    prim = mesh["primitives"][0]
    attrs = prim["attributes"]

    vertices = read_accessor(attrs["POSITION"])
    normals = read_accessor(attrs["NORMAL"]) if "NORMAL" in attrs else []

    colors = []
    if "COLOR_0" in attrs:
        raw = read_accessor(attrs["COLOR_0"])
        # Might be VEC3 or VEC4, normalise to RGB tuples
        colors = [tuple(c[:3]) for c in raw]

    # UVs
    uvs = []
    if "TEXCOORD_0" in attrs:
        uvs = list(read_accessor(attrs["TEXCOORD_0"]))

    # Indices
    faces = []
    if "indices" in prim:
        raw_indices = read_accessor(prim["indices"])
        # Triangles: group into faces of 3
        for i in range(0, len(raw_indices), 3):
            faces.append((raw_indices[i], raw_indices[i + 1], raw_indices[i + 2]))
    else:
        # Non-indexed: every 3 verts form a face
        for i in range(0, len(vertices), 3):
            faces.append((i, i + 1, i + 2))

    # Extract embedded PBR textures
    textures = _extract_glb_textures(gltf, bin_data, buffer_views, file_path)

    return vertices, faces, normals, colors, uvs, textures


def _extract_texture_by_index(gltf, bin_data, buffer_views, tex_idx, glb_path, suffix):
    """
    Extract a single texture image from the GLB by glTF texture index.
    Returns the path to the extracted file, or None.
    """
    textures = gltf.get("textures", [])
    images = gltf.get("images", [])

    if tex_idx is None or tex_idx >= len(textures):
        return None

    img_idx = textures[tex_idx].get("source")
    if img_idx is None or img_idx >= len(images):
        return None

    img_def = images[img_idx]
    bv_idx = img_def.get("bufferView")
    if bv_idx is None or bv_idx >= len(buffer_views):
        return None

    bv = buffer_views[bv_idx]
    offset = bv.get("byteOffset", 0)
    length = bv["byteLength"]
    img_bytes = bin_data[offset : offset + length]

    # Determine extension from mimeType
    mime = img_def.get("mimeType", "image/png")
    ext = ".png" if "png" in mime else ".jpg"

    # Write to a temp file next to the GLB
    glb_dir = os.path.dirname(glb_path)
    texture_path = os.path.join(glb_dir, f"extracted_{suffix}{ext}")
    with open(texture_path, "wb") as f:
        f.write(img_bytes)

    return texture_path


def _extract_glb_textures(gltf, bin_data, buffer_views, glb_path):
    """
    Extract all PBR textures from the first material in a GLB.

    Returns:
        dict with keys "baseColor", "metallicRoughness", "normal" — each
        mapped to a file path or None.
    """
    result = {}
    materials = gltf.get("materials", [])
    if not materials:
        return result

    mat = materials[0]
    pbr = mat.get("pbrMetallicRoughness", {})

    # baseColorTexture
    bc_tex = pbr.get("baseColorTexture")
    if bc_tex:
        path = _extract_texture_by_index(
            gltf, bin_data, buffer_views, bc_tex.get("index"), glb_path, "baseColor",
        )
        if path:
            result["baseColor"] = path

    # metallicRoughnessTexture
    mr_tex = pbr.get("metallicRoughnessTexture")
    if mr_tex:
        path = _extract_texture_by_index(
            gltf, bin_data, buffer_views, mr_tex.get("index"), glb_path, "metallicRoughness",
        )
        if path:
            result["metallicRoughness"] = path

    # normalTexture (lives on the material, not inside pbrMetallicRoughness)
    n_tex = mat.get("normalTexture")
    if n_tex:
        path = _extract_texture_by_index(
            gltf, bin_data, buffer_views, n_tex.get("index"), glb_path, "normal",
        )
        if path:
            result["normal"] = path

    return result


# ---------------------------------------------------------------------------
# MeshImporter
# ---------------------------------------------------------------------------
class MeshImporter:
    """Imports OBJ / GLB mesh files into the current USD stage."""

    SUPPORTED_EXTENSIONS = {".obj", ".glb"}

    def import_to_stage(
        self,
        file_path: str,
        target_path: str = "/World/Imported",
        source_tag: str = "",
        texture_path: str = None,
    ) -> bool:
        """
        Import a mesh file and create a USD Mesh on the active stage.

        Args:
            file_path:    Absolute path to the .obj or .glb file.
            target_path:  USD parent Xform path for the imported geometry.
            source_tag:   Optional origin label (e.g. "triposr") stored as metadata.
            texture_path: Optional path to a texture image (PNG/JPG). For OBJ meshes
                          with baked textures. GLB textures are extracted automatically.

        Returns:
            True on success, False otherwise.
        """
        if not os.path.exists(file_path):
            print(f"[MeshImporter] File not found: {file_path}")
            return False

        ext = Path(file_path).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            print(f"[MeshImporter] Unsupported format: {ext}")
            return False

        # Parse ----------------------------------------------------------------
        uvs = []
        textures = {}
        try:
            if ext == ".obj":
                vertices, faces, normals, colors, uvs = _parse_obj(file_path)
                textures = {"baseColor": texture_path} if texture_path else {}
            else:
                vertices, faces, normals, colors, uvs, textures = _parse_glb(file_path)
                # Explicit texture_path overrides GLB-embedded baseColor
                if texture_path:
                    textures["baseColor"] = texture_path
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[MeshImporter] Failed to parse {file_path}: {e}")
            return False

        if not vertices or not faces:
            print(f"[MeshImporter] Empty mesh in {file_path}")
            return False

        # Stage setup ----------------------------------------------------------
        stage = omni.usd.get_context().get_stage()

        file_name = Path(file_path).stem
        safe_name = "".join(c if c.isalnum() else "_" for c in file_name)
        if safe_name and safe_name[0].isdigit():
            safe_name = "_" + safe_name

        # Unique root path
        base_root = f"{target_path}/{safe_name}"
        root_path = base_root
        counter = 1
        while stage.GetPrimAtPath(root_path):
            root_path = f"{base_root}_{counter}"
            counter += 1

        UsdGeom.Xform.Define(stage, root_path)

        # GLB files are in meters (glTF spec); our scene uses inches
        if ext == ".glb":
            xformable = UsdGeom.Xformable(stage.GetPrimAtPath(root_path))
            xformable.AddScaleOp().Set(Gf.Vec3f(39.3701, 39.3701, 39.3701))

        # Create USD Mesh ------------------------------------------------------
        mesh_path = f"{root_path}/Mesh"
        mesh_prim = UsdGeom.Mesh.Define(stage, mesh_path)

        # Points
        usd_points = Vt.Vec3fArray([Gf.Vec3f(*v) for v in vertices])
        mesh_prim.GetPointsAttr().Set(usd_points)

        # Face topology
        face_vertex_counts = Vt.IntArray([len(f) for f in faces])
        flat_indices = []
        for f in faces:
            flat_indices.extend(f)
        face_vertex_indices = Vt.IntArray(flat_indices)

        mesh_prim.GetFaceVertexCountsAttr().Set(face_vertex_counts)
        mesh_prim.GetFaceVertexIndicesAttr().Set(face_vertex_indices)

        # Normals (per-vertex if available)
        if normals and len(normals) == len(vertices):
            usd_normals = Vt.Vec3fArray([Gf.Vec3f(*n) for n in normals])
            mesh_prim.GetNormalsAttr().Set(usd_normals)
            mesh_prim.SetNormalsInterpolation(UsdGeom.Tokens.vertex)

        # Texture UVs + material  OR  vertex colours
        has_texture = (
            textures.get("baseColor")
            and os.path.exists(textures["baseColor"])
            and uvs
        )

        if has_texture:
            self._apply_pbr_material(stage, root_path, mesh_prim, uvs, textures, ext)
        elif colors and len(colors) == len(vertices):
            # Vertex colours fallback
            display_color = Vt.Vec3fArray([Gf.Vec3f(*c) for c in colors])
            mesh_prim.GetDisplayColorAttr().Set(display_color)
            mesh_prim.GetDisplayColorPrimvar().SetInterpolation(UsdGeom.Tokens.vertex)

        # Extent
        mesh_prim.GetExtentAttr().Set(UsdGeom.Mesh.ComputeExtent(usd_points))

        # Subdivision — we want the mesh as-is, not subdivided
        mesh_prim.GetSubdivisionSchemeAttr().Set("none")

        # Metadata -------------------------------------------------------------
        prim = mesh_prim.GetPrim()
        prim.SetCustomDataByKey("twin:source_file", file_path)
        prim.SetCustomDataByKey("twin:source_format", ext.lstrip("."))
        if source_tag:
            prim.SetCustomDataByKey("twin:import_source", source_tag)
        if has_texture:
            prim.SetCustomDataByKey("twin:texture_file", textures["baseColor"])

        vert_count = len(vertices)
        face_count = len(faces)
        tex_tag = " (textured)" if has_texture else ""
        print(
            f"[MeshImporter] Imported {vert_count} verts, {face_count} faces{tex_tag} → {mesh_path}"
        )
        return True

    # ------------------------------------------------------------------
    # PBR material helpers
    # ------------------------------------------------------------------
    def _apply_pbr_material(self, stage, root_path, mesh_prim, uvs, textures, ext):
        """
        Create UV primvar on the mesh and build a full PBR UsdPreviewSurface
        material graph from the extracted texture dict.

        textures dict keys: "baseColor", "metallicRoughness", "normal"
        (any may be absent).

        For OBJ: uvs are faceVarying (one per face-vertex), V already correct.
        For GLB: uvs are per-vertex with vertex interpolation; V must be flipped
                 (glTF V=0 is top, USD V=0 is bottom).
        """
        primvar_api = UsdGeom.PrimvarsAPI(mesh_prim)

        if ext == ".glb":
            # GLB: per-vertex UVs, flip V for USD convention
            uv_data = Vt.Vec2fArray([Gf.Vec2f(u, 1.0 - v) for u, v in uvs])
            st_primvar = primvar_api.CreatePrimvar(
                "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex,
            )
            st_primvar.Set(uv_data)
        else:
            # OBJ: faceVarying UVs from xatlas, already in correct convention
            face_counts = mesh_prim.GetFaceVertexCountsAttr().Get()
            total_face_verts = sum(face_counts)
            if len(uvs) != total_face_verts:
                print(f"[MeshImporter] UV count mismatch: {len(uvs)} vs {total_face_verts} face-verts, skipping texture")
                return
            uv_data = Vt.Vec2fArray([Gf.Vec2f(*uv) for uv in uvs])
            st_primvar = primvar_api.CreatePrimvar(
                "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying,
            )
            st_primvar.Set(uv_data)

        # Build material graph under /root/Looks
        looks_path = f"{root_path}/Looks"
        mat_path = f"{looks_path}/TripoSR_PBR"

        material = UsdShade.Material.Define(stage, mat_path)

        # --- UsdPreviewSurface shader ---
        pbr_path = f"{mat_path}/PBRShader"
        pbr_shader = UsdShade.Shader.Define(stage, pbr_path)
        pbr_shader.CreateIdAttr("UsdPreviewSurface")
        material.CreateSurfaceOutput().ConnectToSource(
            pbr_shader.ConnectableAPI(), "surface",
        )

        # --- Shared PrimvarReader for ST coords ---
        reader_path = f"{mat_path}/STReader"
        reader_shader = UsdShade.Shader.Define(stage, reader_path)
        reader_shader.CreateIdAttr("UsdPrimvarReader_float2")
        reader_shader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
        reader_shader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

        # --- baseColor texture ---
        base_color_path = textures.get("baseColor")
        if base_color_path and os.path.exists(base_color_path):
            tex_node = UsdShade.Shader.Define(stage, f"{mat_path}/DiffuseTexture")
            tex_node.CreateIdAttr("UsdUVTexture")
            tex_node.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                base_color_path.replace("\\", "/")
            )
            tex_node.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
            tex_node.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")
            tex_node.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
                reader_shader.ConnectableAPI(), "result",
            )
            tex_node.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
            pbr_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                tex_node.ConnectableAPI(), "rgb",
            )

        # --- metallicRoughness texture ---
        mr_path = textures.get("metallicRoughness")
        if mr_path and os.path.exists(mr_path):
            mr_node = UsdShade.Shader.Define(stage, f"{mat_path}/MetallicRoughnessTexture")
            mr_node.CreateIdAttr("UsdUVTexture")
            mr_node.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                mr_path.replace("\\", "/")
            )
            mr_node.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
            mr_node.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")
            mr_node.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
                reader_shader.ConnectableAPI(), "result",
            )
            # glTF packs: G = roughness, B = metallic
            mr_node.CreateOutput("g", Sdf.ValueTypeNames.Float)
            mr_node.CreateOutput("b", Sdf.ValueTypeNames.Float)
            pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).ConnectToSource(
                mr_node.ConnectableAPI(), "g",
            )
            pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).ConnectToSource(
                mr_node.ConnectableAPI(), "b",
            )
        else:
            # Fallback scalar values when no MR texture
            pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.7)
            pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

        # --- normal map texture ---
        normal_path = textures.get("normal")
        if normal_path and os.path.exists(normal_path):
            n_node = UsdShade.Shader.Define(stage, f"{mat_path}/NormalTexture")
            n_node.CreateIdAttr("UsdUVTexture")
            n_node.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
                normal_path.replace("\\", "/")
            )
            n_node.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
            n_node.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")
            n_node.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
                reader_shader.ConnectableAPI(), "result",
            )
            # Signed normal unpacking: scale=2, bias=-1 per channel
            n_node.CreateInput("scale", Sdf.ValueTypeNames.Float4).Set(
                Gf.Vec4f(2.0, 2.0, 2.0, 1.0)
            )
            n_node.CreateInput("bias", Sdf.ValueTypeNames.Float4).Set(
                Gf.Vec4f(-1.0, -1.0, -1.0, 0.0)
            )
            n_node.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
            pbr_shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).ConnectToSource(
                n_node.ConnectableAPI(), "rgb",
            )

        # Bind material to mesh
        UsdShade.MaterialBindingAPI(mesh_prim).Bind(material)
