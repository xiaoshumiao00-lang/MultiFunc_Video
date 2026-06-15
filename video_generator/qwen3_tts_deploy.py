#!/usr/bin/env python3
"""
Qwen3-TTS 1.7B 一键部署脚本
使用 ModelScope 国内镜像下载
"""
import os
import sys
import subprocess

def run_cmd(cmd, desc):
    print(f"\n>>> {desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    失败: {result.stderr[:200] if result.stderr else 'unknown'}")
        return False
    print(f"    成功!")
    return True

def main():
    print("=" * 60)
    print("Qwen3-TTS 1.7B 部署脚本")
    print("=" * 60)

    conda_activate = "source ~/miniconda3/etc/profile.d/conda.sh && conda activate fish-speech"
    work_dir = "/root/qwen3-tts"
    model_dir = f"{work_dir}/models/Qwen3-TTS-12Hz-1.7B-CustomVoice"

    # 1. 检查环境
    print("\n[1/5] 检查环境...")
    if not run_cmd(f"wsl -- bash -c '{conda_activate} && python -c \"import torch; print(torch.__version__)\"'", "Python/PyTorch"):
        print("  请确保 WSL 和 PyTorch 环境已配置")
        return

    # 2. 安装依赖
    print("\n[2/5] 安装依赖...")
    deps = [
        ("qwen-tts", "qwen-tts"),
        ("modelscope", "ModelScope"),
    ]
    for name, pkg in deps:
        if not run_cmd(f"wsl -- bash -c '{conda_activate} && pip install {pkg} -q'", f"安装 {name}"):
            print(f"  {name} 安装失败")

    # 3. 下载模型
    print("\n[3/5] 下载模型 (ModelScope 镜像)...")
    print(f"  目标: {model_dir}")
    print("  预计时间: 5-15 分钟")

    download_script = f"""
{conda_activate}
cd {work_dir}
python -c "
from modelscope import snapshot_download
import os
os.makedirs('{model_dir}', exist_ok=True)
print('开始下载 Qwen3-TTS-1.7B-CustomVoice...')
print('(如果长时间无响应，可按 Ctrl+C 取消，然后尝试手动下载)')
model_dir = snapshot_download(
    'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice',
    cache_dir='{work_dir}/models',
)
print(f'下载完成: {{model_dir}}')
"
"""

    with open(f"{work_dir}/download_model.sh", "w") as f:
        f.write(download_script)

    if not run_cmd(f"wsl -- bash -c '{conda_activate} && python -c \"from modelscope import snapshot_download; print(1)\"'", "检查 ModelScope"):
        print("  ModelScope 导入失败，尝试安装...")
        run_cmd(f"wsl -- bash -c '{conda_activate} && pip install modelscope -q'", "安装 ModelScope")

    # 4. 创建测试脚本
    print("\n[4/5] 创建测试脚本...")

    test_script = f'''#!/usr/bin/env python3
import os
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

MODEL_PATH = "{model_dir}"
OUTPUT_DIR = "{work_dir}/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SAMPLE_TEXT = "大学生活是一段美好的时光，在这里我们可以学习知识，结交朋友。"

def main():
    print("加载模型...")
    model = Qwen3TTSModel.from_pretrained(
        MODEL_PATH if os.path.exists(MODEL_PATH) else "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        device_map="cuda",
        dtype=torch.bfloat16,
    )

    if torch.cuda.is_available():
        print(f"显存占用: {{torch.cuda.memory_allocated()/1e9:.2f}} GB")

    print("生成语音 (Vivian 音色)...")
    wavs, sr = model.generate_custom_voice(
        text=SAMPLE_TEXT,
        language="Chinese",
        speaker="Vivian",
    )

    output_path = os.path.join(OUTPUT_DIR, "test_custom_voice.wav")
    sf.write(output_path, wavs[0], sr)
    print(f"保存: {{output_path}}")
    print(f"时长: {{len(wavs[0])/sr:.2f}} 秒")
    print("完成!")

if __name__ == "__main__":
    main()
'''

    with open(f"{work_dir}/test_tts.py", "w") as f:
        f.write(test_script)

    print("    测试脚本已创建: /root/qwen3-tts/test_tts.py")

    # 5. 创建启动批处理
    print("\n[5/5] 创建 Windows 启动批处理...")

    bat_content = f'''@echo off
chcp 65001 > nul
title Qwen3-TTS 模型下载
echo ============================================================
echo Qwen3-TTS 模型下载
echo ============================================================
echo.
echo 正在从 ModelScope 下载模型...
echo 这可能需要 5-15 分钟，请耐心等待...
echo.
echo 按 Ctrl+C 可以取消
echo.

wsl -- bash -c "sed -i 's/\\r$//' {work_dir}/download_model.sh 2>/dev/null; bash {work_dir}/download_model.sh"

echo.
echo ============================================================
echo 下载完成!
echo.
echo 下一步:
echo 1. 运行测试: wsl -- bash -c "source ~/miniconda3/etc/profile.d/conda.sh ^&^& conda activate fish-speech ^&^& python {work_dir}/test_tts.py"
echo 2. 查看输出: {work_dir}/output/
echo ============================================================
pause
'''

    bat_path = "D:\\\\陈潘HBEU\\\\Desktop\\\\本地生成视频\\\\video-generator\\\\下载Qwen3TTS模型.bat"
    with open(bat_path, "w") as f:
        f.write(bat_content)

    print(f"    批处理已创建: {bat_path}")
    print("    双击运行即可下载模型!")

    print("\n" + "=" * 60)
    print("部署脚本完成!")
    print("=" * 60)
    print("\n下一步:")
    print("  1. 双击 [下载Qwen3TTS模型.bat] 下载模型")
    print("  2. 模型下载完成后，运行测试")
    print("  3. 验证语音克隆效果")
    print("=" * 60)

if __name__ == "__main__":
    main()
