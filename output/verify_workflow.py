#!/usr/bin/env python3
"""验证 digital_combination.json 工作流所需的 ComfyUI 节点和模型是否就绪。"""
import json
import sys
from pathlib import Path

ComfyRoot = Path("D:/FLUX Redux")
NodesDir = ComfyRoot / "custom_nodes"
ModelsDir = ComfyRoot / "models"

required_nodes = [
    "ComfyUI-WanVideoWrapper",
    "audio-separation-nodes-comfyui",
    "ComfyUI-VideoHelperSuite",
    "ComfyUI-KJNodes",
    "ComfyUI-GetAudioDuration",
    "ComfyUI-Basic-Math",
]

required_models = {
    "diffusion_models/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors": ["diffusion_models"],
    "vae/Wan2_1_VAE_bf16.safetensors": ["vae"],
    "text_encoders/umt5-xxl-enc-bf16.safetensors": ["text_encoders"],
    "clip_vision/clip_vision_vit_h.safetensors": ["clip_vision"],
    "loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors": ["loras", "diffusion_models"],
    "diffusion_models/InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors": ["diffusion_models", "checkpoints"],
}

audio_model_dir = ModelsDir / "transformers" / "TencentGameMate" / "chinese-wav2vec2-base"


def node_exists(package: str) -> bool:
    variants = {package, package.replace("-", "_"), package.replace("_", "-")}
    return any((NodesDir / v).is_dir() for v in variants)


def find_model(rel_path: str, search_dirs: list[str]) -> Path | None:
    # First try the exact relative path (includes subdirectories like checkpoints/InfiniteTalk/)
    exact = ModelsDir / rel_path
    if exact.is_file():
        return exact
    # Fallback: search by filename in the allowed top-level directories
    name = Path(rel_path).name
    for d in search_dirs:
        candidate = ModelsDir / d / name
        if candidate.is_file():
            return candidate
    return None


def main():
    print("=" * 50)
    print("digital_combination.json 运行环境验证")
    print("=" * 50)

    all_ok = True

    print("\n[自定义节点检查]")
    for node in required_nodes:
        if node_exists(node):
            print(f"  [OK]   {node}")
        else:
            print(f"  [MISS] {node}")
            all_ok = False

    print("\n[工作流文件格式检查]")
    workflow_path = Path("D:/陈潘HBEU/Desktop/Pixelle-Video-v0.1.15-win64/Pixelle-Video/workflows/selfhost/digital_combination.json")
    if workflow_path.is_file():
        try:
            wf = json.loads(workflow_path.read_text(encoding="utf-8"))
            if isinstance(wf, dict) and any(isinstance(v, dict) and "class_type" in v for v in wf.values()):
                print(f"  [OK]   {workflow_path.name} 为 API 格式")
            elif isinstance(wf, dict) and "nodes" in wf and "links" in wf:
                print(f"  [WARN] {workflow_path.name} 为 UI 格式，需转换为 API 格式才能被 Pixelle-Video 调用")
                all_ok = False
            else:
                print(f"  [WARN] {workflow_path.name} 格式无法识别")
                all_ok = False
        except Exception as e:
            print(f"  [ERR]  解析失败: {e}")
            all_ok = False
    else:
        print(f"  [MISS] {workflow_path}")
        all_ok = False

    print("\n[模型文件检查]")
    for rel_path, dirs in required_models.items():
        found = find_model(rel_path, dirs)
        if found:
            print(f"  [OK]   {rel_path} -> {found}")
        else:
            print(f"  [MISS] {rel_path}")
            all_ok = False

    if audio_model_dir.is_dir():
        print(f"  [OK]   transformers/TencentGameMate/chinese-wav2vec2-base")
    else:
        print(f"  [MISS] transformers/TencentGameMate/chinese-wav2vec2-base")
        all_ok = False

    print()
    if all_ok:
        print("所有检查项均通过。请重启 ComfyUI 后加载工作流。")
    else:
        print("存在缺失项，请参考 digital_combination_diagnosis.md 进行安装/下载。")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
