#!/usr/bin/env python3
"""Qwen3-TTS 调试脚本 - 使用正确的 API"""

import os
import sys

print("=" * 60)
print("Qwen3-TTS 调试（修正API）")
print("=" * 60)

# 1. 检查模型文件
print("\n[1] 检查模型文件...")
model_path = "/root/qwen3-tts/models"
if os.path.exists(model_path):
    files = os.listdir(model_path)
    print(f"    ✅ 找到 {len(files)} 个文件")
else:
    print(f"    ❌ 模型路径不存在: {model_path}")
    sys.exit(1)

# 2. 正确的导入方式
print("\n[2] 导入 Qwen3TTSModel...")
try:
    from qwen_tts import Qwen3TTSModel, Qwen3TTSTokenizer
    print(f"    ✅ 导入成功!")
except Exception as e:
    print(f"    ❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. 初始化模型
print("\n[3] 初始化模型...")
print(f"    这可能需要1-2分钟...")
try:
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map="cuda",
        torch_dtype="bfloat16"
    )
    print(f"    ✅ 模型加载成功!")
except Exception as e:
    print(f"    ❌ 模型加载失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 初始化 tokenizer
print("\n[4] 初始化 Tokenizer...")
try:
    tokenizer = Qwen3TTSTokenizer.from_pretrained(model_path)
    print(f"    ✅ Tokenizer 加载成功!")
except Exception as e:
    print(f"    ❌ Tokenizer 加载失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. 尝试生成
print("\n[5] 测试语音合成...")
test_text = "大学生活是人生中最美好的时光。"

try:
    print(f"    输入: {test_text}")

    # 构建输入
    inputs = tokenizer(text=test_text, return_tensors="pt").to("cuda")

    # 生成
    with torch.no_grad():
        output = model.generate(**inputs, max_length=512)

    print(f"    ✅ 生成成功!")
    print(f"    输出类型: {type(output)}")
    print(f"    输出形状: {output.shape if hasattr(output, 'shape') else 'N/A'}")

    # 保存输出
    output_dir = "/root/qwen3-tts/output"
    os.makedirs(output_dir, exist_ok=True)

    import torch
    import soundfile as sf

    # 如果输出是音频数据（numpy数组或tensor）
    if isinstance(output, torch.Tensor):
        audio_data = output.float().cpu().numpy()
    else:
        audio_data = output

    output_path = os.path.join(output_dir, "debug_output.wav")
    # 假设采样率是 24000Hz
    sf.write(output_path, audio_data, 24000)
    print(f"    ✅ 保存到: {output_path}")

except Exception as e:
    print(f"    ❌ 合成失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 全部测试通过!")
print("=" * 60)
