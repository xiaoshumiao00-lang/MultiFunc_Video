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
Configuration components for Digital Teaching pipeline.
"""

import streamlit as st
from web.i18n import tr
from web.state.cache import (
    cached_number_input,
    cached_radio,
    cached_selectbox,
    cached_slider,
    cached_text_area,
)


def render_teaching_config() -> dict:
    """
    Render digital teaching specific configuration section.
    Returns dict with teaching-specific parameters.
    """
    with st.container(border=True):
        st.markdown(f"**{tr('digital_teaching.section.config')}**")
        
        with st.expander(tr("help.feature_description"), expanded=False):
            st.markdown(f"**{tr('help.what')}**")
            st.markdown(tr("digital_teaching.config.what"))
            st.markdown(f"**{tr('help.how')}**")
            st.markdown(tr("digital_teaching.config.how"))
        
        # Aspect ratio (only landscape per user requirement)
        aspect_ratio = cached_selectbox(
            tr("digital_teaching.aspect_ratio"),
            key="teaching_aspect_ratio",
            options=["16:9"],
            index=0,
            disabled=True
        )

        # Slide fit mode
        fit_mode = cached_radio(
            tr("digital_teaching.slide_fit_mode"),
            key="teaching_slide_fit_mode",
            options=["fit", "cover"],
            format_func=lambda x: tr(f"digital_teaching.fit_mode.{x}"),
            index=0,
            horizontal=True
        )
        
        st.markdown("---")
        st.markdown(f"**{tr('digital_teaching.section.human_position')}**")
        
        # Human scale
        human_scale = cached_slider(
            tr("digital_teaching.human_scale"),
            key="teaching_human_scale",
            min_value=0.05,
            max_value=0.5,
            value=1/6,
            step=0.01,
            format="%.2f",
            help=tr("digital_teaching.human_scale_help")
        )

        # Position offsets
        offset_col1, offset_col2 = st.columns(2)
        with offset_col1:
            human_offset_x = cached_slider(
                tr("digital_teaching.human_offset_x"),
                key="teaching_human_offset_x",
                min_value=0.0,
                max_value=0.2,
                value=0.02,
                step=0.01,
                format="%.2f",
                help=tr("digital_teaching.human_offset_x_help")
            )
        with offset_col2:
            human_offset_y = cached_slider(
                tr("digital_teaching.human_offset_y"),
                key="teaching_human_offset_y",
                min_value=0.0,
                max_value=0.2,
                value=0.02,
                step=0.01,
                format="%.2f",
                help=tr("digital_teaching.human_offset_y_help")
            )

        # Anchor position
        human_anchor = cached_selectbox(
            tr("digital_teaching.human_anchor"),
            key="teaching_human_anchor",
            options=["bottom-right"],
            index=0,
            disabled=True
        )
        
        # Optional prompt for human (e.g. hand gestures)
        with st.expander(tr("digital_teaching.human_prompt_expander"), expanded=False):
            human_prompt = cached_text_area(
                tr("digital_teaching.human_prompt"),
                key="teaching_human_prompt",
                default="",
                placeholder=tr("digital_teaching.human_prompt_placeholder"),
                height=80,
                help=tr("digital_teaching.human_prompt_help")
            )
        
        st.markdown("---")
        st.markdown(f"**{tr('digital_teaching.section.duration')}**")
        
        # Duration mode
        duration_mode = cached_radio(
            tr("digital_teaching.duration_mode"),
            key="teaching_duration_mode",
            options=["auto", "fixed"],
            format_func=lambda x: tr(f"digital_teaching.duration_mode.{x}"),
            index=0,
            horizontal=True
        )

        target_duration = 0.0
        if duration_mode == "fixed":
            target_duration = cached_number_input(
                tr("digital_teaching.target_duration"),
                key="teaching_target_duration",
                min_value=5.0,
                max_value=600.0,
                value=60.0,
                step=5.0,
                help=tr("digital_teaching.target_duration_help")
            )

        st.markdown("---")
        st.markdown(f"**{tr('digital_teaching.section.audio')}**")

        audio_volume = cached_slider(
            tr("digital_teaching.audio_volume"),
            key="teaching_audio_volume",
            min_value=0.0,
            max_value=3.0,
            value=1.5,
            step=0.1,
            format="%.1f",
            help=tr("digital_teaching.audio_volume_help")
        )

        return {
            "aspect_ratio": aspect_ratio,
            "slide_fit_mode": fit_mode,
            "human_scale": human_scale,
            "human_offset_x": human_offset_x,
            "human_offset_y": human_offset_y,
            "human_anchor": human_anchor,
            "human_prompt": human_prompt,
            "duration_mode": duration_mode,
            "target_duration": target_duration,
            "audio_volume": audio_volume,
        }
