"""Generate BuildTeamAI Technical Architecture slide deck."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ── Colours ──────────────────────────────────────────────────
BG_DARK   = RGBColor(0x1A, 0x1A, 0x2E)
BG_MID    = RGBColor(0x22, 0x22, 0x3A)
ACCENT    = RGBColor(0x76, 0xB9, 0x00)  # NVIDIA green
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT     = RGBColor(0xCC, 0xCC, 0xCC)
CODE_BG   = RGBColor(0x16, 0x16, 0x28)
ORANGE    = RGBColor(0xFF, 0x99, 0x00)
CYAN      = RGBColor(0x00, 0xBC, 0xD4)

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)

W = prs.slide_width
H = prs.slide_height

# ── Helpers ──────────────────────────────────────────────────

def _set_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_textbox(slide, left, top, width, height, text, *,
                 font_size=18, bold=False, color=WHITE, align=PP_ALIGN.LEFT,
                 font_name="Consolas"):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = font_name
    p.alignment = align
    return txBox


def _add_title(slide, text, subtitle=None):
    _add_textbox(slide, Inches(0.8), Inches(0.4), Inches(11.5), Inches(0.8),
                 text, font_size=36, bold=True, color=ACCENT, font_name="Segoe UI")
    if subtitle:
        _add_textbox(slide, Inches(0.8), Inches(1.15), Inches(11.5), Inches(0.5),
                     subtitle, font_size=18, color=LIGHT, font_name="Segoe UI")


def _add_code_block(slide, left, top, width, height, text, font_size=11):
    # background rect
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = CODE_BG
    shape.line.fill.background()
    shape.shadow.inherit = False
    # text
    txBox = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.15),
                                     width - Inches(0.4), height - Inches(0.3))
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(font_size)
        p.font.name = "Consolas"
        p.font.color.rgb = LIGHT
        p.space_after = Pt(1)
        p.space_before = Pt(1)


def _add_bullet_list(slide, left, top, width, height, items, font_size=16,
                     color=WHITE, font_name="Segoe UI"):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = item
        p.font.size = Pt(font_size)
        p.font.name = font_name
        p.font.color.rgb = color
        p.space_after = Pt(6)
        p.level = 0


def _add_accent_bar(slide):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                   Inches(0.8), Inches(1.45), Inches(2), Inches(0.04))
    shape.fill.solid()
    shape.fill.fore_color.rgb = ACCENT
    shape.line.fill.background()


def new_slide():
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    _set_bg(slide, BG_DARK)
    return slide


# ══════════════════════════════════════════════════════════════
# SLIDE 1 — Title
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_textbox(s, Inches(0.8), Inches(2.0), Inches(11.5), Inches(1.2),
             "BuildTeamAI", font_size=54, bold=True, color=ACCENT, font_name="Segoe UI")
_add_textbox(s, Inches(0.8), Inches(3.2), Inches(11.5), Inches(0.7),
             "Parametric Industrial Geometry on NVIDIA Omniverse",
             font_size=28, color=WHITE, font_name="Segoe UI")
_add_textbox(s, Inches(0.8), Inches(4.1), Inches(11.5), Inches(0.5),
             "Kit Extension  |  build123d B-Rep Kernel  |  USD Pipeline",
             font_size=18, color=LIGHT, font_name="Segoe UI")
_add_textbox(s, Inches(0.8), Inches(5.5), Inches(11.5), Inches(0.5),
             "Technical Architecture & Implementation",
             font_size=20, color=ORANGE, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════
# SLIDE 2 — System Architecture
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "System Architecture")
_add_accent_bar(s)

arch_text = """\
┌─────────────────────────────────────────────────────┐
│              Omniverse Kit Runtime                   │
│  ┌───────────────────────────────────────────────┐   │
│  │        company.twin.tools Extension           │   │
│  │  ┌──────────┐  ┌───────────┐  ┌───────────┐  │   │
│  │  │    UI    │  │   Core    │  │   Utils   │  │   │
│  │  │ Windows  │  │ Registry  │  │  Mating   │  │   │
│  │  └────┬─────┘  │ Assembly  │  │  Measure  │  │   │
│  │       │        └─────┬─────┘  └───────────┘  │   │
│  │       │              │                        │   │
│  │  ┌────▼──────────────▼────────────────────┐   │   │
│  │  │        Object Generators               │   │   │
│  │  │   structural/  mep/  components/       │   │   │
│  │  └──────────────────┬─────────────────────┘   │   │
│  └─────────────────────│─────────────────────────┘   │
│                   ┌────▼─────┐                       │
│                   │ build123d│  B-Rep Solid Modeling  │
│                   └────┬─────┘                       │
│              ┌─────────▼──────────┐                  │
│              │   usd_utils        │                  │
│              │   create_mesh_     │                  │
│              │   from_shape()     │                  │
│              └─────────┬──────────┘                  │
│                   ┌────▼─────┐                       │
│                   │USD Stage │  Meshes + Materials    │
│                   └──────────┘  + Metadata           │
└─────────────────────────────────────────────────────┘"""

_add_code_block(s, Inches(0.8), Inches(1.8), Inches(11.5), Inches(5.2),
                arch_text, font_size=11)

# ══════════════════════════════════════════════════════════════
# SLIDE 3 — Geometry Pipeline
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "Geometry Pipeline — Core Data Flow")
_add_accent_bar(s)

pipeline = """\
Manufacturer Spec (JSON / AISC DB)
        │
        ▼
  Generator.create(**params)
        │  build123d operations:
        │    Box, Cylinder, extrude, fillet,
        │    boolean union / subtract / intersect
        ▼
  build123d Solid (B-Rep TopoDS_Shape)
        │
        ▼
  usd_utils.create_mesh_from_shape(stage, path, shape)
        │  tessellate → vertices + face indices
        │  create UsdGeom.Mesh prim
        │  apply UsdShade.Material
        │  write metadata via SetCustomDataByKey()
        ▼
  USD Prim on Stage
    ├─ Mesh geometry
    ├─ UsdPreviewSurface material
    ├─ Custom metadata (params for regeneration)
    └─ Mating ports (twin:is_port)"""

_add_code_block(s, Inches(0.8), Inches(1.8), Inches(11.5), Inches(5.2),
                pipeline, font_size=13)

# ══════════════════════════════════════════════════════════════
# SLIDE 4 — Generator Pattern
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "Object Generator Pattern")
_add_accent_bar(s)

code = """\
class TrapezeMaker:
    @staticmethod
    def create(
        stage: Usd.Stage,
        prim_path: str,
        span: float = 48.0,         # inches
        rod_diameter: float = 0.375,
        duct_diameter: float = 12.0,
        ...
    ) -> Usd.Prim:

        # 1. build123d geometry
        rod = Cylinder(radius=rod_diameter/2, height=rod_length)
        channel = extrude(channel_profile, amount=span)
        solid = union(rod, channel, ...)

        # 2. Tessellate to USD
        prim = usd_utils.create_mesh_from_shape(stage, prim_path, solid)

        # 3. Store params as metadata for regeneration
        prim.SetCustomDataByKey("twin:generator", "trapeze")
        prim.SetCustomDataByKey("twin:param:span", span)
        prim.SetCustomDataByKey("twin:param:rod_diameter", rod_diameter)
        return prim"""

_add_code_block(s, Inches(0.8), Inches(1.8), Inches(11.5), Inches(5.0),
                code, font_size=13)

_add_textbox(s, Inches(0.8), Inches(6.9), Inches(11.5), Inches(0.4),
             "All generators follow this pattern. Static create(), units = inches, Y-Up.",
             font_size=14, color=ORANGE, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════
# SLIDE 5 — Module Organization
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "Module Organization")
_add_accent_bar(s)

tree = """\
exts/company.twin.tools/company/twin/tools/
├── extension.py                 # Kit extension entry point
├── core/
│   ├── equipment_registry.py    # Singleton registry
│   ├── assembly.py              # Multi-component assemblies
│   ├── registry_entries.py      # Generator adapters
│   ├── spec_extractor.py        # Spec sheet parsing
│   └── triposr_client.py       # TripoSR API client
├── objects/
│   ├── structural/              # wide_flange, channel, hss_tube
│   │                            # frame, strongback, steel_connections
│   ├── mep/                     # duct_warp, trapeze
│   └── components/              # sheet_metal, pyramid, screen_guard
│                                # stair, construction_cube
├── ui/                          # omni.ui window classes
│   ├── catalog_window.py        # IEIP unified browser
│   ├── wide_flange_window.py    # ... one window per generator
│   ├── step_import_window.py
│   └── step_export_window.py
├── importers/                   # STEP / mesh import
├── exporters/                   # STEP export
├── solvers/
│   └── frame_solver.py          # Structural frame assembly
└── utils/
    ├── mating.py                # Anchor / port connections
    └── measure_tool.py          # Distance / angle measurement"""

