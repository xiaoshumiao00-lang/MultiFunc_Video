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
Style configuration components for web UI (middle column)
"""

import os
from pathlib import Path

import streamlit as st
from loguru import logger

from web.i18n import tr, get_language
from web.state.cache import (
    cached_radio,
    cached_selectbox,
    cached_slider,
    cached_text_input,
    cache_uploaded_files,
    get_cached_file_paths,
    clear_cached_files,
)
from web.utils.async_helpers import run_async
from multifunc_video.config import config_manager


def render_style_config(multifunc_video, key_prefix: str = "digital"):
    """Render style configuration section (middle column)
    
    Args:
        multifunc_video: MultiFuncVideo service instance
        key_prefix: Prefix for Streamlit widget keys to avoid collisions
                    when multiple pipelines render this component on the same page.
    """
    # TTS Section (moved from left column)
    # ====================================================================
    with st.container(border=True):
        st.markdown(f"**{tr('section.tts')}**")
        
        with st.expander(tr("help.feature_description"), expanded=False):
            st.markdown(f"**{tr('help.what')}**")
            st.markdown(tr("tts.what"))
            st.markdown(f"**{tr('help.how')}**")
            st.markdown(tr("tts.how"))
        
        # Get TTS config
        comfyui_config = config_manager.get_comfyui_config()
        tts_config = comfyui_config["tts"]
        
        # Inference mode selection
        tts_mode = cached_radio(
            tr("tts.inference_mode"),
            key=f"{key_prefix}_tts_inference_mode",
            options=["local", "comfyui"],
            index=0 if tts_config.get("inference_mode", "local") == "local" else 1,
            horizontal=True,
            format_func=lambda x: tr(f"tts.mode.{x}")
        )
        
        # Show hint based on mode
        if tts_mode == "local":
            st.caption(tr("tts.mode.local_hint"))
        else:
            st.caption(tr("tts.mode.comfyui_hint"))
        
        # ================================================================
        # Local Mode UI
        # ================================================================
        if tts_mode == "local":
            # Import voice configuration
            from multifunc_video.tts_voices import EDGE_TTS_VOICES, get_voice_display_name
            
            # Get saved voice from config
            local_config = tts_config.get("local", {})
            saved_voice = local_config.get("voice", "zh-CN-YunjianNeural")
            saved_speed = local_config.get("speed", 1.2)
            
            # Build voice options with i18n
            voice_options = []
            voice_ids = []
            default_voice_index = 0
            
            for idx, voice_config in enumerate(EDGE_TTS_VOICES):
                voice_id = voice_config["id"]
                display_name = get_voice_display_name(voice_id, tr, get_language())
                voice_options.append(display_name)
                voice_ids.append(voice_id)
                
                # Set default index if matches saved voice
                if voice_id == saved_voice:
                    default_voice_index = idx
            
            # Two-column layout: Voice | Speed
            voice_col, speed_col = st.columns([1, 1])
            
            with voice_col:
                # Voice selector
                selected_voice_display = cached_selectbox(
                    tr("tts.voice_selector"),
                    key=f"{key_prefix}_tts_local_voice",
                    options=voice_options,
                    index=default_voice_index
                )

                # Get actual voice ID
                selected_voice_index = voice_options.index(selected_voice_display)
                selected_voice = voice_ids[selected_voice_index]

            with speed_col:
                # Speed slider
                tts_speed = cached_slider(
                    tr("tts.speed"),
                    key=f"{key_prefix}_tts_local_speed",
                    min_value=0.5,
                    max_value=2.0,
                    value=saved_speed,
                    step=0.1,
                    format="%.1fx"
                )
                st.caption(tr("tts.speed_label", speed=f"{tts_speed:.1f}"))
            
            # Variables for video generation
            tts_workflow_key = None
            ref_audio_path = None
        
        # ================================================================
        # ComfyUI Mode UI
        # ================================================================
        else:  # comfyui mode
            # Workflow source selection (runninghub / selfhost)
            source_options = {
                "runninghub": tr("asset_based.source.runninghub"),
                "selfhost": tr("asset_based.source.selfhost")
            }

            has_runninghub = bool(comfyui_config.get("runninghub_api_key"))
            has_selfhost = bool(comfyui_config.get("comfyui_url"))

            if has_runninghub:
                default_source_index = 0
            elif has_selfhost:
                default_source_index = 1
            else:
                default_source_index = 0

            tts_workflow_source = cached_radio(
                tr("tts.workflow_source"),
                key=f"{key_prefix}_tts_workflow_source",
                options=list(source_options.keys()),
                format_func=lambda x: source_options[x],
                index=default_source_index,
                horizontal=True
            )

            # Show warning if selected source is not configured
            if tts_workflow_source == "runninghub" and not has_runninghub:
                st.warning(tr("asset_based.source.runninghub_not_configured"))
            elif tts_workflow_source == "selfhost" and not has_selfhost:
                st.warning(tr("asset_based.source.selfhost_not_configured"))

            # List available TTS workflows for selected source
            try:
                all_workflows = multifunc_video.tts.list_workflows()
                source_workflows = [wf for wf in all_workflows if wf["source"] == tts_workflow_source]
            except Exception as e:
                logger.warning(f"Failed to list TTS workflows: {e}")
                source_workflows = []

            tts_workflow_key = None
            if source_workflows:
                workflow_options = {wf["key"]: wf["display_name"] for wf in source_workflows}
                comfyui_default_workflow = tts_config.get("comfyui", {}).get("default_workflow")

                # Prefer configured default if it belongs to the selected source
                if comfyui_default_workflow in workflow_options:
                    default_workflow_key = comfyui_default_workflow
                else:
                    default_workflow_key = source_workflows[0]["key"]

                default_index = list(workflow_options.keys()).index(default_workflow_key)

                tts_workflow_key = cached_selectbox(
                    tr("tts.selector"),
                    key=f"{key_prefix}_tts_workflow_select",
                    options=list(workflow_options.keys()),
                    format_func=lambda x: workflow_options[x],
                    index=default_index
                )
            else:
                st.warning(
                    tr("tts.no_workflow_for_source", source=source_options[tts_workflow_source])
                )

            # Reference audio upload (optional, for voice cloning)
            ref_audio_upload_key = f"{key_prefix}_ref_audio_upload"
            ref_audio_file = st.file_uploader(
                tr("tts.ref_audio"),
                type=["mp3", "wav", "flac", "m4a", "aac", "ogg"],
                help=tr("tts.ref_audio_help"),
                key=ref_audio_upload_key
            )

            # Persist uploaded reference audio and restore cached files on restart
            ref_audio_path = None
            if ref_audio_file is not None:
                # Audio preview player (directly play uploaded file)
                st.audio(ref_audio_file)

                # Save to persistent cache
                cached_paths = cache_uploaded_files(ref_audio_upload_key, ref_audio_file if isinstance(ref_audio_file, list) else [ref_audio_file])
                if cached_paths:
                    ref_audio_path = Path(cached_paths[0])
            else:
                cached_paths = get_cached_file_paths(ref_audio_upload_key)
                if cached_paths:
                    ref_audio_path = Path(cached_paths[0])
                    st.info(f"🔊 {tr('cache.using_cached_ref_audio')}: {ref_audio_path.name}")
                    st.audio(str(ref_audio_path))
                    if st.button(tr("cache.clear_ref_audio"), key=f"clear_{ref_audio_upload_key}"):
                        clear_cached_files(ref_audio_upload_key)
                        st.rerun()

            # Variables for video generation
            selected_voice = None
            tts_speed = None
        
        # ================================================================
        # TTS Preview (works for both modes)
        # ================================================================
        with st.expander(tr("tts.preview_title"), expanded=False):
            # Preview text input
            preview_text = cached_text_input(
                tr("tts.preview_text"),
                key=f"{key_prefix}_tts_preview_text",
                default="大家好，这是一段测试语音。",
                placeholder=tr("tts.preview_text_placeholder")
            )
            
            # Preview button
            if st.button(tr("tts.preview_button"), key=f"{key_prefix}_preview_tts", use_container_width=True):
                with st.spinner(tr("tts.previewing")):
                    try:
                        # Build TTS params based on mode
                        tts_params = {
                            "text": preview_text,
                            "inference_mode": tts_mode
                        }
                        
                        if tts_mode == "local":
                            tts_params["voice"] = selected_voice
                            tts_params["speed"] = tts_speed
                        else:  # comfyui
                            tts_params["workflow"] = tts_workflow_key
                            if ref_audio_path:
                                tts_params["ref_audio"] = str(ref_audio_path)
                        
                        audio_path = run_async(multifunc_video.tts(**tts_params))
                        
                        # Play the audio
                        if audio_path:
                            st.success(tr("tts.preview_success"))
                            if os.path.exists(audio_path):
                                st.audio(audio_path, format="audio/mp3")
                            elif audio_path.startswith('http'):
                                st.audio(audio_path)
                            else:
                                st.error("Failed to generate preview audio")
                            
                            # Show file path
                            st.caption(f"📁 {audio_path}")
                        else:
                            st.error("Failed to generate preview audio")
                    except Exception as e:
                        st.error(tr("tts.preview_failed", error=str(e)))
                        logger.exception(e)
    
    # Return all style configuration parameters (Simplified version only local TTS)
    return {
        "tts_inference_mode": tts_mode,
        "tts_voice": selected_voice if tts_mode == "local" else None,
        "tts_speed": tts_speed if tts_mode == "local" else None,
        "tts_workflow": tts_workflow_key if tts_mode == "comfyui" else None,
        "ref_audio": str(ref_audio_path) if ref_audio_path else None,
    }