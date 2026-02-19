# AISC Steel Shapes Library - Quick Start Guide

## Overview

You now have an AISC-compliant steel shapes library integrated into your Omniverse extension! Starting with **Wide Flange (W-shapes)** beams with parametric dimensions and fabrication features.

## Getting Started

### Access the Tool

1. Open your Omniverse application
2. Navigate to: **Tools > Steel Shapes > Wide Flange**
3. The Wide Flange Beam window opens

## Creating Your First W-Beam

### Basic Steps

1. **Select AISC Section**
   - Dropdown shows: W8x24, W8x31, W10x33, W12x26, W12x40, W14x26, W16x31
   - Each section shows: Depth, Flange Width, Weight per foot
   - Example: W8x24 = 7.93" deep × 6.495" flange × 24 lb/ft

2. **Set Length**
   - Use slider or type value (12" to 600")
   - Quick presets: 8', 10', 12', 16', 20'
   - All dimensions in inches

3. **Click "Create Beam"**
   - Beam appears at `/World/WideFlange`
   - Proper AISC geometry with fillets

## Adding Fabrication Features

### Bolt Holes

**Purpose:** Connection holes in web or flanges

1. Click **"Add Bolt Holes"**
2. Configure:
   - **Location**: Web, Top Flange, or Bottom Flange
   - **Position**: End, Start, or Center
   - **Diameter**: 0.25" to 2.0" (default 7/8" for 3/4" bolt)
   - **Count**: 1 to 10 holes
   - **Spacing**: Vertical/horizontal spacing in inches
3. Click **OK**

**Common Uses:**
- Web holes for shear connections
- Flange holes for moment connections
- Standard spacing is 3" vertical

### End Plates

**Purpose:** Welded plate at beam end for bolted connections

