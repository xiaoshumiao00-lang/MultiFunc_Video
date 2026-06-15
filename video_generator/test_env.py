#!/usr/bin/env python3
"""测试 Fish Speech 环境"""
import os
import sys

print("=" * 60)
print("Fish Speech 环境测试")
print("=" * 60)

# 测试 Python
print(f"Python: {sys.version}")

# 测试 torch
try:
    import torch
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
except Exception as e:
    print(f"PyTorch error: {e}")

# 测试 fish_speech
try:
    import fish_speech
    print(f"fish_speech: OK")
except Exception as e:
    print(f"fish_speech error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
