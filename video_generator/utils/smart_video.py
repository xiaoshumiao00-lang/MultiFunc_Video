"""
智能视频生成器 - 完整流程
1. 文案分段
2. AI分镜生成
3. 逐段生成音频+图片
4. 按时间线组装视频
"""

import asyncio
import json
import re
import time
import httpx
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from config import (
    OUTPUTS_DIR, IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR,
    VIDEO_SETTINGS, WATERMARK, SUBTITLE_SETTINGS,
    VIDEO_THEMES, TTS_MODE, EDGE_TTS_SETTINGS, GPT_SOVITS_SETTINGS,
    COMFYUI_SETTINGS, ZIMAGE_SETTINGS, DEFAULT_IMAGE_MODEL, IMAGE_SETTINGS,
    QWEN_TTS_SETTINGS
)
from utils.tts import TTsgenerator
from utils.gpt_sovits import GPTSoVITSTTS
from utils.qwen_tts import Qwen3TTSTTS, unload_model
from utils.subtitle import generate_ass_subtitle
from utils.university_template import UniversityVideoTemplate
from utils.video import create_video_with_subtitles
from utils.cover_generator import CoverGenerator


@dataclass
class ShotSegment:
    """分镜段落"""
    index: int           # 序号
    cap: str             # 字幕文案
    desc_prompt: str     # 图片提示词（备用）
    desc_keywords: List[str]  # 关键词
    scene_prompt: str = ""     # Ollama生成的场景描述
    audio_path: str = None     # 音频路径
    image_path: str = None      # 图片路径
    start_time: float = 0.0     # 开始时间
    end_time: float = 0.0       # 结束时间
    duration: float = 0.0       # 时长
    words: List[Dict] = None    # TTS 返回的字级时间戳


class TextSegmenter:
    """文案智能分段器"""

    def __init__(self, min_chars: int = 8, max_chars: int = 28):
        self.min_chars = min_chars
        self.max_chars = max_chars

    def segment(self, content: str) -> List[str]:
        """
        对文案进行智能分段

        规则：
        1. 标题（第一句）独立分段
        2. 每段8-20字
        3. 只在完整句子结束后（句号）或逗号分隔的独立完整语意处分段
        4. 不在语义不完整处截断
        """
        content = content.strip()
        if not content:
            return []

        # 分割句子（按句号、感叹号、问号）
        raw_sentences = self._split_sentences(content)
        segments = []

        # 第一句作为标题独立分段
        if raw_sentences:
            title = raw_sentences[0].strip()
            if len(title) <= self.max_chars:
                segments.append(title)
                raw_sentences = raw_sentences[1:]
            else:
                # 标题过长，找第一个逗号断点
                comma_pos = title.find('，')
                if comma_pos >= self.min_chars and comma_pos <= self.max_chars:
                    segments.append(title[:comma_pos + 1])
                    remaining = title[comma_pos + 1:].strip()
                    if remaining:
                        raw_sentences = [remaining] + raw_sentences[1:]
                    else:
                        raw_sentences = raw_sentences[1:]
                else:
                    segments.append(title[:self.max_chars])
                    raw_sentences = raw_sentences[1:]

        # 处理剩余句子 - 按逗号拆分所有句子，收集完整语意
        all_phrases = []
        for sentence in raw_sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # 按逗号拆分句子，保留逗号
            parts = []
            last_idx = 0
            for i, char in enumerate(sentence):
                if char == '，':
                    if last_idx < i + 1:
                        parts.append(sentence[last_idx:i + 1])
                    last_idx = i + 1
            if last_idx < len(sentence):
                parts.append(sentence[last_idx:])

            # 收集所有独立语意
            for part in parts:
                part = part.strip()
                if part:
                    all_phrases.append(part)

        # 合并语意形成分段
        current_segment = ""
        for phrase in all_phrases:
            phrase_len = len(phrase)

            if phrase.endswith('。') or phrase.endswith('！') or phrase.endswith('？'):
                # 完整句子
                if current_segment:
                    current_segment += phrase
                    segments.append(current_segment.strip())
                    current_segment = ""
                else:
                    # 检查是否过长
                    if phrase_len <= self.max_chars:
                        segments.append(phrase)
                    else:
                        # 过长时，在逗号处分割
                        sub_parts = self._split_phrase_at_comma(phrase)
                        for sub in sub_parts:
                            sub = sub.strip()
                            if not sub:
                                continue
                            if len(sub) <= self.max_chars:
                                segments.append(sub)
                            else:
                                segments.append(sub[:self.max_chars])
            else:
                # 不是完整句子（以逗号结尾）
                if phrase_len <= self.max_chars:
                    if len(current_segment) + phrase_len <= self.max_chars:
                        current_segment = phrase if not current_segment else current_segment + phrase
                    else:
                        if current_segment:
                            segments.append(current_segment.strip())
                        current_segment = phrase
                else:
                    # 当前语意过长，在逗号处分割
                    sub_parts = self._split_phrase_at_comma(phrase)
                    for sub in sub_parts:
                        sub = sub.strip()
                        if not sub:
                            continue
                        if len(sub) <= self.max_chars:
                            if len(current_segment) + len(sub) <= self.max_chars:
                                current_segment = sub if not current_segment else current_segment + sub
                            else:
                                if current_segment:
                                    segments.append(current_segment.strip())
                                current_segment = sub
                        else:
                            # 子部分仍然过长，直接截取
                            segments.append(sub[:self.max_chars])

        # 保存最后一段
        if current_segment:
            if len(current_segment) >= self.min_chars:
                segments.append(current_segment.strip())
            elif segments:
                segments[-1] += current_segment.strip()

        # 合并过短的段落到前一段
        final_segments = []
        for seg in segments:
            while len(seg) < self.min_chars and final_segments:
                last = final_segments.pop()
                seg = last + seg
            if seg:
                final_segments.append(seg)

        return final_segments

    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        # 使用常见断句符号分割
        import re
        # 按句号、感叹号、问号分割
        parts = re.split(r'([。！？\n]+)', text)
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            sent = parts[i] + parts[i + 1]
            sentences.append(sent)
        if len(parts) % 2 == 1 and parts[-1]:
            sentences.append(parts[-1])
        return sentences

    def _split_phrase_at_comma(self, text: str) -> List[str]:
        """
        在逗号处分割长语意，保留逗号
        """
        if len(text) <= self.max_chars:
            return [text]

        parts = []
        current = ""
        for char in text:
            current += char
            if char == '，' and len(current) >= self.min_chars:
                parts.append(current)
                current = ""
        if current:
            parts.append(current)

        return parts

    def _split_at_commas(self, text: str) -> List[str]:
        """
        在逗号处分隔长句，保持语义完整
        返回多个完整语意的片段
        """
        if len(text) <= self.max_chars:
            return [text]

        parts = []
        current = ""
        comma_positions = []

        # 找出所有逗号位置
        for i, char in enumerate(text):
            if char == '，':
                comma_positions.append(i)

        # 如果没有逗号或逗号太少，按字数均匀分割
        if len(comma_positions) < 2:
            # 在max_chars附近找一个合适的断点
            mid = len(text) // 2
            # 尽量在标点或词组边界断
            for i in range(mid, min(mid + 10, len(text))):
                if text[i] in '，。、；：':
                    mid = i + 1
                    break
            else:
                # 按字数硬分割
                mid = self.max_chars
            return [text[:mid], text[mid:]]

        # 在逗号处分割，确保每段不超过max_chars
        last_cut = 0
        for comma_pos in comma_positions:
            segment = text[last_cut:comma_pos + 1]
            if len(segment) > self.max_chars:
                # 当前片段过长，先保存之前的
                if current:
                    parts.append(current)
                current = segment
                last_cut = comma_pos + 1
            else:
                if current and len(current) + len(segment) <= self.max_chars:
                    current += segment
                    last_cut = comma_pos + 1
                elif current:
                    parts.append(current)
                    current = segment
                    last_cut = comma_pos + 1
                else:
                    current = segment
                    last_cut = comma_pos + 1

        # 添加最后一段
        remaining = text[last_cut:]
        if remaining:
            if current and len(current) + len(remaining) <= self.max_chars:
                current += remaining
            elif current:
                parts.append(current)
                current = remaining
            else:
                current = remaining

        if current:
            parts.append(current)

        # 合并过短的片段
        if len(parts) > 1 and len(parts[0]) < self.min_chars:
            parts[0] += parts[1]
            parts.pop(1)

        return parts


class ShotGenerator:
    """AI分镜生成器 - 支持本地Ollama(Qwen3.5)和云端(MiniMax)"""

    def __init__(self, use_local: bool = False, local_model: str = "qwen3.5:9b"):
        """
        初始化分镜生成器

        Args:
            use_local: 是否使用本地Ollama模型
            local_model: 本地模型名称（默认qwen3.5:9b）
        """
        self.use_local = use_local
        self.local_model = local_model

        if use_local:
            # 本地 Ollama 配置
            self.ollama_url = "http://localhost:11434/api/chat"
        else:
            # 云端 MiniMax 配置
            self.api_url = "https://api.minimax.chat/v1"
            self.api_key = None  # 需要配置
            self.model = "MiniMax-Text-01"

    def set_api(self, api_url: str, api_key: str):
        """设置API配置"""
        self.api_url = api_url
        self.api_key = api_key

    async def generate_shots(self, content: str) -> List[ShotSegment]:
        """
        使用规则生成分镜（跳过Ollama，速度更快）

        Args:
            content: 完整文案

        Returns:
            分镜列表
        """
        print("[INFO] 使用规则分镜（快速模式）")
        return self._fallback_shots(content)

    async def _generate_shots_local(self, prompt: str, content: str) -> List[ShotSegment]:
        """使用本地Ollama生成分镜"""
        import httpx

        system_prompt = """你是一位专业且富有创意的视频分镜描述专家。
严格按用户要求输出JSON格式，不要输出其他内容。"""

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.local_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False,
                        "think": False,  # 关闭思考功能，加快响应
                        "options": {
                            "temperature": 0.7,
                            "num_ctx": 4096,  # 限制上下文长度，减少GPU占用
                            "num_gpu": 1,     # 使用1个GPU
                            "num_thread": 4   # 使用4线程
                        }
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get("message", {}).get("content", "")
                    if text:
                        return self._parse_shots(text)
                    else:
                        print("[ERROR] Ollama返回内容为空")
                        return self._fallback_shots(content)
                else:
                    print(f"  [INFO] Ollama服务暂不可用，使用本地分镜方案")
                    return self._fallback_shots(content)
        except Exception as e:
            print(f"[ERROR] 本地模型调用失败: {e}")
            return self._fallback_shots(content)

    async def _generate_shots_cloud(self, prompt: str, content: str) -> List[ShotSegment]:
        """使用云端API生成分镜"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.api_url}/text/chatcompletion_v2",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "你是一位专业且富有创意的视频分镜描述专家。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result["choices"][0]["message"]["content"]
                    return self._parse_shots(text)
                else:
                    print(f"[ERROR] API调用失败: {response.status_code}")
                    return self._fallback_shots(content)
        except Exception as e:
            print(f"[ERROR] 云端API调用失败: {e}")
            return self._fallback_shots(content)

    def _build_prompt(self, content: str) -> str:
        """构建分镜生成提示词"""
        return f"""请将以下文案进行分镜创作，输出JSON格式：

## 文案内容
{content}

## 分镜规则
1. 字幕文案分段：文案的第一句话（标题）必须独立成一个cap
2. 每个分段12-35字
3. 总分段数约为文案字数除以20，最多不超过38个
4. 字幕分段cap必须严格按原文拆分，不删减遗漏
5. 可以在字幕中出现"老学长"

## 分镜描述提示词要求（重要！）
1. 画面描述要精准细致，体现情节细节和多人交互场景
2. 必须有交互场景，包括人物和环境
3. 提示词中严禁出现"老学长"，必须用"学长"替代
4. 提示词不少于80字
5. **严禁包含任何文字、字母、数字、符号、标语、招牌、书本上的文字、屏幕上的文字、路牌等，画面必须完全无文字**
6. **如果场景需要展示信息，用图像、图标、图表、手势、表情等视觉元素代替文字**
7. **所有标识、标志都必须以图形化方式呈现，不能有可读的文字内容**

## 分镜关键词要求
1. 根据当前分镜提供合理的视频关键词
2. 每个词不超过4个字，最多3个词
3. 关键词要贴合分镜语境，不重复
4. 不需要就不提供

## 输出格式
```json
[
{{"cap": "字幕文案", "desc_promopt": "分镜图像提示词", "desc_keywords": ["关键词1"]}}
]
```

