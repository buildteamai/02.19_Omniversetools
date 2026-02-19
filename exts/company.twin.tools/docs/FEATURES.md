# Pyramid Feature System

## Overview

The Pyramid Generator now supports a parametric feature system, allowing you to add non-destructive features like fillets to generated pyramids. Features are stored as metadata in USD, making pyramids fully editable after creation.

## Current Features

### Fillets

Add rounded edges to your pyramids using semantic edge selection.

**Semantic Edge Groups:**
- **Vertical Edges**: The 4 edges connecting base to top
- **Base Edges**: The 4 edges forming the bottom square
- **Top Edges**: The 4 edges forming the top square
- **All Edges**: All edges in the pyramid

## Using the Feature System

### Adding a Fillet

1. Open the Pyramid window from `Tools > Objects > Pyramid`
2. Set your base pyramid parameters (base, height, taper angle)
3. Click **"Add Fillet"** button
4. In the dialog:
   - Select an edge group (Vertical, Base, Top, or All)
   - Set the fillet radius (0.1 - 50.0)
   - Click OK
5. The feature appears in the features list
6. Click **"Create Pyramid"** to generate the geometry

### Managing Features

- **Enable/Disable**: Use the checkbox next to each feature
- **Edit**: Click the "Edit" button to modify radius or edge group
- **Delete**: Click the "X" button to remove the feature
- **Reorder**: Features are applied in the order they appear

### Feature Storage

Features are automatically stored in USD metadata:
```python
prim.GetCustomData() = {
    'generatorType': 'pyramid',
    'base': 100.0,
    'height': 100.0,
    'angle': -15.0,
    'features': [
        {'type': 'fillet', 'edges': 'vertical', 'radius': 5.0, 'enabled': True}
    ]
}
```

This allows for future editability - you can reload the parameters and regenerate the geometry.

## Technical Implementation

### PyramidGenerator.create()

```python
solid = PyramidGenerator.create(
    base=100.0,
    height=100.0,
    taper_angle=-15.0,
    features=[
        {'type': 'fillet', 'edges': 'vertical', 'radius': 5.0, 'enabled': True},
        {'type': 'fillet', 'edges': 'base', 'radius': 2.0, 'enabled': True}
    ]
)
```

### Semantic Edge Identification

The system uses geometric analysis to identify edges:
- **Vertical edges**: Large Y component, small X/Z components
- **Base edges**: Y coordinate ≈ 0
- **Top edges**: Y coordinate ≈ height

This approach is robust to parameter changes and different pyramid configurations.

## Future Features

Planned additions to the feature system:
- **Chamfers**: Beveled edges
- **Holes**: Cylindrical or custom-shaped holes
- **Drafts**: Additional taper angles on specific faces
- **Shells**: Hollow out the pyramid
- **Boolean Operations**: Cut or add shapes
- **Patterns**: Linear or circular patterns of features

## Best Practices

1. **Start simple**: Begin with base parameters, then add features
2. **Use semantic edges**: They adapt to parameter changes
3. **Order matters**: Features apply sequentially
4. **Test incrementally**: Add one feature at a time
5. **Save to USD**: Features persist in metadata for later editing

## Troubleshooting

**Fillet fails to apply:**
- Radius too large for edge length
- Conflicting features on same edges
- Solution: Reduce radius or reorder features

**Edges not selected correctly:**
- Check pyramid dimensions (very small/large pyramids may need tolerance adjustment)
- Try "All Edges" for debugging

**Performance issues:**
- Many features increase regeneration time
- Consider disabling unused features rather than deleting
