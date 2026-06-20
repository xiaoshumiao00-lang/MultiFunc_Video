# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
GPU memory cleanup utilities.

Provides one-click release of VRAM occupied by:
- The current Python process (torch CUDA cache)
- Local ComfyUI instance (via /free endpoint)
- Local Ollama instance (via /api/generate keep_alive=0)
"""

import shutil
import subprocess
import time
from typing import Dict, List, Optional

import requests
from loguru import logger


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_PROCESS_NAMES = ["ollama.exe", "llama-server.exe"]


def _normalize_url(url: Optional[str]) -> Optional[str]:
    """Strip trailing slashes and whitespace from a URL."""
    if not url:
        return None
    url = url.strip()
    while url.endswith("/"):
        url = url[:-1]
    return url or None


def get_gpu_memory_info() -> Dict:
    """Return current GPU memory usage via nvidia-smi."""
    result = {"available": False, "used_mb": 0, "total_mb": 0, "error": ""}
    if not shutil.which("nvidia-smi"):
        result["error"] = "nvidia-smi not found"
        return result

    try:
        output = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if output.returncode != 0:
            result["error"] = output.stderr.strip() or "nvidia-smi failed"
            return result

        line = output.stdout.strip().splitlines()[0]
        used, total = line.split(",")
        result["available"] = True
        result["used_mb"] = int(used.strip())
        result["total_mb"] = int(total.strip())
    except Exception as e:
        result["error"] = f"Failed to query GPU memory: {e}"
        logger.warning(result["error"])
    return result


def get_gpu_compute_processes() -> List[Dict]:
    """Return list of GPU compute processes via nvidia-smi."""
    processes: List[Dict] = []
    if not shutil.which("nvidia-smi"):
        return processes

    try:
        output = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,process_name,used_gpu_memory",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if output.returncode != 0:
            return processes

        for line in output.stdout.strip().splitlines():
            parts = line.split(", ")
            if len(parts) >= 3:
                processes.append({
                    "pid": parts[0].strip(),
                    "name": parts[1].strip(),
                    "memory": parts[2].strip(),
                })
    except Exception as e:
        logger.warning(f"Failed to query GPU compute processes: {e}")
    return processes


def clear_torch_cache() -> Dict:
    """Release CUDA memory held by the current Python process."""
    result = {"source": "torch", "success": False, "message": ""}
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            result["success"] = True
            result["message"] = "CUDA cache cleared"
        else:
            result["message"] = "CUDA not available"
    except Exception as e:
        result["message"] = f"torch cleanup failed: {e}"
        logger.warning(result["message"])
    return result


def clear_comfyui_memory(comfyui_url: Optional[str], api_key: Optional[str] = None) -> Dict:
    """Ask a local ComfyUI server to unload models and free memory."""
    result = {"source": "comfyui", "success": False, "message": ""}
    url = _normalize_url(comfyui_url)
    if not url:
        result["message"] = "ComfyUI URL not configured"
        return result

    free_endpoint = f"{url}/free"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {"unload_models": True, "free_memory": True}
    try:
        response = requests.post(free_endpoint, json=payload, headers=headers, timeout=10)
        if response.status_code in (200, 204):
            result["success"] = True
            result["message"] = "ComfyUI models unloaded and memory freed"
        else:
            result["message"] = f"ComfyUI returned {response.status_code}: {response.text[:200]}"
    except requests.exceptions.ConnectionError:
        result["message"] = f"Cannot connect to ComfyUI at {url}"
    except Exception as e:
        result["message"] = f"ComfyUI cleanup failed: {e}"
        logger.warning(result["message"])
    return result


def _list_ollama_models(base_url: str) -> List[str]:
    """Return currently loaded Ollama model names from /api/ps."""
    try:
        response = requests.get(f"{base_url}/api/ps", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            return [m.get("name", m.get("model", "")) for m in models if m.get("name") or m.get("model")]
    except Exception as e:
        logger.debug(f"Failed to list Ollama running models: {e}")
    return []


def kill_ollama_servers() -> Dict:
    """
    Forcefully terminate Ollama-related GPU processes.

    This is a last-resort option for cases where the Ollama API is unreachable
    (e.g. the service crashed but llama-server processes are still holding VRAM).
    Returns a result dict with terminated PIDs and any failures.
    """
    result = {"source": "ollama_force_kill", "success": False, "message": ""}
    terminated = []
    failed = []

    for proc_name in OLLAMA_PROCESS_NAMES:
        try:
            output = subprocess.run(
                ["taskkill", "/F", "/IM", proc_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if output.returncode == 0:
                terminated.append(proc_name)
            elif "not found" in (output.stderr or "").lower() or output.returncode == 128:
                # Process not running is fine
                pass
            else:
                failed.append(f"{proc_name}: {output.stderr.strip() or output.stdout.strip()}")
        except Exception as e:
            failed.append(f"{proc_name}: {e}")

    if terminated and not failed:
        result["success"] = True
        result["message"] = f"Terminated: {', '.join(terminated)}"
    elif terminated:
        result["success"] = True
        result["message"] = f"Terminated: {', '.join(terminated)}; failed: {', '.join(failed)}"
    elif failed:
        result["message"] = f"Failed: {', '.join(failed)}"
    else:
        result["success"] = True
        result["message"] = "No Ollama processes found"

    return result


def clear_ollama_memory(ollama_base_url: Optional[str] = None) -> Dict:
    """
    Unload all currently loaded Ollama models by sending keep_alive=0.

    Uses the default Ollama URL unless a custom one is provided.
    Waits briefly after unloading so the llama-server can release VRAM.
    """
    result = {"source": "ollama", "success": False, "message": ""}
    base_url = _normalize_url(ollama_base_url) or DEFAULT_OLLAMA_URL

    try:
        models = _list_ollama_models(base_url)
        if not models:
            result["success"] = True
            result["message"] = "No Ollama models currently loaded"
            return result

        unloaded = []
        failed = []
        for model in models:
            try:
                resp = requests.post(
                    f"{base_url}/api/generate",
                    json={"model": model, "prompt": "", "keep_alive": 0},
                    timeout=10,
                )
                if resp.status_code == 200:
                    unloaded.append(model)
                else:
                    failed.append(f"{model} ({resp.status_code})")
            except Exception as e:
                failed.append(f"{model} ({e})")

        # Give Ollama a moment to actually release VRAM
        if unloaded:
            time.sleep(2)

        if unloaded and not failed:
            result["success"] = True
            result["message"] = f"Unloaded models: {', '.join(unloaded)}"
        elif unloaded:
            result["success"] = True
            result["message"] = f"Partially unloaded: {', '.join(unloaded)}; failed: {', '.join(failed)}"
        else:
            result["message"] = f"Failed to unload models: {', '.join(failed)}"
    except requests.exceptions.ConnectionError:
        result["message"] = f"Cannot connect to Ollama at {base_url}"
    except Exception as e:
        result["message"] = f"Ollama cleanup failed: {e}"
        logger.warning(result["message"])
    return result


def clear_gpu_memory(
    comfyui_url: Optional[str] = None,
    comfyui_api_key: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
    force_kill_ollama: bool = False,
) -> Dict:
    """
    Release GPU memory from all known sources.

    Returns a summary dict with per-source results, before/after GPU memory
    usage, and the list of remaining GPU compute processes.
    """
    before = get_gpu_memory_info()
    processes_before = get_gpu_compute_processes()

    results = []

    # 1. Current process torch cache
    results.append(clear_torch_cache())

    # 2. ComfyUI
    results.append(clear_comfyui_memory(comfyui_url, comfyui_api_key))

    # 3. Ollama
    results.append(clear_ollama_memory(ollama_base_url))

    # 4. Force kill Ollama processes if requested (e.g. API unreachable)
    if force_kill_ollama:
        results.append(kill_ollama_servers())

    # Allow ComfyUI/Ollama a bit more time to finish releasing memory
    time.sleep(1)

    after = get_gpu_memory_info()
    processes_after = get_gpu_compute_processes()

    success_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - success_count

    if failed_count == 0:
        overall = "success"
    elif success_count > 0:
        overall = "partial"
    else:
        overall = "failed"

    return {
        "overall": overall,
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results,
        "before": before,
        "after": after,
        "processes_before": processes_before,
        "processes_after": processes_after,
    }
