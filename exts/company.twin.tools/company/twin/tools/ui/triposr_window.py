"""
TripoSR Window — Image to 3D mesh generation UI.

Supports two backends:
  - Tripo Cloud (v2.5/v3.0 models via cloud API, returns GLB with PBR)
  - Local Server (open-source TripoSR via FastAPI, returns OBJ)
"""

import asyncio
import os
import threading

import carb.settings
import omni.ui as ui
import omni.kit.app

from ..core.triposr_client import TripoSRClient, TripoCloudClient
from ..importers.mesh_importer import MeshImporter

_SETTINGS_API_KEY = "/exts/company.twin.tools/tripo_api_key"

# Backend indices
_BACKEND_CLOUD = 0
_BACKEND_LOCAL = 1


class _BackendItem(ui.AbstractItem):
    def __init__(self, text):
        super().__init__()
        self.model = ui.SimpleStringModel(text)


class _BackendModel(ui.AbstractItemModel):
    def __init__(self):
        super().__init__()
        self._items = [_BackendItem("Tripo Cloud"), _BackendItem("Local Server")]
        self._current = ui.SimpleIntModel(0)

    def get_item_children(self, item):
        return self._items if item is None else []

    def get_item_value_model(self, item, column_id):
        if item is None:
            return self._current
        return item.model

    @property
    def current_index(self):
        return self._current.as_int

    @current_index.setter
    def current_index(self, value):
        self._current.set_value(value)


