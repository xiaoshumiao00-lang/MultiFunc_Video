#!/usr/bin/env python3
"""
Qwen3-TTS 1.7B 直接测试
直接使用 Model，不依赖 Tokenizer 的 feature_extractor
"""

import os
import torch

print("=" * 60)
print("Qwen3-TTS 1.7B 直接测试")
print("=" * 60)

# 模型路径
model_path = "/root/qwen3-tts/models"

# 1. 加载模型
print("\n[1] 加载 Qwen3TTSModel...")
try:
    from qwen_tts import Qwen3TTSModel
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map="cuda",
        torch_dtype=torch.bfloat16
    )
    print("    ✅ 模型加载成功!")
except Exception as e:
    print(f"    ❌ 模型加载失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 2. 查看模型结构
print("\n[2] 检查模型结构...")
print(f"    模型类型: {type(model)}")
if hasattr(model, 'model'):
    print(f"    包含子模型: {type(model.model)}")
if hasattr(model, 'generate'):
    print("    ✅ 有 generate 方法")

# 3. 查看模型的 generate 方法签名
print("\n[3] 检查 generate 方法...")
import inspect
sig = inspect.signature(model.generate)
print(f"    generate 签名: {sig}")

# 4. 尝试直接生成
print("\n[4] 测试直接生成...")
test_text = "大学生活是人生中最美好的时光。"

try:
    # Qwen3-TTS 使用文本作为输入
    # 有些版本的 API 可能需要特殊的输入格式
    print(f"    输入文本: {test_text}")

    # 方法1：直接传文本
    with torch.no_grad():
        output = model.generate(text=test_text, max_length=512)

    print(f"    ✅ 生成成功!")
    print(f"    输出类型: {type(output)}")

    if hasattr(output, 'shape'):
        print(f"    输出形状: {output.shape}")

    # 5. 保存音频
    print("\n[5] 保存音频...")
    output_dir = "/root/qwen3-tts/output"
    os.makedirs(output_dir, exist_ok=True)

    import soundfile as sf

    if isinstance(output, torch.Tensor):
        audio_data = output.float().cpu().numpy()
        # 如果是 [batch, seq] 格式
        if len(audio_data.shape) > 1:
            audio_data = audio_data[0]
    else:
        audio_data = output

    output_path = os.path.join(output_dir, "direct_output.wav")
    # Qwen3-TTS 通常是 24000Hz 采样率
    sf.write(output_path, audio_data, 24000)
    print(f"    ✅ 保存到: {output_path}")

except Exception as e:
    print(f"    ❌ 生成失败: {e}")
    import traceback
    traceback.print_exc()

    # 尝试其他输入格式
    print("\n[6] 尝试其他输入格式...")

    # 方法2：传 tokenizer 的结果
    try:
        from qwen_tts import Qwen3TTSTokenizer
        tokenizer = Qwen3TTSTokenizer.from_pretrained(model_path)
        print("    tokenizer 加载成功!")

        inputs = tokenizer(text=test_text, return_tensors="pt")
        print(f"    inputs: {inputs.keys()}")

        with torch.no_grad():
            output = model.generate(**inputs, max_length=512)

        print(f"    ✅ 方法2生成成功!")

        audio_data = output.float().cpu().numpy()
        if len(audio_data.shape) > 1:
            audio_data = audio_data[0]

        output_path = os.path.join(output_dir, "method2_output.wav")
        sf.write(output_path, audio_data, 24000)
        print(f"    ✅ 保存到: {output_path}")

    except Exception as e2:
        print(f"    ❌ 方法2也失败: {e2}")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
