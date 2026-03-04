#!/usr/bin/env python3
"""
Standalone Spec Sheet Extractor — runs OUTSIDE Omniverse Kit.

Usage:
    python extract_spec.py image.png                    # Unknown equipment
    python extract_spec.py image.png centrifugal_fan    # Known equipment type
    python extract_spec.py image.png --list             # List available types
    python extract_spec.py --schema centrifugal_fan     # Print JSON template

Output: writes <image_name>.spec.json next to the image (or to --output path).
Drop that JSON into data/specs/ and use "Import Spec JSON" in the Catalog window.

Requires: ANTHROPIC_API_KEY environment variable.
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
VISION_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2048

# ---------------------------------------------------------------------------
# Equipment registry (mirrors registry_entries.py — kept in sync manually)
# ---------------------------------------------------------------------------

EQUIPMENT_SCHEMAS = {
    "centrifugal_fan": {
        "name": "Centrifugal Fan (Scroll Housing)",
        "category": "MEP Systems/Fan",
        "params": {
            "fan_size": {"type": "int", "default": 36, "description": "NYB SWSI fan size (18-73)"},
            "discharge_position": {"type": "enum", "default": "TH", "choices": ["TH", "BH", "UB", "DB", "TAU", "TAD", "BAU"]},
            "include_base": {"type": "bool", "default": True},
        },
    },
    "trapeze": {
        "name": "Trapeze Hanger",
        "category": "MEP Systems",
        "params": {
            "span": {"type": "float", "default": 24.0, "unit": "in", "min": 6.0, "max": 120.0},
            "cantilever": {"type": "float", "default": 2.0, "unit": "in", "min": 0.5, "max": 12.0},
            "drop_length": {"type": "float", "default": 36.0, "unit": "in", "min": 6.0, "max": 240.0},
            "rod_diameter": {"type": "float", "default": 0.5, "unit": "in", "min": 0.25, "max": 1.5},
            "strut_gauge": {"type": "enum", "default": "12 Ga", "choices": ["16 Ga", "14 Ga", "12 Ga", "10 Ga"]},
        },
    },
    "wide_flange": {
        "name": "Wide Flange Beam",
        "category": "Structural",
        "params": {
            "depth": {"type": "float", "default": 12.22, "unit": "in"},
            "flange_width": {"type": "float", "default": 6.49, "unit": "in"},
            "flange_thickness": {"type": "float", "default": 0.38, "unit": "in"},
            "web_thickness": {"type": "float", "default": 0.23, "unit": "in"},
            "fillet_radius": {"type": "float", "default": 0.5, "unit": "in"},
            "length": {"type": "float", "default": 120.0, "unit": "in", "min": 1.0, "max": 960.0},
        },
    },
    "duct_straight": {
        "name": "Straight Duct",
        "category": "MEP Systems/Ductwork",
        "params": {
            "width": {"type": "float", "default": 20.0, "unit": "in", "min": 4.0, "max": 120.0},
            "height": {"type": "float", "default": 10.0, "unit": "in", "min": 4.0, "max": 120.0},
            "length": {"type": "float", "default": 48.0, "unit": "in", "min": 1.0, "max": 600.0},
            "shape": {"type": "enum", "default": "rectangular", "choices": ["rectangular", "round"]},
            "add_flanges": {"type": "bool", "default": True},
        },
    },
    "stair": {
        "name": "Industrial Stair",
        "category": "Components",
        "params": {
            "total_rise": {"type": "float", "default": 120.0, "unit": "in", "min": 12.0, "max": 480.0},
            "width": {"type": "float", "default": 36.0, "unit": "in", "min": 24.0, "max": 72.0},
            "run": {"type": "float", "default": 10.0, "unit": "in", "min": 8.0, "max": 14.0},
            "landing_depth": {"type": "float", "default": 30.0, "unit": "in"},
            "stringer_size": {"type": "enum", "default": "C10", "choices": ["C8", "C10", "C12"]},
            "material": {"type": "enum", "default": "Steel", "choices": ["Steel", "Aluminum"]},
        },
    },
    "channel": {
        "name": "C-Channel",
        "category": "Structural",
        "params": {
            "depth": {"type": "float", "default": 6.0, "unit": "in"},
            "flange_width": {"type": "float", "default": 2.0, "unit": "in"},
            "flange_thickness": {"type": "float", "default": 0.343, "unit": "in"},
            "web_thickness": {"type": "float", "default": 0.200, "unit": "in"},
            "length": {"type": "float", "default": 120.0, "unit": "in", "min": 1.0, "max": 960.0},
            "fillet_radius": {"type": "float", "default": 0.25, "unit": "in"},
        },
    },
    "hss_tube": {
        "name": "HSS Tube (Rectangular)",
        "category": "Structural",
        "params": {
            "outer_width": {"type": "float", "default": 4.0, "unit": "in", "min": 1.0, "max": 24.0},
            "outer_height": {"type": "float", "default": 4.0, "unit": "in", "min": 1.0, "max": 24.0},
            "wall_thickness": {"type": "float", "default": 0.25, "unit": "in", "min": 0.065, "max": 1.0},
            "length": {"type": "float", "default": 120.0, "unit": "in", "min": 1.0, "max": 960.0},
        },
    },
    "strongback": {
        "name": "Strongback",
        "category": "Components",
        "params": {
            "length": {"type": "float", "default": 24.0, "unit": "in", "min": 6.0, "max": 240.0},
            "width": {"type": "float", "default": 8.0, "unit": "in", "min": 2.0, "max": 24.0},
            "height": {"type": "float", "default": 4.0, "unit": "in", "min": 1.0, "max": 12.0},
            "variant": {"type": "enum", "default": "C-Channel", "choices": ["C-Channel", "Strongback", "Stiffener Post"]},
            "gauge": {"type": "enum", "default": "14 Ga", "choices": ["16 Ga", "14 Ga", "12 Ga", "10 Ga"]},
        },
    },
    "screen_guard": {
        "name": "Screen Guard",
        "category": "Components",
        "params": {
            "length": {"type": "float", "default": 96.0, "unit": "in", "min": 24.0, "max": 240.0},
            "height": {"type": "float", "default": 96.0, "unit": "in", "min": 24.0, "max": 144.0},
            "corner_type": {"type": "enum", "default": "None", "choices": ["None", "Left", "Right"]},
            "finish": {"type": "enum", "default": "Safety Yellow", "choices": ["Safety Yellow", "Machine Gray", "Galvanized", "Black"]},
            "include_end_post": {"type": "bool", "default": True},
        },
    },
    "pyramid": {
        "name": "Pyramid / Tapered Extrusion",
        "category": "Components",
        "params": {
            "base": {"type": "float", "default": 100.0, "unit": "in", "min": 1.0, "max": 600.0},
            "height": {"type": "float", "default": 100.0, "unit": "in", "min": 1.0, "max": 600.0},
            "taper_angle": {"type": "float", "default": -15.0, "unit": "deg", "min": -45.0, "max": 45.0},
        },
    },
    "__placeholder__": {
        "name": "Unknown / Placeholder Equipment",
        "category": "General",
        "params": {
            "width": {"type": "float", "default": 24.0, "unit": "in"},
            "height": {"type": "float", "default": 24.0, "unit": "in"},
            "depth": {"type": "float", "default": 24.0, "unit": "in"},
            "label": {"type": "string", "default": "Unknown Equipment"},
        },
    },
}


# ---------------------------------------------------------------------------
# Image encoding
# ---------------------------------------------------------------------------

def _media_type(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
    }.get(ext, "image/png")


def _encode_image(path):
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("ascii")


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_known_prompt(entry_id):
    schema = EQUIPMENT_SCHEMAS[entry_id]
    lines = [
        f"You are analyzing a spec sheet or image of: {schema['name']}",
        "",
        "Extract the following parameters from the image.",
        "Return ONLY valid JSON with this exact structure:",
        "{",
        f'  "entry_id": "{entry_id}",',
        '  "params": {',
    ]

    param_lines = []
    for name, pdef in schema["params"].items():
        extras = f"type: {pdef['type']}"
        if "unit" in pdef:
            extras += f", unit: {pdef['unit']}"
        if "min" in pdef:
            extras += f", min: {pdef['min']}"
        if "max" in pdef:
            extras += f", max: {pdef['max']}"
        if "choices" in pdef:
            extras += f", choices: {pdef['choices']}"
        param_lines.append(f'    "{name}": <{extras}>')

    lines.append(",\n".join(param_lines))
    lines += [
        "  },",
        '  "confidence": <float 0.0-1.0>,',
        '  "source": "<make/model/drawing number if visible>",',
        '  "notes": "<any relevant observations>"',
        "}",
        "",
        "Rules:",
        "- Use null for any value you cannot confidently extract",
        "- All dimensional values should be in inches",
        "- Return ONLY the JSON object, no other text",
    ]
    return "\n".join(lines)


def build_unknown_prompt():
    known_types = [f"{k}: {v['name']}" for k, v in EQUIPMENT_SCHEMAS.items() if k != "__placeholder__"]
    lines = [
        "You are analyzing an image of industrial equipment.",
        "Identify the equipment and extract dimensional data.",
        "",
        "Return ONLY valid JSON with this structure:",
        "{",
        '  "entry_id": "<best matching type from list below, or empty string if no match>",',
        '  "params": {',
        '    "width": <estimated width in inches>,',
        '    "height": <estimated height in inches>,',
        '    "depth": <estimated depth in inches>,',
        '    "label": "<description with make/model if visible>"',
        "  },",
        '  "confidence": <float 0.0-1.0>,',
        '  "source": "<any visible make/model/spec info>",',
        '  "notes": "<observations>"',
        "}",
        "",
        "Known equipment types:",
    ]
    for t in known_types:
        lines.append(f"  - {t}")
    lines += [
        "",
        "Rules:",
        "- All dimensions in inches",
        "- If the equipment clearly matches a known type, set entry_id to that type's key",
        "- If no match, set entry_id to empty string",
        "- Return ONLY the JSON object, no other text",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_vision_api(api_key, image_path, prompt):
    media = _media_type(image_path)
    data = _encode_image(image_path)

    payload = {
        "model": VISION_MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"API Error HTTP {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)

    text = result["content"][0]["text"].strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse API response as JSON: {e}", file=sys.stderr)
        print(f"Raw response:\n{text}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_params(raw, entry_id):
    if entry_id not in EQUIPMENT_SCHEMAS:
        return raw

    schema = EQUIPMENT_SCHEMAS[entry_id]
    validated = {}

    for name, value in raw.items():
        if name not in schema["params"] or value is None:
            continue
        pdef = schema["params"][name]

        try:
            if pdef["type"] == "float":
                value = float(value)
                if "min" in pdef and value < pdef["min"]:
                    value = pdef["min"]
                if "max" in pdef and value > pdef["max"]:
                    value = pdef["max"]
            elif pdef["type"] == "int":
                value = int(value)
            elif pdef["type"] == "bool":
                value = value if isinstance(value, bool) else str(value).lower() in ("true", "1", "yes")
            elif pdef["type"] == "enum":
                value = str(value)
                if "choices" in pdef and value not in pdef["choices"]:
                    lower_map = {c.lower(): c for c in pdef["choices"]}
                    if value.lower() in lower_map:
                        value = lower_map[value.lower()]
                    else:
                        print(f"  Warning: '{value}' not in {pdef['choices']} for {name}", file=sys.stderr)
                        continue
            elif pdef["type"] == "string":
                value = str(value)

            validated[name] = value
        except (ValueError, TypeError) as e:
            print(f"  Warning: type error for {name}={value}: {e}", file=sys.stderr)

    return validated


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def generate_template(entry_id):
    """Generate a blank JSON template for manual filling."""
    schema = EQUIPMENT_SCHEMAS[entry_id]
    params = {name: pdef["default"] for name, pdef in schema["params"].items()}
    return {
        "entry_id": entry_id,
        "params": params,
        "confidence": 1.0,
        "source": "manual entry",
        "notes": f"Template for {schema['name']}",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_scene_prompt():
    """Build a prompt for Claude.ai to generate full scene JSON (for web UI use)."""
    known_types = [f"  - {k}: {v['name']}" for k, v in EQUIPMENT_SCHEMAS.items() if k != "__placeholder__"]

    return """You are analyzing an image of industrial equipment for import into an NVIDIA Omniverse USD scene.

