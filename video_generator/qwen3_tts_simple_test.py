#!/usr/bin/env python3
"""
Qwen3-TTS 简单测试 - 使用预设音色
先测试基本功能，不需要参考音频
"""
import os
import sys
import torch
import soundfile as sf

print("=" * 60)
print("Qwen3-TTS 简单测试 (CustomVoice 预设音色)")
print("=" * 60)

from qwen_tts import Qwen3TTSModel

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
OUTPUT_DIR = "/root/qwen3-tts/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 测试文本
SAMPLE_TEXT = "大学生活是一段美好的时光，在这里我们可以学习知识，结交朋友。"

def main():
    print(f"\n[1/3] 加载 CustomVoice 模型...")
    print("  首次运行会从 HuggingFace 下载模型（约 3-5GB）")
    print("  如果下载慢，请耐心等待...")
    
    try:
        model = Qwen3TTSModel.from_pretrained(
            MODEL_ID,
            device_map="cuda",
            dtype=torch.bfloat16,
        )
        print("  模型加载成功!")
    except Exception as e:
        print(f"  模型加载失败: {e}")
        print("\n如果网络问题导致下载失败，可以尝试:")
        print("  1. 设置 HuggingFace 镜像")
        print("  2. 使用 ModelScope 下载")
        return
    
    if torch.cuda.is_available():
        vram = torch.cuda.memory_allocated() / 1e9
        print(f"  显存占用: {vram:.2f} GB")
    
    print(f"\n[2/3] 生成语音...")
    print(f"  文本: {SAMPLE_TEXT}")
    print(f"  音色: Vivian (预设女声)")
    
    wavs, sr = model.generate_custom_voice(
        text=SAMPLE_TEXT,
        language="Chinese",
        speaker="Vivian",
    )
    
    output_path = os.path.join(OUTPUT_DIR, "test_custom_voice.wav")
    sf.write(output_path, wavs[0], sr)
    
    print(f"\n[3/3] 保存音频: {output_path}")
    print(f"  时长: {len(wavs[0]) / sr:.2f} 秒")
    print(f"  采样率: {sr} Hz")
    
    if torch.cuda.is_available():
        vram = torch.cuda.memory_allocated() / 1e9
        print(f"\n[显存] 最终占用: {vram:.2f} GB")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
