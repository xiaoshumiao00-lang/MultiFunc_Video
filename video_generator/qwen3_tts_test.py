#!/usr/bin/env python3
"""
Qwen3-TTS 1.7B 测试脚本
使用 qwen-tts 包进行中文语音合成
"""

import os
print("=" * 60)
print("Qwen3-TTS 1.7B 测试")
print("=" * 60)

# 1. 检查模型路径
model_path = "/root/qwen3-tts/models"
print(f"\n[1] 检查模型文件...")
print(f"    模型路径: {model_path}")
if os.path.exists(model_path):
    files = os.listdir(model_path)
    print(f"    ✅ 模型文件存在，共 {len(files)} 个文件")
else:
    print(f"    ❌ 模型路径不存在!")
    sys.exit(1)

# 2. 检查 qwen-tts 包
print(f"\n[2] 检查 qwen-tts 包...")
try:
    import qwen_tts
    print(f"    ✅ qwen-tts 已安装")
except ImportError as e:
    print(f"    ❌ qwen-tts 未安装: {e}")
    print(f"    请运行: pip install qwen-tts")
    sys.exit(1)

# 3. 使用 qwen-tts 进行语音合成
print(f"\n[3] 测试语音合成...")
try:
    from qwen_tts import TTSPipeline

    # 创建输出目录
    output_dir = "/root/qwen3-tts/output"
    os.makedirs(output_dir, exist_ok=True)

    # 初始化 TTS 管道
    print(f"    初始化 TTS 管道（首次加载模型约需1-2分钟）...")
    tts = TTSPipeline(model_path=model_path, device="cuda")
    print(f"    ✅ 模型加载成功!")

    # 测试文本
    test_text = "大学生活是人生中最美好的时光之一，我们要好好珍惜。"

    print(f"    输入文本: {test_text}")
    print(f"    正在进行语音合成...")

    # 生成语音
    audio = tts.generate(
        text=test_text,
        voice="zh-CN",  # 中文语音
        speed=1.0,
    )

    # 保存音频
    output_path = os.path.join(output_dir, "test_output.wav")
    tts.save_audio(audio, output_path)

    print(f"    ✅ 语音合成成功!")
    print(f"    输出文件: {output_path}")

    # 检查音频信息
    import soundfile as sf
    info = sf.info(output_path)
    print(f"    音频时长: {info.duration:.2f} 秒")
    print(f"    采样率: {info.samplerate} Hz")
    print(f"    声道数: {info.channels}")

except Exception as e:
    print(f"    ❌ 语音合成失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 测试完成!")
print("=" * 60)