class TripoSRWindow(ui.Window):
    def __init__(self, title="Image to 3D", **kwargs):
        super().__init__(title, width=420, height=460, **kwargs)

        self._local_client = TripoSRClient()
        self._cloud_client = TripoCloudClient()
        self._importer = MeshImporter()

        # Load persisted API key
        settings = carb.settings.get_settings()
        saved_key = settings.get(_SETTINGS_API_KEY) or ""

        # Models — shared
        self._backend_model = _BackendModel()
        self._path_model = ui.SimpleStringModel("")
        self._remove_bg_model = ui.SimpleBoolModel(True)

        # Models — cloud
        self._api_key_model = ui.SimpleStringModel(saved_key)
        self._face_limit_model = ui.SimpleIntModel(50000)

        # Models — local
        self._server_model = ui.SimpleStringModel("http://127.0.0.1:8000")
        self._foreground_ratio_model = ui.SimpleFloatModel(0.85)
        self._resolution_model = ui.SimpleIntModel(320)

        # State
        self._generating = False
        self._generate_btn = None
        self._status_label = None
        self._cloud_frame = None
        self._local_frame = None

        self._build_ui()
        self._update_backend_visibility()

    def _build_ui(self):
        with self.frame:
            with ui.VStack(spacing=8, padding=15):
                # Header
                ui.Label("Image to 3D", style={"font_size": 18, "color": 0xFFDDDDDD})
                ui.Label(
                    "Generate a 3D mesh from a single photo",
                    style={"font_size": 12, "color": 0xFF888888},
                )
                ui.Separator(height=5)

                # Backend selector
                with ui.HStack(height=22):
                    ui.Label("Backend:", width=100, style={"color": 0xFFAAAAAA})
                    combo = ui.ComboBox(self._backend_model, width=ui.Fraction(1))
                    combo.model.add_item_changed_fn(self._on_backend_changed)

                ui.Spacer(height=2)

                # --- Cloud settings ---
                self._cloud_frame = ui.Frame(visible=True)
                with self._cloud_frame:
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=22):
                            ui.Label("API Key:", width=100, style={"color": 0xFFAAAAAA})
                            ui.StringField(model=self._api_key_model, password_mode=True)
                            ui.Button("Test", width=50, clicked_fn=self._on_test_cloud)

                # --- Local settings ---
                self._local_frame = ui.Frame(visible=False)
                with self._local_frame:
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=22):
                            ui.Label("Server:", width=100, style={"color": 0xFFAAAAAA})
                            ui.StringField(model=self._server_model)
                            ui.Button("Test", width=50, clicked_fn=self._on_test_local)

                ui.Spacer(height=4)

                # Image path
                with ui.HStack(height=22):
                    ui.Label("Image Path:", width=100, style={"color": 0xFFAAAAAA})
                    ui.StringField(model=self._path_model)

                ui.Label(
                    "Paste an absolute path to a .png or .jpg image.",
                    style={"font_size": 11, "color": 0xFF666666},
                )

                ui.Spacer(height=4)
                ui.Separator(height=2)

                # Parameters
                ui.Label("Parameters", style={"font_size": 14, "color": 0xFFCCCCCC})

                with ui.HStack(height=22):
                    ui.Label("Remove Background:", width=140)
                    ui.CheckBox(model=self._remove_bg_model)

                # --- Cloud params ---
                self._cloud_params_frame = ui.Frame(visible=True)
                with self._cloud_params_frame:
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=22):
                            ui.Label("Face Limit:", width=140)
                            ui.IntSlider(
                                model=self._face_limit_model,
                                min=10000, max=100000, step=5000,
                            )

                # --- Local params ---
                self._local_params_frame = ui.Frame(visible=False)
                with self._local_params_frame:
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=22):
                            ui.Label("Foreground Ratio:", width=140)
                            ui.FloatSlider(
                                model=self._foreground_ratio_model,
                                min=0.5, max=1.0, step=0.05,
                            )
                        with ui.HStack(height=22):
                            ui.Label("Mesh Resolution:", width=140)
                            ui.IntSlider(
                                model=self._resolution_model,
                                min=32, max=320, step=32,
                            )

                ui.Spacer(height=8)

                # Generate button
                self._generate_btn = ui.Button(
                    "Generate Mesh",
                    clicked_fn=self._on_generate,
                    height=40,
                    style={"background_color": 0xFF2D5A27, "font_size": 16},
                )

                # Status
                ui.Spacer(height=4)
                self._status_label = ui.Label("Ready", style={"color": 0xFFCCCCCC})

    # ------------------------------------------------------------------
    # Backend switching
    # ------------------------------------------------------------------
    def _on_backend_changed(self, model, item):
        self._update_backend_visibility()

    def _update_backend_visibility(self):
        is_cloud = self._backend_model.current_index == _BACKEND_CLOUD
        if self._cloud_frame:
            self._cloud_frame.visible = is_cloud
        if self._local_frame:
            self._local_frame.visible = not is_cloud
        if self._cloud_params_frame:
            self._cloud_params_frame.visible = is_cloud
        if self._local_params_frame:
            self._local_params_frame.visible = not is_cloud

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_status(self, text: str):
        if self._status_label:
            self._status_label.text = text

    def _save_api_key(self):
        key = self._api_key_model.as_string.strip()
        settings = carb.settings.get_settings()
        settings.set(_SETTINGS_API_KEY, key)

    # ------------------------------------------------------------------
    # Test buttons
    # ------------------------------------------------------------------
    def _on_test_cloud(self):
        key = self._api_key_model.as_string.strip()
        if not key:
            self._set_status("Enter an API key first.")
            return
        self._cloud_client.api_key = key
        self._save_api_key()
        info = self._cloud_client.health()
        if info.get("status") == "ready":
            bal = info.get("balance", "?")
            self._set_status(f"Cloud OK — balance: {bal}")
        else:
            self._set_status(f"Cloud error: {info.get('detail', 'unknown')}")

    def _on_test_local(self):
        self._local_client.base_url = self._server_model.as_string.strip()
        info = self._local_client.health()
        if info.get("status") == "ready":
            dev = info.get("device", "?")
            self._set_status(f"Server OK — model on {dev}")
        else:
            detail = info.get("detail", info.get("status", "unknown"))
            self._set_status(f"Server error: {detail}")

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------
    def _on_generate(self):
        if self._generating:
            return

        image_path = self._path_model.as_string.strip().strip('"').strip("'")
        if not image_path:
            self._set_status("Please enter an image path.")
            return
        if not os.path.exists(image_path):
            self._set_status(f"File not found: {image_path}")
            return

        is_cloud = self._backend_model.current_index == _BACKEND_CLOUD

        if is_cloud:
            key = self._api_key_model.as_string.strip()
            if not key:
                self._set_status("Enter a Tripo API key first.")
                return
            self._cloud_client.api_key = key
            self._save_api_key()
        else:
            self._local_client.base_url = self._server_model.as_string.strip()
            if not self._local_client.is_ready():
                self._set_status("Server not reachable. Is api_server.py running?")
                return

        self._generating = True
        self._generate_btn.text = "Generating..."
        self._generate_btn.enabled = False
        backend_label = "Tripo Cloud" if is_cloud else "local server"
        self._set_status(f"Sending image to {backend_label}...")

        self._main_loop = asyncio.get_event_loop()

        params = {"image_path": image_path, "is_cloud": is_cloud}
        if is_cloud:
            params["face_limit"] = self._face_limit_model.as_int
        else:
            params["remove_bg"] = self._remove_bg_model.as_bool
            params["foreground_ratio"] = self._foreground_ratio_model.as_float
            params["mc_resolution"] = self._resolution_model.as_int

        thread = threading.Thread(target=self._generate_worker, args=(params,), daemon=True)
        thread.start()

    def _generate_worker(self, params: dict):
        """Runs on a background thread — calls the selected backend."""
        if params["is_cloud"]:
            result = self._cloud_client.generate(
                image_path=params["image_path"],
                face_limit=params["face_limit"],
            )
        else:
            result = self._local_client.generate(
                image_path=params["image_path"],
                remove_bg=params["remove_bg"],
                foreground_ratio=params["foreground_ratio"],
                mc_resolution=params["mc_resolution"],
                output_format="obj",
            )

        async def _do_import():
            self._on_generate_complete(result)

        self._main_loop.call_soon_threadsafe(asyncio.ensure_future, _do_import())

    def _on_generate_complete(self, result: dict):
        """Called on main thread after the backend responds."""
        self._generating = False
        self._generate_btn.text = "Generate Mesh"
        self._generate_btn.enabled = True

        if "error" in result:
            self._set_status(f"Error: {result['error']}")
            print(f"[TripoSR] Generation failed: {result['error']}")
            return

        mesh_path = result.get("mesh_path", "")
        elapsed = result.get("elapsed_seconds", 0)
        job_id = result.get("job_id", "")

        if not mesh_path or not os.path.exists(mesh_path):
            self._set_status("Error: mesh file not found on disk")
            return

        self._set_status(f"Importing mesh ({elapsed}s inference)...")

        success = self._importer.import_to_stage(
            mesh_path,
            target_path="/World/TripoSR",
            source_tag="triposr",
        )

        if success:
            fmt = result.get("format", "?")
            self._set_status(f"Done — {fmt.upper()} generated in {elapsed}s (job {job_id})")
        else:
            self._set_status("Mesh generated but USD import failed. Check console.")