请严格按照JSON格式输出："""

    def _parse_shots(self, text: str) -> List[ShotSegment]:
        """解析AI返回的分镜JSON"""
        try:
            # 提取JSON部分
            import re
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(text)

            shots = []
            for i, item in enumerate(data):
                shot = ShotSegment(
                    index=i,
                    cap=item.get("cap", ""),
                    desc_prompt=item.get("desc_promopt", ""),
                    desc_keywords=item.get("desc_keywords", [])
                )
                shots.append(shot)
            return shots
        except Exception as e:
            print(f"[ERROR] 解析分镜失败: {e}")
            return []

    def _fallback_shots(self, content: str) -> List[ShotSegment]:
        """备用方案：使用规则生成分镜"""
        segmenter = TextSegmenter(min_chars=8, max_chars=35)
        caps = segmenter.segment(content)

        shots = []
        for i, cap in enumerate(caps):
            shot = ShotSegment(
                index=i,
                cap=cap,
                desc_prompt=f"插画风格，简洁背景，学生形象，{cap[:10]}场景，画面中没有任何文字、字母、数字或符号",
                desc_keywords=[]
            )
            shots.append(shot)
        return shots

    async def classify_theme(self, content: str) -> str:
        """
        使用关键词匹配识别文案类别（默认快速模式）

        Args:
            content: 完整文案内容

        Returns:
            分类主题名称，如"大学学业篇"
        """
        print(f"  [分类] 使用关键词匹配识别类别")
        return self._keyword_fallback_classify(content)

    def _keyword_fallback_classify(self, content: str) -> str:
        """
        基于关键词的备用分类方法

        Args:
            content: 文案内容

        Returns:
            分类主题名称
        """
        # 各类别的关键词映射（优先级从高到低）
        keyword_map = {
            "大学心理篇": ["心理", "情绪", "压力", "焦虑", "抑郁", "emo", "失眠", "心情", "调节", "释放", "疏导", "健康", "心态", "积极", "负面", "自我"],
            "大学就业篇": ["工作", "就业", "简历", "面试", "实习", "招聘", "职业", "岗位", "薪资", "offer", "求职", "就业市场", "毕业找工作", "秋招", "春招", "找工作"],
            "大学规划篇": ["规划", "计划", "安排", "四年", "大三", "大四", "大二", "大一", "时间管理", "提前", "策略", "目标", "时间表", "日程"],
            "大学认知篇": ["认知", "理解", "误解", "真相", "现象", "老师不管", "为什么", "原因", "揭秘", "解读", "认识", "事实", "本质"],
            "大学学业篇": ["考试", "成绩", "学分", "选课", "课堂", "笔记", "作业", "论文", "考研", "上课", "教授", "教室", "自习", "复习", "预习", "学业", "学术"],
            "大学生活篇": ["宿舍", "室友", "食堂", "社团", "聚会", "假期", "周末", "娱乐", "游戏", "追星", "恋爱", "社交", "朋友", "活动", "运动", "健身", "外卖"]
        }

        # 优先检测心理类（因为这类文案特征最明显）
        if any(kw in content for kw in keyword_map["大学心理篇"]):
            return "大学心理篇"

        # 检测就业类
        if any(kw in content for kw in keyword_map["大学就业篇"]):
            return "大学就业篇"

        # 检测规划类
        if any(kw in content for kw in keyword_map["大学规划篇"]):
            return "大学规划篇"

        # 检测认知类
        if any(kw in content for kw in keyword_map["大学认知篇"]):
            return "大学认知篇"

        # 检测学业类（考试、成绩优先于"学习"）
        academic_keywords = ["考试", "成绩", "学分", "选课", "课堂", "笔记", "作业", "论文", "考研", "自习", "复习", "预习"]
        if any(kw in content for kw in academic_keywords):
            return "大学学业篇"

        # 检测生活类
        if any(kw in content for kw in keyword_map["大学生活篇"]):
            return "大学生活篇"

        # 如果文案包含"学习"但不包含上述关键词，归类为学业篇
        if "学习" in content:
            return "大学学业篇"

        # 默认返回大学学业篇
        return "大学学业篇"

    async def generate_summary(self, content: str, theme: str) -> str:
        """
        使用 Ollama 生成视频摘要

        Args:
            content: 完整文案内容
            theme: 文案分类（如"大学学业篇"）

        Returns:
            摘要文本，格式：大学学业篇之：[文案标题]。#话题词1  #话题词2  #话题词3  #话题词4
        """
        import httpx

        # 构建摘要生成提示词
        system_prompt = """你是一个文案优化助手。

你的任务是根据用户提供的文案，生成一个简洁的摘要。

## 任务要求
1. 识别文案的主题，在文案最后新增4个话题词
2. 话题词需与文案内容相关，且必须为常见的话题词
3. 话题词描述的要宽泛，不要太偏或者太具体
4. 话题词一般为2-6个字之间
5. 话题词前面必须有#，如"#话题词1  #话题词2  #话题词3  #话题词4"

## 输出格式
严格按照下面格式输出，不得输出其他文字内容：
"文案分类"之：[文案标题]。话题词

## 示例输出
大学学业篇之：大学给老师送礼？家长别瞎忙，这两点更管用。#大学送礼  #大学日常  #家长建议  #师生关系

## 重要
1. 必须正好4个话题词，用空格分隔
2. 只输出摘要这一行，不要输出其他内容
3. 不要加引号
4. 不要加特殊标记"""

        # 提取文案标题（第一句完整的话）
        title = content.strip()
        for i, char in enumerate(title):
            if char in '。！？':
                title = title[:i+1]
                break
        if len(title) > 50:
            title = title[:50]

        user_prompt = f"""文案分类：{theme}
文案内容：
{content}

请严格按照以下格式生成一行摘要：
{theme}之：[文案标题]。#话题词1  #话题词2  #话题词3  #话题词4

要求：
1. 话题词必须与文案内容相关
2. 话题词要常见、宽泛，不要太偏或太具体
3. 每个话题词2-6个字
4. 必须正好4个话题词

