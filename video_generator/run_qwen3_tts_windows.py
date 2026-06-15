#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen3-TTS 1.7B 测试脚本 (Windows版)
"""

import os
import sys
import torch
import numpy as np

print("=" * 60)
print("Qwen3-TTS 1.7B 直接测试 (Windows)")
print("=" * 60)

# 检查 GPU
print("\n[0] GPU 检查...")
print(f"    PyTorch 版本: {torch.__version__}")
print(f"    CUDA 可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"    GPU 设备: {torch.cuda.get_device_name(0)}")
    print(f"    GPU 显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

# 模型路径
model_path = r"D:\陈潘HBEU\Desktop\MultiFunc_Video\Qwen3_TTS\Qwen3-TTS-12Hz-1___7B-Base"
print(f"\n[1] 模型路径: {model_path}")
print(f"    路径存在: {os.path.exists(model_path)}")

# 检查关键文件
key_files = ["config.json", "model.safetensors", "tokenizer_config.json"]
for f in key_files:
    fp = os.path.join(model_path, f)
    exists = os.path.exists(fp)
    status = "[OK]" if exists else "[MISSING]"
    print(f"    {f}: {status}")

# 2. 加载模型
print("\n[2] 加载 Qwen3TTSModel...")
try:
    from qwen_tts import Qwen3TTSModel
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map="cuda",
        dtype=torch.bfloat16
    )
    print("    [SUCCESS] 模型加载成功!")
except Exception as e:
    print(f"    [FAIL] 模型加载失败: {e}")
    import traceback
    traceback.print_exc()
    input("\n按回车键退出...")
    sys.exit(1)

# 3. 查看模型类型
print("\n[3] 检查模型类型...")
tts_model_type = getattr(model.model, "tts_model_type", "unknown")
tts_model_size = getattr(model.model, "tts_model_size", "unknown")
tokenizer_type = getattr(model.model, "tokenizer_type", "unknown")
print(f"    tts_model_type: {tts_model_type}")
print(f"    tts_model_size: {tts_model_size}")
print(f"    tokenizer_type: {tokenizer_type}")

# 4. 获取支持的 speakers
print("\n[4] 支持的 Speakers...")
speakers = model.get_supported_speakers()
if speakers:
    print(f"    支持 {len(speakers)} 个音色:")
    for s in speakers[:10]:
        print(f"      - {s}")
    if len(speakers) > 10:
        print(f"      ... 还有 {len(speakers)-10} 个")
else:
    print("    无预定义 speakers（可能是 Base 模型）")

# 5. 测试生成
print("\n[5] 测试语音生成...")
test_text = "大学生活是人生中最美好的时光，我们要珍惜这段青春年华。"

wavs = None
sr = None

try:
    print(f"    输入文本: {test_text}")

    if tts_model_type == "custom_voice":
        print("    使用 generate_custom_voice 方法...")
        speaker = speakers[0] if speakers else "Auto"
        print(f"    Speaker: {speaker}")
        wavs, sr = model.generate_custom_voice(
            text=test_text,
            speaker=speaker,
            language="Auto",
        )
    elif tts_model_type == "base":
        print("    使用 generate_voice_clone 方法（需要参考音频）...")
        print("    [跳过] Base 模型需要参考音频，请提供 ref_audio 参数")
    elif tts_model_type == "voice_design":
        print("    使用 generate_voice_design 方法...")
        wavs, sr = model.generate_voice_design(
            text=test_text,
            instruct="",
            language="Auto",
        )
    else:
        print(f"    [未知模型类型: {tts_model_type}]")

except Exception as e:
    print(f"    [FAIL] 生成失败: {e}")
    import traceback
    traceback.print_exc()

# 6. 保存音频
if wavs:
    print("\n[6] 保存音频...")
    import soundfile as sf
    output_dir = r"D:\陈潘HBEU\Desktop\MultiFunc_Video\Qwen3_TTS\output"
    os.makedirs(output_dir, exist_ok=True)
    audio_data = wavs[0].astype(np.float32)
    output_path = os.path.join(output_dir, "test_output.wav")
    sf.write(output_path, audio_data, sr)
    print(f"    [SUCCESS] 已保存到: {output_path}")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
input("\n按回车键退出...")