_add_code_block(s, Inches(0.8), Inches(1.8), Inches(11.5), Inches(5.2),
                tree, font_size=12)

# ══════════════════════════════════════════════════════════════
# SLIDE 6 — IEIP Equipment Registry
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "IEIP — Equipment Registry")
_add_accent_bar(s)

reg = """\
┌──────────────────────────────────────────────────────────┐
│            EquipmentRegistry  (Singleton)                │
│                                                          │
│  register(entry_id, RegistryEntry)                       │
│  get(entry_id) → RegistryEntry                           │
│  list_category(cat) → [RegistryEntry, ...]               │
│                                                          │
│  ┌────────────────────────────────────────────────────┐   │
│  │  RegistryEntry                                     │   │
│  │    entry_id:        str                            │   │
│  │    category:        str                            │   │
│  │    generator_type:  A (stage-aware) | B (geom)     │   │
│  │    detail_levels:   [0, 1, 2, 3]                   │   │
│  │    param_schema:    dict                            │   │
│  │    create(stage, path, **kw) → Prim                │   │
│  └────────────────────────────────────────────────────┘   │
│                                                          │
│  GeneratorAdapter wraps existing create() methods        │
│  → zero modification to generators                       │
└──────────────────────────────────────────────────────────┘"""

_add_code_block(s, Inches(0.5), Inches(1.8), Inches(7.5), Inches(5.0),
                reg, font_size=11)

