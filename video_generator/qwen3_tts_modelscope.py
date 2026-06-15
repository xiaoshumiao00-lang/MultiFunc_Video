#!/usr/bin/env python3
"""
Qwen3-TTS ModelScope 下载脚本
使用国内镜像下载，速度更快
"""
import os
import sys

print("=" * 60)
print("Qwen3-TTS ModelScope 下载")
print("=" * 60)

# 安装 modelscope
print("\n[1/3] 安装 ModelScope...")
import subprocess
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "modelscope", "-q"],
    capture_output=True,
    text=True
)
print("  ModelScope 安装完成!" if result.returncode == 0 else f"  安装失败: {result.stderr[:100]}")

# 下载模型
from modelscope import snapshot_download

MODEL_DIR = "/root/qwen3-tts/models"
os.makedirs(MODEL_DIR, exist_ok=True)

print("\n[2/3] 从 ModelScope 下载 Qwen3-TTS-1.7B-CustomVoice...")
print("  这可能需要 5-15 分钟，取决于网络速度...")

try:
    model_dir = snapshot_download(
        'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice',
        cache_dir=MODEL_DIR,
    )
    print(f"  下载完成: {model_dir}")
except Exception as e:
    print(f"  下载出错: {e}")
    print("\n  备选方案: 手动下载")
    print("  1. 访问 https://www.modelscope.cn/models/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
    print("  2. 下载模型文件到 /root/qwen3-tts/models/")

print("\n[3/3] 检查下载的文件...")
models_path = os.path.join(MODEL_DIR, "Qwen")
if os.path.exists(models_path):
    print("  模型文件:")
    for f in os.listdir(models_path):
        size = os.path.getsize(os.path.join(models_path, f)) / 1024 / 1024
        print(f"    {f}: {size:.1f} MB")
else:
    print("  模型目录不存在")

print("\n" + "=" * 60)
print("下载脚本完成!")
print("=" * 60)
