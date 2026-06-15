"""
Qwen3-TTS 语音合成模块
支持语音克隆（只需3-10秒参考音频）和零样本合成
"""

import os
import time
import torch
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple

# 全局模型实例（避免重复加载）
_model_instance = None
_model_path = None


def get_model(model_path: str = None, device: str = "cuda") -> 'Qwen3TTSModel':
    """
    获取或加载 Qwen3-TTS 模型单例

    Args:
        model_path: 模型路径，默认使用配置中的路径
        device: 设备 "cuda" 或 "cpu"

    Returns:
        Qwen3TTSModel 实例
    """
    global _model_instance, _model_path

    if model_path is None:
        from config import QWEN_TTS_SETTINGS
        model_path = QWEN_TTS_SETTINGS.get("model_path", "")

    # 如果已加载相同模型，直接返回
    if _model_instance is not None and _model_path == model_path:
        return _model_instance

    print(f"[Qwen-TTS] 加载模型: {model_path}")

    from qwen_tts import Qwen3TTSModel

    _model_instance = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map=device,
        dtype=torch.bfloat16 if device == "cuda" else torch.float32
    )
    _model_path = model_path

    print(f"[Qwen-TTS] 模型加载完成!")
    return _model_instance


def unload_model():
    """卸载模型，释放显存"""
    global _model_instance, _model_path
    if _model_instance is not None:
        del _model_instance
        _model_instance = None
        _model_path = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[Qwen-TTS] 模型已卸载")


class Qwen3TTSTTS:
    """Qwen3-TTS 文本转语音类"""

    def __init__(self, model_path: str = None, device: str = "cuda"):
        """
        初始化 Qwen3-TTS

        Args:
            model_path: 模型路径，默认使用配置
            device: 设备 "cuda" 或 "cpu"
        """
        self.model_path = model_path
        self.device = device
        self.model = None
        self._tts_model_type = None
        self._speakers = None

    def _ensure_model(self):
        """确保模型已加载"""
        if self.model is None:
            self.model = get_model(self.model_path, self.device)
            self._tts_model_type = getattr(self.model.model, "tts_model_type", "unknown")
            self._speakers = self.model.get_supported_speakers()

    def is_available(self) -> bool:
        """检查模型是否可用"""
        try:
            self._ensure_model()
            return self.model is not None
        except Exception:
            return False

    def get_model_info(self) -> Dict:
        """获取模型信息"""
        self._ensure_model()
        return {
            "tts_model_type": self._tts_model_type,
            "speakers": self._speakers,
            "model_path": self.model_path
        }

    def generate_speech(
        self,
        text: str,
        ref_audio_path: str = None,
        prompt_text: str = None,
        speaker: str = None,
        language: str = "Auto",
        speed: float = 1.0,
        output_path: str = None,
        **kwargs
    ) -> Dict:
        """
        生成语音文件

        Args:
            text: 要合成的文本
            ref_audio_path: 参考音频路径（用于语音克隆）
            prompt_text: 参考音频对应的文本
            speaker: 预定义音色名称（用于 CustomVoice 模型）
            language: 语言 "Auto"/"zh"/"en"
            speed: 语速 (0.5-2.0)
            output_path: 输出文件路径

        Returns:
            包含音频路径和时长的字典
        """
        self._ensure_model()

        if not output_path:
            timestamp = time.strftime("%Y%m%d%H%M%S")
            output_path = f"outputs/audio/qwen_tts_{timestamp}.wav"
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        try:
            if self._tts_model_type == "custom_voice":
                # CustomVoice 模型 - 使用预定义音色
                if speaker is None:
                    speaker = self._speakers[0] if self._speakers else "Auto"
                print(f"[Qwen-TTS] 使用音色: {speaker}")
                wavs, sr = self.model.generate_custom_voice(
                    text=text,
                    speaker=speaker,
                    language=language,
                    **kwargs
                )

            elif self._tts_model_type == "base":
                # Base 模型 - 需要语音克隆
                if ref_audio_path is None:
                    raise ValueError("Base 模型需要提供 ref_audio_path 进行语音克隆")
                if not os.path.exists(ref_audio_path):
                    raise FileNotFoundError(f"参考音频不存在: {ref_audio_path}")

                print(f"[Qwen-TTS] 使用语音克隆，参考音频: {ref_audio_path}")
                wavs, sr = self.model.generate_voice_clone(
                    text=text,
                    ref_audio=ref_audio_path,
                    ref_text=prompt_text,
                    language=language,
                    **kwargs
                )

            elif self._tts_model_type == "voice_design":
                # VoiceDesign 模型 - 使用指令控制
                instruct = kwargs.get("instruct", "")
                wavs, sr = self.model.generate_voice_design(
                    text=text,
                    instruct=instruct,
                    language=language,
                    **kwargs
                )

            else:
                raise ValueError(f"未知模型类型: {self._tts_model_type}")

            # 保存音频
            import soundfile as sf
            audio_data = wavs[0].astype(np.float32)
            sf.write(output_path, audio_data, sr)

            # 获取时长
            duration = len(audio_data) / sr

            return {
                "audio_path": output_path,
                "duration": duration,
                "sample_rate": sr,
                "text": text,
                "speaker": speaker if self._tts_model_type == "custom_voice" else "cloned",
                "model_type": self._tts_model_type
            }

        except Exception as e:
            raise Exception(f"Qwen3-TTS 语音合成失败: {str(e)}")

    def generate_with_timestamps(
        self,
        text: str,
        ref_audio_path: str = None,
        prompt_text: str = None,
        speaker: str = None,
        language: str = "Auto",
        speed: float = 1.0,
        output_path: str = None,
        **kwargs
    ) -> Dict:
        """
        生成语音并返回时间戳信息

        Returns:
            包含音频路径、时长和分词信息的字典
        """
        result = self.generate_speech(
            text=text,
            ref_audio_path=ref_audio_path,
            prompt_text=prompt_text,
            speaker=speaker,
            language=language,
            speed=speed,
            output_path=output_path,
            **kwargs
        )

        # 生成词级时间戳（估算）
        words = self._generate_word_timestamps(text, result["duration"])

        return {
            "audio_path": result["audio_path"],
            "duration": result["duration"],
            "sample_rate": result.get("sample_rate", 24000),
            "words": words,
            "text": text
        }

    def _generate_word_timestamps(self, text: str, duration: float) -> List[Dict]:
        """
        生成词级时间戳（估算）

        Args:
            text: 文本
            duration: 总时长（秒）

        Returns:
            词列表
        """
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

    def list_speakers(self) -> List[str]:
        """获取支持的音色列表"""
        self._ensure_model()
        return self._speakers or []


