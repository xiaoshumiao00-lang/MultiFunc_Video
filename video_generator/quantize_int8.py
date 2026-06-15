#!/usr/bin/env python3
"""在WSL中运行INT8量化"""
import os
import sys
import time

print("=" * 60)
print("Fish Speech S2-Pro INT8 量化")
print("=" * 60)
print()

# 设置环境变量
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"
os.chdir("/root/fish-speech")

print(f"Starting quantization at {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("This may take 5-15 minutes...")
print()

from tools.llama.quantize import WeightOnlyInt8QuantHandler
from fish_speech.models.text2semantic.inference import load_model
from fish_speech.models.text2semantic.llama import find_multiple
import torch

checkpoint_path = "checkpoints/fishaudio/s2-pro"
device = "cpu"
precision = torch.bfloat16

print("Loading model (CPU, bfloat16)...")
t0 = time.time()
model, _ = load_model(
    checkpoint_path=checkpoint_path,
    device=device,
    precision=precision,
    compile=False,
)
print(f"Model loaded in {time.time() - t0:.2f}s")

print("\nQuantizing to INT8 weight-only...")
t1 = time.time()
quant_handler = WeightOnlyInt8QuantHandler(model)
quantized_state_dict = quant_handler.create_quantized_state_dict()
print(f"Quantization done in {time.time() - t1:.2f}s")

# Save quantized model
import shutil
from pathlib import Path

dst_name = Path("checkpoints/fishaudio/s2-pro-int8")
if dst_name.exists():
    print(f"Removing existing: {dst_name}")
    shutil.rmtree(dst_name)

print(f"\nCopying files to {dst_name}...")
shutil.copytree(str(Path(checkpoint_path).resolve()), str(dst_name.resolve()))

# Remove codec from destination (we don't need to copy it)
codec_dst = dst_name / "codec.pth"
if codec_dst.exists():
    codec_dst.unlink()

# Remove safetensors (we'll use model.pth instead)
for f in dst_name.glob("model-*.safetensors"):
    f.unlink()
index_json = dst_name / "model.safetensors.index.json"
if index_json.exists():
    index_json.unlink()

quantize_path = dst_name / "model.pth"
print(f"Saving quantized weights to {quantize_path}...")
quantize_path.unlink(missing_ok=True)
torch.save(quantized_state_dict, quantize_path)

total_time = time.time() - t0
print(f"\n{'=' * 60}")
print(f"Quantization complete! Total time: {total_time:.2f}s")
print(f"Quantized model saved to: {quantize_path}")
print(f"{'=' * 60}")
