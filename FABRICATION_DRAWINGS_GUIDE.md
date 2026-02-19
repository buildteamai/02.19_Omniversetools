# Fabrication Drawings System - Complete Guide

## Overview

Your Steel Shapes library now includes a **complete fabrication drawing system** that exports DXF and PDF shop drawings for steel fabricators. The system generates AISC-compliant drawings with dimensions, GD&T callouts, and cut lists.

## Features

✅ **Multi-View Drawings** - Front, side, and detail views
✅ **Dimensioning** - Accurate AISC dimensions with labels
✅ **GD&T Callouts** - Geometric dimensioning and tolerancing
✅ **Cut List / BOM** - Complete bill of materials
✅ **Title Block** - Professional engineering title block
✅ **General Notes** - AISC standard fabrication notes
✅ **DXF Export** - CAD/CAM compatible format
✅ **PDF Export** - Review and approval format

## Quick Start

### Export Drawings for a Beam

1. **Create or Select Beam**:
   - Create a new W-beam with Tools > Steel Shapes > Wide Flange
   - OR select an existing beam and click "Load Selected"

2. **Configure Beam**:
   - Set AISC section (e.g., W8x24)
   - Set length (e.g., 120")
   - Add features (bolt holes, end plates, copes)

3. **Export Drawings**:
   - Click **"Export Fabrication Drawings"** button
   - Configure export settings in dialog
   - Click **"Export"**

4. **Review Output**:
   - DXF files open in AutoCAD, SolidWorks, etc.
   - PDF files open in any PDF viewer
   - Files saved to specified output folder

## Export Dialog Settings

### Output Format

- **DXF**: For fabricators using CAD/CAM systems
- **PDF**: For engineering review and approval
- **Both**: Creates both formats simultaneously

### Title Block Information

| Field | Description | Example |
|-------|-------------|---------|
| Project Name | Project or job name | "Steel Fabrication Project" |
| Engineer | PE license engineer | "John Smith, PE" |
| Drawing Number | Unique drawing identifier | "S-001" |

**Auto-Populated Fields:**
- Drawing Title: Generated from beam designation
- Designer: "BuildTeamAI"
- Date: Current date
- Scale: "1:10" (standard for steel details)
- Revision: "A" (initial)

### Output Folder

- Default: `C:/Programming/buildteamai/output`
- Folder created automatically if it doesn't exist
- Files named: `W8x24_L120.dxf` / `W8x24_L120.pdf`

## Drawing Contents

### Views Generated

**1. Front View** (Beam Profile)
- Shows I-beam cross-section
- Displays:
  - Overall depth
  - Flange width and thickness
  - Web thickness
  - Bolt holes in web (if present)
  - Profile dimensions

**2. Side View** (Beam Length)
- Shows full beam length
- Displays:
  - Overall length
  - Feature locations (copes, end plates)
  - Bolt hole positions
  - Connection details

**3. End Detail View** (Enlarged)
- Enlarged view of beam end
- Shows:
  - End plate details (if present)
  - Bolt hole patterns
  - Cope dimensions (if present)
  - Connection details

### Dimensions Included

**Main Dimensions:**
- Overall length (with feet-inches notation)
- Beam depth (d)
- Flange width (bf)
- Flange thickness (tf)
- Web thickness (tw)

**Feature Dimensions:**
- Bolt hole spacing and edge distances
- End plate thickness and dimensions
- Cope depth and height
- Distance from beam end to features

### GD&T Callouts

**Perpendicularity (⊥):**
- Web to flanges: ±0.010"
- End cuts to beam axis: ±0.030"

**Flatness (⌭):**
- Top flange: ±0.020"
- Bottom flange: ±0.020"

**Datums:**
- Datum A: Flange surface
- Datum B: Beam centerline

### Cut List / Bill of Materials

| Column | Contents |
|--------|----------|
| MRK | Mark number (B1, PL2, H3, etc.) |
| QTY | Quantity |
| DESCRIPTION | Component description |
| MATERIAL | Steel grade (A992, A36) |
| LENGTH | Length in inches (if applicable) |
| WEIGHT | Weight in pounds |

**Items Included:**
1. Main beam member (W8x24 × 10'-0")
2. End plates (if added)
3. Bolt holes (count and size)
4. Any additional components

### General Notes

**Standard Notes (Always Included):**
1. ALL DIMENSIONS IN INCHES UNLESS OTHERWISE NOTED
2. MATERIAL: ASTM A992 STEEL UNLESS OTHERWISE NOTED
3. WELDING: AWS D1.1 STRUCTURAL WELDING CODE
4. BOLT HOLES: STD HOLES UNLESS OTHERWISE NOTED
5. PAINT: ONE COAT SHOP PRIMER AFTER FABRICATION
6. FABRICATOR TO VERIFY ALL DIMENSIONS IN FIELD

**Feature-Specific Notes:**
- BOLT HOLES: STD HOLES PER AISC, DEBURR ALL HOLES
- END PLATE: FILLET WELD ALL AROUND, TYP
- COPE: CUT SQUARE, GRIND SMOOTH

## File Formats

### DXF (Drawing Exchange Format)

**Purpose:** CAD/CAM systems, CNC programming
**Opens In:** AutoCAD, SolidWorks, Inventor, QCAD, etc.
**Layer Structure:**
- BORDER: Drawing border (white, heavy)
- TITLEBLOCK: Title block lines and text
- GEOMETRY: Main beam geometry (white, medium)
- HIDDEN: Hidden lines (gray, dashed)
- CENTER: Centerlines (red, dash-dot)
- DIMENSIONS: Dimension lines and text (cyan)
- TEXT: General text labels (white)
- NOTES: General notes (yellow)
- TABLES: Cut list table (green)

**Uses:**
- Import into fabricator's CAD system
- CNC programming for plasma/laser cutting
- Shop floor reference drawings
- Quality control measurements

### PDF (Portable Document Format)

**Purpose:** Review, approval, archival
**Opens In:** Adobe Reader, web browsers, etc.
**Page Size:** ARCH B (11" × 17")

**Uses:**
- Engineering review and approval
- Email to clients/engineers
- Print for shop floor
- Project archives
- Submittal packages

## Architecture

### Clean Code Organization

```
company/twin/tools/fabrication/
├── drawings/
│   ├── base_drawing.py          # Abstract base class
│   └── wide_flange_drawing.py   # W-beam implementation
├── exporters/
│   ├── dxf_exporter.py          # DXF export (ezdxf)
│   └── pdf_exporter.py          # PDF export (reportlab)
├── templates/
│   └── title_blocks.py          # Title block layouts
└── data/
    └── aisc_standards.py        # AISC detailing standards
```

### Extensibility

**Adding New Shape Types:**
1. Create new drawing class (inherit from `BaseDrawing`)
2. Implement required methods:
   - `generate_views()`
   - `generate_dimensions()`
   - `generate_gdt_callouts()`
   - `generate_cut_list()`
   - `get_main_view_geometry()`
3. Export works automatically with existing DXF/PDF exporters

**Example: Channels (C-shapes)**
```python
class ChannelDrawing(BaseDrawing):
    def generate_views(self):
        # Return front, side, top views
        pass

    def generate_dimensions(self):
        # Return channel-specific dimensions
        pass
    # etc...
```

### Dependencies

**Required Python Libraries:**
- `ezdxf` - DXF file creation
- `reportlab` - PDF generation

**Install with:**
```bash
pip install ezdxf reportlab
```

## Example Workflows

### Example 1: Simple Beam Drawing

**Scenario:** Basic W8x24 × 10' beam, no connections

1. Select W8x24, length 120"
2. Click "Export Fabrication Drawings"
3. Format: PDF
4. Project: "Office Building"
5. Engineer: "Jane Doe, PE"
6. Export

**Output:** PDF with front/side views, basic dimensions, cut list

### Example 2: Beam with Shear Connection

**Scenario:** W10x33 × 16' with web bolt holes

1. Select W10x33, length 192"
2. Add Bolt Holes: Web, End, 4 holes, 3" spacing
3. Click "Export Fabrication Drawings"
4. Format: Both (DXF + PDF)
5. Drawing Number: "S-002"
6. Export

**Output:**
- DXF: For fabricator CNC programming
- PDF: For engineer approval
- Both show bolt hole locations and dimensions

### Example 3: End Plate Connection

**Scenario:** W12x40 × 20' with welded end plate

1. Select W12x40, length 240"
2. Add End Plate: Start, 0.75" thick
3. Add Bolt Holes: Top Flange (for end plate bolts)
4. Click "Export Fabrication Drawings"
5. Format: Both
6. Project: "Industrial Facility"
7. Export

**Output:**
- Detailed end plate dimensions
- Weld symbols noted
- Cut list includes plate weight
- End detail view shows plate attachment

### Example 4: Beam Framing Connection

**Scenario:** W8x24 coped for girder connection

1. Select W8x24, length 120"
2. Add Cope: Start, Top, 2" deep × 1.5" high
3. Add Bolt Holes: Web, Start, 3 holes
4. Export drawings
5. Format: DXF for fabricator

**Output:**
- Cope dimensions clearly marked
- Bolt holes positioned relative to cope
- Side view shows cope profile
- Fabricator can program cope cut

## Troubleshooting

### "ezdxf not installed" Error

**Problem:** DXF export fails
**Solution:** Install library
```bash
pip install ezdxf
```

### "reportlab not installed" Error

**Problem:** PDF export fails
**Solution:** Install library
```bash
pip install reportlab
```

### Drawing Not Showing Features

**Problem:** Features don't appear in drawing
**Solution:**
- Verify features are enabled (checkbox)
- Check feature parameters are valid
- Regenerate beam before exporting

### File Not Found Error

**Problem:** Can't find output directory
**Solution:**
- Check path is valid
- Ensure no typos in folder name
- System creates folder if it doesn't exist

### Dimensions Overlapping

**Problem:** Dimension text overlaps geometry
**Solution:**
- This is expected for complex features
- Use DXF and adjust in CAD software
- Or simplify feature arrangement

## Best Practices

### For Fabricators

1. **Use DXF Format** - Import into your CAD/CAM system
2. **Verify Dimensions** - Always field-verify before cutting
3. **Check Bolt Patterns** - Confirm hole spacing meets your standards
4. **Review Notes** - Read general notes for material and welding specs

### For Engineers

1. **Use PDF Format** - Easy review and markup
2. **Verify Cut List** - Confirm material grades and quantities
3. **Check GD&T** - Ensure tolerances are appropriate
4. **Stamp & Sign** - Add professional seal before issuing

### For Project Teams

1. **Consistent Numbering** - Use sequential drawing numbers (S-001, S-002, etc.)
2. **Project Names** - Use consistent project naming
3. **Revision Control** - Update revision letter when making changes
4. **Archive Files** - Save both DXF and PDF for records

## Future Enhancements

Coming soon:

- **3D Isometric Views**
- **Weld Symbols** (detailed AWS D1.1 symbols)
- **Bolt Patterns** (AISC standard patterns)
- **Material Callouts** (specific grades and certifications)
- **Connection Capacity Tables**
- **Multi-Sheet Drawings** (for complex assemblies)
- **Automated Detailing** (suggest connections based on loads)

---

**Ready to generate shop drawings? Create a beam and click "Export Fabrication Drawings"!** 📐🔧
