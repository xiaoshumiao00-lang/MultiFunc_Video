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

# Import i18n
from web.i18n import tr

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
    gpu_cleanup_col1, gpu_cleanup_col2 = st.columns([3, 1])
    with gpu_cleanup_col1:
        force_kill = st.checkbox(
            tr("gpu.force_kill_ollama"),
            key="force_kill_ollama_checkbox",
            help=tr("gpu.force_kill_ollama_help"),
        )
    with gpu_cleanup_col2:
        run_cleanup = st.button(
            tr("btn.clear_gpu_memory"),
            key="clear_gpu_memory_btn",
            use_container_width=True,
            type="secondary",
        )
    
    if run_cleanup:
        try:
            from web.utils.gpu_cleanup import clear_gpu_memory
            from multifunc_video.config import config_manager
            
            comfyui_config = config_manager.get_comfyui_config()
            
            with st.spinner(tr("status.clearing_gpu_memory")):
                summary = clear_gpu_memory(
                    comfyui_url=comfyui_config.get("comfyui_url"),
                    comfyui_api_key=comfyui_config.get("comfyui_api_key"),
                    force_kill_ollama=force_kill,
                )
            
            st.session_state["gpu_cleanup_summary"] = summary
            st.rerun()
        except Exception as e:
            st.error(f"{tr('status.gpu_memory_failed')}: {e}")
    
    summary = st.session_state.get("gpu_cleanup_summary")
    if summary:
        if summary["overall"] == "success":
            st.success(tr("status.gpu_memory_cleared"))
        elif summary["overall"] == "partial":
            st.warning(tr("status.gpu_memory_partial"))
        else:
            st.error(tr("status.gpu_memory_failed"))
        
        with st.expander(tr("status.gpu_memory_details"), expanded=True):
            # Memory delta
            before = summary.get("before", {})
            after = summary.get("after", {})
            if before.get("available") and after.get("available"):
                used_before = before["used_mb"]
                used_after = after["used_mb"]
                total = after["total_mb"]
                delta = used_before - used_after
                st.write(
                    f"**GPU Memory:** {used_before} MB → {used_after} MB / {total} MB "
                    f"(released {delta} MB)"
                )
            elif before.get("error"):
                st.write(f"**GPU Memory:** {before['error']}")
            else:
                st.write("**GPU Memory:** nvidia-smi not available")
            
            st.write("**Cleanup results:**")
            for result in summary["results"]:
                icon = "✅" if result["success"] else "⚠️"
                st.write(f"{icon} **{result['source']}**: {result['message']}")
            
            # Remaining GPU processes
            processes_after = summary.get("processes_after", [])
            if processes_after:
                st.write("**Remaining GPU processes:**")
                for proc in processes_after:
                    st.write(f"- `{proc['name']}` (PID {proc['pid']}) — {proc['memory']}")
                
                has_ollama = any("llama-server" in p["name"] or "ollama" in p["name"] for p in processes_after)
                if has_ollama and not force_kill:
                    st.warning(tr("gpu.ollama_still_running"))
            else:
                st.write("**Remaining GPU processes:** none")
    
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

