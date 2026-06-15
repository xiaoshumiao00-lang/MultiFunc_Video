import os
import time
from pathlib import Path
from typing import Any

import streamlit as st
from loguru import logger

from web.i18n import tr, get_language
from web.pipelines.base import PipelineUI, register_pipeline_ui
from web.components.content_input import render_version_info
from web.components.digital_tts_config import render_style_config
from web.components.digital_teaching_config import render_teaching_config
from web.state.cache import (
    cached_radio,
    cached_text_area,
    cache_uploaded_files,
    clear_cached_files,
    get_cached_file_paths,
)
from web.utils.async_helpers import run_async
from multifunc_video.config import config_manager
from multifunc_video.utils.os_util import create_task_output_dir
from multifunc_video.services.teaching_composer import TeachingComposer, TeachingCompositionParams
from multifunc_video.services.llm_service import LLMService


class DigitalTeachingPipelineUI(PipelineUI):
    """
    UI for the Digital Human Teaching Video Generation Pipeline.
    Generates teaching videos from PPT/PDF + digital human + narration.
    """
    name = "digital_teaching"
    icon = "👨‍🏫"
    
    @property
    def display_name(self):
        return tr("pipeline.digital_teaching.name")
    
    @property
    def description(self):
        return tr("pipeline.digital_teaching.description")

    def render(self, multifunc_video: Any):
        # Three-column layout
        left_col, middle_col, right_col = st.columns([1, 1, 1])
        
        # ====================================================================
        # Left Column: Asset Upload (character + PPT)
        # ====================================================================
        with left_col:
            character_params = self.render_character_input()
            teaching_file_params = self.render_teaching_file_input()
            style_params = render_style_config(multifunc_video, key_prefix="digital_teaching")
            render_version_info()
        
        # ====================================================================
        # Middle Column: Video Configuration
        # ====================================================================
        with middle_col:
            workflow_config = self.workflow_path_config()
            script_params = self.render_script_input()
            teaching_config = render_teaching_config()
        
        # ====================================================================
        # Right Column: Output Preview
        # ====================================================================
        with right_col:
            video_params = {
                **character_params,
                **teaching_file_params,
                **script_params,
                **teaching_config,
                **style_params,
                "workflow_config": workflow_config,
            }
            
            self._render_output_preview(multifunc_video, video_params)

    def render_character_input(self) -> dict:
        """Render digital human character image upload section"""
        with st.container(border=True):
            st.markdown(f"**{tr('digital_teaching.section.character_assets')}**")
            
            with st.expander(tr("help.feature_description"), expanded=False):
                st.markdown(f"**{tr('help.what')}**")
                st.markdown(tr("digital_teaching.character.what"))
                st.markdown(f"**{tr('help.how')}**")
                st.markdown(tr("digital_teaching.character.how"))
            
            uploaded_files = st.file_uploader(
                tr("digital_teaching.character.upload"),
                type=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
                help=tr("digital_teaching.character.upload_help"),
                key="teaching_character_files"
            )

            # Persist uploaded files and restore cached files across restarts
            character_asset_paths = []
            character_cache_key = "teaching_character_files"
            if uploaded_files:
                character_asset_paths = cache_uploaded_files(character_cache_key, uploaded_files)
                st.success(tr("digital_teaching.character.success"))

                with st.expander(tr("digital_teaching.character.preview"), expanded=True):
                    cols = st.columns(3)
                    for i, (file, path) in enumerate(zip(uploaded_files, character_asset_paths)):
                        with cols[i % 3]:
                            st.image(file, caption=file.name, use_container_width=True)
            else:
                cached_paths = get_cached_file_paths(character_cache_key)
                if cached_paths:
                    character_asset_paths = cached_paths
                    st.info(f"📁 {tr('cache.using_cached_files', count=len(cached_paths))}")
                    with st.expander(tr("digital_teaching.character.preview"), expanded=True):
                        cols = st.columns(3)
                        for i, path in enumerate(character_asset_paths):
                            with cols[i % 3]:
                                st.image(path, caption=Path(path).name, use_container_width=True)
                    if st.button(tr("cache.clear_files"), key="clear_teaching_character_files"):
                        clear_cached_files(character_cache_key)
                        st.rerun()
                else:
                    st.info(tr("digital_teaching.character.empty_hint"))

            return {"character_assets": character_asset_paths}

    def render_teaching_file_input(self) -> dict:
        """Render PPT/PDF upload section"""
        with st.container(border=True):
            st.markdown(f"**{tr('digital_teaching.section.teaching_file')}**")
            
            with st.expander(tr("help.feature_description"), expanded=False):
                st.markdown(f"**{tr('help.what')}**")
                st.markdown(tr("digital_teaching.teaching_file.what"))
                st.markdown(f"**{tr('help.how')}**")
                st.markdown(tr("digital_teaching.teaching_file.how"))
            
            uploaded_file = st.file_uploader(
                tr("digital_teaching.teaching_file.upload"),
                type=["pptx", "pdf"],
                accept_multiple_files=False,
                help=tr("digital_teaching.teaching_file.upload_help"),
                key="teaching_material_file"
            )

            # Persist uploaded file and restore cached file across restarts
            teaching_file_path = ""
            material_cache_key = "teaching_material_file"
            if uploaded_file:
                cached_paths = cache_uploaded_files(material_cache_key, [uploaded_file])
                if cached_paths:
                    teaching_file_path = cached_paths[0]
                st.success(tr("digital_teaching.teaching_file.success", filename=uploaded_file.name))

                # Preview slides
                temp_dir = Path(teaching_file_path).parent
                try:
                    from multifunc_video.services.ppt_service import PPTService
                    ppt_service = PPTService()
                    slides = ppt_service.parse(teaching_file_path, output_dir=str(temp_dir / "slides_preview"))

                    if slides:
                        st.caption(tr("digital_teaching.teaching_file.preview_caption", count=len(slides)))
                        preview_cols = st.columns(min(3, len(slides)))
                        for i, slide in enumerate(slides[:6]):  # Show first 6 slides
                            with preview_cols[i % 3]:
                                st.image(slide.image_path, caption=f"{tr('digital_teaching.slide')} {slide.index + 1}", use_container_width=True)
                        if len(slides) > 6:
                            st.caption(tr("digital_teaching.teaching_file.more_slides", count=len(slides) - 6))
                except Exception as e:
                    logger.warning(f"预览课件失败: {e}")
                    st.warning(tr("digital_teaching.teaching_file.preview_failed", error=str(e)))
            else:
                cached_paths = get_cached_file_paths(material_cache_key)
                if cached_paths:
                    teaching_file_path = cached_paths[0]
                    st.info(f"📁 {tr('cache.using_cached_file')}: {Path(teaching_file_path).name}")
                    if st.button(tr("cache.clear_file"), key="clear_teaching_material_file"):
                        clear_cached_files(material_cache_key)
                        st.rerun()
                else:
                    st.info(tr("digital_teaching.teaching_file.empty_hint"))

            return {"teaching_file_path": teaching_file_path}

    def render_script_input(self) -> dict:
        """Render optional teaching script input"""
        with st.container(border=True):
            st.markdown(f"**{tr('digital_teaching.section.script')}**")
            
            with st.expander(tr("help.feature_description"), expanded=False):
                st.markdown(f"**{tr('help.what')}**")
                st.markdown(tr("digital_teaching.script.what"))
                st.markdown(f"**{tr('help.how')}**")
                st.markdown(tr("digital_teaching.script.how"))
            
            script = cached_text_area(
                tr("digital_teaching.script.label"),
                key="teaching_script",
                placeholder=tr("digital_teaching.script.placeholder"),
                height=180,
                help=tr("digital_teaching.script.help")
            )
            
            if not script.strip():
                st.info(tr("digital_teaching.script.auto_generate_hint"))
            
            return {"teaching_script": script}

    def workflow_path_config(self) -> dict:
        """Render workflow source selection (same as digital_human)"""
        with st.container(border=True):
            st.markdown(f"**{tr('asset_based.section.source')}**")
            
            with st.expander(tr("help.feature_description"), expanded=False):
                st.markdown(f"**{tr('help.what')}**")
                st.markdown(tr("asset_based.source.what"))
                st.markdown(f"**{tr('help.how')}**")
                st.markdown(tr("asset_based.source.how"))
            
            source_options = {
                "runninghub": tr("asset_based.source.runninghub"),
                "selfhost": tr("asset_based.source.selfhost")
            }
            
            comfyui_config = config_manager.get_comfyui_config()
            has_runninghub = bool(comfyui_config.get("runninghub_api_key"))
            has_selfhost = bool(comfyui_config.get("comfyui_url"))
            
            if has_runninghub:
                default_source_index = 0
            elif has_selfhost:
                default_source_index = 1
            else:
                default_source_index = 0
            
            source = cached_radio(
                tr("asset_based.source.select"),
                key="teaching_workflow_source",
                options=list(source_options.keys()),
                format_func=lambda x: source_options[x],
                index=default_source_index,
                horizontal=True,
                label_visibility="collapsed"
            )
            
            if source == "runninghub":
                if not has_runninghub:
                    st.warning(tr("asset_based.source.runninghub_not_configured"))
            else:
                if not has_selfhost:
                    st.warning(tr("asset_based.source.selfhost_not_configured"))
            
            return {
                "workflow_source": source,
                "first_workflow_path": f"workflows/{source}/digital_image.json",
                "second_workflow_path": f"workflows/{source}/digital_combination.json",
                "third_workflow_path": f"workflows/{source}/digital_customize.json"
            }

    def _render_output_preview(self, multifunc_video: Any, video_params: dict):
        """Render output preview and generation button"""
        with st.container(border=True):
            st.markdown(f"**{tr('section.video_generation')}**")
            
            # Check configuration
            if not config_manager.validate():
                st.warning(tr("settings.not_configured"))
            
            character_assets = video_params.get("character_assets", [])
            teaching_file_path = video_params.get("teaching_file_path", "")
            teaching_script = video_params.get("teaching_script", "")
            
            # Validation
            if not character_assets:
                st.info(tr("digital_teaching.character.warning"))
                st.button(
                    tr("btn.generate"),
                    type="primary",
                    use_container_width=True,
                    disabled=True,
                    key="digital_teaching_generate_disabled_character"
                )
                return
            
            if not teaching_file_path:
                st.info(tr("digital_teaching.teaching_file.warning"))
                st.button(
                    tr("btn.generate"),
                    type="primary",
                    use_container_width=True,
                    disabled=True,
                    key="digital_teaching_generate_disabled_file"
                )
                return
            
            # Generate button
            if st.button(tr("btn.generate"), type="primary", use_container_width=True, key="digital_teaching_generate"):
                if not config_manager.validate():
                    st.error(tr("settings.not_configured"))
                    st.stop()
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                start_time = time.time()
                
                try:
                    async def generate_teaching_video():
                        task_dir, task_id = create_task_output_dir()
                        
                        def progress_callback(step, total, message):
                            progress = min(0.99, step / total)
                            progress_bar.progress(int(progress * 100))
                            status_text.text(message)
                        
                        # Build composition params
                        params = TeachingCompositionParams(
                            character_image_path=character_assets[0],
                            teaching_file_path=teaching_file_path,
                            task_dir=task_dir,
                            teaching_script=teaching_script,
                            human_scale=video_params.get("human_scale", 1/6),
                            human_offset_x=video_params.get("human_offset_x", 0.02),
                            human_offset_y=video_params.get("human_offset_y", 0.02),
                            human_anchor=video_params.get("human_anchor", "bottom-right"),
                            duration_mode=video_params.get("duration_mode", "auto"),
                            target_duration=video_params.get("target_duration", 0.0),
                            width=1920,
                            height=1080,
                            slide_fit_mode=video_params.get("slide_fit_mode", "fit"),
                            human_prompt=video_params.get("human_prompt", ""),
                            workflow_source=video_params.get("workflow_config", {}).get("workflow_source", "runninghub"),
                            tts_inference_mode=video_params.get("tts_inference_mode", "local"),
                            tts_voice=video_params.get("tts_voice"),
                            tts_speed=video_params.get("tts_speed"),
                            tts_workflow=video_params.get("tts_workflow"),
                            ref_audio=video_params.get("ref_audio"),
                            audio_volume=video_params.get("audio_volume", 1.0),
                            gpt_sovits_project_path=video_params.get("gpt_sovits_project_path"),
                            gpt_sovits_api_url=video_params.get("gpt_sovits_api_url"),
                            gpt_sovits_ref_audio=video_params.get("gpt_sovits_ref_audio"),
                            gpt_sovits_prompt_text=video_params.get("gpt_sovits_prompt_text", ""),
                            gpt_sovits_prompt_lang=video_params.get("gpt_sovits_prompt_lang", "zh"),
                            gpt_sovits_text_lang=video_params.get("gpt_sovits_text_lang", "zh"),
                            qwen3_tts_model_path=video_params.get("qwen3_tts_model_path"),
                            qwen3_tts_device=video_params.get("qwen3_tts_device"),
                            qwen3_tts_ref_audio=video_params.get("qwen3_tts_ref_audio"),
                            qwen3_tts_prompt_text=video_params.get("qwen3_tts_prompt_text", ""),
                            qwen3_tts_speaker=video_params.get("qwen3_tts_speaker"),
                            qwen3_tts_language=video_params.get("qwen3_tts_language"),
                        )
                        
                        llm_service = LLMService(config_manager.get_llm_config())
                        composer = TeachingComposer(multifunc_video, llm_service)
                        final_video = await composer.compose(params, progress_callback)
                        
                        return final_video
                    
                    final_video_path = run_async(generate_teaching_video())
                    
                    total_time = time.time() - start_time
                    progress_bar.progress(100)
                    status_text.text(tr("status.success"))
                    
                    st.success(tr("status.video_generated", path=final_video_path))
                    st.markdown("---")
                    
                    if os.path.exists(final_video_path):
                        file_size_mb = os.path.getsize(final_video_path) / (1024 * 1024)
                        info_text = (
                            f"⏱️ {tr('info.generation_time')} {total_time:.1f}s   "
                            f"📦 {file_size_mb:.2f}MB"
                        )
                        st.caption(info_text)
                        st.markdown("---")
                        st.video(final_video_path)
                        
                        with open(final_video_path, "rb") as video_file:
                            video_bytes = video_file.read()
                            video_filename = os.path.basename(final_video_path)
                            st.download_button(
                                label="⬇️ 下载视频" if get_language() == "zh_CN" else "⬇️ Download Video",
                                data=video_bytes,
                                file_name=video_filename,
                                mime="video/mp4",
                                use_container_width=True
                            )
                    else:
                        st.error(tr("status.video_not_found", path=final_video_path))
                
                except Exception as e:
                    import traceback
                    status_text.text("")
                    progress_bar.empty()
                    error_detail = f"{type(e).__name__}: {e}"
                    tb_text = traceback.format_exc()
                    st.error(tr("status.error", error=error_detail))
                    with st.expander("🔍 查看详细错误信息（请复制给技术支持）", expanded=True):
                        st.code(tb_text, language="text")
                    logger.exception(e)
                    st.stop()


# Register self
register_pipeline_ui(DigitalTeachingPipelineUI)