Generate a COMPLETE scene description as JSON. The JSON must follow this exact schema:

{
  "$schema": "omniverse-usd-geometry",
  "metadata": {
    "title": "<equipment description>",
    "description": "<detailed description>",
    "units": "inches",
    "up_axis": "Y",
    "metersPerUnit": 0.0254
  },
  "dimensions_reference": {
    "<dimension_name>_in": <value>,
    ...
  },
  "defaultPrim": "/<RootPrimName>",
  "prims": {
    "/<RootPrimName>": {
      "type": "Xform",
      "children": ["/<RootPrimName>/Part1", "/<RootPrimName>/Part2", ...]
    },
    "/<RootPrimName>/Part1": {
      "type": "Cube|Cylinder|Mesh|Xform",
      "geometry": {
        // For Cube: "size_x_in", "size_y_in", "size_z_in"
        // For Cylinder: "radius_in", "height_in", "axis" ("X"|"Y"|"Z")
        //   Optional: "is_hollow": true, "inner_radius_in": N
        // For Mesh: "profile" + profile-specific params (see below)
      },
      "xform": {
        "translate": [x, y, z],
        "rotate": [rx, ry, rz]
      },
      "material": "/<RootPrimName>/Materials/<MaterialName>"
    },
    "/<RootPrimName>/Materials": {
      "type": "Scope",
      "children": {
        "/<RootPrimName>/Materials/<MatName>": {
          "type": "Material",
          "shader": "UsdPreviewSurface",
          "inputs": {
            "diffuseColor": [r, g, b],
            "metallic": 0.0-1.0,
            "roughness": 0.0-1.0
          }
        }
      }
    }
  },
  "custom_attributes": {
    "<namespace>:<key>": "<value>",
    "industrial:equipment_type": "<type>"
  }
}

