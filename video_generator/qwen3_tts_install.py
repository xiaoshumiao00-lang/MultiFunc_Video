#!/usr/bin/env python3
"""
Qwen3-TTS 部署脚本
安装 qwen-tts 包
"""
import subprocess
import sys

print("=" * 60)
print("Qwen3-TTS 安装脚本")
print("=" * 60)

# 安装 qwen-tts 包
print("\n[1/2] 安装 qwen-tts 包...")
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-U", "qwen-tts", "--quiet"],
    capture_output=True,
    text=True
)
if result.returncode == 0:
    print("  qwen-tts 安装成功!")
else:
    print(f"  安装出错: {result.stderr[:200] if result.stderr else 'unknown error'}")

# 验证安装
print("\n[2/2] 验证安装...")
try:
    import qwen_tts
    print(f"  qwen_tts 版本: {qwen_tts.__version__ if hasattr(qwen_tts, '__version__') else '未知'}")
    
    from qwen_tts import Qwen3TTSModel
    print("  Qwen3TTSModel 导入成功!")
    
    print("\n" + "=" * 60)
    print("安装完成!")
    print("=" * 60)
except ImportError as e:
    print(f"  导入失败: {e}")
    print("\n备选方案: 使用 transformers 直接加载")
    print("  pip install transformers>=4.37.0")
