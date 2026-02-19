"""
Quick Test: Verify Pyramid Feature System

This script tests the basic functionality of the pyramid feature system
without requiring a full Omniverse environment.
"""

import sys
sys.path.append("C:/Programming/buildteamai/exts/company.twin.tools")

from company.twin.tools.objects.pyramid import PyramidGenerator

def test_basic_pyramid():
    """Test creating a basic pyramid without features"""
    print("Test 1: Basic pyramid (no features)...")
    try:
        solid = PyramidGenerator.create(
            base=100.0,
            height=100.0,
            taper_angle=-15.0
        )
        print(f"  ✓ Created pyramid with {len(solid.edges())} edges")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_pyramid_with_fillet():
    """Test creating a pyramid with one fillet feature"""
    print("\nTest 2: Pyramid with vertical fillet...")
    try:
        features = [
            {'type': 'fillet', 'edges': 'vertical', 'radius': 5.0, 'enabled': True}
        ]
        solid = PyramidGenerator.create(
            base=100.0,
            height=100.0,
            taper_angle=-15.0,
            features=features
        )
        print(f"  ✓ Created pyramid with {len(solid.edges())} edges (filleted)")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_multiple_fillets():
    """Test creating a pyramid with multiple fillets"""
    print("\nTest 3: Pyramid with multiple fillets...")
    try:
        features = [
            {'type': 'fillet', 'edges': 'vertical', 'radius': 5.0, 'enabled': True},
            {'type': 'fillet', 'edges': 'base', 'radius': 3.0, 'enabled': True}
        ]
        solid = PyramidGenerator.create(
            base=100.0,
            height=100.0,
            taper_angle=-15.0,
            features=features
        )
        print(f"  ✓ Created pyramid with {len(solid.edges())} edges (multiple fillets)")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_disabled_feature():
    """Test that disabled features are not applied"""
    print("\nTest 4: Disabled feature should be skipped...")
    try:
        features_enabled = [
            {'type': 'fillet', 'edges': 'vertical', 'radius': 5.0, 'enabled': True}
        ]
        solid_enabled = PyramidGenerator.create(
            base=100.0, height=100.0, taper_angle=-15.0,
            features=features_enabled
        )

        features_disabled = [
            {'type': 'fillet', 'edges': 'vertical', 'radius': 5.0, 'enabled': False}
        ]
        solid_disabled = PyramidGenerator.create(
            base=100.0, height=100.0, taper_angle=-15.0,
            features=features_disabled
        )

        edges_enabled = len(solid_enabled.edges())
        edges_disabled = len(solid_disabled.edges())

        if edges_disabled < edges_enabled:
            print(f"  ✓ Disabled feature skipped (enabled: {edges_enabled} edges, disabled: {edges_disabled} edges)")
            return True
        else:
            print(f"  ✗ Disabled feature may not have been skipped")
            return False

    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_semantic_edges():
    """Test semantic edge identification"""
    print("\nTest 5: Semantic edge identification...")
    try:
        # Create base pyramid
        solid = PyramidGenerator.create(
            base=100.0,
            height=100.0,
            taper_angle=-15.0
        )

        # Test edge group identification
        vertical_edges = PyramidGenerator._get_semantic_edges(solid, 'vertical', 100, 100, 70)
        base_edges = PyramidGenerator._get_semantic_edges(solid, 'base', 100, 100, 70)
        top_edges = PyramidGenerator._get_semantic_edges(solid, 'top', 100, 100, 70)
        all_edges = PyramidGenerator._get_semantic_edges(solid, 'all', 100, 100, 70)

        print(f"  Vertical edges: {len(vertical_edges)}")
        print(f"  Base edges: {len(base_edges)}")
        print(f"  Top edges: {len(top_edges)}")
        print(f"  All edges: {len(all_edges)}")

        # Basic validation: should find edges in each group
        if len(vertical_edges) > 0 and len(base_edges) > 0 and len(top_edges) > 0:
            print(f"  ✓ All edge groups identified")
            return True
        else:
            print(f"  ✗ Some edge groups not found")
            return False

    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Pyramid Feature System - Quick Tests")
    print("=" * 60)

    results = []
    results.append(test_basic_pyramid())
    results.append(test_pyramid_with_fillet())
    results.append(test_multiple_fillets())
    results.append(test_disabled_feature())
    results.append(test_semantic_edges())

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Tests Passed: {passed}/{total}")

    if passed == total:
        print("✓ All tests passed! Feature system is working correctly.")
    else:
        print("✗ Some tests failed. Check error messages above.")

    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