# Detail levels on the right
items = [
    "Detail Level 0 — PLACEHOLDER",
    "    Bounding box only",
    "",
    "Detail Level 1 — SCHEMATIC",
    "    Simplified outline geometry",
    "",
    "Detail Level 2 — PARAMETRIC",
    "    Full geometry, no cosmetic details",
    "",
    "Detail Level 3 — DETAILED",
    "    Fillets, threads, labels, cosmetics",
]
_add_bullet_list(s, Inches(8.3), Inches(2.0), Inches(4.5), Inches(4.5),
                 items, font_size=14, color=LIGHT)

# ══════════════════════════════════════════════════════════════
# SLIDE 7 — Assembly System
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "Assembly System")
_add_accent_bar(s)

asm = """\
JSON Template  (data/assemblies/*.json)
┌──────────────────────────────────────────┐
│ {                                        │
│   "assembly_id": "trapeze_run",          │
│   "components": [                        │
│     {                                    │
│       "entry_id": "trapeze",             │
│       "params": { "span": 48 },          │
│       "transform": [0, 0, 0],            │
│       "ports": ["top_left", "top_right"] │
│     },                                   │
│     {                                    │
│       "entry_id": "wide_flange",         │
│       "params": {                        │
│         "size": "W8x18",                 │
│         "length": 120                    │
│       },                                 │
│       "mate_to": {                       │
│         "component": 0,                  │
│         "port": "top_left"               │
│       }                                  │
│     }                                    │
│   ]                                      │
│ }                                        │
└──────────────────────────────────────────┘"""

_add_code_block(s, Inches(0.5), Inches(1.8), Inches(6.5), Inches(5.2),
                asm, font_size=11)

