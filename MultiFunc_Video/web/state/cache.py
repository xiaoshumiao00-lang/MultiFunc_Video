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
UI state cache for web UI

Persists user inputs (text, selections, sliders, uploaded files) across
Streamlit sessions. Data is stored under `.workbuddy/cache/` so that inputs
survive server restarts.
"""

import json
import shutil
from pathlib import Path
from typing import Any, List, Optional

import streamlit as st
from loguru import logger


CACHE_DIR = Path(".workbuddy/cache")
STATE_FILE = CACHE_DIR / "ui_state.json"
UPLOAD_DIR = CACHE_DIR / "uploads"

_STATE_CACHE_KEY_PREFIX = "cache_"


def _ensure_dirs() -> None:
    """Ensure cache directories exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    """Load persisted UI state from disk."""
    _ensure_dirs()
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as e:
        logger.warning(f"Failed to load UI cache: {e}")
        return {}


def save_state(state: dict) -> None:
    """Persist UI state to disk."""
    _ensure_dirs()
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save UI cache: {e}")


def _session_key(key: str) -> str:
    """Key used in st.session_state for cached values."""
    return f"{_STATE_CACHE_KEY_PREFIX}{key}"


def get(key: str, default: Any = None) -> Any:
    """
    Get cached value. Priority:
    1. Current session state (fastest during rerun)
    2. Persisted cache file
    3. Provided default
    """
    session_key = _session_key(key)
    if session_key in st.session_state:
        return st.session_state[session_key]
    return load_state().get(key, default)


def set(key: str, value: Any) -> None:
    """Cache a value both in session state and on disk."""
    st.session_state[_session_key(key)] = value
    state = load_state()
    state[key] = value
    save_state(state)


def delete(key: str) -> None:
    """Remove a cached key."""
    session_key = _session_key(key)
    if session_key in st.session_state:
        del st.session_state[session_key]
    state = load_state()
    if key in state:
        del state[key]
        save_state(state)


def clear_all() -> None:
    """Clear all cached UI state and uploaded files."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    for k in list(st.session_state.keys()):
        if k.startswith(_STATE_CACHE_KEY_PREFIX):
            del st.session_state[k]
    logger.info("UI cache cleared")


def load_state_into_session() -> None:
    """Load persisted cache values into session state at startup."""
    state = load_state()
    for key, value in state.items():
        session_key = _session_key(key)
        if session_key not in st.session_state:
            st.session_state[session_key] = value
    logger.debug(f"Loaded {len(state)} cached UI values into session state")


# =============================================================================
# Uploaded file persistence
# =============================================================================


def cache_uploaded_files(key: str, uploaded_files) -> List[str]:
    """
    Persist uploaded files to `.workbuddy/cache/uploads/<key>/`.

    Args:
        key: Widget/cache namespace.
        uploaded_files: List of Streamlit UploadedFile objects.

    Returns:
        List of absolute paths to persisted files.
    """
    if not uploaded_files:
        return []

    target_dir = UPLOAD_DIR / key
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for uploaded_file in uploaded_files:
        dest = target_dir / uploaded_file.name
        with open(dest, "wb") as f:
            f.write(uploaded_file.getbuffer())
        paths.append(str(dest.absolute()))

    set(f"{key}_paths", paths)
    logger.info(f"Cached {len(paths)} uploaded file(s) for '{key}'")
    return paths


def get_cached_file_paths(key: str) -> List[str]:
    """
    Return cached file paths for a given key, syncing with disk.
    Only returns paths that still exist.
    """
    target_dir = UPLOAD_DIR / key
    if not target_dir.exists():
        return []
    paths = sorted(
        str(p.absolute())
        for p in target_dir.iterdir()
        if p.is_file() and p.exists()
    )
    set(f"{key}_paths", paths)
    return paths


def clear_cached_files(key: str) -> None:
    """Remove persisted files for a single key."""
    target_dir = UPLOAD_DIR / key
    if target_dir.exists():
        shutil.rmtree(target_dir)
    delete(f"{key}_paths")


def has_cached_files(key: str) -> bool:
    """Check whether persisted files exist for a key."""
    target_dir = UPLOAD_DIR / key
    return target_dir.exists() and any(target_dir.iterdir())


# =============================================================================
# Streamlit widget helpers
# =============================================================================


def _make_on_change(key: str):
    """Build an on_change callback that persists the widget value."""
    def callback():
        set(key, st.session_state[key])
    return callback


def cached_text_input(label: str, key: str, default: str = "", **kwargs) -> str:
    """Text input with persisted default value."""
    value = get(key, default)
    return st.text_input(
        label,
        value=value,
        key=key,
        on_change=_make_on_change(key),
        **kwargs
    )


def cached_text_area(label: str, key: str, default: str = "", **kwargs) -> str:
    """Text area with persisted default value."""
    value = get(key, default)
    return st.text_area(
        label,
        value=value,
        key=key,
        on_change=_make_on_change(key),
        **kwargs
    )


def cached_selectbox(label: str, key: str, options: List[Any], index: int = 0, **kwargs) -> Any:
    """Selectbox with persisted default selection."""
    cached = get(key, None)
    if cached in options:
        idx = options.index(cached)
    else:
        idx = index
    return st.selectbox(
        label,
        options,
        index=idx,
        key=key,
        on_change=_make_on_change(key),
        **kwargs
    )


def cached_radio(label: str, key: str, options: List[Any], index: int = 0, **kwargs) -> Any:
    """Radio with persisted default selection."""
    cached = get(key, None)
    if cached in options:
        idx = options.index(cached)
    else:
        idx = index
    return st.radio(
        label,
        options,
        index=idx,
        key=key,
        on_change=_make_on_change(key),
        **kwargs
    )


def cached_slider(label: str, key: str, min_value, max_value, value, **kwargs):
    """Slider with persisted default value."""
    cached = get(key, value)
    try:
        cached = max(min_value, min(max_value, cached))
    except Exception:
        cached = value
    return st.slider(
        label,
        min_value=min_value,
        max_value=max_value,
        value=cached,
        key=key,
        on_change=_make_on_change(key),
        **kwargs
    )


def cached_number_input(label: str, key: str, min_value=None, max_value=None, value=None, **kwargs):
    """Number input with persisted default value."""
    cached = get(key, value)
    try:
        if min_value is not None:
            cached = max(min_value, cached)
        if max_value is not None:
            cached = min(max_value, cached)
    except Exception:
        cached = value
    return st.number_input(
        label,
        min_value=min_value,
        max_value=max_value,
        value=cached,
        key=key,
        on_change=_make_on_change(key),
        **kwargs
    )


def cached_checkbox(label: str, key: str, value: bool = False, **kwargs) -> bool:
    """Checkbox with persisted default value."""
    cached = get(key, value)
    return st.checkbox(
        label,
        value=cached,
        key=key,
        on_change=_make_on_change(key),
        **kwargs
    )


def cached_color_picker(label: str, key: str, default: str = "#000000", **kwargs) -> str:
    """Color picker with persisted default value."""
    value = get(key, default)
    return st.color_picker(
        label,
        value=value,
        key=key,
        on_change=_make_on_change(key),
        **kwargs
    )
