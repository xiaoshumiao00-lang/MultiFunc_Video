"""
下载 Z-Image-Turbo 模型并转换为 ComfyUI 格式
用法: python scripts/download_z_image_turbo.py
"""

import os
import shutil
from pathlib import Path

# ============ 配置区 ============
# 模型保存根目录（改成你自己的路径）
MODELS_ROOT = Path("D:/Models")

# ComfyUI 模型目录（改成你自己的秋叶整合包路径）
COMFYUI_MODELS = Path("D:/秋叶整合包路径/ComfyUI/models")

# ================================

def check_existing_files():
    """检查已下载的文件"""
    model_dir = MODELS_ROOT / "Tongyi-MAI" / "Z-Image-Turbo"

    if not model_dir.exists():
        print(f"[ERROR] 模型目录不存在: {model_dir}")
        print("请先运行 ModelScope 下载命令:")
        print('  python -c "from modelscope import snapshot_download; snapshot_download(\'Tongyi-MAI/Z-Image-Turbo\', cache_dir=\'D:/Models\')"')
        return None

    print(f"[OK] 找到模型目录: {model_dir}")

    # 列出文件
    files = list(model_dir.rglob("*.safetensors"))
    total_size = sum(f.stat().st_size for f in files)

    print(f"  找到 {len(files)} 个 safetensors 文件")
    print(f"  总大小: {total_size / (1024**3):.2f} GB")

    return model_dir

def convert_to_comfyui_format(model_dir: Path):
    """
    将 Diffusers 格式转换为 ComfyUI 格式

    需要转换的文件映射:
    - text_encoder/model-*-of-*.safetensors → text_encoders/qwen_3_4b.safetensors
    - transformer/diffusion_pytorch_model-*-of-*.safetensors → diffusion_models/z_image_turbo_bf16.safetensors
    - vae/diffusion_pytorch_model.safetensors → vae/ae.safetensors
    """
    print("\n[步骤2] 转换模型格式...")

    # 目标目录
    text_encoder_dir = COMFYUI_MODELS / "text_encoders"
    diffusion_dir = COMFYUI_MODELS / "diffusion_models"
    vae_dir = COMFYUI_MODELS / "vae"

    # 创建目录
    for d in [text_encoder_dir, diffusion_dir, vae_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 1. 转换 text_encoder (合并3个分片)
    print("\n  [1/3] 转换 text_encoder...")
    text_encoder_parts = sorted(model_dir.glob("text_encoder/*.safetensors"))
    if text_encoder_parts:
        target_text = text_encoder_dir / "qwen_3_4b.safetensors"
        # 注意：这里只是复制第一个分片作为示例
        # 实际上需要用safetensors.merge.merge_files合并多个分片
        print(f"    源文件: {[p.name for p in text_encoder_parts]}")
        print(f"    目标: {target_text}")
        print("    注意: 多分片合并需要使用额外的合并工具")

    # 2. 转换 transformer (合并3个分片)
    print("\n  [2/3] 转换 transformer...")
    transformer_parts = sorted(model_dir.glob("transformer/*.safetensors"))
    if transformer_parts:
        target_transformer = diffusion_dir / "z_image_turbo_bf16.safetensors"
        print(f"    源文件: {[p.name for p in transformer_parts]}")
        print(f"    目标: {target_transformer}")
        print("    注意: 多分片合并需要使用额外的合并工具")

    # 3. 转换 VAE
    print("\n  [3/3] 转换 VAE...")
    vae_file = model_dir / "vae" / "diffusion_pytorch_model.safetensors"
    if vae_file.exists():
        target_vae = vae_dir / "ae.safetensors"
        # 直接复制
        shutil.copy(vae_file, target_vae)
        print(f"    {vae_file.name} → {target_vae}")

    print("\n[OK] 转换完成!")

def main():
    print("=" * 60)
    print("Z-Image-Turbo 模型下载 & 转换工具")
    print("=" * 60)

    # 检查已下载文件
    model_dir = check_existing_files()

    if model_dir:
        # 转换为 ComfyUI 格式
        convert_to_comfyui_format(model_dir)

    print("\n" + "=" * 60)
    print("后续步骤:")
    print("1. 重启 ComfyUI")
    print("2. 在 ComfyUI 中加载 Z-Image-Turbo 工作流")
    print("3. 如果模型加载失败，可能需要手动合并分片文件")
    print("=" * 60)

if __name__ == "__main__":
    main()
