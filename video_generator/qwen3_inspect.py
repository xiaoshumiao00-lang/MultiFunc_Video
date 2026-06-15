#!/usr/bin/env python3
"""Qwen3-TTS 检查模型方法"""

import os
import torch

print("=" * 60)
print("Qwen3-TTS 方法检查")
print("=" * 60)

model_path = "/root/qwen3-tts/models"

# 加载模型
print("\n[1] 加载模型...")
from qwen_tts import Qwen3TTSModel
model = Qwen3TTSModel.from_pretrained(
    model_path,
    device_map="cuda",
    torch_dtype=torch.bfloat16
)
print("    ✅ 模型加载成功!")

# 查看模型方法
print("\n[2] Qwen3TTSModel 方法:")
methods = [m for m in dir(model) if not m.startswith('_')]
for m in methods:
    print(f"    - {m}")

# 查看子模型
print("\n[3] 子模型:")
if hasattr(model, 'model'):
    sub_model = model.model
    print(f"    子模型类型: {type(sub_model)}")
    sub_methods = [m for m in dir(sub_model) if not m.startswith('_') and callable(getattr(sub_model, m, None))]
    for m in sub_methods[:20]:
        print(f"    - {m}")

# 查看 core 模块
print("\n[4] qwen_tts.core 模块:")
from qwen_tts import core
print(f"    core 内容: {dir(core)}")

# 查看 inference 模块
print("\n[5] qwen_tts.inference 模块:")
from qwen_tts import inference
print(f"    inference 内容: {dir(inference)}")

# 尝试导出音频
print("\n[6] 尝试正确用法...")
try:
    # 查看 Qwen3TTSModel 的 __call__ 方法
    if hasattr(model, '__call__'):
        print("    模型有 __call__ 方法")

    # 检查 model.generate 是否存在（不是 method 而是子模型的 generate）
    if hasattr(model.model, 'generate'):
        print("    子模型有 generate 方法!")
except Exception as e:
    print(f"    错误: {e}")

print("\n" + "=" * 60)
