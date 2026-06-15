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
Home Page - Main video generation interface
"""

import sys
from pathlib import Path

# Add project root to sys.path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

# Import state management
from web.state.session import init_session_state, init_i18n, get_multifunc_video

# Import components
from web.components.header import render_header
from web.components.settings import render_advanced_settings
from web.components.faq import render_faq_sidebar

# Page config
st.set_page_config(
    page_title="Home - MultiFunc_Video",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main():
    """Main UI entry point"""
    # Initialize session state and i18n
    init_session_state()
    init_i18n()
    
    # Render header (title + language selector)
    render_header()
    
    # One-click GPU memory cleanup
    if st.button(tr("btn.clear_gpu_memory"), key="clear_gpu_memory_btn", use_container_width=False):
        try:
            from web.utils.gpu_cleanup import clear_gpu_memory
            from multifunc_video.config import config_manager
            
            comfyui_config = config_manager.get_comfyui_config()
            llm_config = config_manager.get_llm_config()
            
            # Detect Ollama endpoint from LLM base URL (default port 11434)
            llm_base_url = str(llm_config.get("base_url") or "")
            ollama_url = llm_base_url if "11434" in llm_base_url else None
            
            with st.spinner(tr("status.clearing_gpu_memory")):
                summary = clear_gpu_memory(
                    comfyui_url=comfyui_config.get("comfyui_url"),
                    comfyui_api_key=comfyui_config.get("comfyui_api_key"),
                    ollama_base_url=ollama_url,
                )
            
            if summary["overall"] == "success":
                st.success(tr("status.gpu_memory_cleared"))
            elif summary["overall"] == "partial":
                st.warning(tr("status.gpu_memory_partial"))
            else:
                st.error(tr("status.gpu_memory_failed"))
            
            with st.expander(tr("status.gpu_memory_details")):
                for result in summary["results"]:
                    icon = "✅" if result["success"] else "⚠️"
                    st.write(f"{icon} **{result['source']}**: {result['message']}")
        except Exception as e:
            st.error(f"{tr('status.gpu_memory_failed')}: {e}")
    
    # Render FAQ in sidebar
    render_faq_sidebar()
    
    # Initialize MultiFunc_Video
    multifunc_video = get_multifunc_video()
    
    # Render system configuration (LLM + ComfyUI)
    render_advanced_settings()
    
    # ========================================================================
    # Pipeline Selection & Delegation
    # ========================================================================
    from web.pipelines import get_all_pipeline_uis
    
    # Get all registered pipelines
    pipelines = get_all_pipeline_uis()
    
    # Use Tabs for pipeline selection
    # Note: st.tabs returns a list of containers, one for each tab
    tab_labels = [f"{p.icon} {p.display_name}" for p in pipelines]
    tabs = st.tabs(tab_labels)
    
    # Render each pipeline in its corresponding tab
    for i, pipeline in enumerate(pipelines):
        with tabs[i]:
            # Show description if available
            if pipeline.description:
                st.caption(pipeline.description)
            
            # Delegate rendering
            pipeline.render(multifunc_video)


if __name__ == "__main__":
    main()