flow = """\
Assembly.build(stage, template)
        │
        │  1. Instantiate each component
        │     via registry lookup
        │
        │  2. Resolve mate_to references
        │     → align port positions
        │
        │  3. Group under Xform prim
        │
        ▼
  USD Xform
    ├─ child mesh 0  (trapeze)
    ├─ child mesh 1  (wide_flange)
    └─ assembly metadata"""

_add_code_block(s, Inches(7.3), Inches(1.8), Inches(5.5), Inches(5.2),
                flow, font_size=12)

# ══════════════════════════════════════════════════════════════
# SLIDE 8 — Mating System
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "Mating / Connection System")
_add_accent_bar(s)

mate_code = """\
# ── Port Definition (on generator output prim) ──────────────

prim.CreateAttribute("twin:is_port",
    Sdf.ValueTypeNames.Bool).Set(True)

prim.CreateAttribute("twin:port_name",
    Sdf.ValueTypeNames.String).Set("top_left")

prim.CreateAttribute("twin:port_direction",
    Sdf.ValueTypeNames.Float3).Set((0, 1, 0))


# ── Mating Operation  (utils/mating.py) ─────────────────────

def mate(stage, prim_a, port_a_name, prim_b, port_b_name):
    # 1. Find port transforms on both prims
    port_a = find_port(prim_a, port_a_name)
    port_b = find_port(prim_b, port_b_name)

    # 2. Compute alignment transform
    #    (position match + normal alignment)
    xform = compute_mate_transform(port_a, port_b)

    # 3. Apply transform to child prim
    UsdGeom.Xformable(prim_b).ClearXformOpOrder()
    prim_b.AddTranslateOp().Set(xform.translation)
    prim_b.AddRotateXYZOp().Set(xform.rotation)

    # 4. Record connection in metadata
    prim_b.SetCustomDataByKey("twin:mated_to",
        f"{prim_a.GetPath()}:{port_a_name}")"""

_add_code_block(s, Inches(0.8), Inches(1.8), Inches(11.5), Inches(5.2),
                mate_code, font_size=12)

_add_textbox(s, Inches(0.8), Inches(7.05), Inches(11.5), Inches(0.35),
             "Ports survive regeneration — stored as USD attributes, not volatile state.",
             font_size=14, color=ORANGE, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════
# SLIDE 9 — UI Pattern
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "UI Pattern — omni.ui Windows")
_add_accent_bar(s)

ui_code = """\
# ── ComboBox Dropdown (ListItemModel) ────────────────────

class SizeModel(ui.AbstractItemModel):
    def __init__(self, options: list[str]):
        super().__init__()
        self._items = [ListItem(o) for o in options]

    def get_item_children(self, item):
        return self._items if item is None else []


# ── Window Structure ─────────────────────────────────────

class WideFlangeWindow(ui.Window):
    def __init__(self):
        super().__init__("Wide Flange", width=300, height=400)
        self._build_ui()

    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=8):
                ui.Label("Section Size")
                self._size_combo = ui.ComboBox(self._size_model)

                ui.Label("Length (in)")
                self._length = ui.FloatField(default_value=120.0)

                ui.Button("Create", clicked_fn=self._on_create)

    def _on_create(self):
        stage = omni.usd.get_context().get_stage()
        WideFlangeMaker.create(stage, "/World/WF_001",
            size=self._get_selected_size(),
            length=self._length.model.get_value_as_float())"""

_add_code_block(s, Inches(0.8), Inches(1.8), Inches(11.5), Inches(5.2),
                ui_code, font_size=12)

# ══════════════════════════════════════════════════════════════
# SLIDE 10 — Data-Driven Generators
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "Data-Driven Generators — AISC Example")
_add_accent_bar(s)

aisc_json = """\
data/aisc_wide_flanges.json
{
  "W10x22": {
    "d":  10.17,     // depth (inches)
    "bf":  5.75,     // flange width
    "tf":  0.360,    // flange thickness
    "tw":  0.240,    // web thickness
    "weight": 22     // lb/ft
  },
  "W12x26": { ... },
  "W14x30": { ... },
  ...  // full AISC catalog
}"""

