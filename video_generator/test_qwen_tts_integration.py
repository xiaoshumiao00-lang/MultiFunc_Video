#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen3-TTS 集成测试
测试 Qwen TTS 是否可以正常集成到视频生成流程
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import QWEN_TTS_SETTINGS, TTS_MODE, AUDIO_DIR
from utils.qwen_tts import Qwen3TTSTTS

print("=" * 60)
print("Qwen3-TTS 集成测试")
print("=" * 60)

print(f"\n[配置检查]")
print(f"  TTS_MODE: {TTS_MODE}")
print(f"  模型路径: {QWEN_TTS_SETTINGS.get('model_path')}")
print(f"  参考音频: {QWEN_TTS_SETTINGS.get('ref_audio_path')}")
print(f"  Speaker: {QWEN_TTS_SETTINGS.get('speaker')}")

# 检查模型路径是否存在
model_path = QWEN_TTS_SETTINGS.get("model_path", "")
if not os.path.exists(model_path):
    print(f"\n[错误] 模型路径不存在: {model_path}")
    exit(1)

print(f"\n[1] 初始化 Qwen3TTSTTS...")
tts = Qwen3TTSTTS(
    model_path=model_path,
    device=QWEN_TTS_SETTINGS.get("device", "cuda")
)

print(f"\n[2] 检查模型可用性...")
if not tts.is_available():
    print("[错误] 模型加载失败")
    exit(1)
print("[OK] 模型可用")

print(f"\n[3] 获取模型信息...")
info = tts.get_model_info()
print(f"  模型类型: {info['tts_model_type']}")
speakers = info.get('speakers', [])
if speakers:
    print(f"  支持音色数: {len(speakers)}")
    print(f"  前5个音色: {speakers[:5]}")
else:
    print("  无预定义音色（需要使用语音克隆）")

# 检查是否需要语音克隆
ref_audio = QWEN_TTS_SETTINGS.get("ref_audio_path", "")
if not ref_audio or not os.path.exists(ref_audio):
    print(f"\n[警告] 参考音频不存在，将使用预定义音色（如果有）")
    ref_audio = None

print(f"\n[4] 测试语音合成...")
test_text = "大学生活是人生中最美好的时光，我们要珍惜这段青春年华。"

try:
    result = tts.generate_with_timestamps(
        text=test_text,
        ref_audio_path=ref_audio if ref_audio else None,
        prompt_text=QWEN_TTS_SETTINGS.get("prompt_text") if ref_audio else None,
        speaker=QWEN_TTS_SETTINGS.get("speaker"),
        language=QWEN_TTS_SETTINGS.get("language", "Auto"),
        output_path=os.path.join(AUDIO_DIR, "test_qwen_integration.wav"),
        speed=QWEN_TTS_SETTINGS.get("speed", 1.0)
    )

    print(f"\n[OK] 语音合成成功!")
    print(f"  音频文件: {result['audio_path']}")
    print(f"  时长: {result['duration']:.2f}秒")
    print(f"  采样率: {result.get('sample_rate', 'N/A')}Hz")
    print(f"  分词数: {len(result.get('words', []))}")

except Exception as e:
    print(f"\n[错误] 语音合成失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)