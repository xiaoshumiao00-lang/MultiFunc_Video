"""
Edge-TTS 封装模块 - 本地免费文本转语音
支持多种中文音色，自动生成带时间戳的字幕文件
"""

import asyncio
import edge_tts
from pathlib import Path
from typing import List, Dict, Optional
import json


class TTsgenerator:
    """TTS生成器类"""

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%",
                 volume: str = "+0%", pitch: str = "+0Hz"):
        """
        初始化TTS生成器

        Args:
            voice: 语音音色
            rate: 语速调整，如 "+10%" 或 "-10%"
            volume: 音量调整
            pitch: 音调调整
        """
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

    async def generate_audio_with_timestamps(self, text: str, output_path: str) -> Dict:
        """
        生成音频并获取每个字的时间戳

        Args:
            text: 要转换的文本
            output_path: 输出音频文件路径

        Returns:
            包含音频信息和时间戳的字典
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 使用edge-tts生成音频
        communicate = edge_tts.Communicate(text, self.voice,
                                           rate=self.rate,
                                           volume=self.volume,
                                           pitch=self.pitch)
        await communicate.save(str(output_file))

        # 获取音频时长
        import librosa
        duration = librosa.get_duration(filename=str(output_file))

        # 使用微软的presist布局来获取精确时间戳
        # edge-tts提供了word级别的timing信息
        words_with_time = await self._get_word_timings(text)

        return {
            "audio_path": str(output_file),
            "duration": duration,
            "words": words_with_time,
            "text": text
        }

    async def _get_word_timings(self, text: str) -> List[Dict]:
        """获取每个词的时间戳"""
        words = []

        # 使用edge-tts的子词功能获取精确时间戳
        try:
            import re

            # 获取音频和word边界信息
            all_text = ""
            async for word in edge_tts.Communicate(text, self.voice)._sync_text():
                if word.get("type") == "word":
                    words.append({
                        "word": word.get("text", ""),
                        "start": word.get("start", 0) / 1000,  # 转换为秒
                        "end": word.get("end", 0) / 1000,
                    })
        except Exception as e:
            # 如果无法获取精确时间戳，使用估计值
            print(f"警告: 无法获取精确时间戳，使用估计值: {e}")
            words = self._estimate_word_timings(text)

        return words

    def _estimate_word_timings(self, text: str) -> List[Dict]:
        """基于字符数估计时间戳（备选方案）"""
        import re
        import subprocess

        # 获取音频时长
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', self.voice],
            capture_output=True, text=True, encoding='utf-8', errors='ignore'
        )

        # 简单的按字符平均分配
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        num_chars = len(chinese_chars)
        avg_duration_per_char = 0.3  # 估计每个中文字符300ms

        words = []
        current_time = 0.0
        for char in chinese_chars:
            words.append({
                "word": char,
                "start": current_time,
                "end": current_time + avg_duration_per_char
            })
            current_time += avg_duration_per_char

        return words

    def generate_audio_sync(self, text: str, output_path: str,
                           progress_callback=None) -> str:
        """
        同步方法生成音频

        Args:
            text: 要转换的文本
            output_path: 输出音频文件路径
            progress_callback: 进度回调函数

        Returns:
            生成的音频文件路径
        """
        return asyncio.run(self.generate_audio_with_timestamps(text, output_path))


def generate_srt_subtitle(words: List[Dict], output_path: str) -> str:
    """
    根据时间戳生成SRT字幕文件

    Args:
        words: 包含时间戳的词语列表
        output_path: 输出SRT文件路径

    Returns:
        SRT文件路径
    """
    srt_content = []
    subtitle_index = 1

    # 将词语组合成句子（每句话作为一个字幕块）
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

            # SRT格式：索引号\n开始时间 --> 结束时间\n文本\n\n
            start_time = _format_srt_time(sentence_start)
            end_time = _format_srt_time(sentence_end)

            srt_content.append(f"{subtitle_index}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(sentence_text)
            srt_content.append("")

            subtitle_index += 1
            current_sentence = []
            sentence_start = None

    # 写入文件
    srt_file = Path(output_path)
    srt_file.parent.mkdir(parents=True, exist_ok=True)
    srt_file.write_text("\n".join(srt_content), encoding="utf-8")

    return str(srt_file)


def _format_srt_time(seconds: float) -> str:
    """将秒数格式化为SRT时间格式 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


async def list_available_voices():
    """列出所有可用的中文语音"""
    voices = await edge_tts.list_voices()
    chinese_voices = [v for v in voices if v["Locale"].startswith("zh-")]
    return chinese_voices


if __name__ == "__main__":
    # 测试代码
    async def test():
        voices = await list_available_voices()
        print("可用的中文语音：")
        for v in voices[:10]:
            print(f"  {v['Name']} - {v['ShortName']} ({v['Gender']})")

    asyncio.run(test())