Supported Mesh profiles:
- "involute_scroll": inner_radius_in, outer_radius_max_in, wall_thickness_in, depth_in, segments, center
- "truncated_cone": large_radius_in, small_radius_in, height_in, axis, segments
- "rectangular_ring": outer_width_in, outer_depth_in, inner_width_in, inner_depth_in, thickness_in
- "flat_plate": width_in, height_in, thickness_in

For bolt patterns, use "children_generated" with circular pattern:
{
  "children_generated": {
    "count": N,
    "template": {
      "type": "Cylinder",
      "geometry": {"radius_in": R, "height_in": H, "axis": "Z"},
      "pattern": "circular",
      "pattern_radius_in": R,
      "pattern_center": [x, y, z],
      "start_angle_deg": 0,
      "increment_deg": 360/N
    }
  }
}

Known equipment types for the "industrial:equipment_type" attribute:
""" + "\n".join(known_types) + """

Rules:
- ALL dimensions in inches, Y-Up coordinate system
- Use realistic PBR material values (metallic steel, painted surfaces, cast iron, etc.)
- Break the equipment into logical sub-components (housing, base, drive, flanges, etc.)
- Include bolt holes and connection points where visible
- Return ONLY the JSON object, no other text
"""


def main():
    parser = argparse.ArgumentParser(
        description="Extract equipment parameters from spec sheet images using Claude Vision.",
        epilog="Output JSON files can be imported into Omniverse Kit via the Equipment Catalog.",
    )
    parser.add_argument("image", nargs="?", help="Path to spec sheet image (png/jpg/bmp/webp)")
    parser.add_argument("entry_id", nargs="?", help="Equipment type (e.g., centrifugal_fan). Omit for auto-detect.")
    parser.add_argument("--list", action="store_true", help="List all known equipment types")
    parser.add_argument("--schema", metavar="TYPE", help="Print blank JSON template for a type")
    parser.add_argument("--output", "-o", metavar="PATH", help="Output JSON path (default: <image>.spec.json)")
    parser.add_argument("--prompt", metavar="TYPE", help="Print Claude.ai prompt for a known equipment type (copy-paste into web UI)")
    parser.add_argument("--prompt-scene", action="store_true", help="Print Claude.ai prompt for full scene JSON generation")

    args = parser.parse_args()

    if args.prompt_scene:
        print(build_scene_prompt())
        return

    if args.prompt:
        if args.prompt not in EQUIPMENT_SCHEMAS:
            print(f"Unknown type: {args.prompt}. Use --list to see available types.", file=sys.stderr)
            sys.exit(1)
        print(build_known_prompt(args.prompt))
        return

    if args.list:
        print("Available equipment types:\n")
        for eid, schema in EQUIPMENT_SCHEMAS.items():
            if eid == "__placeholder__":
                continue
            params = ", ".join(schema["params"].keys())
            print(f"  {eid:20s}  {schema['name']}")
            print(f"  {'':20s}  params: {params}\n")
        return

    if args.schema:
        if args.schema not in EQUIPMENT_SCHEMAS:
            print(f"Unknown type: {args.schema}. Use --list to see available types.", file=sys.stderr)
            sys.exit(1)
        template = generate_template(args.schema)
        print(json.dumps(template, indent=2))
        return

    if not args.image:
        parser.print_help()
        sys.exit(1)

    if not os.path.isfile(args.image):
        print(f"File not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        print("Set it with: export ANTHROPIC_API_KEY=sk-ant-...", file=sys.stderr)
        sys.exit(1)

    # Determine mode
    entry_id = args.entry_id
    if entry_id and entry_id not in EQUIPMENT_SCHEMAS:
        print(f"Unknown type: {entry_id}. Use --list to see available types.", file=sys.stderr)
        sys.exit(1)

    if entry_id:
        print(f"Extracting {EQUIPMENT_SCHEMAS[entry_id]['name']} parameters from {args.image}...")
        prompt = build_known_prompt(entry_id)
    else:
        print(f"Analyzing unknown equipment from {args.image}...")
        prompt = build_unknown_prompt()

    # Call API
    result = call_vision_api(api_key, args.image, prompt)

    # Validate
    detected_id = result.get("entry_id", entry_id or "")
    raw_params = result.get("params", {})

    if detected_id and detected_id in EQUIPMENT_SCHEMAS:
        result["params"] = validate_params(raw_params, detected_id)
        result["entry_id"] = detected_id
    else:
        result["entry_id"] = ""
        result["params"] = raw_params

    confidence = result.get("confidence", 0.0)

    # Output
    out_path = args.output or (os.path.splitext(args.image)[0] + ".spec.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nResult (confidence: {int(confidence * 100)}%):")
    print(json.dumps(result, indent=2))
    print(f"\nSaved to: {out_path}")
    print("Import this file in Omniverse via Equipment Catalog > Import Spec JSON")


if __name__ == "__main__":
    main()