示例：{theme}之：大学给老师送礼？家长别瞎忙，这两点更管用。#大学送礼  #大学日常  #家长建议  #师生关系"""

        # 添加重试机制
        max_retries = 2
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                print(f"  [DEBUG] 尝试生成摘要 (第 {retry_count + 1}/{max_retries + 1} 次)...")
                async with httpx.AsyncClient(timeout=600) as client:  # 增加到600秒超时
                    response = await client.post(
                        self.ollama_url,
                        json={
                            "model": self.local_model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            "stream": False,
                            "options": {
                                "temperature": 0.3,  # 降低随机性
                                "num_ctx": 2048,     # 上下文长度
                                "num_gpu": 1,        # 使用1个GPU
                                "num_thread": 4      # 使用4线程
                            },
                            "template": {
                                "enable_thinking": False  # 禁用Qwen3.5的思考模式
                            }
                        }
                    )

                if response.status_code == 200:
                    result = response.json()
                    message = result.get("message", {})
                    raw_summary = message.get("content", "").strip()
                    
                    if raw_summary:
                        # 清理特殊标记
                        import re
                        # 去掉 <|endoftext|> <|im_start|> 等标记
                        raw_summary = re.sub(r'<\|[^|]+\|>', '', raw_summary)
                        raw_summary = raw_summary.strip()
                        
                        # 去掉可能的引号
                        raw_summary = raw_summary.strip('"').strip("'")
                        
                        # 去掉可能的换行
                        raw_summary = raw_summary.replace('\n', ' ').replace('\r', '')
                        
                        # 去掉开头的 "主题之：" 如果已经有了主题前缀
                        # 检查是否重复了 theme
                        if raw_summary.startswith(f'{theme}之：{theme}之：'):
                            raw_summary = raw_summary[len(theme) + 4:]  # 去掉重复的 "大学学业篇之："
                        elif raw_summary.startswith(f'{theme}之：'):
                            pass  # 正常的
                        else:
                            # 如果AI没有按格式输出，手动构造
                            topic_words = self._extract_topic_words(raw_summary)
                            main_part = raw_summary
                            for tw in topic_words:
                                main_part = main_part.replace(tw, '').strip()
                            main_part = main_part.rstrip('。').rstrip('.').strip()
                            if main_part and not main_part.endswith('。'):
                                main_part += '。'
                            raw_summary = f"{theme}之：{main_part} {'  '.join(topic_words[:4])}"
                        
                        # 确保格式正确：去掉末尾可能多余的句号或标点
                        raw_summary = raw_summary.strip()
                        
                        # 提取话题词确保有4个
                        topic_words = self._extract_topic_words(raw_summary)
                        
                        # 如果话题词不够或不正确，用默认的
                        if len(topic_words) < 4:
                            # 从文案内容中智能提取
                            topic_words = self._extract_topics_from_content(content)
                        
                        # 确保话题词不重复
                        unique_topics = []
                        seen = set()
                        for tw in topic_words:
                            clean_tw = tw.strip().replace('#', '')
                            if clean_tw and clean_tw not in seen:
                                seen.add(clean_tw)
                                unique_topics.append(f"#{clean_tw}")
                        
                        while len(unique_topics) < 4:
                            extras = ["#日常", "#校园", "#成长", "#学习"]
                            for ex in extras:
                                if ex[1:] not in seen:
                                    seen.add(ex[1:])
                                    unique_topics.append(ex)
                                    if len(unique_topics) >= 4:
                                        break
                        
                        # 重新组装摘要行
                        # 提取标题部分（去掉话题词和多余的标点）
                        summary_line = raw_summary
                        for tw in unique_topics:
                            summary_line = summary_line.replace(tw, '')
                        summary_line = summary_line.strip()
                        # 去掉末尾的话题词分隔符等
                        summary_line = summary_line.rstrip('。').rstrip('.').strip()
                        if summary_line and not summary_line.endswith('。'):
                            summary_line += '。'
                        
                        # 避免重复主题前缀
                        if summary_line.startswith(f'{theme}之：{theme}之：'):
                            summary_line = summary_line[len(theme) + 4:]
                        elif summary_line.startswith(f'{theme}之：'):
                            pass
                        else:
                            summary_line = f"{theme}之：{title}。".replace('。。', '。')
                        
                        final_line = f"{summary_line} {'  '.join(unique_topics[:4])}"
                        
                        print(f"  [DEBUG] Final summary line: {final_line[:100]}")
                        
                        return f"{final_line}\n\n【文案全文】\n{content}"
                    else:
                        print(f"  [WARNING] AI返回空内容，尝试重试...")
                        retry_count += 1
                        if retry_count <= max_retries:
                            import asyncio
                            await asyncio.sleep(2)  # 等待2秒后重试
                            continue
                        return self._fallback_summary(content, theme)
                else:
                    print(f"  [INFO] 摘要服务返回状态码 {response.status_code}，尝试重试...")
                    retry_count += 1
                    if retry_count <= max_retries:
                        import asyncio
                        await asyncio.sleep(2)
                        continue
                    print(f"  [INFO] 摘要服务暂不可用，使用本地摘要方案")
                    return self._fallback_summary(content, theme)
                    
            except httpx.TimeoutException as e:
                last_error = e
                retry_count += 1
                print(f"  [WARNING] 摘要生成超时 (第 {retry_count}/{max_retries + 1} 次)，尝试重试...")
                if retry_count <= max_retries:
                    import asyncio
                    await asyncio.sleep(3)  # 超时后等待3秒再重试
                    continue
                break  # 重试次数用完，跳出循环
                
            except Exception as e:
                last_error = e
                retry_count += 1
                print(f"  [WARNING] 摘要生成错误 (第 {retry_count}/{max_retries + 1} 次): {type(e).__name__}: {e}")
                if retry_count <= max_retries:
                    import asyncio
                    await asyncio.sleep(2)
                    continue
                break  # 重试次数用完，跳出循环
        
        # 所有重试都失败了，使用备用方案
        import traceback
        print(f"  [ERROR] 摘要生成最终失败 ({type(last_error).__name__})，使用本地备用方案")
        return self._fallback_summary(content, theme)

    def _extract_topic_words(self, text: str) -> List[str]:
        """从文本中提取话题词"""
        import re
        # 匹配 #开头的话题词，2-8个字符（包含#号）
        pattern = r'#[\u4e00-\u9fa5a-zA-Z0-9]{1,7}'
        matches = re.findall(pattern, text)
        # 清理并去重
        cleaned = []
        seen = set()
        for m in matches:
            clean = m.strip()
            if clean not in seen and len(clean) > 1:
                seen.add(clean)
                cleaned.append(clean)
        return cleaned

    def _extract_topics_from_content(self, content: str) -> List[str]:
        """从文案内容中智能提取话题词 - 根据文案主题动态生成"""
        import re
        
        # 扩充版主题关键词映射（200+ 映射，覆盖更全面）
        topic_mappings = {
            # ========== 学业相关 ==========
            # 考试测评
            "考试": "#大学考试", "期末考": "#期末复习", "期中": "#期中考试", "补考": "#考试安排",
            "四六级": "#四六级备考", "英语": "#英语学习", "托福": "#留学考试", "雅思": "#雅思备考",
            "成绩": "#成绩提升", "绩点": "#绩点攻略", "GPA": "#GPA提升", "排名": "#成绩排名",
            "挂科": "#挂科应对", "重修": "#重修攻略",
            
            # 课程学习
            "选课": "#选课攻略", "学分": "#学分规划", "课堂": "#课堂学习", "上课": "#上课技巧",
            "逃课": "#逃课后果", "请假": "#请假攻略", "迟到": "#时间管理", "早退": "#作息管理",
            "笔记": "#学习笔记", "思维导图": "#高效学习", "预习": "#预习方法", "复习": "#复习技巧",
            "自习": "#自习方法", "图书馆": "#图书馆学习", "熬夜": "#熬夜学习", "通宵": "#作息管理",
            
            # 论文作业
            "论文": "#论文写作", "开题": "#论文开题", "查重": "#论文查重", "答辩": "#毕业答辩",
            "作业": "#大学作业", "实验报告": "#实验报告", "课程设计": "#课程设计",
            
            # 考研保研
            "考研": "#考研备战", "保研": "#保研攻略", "推免": "#推免攻略", "分数线": "#考研分数线",
            "复习": "#考研复习", "备考": "#备考攻略", "上岸": "#考研上岸", "二战": "#考研二战",
            "调剂": "#调剂攻略",
            
            # 学业规划
            "学业": "#学业规划", "学术": "#学术成长", "专业": "#专业选择", "转专业": "#转专业攻略",
            "辅修": "#辅修攻略", "双学位": "#双学位", "休学": "#休学攻略", "复学": "#复学安排",
            
            # ========== 生活相关 ==========
            # 宿舍生活
            "宿舍": "#宿舍生活", "室友": "#室友关系", "室友矛盾": "#宿舍矛盾", "宿舍卫生": "#宿舍卫生",
            "室友关系": "#室友关系", "室友睡觉": "#作息冲突", "宿舍限电": "#宿舍规定", "查寝": "#宿舍管理",
            
            # 食堂餐饮
            "食堂": "#校园食堂", "外卖": "#外卖日常", "美食": "#校园美食", "吃饭": "#饮食习惯",
            "夜宵": "#夜宵生活", "零食": "#零食日常", "减肥": "#健康生活", "节食": "#饮食管理",
            
            # 社交活动
            "社团": "#社团活动", "社团活动": "#社团经历", "社团面试": "#社团纳新", "学生会": "#学生会工作",
            "聚会": "#同学聚会", "轰趴": "#社交聚会", "团建": "#团队建设", "聚餐": "#社交聚餐",
            "KTV": "#娱乐活动", "酒吧": "#夜生活", "生日": "#生日聚会",
            
            # 恋爱关系
            "恋爱": "#大学恋爱", "表白": "#表白攻略", "分手": "#分手处理", "异地恋": "#异地恋",
            "单身": "#单身生活", "相亲": "#相亲经历", "约会": "#约会技巧", "脱单": "#脱单攻略",
            
            # 游戏娱乐
            "游戏": "#游戏生活", "原神": "#游戏日常", "王者": "#王者荣耀", "LOL": "#游戏社交",
            "吃鸡": "#游戏日常", "steam": "#游戏爱好者", "氪金": "#游戏消费", "段位": "#游戏段位",
            
            # 运动健康
            "运动": "#校园运动", "跑步": "#跑步健身", "健身": "#健身生活", "健身房": "#健身日常",
            "打球": "#球类运动", "篮球": "#篮球运动", "足球": "#足球运动", "游泳": "#游泳运动",
            "瑜伽": "#瑜伽健身", "减肥": "#减肥健身",
            
            # 消费理财
            "生活费": "#生活费管理", "省钱": "#省钱攻略", "赚钱": "#赚钱方式", "兼职": "#兼职经历",
            "实习工资": "#实习收入", "奖学金": "#奖学金攻略", "助学金": "#助学金申请", "贷款": "#助学贷款",
            "花呗": "#信用消费", "理财": "#理财入门",
            
            # ========== 规划相关 ==========
            # 大学阶段
            "大一": "#大一新生", "大二": "#大二阶段", "大三": "#大三生活", "大四": "#大四毕业",
            "毕业": "#大学毕业", "四年": "#大学四年", "新生": "#新生指南", "老生": "#学长学姐",
            
            # 时间规划
            "规划": "#大学规划", "计划": "#学习计划", "安排": "#时间安排", "时间管理": "#时间管理",
            "拖延": "#拖延症", "效率": "#效率提升", "目标": "#目标设定", "清单": "#待办清单",
            
            # 毕业去向
            "毕业": "#毕业规划", "毕业照": "#毕业回忆", "毕业论文": "#毕业设计", "毕业旅行": "#毕业旅行",
            "应届生": "#应届生", "往届生": "#往届生", "毕业季": "#毕业季",
            
            # ========== 就业相关 ==========
            # 求职准备
            "工作": "#就业准备", "就业": "#大学生就业", "求职": "#求职经验", "校招": "#校园招聘",
            "社招": "#社会招聘", "秋招": "#秋招备战", "春招": "#春招求职", "春招": "#春招备战",
            
            # 简历面试
            "简历": "#简历制作", "简历优化": "#简历提升", "面试": "#面试技巧", "面试技巧": "#面试经验",
            "自我介绍": "#自我介绍", "无领导小组": "#群面技巧", "结构化": "#面试准备",
            
            # 实习经历
            "实习": "#实习经验", "实习经历": "#实习收获", "实习生": "#职场体验", "转正": "#实习转正",
            "大厂": "#大厂实习", "offer": "#求职offer", "三方": "#三方协议", "毁约": "#求职违约",
            
            # 职业发展
            "职业": "#职业发展", "岗位": "#岗位选择", "行业": "#行业选择", "薪资": "#薪资待遇",
            "晋升": "#职业晋升", "跳槽": "#跳槽建议", "创业": "#创业经历", "考研": "#学历提升",
            
            # ========== 认知相关 ==========
            # 认知提升
            "认知": "#认知提升", "思维": "#思维提升", "格局": "#格局打开", "视野": "#视野拓展",
            "成长": "#个人成长", "成熟": "#走向成熟", "独立": "#独立成长",
            
            # 理解大学
            "真相": "#大学真相", "内幕": "#高校内幕", "揭秘": "#揭秘大学", "潜规则": "#校园潜规则",
            "现实": "#社会现实", "残酷": "#现实残酷", "道理": "#人生道理",
            
            # 校园现象
            "现象": "#校园现象", "内卷": "#内卷现象", "躺平": "#躺平生活", "摆烂": "#摆烂心态",
            "卷王": "#内卷日常", "凡尔赛": "#凡尔赛文学",
            
            # 深度思考
            "为什么": "#深度思考", "原因": "#原因分析", "本质": "#本质思考", "如何": "#方法论",
            "怎么办": "#问题解决", "要不要": "#选择纠结", "该不该": "#选择建议",
            
            # ========== 心理相关 ==========
            # 情绪管理
            "情绪": "#情绪管理", "心情": "#心情管理", "emo": "#情绪调节", "郁闷": "#情绪低落",
            "难过": "#情绪疏导", "压抑": "#压力信号", "崩溃": "#情绪崩溃", "大哭": "#情绪释放",
            
            # 压力释放
            "压力": "#压力释放", "焦虑": "#缓解焦虑", "紧张": "#缓解紧张", "不安": "#情绪不安",
            "压力山大": "#高压状态", "焦虑症": "#心理问题",
            
            # 心理问题
            "心理": "#心理健康", "抑郁": "#心理调节", "自闭": "#心理疏导", "社恐": "#社交恐惧",
            "孤独": "#孤独感", "寂寞": "#寂寞感", "失眠": "#睡眠改善", "熬夜": "#作息紊乱",
            
            # 心态调节
            "调节": "#自我调节", "释放": "#释放压力", "疏导": "#心理疏导", "健康": "#健康生活",
            "心态": "#心态调整", "积极": "#积极心态", "乐观": "#乐观生活", "正能量": "#正能量",
            "负能量": "#负面情绪", "悲观": "#悲观情绪", "自卑": "#自卑心理", "自信": "#自信建立",
            "玻璃心": "#心理建设", "钝感力": "#情绪管理",
            
            # ========== 关系相关 ==========
            # 师生关系
            "老师": "#师生关系", "导师": "#导师关系", "教授": "#教授印象", "辅导员": "#辅导员",
            "送礼": "#师生关系", "好处": "#利益关系",
            
            # 家长相关
            "家长": "#家长建议", "父母": "#父母沟通", "原生家庭": "#家庭关系", "催婚": "#家庭压力",
            "电话": "#家长联系", "生活费": "#家庭支持",
            
            # 同学关系
            "同学": "#同学关系", "朋友": "#大学友谊", "闺蜜": "#闺蜜情谊", "兄弟": "#兄弟情谊",
            "学长": "#学长学姐", "学姐": "#学姐学妹", "老乡": "#老乡关系",
            
            # ========== 其他 ==========
            "开学": "#开学季", "放假": "#放假安排", "假期": "#大学假期", "暑假": "#暑期生活",
            "寒假": "#寒假生活", "五一": "#假期安排", "国庆": "#假期安排", "中秋": "#节日生活",
            "考证": "#证书考取", "考公": "#考公上岸", "国考": "#公务员考试", "省考": "#省考备考",
            "入党": "#入党流程", "团支部": "#团支部", "学生会": "#学生会竞选", "班干部": "#班干部竞选",
            "投票": "#投票评选", "评优": "#评奖评优", "奖学金": "#奖学金评选", "助学金": "#助学金申请",
            "贫困生": "#贫困生", "补助": "#生活补助", "医保": "#校园医保", "保险": "#保险知识",
            "火车票": "#学生票", "学生证": "#学生优惠", "身份证": "#证件办理", "户口": "#户口迁移",
            "电脑": "#电脑推荐", "手机": "#手机推荐", "平板": "#平板学习", "iPad": "#无纸化学习",
            "耳机": "#耳机推荐", "键盘": "#外设推荐", "鼠标": "#外设推荐", "显示器": "#显示器推荐",
            "租房": "#租房攻略", "租房": "#校外租房", "宿舍神器": "#宿舍好物", "收纳": "#收纳技巧",
            "被子": "#宿舍收纳", "窗帘": "#宿舍装饰", "台灯": "#学习好物", "闹钟": "#起床困难",
            "快递": "#取快递", "外卖": "#点外卖", "网购": "#网购攻略", "退货": "#网购售后",
        }
        
        # 改进：扫描整个文案内容来匹配关键词，而不只是第一句
        matched_topics = []
        topic_counts = {}  # 记录每个话题词被匹配到的次数（用于优先级排序）
        
        for phrase, topic in topic_mappings.items():
            if phrase in content:
                # 统计匹配次数，次数越多优先级越高
                count = content.count(phrase)
                if topic not in topic_counts:
                    topic_counts[topic] = count
                    matched_topics.append(topic)
                else:
                    topic_counts[topic] += count
                if len(matched_topics) >= 4:
                    break
        
        # 按匹配次数排序，次数多的优先
        if matched_topics:
            matched_topics.sort(key=lambda t: topic_counts.get(t, 0), reverse=True)
        
        # 如果没有匹配到4个，补充通用话题词
        general_topics = ["#大学生活", "#校园日常", "#大学生", "#成长记录", "#经验分享", "#干货分享"]
        for gt in general_topics:
            if gt not in matched_topics and len(matched_topics) < 4:
                matched_topics.append(gt)
        
        return matched_topics[:4]

    def _fallback_summary(self, content: str, theme: str) -> str:
        """备用摘要生成（当Ollama不可用时）"""
        # 提取标题（只取到第一个标点符号为止）
        title = content.strip()
        for i, char in enumerate(title):
            if char in '。！？':
                title = title[:i+1]
                break
        
        # 清理标题：确保只有一个句号
        title = title.rstrip('。').rstrip('.').strip()
        if title and not title.endswith('。'):
            title += '。'
        
        if len(title) > 50:
            title = title[:50]

        # 从文案中智能提取话题词（根据文案主题动态生成）
        topic_words = self._extract_topics_from_content(content)
        
        return f"{theme}之：{title} {'  '.join(topic_words[:4])}\n\n【文案全文】\n{content}"


