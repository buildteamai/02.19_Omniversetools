#!/usr/bin/env python3
"""
Export Equipment Schemas — generates blank JSON templates for manual filling.

Usage:
    python export_schema.py                     # Export all schemas
    python export_schema.py centrifugal_fan     # Export one schema
    python export_schema.py --output-dir specs/ # Write to directory

Output files are compatible with "Import Spec JSON" in the Equipment Catalog.
"""

import argparse
import json
import os
import sys

# Import schemas from the extraction tool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_spec import EQUIPMENT_SCHEMAS


def generate_template(entry_id):
    """Generate a blank .spec.json template with defaults pre-filled."""
    schema = EQUIPMENT_SCHEMAS[entry_id]
    params = {}
    for name, pdef in schema["params"].items():
        params[name] = pdef["default"]

    return {
        "entry_id": entry_id,
        "params": params,
        "confidence": 1.0,
        "source": "manual entry",
        "notes": f"Template for {schema['name']} — fill in values and import into Kit",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Export equipment parameter schemas as JSON templates.",
        epilog="Generated files can be filled in manually and imported via Equipment Catalog > Import Spec JSON.",
    )
    parser.add_argument(
        "entry_id", nargs="?",
        help="Equipment type to export (e.g., centrifugal_fan). Omit for all.",
    )
    parser.add_argument(
        "--output-dir", "-d", metavar="DIR", default=".",
        help="Directory for output files (default: current directory)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available equipment types",
    )

    args = parser.parse_args()

    if args.list:
        print("Available equipment types:\n")
        for eid, schema in EQUIPMENT_SCHEMAS.items():
            if eid == "__placeholder__":
                continue
            print(f"  {eid:20s}  {schema['name']}")
        return

    # Determine which schemas to export
    if args.entry_id:
        if args.entry_id not in EQUIPMENT_SCHEMAS:
            print(f"Unknown type: {args.entry_id}. Use --list to see options.",
                  file=sys.stderr)
            sys.exit(1)
        ids = [args.entry_id]
    else:
        ids = [k for k in EQUIPMENT_SCHEMAS if k != "__placeholder__"]

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    for eid in ids:
        template = generate_template(eid)
        out_path = os.path.join(args.output_dir, f"{eid}.spec.json")
        with open(out_path, "w") as f:
            json.dump(template, f, indent=2)
        print(f"  {out_path}")

    print(f"\nExported {len(ids)} template(s) to {os.path.abspath(args.output_dir)}")
    print("Fill in parameter values, then import via Equipment Catalog > Import Spec JSON")


if __name__ == "__main__":
    main()
