"""
GPT-SoVITS TTS 模块
用于调用本地GPT-SoVITS API进行语音合成
"""
import requests
import base64
import json
import time
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union


def add_reverb(audio_path: str, output_path: str = None,
               reverb_delay_ms: int = 40, decay_db: float = 12,
               wet_mix: float = 0.25) -> str:
    """
    为音频添加混响效果，模拟真实录音环境，降低AI味
    使用pydub的overlay实现简单混响

    Args:
        audio_path: 输入音频路径
        output_path: 输出音频路径（默认覆盖原文件）
        reverb_delay_ms: 延迟毫秒数（30-50最佳）
        decay_db: 衰减分贝数（10-15dB最佳）
        wet_mix: 混响比例（0.2-0.3最佳，太高会发闷）

    Returns:
        添加混响后的音频路径
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        print("警告: pydub未安装，无法添加混响效果")
        return audio_path

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    if not output_path:
        output_path = audio_path

    try:
        audio = AudioSegment.from_file(audio_path)

        # 创建延迟音频（混响的"早反射"部分）
        # 延迟reverb_delay_ms毫秒，模拟真实空间
        delayed = audio[reverb_delay_ms:]

        # 衰减后的延迟（模拟声音在空间中的多次反射）
        delayed = delayed.apply_gain(-decay_db)

        # wet_mix次叠加混响（pydub不支持乘以浮点数，需要循环）
        reverb_part = delayed
        for _ in range(int(wet_mix * 10)):
            reverb_part = reverb_part + delayed.apply_gain(-3)

        # 叠加混响
        output = audio.overlay(reverb_part[:len(audio)])

        # 导出
        fmt = 'wav' if output_path.endswith('.wav') else 'mp3'
        output.export(output_path, format=fmt)

        return output_path
    except Exception as e:
        print(f"混响处理失败: {e}，返回原音频")
        return audio_path


def add_reverb_with_ffmpeg(audio_path: str, output_path: str = None,
                           reverb_size: float = 0.8,
                           reverb_damping: float = 0.7,
                           reverb_wet: float = 0.25,
                           reverb_width: float = 1.0) -> str:
    """
    使用FFmpeg的自由维纳尔滤波器添加更自然的混响效果

    Args:
        audio_path: 输入音频路径
        output_path: 输出音频路径
        reverb_size: 混响空间大小（0.5-1.0）
        reverb_damping: 高频衰减（0.5-1.0，值越大高频衰减越快）
        reverb_wet: 混响比例（0.2-0.35）
        reverb_width: 立体声宽度（0.5-1.5）

    Returns:
        添加混响后的音频路径
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    if not output_path:
        output_path = audio_path

    # 检查ffmpeg是否可用
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True,
                      encoding='utf-8', errors='ignore')
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("警告: ffmpeg不可用，使用pydub替代方案")
        return add_reverb(audio_path, output_path)

    try:
        # 使用ffmpeg的aecho滤波器创建自然混响
        # aecho格式: in_gain:out_gain:delay_ms:decay
        # delay_ms = reverb_size * 40
        delay_ms = int(reverb_size * 40)
        cmd = [
            'ffmpeg', '-y', '-i', audio_path,
            '-af', f'aecho=0.8:0.7:{delay_ms}:{reverb_wet}',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, check=True,
                              encoding='utf-8', errors='ignore')

        if result.returncode != 0:
            print(f"FFmpeg混响失败，使用pydub替代")
            return add_reverb(audio_path, output_path)

        return output_path
    except Exception as e:
        print(f"混响处理异常: {e}，返回原音频")
        return add_reverb(audio_path, output_path)