# 便捷函数
def generate_speech(
    text: str,
    ref_audio_path: str = None,
    prompt_text: str = None,
    speaker: str = None,
    output_path: str = None,
    speed: float = 1.0,
    **kwargs
) -> str:
    """
    便捷函数：生成语音文件

    Args:
        text: 要合成的文本
        ref_audio_path: 参考音频路径
        prompt_text: 参考音频文本
        speaker: 预定义音色
        output_path: 输出路径
        speed: 语速

    Returns:
        生成的音频文件路径
    """
    tts = Qwen3TTSTTS()
    result = tts.generate_speech(
        text=text,
        ref_audio_path=ref_audio_path,
        prompt_text=prompt_text,
        speaker=speaker,
        speed=speed,
        output_path=output_path,
        **kwargs
    )
    return result["audio_path"]


def is_model_loaded() -> bool:
    """检查模型是否已加载"""
    return _model_instance is not None


# 测试代码
if __name__ == "__main__":
    from config import QWEN_TTS_SETTINGS

    print("=" * 50)
    print("Qwen3-TTS 语音合成测试")
    print("=" * 50)

    model_path = QWEN_TTS_SETTINGS.get("model_path", "")
    ref_audio = QWEN_TTS_SETTINGS.get("ref_audio_path", "")
    prompt_text = QWEN_TTS_SETTINGS.get("prompt_text", "")

    print(f"模型路径: {model_path}")
    print(f"参考音频: {ref_audio}")

    tts = Qwen3TTSTTS(model_path=model_path)

    if not tts.is_available():
        print("错误: Qwen3-TTS 模型加载失败")
        exit(1)

    # 获取模型信息
    info = tts.get_model_info()
    print(f"\n模型类型: {info['tts_model_type']}")
    if info['speakers']:
        print(f"支持音色数: {len(info['speakers'])}")
        print(f"音色列表: {info['speakers'][:5]}...")

    test_text = "大学生活中，学习是最重要的事情之一。掌握科学的学习方法，让你的成绩突飞猛进。"

    print(f"\n合成文本: {test_text}")

    try:
        result = tts.generate_with_timestamps(
            text=test_text,
            ref_audio_path=ref_audio if ref_audio else None,
            prompt_text=prompt_text if prompt_text else None,
            output_path="outputs/audio/test_qwen_tts.wav"
        )

        print(f"\n[OK] 语音合成成功!")
        print(f"  音频文件: {result['audio_path']}")
        print(f"  时长: {result['duration']:.2f}秒")
        print(f"  采样率: {result['sample_rate']}Hz")

    except Exception as e:
        print(f"\n[FAIL] 语音合成失败: {e}")
        import traceback
        traceback.print_exc()