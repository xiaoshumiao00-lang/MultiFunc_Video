#!/usr/bin/env python3
"""
Qwen3-TTS 模型下载脚本
下载 Qwen3-TTS-1.7B-CustomVoice 模型到本地
"""
import os
from pathlib import Path

model_dir = Path("/root/qwen3-tts/models/Qwen3-TTS-12Hz-1.7B-CustomVoice")
model_dir.parent.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("Qwen3-TTS-1.7B-CustomVoice 模型下载")
print("=" * 60)
print(f"目标路径: {model_dir}")
print()

# 使用 huggingface-cli 下载（推荐，速度快）
from huggingface_hub import snapshot_download

print("正在从 HuggingFace 下载模型...")
print("如果下载慢，可以尝试:")
print("  1. 设置国内镜像: huggingface-cli login")
print("  2. 或使用 ModelScope: https://www.modelscope.cn/models")
print()

try:
    # 下载完整模型
    local_dir = snapshot_download(
        repo_id="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        local_dir=str(model_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print(f"\n模型下载完成: {local_dir}")
    print("\n文件列表:")
    for f in sorted(model_dir.glob("*")):
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"  {f.name}: {size_mb:.1f} MB")
except Exception as e:
    print(f"下载出错: {e}")
    print("\n备选方案：手动下载")
    print("HuggingFace: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
    print("ModelScope: https://www.modelscope.cn/models/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
