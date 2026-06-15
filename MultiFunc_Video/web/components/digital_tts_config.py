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
            options=["local", "comfyui", "gpt_sovits"],
            index=["local", "comfyui", "gpt_sovits"].index(tts_config.get("inference_mode", "local")),
            horizontal=True,
            format_func=lambda x: tr(f"tts.mode.{x}")
        )
        
        # Show hint based on mode
        if tts_mode == "local":
            st.caption(tr("tts.mode.local_hint"))
        elif tts_mode == "comfyui":
            st.caption(tr("tts.mode.comfyui_hint"))
        else:
            st.caption(tr("tts.mode.gpt_sovits_hint"))
        
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
            # GPT-SoVITS variables (not used in this mode)
            sovits_project_path = ""
            sovits_api_url = "http://127.0.0.1:9880"
            sovits_ref_audio_path = None
            sovits_prompt_text = ""
            sovits_prompt_lang = "zh"
            sovits_text_lang = "zh"
        
        # ================================================================
        # ComfyUI Mode UI
        # ================================================================
        elif tts_mode == "comfyui":
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
            # GPT-SoVITS variables (not used in this mode)
            sovits_project_path = ""
            sovits_api_url = "http://127.0.0.1:9880"
            sovits_ref_audio_path = None
            sovits_prompt_text = ""
            sovits_prompt_lang = "zh"
            sovits_text_lang = "zh"
        
        # ================================================================
        # GPT-SoVITS Mode UI
        # ================================================================
        elif tts_mode == "gpt_sovits":
            sovits_config = tts_config.get("gpt_sovits", {})
            
            # Auto-start hint
            st.info(tr("tts.sovits.auto_start_hint"))
            
            # ---- Project path with folder browser ----
            saved_project_path = sovits_config.get("project_path", "")
            project_path_key = f"{key_prefix}_sovits_project_path"
            sovits_project_path = cached_text_input(
                tr("tts.sovits.project_path"),
                key=project_path_key,
                default=saved_project_path,
                help=tr("tts.sovits.project_path_help")
            )
            
            # Folder browser
            with st.expander("📁 " + tr("tts.sovits.browse_folder")):
                browser_dir_key = f"{key_prefix}_sovits_browser_dir"
                # Initialize browser dir to project path parent or D:/
                if browser_dir_key not in st.session_state:
                    if sovits_project_path and os.path.isdir(sovits_project_path):
                        st.session_state[browser_dir_key] = sovits_project_path
                    else:
                        st.session_state[browser_dir_key] = "D:/"
                
                current_browser_dir = st.session_state[browser_dir_key]
                st.code(current_browser_dir, language=None)
                
                # Navigation buttons
                fb_col1, fb_col2 = st.columns(2)
                with fb_col1:
                    parent_dir = str(Path(current_browser_dir).parent)
                    if parent_dir != current_browser_dir and os.path.isdir(parent_dir):
                        if st.button("⬆️ " + tr("tts.sovits.parent_dir"), key=f"{key_prefix}_sovits_up", use_container_width=True):
                            st.session_state[browser_dir_key] = parent_dir
                            st.rerun()
                with fb_col2:
                    if st.button("✅ " + tr("tts.sovits.select_this_folder"), key=f"{key_prefix}_sovits_pick_dir", type="primary", use_container_width=True):
                        from web.state.cache import set as cache_set
                        cache_set(project_path_key, current_browser_dir)
                        st.rerun()
                
                # List subdirectories as selectbox
                try:
                    entries = sorted(os.listdir(current_browser_dir))
                    dirs = [d for d in entries if os.path.isdir(os.path.join(current_browser_dir, d)) and not d.startswith('.')]
                    
                    if dirs:
                        selected_subdir = st.selectbox(
                            tr("tts.sovits.subdirectories"),
                            options=dirs,
                            key=f"{key_prefix}_sovits_dir_select"
                        )
                        if st.button("📂 " + tr("tts.sovits.enter_directory"), key=f"{key_prefix}_sovits_enter_dir", use_container_width=True):
                            st.session_state[browser_dir_key] = os.path.join(current_browser_dir, selected_subdir)
                            st.rerun()
                    else:
                        st.caption(tr("tts.sovits.no_subdirectories"))
                except (PermissionError, OSError) as e:
                    st.error(f"❌ {e}")
            
            # ---- API URL ----
            saved_api_url = sovits_config.get("api_url", "http://127.0.0.1:9880")
            sovits_api_url = cached_text_input(
                tr("tts.sovits.api_url"),
                key=f"{key_prefix}_sovits_api_url",
                default=saved_api_url,
                help=tr("tts.sovits.api_url_help")
            )
            
            # ---- Reference audio (file_uploader, same as PPT/PDF upload) ----
            sovits_ref_audio_upload_key = f"{key_prefix}_sovits_ref_audio_upload"
            sovits_ref_audio_file = st.file_uploader(
                tr("tts.sovits.ref_audio"),
                type=["mp3", "wav", "flac", "m4a", "aac", "ogg"],
                help=tr("tts.sovits.ref_audio_help"),
                key=sovits_ref_audio_upload_key
            )

            # Persist uploaded reference audio and restore cached files on restart
            sovits_ref_audio_path = None
            if sovits_ref_audio_file is not None:
                # Audio preview player
                st.audio(sovits_ref_audio_file)

                # Save to persistent cache
                cached_paths = cache_uploaded_files(
                    sovits_ref_audio_upload_key,
                    sovits_ref_audio_file if isinstance(sovits_ref_audio_file, list) else [sovits_ref_audio_file]
                )
                if cached_paths:
                    sovits_ref_audio_path = Path(cached_paths[0])
            else:
                cached_paths = get_cached_file_paths(sovits_ref_audio_upload_key)
                if cached_paths:
                    sovits_ref_audio_path = Path(cached_paths[0])
                    st.info(f"🔊 {tr('cache.using_cached_ref_audio')}: {sovits_ref_audio_path.name}")
                    st.audio(str(sovits_ref_audio_path))
                    if st.button(tr("cache.clear_ref_audio"), key=f"clear_{sovits_ref_audio_upload_key}"):
                        clear_cached_files(sovits_ref_audio_upload_key)
                        st.rerun()
            
            # ---- Reference audio text and language (two columns) ----
            lang_col1, lang_col2 = st.columns([1, 1])
            
            with lang_col1:
                sovits_prompt_text = cached_text_input(
                    tr("tts.sovits.prompt_text"),
                    key=f"{key_prefix}_sovits_prompt_text",
                    default="",
                    help=tr("tts.sovits.prompt_text_help")
                )
            
            with lang_col2:
                lang_options = {
                    "zh": "中文",
                    "en": "英文",
                    "ja": "日文",
                    "ko": "韩文",
                    "yue": "粤语",
                    "auto": "自动检测",
                }
                saved_prompt_lang = sovits_config.get("prompt_lang", "zh")
                sovits_prompt_lang = cached_selectbox(
                    tr("tts.sovits.prompt_lang"),
                    key=f"{key_prefix}_sovits_prompt_lang",
                    options=list(lang_options.keys()),
                    format_func=lambda x: lang_options[x],
                    index=list(lang_options.keys()).index(
                        saved_prompt_lang if saved_prompt_lang in lang_options else "zh"
                    ),
                )
                
                # Synthesis language
                saved_text_lang = sovits_config.get("text_lang", "zh")
                sovits_text_lang = cached_selectbox(
                    tr("tts.sovits.text_lang"),
                    key=f"{key_prefix}_sovits_text_lang",
                    options=list(lang_options.keys()),
                    format_func=lambda x: lang_options[x],
                    index=list(lang_options.keys()).index(
                        saved_text_lang if saved_text_lang in lang_options else "zh"
                    ),
                )
            
            # Speed slider
            saved_speed = sovits_config.get("speed_factor", 1.0)
            tts_speed = cached_slider(
                tr("tts.speed"),
                key=f"{key_prefix}_sovits_speed",
                min_value=0.5,
                max_value=2.0,
                value=saved_speed,
                step=0.1,
                format="%.1fx"
            )
            st.caption(tr("tts.speed_label", speed=f"{tts_speed:.1f}"))
            
            # Variables for video generation
            selected_voice = None
            tts_workflow_key = None
            ref_audio_path = None  # Not used for sovits mode
        
        # ================================================================
        # TTS Preview (works for all modes)
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
                        elif tts_mode == "comfyui":
                            tts_params["workflow"] = tts_workflow_key
                            if ref_audio_path:
                                tts_params["ref_audio"] = str(ref_audio_path)
                        elif tts_mode == "gpt_sovits":
                            tts_params["speed"] = tts_speed
                            tts_params["gpt_sovits_project_path"] = sovits_project_path
                            tts_params["gpt_sovits_api_url"] = sovits_api_url
                            if sovits_ref_audio_path:
                                tts_params["gpt_sovits_ref_audio"] = str(sovits_ref_audio_path)
                            tts_params["gpt_sovits_prompt_text"] = sovits_prompt_text
                            tts_params["gpt_sovits_prompt_lang"] = sovits_prompt_lang
                            tts_params["gpt_sovits_text_lang"] = sovits_text_lang
                        
                        audio_path = run_async(multifunc_video.tts(**tts_params))
                        
                        # Play the audio
                        if audio_path:
                            st.success(tr("tts.preview_success"))
                            if os.path.exists(audio_path):
                                # Determine audio format from file extension
                                ext = os.path.splitext(audio_path)[1].lower()
                                audio_format = "audio/wav" if ext == ".wav" else "audio/mp3"
                                st.audio(audio_path, format=audio_format)
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
    
    # Return all style configuration parameters
    result = {
        "tts_inference_mode": tts_mode,
        "tts_voice": selected_voice if tts_mode == "local" else None,
        "tts_speed": tts_speed if tts_mode in ("local", "gpt_sovits") else None,
        "tts_workflow": tts_workflow_key if tts_mode == "comfyui" else None,
        "ref_audio": str(ref_audio_path) if ref_audio_path else None,
    }
    
    # Add GPT-SoVITS specific parameters
    if tts_mode == "gpt_sovits":
        result.update({
            "gpt_sovits_project_path": sovits_project_path,
            "gpt_sovits_api_url": sovits_api_url,
            "gpt_sovits_ref_audio": str(sovits_ref_audio_path) if sovits_ref_audio_path else None,
            "gpt_sovits_prompt_text": sovits_prompt_text,
            "gpt_sovits_prompt_lang": sovits_prompt_lang,
            "gpt_sovits_text_lang": sovits_text_lang,
        })
    
    return result