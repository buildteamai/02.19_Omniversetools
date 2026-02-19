# Quick Start: Pyramid Feature System

## What's New?

Your Pyramid Generator now supports **parametric features**! You can add filleted edges to pyramids using semantic edge selection, and all features are stored in USD metadata for future editability.

## Using the Feature System

### Launch the Pyramid Window

1. Start your Omniverse application
2. Go to **Tools > Objects > Pyramid**
3. The enhanced Pyramid window opens

### Create a Basic Pyramid

1. Set parameters:
   - Base Length: 100
   - Height: 100
   - Taper Angle: -15
2. Click **"Create Pyramid"**
3. A pyramid appears at `/World/Pyramid`

### Add Your First Fillet

1. Click **"Add Fillet"** button
2. In the dialog:
   - Select **"Vertical"** from the Edge Group dropdown
   - Set Radius to **5.0**
   - Click **OK**
3. You'll see: `☑ Fillet - Vertical Edges (r=5.0) [Edit] [X]`
4. Click **"Create Pyramid"**
5. Your pyramid now has rounded vertical edges!

### Add Multiple Fillets

1. Click **"Add Fillet"** again
2. Select **"Base"** edges, radius **3.0**, click OK
3. Click **"Add Fillet"** again
4. Select **"Top"** edges, radius **2.0**, click OK
5. Click **"Create Pyramid"**
6. Your pyramid now has 3 different filleted edge groups!

### Use Feature Presets

1. Open the **Variant** dropdown
2. Select **"Rounded Edges"** - automatically loads a preset with filleted vertical edges
3. Select **"Fully Rounded"** - loads a preset with all edges filleted
4. Click **"Create Pyramid"** to see the result

### Edit a Feature

1. Click the **[Edit]** button next to a feature
2. Change the radius or edge group
3. Click **OK**
4. Create a new pyramid to see the changes

### Disable a Feature (Without Deleting)

1. **Uncheck** the checkbox next to a feature
2. Click **"Create Pyramid"**
3. The disabled feature won't be applied
4. Re-check to enable it again

### Delete a Feature

1. Click the **[X]** button next to a feature
2. The feature is permanently removed from the list

## Edge Groups Explained

- **Vertical Edges** (4 edges): Connect the base square to the top square
- **Base Edges** (4 edges): Form the bottom square of the pyramid
- **Top Edges** (4 edges): Form the top square of the pyramid
- **All Edges** (12 edges): Every edge in the pyramid

## Tips & Tricks

1. **Start Simple**: Begin with just vertical edge fillets (most common)
2. **Feature Order Matters**: Features are applied in the order shown
3. **Fillet Radius**: Start with small radii (3-5) and increase as needed
4. **Large Radii**: Too large a radius may fail - keep it < 10-20% of base dimension
5. **Experiment**: Use variants to quickly try different configurations

## Troubleshooting

**Problem**: Fillet doesn't appear
- **Solution**: Radius may be too small or too large. Try 5.0 as a starting point.

**Problem**: Error when creating pyramid
- **Solution**: Fillet radius may be larger than edge length. Reduce the radius.

**Problem**: Features list is empty
- **Solution**: Click "Add Fillet" to add your first feature.

## What's Stored?

When you create a pyramid with features, the following is saved in USD metadata:
- Generator type (`'pyramid'`)
- Base parameters (base, height, angle)
- Complete features list with all settings

This enables future editability - you'll be able to reload and modify pyramids in future versions!

## Examples

Check out the examples folder for programmatic usage:
- `examples/test_pyramid_features.py` - Quick tests
- `examples/pyramid_with_fillets.py` - 5 detailed examples

## Documentation

For complete technical details, see:
- `exts/company.twin.tools/docs/FEATURES.md` - Full feature documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical implementation details

## Future Features Coming Soon

- Chamfered edges (beveled corners)
- Holes through faces
- Shell (hollow out)
- Edit mode (modify existing pyramids)
- Feature patterns (repeat features)

---

**Ready to create some amazing pyramids? Open the Pyramid window and start adding features!** 🔺✨