_add_code_block(s, Inches(0.5), Inches(1.8), Inches(5.8), Inches(4.5),
                aisc_json, font_size=13)

gen_code = """\
WideFlangeMaker.create():

  spec = load_json(size)  # e.g. "W10x22"

  # build123d: extrude I-profile
  flange_top = Box(
      spec.bf, spec.tf, length)
  web = Box(
      spec.tw, spec.d - 2*spec.tf, length)
  flange_bot = Box(
      spec.bf, spec.tf, length)

  solid = union(
      flange_top, web, flange_bot)

  # → tessellate → USD Mesh"""

_add_code_block(s, Inches(6.7), Inches(1.8), Inches(6.1), Inches(4.5),
                gen_code, font_size=13)

_add_textbox(s, Inches(0.8), Inches(6.5), Inches(11.5), Inches(0.5),
             "Any AISC section generated on demand — no pre-modeled geometry stored.",
             font_size=16, color=ORANGE, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════
# SLIDE 11 — Frame Solver
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "Frame Solver")
_add_accent_bar(s)

frame = """\
solvers/frame_solver.py

Input:
  ┌─────────────────────────────────────────┐
  │  Member definitions:                    │
  │    - start / end points (3D vectors)    │
  │    - section size   (e.g. "W8x18")     │
  │    - member type    (beam/column/brace) │
  └─────────────────────────────────────────┘

Process:
  ┌─────────────────────────────────────────┐
  │  1. Generate each member geometry       │
  │     (via WideFlangeMaker / ChannelMaker)│
  │  2. Orient along start → end vector     │
  │  3. Generate connections at joints      │
  │  4. Group under frame Xform prim        │
  └─────────────────────────────────────────┘

Output:
  ┌─────────────────────────────────────────┐
  │  Complete structural frame as USD       │
  │  hierarchy with per-member metadata     │
  │  and connection details                 │
  └─────────────────────────────────────────┘"""

_add_code_block(s, Inches(0.8), Inches(1.8), Inches(11.5), Inches(5.2),
                frame, font_size=13)

# ══════════════════════════════════════════════════════════════
# SLIDE 12 — TripoSR Integration
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "TripoSR — Image-to-3D Integration")
_add_accent_bar(s)

tripo = """\
┌─────────────┐       HTTP         ┌────────────────────┐
│   Kit UI    │ ◄───────────────► │  FastAPI Server     │
│  triposr_   │   localhost:8000   │  (Python 3.10)     │
│  window.py  │                    │                    │
└──────┬──────┘                    │  TripoSR Model    │
       │                           │  PyTorch + CUDA   │
       │  POST /generate           │  RTX A3000 12GB   │
       │  { image: base64 }        │                    │
       │                           │  Performance:     │
       │  Response:                │  ~10s total       │
       │  { mesh: OBJ data }      │    5.4s model load │
       │                           │    1.7s inference  │
       ▼                           │    2.4s extraction │
  mesh_importer.py                 └────────────────────┘
       │
       ▼
  UsdGeom.Mesh on stage"""

_add_code_block(s, Inches(0.5), Inches(1.8), Inches(8.0), Inches(5.0),
                tripo, font_size=12)

stack_items = [
    "Tech Stack:",
    "",
    "  PyTorch 2.5.1 + cu121",
    "  PyMCubes (no C++ compiler)",
    "  RTX A3000 12GB VRAM",
    "  Python 3.10 embeddable",
    "",
    "  Model weights: ~1.68 GB",
    "  (HuggingFace cache)",
    "",
    "  Input:  any photo/render",
    "  Output: OBJ mesh → USD",
]
_add_bullet_list(s, Inches(8.8), Inches(2.0), Inches(4.0), Inches(4.5),
                 stack_items, font_size=13, color=LIGHT, font_name="Consolas")