1. Click **"Add End Plate"**
2. Configure:
   - **End**: Start or End of beam
   - **Thickness**: Plate thickness (1/4" to 2")
   - **Height**: Plate height (0 = auto, extends 1" beyond beam)
   - **Width**: Plate width (0 = auto, matches flange)
3. Click **OK**

**Common Uses:**
- Moment connections
- Simple shear connections
- Column-to-beam connections

### Cope Cuts

**Purpose:** Notch in flange for beam-to-beam clearance

1. Click **"Add Cope"**
2. Configure:
   - **End**: Start or End of beam
   - **Flange**: Top or Bottom
   - **Depth**: How far into beam (inches)
   - **Height**: How much flange to remove (inches)
3. Click **OK**

**Common Uses:**
- Beam framing into girder flange
- Allow bolted connection clearance
- Standard cope: 2" deep × 1.5" high

## Editing Existing Beams

### Workflow

1. **Select beam** in viewport
2. Click **"Load Selected"**
3. **Modify** any parameters:
   - Change AISC section
   - Adjust length
   - Add/edit/remove features
4. Click **"Update Beam"** to regenerate
5. Click **"Clear"** to exit edit mode

### Example: Add Holes to Existing Beam

1. Create a W8x24 × 10' beam
2. Select it → Click "Load Selected"
3. Click "Add Bolt Holes"
4. Configure: Web, End, 2 holes, 3" spacing
5. Click "Update Beam"
6. Beam regenerates with holes!

## Feature Management

### Enable/Disable Features

- **Checkbox**: Toggle feature on/off without deleting
- Disabled features remain in list but aren't applied
- Re-enable anytime

### Edit Features

- Click **[Edit]** button on any feature
- Modify parameters
- Click OK to update

### Delete Features

- Click **[X]** button to permanently remove
- Cannot be undone (unless you reload from selection)

## AISC Sections Available

| Section | Depth | Flange | Weight | Typical Use |
|---------|-------|--------|--------|-------------|
| W8x24   | 7.93" | 6.50"  | 24 lb/ft | Light framing, joists |
| W8x31   | 8.00" | 8.00"  | 31 lb/ft | Medium framing |
| W10x33  | 9.73" | 7.96"  | 33 lb/ft | Floor beams |
| W12x26  | 12.22"| 6.49"  | 26 lb/ft | Long span joists |
| W12x40  | 11.94"| 8.01"  | 40 lb/ft | Primary beams |
| W14x26  | 13.91"| 5.03"  | 26 lb/ft | Light girders |
| W16x31  | 15.88"| 5.53"  | 31 lb/ft | Deep beams |

## Technical Details

### Geometry Properties

All beams include:
- ✅ Accurate AISC dimensions
- ✅ Web-to-flange fillets (0.5" radius typical)
- ✅ Proper I-beam profile
- ✅ Parametric length
- ✅ build123d solid modeling

### USD Metadata

Stored with each beam:
```json
{
  "generatorType": "wide_flange",
  "designation": "W8x24",
  "length": 120.0,
  "aisc_data": { /* full AISC dimensions */ },
  "features": [ /* bolt holes, end plates, copes */ ]
}
```

This enables:
- Full editability after creation
- Smart BIM workflows
- Fabrication data export
- Clash detection with features

## Example Workflows

### Example 1: Simple Beam

1. Select W12x26
2. Length = 144" (12 feet)
3. Create Beam
4. **Result**: Basic beam, no connections

### Example 2: Beam with Web Shear Connection

1. Select W10x33
2. Length = 192" (16 feet)
3. Add Bolt Holes:
   - Location: Web
   - Position: End
   - Count: 4
   - Spacing: 3"
4. Create Beam
5. **Result**: Beam ready for bolted shear tab

### Example 3: End Plate Moment Connection

1. Select W12x40
2. Length = 240" (20 feet)
3. Add End Plate:
   - End: Start
   - Thickness: 0.75"
   - Height: Auto (13.94")
   - Width: Auto (8.01")
4. Add Bolt Holes:
   - Location: (Add separately for flange holes if needed)
5. Create Beam
6. **Result**: Beam with welded end plate

### Example 4: Beam Framing into Girder

1. Select W8x24
2. Length = 120" (10 feet)
3. Add Cope:
   - End: Start
   - Flange: Top
   - Depth: 2"
   - Height: 1.5"
4. Add Bolt Holes:
   - Location: Web
   - Position: Start
   - Count: 3
5. Create Beam
6. **Result**: Beam ready to frame into girder web

## Tips & Best Practices

### Beam Selection

- **Light loads**: W8 or W10 series
- **Medium loads**: W12 series
- **Heavy loads**: W14 or W16 series
- **Long spans**: Deeper sections (W14, W16)

### Feature Placement

- **Bolt holes**: Typical 3" spacing, minimum edge distance 1.5"
- **End plates**: Extend 1-2" beyond beam depth
- **Copes**: Standard 2"×1.5", max 1/3 of flange height

### Design Considerations

- Check clearances before adding features
- Verify bolt edge distances meet AISC requirements
- Consider weld access for end plates
- Account for cope reductions in capacity

## Future Enhancements

Coming soon to the Steel Shapes library:

- **Channels (C-shapes)**
- **Angles (L-shapes)**
- **HSS Tubes (Rectangular & Square)**
- **Custom hole patterns** (bolt circle, grid)
- **Stiffener plates**
- **Gusset plates**
- **Advanced welds** (fillet, groove)
- **Full AISC catalog** (200+ sections)

## Troubleshooting

**Beam doesn't appear:**
- Check USD stage is open
- Verify AISC data file exists at `data/aisc_wide_flanges.json`

**Features not applying:**
- Check feature is enabled (checkbox)
- Verify parameters are reasonable
- Check console for error messages

**Can't find beam to edit:**
- Select beam in viewport first
- Check it's a wide_flange type (not other geometry)
- Verify metadata exists (created with this tool)

**Holes in wrong location:**
- Check "Position" setting (End vs Start vs Center)
- Verify "Location" (Web vs Flange)
- Adjust spacing if holes overlap

---

**Ready to build steel structures? Open Tools > Steel Shapes > Wide Flange and start designing!** 🏗️⚙️
