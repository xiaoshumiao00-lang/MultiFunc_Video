#!/usr/bin/env python3
"""通过 ModelScope 下载 digital_combination.json 缺失模型。"""
import sys
from pathlib import Path
from modelscope.hub.file_download import model_file_download
from modelscope.hub.snapshot_download import snapshot_download

ComfyRoot = Path("D:/FLUX Redux")
ModelsDir = ComfyRoot / "models"


def download_file(repo_id: str, file_path: str, local_dir: Path, rename: str | None = None):
    local_dir.mkdir(parents=True, exist_ok=True)
    print(f"[DOWNLOAD] {repo_id}/{file_path} -> {local_dir}")
    downloaded = model_file_download(
        model_id=repo_id,
        file_path=file_path,
        local_dir=str(local_dir),
    )
    downloaded_path = Path(downloaded)
    if rename and downloaded_path.name != rename:
        target = local_dir / rename
        if target.exists():
            target.unlink()
        downloaded_path.rename(target)
        print(f"[RENAMED] {downloaded_path.name} -> {rename}")
        return target
    return downloaded_path


def download_snapshot(repo_id: str, local_dir: Path):
    local_dir.mkdir(parents=True, exist_ok=True)
    print(f"[DOWNLOAD] {repo_id} -> {local_dir}")
    return snapshot_download(
        model_id=repo_id,
        cache_dir=str(local_dir),
        local_dir=str(local_dir),
    )


def main():
    # InfiniteTalk (MultiTalkModelLoader reads from diffusion_models, not checkpoints)
    download_file(
        "Kijai/WanVideo_comfy",
        "InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors",
        ModelsDir / "diffusion_models",
    )

    # lightx2v LoRA (rank64 available, alias to workflow expected name)
    download_file(
        "lightx2v/Wan2.1-I2V-14B-480P-StepDistill-CfgDistill-Lightx2v",
        "loras/Wan21_I2V_14B_lightx2v_cfg_step_distill_lora_rank64.safetensors",
        ModelsDir / "loras",
        rename="lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors",
    )

    # chinese-wav2vec2-base (DownloadAndLoadWav2VecModel loads from models/transformers)
    download_snapshot(
        "TencentGameMate/chinese-wav2vec2-base",
        ModelsDir / "transformers" / "TencentGameMate" / "chinese-wav2vec2-base",
    )

    print("\n[OK] Model downloads complete.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
