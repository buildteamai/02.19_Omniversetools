"""
TripoSR / Tripo Cloud API Clients
===================================
Lightweight HTTP clients for 3D mesh generation from images.
Uses only stdlib (urllib) — no requests/httpx dependency needed in Kit.

Two backends:
  - ``TripoSRClient``   — local FastAPI server (open-source TripoSR model)
  - ``TripoCloudClient`` — Tripo cloud API (v2.5/v3.0 models, PBR textures)

Usage::

    # Local server
    client = TripoSRClient()
    result = client.generate("widget.png")

    # Cloud API
    cloud = TripoCloudClient("tsk_xxxxx")
    result = cloud.generate("widget.png")  # returns GLB
"""

import json
import os
import tempfile
import time
import uuid
import urllib.request
import urllib.error
from typing import Optional


class TripoSRClient:
    """Synchronous client for the TripoSR FastAPI server."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def is_ready(self, timeout: float = 3.0) -> bool:
        """Return True if the server is up and the model is loaded."""
        try:
            req = urllib.request.Request(f"{self.base_url}/health")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
                return data.get("status") == "ready"
        except Exception:
            return False

    def health(self, timeout: float = 3.0) -> dict:
        """Return the full health payload or an error dict."""
        try:
            req = urllib.request.Request(f"{self.base_url}/health")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------
    def generate(
        self,
        image_path: str,
        remove_bg: bool = True,
        foreground_ratio: float = 0.85,
        mc_resolution: int = 256,
        output_format: str = "obj",
        timeout: float = 120.0,
    ) -> dict:
        """
        Send an image to the server and get back the generated mesh path.

        Args:
            image_path:       Local path to the input image (.png, .jpg, etc.)
            remove_bg:        Whether the server should remove background.
            foreground_ratio: Foreground-to-image ratio (0.5–1.0).
            mc_resolution:    Marching cubes grid resolution (32–320).
            output_format:    "obj" or "glb".
            timeout:          HTTP timeout in seconds.

        Returns:
            dict with keys: job_id, mesh_path, format, elapsed_seconds
            On error: dict with key "error".
        """
        if not os.path.exists(image_path):
            return {"error": f"Image file not found: {image_path}"}

        # Build query string
        params = (
            f"remove_bg={'true' if remove_bg else 'false'}"
            f"&foreground_ratio={foreground_ratio}"
            f"&mc_resolution={mc_resolution}"
            f"&output_format={output_format}"
        )
        url = f"{self.base_url}/generate/json?{params}"

        # Build multipart/form-data body
        boundary = uuid.uuid4().hex
        filename = os.path.basename(image_path)

        with open(image_path, "rb") as f:
            file_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n"
            f"\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace") if e.fp else str(e)
            return {"error": f"HTTP {e.code}: {detail}"}
        except urllib.error.URLError as e:
            return {"error": f"Connection failed: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}


class TripoCloudClient:
    """Synchronous client for the Tripo cloud API (v2 endpoint)."""

    BASE_URL = "https://api.tripo3d.ai/v2/openapi"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, body: Optional[bytes] = None,
                 headers: Optional[dict] = None, timeout: float = 15.0) -> dict:
        """Make an authenticated request and return parsed JSON."""
        url = f"{self.BASE_URL}{path}"
        hdrs = {"Authorization": f"Bearer {self.api_key}"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    # ------------------------------------------------------------------
    # Health / balance
    # ------------------------------------------------------------------
    def is_ready(self, timeout: float = 5.0) -> bool:
        """Return True if the API key is valid (balance check succeeds)."""
        try:
            data = self._request("GET", "/user/balance", timeout=timeout)
            return data.get("code") == 0
        except Exception:
            return False

    def health(self, timeout: float = 5.0) -> dict:
        """Return balance info or an error dict."""
        try:
            data = self._request("GET", "/user/balance", timeout=timeout)
            if data.get("code") == 0:
                bal = data.get("data", {})
                return {
                    "status": "ready",
                    "balance": bal.get("balance", 0),
                    "frozen": bal.get("frozen", 0),
                }
            return {"status": "error", "detail": data.get("message", "unknown")}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    # ------------------------------------------------------------------
    # Upload image → image_token
    # ------------------------------------------------------------------
    def _upload_image(self, image_path: str, timeout: float = 30.0) -> str:
        """Upload an image file and return the image_token."""
        boundary = uuid.uuid4().hex
        filename = os.path.basename(image_path)

        with open(image_path, "rb") as f:
            file_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n"
            f"\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

        url = f"{self.BASE_URL}/upload"
        req = urllib.request.Request(
            url, data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())

        if data.get("code") != 0:
            raise RuntimeError(f"Upload failed: {data.get('message', data)}")
        return data["data"]["image_token"]

    # ------------------------------------------------------------------
    # Create task
    # ------------------------------------------------------------------
    def _create_task(
        self,
        image_token: str,
        model_version: str = "v2.5-20250123",
        texture: bool = True,
        pbr: bool = True,
        face_limit: int = 50000,
        timeout: float = 15.0,
    ) -> str:
        """Submit an image_to_model task and return the task_id."""
        payload = {
            "type": "image_to_model",
            "file": {"type": "image", "file_token": image_token},
            "model_version": model_version,
            "texture": texture,
            "pbr": pbr,
            "face_limit": face_limit,
        }
        body = json.dumps(payload).encode()
        data = self._request(
            "POST", "/task",
            body=body,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        if data.get("code") != 0:
            raise RuntimeError(f"Task creation failed: {data.get('message', data)}")
        return data["data"]["task_id"]

    # ------------------------------------------------------------------
    # Poll task until completion
    # ------------------------------------------------------------------
    def _poll_task(
        self,
        task_id: str,
        poll_interval: float = 3.0,
        timeout: float = 300.0,
    ) -> dict:
        """Poll until the task succeeds or fails. Returns the task data dict."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data = self._request("GET", f"/task/{task_id}", timeout=15.0)
            if data.get("code") != 0:
                raise RuntimeError(f"Poll error: {data.get('message', data)}")

            task_data = data["data"]
            status = task_data.get("status")

            if status == "success":
                return task_data
            if status in ("failed", "cancelled", "unknown"):
                raise RuntimeError(f"Task {task_id} {status}: {task_data}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

    # ------------------------------------------------------------------
    # Download output file
    # ------------------------------------------------------------------
    def _download_file(self, url: str, dest_path: str, timeout: float = 60.0) -> str:
        """Download a file from a URL to a local path."""
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        return dest_path

    # ------------------------------------------------------------------
    # Generate (full pipeline)
    # ------------------------------------------------------------------
    def generate(
        self,
        image_path: str,
        model_version: str = "v2.5-20250123",
        texture: bool = True,
        pbr: bool = True,
        face_limit: int = 50000,
        poll_interval: float = 3.0,
        timeout: float = 300.0,
    ) -> dict:
        """
        Full pipeline: upload → create task → poll → download GLB.

        Returns dict matching TripoSRClient.generate() shape:
            {mesh_path, job_id, elapsed_seconds, format}
        On error: {error}.
        """
        if not os.path.exists(image_path):
            return {"error": f"Image file not found: {image_path}"}
        if not self.api_key:
            return {"error": "No API key configured"}

        t0 = time.monotonic()
        try:
            image_token = self._upload_image(image_path)
            task_id = self._create_task(
                image_token,
                model_version=model_version,
                texture=texture,
                pbr=pbr,
                face_limit=face_limit,
            )
            task_data = self._poll_task(task_id, poll_interval=poll_interval, timeout=timeout)

            # Extract the model download URL from rendered output
            output = task_data.get("output", {})
            model_url = output.get("pbr_model") or output.get("model")
            if not model_url:
                return {"error": f"No model URL in task output: {output}"}

            # Download to temp dir
            out_dir = os.path.join(tempfile.gettempdir(), "tripo_cloud", task_id)
            dest = os.path.join(out_dir, "model.glb")
            self._download_file(model_url, dest)

            elapsed = round(time.monotonic() - t0, 1)
            return {
                "mesh_path": dest,
                "job_id": task_id,
                "elapsed_seconds": elapsed,
                "format": "glb",
            }

        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace") if e.fp else str(e)
            return {"error": f"HTTP {e.code}: {detail}"}
        except urllib.error.URLError as e:
            return {"error": f"Connection failed: {e.reason}"}
        except (RuntimeError, TimeoutError) as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}
