"""Command Palette — keyboard-driven fuzzy search over all tools.

Zero external dependencies: pure stdlib string matching via difflib.
"""

import omni.ui
from difflib import SequenceMatcher

COMMANDS = [
    {"name": "Equipment Catalog",     "category": "Catalog",       "tags": ["browse", "search", "ieip"],              "method": "_show_catalog_window"},
    {"name": "Wide Flange",           "category": "Structural",    "tags": ["beam", "w-shape", "aisc", "steel"],      "method": "_show_wide_flange_window"},
    {"name": "Channel",               "category": "Structural",    "tags": ["c-shape", "aisc", "steel"],              "method": "_show_channel_window"},
    {"name": "HSS Tube",              "category": "Structural",    "tags": ["tube", "hollow", "aisc", "steel"],       "method": "_show_hss_window"},
    {"name": "Strongback",            "category": "Structural",    "tags": ["brace", "support"],                      "method": "_show_strongback_window"},
    {"name": "Frame Generator",       "category": "Structural",    "tags": ["frame", "skeleton"],                     "method": "_show_frame_window"},
    {"name": "Steel Connection",      "category": "Structural",    "tags": ["joint", "bolt", "weld"],                 "method": "_show_steel_connection_window"},
    {"name": "Ductwork",              "category": "MEP",           "tags": ["duct", "hvac", "air"],                   "method": "_show_duct_window"},
    {"name": "Piping",                "category": "MEP",           "tags": ["pipe", "plumbing"],                      "method": "_show_pipe_window"},
    {"name": "Trapeze Hanger",        "category": "MEP",           "tags": ["hanger", "support", "trapeze"],          "method": "_show_trapeze_window"},
    {"name": "Exhaust Tap",           "category": "MEP",           "tags": ["tap", "exhaust", "vent"],                "method": "_show_tap_window"},
    {"name": "Fan Controls",          "category": "MEP",           "tags": ["fan", "blower", "ventilation"],          "method": "_show_fan_controls_window"},
    {"name": "Fan Design",            "category": "MEP",           "tags": ["fan", "blower", "centrifugal", "cfm", "pressure", "impeller"], "method": "_show_fan_design_window"},
    {"name": "Sheet Metal Panel",     "category": "Components",    "tags": ["panel", "sheet", "metal"],               "method": "_show_sheet_metal_window"},
    {"name": "Transition / Pyramid",  "category": "Components",    "tags": ["pyramid", "transition", "hopper"],       "method": "_show_pyramid_window"},
    {"name": "Safety Fence",          "category": "Components",    "tags": ["fence", "guard", "screen", "railing"],   "method": "_show_screen_guard_window"},
    {"name": "Industrial Stair",      "category": "Components",    "tags": ["stair", "stairs", "step"],               "method": "_show_stair_window"},
    {"name": "Conveyor (OHPF)",       "category": "Components",    "tags": ["conveyor", "overhead", "power free"],    "method": "_show_ohpf_window"},
    {"name": "Platform",              "category": "Components",    "tags": ["platform", "table", "workbench"],        "method": "_show_platform_window"},
    {"name": "Construction Cube",     "category": "Components",    "tags": ["cube", "construction", "module"],        "method": "_show_construction_cube_window"},
    {"name": "Building Configurator", "category": "Buildings",     "tags": ["building", "structure"],                 "method": "_show_building_window"},
    {"name": "Enclosure Configurator","category": "Buildings",     "tags": ["enclosure", "room", "booth"],            "method": "_show_enclosure_configurator"},
    {"name": "Mate Objects",          "category": "Assembly",      "tags": ["mate", "connect", "snap", "anchor"],     "method": "_show_mating_window"},
    {"name": "New Scene (ANSI)",      "category": "Scene",         "tags": ["new", "scene", "reset"],                 "method": "_new_ansi_scene"},
    {"name": "Measurement Tool",      "category": "Scene",         "tags": ["measure", "distance", "ruler"],          "method": "_show_measure_window"},
    {"name": "Style Editor",          "category": "Scene",         "tags": ["style", "material", "color"],            "method": "_show_style_editor_window"},
    {"name": "STEP File Import",      "category": "Import/Export", "tags": ["step", "import", "cad"],                 "method": "_show_step_import_window"},
    {"name": "STEP File Export",      "category": "Import/Export", "tags": ["step", "export", "cad"],                 "method": "_show_step_export_window"},
    {"name": "Image to 3D (TripoSR)", "category": "Import/Export", "tags": ["image", "3d", "triposr", "mesh"],       "method": "_show_triposr_window"},
    {"name": "Insert Equipment",      "category": "Import/Export", "tags": ["insert", "usd", "reference"],            "method": "_show_insert_equipment_window"},
    {"name": "BOM Export",            "category": "Import/Export", "tags": ["bom", "bill of materials", "csv"],       "method": "_show_bom_window"},
]

