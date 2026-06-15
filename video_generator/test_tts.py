#!/usr/bin/env python3
"""
Qwen3-TTS 测试脚本
测试预设音色和语音克隆
"""
import os
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

# 配置
MODEL_PATH = "/root/qwen3-tts/models/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
OUTPUT_DIR = "/root/qwen3-tts/output"
REF_AUDIO = "/root/qwen3-tts/ref_audio.wav"  # 可选：语音克隆参考

SAMPLE_TEXT = "大学生活是一段美好的时光，在这里我们可以学习知识，结交朋友，参与各种有趣的活动。"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    print("=" * 60)
    print("Qwen3-TTS 测试")
    print("=" * 60)

    # 检查模型路径
    if os.path.exists(MODEL_PATH):
        print(f"使用本地模型: {MODEL_PATH}")
        model_id = MODEL_PATH
    else:
        print("使用在线模型 (首次会自动下载)...")
        model_id = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"

    # 加载模型
    print("\n[1/4] 加载模型...")
    print("  (首次加载需要下载模型，请耐心等待)")

    model = Qwen3TTSModel.from_pretrained(
        model_id,
        device_map="cuda",
        dtype=torch.bfloat16,
    )

    if torch.cuda.is_available():
        vram = torch.cuda.memory_allocated() / 1e9
        print(f"  模型加载完成! 显存: {vram:.2f} GB")

    # 测试 1: 预设音色
    print("\n[2/4] 测试预设音色 (Vivian)...")
    wavs, sr = model.generate_custom_voice(
        text=SAMPLE_TEXT,
        language="Chinese",
        speaker="Vivian",
    )

    output_path = os.path.join(OUTPUT_DIR, "test_vivian.wav")
    sf.write(output_path, wavs[0], sr)
    print(f"  保存: {output_path}")
    print(f"  时长: {len(wavs[0]) / sr:.2f} 秒")

    # 测试 2: 另一个预设音色
    print("\n[3/4] 测试预设音色 (Emma)...")
    wavs, sr = model.generate_custom_voice(
        text=SAMPLE_TEXT,
        language="Chinese",
        speaker="Emma",
    )

    output_path = os.path.join(OUTPUT_DIR, "test_emma.wav")
    sf.write(output_path, wavs[0], sr)
    print(f"  保存: {output_path}")
    print(f"  时长: {len(wavs[0]) / sr:.2f} 秒")

    # 测试 3: 语音克隆 (如果有参考音频)
    print("\n[4/4] 测试语音克隆...")
    if os.path.exists(REF_AUDIO):
        print(f"  参考音频: {REF_AUDIO}")

        # 创建克隆提示
        prompt = model.create_voice_clone_prompt(
            ref_audio=REF_AUDIO,
            ref_text="这是参考音频对应的文本内容。",
        )

        # 使用克隆音色生成
        wavs, sr = model.generate_voice_clone(
            text=SAMPLE_TEXT,
            language="Chinese",
            voice_clone_prompt=prompt,
        )

        output_path = os.path.join(OUTPUT_DIR, "test_cloned.wav")
        sf.write(output_path, wavs[0], sr)
        print(f"  保存: {output_path}")
        print(f"  时长: {len(wavs[0]) / sr:.2f} 秒")
    else:
        print("  参考音频不存在，跳过语音克隆测试")
        print(f"  (如需测试，请添加参考音频到: {REF_AUDIO})")

    # 显存统计
    if torch.cuda.is_available():
        vram = torch.cuda.memory_allocated() / 1e9
        print(f"\n[显存] 最终占用: {vram:.2f} GB")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
    print(f"\n输出文件:")
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith(".wav"):
            fpath = os.path.join(OUTPUT_DIR, f)
            size_mb = os.path.getsize(fpath) / 1024 / 1024
            print(f"  - {f} ({size_mb:.1f} MB)")

if __name__ == "__main__":
    main()