# ══════════════════════════════════════════════════════════════
# SLIDE 13 — Import / Export
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "Import / Export Pipelines")
_add_accent_bar(s)

imp_exp = """\
STEP Import:
  .STEP / .STP
       │
       ▼
  OpenCascade (via build123d)
       │
       ▼
  tessellate → UsdGeom.Mesh
  preserve assembly structure as USD hierarchy


STEP Export:
  USD prims with twin:generator metadata
       │
       ▼
  Re-invoke generator with stored params
       │
       ▼
  build123d solid → OCC STEP writer → .STEP file


Mesh Import:
  OBJ / FBX / glTF
       │
       ▼
  mesh_importer.py → vertex/face extraction → UsdGeom.Mesh"""

_add_code_block(s, Inches(0.8), Inches(1.8), Inches(11.5), Inches(5.2),
                imp_exp, font_size=13)

# ══════════════════════════════════════════════════════════════
# SLIDE 14 — Metadata & Regeneration
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "Metadata & Regeneration")
_add_accent_bar(s)

meta = """\
Every generated prim carries:
┌───────────────────────────────────────────┐
│ CustomData (standard metadata):           │
│   twin:generator     = "wide_flange"      │
│   twin:param:size    = "W10x22"           │
│   twin:param:length  = 120.0              │
│                                           │
│ IEIP Namespace (catalog objects):         │
│   ieip:entry_id      = "wide_flange"      │
│   ieip:detail_level  = 2                  │
│   ieip:param:*       = ...                │
└───────────────────────────────────────────┘"""

_add_code_block(s, Inches(0.5), Inches(1.8), Inches(6.0), Inches(4.0),
                meta, font_size=13)

regen = """\
Regeneration Flow:

  1. Read metadata from prim
     └─ twin:generator → "wide_flange"
     └─ twin:param:*   → {size, length}

  2. Look up generator in registry
     └─ EquipmentRegistry.get(entry_id)

  3. Re-invoke create() with stored params
     └─ WideFlangeMaker.create(**params)

  4. Replace mesh data in-place
     └─ Preserve transform
     └─ Preserve mating connections
     └─ Update metadata"""

_add_code_block(s, Inches(6.8), Inches(1.8), Inches(6.0), Inches(4.0),
                regen, font_size=12)

_add_textbox(s, Inches(0.8), Inches(6.2), Inches(11.5), Inches(0.5),
             "Change any parameter → regenerate geometry → connections and position preserved.",
             font_size=16, color=ORANGE, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════
# SLIDE 15 — Tech Stack Summary
# ══════════════════════════════════════════════════════════════
s = new_slide()
_add_title(s, "Tech Stack Summary")
_add_accent_bar(s)

# Table as code block (cleanest in monospace)
table = """\
 Layer              Technology
 ──────────────────────────────────────────────────
 Runtime            NVIDIA Omniverse Kit 106+
 Scene Format       USD (Universal Scene Description)
 CAD Kernel         build123d  (OpenCascade B-Rep)
 GPU Compute        PyTorch 2.5.1 + CUDA 12.1
 AI Mesh Gen        TripoSR  (image → 3D)
 UI Framework       omni.ui
 Language           Python 3.10+
 Data Formats       JSON  (AISC, assemblies, specs)
 Coordinate Sys     Inches, Y-Up
 Import / Export    STEP, OBJ, FBX, glTF
 Version Control    Git
 GPU Hardware       NVIDIA RTX A3000  (12 GB)"""

_add_code_block(s, Inches(1.5), Inches(2.0), Inches(10.0), Inches(4.5),
                table, font_size=16)

_add_textbox(s, Inches(0.8), Inches(6.8), Inches(11.5), Inches(0.4),
             "All units: inches  |  All geometry: B-Rep (not mesh approximation)  |  All output: USD-native",
             font_size=14, color=ACCENT, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════
out_path = r"C:\programming\buildteamai\BuildTeamAI_Technical_Architecture.pptx"
prs.save(out_path)
print(f"Saved: {out_path}")
print(f"Slides: {len(prs.slides)}")
