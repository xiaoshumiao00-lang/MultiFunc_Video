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
Prompts for generating teaching narration scripts from PPT/PDF content.
"""

from typing import List


def build_teaching_script_prompt(slides: List[dict], language_hint: str = "中文") -> str:
    """
    Build a prompt that asks the LLM to generate a teaching narration script
    based on slide contents.
    
    Args:
        slides: List of slide dicts with keys: index, title, text
        language_hint: Target language for the script
    
    Returns:
        Prompt string
    """
    slide_sections = []
    for slide in slides:
        title = slide.get("title", "")
        text = slide.get("text", "")
        index = slide.get("index", 0)
        section = f"【第 {index + 1} 页】"
        if title:
            section += f"\n标题：{title}"
        if text:
            # Limit text length to avoid token overflow
            display_text = text[:800]
            if len(text) > 800:
                display_text += "..."
            section += f"\n内容：{display_text}"
        slide_sections.append(section)
    
    slides_text = "\n\n".join(slide_sections)
    
    prompt = f"""你是一位经验丰富的教学视频讲解员。请根据以下课件内容，生成一段自然、口语化、适合配音的教学口播文案。

要求：
1. 使用{language_hint}，语言自然流畅，适合口头讲解。
2. 文案要紧密围绕课件内容展开，不要添加课件中没有的信息。
3. 按照课件页码顺序组织内容，每一页的内容讲解要完整。
4. 可以在讲解中使用"我们来看第一页"、"接下来"、"总结一下"等过渡语。
5. 总时长控制在适合教学的范围内，讲解节奏适中。
6. 只输出口播文案正文，不要输出任何标题、页码标记或额外说明。
7. 文案中不要出现"首先"、"其次"等过于刻板的连接词堆砌。

课件内容：

{slides_text}

请生成教学口播文案："""

    return prompt


def build_slide_segment_prompt(full_script: str, slides: List[dict]) -> str:
    """
    Build a prompt that splits the full script into segments aligned with slides.
    
    Args:
        full_script: The complete narration script
        slides: List of slide dicts
    
    Returns:
        Prompt string
    """
    slides_text = "\n".join([
        f"第 {s.get('index', 0) + 1} 页：{s.get('title', '') or s.get('text', '')[:50]}"
        for s in slides
    ])
    
    prompt = f"""请将以下完整口播文案按课件页拆分为对应片段。

课件页概览：
{slides_text}

完整口播文案：
{full_script}

请严格按以下 JSON 格式输出，不要包含其他内容：
{{
  "segments": [
    {{"slide_index": 0, "text": "对应第1页的口播文案片段"}},
    {{"slide_index": 1, "text": "对应第2页的口播文案片段"}}
  ]
}}

要求：
1. 每个片段的 text 必须是完整口播文案中的连续子串。
2. 所有片段拼接后应等于完整口播文案（允许少量连接词差异）。
3. 不要合并或跳过任何一页。
4. 只输出 JSON，不要任何解释。"""

    return prompt


def build_free_segment_prompt(full_script: str, slides: List[dict]) -> str:
    """
    Build a prompt that splits the full script into time-bounded segments
    with flexible slide mapping. A segment may span multiple slides, and
    a slide may be covered by multiple consecutive segments.

    Args:
        full_script: The complete narration script
        slides: List of slide dicts

    Returns:
        Prompt string
    """
    slides_text = "\n".join([
        f"第 {s.get('index', 0) + 1} 页：{s.get('title', '') or s.get('text', '')[:80]}"
        for s in slides
    ])

    prompt = f"""请将以下完整口播文案切分为若干片段，用于后续配音和数字人视频生成。

课件页概览（共 {len(slides)} 页）：
{slides_text}

完整口播文案：
{full_script}

请严格按以下 JSON 格式输出，不要包含其他内容：
{{
  "segments": [
    {{"text": "...", "slide_start": 0, "slide_end": 0}},
    {{"text": "...", "slide_start": 0, "slide_end": 1}}
  ]
}}

要求：
1. 每个片段在中文正常语速下约 10 秒，绝对不要超过 15 秒。
2. 必须在标点符号或语义完整处切断，不要切断词语或句子。
3. 每个片段标注对应的 PPT 起始页和结束页（slide_start 和 slide_end 均从 0 开始，包含）。
4. 允许一个片段跨多页，也允许多个连续片段属于同一页。
5. 所有片段的 text 拼接后应等于完整口播文案（允许极少量连接词差异）。
6. 优先在课件页切换的过渡语附近（如"我们来看下一页"、"总结一下"）进行切分。
7. 只输出 JSON，不要任何解释、标题或 Markdown 代码块。"""

    return prompt
