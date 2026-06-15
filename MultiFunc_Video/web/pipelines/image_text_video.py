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
图文视频 Pipeline UI

集成 AutoVideo 技能使用的本地 video-generator 视频生成引擎：
- 输入：视频文案、参考音频（音色克隆）、背景音乐（可选）、视频风格、语速等
- 输出：短视频、标题、摘要
- 支持一键上传至飞书多维表格
"""

import os
import time
from pathlib import Path
from typing import Any

import streamlit as st
from loguru import logger

from web.i18n import tr, get_language
from web.pipelines.base import PipelineUI, register_pipeline_ui
from web.state.cache import (
    cached_text_area,
    cached_text_input,
    cached_selectbox,
    cached_radio,
    cached_slider,
    cached_checkbox,
    cache_uploaded_files,
    get_cached_file_paths,
    clear_cached_files,
)
from multifunc_video.services.image_text_video_service import ImageTextVideoService


class ImageTextVideoPipelineUI(PipelineUI):
    """图文视频 Pipeline UI"""

    name = "image_text_video"
    icon = "🖼️"

    @property
    def display_name(self):
        return tr("pipeline.image_text_video.name")

    @property
    def description(self):
        return tr("pipeline.image_text_video.description")

    def render(self, multifunc_video: Any):
        # 三栏布局：输入参数 | 高级设置 | 输出预览
        left_col, middle_col, right_col = st.columns([1, 1, 1])

        with left_col:
            input_params = self._render_input_section()

        with middle_col:
            style_params = self._render_style_section()

        with right_col:
            params = {**input_params, **style_params}
            self._render_output_section(multifunc_video, params)

    def _render_input_section(self) -> dict:
        """左侧：文案、参考音频、背景音乐"""
        with st.container(border=True):
            st.markdown(f"**{tr('image_text_video.input.section')}**")

            # 视频文案
            text = cached_text_area(
                tr("image_text_video.input.text"),
                key="itv_text",
                placeholder=tr("image_text_video.input.text_placeholder"),
                height=240,
                help=tr("image_text_video.input.text_help")
            )

            # 参考音频
            st.markdown(f"**{tr('image_text_video.input.ref_audio')}**")
            ref_audio_file = st.file_uploader(
                tr("image_text_video.input.ref_audio_help"),
                type=["mp3", "wav", "m4a", "aac"],
                accept_multiple_files=False,
                key="itv_ref_audio"
            )
            ref_audio_paths = []
            if ref_audio_file:
                ref_audio_paths = cache_uploaded_files("itv_ref_audio", [ref_audio_file])
                st.audio(ref_audio_file, format=f"audio/{Path(ref_audio_file.name).suffix.lstrip('.')}")
            else:
                cached = get_cached_file_paths("itv_ref_audio")
                if cached:
                    ref_audio_paths = cached
                    st.info(f"📁 {tr('cache.using_cached_files', count=len(cached))}")
                    if st.button(tr("cache.clear_files"), key="clear_itv_ref_audio"):
                        clear_cached_files("itv_ref_audio")
                        st.rerun()

            # 参考音频文本
            ref_audio_text = cached_text_area(
                tr("image_text_video.input.ref_audio_text"),
                key="itv_ref_audio_text",
                default="",
                height=80,
                help=tr("image_text_video.input.ref_audio_text_help")
            )

            # 背景音乐（可选）
            st.markdown(f"**{tr('image_text_video.input.bgm')}**")
            bgm_file = st.file_uploader(
                tr("image_text_video.input.bgm_help"),
                type=["mp3", "wav", "m4a", "aac"],
                accept_multiple_files=False,
                key="itv_bgm"
            )
            bgm_paths = []
            if bgm_file:
                bgm_paths = cache_uploaded_files("itv_bgm", [bgm_file])
                st.audio(bgm_file, format=f"audio/{Path(bgm_file.name).suffix.lstrip('.')}")
            else:
                cached = get_cached_file_paths("itv_bgm")
                if cached:
                    bgm_paths = cached
                    st.info(f"📁 {tr('cache.using_cached_files', count=len(cached))}")
                    if st.button(tr("cache.clear_files"), key="clear_itv_bgm"):
                        clear_cached_files("itv_bgm")
                        st.rerun()

            return {
                "text": text,
                "ref_audio_path": ref_audio_paths[0] if ref_audio_paths else None,
                "ref_audio_file": ref_audio_file,
                "ref_audio_text": ref_audio_text,
                "bgm_path": bgm_paths[0] if bgm_paths else None,
                "bgm_file": bgm_file,
            }

    def _render_style_section(self) -> dict:
        """中间：风格、语速、音量、上传选项"""
        with st.container(border=True):
            st.markdown(f"**{tr('image_text_video.style.section')}**")

            # 视频主题/风格
            theme_options = self._get_theme_options()
            theme = cached_selectbox(
                tr("image_text_video.style.theme"),
                key="itv_theme",
                options=theme_options,
                index=0,
                help=tr("image_text_video.style.theme_help")
            )
            theme_value = None if theme == tr("image_text_video.style.theme_auto") else theme

            # 自定义图片提示词
            image_prompt = cached_text_area(
                tr("image_text_video.style.image_prompt"),
                key="itv_image_prompt",
                default="",
                height=100,
                help=tr("image_text_video.style.image_prompt_help")
            )

            # 画面方向
            orientation = cached_radio(
                tr("image_text_video.style.orientation"),
                key="itv_orientation",
                options=["portrait", "landscape"],
                format_func=lambda x: tr(f"image_text_video.style.orientation_{x}"),
                index=0,
                horizontal=True
            )

            # 语速
            speed = cached_slider(
                tr("image_text_video.style.speed"),
                key="itv_speed",
                min_value=0.5,
                max_value=2.0,
                value=1.0,
                step=0.05,
                help=tr("image_text_video.style.speed_help")
            )

            # 背景音乐音量
            bgm_volume = cached_slider(
                tr("image_text_video.style.bgm_volume"),
                key="itv_bgm_volume",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.05,
                help=tr("image_text_video.style.bgm_volume_help")
            )

            # 自动上传飞书
            auto_upload = cached_checkbox(
                tr("image_text_video.style.auto_upload"),
                key="itv_auto_upload",
                value=True,
                help=tr("image_text_video.style.auto_upload_help")
            )

            return {
                "theme": theme_value,
                "image_prompt": image_prompt,
                "orientation": orientation,
                "speed": speed,
                "bgm_volume": bgm_volume,
                "auto_upload": auto_upload
            }

    def _render_output_section(self, multifunc_video: Any, params: dict):
        """右侧：生成按钮、进度、结果展示"""
        with st.container(border=True):
            st.markdown(f"**{tr('section.video_generation')}**")

            text = params.get("text", "").strip()
            ref_audio_path = params.get("ref_audio_path")
            ref_audio_file = params.get("ref_audio_file")
            bgm_path = params.get("bgm_path")
            bgm_file = params.get("bgm_file")

            # 校验
            if not text:
                st.info(tr("image_text_video.output.text_warning"))
                st.button(tr("btn.generate"), type="primary", use_container_width=True,
                         disabled=True, key="itv_generate_text_disabled")
                return

            if not ref_audio_path and not ref_audio_file:
                st.info(tr("image_text_video.output.ref_audio_warning"))
                st.button(tr("btn.generate"), type="primary", use_container_width=True,
                         disabled=True, key="itv_generate_audio_disabled")
                return

            if st.button(tr("btn.generate"), type="primary", use_container_width=True, key="itv_generate"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                log_expander = st.expander(tr("image_text_video.output.log"), expanded=False)
                log_lines = []

                def progress_callback(step: int, total: int, message: str):
                    progress = min(0.99, step / total) if total > 0 else 0
                    progress_bar.progress(int(progress * 100))
                    status_text.text(f"[{step}/{total}] {message}")

                try:
                    start_time = time.time()

                    service = ImageTextVideoService()

                    # 读取上传文件字节
                    ref_audio_bytes = ref_audio_file.read() if ref_audio_file else None
                    if ref_audio_file:
                        ref_audio_file.seek(0)
                    bgm_bytes = bgm_file.read() if bgm_file else None
                    if bgm_file:
                        bgm_file.seek(0)

                    result = service.generate(
                        text=text,
                        ref_audio_bytes=ref_audio_bytes,
                        ref_audio_filename=ref_audio_file.name if ref_audio_file else None,
                        ref_audio_text=params.get("ref_audio_text", ""),
                        bgm_bytes=bgm_bytes,
                        bgm_filename=bgm_file.name if bgm_file else None,
                        bgm_volume=params.get("bgm_volume", 0.3),
                        theme=params.get("theme"),
                        image_prompt=params.get("image_prompt", ""),
                        speed=params.get("speed", 1.0),
                        orientation=params.get("orientation", "portrait"),
                        progress_callback=progress_callback,
                        timeout=3600
                    )

                    # 显示日志
                    with log_expander:
                        st.text("\\n".join(log_lines[-200:]))

                    # 自动上传飞书
                    upload_info = None
                    if params.get("auto_upload", True):
                        status_text.text(tr("image_text_video.progress.upload"))
                        try:
                            upload_info = service.upload_to_feishu(result, auto_upload=True)
                            st.success(tr("image_text_video.output.upload_success",
                                         record_id=upload_info.get("record_id", "")))
                        except Exception as e:
                            logger.exception(e)
                            st.warning(tr("image_text_video.output.upload_failed", error=str(e)))

                    progress_bar.progress(100)
                    status_text.text(tr("status.success"))

                    total_time = time.time() - start_time

                    # 展示结果
                    st.markdown("---")
                    st.markdown(f"### {tr('image_text_video.output.title')}")
                    st.markdown(f"**{result['title']}**")

                    st.markdown(f"### {tr('image_text_video.output.summary')}")
                    st.markdown(result['summary'] or tr("image_text_video.output.no_summary"))

                    if result.get("cover_path") and Path(result["cover_path"]).exists():
                        st.image(result["cover_path"], caption=tr("image_text_video.output.cover"),
                                 use_container_width=True)

                    if Path(result["video_path"]).exists():
                        file_size_mb = os.path.getsize(result["video_path"]) / (1024 * 1024)
                        info = f"⏱️ {tr('info.generation_time')} {total_time:.1f}s   📦 {file_size_mb:.2f}MB"
                        if upload_info:
                            info += f"   ✅ {tr('image_text_video.output.uploaded')}"
                        st.caption(info)

                        st.video(result["video_path"])

                        with open(result["video_path"], "rb") as f:
                            st.download_button(
                                label="⬇️ " + ("下载视频" if get_language() == "zh_CN" else "Download Video"),
                                data=f.read(),
                                file_name=Path(result["video_path"]).name,
                                mime="video/mp4",
                                use_container_width=True,
                                key="itv_download_video"
                            )

                    # 保存结果到 session，便于历史记录
                    st.session_state["itv_last_result"] = result
                    st.session_state["itv_last_upload"] = upload_info

                except Exception as e:
                    logger.exception(e)
                    progress_bar.empty()
                    status_text.text("")
                    with log_expander:
                        st.text("\\n".join(log_lines[-200:]))
                    st.error(tr("status.error", error=str(e)))
                    st.stop()

    def _get_theme_options(self) -> list:
        """获取视频主题选项"""
        # 从项目内部 video_generator 配置中读取主题列表
        try:
            import sys
            from pathlib import Path
            vg_path = str(Path(__file__).parent.parent.parent.parent / "video_generator")
            if vg_path not in sys.path:
                sys.path.insert(0, vg_path)
            from config import VIDEO_THEMES
            themes = list(VIDEO_THEMES.keys())
        except Exception as e:
            logger.warning(f"读取 video_generator 主题失败: {e}")
            themes = ["大学生活篇", "大学学业篇", "大学规划篇", "大学就业篇", "大学认知篇", "大学心理篇"]

        auto_label = tr("image_text_video.style.theme_auto")
        return [auto_label] + themes


register_pipeline_ui(ImageTextVideoPipelineUI)