class GPTSoVITSTTS:
    """GPT-SoVITS 文本转语音类"""

    def __init__(self, api_url: str = "http://127.0.0.1:9880"):
        """
        初始化GPT-SoVITS TTS

        Args:
            api_url: GPT-SoVITS API地址
        """
        self.api_url = api_url.rstrip('/')

    def is_available(self) -> bool:
        """检查API服务是否可用"""
        try:
            r = requests.get(f"{self.api_url}/docs", timeout=5)
            return r.status_code == 200
        except:
            return False

    def generate_speech(self, text: str, ref_audio_path: str, prompt_text: str,
                       ref_lang: str = "en", text_lang: str = "en",
                       speed: float = 1.0, output_path: str = None) -> Dict:
        """
        生成语音文件

        Args:
            text: 要合成的文本
            ref_audio_path: 参考音频路径
            prompt_text: 参考音频对应的文本
            ref_lang: 参考音频语言 (en/zh/auto)
            text_lang: 合成文本语言 (en/zh/auto)
            speed: 语速 (0.5-2.0)
            output_path: 输出文件路径

        Returns:
            包含音频路径和时长的字典
        """
        if not os.path.exists(ref_audio_path):
            raise FileNotFoundError(f"参考音频不存在: {ref_audio_path}")

        # 使用POST方式（GET方式生成音频太短）
        # 参数优化：降低AI味，增加自然度
        data = {
            "text": text,
            "text_lang": text_lang,
            "ref_audio_path": ref_audio_path,
            "prompt_text": prompt_text,
            "prompt_lang": ref_lang,
            "top_k": 10,        # 降低随机性，从15改为10
            "top_p": 0.8,       # 降低随机性，从0.9改为0.8
            "temperature": 0.7, # 降低随机性，从1.0改为0.7
            "speed_factor": speed,
        }

        try:
            start = time.time()
            r = requests.post(f"{self.api_url}/tts", json=data, timeout=300)
            elapsed = time.time() - start

            if r.status_code != 200:
                error = r.text
                try:
                    error = r.json().get('message', r.text)
                except:
                    pass
                raise Exception(f"API错误: {error}")

            # 获取内容类型
            content_type = r.headers.get('Content-Type', 'audio/wav')

            # 确定输出路径
            if not output_path:
                timestamp = time.strftime("%Y%m%d%H%M%S")
                output_path = f"output/tts_{timestamp}.wav"

            # 确保目录存在
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

            # 保存音频
            with open(output_path, 'wb') as f:
                f.write(r.content)

            # 自动添加混响效果，降低AI味
            output_path_with_reverb = add_reverb_with_ffmpeg(
                output_path,
                reverb_size=0.8,      # 适中空间感
                reverb_damping=0.7,   # 高频自然衰减
                reverb_wet=0.25,     # 25%混响比例，不过于发闷
                reverb_width=1.0     # 单声道保持1.0
            )

            return {
                "audio_path": output_path_with_reverb,
                "original_path": output_path,  # 保留原始路径
                "duration": elapsed,
                "content_type": content_type,
                "text": text,
                "reverb_applied": output_path_with_reverb != output_path
            }

        except requests.exceptions.Timeout:
            raise TimeoutError("GPT-SoVITS API请求超时")
        except Exception as e:
            raise Exception(f"GPT-SoVITS语音合成失败: {str(e)}")

    def generate_with_timestamps(self, text: str, ref_audio_path: str,
                                 prompt_text: str, ref_lang: str = "en",
                                 text_lang: str = "en", speed: float = 1.0,
                                 output_path: str = None) -> Dict:
        """
        生成语音并尝试获取时间戳信息

        Args:
            text: 要合成的文本
            ref_audio_path: 参考音频路径
            prompt_text: 参考音频对应的文本
            ref_lang: 参考音频语言
            text_lang: 合成文本语言
            speed: 语速
            output_path: 输出文件路径

        Returns:
            包含音频路径、时长和分词信息的字典
        """
        result = self.generate_speech(
            text=text,
            ref_audio_path=ref_audio_path,
            prompt_text=prompt_text,
            ref_lang=ref_lang,
            text_lang=text_lang,
            speed=speed,
            output_path=output_path
        )

        # GPT-SoVITS默认不返回精确时间戳，这里返回估算值
        # 基于音频长度和文本长度估算每个字的时间范围
        duration = self._estimate_duration(result["audio_path"], text)

        # 生成word-level时间戳（估算）
        words = self._generate_word_timestamps(text, duration)

        return {
            "audio_path": result["audio_path"],
            "duration": duration,
            "words": words,
            "text": text
        }

    def _estimate_duration(self, audio_path: str, text: str) -> float:
        """估算音频时长"""
        try:
            # 使用pydub获取实际音频时长
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # 转换为秒
        except:
            # 回退方案：基于字符数估算（中文约0.4秒/字）
            return len(text) * 0.4

    def _generate_word_timestamps(self, text: str, duration: float) -> List[Dict]:
        """
        生成词级时间戳（估算）

        GPT-SoVITS不返回精确时间戳，这里基于均匀分布估算
        实际使用时建议使用WebUI界面工具获取精确时间戳

        Args:
            text: 文本
            duration: 总时长（秒）

        Returns:
            词列表，每个词包含start、end、word
        """
        # 移除标点符号进行分词
        import re
        # 按句子分割
        sentences = re.split(r'[。！？，、；：""''（）]', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            sentences = [text]

        total_chars = sum(len(s) for s in sentences)
        if total_chars == 0:
            return []

        words = []
        current_time = 0.0

        for sentence in sentences:
            if not sentence:
                continue
            char_duration = duration / total_chars
            start = current_time
            end = start + len(sentence) * char_duration
            words.append({
                "word": sentence,
                "start": round(start, 2),
                "end": round(end, 2),
                "start_time": start,
                "end_time": end
            })
            current_time = end

        return words

    def set_reference_audio(self, ref_audio_path: str, prompt_text: str,
                           ref_lang: str = "en") -> bool:
        """
        预先设置参考音频（如果API支持）

        Args:
            ref_audio_path: 参考音频路径
            prompt_text: 参考音频文本
            ref_lang: 参考音频语言

        Returns:
            是否设置成功
        """
        try:
            params = {
                "refer_audio_path": ref_audio_path,
                "prompt_text": prompt_text,
                "prompt_lang": ref_lang
            }
            r = requests.get(f"{self.api_url}/set_refer_audio", params=params, timeout=30)
            return r.status_code == 200
        except:
            return False

    def set_gpt_weights(self, weights_path: str) -> bool:
        """设置GPT模型权重"""
        try:
            params = {"weights_path": weights_path}
            r = requests.get(f"{self.api_url}/set_gpt_weights", params=params, timeout=30)
            return r.status_code == 200
        except:
            return False

    def set_sovits_weights(self, weights_path: str) -> bool:
        """设置SoVITS模型权重"""
        try:
            params = {"weights_path": weights_path}
            r = requests.get(f"{self.api_url}/set_sovits_weights", params=params, timeout=30)
            return r.status_code == 200
        except:
            return False


def generate_speech(text: str, ref_audio_path: str, prompt_text: str,
                   output_path: str = None, speed: float = 1.0,
                   api_url: str = "http://127.0.0.1:9880") -> str:
    """
    便捷函数：生成语音文件

    Args:
        text: 要合成的文本
        ref_audio_path: 参考音频路径
        prompt_text: 参考音频文本
        output_path: 输出路径
        speed: 语速
        api_url: API地址

    Returns:
        生成的音频文件路径
    """
    tts = GPTSoVITSTTS(api_url=api_url)
    result = tts.generate_speech(
        text=text,
        ref_audio_path=ref_audio_path,
        prompt_text=prompt_text,
        speed=speed,
        output_path=output_path
    )
    return result["audio_path"]


# 测试代码
if __name__ == "__main__":
    import sys

    API_URL = "http://127.0.0.1:9880"
    # 迁移后的参考音频路径（请根据实际情况修改）
    REF_AUDIO = r"D:\陈潘HBEU\Desktop\本地生成视频\video-generator\voices\很多同学.wav"
    PROMPT_TEXT = "很多同学都在问我记笔记的秘诀，其实关键不在于记多少，而在于怎么记。"

    print("="*50)
    print("GPT-SoVITS 语音合成测试")
    print("="*50)

    tts = GPTSoVITSTTS(api_url=API_URL)

    if not tts.is_available():
        print("错误: GPT-SoVITS API服务未运行")
        print("请先启动: python api_v2.py")
        sys.exit(1)

    print(f"API服务状态: 可用")
    print(f"参考音频: {REF_AUDIO}")

    test_text = "大学生活中，学习是最重要的事情之一。掌握科学的学习方法，让你的成绩突飞猛进。"

    print(f"\n合成文本: {test_text}")

    try:
        result = tts.generate_with_timestamps(
            text=test_text,
            ref_audio_path=REF_AUDIO,
            prompt_text=PROMPT_TEXT,
            ref_lang="en",
            text_lang="en",
            speed=1.0,
            output_path="output/test_gpt_sovits.wav"
        )

        print(f"\n[OK] 语音合成成功!")
        print(f"  音频文件: {result['audio_path']}")
        print(f"  时长: {result['duration']:.2f}秒")
        print(f"  分词数: {len(result['words'])}")

    except Exception as e:
        print(f"\n[FAIL] 语音合成失败: {e}")