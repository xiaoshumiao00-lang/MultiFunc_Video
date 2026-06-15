"""
字幕处理工具 - 生成和管理SRT字幕文件
"""

from pathlib import Path
from typing import List, Dict, Optional
import re


class SubtitleGenerator:
    """字幕生成器"""

    def __init__(self):
        self.subtitles = []

    def add_subtitle(self, start_time: float, end_time: float, text: str):
        """添加一条字幕"""
        self.subtitles.append({
            "start": start_time,
            "end": end_time,
            "text": text
        })

    def generate_srt(self, output_path: str) -> str:
        """
        生成SRT格式字幕文件

        Args:
            output_path: 输出路径

        Returns:
            生成的SRT文件路径
        """
        srt_content = []
        for i, subtitle in enumerate(self.subtitles, 1):
            start = self._format_time(subtitle["start"])
            end = self._format_time(subtitle["end"])
            srt_content.append(f"{i}")
            srt_content.append(f"{start} --> {end}")
            srt_content.append(subtitle["text"])
            srt_content.append("")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("\n".join(srt_content), encoding="utf-8")

        return str(output_file)

    def _format_time(self, seconds: float) -> str:
        """秒转换为SRT时间格式 HH:MM:SS,mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def from_word_timings(words: List[Dict], output_path: Optional[str] = None) -> 'SubtitleGenerator':
        """
        从词语时间戳列表创建字幕生成器

        Args:
            words: 包含word, start, end的列表
            output_path: 可选的输出路径

        Returns:
            SubtitleGenerator实例
        """
        generator = SubtitleGenerator()
        current_sentence = []
        sentence_start = None

        for i, word_info in enumerate(words):
            if sentence_start is None:
                sentence_start = word_info["start"]

            current_sentence.append(word_info["word"])

            # 遇到标点符号结束句子
            if word_info["word"] in "。！？.!?" or i == len(words) - 1:
                sentence_text = "".join(current_sentence)
                generator.add_subtitle(sentence_start, word_info["end"], sentence_text)
                current_sentence = []
                sentence_start = None

        if output_path:
            generator.generate_srt(output_path)

        return generator


def read_srt(file_path: str) -> List[Dict]:
    """
    读取SRT字幕文件

    Args:
        file_path: SRT文件路径

    Returns:
        字幕列表
    """
    content = Path(file_path).read_text(encoding="utf-8")
    subtitles = []

    blocks = content.strip().split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            # 第二行是时间码
            time_match = re.match(
                r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
                lines[1]
            )
            if time_match:
                subtitles.append({
                    "index": int(lines[0]),
                    "start": _parse_time(time_match.group(1)),
                    "end": _parse_time(time_match.group(2)),
                    "text": "\n".join(lines[2:])
                })

    return subtitles


def _parse_time(time_str: str) -> float:
    """解析SRT时间字符串为秒"""
    match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", time_str)
    if match:
        h, m, s, ms = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    return 0.0


def srt_to_ass(srt_path: str, ass_path: str) -> str:
    """
    将SRT转换为ASS字幕格式

    Args:
        srt_path: SRT文件路径
        ass_path: ASS输出路径

    Returns:
        ASS文件路径
    """
    subtitles = read_srt(srt_path)

    ass_content = """[Script Info]
Title: Generated Subtitle
ScriptType: v4.00+
PlayDepth: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    for sub in subtitles:
        start = _format_ass_time(sub["start"])
        end = _format_ass_time(sub["end"])
        text = sub["text"].replace("\n", "\\N")
        ass_content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"

    output_file = Path(ass_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(ass_content, encoding="utf-8")

    return str(ass_path)


def _format_ass_time(seconds: float) -> str:
    """秒转换为ASS时间格式 H:MM:SS.cc"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def generate_ass_subtitle(words: List[Dict], output_path: str,
                          font_size: int = 24,
                          primary_color: str = "&H00FFFFFF",
                          outline_color: str = "&H00000000") -> str:
    """
    根据时间戳生成ASS字幕文件（FFmpeg兼容）

    Args:
        words: 包含时间戳的词语列表
        output_path: 输出ASS文件路径
        font_size: 字体大小
        primary_color: 主颜色（ASS格式）
        outline_color: 描边颜色（ASS格式）

    Returns:
        ASS文件路径
    """
    # 收集句子
    sentences = []
    current_sentence = []
    sentence_start = None

    for i, word_info in enumerate(words):
        if sentence_start is None:
            sentence_start = word_info["start"]

        current_sentence.append(word_info["word"])

        # 遇到句号、问号、感叹号或最后一个词时结束句子
        if word_info["word"] in "。！？.!?" or i == len(words) - 1:
            sentence_text = "".join(current_sentence)
            sentence_end = word_info["end"]
            sentences.append({
                "start": sentence_start,
                "end": sentence_end,
                "text": sentence_text
            })
            current_sentence = []
            sentence_start = None

    # 生成ASS内容
    ass_content = f"""[Script Info]
Title: Generated Subtitle
ScriptType: v4.00+
PlayDepth: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},{primary_color},&H000000FF,{outline_color},&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    for sub in sentences:
        start = _format_ass_time(sub["start"])
        end = _format_ass_time(sub["end"])
        # ASS使用\N作为换行符
        text = sub["text"].replace("\n", "\\N")
        ass_content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"

    # 写入文件
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(ass_content, encoding="utf-8")

    return str(output_file)