class SmartVideoGenerator:
    """智能视频生成器 - 完整流程"""

    def __init__(self, theme: str = None,
                 tts_mode: str = TTS_MODE,
                 use_comfyui: bool = True,
                 use_local_llm: bool = True,  # 改为默认使用本地模型
                 local_llm_model: str = "qwen3.5:9b",
                 auto_classify: bool = True):  # 新增：自动分类开关
        """
        初始化视频生成器

        Args:
            theme: 视频主题（可选，为None时自动识别）
            tts_mode: TTS模式
            use_comfyui: 是否使用ComfyUI生成图片
            use_local_llm: 是否使用本地Ollama模型生成分镜
            local_llm_model: 本地模型名称（默认qwen3.5:9b）
            auto_classify: 是否自动分类（默认开启）
        """
        self.user_theme = theme  # 保存用户指定的theme（如果有）
        self.theme = theme or "大学学业篇"  # 临时设置，后面会重新分类
        self.watermark_text = VIDEO_THEMES.get(self.theme, {}).get("watermark", self.theme)
        self.tts_mode = tts_mode
        self.use_comfyui = use_comfyui
        self.use_local_llm = use_local_llm
        self.local_llm_model = local_llm_model
        self.auto_classify = auto_classify
        self.ollama_url = "http://localhost:11434/api/chat"  # Ollama API 地址

        self.segmenter = TextSegmenter()
        self.shot_generator = ShotGenerator(use_local=use_local_llm, local_model=local_llm_model)

    async def _auto_detect_theme(self, content: str) -> str:
        """
        自动识别文案类别

        Args:
            content: 文案内容

        Returns:
            识别到的类别名称
        """
        if not self.auto_classify and self.user_theme:
            print(f"  [分类] 使用用户指定类别: {self.user_theme}")
            return self.user_theme

        if self.auto_classify:
            print("  [分类] 正在使用关键词匹配识别文案类别...")
            # 直接使用本地关键词匹配，不再启动 Ollama 服务
            # classify_theme 内部已实现高效的本地分类逻辑
            detected_theme = await self.shot_generator.classify_theme(content)
            return detected_theme
        else:
            return self.user_theme or "大学学业篇"

    async def generate(self, content: str,
                      output_name: str = None,
                      positive_prompt: str = None,
                      negative_prompt: str = None) -> Dict:
        """
        完整智能视频生成流程

        Args:
            content: 文案内容
            output_name: 输出文件名
            positive_prompt: 通用正向提示词
            negative_prompt: 通用负向提示词

        Returns:
            生成结果
        """
        import datetime as dt
        output_name = output_name or f"smart_{dt.datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 创建专用文件夹（同目录存放视频、封面、摘要）
        output_folder = VIDEOS_DIR / output_name
        output_folder.mkdir(parents=True, exist_ok=True)

        print("=" * 60)
        print(f"Smart Video Generation: {output_name}")
        print(f"  Output folder: {output_folder}")
        print("=" * 60)

        # Step 0: 自动识别文案类别
        print("\n[Progress] 2/10: 解析文案 / 自动分类")
        self.theme = await self._auto_detect_theme(content)
        self.watermark_text = VIDEO_THEMES.get(self.theme, {}).get("watermark", self.theme)
        print(f"  [分类] 最终使用类别: {self.theme}")

        # Step 1: AI分镜
        print("\n[Progress] 3/10: 生成分镜")
        shots = await self._generate_shots(content)
        if not shots:
            raise Exception("Failed to generate shots")
        print(f"  Generated {len(shots)} shots")

        # Step 2: 生成视频摘要（使用本地智能提取，速度快且稳定）
        summary_path = None
        summary = None
        print("\n[Progress] 4/10: 生成视频摘要")
        try:
            # 使用本地智能提取生成摘要（速度快，无需等待Ollama）
            summary = self.shot_generator._fallback_summary(content, self.theme)
            if summary:
                # 保存摘要到专用文件夹
                summary_path = str(output_folder / "summary.txt")
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(summary)
                print(f"  Summary saved: {summary_path}")
            else:
                print("  [WARNING] Summary generation returned empty")
        except Exception as e:
            print(f"  [WARNING] Summary generation failed: {type(e).__name__}: {e}")

        # Step 3: 生成音频（获取时间戳）
        print("\n[Progress] 5/10: 生成配音")
        await self._generate_audios(shots)
        print(f"  Audio generation complete")

        # Step 4: 生成图片
        print("\n[Progress] 6/10: 生成画面")
        # 默认负向提示词，严格禁止文字出现
        default_neg_prompt = (
            "low quality, blurry, bad anatomy, distorted, "
            "text, words, letters, numbers, symbols, alphabet, font, typography, "
            "signage, sign, billboard, poster with text, book with text, screen with text, "
            "written words, printed text, handwriting, caption, subtitle, watermark, logo with text"
        )
        neg_prompt = negative_prompt or default_neg_prompt
        await self._generate_images(shots, neg_prompt, output_name)
        print(f"  Image generation complete")

        # Step 5: 合成字幕
        print("\n[Progress] 7/10: 生成字幕")
        subtitle_path = await self._generate_subtitles(shots, output_name)
        print(f"  Subtitle: {subtitle_path}")

        # Step 6: 合成视频
        print("\n[Progress] 8/10: 合成视频")
        video_path = await self._synthesize_video(shots, subtitle_path, output_name, output_folder)
        print(f"  Video: {video_path}")

        # 所有任务完成后关闭 Ollama 服务
        if self.use_local_llm:
            self._stop_ollama_service()

        # Step 7: 生成封面
        print("\n[Progress] 9/10: 生成封面")
        cover_path = await self._generate_cover(shots, output_name, output_folder)
        if cover_path:
            print(f"  Cover: {cover_path}")
        else:
            print("  [WARNING] Cover generation skipped")

        # 统计
        total_duration = shots[-1].end_time if shots else 0

        print(f"\nComplete! Duration: {total_duration:.1f}s")
        print(f"  Video: {video_path}")
        print(f"  Subtitle: {subtitle_path}")
        if summary_path:
            print(f"  Summary: {summary_path}")
        if cover_path:
            print(f"  Cover: {cover_path}")

        return {
            "video_path": video_path,
            "subtitle_path": subtitle_path,
            "summary_path": summary_path,
            "cover_path": cover_path,
            "shots": [
                {
                    "cap": s.cap,
                    "image": s.image_path,
                    "audio": s.audio_path,
                    "start": s.start_time,
                    "end": s.end_time,
                    "duration": s.duration
                } for s in shots
            ],
            "total_duration": total_duration
        }

    async def _generate_shots(self, content: str) -> List[ShotSegment]:
        """生成分镜"""
        return await self.shot_generator.generate_shots(content)

    async def _generate_audios(self, shots: List[ShotSegment]):
        """逐段生成音频并记录时间戳"""
        qwen_tts = None

        # 如果使用 Qwen TTS，先加载一次模型
        if self.tts_mode == "qwen_tts":
            from utils.qwen_tts import get_model
            print("  [Qwen-TTS] 加载模型...")
            get_model(
                model_path=QWEN_TTS_SETTINGS.get("model_path"),
                device=QWEN_TTS_SETTINGS.get("device", "cuda")
            )
            qwen_tts = Qwen3TTSTTS(
                model_path=QWEN_TTS_SETTINGS.get("model_path"),
                device=QWEN_TTS_SETTINGS.get("device", "cuda")
            )
            print("  [Qwen-TTS] 模型加载完成")

        for shot in shots:
            try:
                audio_path, duration, words = await self._generate_single_audio(shot.cap, qwen_tts)
                shot.audio_path = audio_path
                shot.duration = duration
                shot.words = words
            except Exception as e:
                print(f"  [WARNING] Audio failed for shot {shot.index}: {e}")
                shot.audio_path = None
                shot.duration = 2.0  # 默认2秒
                shot.words = []

        # Qwen TTS 所有音频生成完毕，卸载模型释放显存
        if self.tts_mode == "qwen_tts" and qwen_tts is not None:
            from utils.qwen_tts import unload_model
            print("  [Qwen-TTS] 卸载模型，释放显存...")
            unload_model()

        # 计算时间戳
        current_time = 0.0
        for shot in shots:
            shot.start_time = current_time
            shot.end_time = current_time + shot.duration
            current_time = shot.end_time

    async def _generate_single_audio(self, text: str, qwen_tts=None) -> Tuple[str, float, List[Dict]]:
        """生成单段音频并返回时间戳信息"""
        import uuid

        if self.tts_mode == "gpt_sovits":
            audio_path = AUDIO_DIR / f"shot_{uuid.uuid4().hex[:8]}.wav"
            gpt_tts = GPTSoVITSTTS(api_url=GPT_SOVITS_SETTINGS["api_url"])

            # 克隆模式
            audio_result = gpt_tts.generate_with_timestamps(
                text=text,
                ref_audio_path=GPT_SOVITS_SETTINGS["ref_audio_path"],
                prompt_text=GPT_SOVITS_SETTINGS["prompt_text"],
                ref_lang=GPT_SOVITS_SETTINGS["ref_lang"],
                text_lang=GPT_SOVITS_SETTINGS["text_lang"],
                output_path=str(audio_path),
                speed=GPT_SOVITS_SETTINGS["speed"]
            )

        elif self.tts_mode == "qwen_tts":
            audio_path = AUDIO_DIR / f"shot_{uuid.uuid4().hex[:8]}.wav"

            # 语音克隆模式（复用已加载的模型）
            ref_audio_path = QWEN_TTS_SETTINGS.get("ref_audio_path")
            prompt_text = QWEN_TTS_SETTINGS.get("prompt_text")
            print(f"  [Qwen-TTS] 生成音频，参考音频: {ref_audio_path}")
            print(f"  [Qwen-TTS] 参考音频文本: {prompt_text[:100] if prompt_text else '(空)'}")
            audio_result = qwen_tts.generate_with_timestamps(
                text=text,
                ref_audio_path=ref_audio_path,
                prompt_text=prompt_text,
                speaker=QWEN_TTS_SETTINGS.get("speaker"),
                language=QWEN_TTS_SETTINGS.get("language", "Auto"),
                output_path=str(audio_path),
                speed=QWEN_TTS_SETTINGS.get("speed", 1.0)
            )

        else:
            audio_path = AUDIO_DIR / f"shot_{uuid.uuid4().hex[:8]}.mp3"
            tts = TTsgenerator(
                voice=EDGE_TTS_SETTINGS.get("voice", "zh-CN-XiaoxiaoNeural"),
                rate=EDGE_TTS_SETTINGS.get("rate", "+0%"),
                volume=EDGE_TTS_SETTINGS.get("volume", "+100%"),
                pitch=EDGE_TTS_SETTINGS.get("pitch", "+0Hz")
            )
            audio_result = await tts.generate_audio_with_timestamps(text, str(audio_path))

        # 获取实际时长
        duration = audio_result.get("duration", 3.0)
        words = audio_result.get("words", [])

        return str(audio_path), duration, words

    async def _generate_scene_and_keywords_with_ollama(self, shots: List[ShotSegment]):
        """
        使用 Ollama 本地模型生成场景描述和关键词

        Args:
            shots: 分镜列表

        Returns:
            更新后的分镜列表，包含 scene_prompt 和 desc_keywords
        """
        import httpx

        # 根据图片模型选择提示词语言
        if DEFAULT_IMAGE_MODEL == "zimage":
            lang = "中文"
            system_prompt = """# 角色
你是一位专业且富有创意的视频分镜描述专家，专注于大学教育视频分镜创作，能够将文案转化为生动、形象且符合极简风格要求的视频分镜描述。

## 技能: 创作视频分镜描述
1. 仔细研读用户提供的分段文案内容，全面理解其中的大学教育知识、情节以及人物情绪等关键要素。
2. 依据分段文案内容，精心设计一个统一协调的配图内容。
3. 分镜描述提示词desc_prompt：画面描述要精准、细致地体现文案情节细节以及多个人物和场景交互等方面，必须有交互场景，分镜描述必须包括人物和交互环境。
4. 提示词不少于80字。
5. 画面中绝对不能出现任何文字、字母、数字、符号。
6. 使用中式彩色插画风格描述。

分段文案如下：{{content}}

请直接输出场景描述，不要输出其他内容。"""
        else:
            lang = "英文"
            system_prompt = """# Role
You are a professional and creative video shot description expert, specializing in university education video shot creation. You can transform text into vivid, visual, and minimalist-style video shot descriptions.

## Skill: Create Video Shot Descriptions
1. Carefully study the provided segment text content to fully understand the university education knowledge, plot, and character emotions.
2. Based on the segment text, design a unified and coordinated illustration content.
3. Shot description (desc_prompt): The scene description should accurately and meticulously reflect the plot details and interactions between multiple characters and the environment. Must include interactive scenes, characters, and the interactive environment.
4. Description should be at least 80 words.
5. Absolutely no text, letters, numbers, or symbols should appear in the image.
6. Use Chinese color illustration style description.

Segment text: {{content}}

Please output only the scene description, nothing else."""

        # 关键词生成的系统提示（只生成1个关键词，用于图片上方）
        if DEFAULT_IMAGE_MODEL == "zimage":
            keyword_system_prompt = """# 角色
你是一位专业且富有创意的视频分镜关键词专家，专注于大学教育视频分镜创作。

## 技能: 生成分镜关键词
1. 仔细研读用户提供的分段文案内容，全面理解其中的核心概念和主题。
2. 根据分镜及完整视频文案，提供当前分镜合理的视频关键词，用于动态显示在视频画面上方。
3. 关键词为一个词语，不超过4个字。
4. 不要出现类似"互动引导"等通用词汇。
5. 关键词要精准反映分段文案的核心内容。

分段文案如下：{{content}}

请直接输出1个关键词，不要加任何前缀或后缀，不要输出其他内容。"""
        else:
            keyword_system_prompt = """# Role
You are a professional and creative video shot keyword expert, specializing in university education video shot creation.

## Skill: Generate Shot Keywords
1. Carefully study the provided segment text content to fully understand the core concepts and themes.
2. Based on the shot and the complete video text, provide appropriate video keywords for the current shot to be displayed above the video image.
3. The keyword should be a single term, no more than 4 characters or 2-4 words.
4. Avoid generic terms like "interactive guide".
5. The keyword should accurately reflect the core content of the segment text.

Segment text: {{content}}

Please output only 1 keyword, no prefixes or suffixes, nothing else."""

        # 启动 Ollama 服务
        ollama_started = self._start_ollama_service()
        if not ollama_started:
            print("  [Warning] Ollama service not available, using fallback")
            for shot in shots:
                cap = shot.cap.strip()
                shot.scene_prompt = self._extract_scene_from_cap_zh(cap) if DEFAULT_IMAGE_MODEL == "zimage" else self._extract_scene_from_cap_en(cap)
                kw_list = self._extract_keywords_from_cap(cap)
                shot.desc_keywords = [kw_list[0]] if kw_list else [""]
            return shots

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                for i, shot in enumerate(shots):
                    cap = shot.cap.strip()
                    print(f"  [Ollama] Generating scene + keywords for shot {i+1}/{len(shots)}...")

                    try:
                        # 1. 生成场景描述
                        # 将 {{content}} 替换为实际的分段文案
                        scene_system_prompt = system_prompt.replace("{{content}}", cap)
                        scene_response = await client.post(
                            self.ollama_url,
                            json={
                                "model": self.local_llm_model,
                                "messages": [
                                    {"role": "system", "content": scene_system_prompt},
                                    {"role": "user", "content": f"请根据上述分段文案生成场景描述。"}
                                ],
                                "stream": False,
                                "think": False  # 关闭思考功能，加快响应
                            }
                        )

                        if scene_response.status_code == 200:
                            scene_data = scene_response.json()
                            scene_text = scene_data.get("message", {}).get("content", "").strip()
                            if scene_text:
                                shot.scene_prompt = scene_text
                                print(f"    Scene: {scene_text[:60]}...")
                            else:
                                # 使用 fallback
                                shot.scene_prompt = self._extract_scene_from_cap_zh(cap) if DEFAULT_IMAGE_MODEL == "zimage" else self._extract_scene_from_cap_en(cap)
                                print(f"    [Fallback] Using preset scene")
                        else:
                            # 使用 fallback
                            shot.scene_prompt = self._extract_scene_from_cap_zh(cap) if DEFAULT_IMAGE_MODEL == "zimage" else self._extract_scene_from_cap_en(cap)
                            print(f"    [Fallback] Ollama scene error: {scene_response.status_code} - {scene_response.text[:100] if scene_response.text else 'empty'}")

                    except httpx.ConnectError as e:
                        print(f"  [ERROR] Ollama 连接失败: {e}")
                        shot.scene_prompt = self._extract_scene_from_cap_zh(cap) if DEFAULT_IMAGE_MODEL == "zimage" else self._extract_scene_from_cap_en(cap)
                    except httpx.TimeoutException as e:
                        print(f"  [ERROR] Ollama 请求超时: {e}")
                        shot.scene_prompt = self._extract_scene_from_cap_zh(cap) if DEFAULT_IMAGE_MODEL == "zimage" else self._extract_scene_from_cap_en(cap)
                    except Exception as e:
                        print(f"  [Warning] Ollama scene failed: {type(e).__name__}: {e}")
                        shot.scene_prompt = self._extract_scene_from_cap_zh(cap) if DEFAULT_IMAGE_MODEL == "zimage" else self._extract_scene_from_cap_en(cap)

                    try:
                        # 2. 生成关键词
                        # 将 {{content}} 替换为实际的分段文案
                        kw_system_prompt = keyword_system_prompt.replace("{{content}}", cap)
                        kw_response = await client.post(
                            self.ollama_url,
                            json={
                                "model": self.local_llm_model,
                                "messages": [
                                    {"role": "system", "content": kw_system_prompt},
                                    {"role": "user", "content": f"请根据上述分段文案生成关键词。"}
                                ],
                                "stream": False,
                                "think": False  # 关闭思考功能，加快响应
                            }
                        )

                        if kw_response.status_code == 200:
                            kw_data = kw_response.json()
                            kw_text = kw_data.get("message", {}).get("content", "").strip()
                            if kw_text:
                                # 解析关键词 - 只取1个
                                keyword = kw_text.strip().replace("\n", "").replace("关键词：", "").replace("keyword:", "")
                                if "、" in keyword:
                                    keyword = keyword.split("、")[0].strip()
                                if keyword:
                                    shot.desc_keywords = [keyword]
                                else:
                                    shot.desc_keywords = self._extract_keywords_from_cap(cap)
                                print(f"    Keyword: {shot.desc_keywords}")
                            else:
                                kw_list = self._extract_keywords_from_cap(cap)
                                shot.desc_keywords = [kw_list[0]] if kw_list else [""]
                                print(f"    [Fallback] Using preset keywords")
                        else:
                            kw_list = self._extract_keywords_from_cap(cap)
                            shot.desc_keywords = [kw_list[0]] if kw_list else [""]
                            print(f"    [Fallback] Ollama keyword error: {kw_response.status_code}")

                    except httpx.ConnectError:
                        kw_list = self._extract_keywords_from_cap(cap)
                        shot.desc_keywords = [kw_list[0]] if kw_list else [""]
                    except httpx.TimeoutException:
                        kw_list = self._extract_keywords_from_cap(cap)
                        shot.desc_keywords = [kw_list[0]] if kw_list else [""]
                    except Exception as e:
                        print(f"  [Warning] Ollama keyword failed: {type(e).__name__}: {e}")
                        kw_list = self._extract_keywords_from_cap(cap)
                        shot.desc_keywords = [kw_list[0]] if kw_list else [""]

                    # 避免请求过快
                    await asyncio.sleep(0.5)

        finally:
            # 确保停止 Ollama 服务
            self._stop_ollama_service()

        return shots

    def _start_ollama_service(self):
        """启动 Ollama 服务"""
        import subprocess
        import time
        import os

        try:
            # 检查服务是否已运行
            response = httpx.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                print("  [Ollama] Service already running")
                return True
        except Exception as e:
            print(f"  [Ollama] Service not responding: {type(e).__name__}")

        print("  [Ollama] Starting service...")
        try:
            # Ollama 安装路径（Windows 默认）
            ollama_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
            
            # 如果默认路径不存在，尝试从环境变量找
            if not os.path.exists(ollama_path):
                # 尝试使用 PATH 中的 ollama
                ollama_path = "ollama"
            
            # 启动 ollama serve
            subprocess.Popen(
                [ollama_path, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            # 等待服务启动（增加等待时间到30秒）
            print("  [Ollama] Waiting for service to be ready...")
            for i in range(30):
                time.sleep(1)
                try:
                    response = httpx.get("http://localhost:11434/api/tags", timeout=5)
                    if response.status_code == 200:
                        print(f"  [Ollama] Service started successfully (took {i+1}s)")
                        return True
                except Exception as e:
                    if i < 5:  # 前5秒只打印一次
                        print(f"  [Ollama] Still waiting... ({type(e).__name__})")
                    elif i == 5:
                        print("  [Ollama] Still waiting... (may take a while)")
                    continue
            print("  [Ollama] Service start timeout (30s)")
            return False
        except Exception as e:
            print(f"  [Ollama] Failed to start service: {e}")
            return False

    def _stop_ollama_service(self):
        """停止 Ollama 服务并释放显存"""
        import subprocess
        import time

        try:
            # 1. 先尝试优雅地让 Ollama 卸载当前模型（释放显存）
            try:
                httpx.post(
                    "http://localhost:11434/api/generate",
                    json={"model": self.local_llm_model, "prompt": "", "keep_alive": 0},
                    timeout=10
                )
            except Exception:
                pass

            # 2. 等待 llama-server 释放显存
            time.sleep(1)

            # 3. 结束 ollama 相关进程（包括可能残留的 llama-server）
            for proc_name in ["ollama.exe", "llama-server.exe"]:
                subprocess.run(
                    ["taskkill", "/IM", proc_name, "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            print("  [Ollama] Service stopped and VRAM released")
        except Exception as e:
            print(f"  [Ollama] Failed to stop service: {e}")

    async def _generate_images(self, shots: List[ShotSegment], negative_prompt: str, output_name: str = "default"):
        """逐段生成图片"""

        # 根据模型类型选择提示词语言
        if DEFAULT_IMAGE_MODEL == "zimage":
            # Z-Image-Turbo 使用中文提示词（对中文理解更好）
            STYLE_PREFIX = (
                "中式水彩插画，纯白色背景，手绘风格，三维，线条简洁流畅，"
                "大学生造型，人物生动自然，有场景互动感，配色对比鲜明"
            )
            # 中文负向提示词
            text_ban_keywords = (
                "低质量, 模糊, 坏结构, 扭曲, 变形, "
                "文字, 字母, 数字, 符号, 字幕, 标题, 水印, logo, signage, billboard, poster, caption"
            )
        else:
            # FLUX 使用英文提示词
            STYLE_PREFIX = (
                "Chinese watercolor illustration, pure white background, hand-drawn style, 3D, "
                "clean and smooth brushstrokes, university student character design, vivid and natural figures, "
                "interactive scene atmosphere, crisp and contrasting color scheme, "
                "multiple characters with detailed expressions and postures, "
                "engaging campus life scenes with environmental interaction"
            )
            # 英文负向提示词
            text_ban_keywords = (
                "text, words, letters, numbers, symbols, alphabet, font, typography, "
                "signage, sign, billboard, poster with text, book with text, screen with text, "
                "written words, printed text, handwriting, caption, subtitle, watermark, logo with text"
            )

        if negative_prompt:
            # 合并用户传入的负向提示词和文字禁止关键词
            if "text" not in negative_prompt.lower() and "文字" not in negative_prompt:
                negative_prompt = f"{negative_prompt}, {text_ban_keywords}"
        else:
            negative_prompt = f"low quality, blurry, bad anatomy, distorted, {text_ban_keywords}"

        if not self.use_comfyui:
            for shot in shots:
                shot.image_path = None
            return

        # Step 1: 使用 Ollama 生成场景描述和关键词
        if self.use_local_llm:
            print("\n  [Step 1/2] Generating scene descriptions and keywords with Ollama...")
            try:
                await self._generate_scene_and_keywords_with_ollama(shots)
            except Exception as e:
                print(f"  [Warning] Ollama scene/keyword generation failed: {e}")
                print(f"  [Info] Falling back to preset mappings")
                for shot in shots:
                    cap = shot.cap.strip()
                    shot.scene_prompt = self._extract_scene_from_cap_zh(cap) if DEFAULT_IMAGE_MODEL == "zimage" else self._extract_scene_from_cap_en(cap)
                    kw_list = self._extract_keywords_from_cap(cap)
                    shot.desc_keywords = [kw_list[0]] if kw_list else [""]

            # 关键：确保 Ollama 已完全停止并释放显存，再启动 ComfyUI
            print("  [Memory] Clearing Ollama residual VRAM...")
            self._stop_ollama_service()
        else:
            print("\n  [Step 1/2] Skipping Ollama (use_local_llm=False), using preset mappings...")
            for shot in shots:
                cap = shot.cap.strip()
                shot.scene_prompt = self._extract_scene_from_cap_zh(cap) if DEFAULT_IMAGE_MODEL == "zimage" else self._extract_scene_from_cap_en(cap)
                kw_list = self._extract_keywords_from_cap(cap)
                shot.desc_keywords = [kw_list[0]] if kw_list else [""]
        # 等待进程完全终止
        import time
        time.sleep(1)
        # 清理 CUDA 缓存
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                print(f"  [Memory] VRAM cleared, current: {torch.cuda.memory_allocated()/1e9:.1f}GB")
        except ImportError:
            pass

        # Step 2: 使用 ComfyUI 生成图片
        print("\n  [Step 2/2] Generating images with ComfyUI...")

        try:
            from utils.comfyui_api import get_comfyui_api
            api = get_comfyui_api()

            if not api.is_alive():
                print("  [WARNING] ComfyUI not available, generating fallback images")
                for i, shot in enumerate(shots):
                    fallback_path = await self._create_default_image(
                        [shot], f"{output_name}_shot_{i}", width=1120, height=840
                    )
                    shot.image_path = fallback_path
                return

            for i, shot in enumerate(shots):
                print(f"  Generating image {i+1}/{len(shots)}...")

                # 使用 Ollama 生成的 scene_prompt
                scene_prompt = getattr(shot, 'scene_prompt', None)
                if not scene_prompt:
                    # Fallback
                    scene_prompt = self._extract_scene_from_cap_zh(shot.cap) if DEFAULT_IMAGE_MODEL == "zimage" else self._extract_scene_from_cap_en(shot.cap)

                prompt = f"{STYLE_PREFIX}, {scene_prompt}"
                print(f"    Prompt: {prompt[:80]}...")

                result = api.generate_image(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=1120,
                    height=840,
                    steps=IMAGE_SETTINGS.get("steps", 8 if DEFAULT_IMAGE_MODEL == "zimage" else 25),
                    seed=0,
                    output_path=str(IMAGES_DIR),
                    model=IMAGE_SETTINGS.get("model"),
                    vae=IMAGE_SETTINGS.get("vae"),
                    clip1=IMAGE_SETTINGS.get("text_encoder" if DEFAULT_IMAGE_MODEL == "zimage" else "clip1"),
                    clip2=IMAGE_SETTINGS.get("clip2"),
                    model_type=IMAGE_SETTINGS.get("model_type", DEFAULT_IMAGE_MODEL)
                )

                if result["success"] and result.get("saved_paths"):
                    shot.image_path = result["saved_paths"][0]
                else:
                    print(f"    [WARNING] Image generation failed, using fallback")
                    fallback_path = await self._create_default_image(
                        [shot], f"{output_name}_shot_{i}", width=1120, height=840
                    )
                    shot.image_path = fallback_path

            # 所有图片生成完成后统一释放 ComfyUI 显存
            print("  [Memory] Freeing ComfyUI VRAM after all images generated...")
            free_result = api.free_memory()
            print(f"  [Memory] {free_result.get('message', 'VRAM free result unknown')}")

        except Exception as e:
            print(f"  [ERROR] Image generation error: {e}")
            for i, shot in enumerate(shots):
                if not shot.image_path:
                    fallback_path = await self._create_default_image(
                        [shot], f"{output_name}_shot_{i}", width=1120, height=840
                    )
                    shot.image_path = fallback_path

    def _extract_scene_from_cap_en(self, cap: str) -> str:
        """
        从字幕文案中提取详细的英文画面描述
        生成至少80字的详细场景，包含人物和交互场景
        """
        cap = cap.strip()

        # 详细的场景映射表（英文描述，至少80字）
        scene_map = {
            "大一大二可以提前修大三大四的学分": "A university student standing confidently in front of a large calendar or schedule board, pointing at future semesters with an excited expression, books and laptops scattered on a desk nearby, showing academic planning and time management, two students discussing course selection together in a campus library setting",
            "很多同学都老老实实按着推荐课表走": "Multiple college students sitting in a traditional classroom following the standard curriculum, some looking bored while a few students are actively taking notes, a professor lecturing at the front of the room, classmates exchanging confused glances about their academic progress",
            "没课的时候就在宿舍躺平或者打游戏": "A group of college students relaxing in a dorm room, one lying on the bed scrolling through phone, another playing video games enthusiastically on a computer desk, scattered snacks and energy drinks on the table, lazy afternoon sunlight streaming through the window",
            "老学长告诉你们这其实浪费了": "A senior student with confident posture sharing advice with younger students, gesturing meaningfully while explaining the importance of time management, the younger students listening attentively with surprised expressions, books and coffee cups on the table creating a warm study atmosphere",
            "最好的战略机遇期": "A dramatic scene showing a university student at a crossroads, looking at a split path with one direction leading to a bright successful future and another to an uncertain 普通 path, alarm clock and calendar elements emphasizing the importance of timing, mentor figure pointing toward the better direction with encouraging smile",
            "学校教务系统没有设置严格的年级壁垒": "University administrative office scene showing a friendly counselor helping students with course registration, computer screen displaying course selection system interface, students from different grades discussing together, bulletin board with course information and requirement charts visible",
            "低年级精力最充沛的时候": "Energetic young university students participating in various activities, one studying intensely at a desk with high concentration, another exercising in campus sports field, sunrise background symbolizing new beginnings and full energy, laptop and notebooks showing active learning state",
            "把大三甚至大四的选修课给提前修了": "A motivated student completing advanced elective courses early, textbooks from third and fourth year sitting proudly on the desk, a course completion certificate or academic planner showing progress, determined expression while studying ahead of schedule, campus scenery visible through the window",
            "大三下学期和大四的时候拥有绝对的主动权": "A confident final-year student graduating with honors, wearing graduation gown holding diploma, standing in front of university gate with proud posture, relaxed smile while peers around are still stressed about requirements, career or further education offers displayed in the background",
            "绝对的主动权": "A strategic board meeting scene with a student planning their academic path, chess pieces or planning charts showing calculated decisions, other students in chaos while this student stays calm and in control, success indicators like trophies certificates or job offers surrounding the scene"
        }

        # 精确匹配
        for key, scene in scene_map.items():
            if key in cap:
                return scene

        # 模糊匹配关键词
        if any(k in cap for k in ["学分", "选课", "提前", "修"]):
            return "A serious university student carefully planning their course schedule on a computer, course catalog open on the desk, multiple year textbooks stacked neatly, planning chart showing academic roadmap with milestone markers, confident expression while organizing future academic goals"
        elif any(k in cap for k in ["宿舍", "躺平", "游戏", "打游戏"]):
            return "A college dorm room scene with relaxed atmosphere, students engaged in leisure activities like gaming and phone scrolling, messy but comfortable living space with snacks and drinks, contrast between lazy relaxation and productivity, some students looking unfulfilled while others enjoying free time"
        elif any(k in cap for k in ["老学长", "学长"]):
            return "A wise senior student sharing valuable experience with younger undergraduates, warm conversation atmosphere in campus café or study area, meaningful hand gestures while giving advice, attentive expressions from younger students taking mental notes, books and coffee creating intellectual friendship atmosphere"
        elif any(k in cap for k in ["战略", "机遇", "时机"]):
            return "A symbolic scene of opportunity and timing, university student seizing the perfect moment like catching a flying paper airplane marked with opportunity, calendar pages turning dramatically, decisive action pose with confident expression, background showing progression from confusion to clarity"
        elif any(k in cap for k in ["精力", "充沛", "活力"]):
            return "Full of energy young university student tackling multiple tasks simultaneously, morning sunrise or bright lighting symbolizing peak energy hours, efficient study session with excellent focus, sports and academic activities combined in dynamic composition, productive atmosphere with planners and achievement lists"
        elif any(k in cap for k in ["主动权", "主动", "控制"]):
            return "A empowered university student taking control of their academic destiny, standing at center with strategic planning materials around, other students following blindly while this student leads confidently, success indicators like completed requirements and achieved goals displayed proudly, future roadmap showing clear direction"
        elif any(k in cap for k in ["毕业", "大四", "大三"]):
            return "Final year university student in graduation attire with proud confident stance, surrounding peers in different states of academic stress, completion certificates and employer contacts visible, university campus landmark background symbolizing achievement, relaxed smile showing readiness for next chapter"
        elif any(k in cap for k in ["安逸", "滋润", "舒服"]):
            return "Comfortable but potentially misleading college life scene, student enjoying easy going campus life with leisure activities, contrast between current comfort and future challenges appearing in background shadows, friends hanging out happily without concerns, calendar showing approaching deadlines unnoticed"
        elif any(k in cap for k in ["按着", "推荐", "课表", "老老实实"]):
            return "Students following standard curriculum without questioning, everyone wearing similar expressions of compliance, traditional classroom setting with standard textbook materials, contrast between rule followers and independent thinkers in the same scene, clock showing time passing while progress remains minimal"

        # 默认场景：基于字幕内容生成描述
        # 提取关键词构建场景
        keywords = self._extract_keywords_from_cap(cap)

        return f"A vivid Chinese university campus scene capturing the essence of: '{cap}', featuring engaged student characters with natural poses and expressions, interactive environment with campus elements like desks, books, and outdoor settings, hand-drawn textbook illustration style with clean lines and vibrant contrasting colors, emotional narrative moment showing the meaning behind the message, absolutely no text or words or letters or numbers in the image"

    def _extract_scene_from_cap_zh(self, cap: str) -> str:
        """
        从字幕文案中提取详细的中文画面描述
        用于 Z-Image-Turbo 模型，中文理解效果更好
        """
        cap = cap.strip()

        # 详细的中文场景映射表
        scene_map = {
            "大一大二可以提前修大三大四的学分": "一个自信的大学生站在巨大的日历和计划板前，兴奋地指向未来学期的课程，手里拿着书籍和平板电脑，展现学业规划和时间管理的场景，两个学生在图书馆里边讨论选课",
            "很多同学都老老实实按着推荐课表走": "多个大学生坐在传统教室里按照标准课程表学习，有些看起来无聊而一些学生在认真做笔记，教授在讲台前授课，同学们互相交换困惑的眼神",
            "没课的时候就在宿舍躺平或者打游戏": "一群大学生在宿舍放松，一个躺在床上刷手机，另一个在电脑桌前热情地玩游戏，桌上散落着零食和饮料，懒洋洋的午后阳光从窗户照进来",
            "老学长告诉你们这其实浪费了": "一个姿态自信的学长正在向低年级学生分享建议，用手示意有意义地解释时间管理的重要性，低年级学生专注地听讲露出惊讶的表情，桌上的书籍和咖啡杯营造出温馨的学习氛围",
            "最好的战略机遇期": "戏剧性的场景展示一个大学生站在十字路口，看着一条通向光明未来的路和另一条不确定的路，闹钟和日历强调时机的重要性，导师用鼓励的微笑指向更好的方向",
            "学校教务系统没有设置严格的年级壁垒": "大学教务办公室场景，友善的辅导员帮助学生选课，电脑屏幕显示选课系统界面，不同年级的学生一起讨论，黑板报上可见课程信息和需求图表",
            "低年级精力最充沛的时候": "充满活力的大学生参与各种活动，一个在桌前专注地学习，另一个在校园运动场锻炼，象征新开始和充沛精力的日出背景，平板电脑和笔记本展示积极学习的状态",
            "把大三甚至大四的选修课给提前修了": "一个积极的学生提前完成高级选修课，大三和大四的教科书骄傲地摆在桌上，课程完成证书或学业计划表显示进度，坚定的表情表示超前学习，窗外可见校园风景",
            "大三下学期和大四的时候拥有绝对的主动权": "一个大四学生以优异成绩毕业，穿着毕业礼服自信地站着，身边的同学还在为学业要求而压力山大，职业或深造offer在背景中展示",
            "绝对的主动权": "一个战略性场景，学生规划学业路径，其他同学迷茫而这个学生冷静掌控，成功指标如奖杯证书或工作offer围绕场景"
        }

        # 精确匹配
        for key, scene in scene_map.items():
            if key in cap:
                return scene

        # 模糊匹配关键词
        if any(k in cap for k in ["学分", "选课", "提前", "修"]):
            return "一个认真规划课程表的大学生，电脑上打开选课系统，桌上堆着多学年教科书，规划图显示学业路线图和时间节点，自信的表情组织未来的学业目标"
        elif any(k in cap for k in ["宿舍", "躺平", "游戏", "打游戏"]):
            return "大学宿舍场景，放松的氛围，学生进行游戏和刷手机等休闲活动，杂乱但舒适的居住空间，零食和饮料散落，对比慵懒放松和生产力的差异"
        elif any(k in cap for k in ["老学长", "学长"]):
            return "一个智慧的学长向本科生分享宝贵经验，校园咖啡厅或学习区的温馨对话氛围，做手势给出建议，低年级学生认真听取做笔记，书籍和咖啡营造知识友谊氛围"
        elif any(k in cap for k in ["战略", "机遇", "时机"]):
            return "机会和时机的象征场景，大学生像抓住带有机会标记的纸飞机一样抓住最佳时机，日历页戏剧性翻动，自信表情的果断行动姿势，背景从困惑到清晰的过渡"
        elif any(k in cap for k in ["精力", "充沛", "活力"]):
            return "精力充沛的大学生同时处理多项任务，象征高峰能量小时的清晨阳光或明亮照明，高效学习的专注状态，运动和学术活动动态结合，生产力的氛围与成就清单"
        elif any(k in cap for k in ["主动权", "主动", "控制"]):
            return "一个有权力的大学生活掌控自己的学业命运，站在战略规划资料中间，其他学生盲目跟随而这个学生自信引领，完成的要求和达成的目标作为成功指标骄傲展示，未来的路线图显示清晰方向"
        elif any(k in cap for k in ["毕业", "大四", "大三"]):
            return "大四学生穿毕业礼服骄傲自信的姿态，周围的同学处于不同学业压力状态，完成的证书和雇主联系方式可见，大学校园地标背景象征成就，微笑展示为下一章做好准备"
        elif any(k in cap for k in ["安逸", "滋润", "舒服"]):
            return "舒适但可能误导的大学生活场景，学生享受悠闲的校园生活与休闲活动，当前舒适和未来挑战形成对比，背景阴影中出现，朋友快乐地闲逛没有担忧，日历显示未被注意的即将到来的截止日期"
        elif any(k in cap for k in ["按着", "推荐", "课表", "老老实实"]):
            return "学生不问问题地遵循标准课程，每个人戴着相似的顺从表情，传统课堂设置与标准教科书材料，规则遵循者和独立思考者在同一场景形成对比，时钟显示时间流逝而进步仍然微小"

        # 默认场景：基于字幕内容生成描述
        keywords = self._extract_keywords_from_cap(cap)
        keyword_str = "、".join(keywords) if keywords else cap[:10]

        return f"生动的大学生校园场景，画面呈现：'{cap}'，特征是参与的学生角色姿态自然表情丰富，互动环境包含校园元素如课桌、书籍和户外场景，手绘教科书插图风格线条干净色彩鲜艳，情感叙事时刻展示信息背后的意义，画面中绝对不能包含任何文字、字母、数字或符号"

    def _extract_keywords_from_cap(self, cap: str, full_content: str = None) -> List[str]:
        """
        从字幕文案中提取关键词列表

        规则：
        1. 每个词不超过4个字，最多3个词
        2. 关键词不允许重复
        3. 根据当前分镜内容智能判断，不适合就不提供
        4. 不出现"互动引导"等无关词汇

        Args:
            cap: 当前分镜字幕文案
            full_content: 完整视频文案（可选）

        Returns:
            关键词列表（最多3个词）
        """
        cap = cap.strip()
        keywords = []

        # 预设关键词映射表（根据"提前修学分"主题定制）
        keyword_map = {
            # 主题核心词
            "提前修学分": ["提前修学分", "学分规划"],
            "学分": ["学分", "选课"],
            "修课": ["修课", "选课"],
            "选课": ["选课", "学分"],

            # 行动类
            "实习": ["实习", "实践经验"],
            "大三": ["大三", "关键期"],
            "大四": ["大四", "毕业季"],
            "毕业": ["毕业", "就业"],
            "考研": ["考研", "升学"],
            "就业": ["就业", "职业发展"],

            # 状态类
            "主动权": ["主动权", "掌控感"],
            "战略": ["战略", "规划"],
            "规划": ["规划", "目标"],
            "精力": ["精力充沛", "黄金期"],
            "时间": ["时间管理", "效率"],
            "安逸": ["舒适区", "警惕"],
            "躺平": ["躺平", "反思"],

            # 方法类
            "课表": ["课表", "选课攻略"],
            "教务": ["教务系统", "规则"],
            "推荐": ["推荐", "参考"],
            "按着": ["按部就班", "突破"],

            # 建议类
            "老学长": ["学长建议", "经验分享"],
            "学长": ["学长建议", "过来人"],
            "告诉": ["建议", "提醒"],
            "浪费": ["避免浪费", "珍惜"],

            # 结果类
            "王炸": ["王炸", "大招"],
            "最好": ["最优", "策略"],
            "战略机遇期": ["机遇期", "窗口期"],
            "绝对": ["绝对", "优势"],
        }

        # 优先级匹配：精确匹配优先
        found_keywords = []
        for key, kws in keyword_map.items():
            if key in cap:
                for kw in kws:
                    if kw not in found_keywords and len(kw) <= 4:
                        found_keywords.append(kw)
                        if len(found_keywords) >= 3:
                            return found_keywords

        # 如果没有预设匹配，动态提取
        if not found_keywords:
            # 提取有实质意义的名词/动词短语
            meaningful_words = []

            # 方法1：提取4字短语
            for i in range(len(cap) - 3):
                phrase = cap[i:i+4]
                # 跳过包含语气词和标点的
                if all(c not in "，。、！？；：""''（）的了是在和" for c in phrase):
                    # 优先选择包含关键词的
                    if any(c in phrase for c in "学业规划实习就业考研升学技能证书"):
                        meaningful_words.append(phrase)

            # 方法2：提取2-3字短语
            for i in range(len(cap) - 1):
                phrase = cap[i:i+2]
                if all(c not in "，。、！？；：""''（）的了是在和有个" for c in phrase):
                    if any(c in phrase for c in "学分选课实习就业考研规划"):
                        meaningful_words.append(phrase)

            # 去重并限制长度
            seen = set()
            for word in meaningful_words:
                word = word[:4]  # 不超过4字
                if word not in seen and word not in found_keywords:
                    seen.add(word)
                    found_keywords.append(word)
                    if len(found_keywords) >= 3:
                        break

        # 如果仍没有，返回空列表（不显示关键词）
        if not found_keywords:
            return []

        return found_keywords[:3]

    async def _generate_subtitles(self, shots: List[ShotSegment], output_name: str) -> str:
        """生成字幕文件"""
        # 收集所有时间轴，优先使用 TTS 返回的时间戳
        all_words = []
        for shot in shots:
            words = self._get_words_from_shot(shot)
            if not words:
                # 如果时间戳为空，回退到均匀分配
                words = self._estimate_words_timing(shot)
            all_words.extend(words)

        subtitle_path = AUDIO_DIR / f"{output_name}.ass"
        generate_ass_subtitle(all_words, str(subtitle_path))
        return str(subtitle_path)

    def _get_words_from_shot(self, shot: ShotSegment) -> List[Dict]:
        """从音频结果获取单词时间轴

        优先使用 TTS 返回的真实/估算时间戳，并叠加到 shot 的全局时间轴上。
        如果时间戳不可用，则回退到均匀分配。
        """
        words = []
        cap = shot.cap
        duration = shot.duration
        char_count = len(cap)

        # 优先使用 TTS 返回的时间戳（Edge-TTS 为真实时间戳，其余为模型估算）
        shot_words = getattr(shot, "words", None)
        if shot_words:
            for w in shot_words:
                words.append({
                    "word": w.get("word", ""),
                    "start": shot.start_time + w.get("start", 0.0),
                    "end": shot.start_time + w.get("end", 0.0),
                })
            return words

        # 回退：按字符均匀分配时间
        for i, char in enumerate(cap):
            start_ratio = i / char_count if char_count > 0 else 0
            end_ratio = (i + 1) / char_count if char_count > 0 else 1

            words.append({
                "word": char,
                "start": shot.start_time + start_ratio * duration,
                "end": shot.start_time + end_ratio * duration
            })

        return words

    def _estimate_words_timing(self, shot: ShotSegment) -> List[Dict]:
        """估算单词时间轴"""
        words = []
        cap = shot.cap
        duration = shot.duration
        char_count = len(cap)

        for i, char in enumerate(cap):
            start_ratio = i / char_count if char_count > 0 else 0
            end_ratio = (i + 1) / char_count if char_count > 0 else 1

            words.append({
                "word": char,
                "start": shot.start_time + start_ratio * duration,
                "end": shot.start_time + end_ratio * duration
            })

        return words

    async def _generate_cover(self, shots: List[ShotSegment], output_name: str, output_folder: Path = None) -> Optional[str]:
        """
        生成视频封面

        使用第一张生成的图片作为背景，创建9:16竖屏封面：
        - 顶部黑色区域
        - 中间红色"大学xx篇之"
        - 下方白色主题文字
        - 背景是AI生成的图片（模糊处理）

        Args:
            shots: 分镜列表
            output_name: 输出文件名
            output_folder: 专用输出文件夹

        Returns:
            封面路径，失败返回None
        """
        try:
            # 找第一张有效的图片作为背景
            background_image = None
            main_title = ""

            for shot in shots:
                if shot.image_path and Path(shot.image_path).exists():
                    background_image = shot.image_path
                    # 提取标题（第一句完整的话）
                    if main_title and not main_title.endswith(('。', '！', '？')):
                        for i, char in enumerate(shot.cap):
                            if char in '。！？':
                                main_title = shot.cap[:i+1]
                                break
                    else:
                        main_title = shot.cap
                    break

            if not background_image:
                print("  [WARNING] No background image found for cover")
                return None

            # 提取主标题（文案第一句话）
            if not main_title:
                if shots:
                    first_cap = shots[0].cap if shots else ""
                    for i, char in enumerate(first_cap):
                        if char in '。！？':
                            main_title = first_cap[:i+1]
                            break
                    if not main_title:
                        # 如果没有标点，在合适的位置截断（保留完整词语）
                        cutoff = len(first_cap)
                        for i, char in enumerate(first_cap):
                            if char in '的地得着了过' and i >= 15:
                                cutoff = i + 1
                                break
                        if cutoff < len(first_cap):
                            main_title = first_cap[:cutoff]
                        else:
                            main_title = first_cap[:25] if first_cap else ""

            # 生成封面 - 保存到专用文件夹
            cover_generator = CoverGenerator(theme=self.watermark_text)
            if output_folder is None:
                output_folder = VIDEOS_DIR / output_name
            cover_path = str(output_folder / "cover.png")

            cover_generator.create_cover(
                background_image=background_image,
                category=self.watermark_text,
                main_title=main_title,
                output_path=cover_path
            )

            print(f"  Cover generated: {cover_path}")
            return cover_path

        except Exception as e:
            print(f"  [WARNING] Cover generation failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _synthesize_video(self, shots: List[ShotSegment],
                              subtitle_path: str,
                              output_name: str,
                              output_folder: Path = None) -> str:
        """合成最终视频 - 使用大学模板"""
        from utils.university_template import create_university_video

        # 视频保存路径：专用文件夹
        if output_folder is None:
            output_folder = VIDEOS_DIR / output_name
        video_path = output_folder / "video.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)

        # 合并音频
        merged_audio = await self._merge_audios(shots, output_name)

        # 准备分镜数据
        shot_data = []
        for i, shot in enumerate(shots):
            # 交替左右位置
            position = "left" if i % 2 == 0 else "right"

            # 获取关键词（从desc_keywords取第一个，或从字幕截取）
            keyword = ""
            if shot.desc_keywords and len(shot.desc_keywords) > 0:
                keyword = shot.desc_keywords[0]
            elif len(shot.cap) >= 4:
                keyword = shot.cap[:4]

            shot_data.append({
                "image_path": shot.image_path,
                "keyword": keyword,
                "subtitle": shot.cap,  # 完整字幕（不截断）
                "duration": shot.duration
            })

        # 提取主标题（文案第一句话）
        main_title = ""
        if shots:
            # 从第一句字幕中提取第一句完整的话作为标题
            first_cap = shots[0].cap if shots else ""
            # 找到第一个句号、问号或感叹号
            for i, char in enumerate(first_cap):
                if char in '。！？':
                    main_title = first_cap[:i+1]
                    break
            if not main_title and first_cap:
                # 如果没有标点，在合适的位置截断（保留完整词语）
                # 优先在助词处截断：的地得着了过
                cutoff = len(first_cap)
                for i, char in enumerate(first_cap):
                    if char in '的地得着了过' and i >= 15:
                        cutoff = i + 1
                        break
                if cutoff < len(first_cap):
                    main_title = first_cap[:cutoff]
                else:
                    main_title = first_cap[:25]  # 最多取前25字，保留完整语义

        # 使用模板创建视频
        try:
            create_university_video(
                shots=shot_data,
                theme=self.watermark_text,
                audio_path=merged_audio,
                output_path=str(video_path),
                main_title=main_title
            )
            print(f"  Video saved: {video_path}")
        except Exception as e:
            print(f"  [ERROR] Template video failed: {e}")
            # 回退到简单模式
            await self._synthesize_video_simple(shots, subtitle_path, output_name, output_folder)

        return str(video_path)

    async def _synthesize_video_simple(self, shots: List[ShotSegment],
                                     subtitle_path: str,
                                     output_name: str,
                                     output_folder: Path = None) -> str:
        """简单视频合成（备用）"""
        import subprocess
        import shutil
        from pathlib import Path

        # 视频保存路径：专用文件夹
        if output_folder is None:
            output_folder = VIDEOS_DIR / output_name
        video_path = output_folder / "video.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)

        # 检查有效的分镜（有图片）
        valid_shots = [s for s in shots if s.image_path]

        if not valid_shots:
            default_img = await self._create_default_image(shots, output_name)
            valid_shots = [type('obj', (object,), {
                'image_path': default_img,
                'start_time': 0,
                'end_time': shots[-1].end_time if shots else 10
            })()]

        width = VIDEO_SETTINGS.get("width", 1080)
        height = VIDEO_SETTINGS.get("height", 1920)

        # 逐段生成视频片段
        segment_files = []
        for i, shot in enumerate(valid_shots):
            seg_path = IMAGES_DIR / f"seg_{i}_{output_name}.mp4"
            seg_duration = shot.end_time - shot.start_time

            # 准备音频输入：有音频用音频文件，无音频用 lavfi anullsrc 生成静音
            if shot.audio_path and Path(shot.audio_path).exists():
                audio_input = ["-i", shot.audio_path]
                audio_filter = "volume=2.0"
            else:
                audio_input = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
                audio_filter = "volume=0.0"

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", shot.image_path,
            ] + audio_input + [
                "-t", str(seg_duration),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},format=yuv420p",
                "-af", audio_filter,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-profile:v", "high",
                "-level", "4.0",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                str(seg_path)
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result.returncode == 0:
                    segment_files.append(str(seg_path))
                else:
                    print(f"  [ERROR] Segment {i} failed: {result.stderr[:200] if result.stderr else 'unknown'}")
            except Exception as e:
                print(f"  [ERROR] Segment {i} error: {e}")

        # 合并片段
        if len(segment_files) > 1:
            concat_list = AUDIO_DIR / f"{output_name}_concat.txt"
            with open(concat_list, 'w') as f:
                for seg_file in segment_files:
                    f.write(f"file '{seg_file}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(video_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                shutil.copy(segment_files[0], str(video_path))
        elif len(segment_files) == 1:
            shutil.copy(segment_files[0], str(video_path))

        print(f"  Video saved: {video_path}")
        return str(video_path)

    def generate_sync(self, content: str, output_name: str = None,
                    positive_prompt: str = None, negative_prompt: str = None) -> Dict:
        """同步版本"""
        return asyncio.run(self.generate(content, output_name, positive_prompt, negative_prompt))

    async def _create_default_image(self, shots: List[ShotSegment], output_name: str,
                                     width: int = None, height: int = None) -> str:
        """创建默认图片

        Args:
            shots: 分镜列表（用于提取文案）
            output_name: 输出文件名
            width: 图片宽度，默认使用视频宽度
            height: 图片高度，默认使用视频高度
        """
        from PIL import Image, ImageDraw, ImageFont

        if width is None:
            width = VIDEO_SETTINGS.get("width", 1080)
        if height is None:
            height = VIDEO_SETTINGS.get("height", 1920)

        img_path = IMAGES_DIR / f"{output_name}_default.png"
        # 使用温暖的浅色调背景，避免 UniversityVideoTemplate 中灰占位框的廉价感
        img = Image.new('RGB', (width, height), color=(245, 247, 250))
        draw = ImageDraw.Draw(img)

        # 尝试加载中文字体，优先使用系统黑体
        font_size_title = max(32, min(60, width // 18))
        font_size_body = max(24, min(40, width // 24))
        try:
            font_title = ImageFont.truetype("simhei.ttf", font_size_title)
            font_body = ImageFont.truetype("simhei.ttf", font_size_body)
        except:
            try:
                font_title = ImageFont.truetype("msyh.ttc", font_size_title)
                font_body = ImageFont.truetype("msyh.ttc", font_size_body)
            except:
                font_title = ImageFont.load_default()
                font_body = font_title

        # 绘制主题标签
        theme_text = self.watermark_text or "图文视频"
        bbox = draw.textbbox((0, 0), theme_text, font=font_title)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) // 2, height // 3),
                 theme_text, fill=(80, 120, 180), font=font_title)

        # 绘制分镜文案（取第一句）
        body_text = ""
        if shots and shots[0].cap:
            body_text = shots[0].cap.strip()
            if len(body_text) > 40:
                body_text = body_text[:40] + "..."
        if body_text:
            # 简单换行处理
            max_chars_per_line = max(10, width // font_size_body)
            lines = []
            for i in range(0, len(body_text), max_chars_per_line):
                lines.append(body_text[i:i+max_chars_per_line])
            y_offset = height // 2
            for line in lines[:3]:
                bbox = draw.textbbox((0, 0), line, font=font_body)
                line_width = bbox[2] - bbox[0]
                draw.text(((width - line_width) // 2, y_offset),
                         line, fill=(100, 100, 100), font=font_body)
                y_offset += font_size_body + 10

        # 添加 subtle 装饰边框
        draw.rectangle([20, 20, width - 20, height - 20],
                      outline=(200, 210, 230), width=4)

        img.save(img_path)
        return str(img_path)

    async def _merge_audios(self, shots: List[ShotSegment], output_name: str) -> str:
        """合并多段音频

        为保证声画同步，每个 shot 都必须有对应时长的音频：
        - 成功生成的音频直接使用
        - 生成失败的 shot 会用静音填充到其 duration
        """
        import subprocess
        import uuid

        merged_path = AUDIO_DIR / f"{output_name}_merged.wav"

        # 为每个 shot 准备等长音频（成功音频或静音填充）
        segment_audios = []
        for i, shot in enumerate(shots):
            if shot.audio_path and Path(shot.audio_path).exists():
                # 校验实际时长是否与 shot.duration 一致，偏差过大时补齐/截断
                actual_duration = self._get_audio_duration(str(shot.audio_path))
                if actual_duration is not None and abs(actual_duration - shot.duration) > 0.05:
                    print(f"  [WARNING] Audio duration mismatch for shot {i}: "
                          f"expected {shot.duration:.2f}s, got {actual_duration:.2f}s, adjusting")
                    padded_path = AUDIO_DIR / f"{output_name}_pad_{uuid.uuid4().hex[:8]}.wav"
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(shot.audio_path),
                        "-af", "apad=whole_len=0",
                        "-t", str(shot.duration),
                        "-c:a", "pcm_s16le",
                        "-ar", "44100",
                        "-ac", "2",
                        str(padded_path)
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    if result.returncode == 0:
                        segment_audios.append(str(padded_path))
                    else:
                        segment_audios.append(str(shot.audio_path))
                else:
                    segment_audios.append(str(shot.audio_path))
            else:
                # 生成静音填充，时长精确匹配 shot.duration
                silent_path = AUDIO_DIR / f"{output_name}_silent_{uuid.uuid4().hex[:8]}.wav"
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", str(shot.duration),
                    "-c:a", "pcm_s16le",
                    "-ar", "44100",
                    "-ac", "2",
                    str(silent_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result.returncode == 0:
                    segment_audios.append(str(silent_path))
                    print(f"  [INFO] Silent padding generated for shot {i}: {shot.duration:.2f}s")
                else:
                    print(f"  [WARNING] Failed to generate silent padding for shot {i}")

        if not segment_audios:
            # 没有任何分镜时创建 10 秒静音
            silent_wav = AUDIO_DIR / f"{output_name}_silent.wav"
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", "10",
                str(silent_wav)
            ]
            subprocess.run(cmd, capture_output=True)
            return str(silent_wav)

        # 如果只有一段音频，直接返回
        if len(segment_audios) == 1:
            return segment_audios[0]

        # 创建concat列表文件
        concat_list_path = AUDIO_DIR / f"{output_name}_concat.txt"
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            for audio_path in segment_audios:
                f.write(f"file '{audio_path}'\n")

        # 使用FFmpeg concat方式合并
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c", "copy",
            str(merged_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                print(f"  [WARNING] Audio merge failed: {result.stderr[:200] if result.stderr else 'unknown'}")
                # 回退：使用 amix 前先把所有音频 pad 到总时长再混合会同时播放，改为串接 fallback
                return await self._concat_audios_fallback(segment_audios, merged_path)
        except Exception as e:
            print(f"  [ERROR] Audio merge error: {e}")
            return segment_audios[0] if segment_audios else str(merged_path)

        return str(merged_path)

    async def _concat_audios_fallback(self, audio_paths: List[str], output_path: Path) -> str:
        """备用音频合并方法：使用 FFmpeg concat demuxer 串接音频

        与 amix 不同，此函数按顺序拼接音频，避免所有句子同时播放。
        """
        import subprocess

        if not audio_paths:
            return str(output_path)
        if len(audio_paths) == 1:
            return audio_paths[0]

        concat_list_path = output_path.parent / f"{output_path.stem}_fallback_concat.txt"
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            for path in audio_paths:
                f.write(f"file '{path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c:a", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode == 0:
                return str(output_path)
            else:
                print(f"  [WARNING] Concat fallback failed: {result.stderr[:200] if result.stderr else 'unknown'}")
        except Exception as e:
            print(f"  [ERROR] Concat fallback error: {e}")

        return audio_paths[0]

    def _get_audio_duration(self, audio_path: str) -> Optional[float]:
        """使用 ffprobe 获取音频实际时长"""
        import subprocess
        import re
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode == 0:
                duration_str = result.stdout.strip()
                if duration_str:
                    return float(duration_str)
        except Exception:
            pass
        return None

    async def _create_multi_shot_video(self, shots: List[ShotSegment],
                                     audio_path: str,
                                     subtitle_path: str,
                                     output_path: str,
                                     duration: float):
        """
        创建多段落视频 - 每段显示对应图片
        使用FFmpeg filter_complex实现
        """
        import subprocess
        from pathlib import Path

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 获取视频尺寸
        width = VIDEO_SETTINGS.get("width", 1080)
        height = VIDEO_SETTINGS.get("height", 1920)

        # 收集有图片的分段
        valid_shots = [s for s in shots if s.image_path]

        if not valid_shots:
            # 无图片，使用默认
            default_img = await self._create_default_image(shots, "temp")
            valid_shots = [type('obj', (object,), {'image_path': default_img, 'start_time': 0, 'end_time': duration})()]

        # 构建FFmpeg命令
        inputs = []
        for shot in valid_shots:
            inputs.extend(["-loop", "1", "-i", shot.image_path])
        inputs.extend(["-i", audio_path])

        # 构建filter_complex处理多图片切换
        # 简化处理：使用多个trim和concat
        total_shots = len(valid_shots)

        # 动态构建filter
        filter_lines = []
        for i, shot in enumerate(valid_shots):
            start_ms = int(shot.start_time * 1000)
            end_ms = int(shot.end_time * 1000)
            duration_ms = end_ms - start_ms

            # 缩放图片到目标尺寸
            filter_lines.append(
                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setpts=PTS-STARTPTS+{start_ms}/TB,"
                f"trim=0:{duration_ms/1000},setpts=PTS-STARTPTS[v{i}]"
            )

        # 拼接所有视频段
        if filter_lines:
            concat_inputs = "".join([f"[v{i}]" for i in range(total_shots)])
            filter_lines.append(f"{concat_inputs}concat=n={total_shots}:v=1:a=0[outv]")

        # 添加字幕
        if subtitle_path and Path(subtitle_path).exists():
            filter_lines.append(f"[outv]subtitles={Path(subtitle_path).name}[outv_final]")
        else:
            filter_lines.append("[outv]copy[outv_final]")

        filter_complex = ";".join(filter_lines)

        # 切换工作目录到字幕所在目录
        import os
        original_cwd = os.getcwd()
        if subtitle_path and Path(subtitle_path).exists():
            os.chdir(Path(subtitle_path).parent)

        cmd = [
            "ffmpeg", "-y",
            "-t", str(duration)
        ] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "[outv_final]",
            "-map", f"{total_shots}:a",
            "-af", "volume=2.0",  # 音频音量增大200%
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                print(f"  [WARNING] Multi-shot video failed, trying simple method")
                # 回退到简单方法
                await self._create_simple_video(shots, audio_path, subtitle_path, output_path, duration)
        except Exception as e:
            print(f"  [ERROR] Video synthesis error: {e}")
            await self._create_simple_video(shots, audio_path, subtitle_path, output_path, duration)
        finally:
            os.chdir(original_cwd)

    async def _create_simple_video(self, shots: List[ShotSegment],
                                 audio_path: str,
                                 subtitle_path: str,
                                 output_path: str,
                                 duration: float):
        """简单视频合成 - 单图片"""
        # 使用第一张图片
        first_image = None
        for shot in shots:
            if shot.image_path:
                first_image = shot.image_path
                break

        if not first_image:
            first_image = await self._create_default_image(shots, "temp")

        create_video_with_subtitles(
            image_path=first_image,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            watermark_text=self.watermark_text,
            video_settings=VIDEO_SETTINGS,
            watermark_settings=WATERMARK,
            subtitle_settings=SUBTITLE_SETTINGS
        )


# 同步版本
def generate_smart_video(content: str, **kwargs) -> Dict:
    """快捷函数：生成智能视频"""
    generator = SmartVideoGenerator(**kwargs)
    return asyncio.run(generator.generate(content, **kwargs))


if __name__ == "__main__":
    print("Smart Video Generator Module")
    print("Import and use: from utils.smart_video import SmartVideoGenerator, generate_smart_video")