"""
Example: Creating Pyramids with Filleted Edges

This example demonstrates how to use the PyramidGenerator with the new feature system
to create pyramids with filleted edges programmatically.
"""

import sys
sys.path.append("C:/Programming/buildteamai/exts/company.twin.tools")

from company.twin.tools.objects.pyramid import PyramidGenerator
import build123d as bd

def example_1_vertical_fillet():
    """Create a pyramid with filleted vertical edges"""
    print("\n=== Example 1: Pyramid with Filleted Vertical Edges ===")

    features = [
        {
            'type': 'fillet',
            'edges': 'vertical',
            'radius': 5.0,
            'enabled': True
        }
    ]

    solid = PyramidGenerator.create(
        base=100.0,
        height=100.0,
        taper_angle=-15.0,
        features=features
    )

    print(f"Created pyramid with {len(features)} feature(s)")
    print(f"Vertices: {len(solid.vertices())}, Faces: {len(solid.faces())}")

    # Export to STEP file for inspection
    bd.export_step(solid, "pyramid_vertical_fillet.step")
    print("Exported to: pyramid_vertical_fillet.step")

    return solid


def example_2_multiple_fillets():
    """Create a pyramid with multiple filleted edge groups"""
    print("\n=== Example 2: Pyramid with Multiple Fillets ===")

    features = [
        {
            'type': 'fillet',
            'edges': 'vertical',
            'radius': 5.0,
            'enabled': True
        },
        {
            'type': 'fillet',
            'edges': 'base',
            'radius': 3.0,
            'enabled': True
        },
        {
            'type': 'fillet',
            'edges': 'top',
            'radius': 2.0,
            'enabled': True
        }
    ]

    solid = PyramidGenerator.create(
        base=150.0,
        height=120.0,
        taper_angle=-20.0,
        features=features
    )

    print(f"Created pyramid with {len(features)} feature(s)")
    print(f"Vertices: {len(solid.vertices())}, Faces: {len(solid.faces())}")

    bd.export_step(solid, "pyramid_multiple_fillets.step")
    print("Exported to: pyramid_multiple_fillets.step")

    return solid


def example_3_disabled_feature():
    """Demonstrate feature enable/disable"""
    print("\n=== Example 3: Feature Enable/Disable ===")

    # Create with all features enabled
    features_enabled = [
        {'type': 'fillet', 'edges': 'vertical', 'radius': 5.0, 'enabled': True},
        {'type': 'fillet', 'edges': 'base', 'radius': 3.0, 'enabled': True}
    ]

    solid_with_features = PyramidGenerator.create(
        base=100.0, height=100.0, taper_angle=-15.0,
        features=features_enabled
    )

    print(f"With features: {len(solid_with_features.faces())} faces")

    # Disable one feature
    features_enabled[1]['enabled'] = False

    solid_partial = PyramidGenerator.create(
        base=100.0, height=100.0, taper_angle=-15.0,
        features=features_enabled
    )

    print(f"With 1 disabled: {len(solid_partial.faces())} faces")

    return solid_with_features


def example_4_different_pyramids():
    """Create various pyramid types with fillets"""
    print("\n=== Example 4: Different Pyramid Configurations ===")

    configs = [
        {"name": "Tall Steep", "base": 50, "height": 200, "angle": -5, "fillet": 3},
        {"name": "Flat Wide", "base": 200, "height": 50, "angle": -30, "fillet": 5},
        {"name": "Inverted", "base": 50, "height": 100, "angle": 15, "fillet": 4},
        {"name": "Large Base", "base": 300, "height": 150, "angle": -20, "fillet": 10}
    ]

    for config in configs:
        features = [
            {'type': 'fillet', 'edges': 'vertical', 'radius': config['fillet'], 'enabled': True}
        ]

        solid = PyramidGenerator.create(
            base=config['base'],
            height=config['height'],
            taper_angle=config['angle'],
            features=features
        )

        filename = f"pyramid_{config['name'].lower().replace(' ', '_')}.step"
        bd.export_step(solid, filename)
        print(f"{config['name']}: {len(solid.faces())} faces -> {filename}")


def example_5_all_edges():
    """Create a pyramid with all edges filleted"""
    print("\n=== Example 5: All Edges Filleted ===")

    features = [
        {
            'type': 'fillet',
            'edges': 'all',
            'radius': 4.0,
            'enabled': True
        }
    ]

    solid = PyramidGenerator.create(
        base=120.0,
        height=100.0,
        taper_angle=-18.0,
        features=features
    )

    print(f"Created pyramid with all edges filleted")
    print(f"Vertices: {len(solid.vertices())}, Faces: {len(solid.faces())}")

    bd.export_step(solid, "pyramid_all_edges.step")
    print("Exported to: pyramid_all_edges.step")

    return solid


def main():
    """Run all examples"""
    print("=" * 60)
    print("Pyramid Feature System Examples")
    print("=" * 60)

    try:
        example_1_vertical_fillet()
        example_2_multiple_fillets()
        example_3_disabled_feature()
        example_4_different_pyramids()
        example_5_all_edges()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("Check the generated STEP files for visual inspection.")
        print("=" * 60)

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
