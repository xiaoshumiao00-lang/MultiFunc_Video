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

from typing import Dict, List, Optional

import requests
from loguru import logger


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def _normalize_url(url: Optional[str]) -> Optional[str]:
    """Strip trailing slashes and whitespace from a URL."""
    if not url:
        return None
    url = url.strip()
    while url.endswith("/"):
        url = url[:-1]
    return url or None


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


def clear_ollama_memory(ollama_base_url: Optional[str] = None) -> Dict:
    """
    Unload all currently loaded Ollama models by sending keep_alive=0.

    If the configured LLM is not obviously an Ollama endpoint, we still try the
    default Ollama URL as a best-effort cleanup.
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
) -> Dict:
    """
    Release GPU memory from all known sources.

    Returns a summary dict with per-source results and an overall status.
    """
    results = []

    # 1. Current process torch cache
    results.append(clear_torch_cache())

    # 2. ComfyUI
    results.append(clear_comfyui_memory(comfyui_url, comfyui_api_key))

    # 3. Ollama
    results.append(clear_ollama_memory(ollama_base_url))

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
    }
