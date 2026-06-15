"""
Z-Image-Turbo 模型格式转换脚本
将 ModelScope 的 Diffusers 格式转换为 ComfyUI 格式

用法: python scripts/convert_z_image_to_comfyui.py
"""

import os
import shutil
from pathlib import Path
from safetensors.torch import load_file, save_file

# ============ 配置区 ============
# ModelScope 下载的模型路径
MODEL_SOURCE = Path(r"D:\Models\Tongyi-MAI\Z-Image-Turbo")

# ComfyUI 模型目录（秋叶整合包）
COMFYUI_MODELS = Path(r"D:\FLUX Redux\models")

# ================================

def merge_safetensors(input_files, output_path):
    """合并多个 safetensors 分片文件"""
    print(f"  合并 {len(input_files)} 个分片...")

    # 读取所有分片
    tensors = {}
    for f in sorted(input_files):
        print(f"    加载: {f.name}")
        part = load_file(str(f))
        tensors.update(part)

    # 保存合并后的文件
    print(f"    保存到: {output_path.name}")
    save_file(tensors, str(output_path))

    return output_path

def convert_text_encoder():
    """转换 text_encoder"""
    print("\n[1/3] 转换 text_encoder...")

    source_dir = MODEL_SOURCE / "text_encoder"
    target_dir = COMFYUI_MODELS / "text_encoders"
    target_dir.mkdir(parents=True, exist_ok=True)

    # 查找所有分片
    parts = sorted(source_dir.glob("model-*-of-*.safetensors"))
    if not parts:
        print("  [跳过] 未找到 text_encoder 分片文件")
        return

    output_file = target_dir / "qwen_3_4b.safetensors"

    if output_file.exists():
        print(f"  [跳过] {output_file.name} 已存在")
    else:
        merge_safetensors(parts, output_file)
        print(f"  [完成] → {output_file}")

def convert_transformer():
    """转换 transformer (主模型)"""
    print("\n[2/3] 转换 transformer (主模型)...")

    source_dir = MODEL_SOURCE / "transformer"
    target_dir = COMFYUI_MODELS / "diffusion_models"
    target_dir.mkdir(parents=True, exist_ok=True)

    # 查找所有分片
    parts = sorted(source_dir.glob("diffusion_pytorch_model-*-of-*.safetensors"))
    if not parts:
        print("  [跳过] 未找到 transformer 分片文件")
        return

    output_file = target_dir / "z_image_turbo_bf16.safetensors"

    if output_file.exists():
        print(f"  [跳过] {output_file.name} 已存在")
    else:
        merge_safetensors(parts, output_file)
        print(f"  [完成] → {output_file}")

def convert_vae():
    """转换 VAE"""
    print("\n[3/3] 转换 VAE...")

    source_file = MODEL_SOURCE / "vae" / "diffusion_pytorch_model.safetensors"
    target_dir = COMFYUI_MODELS / "vae"
    target_dir.mkdir(parents=True, exist_ok=True)

    output_file = target_dir / "ae.safetensors"

    if output_file.exists():
        print(f"  [跳过] {output_file.name} 已存在")
    elif source_file.exists():
        shutil.copy(source_file, output_file)
        print(f"  [完成] {source_file.name} → {output_file.name}")
    else:
        print("  [错误] 未找到 VAE 文件")

def main():
    print("=" * 60)
    print("Z-Image-Turbo 格式转换工具")
    print("=" * 60)
    print(f"\n源目录: {MODEL_SOURCE}")
    print(f"目标目录: {COMFYUI_MODELS}")

    # 检查源目录
    if not MODEL_SOURCE.exists():
        print(f"\n[错误] 源目录不存在: {MODEL_SOURCE}")
        print("请先下载模型")
        return

    # 转换各组件
    convert_text_encoder()
    convert_transformer()
    convert_vae()

    print("\n" + "=" * 60)
    print("转换完成!")
    print("=" * 60)
    print("\n后续步骤:")
    print("1. 重启 ComfyUI")
    print("2. 加载 Z-Image-Turbo 工作流")
    print("3. 如果 ComfyUI 能识别模型即可使用")
    print("\n注意: 如果 ComfyUI 仍无法加载，可能需要从 HuggingFace 下载")
    print("      ComfyUI 专用格式的版本")

if __name__ == "__main__":
    main()
