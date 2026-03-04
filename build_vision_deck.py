"""BuildTeamAI Executive Vision Deck - The Physics Engine for the Built World"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

prs = Presentation()
prs.slide_width = Emu(12192000)
prs.slide_height = Emu(6858000)

# Color Palette
BLACK = RGBColor(0x0D, 0x0D, 0x0D)
DARK_BG = RGBColor(0x12, 0x12, 0x14)
CARD_BG = RGBColor(0x1A, 0x1A, 0x1E)
NVIDIA_GREEN = RGBColor(0x76, 0xB9, 0x00)
ACCENT_CYAN = RGBColor(0x00, 0xD4, 0xAA)
ACCENT_BLUE = RGBColor(0x00, 0x96, 0xD6)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xCC, 0xCC, 0xCC)
MID_GRAY = RGBColor(0x88, 0x88, 0x88)
DIM_GRAY = RGBColor(0x55, 0x55, 0x55)
ORANGE_ACCENT = RGBColor(0xFF, 0x8C, 0x00)
RED_ACCENT = RGBColor(0xE8, 0x3E, 0x3E)
PURPLE_ACCENT = RGBColor(0xBB, 0x66, 0xFF)

SLIDE_W = 12192000
SLIDE_H = 6858000


def add_bg(slide, color=DARK_BG):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.line.fill.background()
    return bg


def add_text(slide, left, top, width, height, text, font_size=18,
             color=WHITE, bold=False, alignment=PP_ALIGN.LEFT,
             font_name="Segoe UI"):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = alignment
    return txBox


def add_multiline(slide, left, top, width, height, lines, font_size=16,
                  default_color=LIGHT_GRAY, font_name="Segoe UI"):
    """lines = list of (text,) or (text, color) or (text, color, bold)"""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(lines):
        if isinstance(item, str):
            txt, clr, b = item, default_color, False
        elif len(item) == 2:
            txt, clr = item
            b = False
        else:
            txt, clr, b = item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = txt
        p.font.size = Pt(font_size)
        p.font.color.rgb = clr
        p.font.bold = b
        p.font.name = font_name
        p.space_after = Pt(int(font_size * 0.35))
    return txBox


def add_accent_line(slide, left, top, width, color=NVIDIA_GREEN, height=Emu(36000)):
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    line.fill.solid()
    line.fill.fore_color.rgb = color
    line.line.fill.background()
    return line


def add_card(slide, left, top, width, height, color=CARD_BG):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = color
    card.line.fill.background()
    return card


# ===================================================================
# SLIDE 1 - TITLE
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, BLACK)
add_accent_line(slide, 0, 0, SLIDE_W, NVIDIA_GREEN, Emu(54000))

add_text(slide, Emu(914400), Emu(1371600), Emu(10363200), Emu(800000),
         "BuildTeamAI", font_size=52, color=WHITE, bold=True,
         font_name="Segoe UI Light")

add_text(slide, Emu(914400), Emu(2286000), Emu(10363200), Emu(600000),
         "The Physics Engine for the Built World", font_size=32,
         color=NVIDIA_GREEN, font_name="Segoe UI")

add_accent_line(slide, Emu(914400), Emu(3100000), Emu(2000000), NVIDIA_GREEN, Emu(36000))

add_multiline(slide, Emu(914400), Emu(3400000), Emu(9000000), Emu(1200000), [
    ("A proprietary mathematical system that derives geometry", LIGHT_GRAY),
    ("from first-principles physics and engineering law.", LIGHT_GRAY),
    ("", LIGHT_GRAY),
    ("Not another CAD tool. Not generative AI. Mathematics.", WHITE, True),
], font_size=18)

add_text(slide, Emu(914400), Emu(5943600), Emu(10363200), Emu(400000),
         "Executive Vision  |  March 2026  |  NVIDIA Omniverse Platform",
         font_size=13, color=MID_GRAY)


# ===================================================================
# SLIDE 2 - THE BROKEN PARADIGM
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)

add_text(slide, Emu(914400), Emu(365760), Emu(10363200), Emu(500000),
         "The Broken Paradigm", font_size=36, color=WHITE, bold=True)
add_accent_line(slide, Emu(914400), Emu(850000), Emu(1500000), RED_ACCENT)

add_text(slide, Emu(914400), Emu(1100000), Emu(10363200), Emu(500000),
         "Engineering design has not fundamentally changed in 40 years.",
         font_size=20, color=LIGHT_GRAY)

cols = [
    ("Traditional CAD",
     "Engineers manually author geometry\npoint by point, surface by surface.\n\nThe knowledge lives in the\nengineer\u2019s head. The file is\njust a recording.",
     RED_ACCENT),
    ("Generative AI",
     "Promising demonstrations.\nUnreliable execution.\n\nNo traceability. No engineering\nvalidity. A guess that looks\nplausible but cannot be verified.",
     ORANGE_ACCENT),
    ("BIM / Data Models",
     "Labels on geometry, not\nunderstanding of geometry.\n\nA wall is a \u2018wall\u2019 because\nsomeone tagged it, not because\nthe math says so.",
     ORANGE_ACCENT),
]

card_w = Emu(3200000)
card_h = Emu(3400000)
gap = Emu(350000)
start_x = Emu(914400)

for i, (title, body, accent) in enumerate(cols):
    x = start_x + i * (card_w + gap)
    y = Emu(1700000)
    add_card(slide, x, y, card_w, card_h)
    add_accent_line(slide, x + Emu(180000), y + Emu(120000), Emu(600000), accent, Emu(30000))
    add_text(slide, x + Emu(180000), y + Emu(220000), card_w - Emu(360000), Emu(400000),
             title, font_size=20, color=WHITE, bold=True)
    add_text(slide, x + Emu(180000), y + Emu(700000), card_w - Emu(360000), Emu(2500000),
             body, font_size=15, color=LIGHT_GRAY)

add_text(slide, Emu(914400), Emu(5500000), Emu(10363200), Emu(800000),
         "The common failure: geometry is the INPUT.\nWe believe geometry should be the OUTPUT.",
         font_size=20, color=WHITE, bold=True)


# ===================================================================
# SLIDE 3 - THE PARADIGM SHIFT
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)

add_text(slide, Emu(914400), Emu(365760), Emu(10363200), Emu(500000),
         "The Paradigm Shift", font_size=36, color=WHITE, bold=True)
add_accent_line(slide, Emu(914400), Emu(850000), Emu(1500000), NVIDIA_GREEN)

add_text(slide, Emu(914400), Emu(1200000), Emu(10363200), Emu(500000),
         "Physics  +  Engineering Law  +  Constraints", font_size=28,
         color=NVIDIA_GREEN, bold=True, alignment=PP_ALIGN.CENTER)

add_text(slide, Emu(914400), Emu(1700000), Emu(10363200), Emu(500000),
         "= Geometry", font_size=36, color=WHITE, bold=True,
         alignment=PP_ALIGN.CENTER)

add_accent_line(slide, Emu(3500000), Emu(2300000), Emu(5000000), NVIDIA_GREEN, Emu(24000))

add_multiline(slide, Emu(914400), Emu(2600000), Emu(10363200), Emu(3500000), [
    ("A fan\u2019s scroll housing is not drawn. It is the solution to the", LIGHT_GRAY),
    ("fluid continuity equation: A(\u03b8) = A_outlet \u00d7 (\u03b8 / 2\u03c0)", WHITE, True),
    ("", LIGHT_GRAY),
    ("A beam\u2019s cross-section is not modeled. It is selected by solving", LIGHT_GRAY),
    ("the moment of inertia equation against the load path.", WHITE, True),
    ("", LIGHT_GRAY),
    ("A building\u2019s HVAC layout is not arranged. It is derived from the", LIGHT_GRAY),
    ("thermal load distribution and pressure drop network.", WHITE, True),
    ("", LIGHT_GRAY),
    ("Every dimension has a provenance. Every shape has a reason.", NVIDIA_GREEN, True),
], font_size=18)


# ===================================================================
# SLIDE 4 - THE MATHEMATICAL FRAMEWORK
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)

add_text(slide, Emu(914400), Emu(365760), Emu(10363200), Emu(500000),
         "The Mathematical Framework", font_size=36, color=WHITE, bold=True)
add_accent_line(slide, Emu(914400), Emu(850000), Emu(1500000), ACCENT_CYAN)

layers = [
    ("TOPOLOGY", "Graph Theory",
     "What exists and how it connects.\nComponents, machines, systems, buildings\nas nodes and typed edges in a directed graph.",
     ACCENT_CYAN),
    ("GOVERNING EQUATIONS", "Calculus & Physics",
     "The laws that determine shape and size.\nFluid dynamics, structural mechanics,\nthermodynamics \u2014 encoded as solvers.",
     NVIDIA_GREEN),
    ("CONSTRAINT SYSTEMS", "Algebraic Geometry",
     "The rules that make a configuration valid.\nSolving simultaneous equations guarantees\nphysically correct assemblies.",
     ACCENT_BLUE),
    ("TRANSFORMATION GROUPS", "Group Theory",
     "Symmetries that generate variants.\nUp-blast, down-blast, horizontal \u2014\nsame math, different boundary conditions.",
     ORANGE_ACCENT),
]

for i, (label, math_field, desc, accent) in enumerate(layers):
    y = Emu(1200000 + i * 1300000)
    add_accent_line(slide, Emu(914400), y, Emu(54000), accent, Emu(900000))
    add_text(slide, Emu(1100000), y, Emu(3000000), Emu(350000),
             label, font_size=14, color=accent, bold=True)
    add_text(slide, Emu(1100000), y + Emu(300000), Emu(3000000), Emu(350000),
             math_field, font_size=22, color=WHITE, bold=True)
    add_text(slide, Emu(5200000), y, Emu(6000000), Emu(900000),
             desc, font_size=15, color=LIGHT_GRAY)


# ===================================================================
# SLIDE 5 - ONE SYSTEM, EVERY SCALE
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)

add_text(slide, Emu(914400), Emu(365760), Emu(10363200), Emu(500000),
         "One System, Every Scale", font_size=36, color=WHITE, bold=True)
add_accent_line(slide, Emu(914400), Emu(850000), Emu(1500000), NVIDIA_GREEN)

add_text(slide, Emu(914400), Emu(1100000), Emu(10363200), Emu(500000),
         "The same mathematical structures apply from a bolt to a city.",
         font_size=18, color=LIGHT_GRAY)

scales = [
    ("COMPONENT", "Bolt, blade, bearing,\nflange", "Stress equations\nMaterial properties", ACCENT_CYAN),
    ("MACHINE", "Fan, pump, conveyor,\nrobot", "Performance curves\nFluid / mechanical law", NVIDIA_GREEN),
    ("CELL", "Paint booth, weld station,\nassembly line", "Process flow\nEnvironmental control", ACCENT_BLUE),
    ("BUILDING", "Factory, warehouse,\ndata center", "Structural load paths\nUtility networks", ORANGE_ACCENT),
    ("SITE / CITY", "Campus, district,\ninfrastructure", "Logistics\nTerrain, zoning", PURPLE_ACCENT),
]

col_w = Emu(1900000)
col_gap = Emu(200000)
start_x = Emu(914400)

for i, (label, examples, physics, accent) in enumerate(scales):
    x = start_x + i * (col_w + col_gap)
    y = Emu(1700000)
    add_accent_line(slide, x, y, col_w, accent, Emu(48000))
    add_card(slide, x, y + Emu(48000), col_w, Emu(3600000))
    add_text(slide, x + Emu(120000), y + Emu(200000), col_w - Emu(240000), Emu(350000),
             label, font_size=14, color=accent, bold=True)
    add_text(slide, x + Emu(120000), y + Emu(600000), col_w - Emu(240000), Emu(1200000),
             examples, font_size=13, color=WHITE)
    add_accent_line(slide, x + Emu(120000), y + Emu(1900000), Emu(800000), DIM_GRAY, Emu(12000))
    add_text(slide, x + Emu(120000), y + Emu(2100000), col_w - Emu(240000), Emu(1400000),
             physics, font_size=13, color=MID_GRAY)

add_text(slide, Emu(914400), Emu(5700000), Emu(10363200), Emu(600000),
         "Each level inherits boundary conditions from above. Constraints cascade downward.\nFunction determines form at every scale.",
         font_size=16, color=LIGHT_GRAY)


# ===================================================================
# SLIDE 6 - VARIANTS FROM MATHEMATICS
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)

add_text(slide, Emu(914400), Emu(365760), Emu(10363200), Emu(500000),
         "Variants From Mathematics, Not Templates", font_size=36,
         color=WHITE, bold=True)
add_accent_line(slide, Emu(914400), Emu(850000), Emu(1500000), NVIDIA_GREEN)

add_text(slide, Emu(914400), Emu(1100000), Emu(10363200), Emu(500000),
         "One centrifugal fan. Infinite configurations. Zero templates.",
         font_size=20, color=LIGHT_GRAY)

# Left - the invariant
add_card(slide, Emu(914400), Emu(1800000), Emu(4800000), Emu(4200000))
add_text(slide, Emu(1100000), Emu(1900000), Emu(4400000), Emu(350000),
         "THE INVARIANT", font_size=14, color=NVIDIA_GREEN, bold=True)
add_multiline(slide, Emu(1100000), Emu(2300000), Emu(4400000), Emu(3500000), [
    ("Topology: wheel + shaft + housing + motor", WHITE, True),
    ("", LIGHT_GRAY),
    ("Performance: 10,000 CFM @ 2\" SP", LIGHT_GRAY),
    ("Continuity: A(\u03b8) = A_out \u00d7 \u03b8/2\u03c0", LIGHT_GRAY),
    ("Euler: \u0394P = \u03c1 U\u2082 C\u03b82 \u2212 \u03c1 U\u2081 C\u03b81", LIGHT_GRAY),
    ("Similarity: Q \u221d N D\u00b3", LIGHT_GRAY),
    ("", LIGHT_GRAY),
    ("The physics does not change.", WHITE, True),
    ("The equations do not change.", WHITE, True),
    ("The topology does not change.", WHITE, True),
], font_size=15)

# Right - the variants
add_card(slide, Emu(6000000), Emu(1800000), Emu(5200000), Emu(4200000))
add_text(slide, Emu(6200000), Emu(1900000), Emu(4800000), Emu(350000),
         "THE VARIANTS (boundary conditions)", font_size=14, color=ACCENT_CYAN, bold=True)

variants = [
    ("Up-blast", "Rotate discharge +Y, gravity opposed\nAdd drain, curb cap, weather hood"),
    ("Down-blast", "Rotate discharge -Y, gravity assisted\nAdd inlet hood, condensation mgmt"),
    ("Horizontal", "Discharge along +X\nStandard base, side access"),
    ("Belt drive L", "Motor offset +Z from wheel axis\nBelt guard on +Z face"),
    ("Belt drive R", "Mirror motor across symmetry plane\nBelt guard follows"),
]

for i, (vname, vdesc) in enumerate(variants):
    y = Emu(2350000 + i * 680000)
    add_text(slide, Emu(6200000), y, Emu(1600000), Emu(400000),
             vname, font_size=14, color=ACCENT_CYAN, bold=True)
    add_text(slide, Emu(7800000), y, Emu(3200000), Emu(600000),
             vdesc, font_size=12, color=LIGHT_GRAY)


# ===================================================================
# SLIDE 7 - WHY NVIDIA OMNIVERSE
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)

add_text(slide, Emu(914400), Emu(365760), Emu(10363200), Emu(500000),
         "Why NVIDIA Omniverse", font_size=36, color=WHITE, bold=True)
add_accent_line(slide, Emu(914400), Emu(850000), Emu(1500000), NVIDIA_GREEN)

add_text(slide, Emu(914400), Emu(1100000), Emu(10363200), Emu(500000),
         "This system needs a platform built for physics. Omniverse is that platform.",
         font_size=20, color=LIGHT_GRAY)

reasons = [
    ("USD as Universal Scene Description",
     "Our mathematical objects serialize natively to USD prims with full metadata.\nEvery parameter, equation reference, and constraint stored as scene data.\nThe geometry carries its own engineering DNA.",
     NVIDIA_GREEN),
    ("GPU-Accelerated Physics",
     "Real-time constraint solving and physics simulation on NVIDIA hardware.\nChange a CFM requirement \u2014 watch the entire facility re-derive in real time.\nPhysX and Warp for structural, thermal, and fluid validation.",
     ACCENT_CYAN),
    ("Collaborative Digital Twin",
     "Multiple engineers, same live scene, same mathematical truth.\nStructural changes propagate to MEP. MEP propagates to architectural.\nOne model. One source of truth. Physically consistent by construction.",
     ACCENT_BLUE),
    ("Ecosystem and Scale",
     "Connectors to every major tool in AEC and manufacturing.\nNucleus for enterprise deployment. Cloud for global collaboration.\nThe platform scales from a single machine to a facility to a city.",
     ORANGE_ACCENT),
]

for i, (title, desc, accent) in enumerate(reasons):
    y = Emu(1700000 + i * 1150000)
    add_accent_line(slide, Emu(914400), y, Emu(54000), accent, Emu(850000))
    add_text(slide, Emu(1200000), y, Emu(4000000), Emu(400000),
             title, font_size=18, color=WHITE, bold=True)
    add_text(slide, Emu(1200000), y + Emu(350000), Emu(10000000), Emu(700000),
             desc, font_size=14, color=LIGHT_GRAY)


# ===================================================================
# SLIDE 8 - THE MOAT
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, BLACK)

add_text(slide, Emu(914400), Emu(365760), Emu(10363200), Emu(500000),
         "The Moat", font_size=36, color=WHITE, bold=True)
add_accent_line(slide, Emu(914400), Emu(850000), Emu(1500000), NVIDIA_GREEN)

add_text(slide, Emu(914400), Emu(1200000), Emu(10363200), Emu(600000),
         "Proprietary mathematical formalism is not something you clone from GitHub.",
         font_size=22, color=WHITE, bold=True)

moat_items = [
    ("Encoded Engineering Knowledge",
     "Decades of engineering correlations, performance curves, and physical laws\ntranslated into a computable mathematical system. Domain expertise\nrendered as software \u2014 it cannot be replicated without the same depth."),
    ("Correct by Construction",
     "Every output is traceable to physics. No black boxes. No hallucinations.\nWhen a customer asks 'why is this 24 inches?' the system answers with\nthe equation, the inputs, and the engineering standard that governs it."),
    ("Compounding Returns",
     "Each new equipment class increases the value of every other class.\nA fan connects to ductwork connects to structure connects to building.\nThe network effect is mathematical."),
    ("Verification is Built In",
     "Competitors can generate geometry. Only this system can prove it is correct.\nEvery dimension has provenance. Every assembly satisfies its constraints.\nThis is auditable engineering, not artistic approximation."),
]

for i, (title, desc) in enumerate(moat_items):
    y = Emu(2000000 + i * 1100000)
    add_text(slide, Emu(914400), y, Emu(500000), Emu(400000),
             "0{}".format(i + 1), font_size=28, color=NVIDIA_GREEN, bold=True,
             font_name="Segoe UI Light")
    add_text(slide, Emu(1500000), y, Emu(9500000), Emu(350000),
             title, font_size=18, color=WHITE, bold=True)
    add_text(slide, Emu(1500000), y + Emu(350000), Emu(9500000), Emu(700000),
             desc, font_size=13, color=LIGHT_GRAY)


# ===================================================================
# SLIDE 9 - CROSSING THE MOAT
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)

add_text(slide, Emu(914400), Emu(365760), Emu(10363200), Emu(500000),
         "Crossing the Moat", font_size=36, color=WHITE, bold=True)
add_accent_line(slide, Emu(914400), Emu(850000), Emu(1500000), NVIDIA_GREEN)

add_text(slide, Emu(914400), Emu(1100000), Emu(10363200), Emu(500000),
         "A phased approach grounded in engineering reality, not hype.",
         font_size=20, color=LIGHT_GRAY)

phases = [
    ("NOW", "Foundation",
     "Structural steel + MEP primitives\nConstraint validation framework\nAnchor-based assembly system\nProven on NVIDIA Omniverse / USD",
     NVIDIA_GREEN, "PROVEN"),
    ("NEXT", "Industrial Equipment",
     "Fans, pumps, conveyors, vessels\nPhysics-derived geometry engine\nVariant generation from\nboundary conditions",
     ACCENT_CYAN, "BUILDING"),
    ("THEN", "Facility Scale",
     "Process flow to spatial layout\nUtility network auto-routing\nStructural system generation\nFull facility from functional spec",
     ACCENT_BLUE, "ROADMAP"),
    ("FUTURE", "Urban and Beyond",
     "Building to site to district\nInfrastructure networks\nTerrain-aware placement\nCity-scale digital twin",
     PURPLE_ACCENT, "VISION"),
]

card_w = Emu(2500000)
card_h = Emu(3800000)
gap = Emu(200000)
start_x = Emu(640000)

for i, (when, title, desc, accent, status) in enumerate(phases):
    x = start_x + i * (card_w + gap)
    y = Emu(1700000)
    add_card(slide, x, y, card_w, card_h)
    add_accent_line(slide, x, y, card_w, accent, Emu(48000))
    add_text(slide, x + Emu(150000), y + Emu(150000), Emu(1000000), Emu(300000),
             when, font_size=13, color=accent, bold=True)
    add_text(slide, x + Emu(150000), y + Emu(500000), card_w - Emu(300000), Emu(400000),
             title, font_size=20, color=WHITE, bold=True)
    add_text(slide, x + Emu(150000), y + Emu(1000000), card_w - Emu(300000), Emu(2200000),
             desc, font_size=13, color=LIGHT_GRAY)
    add_text(slide, x + Emu(150000), y + Emu(3400000), card_w - Emu(300000), Emu(300000),
             status, font_size=11, color=accent, bold=True)

add_text(slide, Emu(914400), Emu(5800000), Emu(10363200), Emu(400000),
         "Each phase builds the equation library. Each equation compounds the value of the system.",
         font_size=16, color=WHITE, bold=True)


# ===================================================================
# SLIDE 10 - COMPETITIVE LANDSCAPE
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide)

add_text(slide, Emu(914400), Emu(365760), Emu(10363200), Emu(500000),
         "Competitive Landscape", font_size=36, color=WHITE, bold=True)
add_accent_line(slide, Emu(914400), Emu(850000), Emu(1500000), NVIDIA_GREEN)

headers = ["", "Traditional\nCAD", "Generative\nAI", "BIM\nPlatforms", "BuildTeamAI"]
header_colors = [DIM_GRAY, MID_GRAY, MID_GRAY, MID_GRAY, NVIDIA_GREEN]
col_positions = [Emu(914400), Emu(3200000), Emu(4900000), Emu(6600000), Emu(8300000)]
col_w_tbl = Emu(1500000)

for i in range(1, len(headers)):
    add_text(slide, col_positions[i], Emu(1200000), col_w_tbl, Emu(600000),
             headers[i], font_size=13, color=header_colors[i], bold=True,
             alignment=PP_ALIGN.CENTER)

rows = [
    ("Physics-derived geometry", "X", "X", "X", "Y"),
    ("Every dimension traceable", "X", "X", "X", "Y"),
    ("Infinite variants from math", "X", "X", "X", "Y"),
    ("Engineering verification built-in", "O", "X", "O", "Y"),
    ("Real-time parametric updates", "O", "X", "O", "Y"),
    ("No per-seat CAD license", "X", "Y", "X", "Y"),
    ("Scale: component to city", "X", "O", "O", "Y"),
    ("Collaborative (multi-user)", "O", "X", "O", "Y"),
]

CHECK = "\u2713"
CROSS = "\u2717"
PARTIAL = "\u25CB"

for j, (label, *values) in enumerate(rows):
    y = Emu(1900000 + j * 450000)
    if j % 2 == 0:
        row_bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Emu(914400), y - Emu(50000),
            Emu(9500000), Emu(400000))
        row_bg.fill.solid()
        row_bg.fill.fore_color.rgb = RGBColor(0x18, 0x18, 0x1C)
        row_bg.line.fill.background()

    add_text(slide, Emu(914400), y, Emu(2200000), Emu(350000),
             label, font_size=13, color=LIGHT_GRAY)

    for k, val in enumerate(values):
        if val == "Y":
            symbol, clr = CHECK, NVIDIA_GREEN
        elif val == "X":
            symbol, clr = CROSS, RGBColor(0x66, 0x33, 0x33)
        else:
            symbol, clr = PARTIAL, MID_GRAY
        add_text(slide, col_positions[k + 1], y, col_w_tbl, Emu(350000),
                 symbol, font_size=18, color=clr, alignment=PP_ALIGN.CENTER)


# ===================================================================
# SLIDE 11 - THE VISION
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, BLACK)

add_text(slide, Emu(914400), Emu(365760), Emu(10363200), Emu(500000),
         "The Vision", font_size=36, color=WHITE, bold=True)
add_accent_line(slide, Emu(914400), Emu(850000), Emu(1500000), NVIDIA_GREEN)

add_multiline(slide, Emu(914400), Emu(1400000), Emu(10363200), Emu(4000000), [
    ("An engineer describes a function.", WHITE, True),
    ("", WHITE),
    ("The system solves for the geometry.", NVIDIA_GREEN, True),
    ("", WHITE),
    ("Every surface is a solution to an equation.", LIGHT_GRAY),
    ("Every assembly satisfies its constraints.", LIGHT_GRAY),
    ("Every building is physically consistent.", LIGHT_GRAY),
    ("Every city is a network of solved systems.", LIGHT_GRAY),
    ("", LIGHT_GRAY),
    ("This is not incremental improvement.", WHITE),
    ("This is a new foundation for engineering design.", WHITE, True),
], font_size=22)

add_text(slide, Emu(914400), Emu(5200000), Emu(10363200), Emu(600000),
         "Built on NVIDIA Omniverse. Powered by mathematics.\nReady for the industries that build the world.",
         font_size=18, color=MID_GRAY)


# ===================================================================
# SLIDE 12 - CLOSING / CALL TO ACTION
# ===================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, BLACK)
add_accent_line(slide, 0, 0, SLIDE_W, NVIDIA_GREEN, Emu(54000))

add_text(slide, Emu(914400), Emu(1500000), Emu(10363200), Emu(800000),
         "BuildTeamAI", font_size=48, color=WHITE, bold=True,
         font_name="Segoe UI Light")

add_text(slide, Emu(914400), Emu(2400000), Emu(10363200), Emu(600000),
         "The Physics Engine for the Built World", font_size=28,
         color=NVIDIA_GREEN, font_name="Segoe UI")

add_accent_line(slide, Emu(914400), Emu(3200000), Emu(2000000), NVIDIA_GREEN, Emu(30000))

add_multiline(slide, Emu(914400), Emu(3600000), Emu(10363200), Emu(2000000), [
    ("We are not building another CAD tool.", LIGHT_GRAY),
    ("We are not chasing generative AI hype.", LIGHT_GRAY),
    ("We are building the mathematical engine that makes", WHITE),
    ("geometry a consequence of physics.", NVIDIA_GREEN, True),
    ("", WHITE),
    ("Let\u2019s build this together.", WHITE, True),
], font_size=20)

add_text(slide, Emu(914400), Emu(5943600), Emu(10363200), Emu(400000),
         "BuildTeamAI  |  NVIDIA Omniverse Partner  |  March 2026",
         font_size=13, color=MID_GRAY)


# === SAVE ===
output_path = os.path.join("C:/programming/buildteamai", "BuildTeamAI_Physics_Engine_Vision.pptx")
prs.save(output_path)
print("Saved: {}".format(output_path))
print("Slides: {}".format(len(prs.slides)))