# Category display colors (RGBA floats)
_CATEGORY_COLORS = {
    "Catalog":       (0.2, 0.6, 1.0, 1.0),
    "Structural":    (0.9, 0.5, 0.1, 1.0),
    "MEP":           (0.2, 0.8, 0.4, 1.0),
    "Components":    (0.7, 0.5, 0.9, 1.0),
    "Buildings":     (0.9, 0.7, 0.2, 1.0),
    "Assembly":      (0.4, 0.7, 0.9, 1.0),
    "Scene":         (0.6, 0.6, 0.6, 1.0),
    "Import/Export": (0.5, 0.8, 0.8, 1.0),
}


def _score(query, cmd):
    """Score a command against a search query. Higher is better."""
    q = query.lower()
    # Check name, category, and tags
    name_lower = cmd["name"].lower()
    cat_lower = cmd["category"].lower()
    tags_str = " ".join(cmd["tags"])

    # Exact substring match in name gets highest priority
    if q in name_lower:
        return 2.0

    # Exact substring match in tags
    if q in tags_str:
        return 1.5

    # Exact substring match in category
    if q in cat_lower:
        return 1.2

    # Fuzzy match against combined text
    combined = f"{name_lower} {cat_lower} {tags_str}"
    return SequenceMatcher(None, q, combined).ratio()


class CommandPaletteWindow:
    """Lightweight fuzzy-search popup for tool access."""

    WINDOW_NAME = "Command Palette"

    def __init__(self):
        self._extension = None
        self._result_frames = []
        self._window = omni.ui.Window(
            self.WINDOW_NAME,
            width=420,
            height=500,
            flags=(
                omni.ui.WINDOW_FLAGS_NO_SCROLLBAR
            ),
        )
        self._build_ui()

    def _build_ui(self):
        with self._window.frame:
            with omni.ui.VStack(spacing=4):
                # Search input
                with omni.ui.HStack(height=30):
                    omni.ui.Label("Search:", width=50)
                    self._search_field = omni.ui.StringField(height=26)
                    self._search_field.model.add_value_changed_fn(self._on_search_changed)

                omni.ui.Separator(height=2)

                # Results area
                self._results_scroll = omni.ui.ScrollingFrame(
                    horizontal_scrollbar_policy=omni.ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
                    vertical_scrollbar_policy=omni.ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                )
                with self._results_scroll:
                    self._results_container = omni.ui.VStack(spacing=2)

        # Initial population with all commands
        self._update_results("")

    def _on_search_changed(self, model):
        query = model.as_string.strip()
        self._update_results(query)

    def _update_results(self, query):
        """Re-render the results list based on the query."""
        # Clear previous results
        # Rebuild inside the container
        self._results_container.clear()

        if query:
            scored = [(cmd, _score(query, cmd)) for cmd in COMMANDS]
            scored.sort(key=lambda x: x[1], reverse=True)
            filtered = [(cmd, s) for cmd, s in scored if s > 0.3][:12]
        else:
            filtered = [(cmd, 1.0) for cmd in COMMANDS]

        with self._results_container:
            for cmd, _ in filtered:
                self._build_result_row(cmd)

    def _build_result_row(self, cmd):
        """Build a single clickable result row."""
        method_name = cmd["method"]
        cat = cmd["category"]
        color = _CATEGORY_COLORS.get(cat, (0.5, 0.5, 0.5, 1.0))

        with omni.ui.HStack(height=24, spacing=6):
            # Category badge
            with omni.ui.ZStack(width=90):
                omni.ui.Rectangle(
                    style={
                        "background_color": omni.ui.color(*color),
                        "border_radius": 3,
                    }
                )
                omni.ui.Label(
                    cat,
                    alignment=omni.ui.Alignment.CENTER,
                    style={"font_size": 12, "color": omni.ui.color(1, 1, 1, 1)},
                )

            # Command name as clickable label
            btn = omni.ui.Button(
                cmd["name"],
                height=24,
                clicked_fn=lambda m=method_name: self._invoke(m),
                style={
                    "Button": {"background_color": omni.ui.color(0.22, 0.22, 0.22, 1.0), "border_radius": 3},
                    "Button:hovered": {"background_color": omni.ui.color(0.32, 0.32, 0.32, 1.0)},
                    "Button.Label": {"font_size": 14, "alignment": omni.ui.Alignment.LEFT_CENTER},
                },
            )

    def _invoke(self, method_name):
        """Call the named method on the extension instance."""
        if self._extension is None:
            from ..extension import get_extension
            self._extension = get_extension()

        if self._extension is None:
            print("[CommandPalette] No extension instance available")
            return

        fn = getattr(self._extension, method_name, None)
        if fn:
            fn()
            self._window.visible = False
        else:
            print(f"[CommandPalette] Method not found: {method_name}")

    @property
    def visible(self):
        return self._window.visible

    @visible.setter
    def visible(self, value):
        self._window.visible = value
        if value:
            # Reset search and focus
            self._search_field.model.set_value("")
            self._update_results("")
            self._window.focus()

    def destroy(self):
        if self._window:
            self._window.destroy()
            self._window = None
