#!/usr/bin/env python3
import sys
sys.path.insert(0, "/root/fish-speech")

import torch
print("STEP1: Python and Torch OK")
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    props = torch.cuda.get_device_properties(0)
    print(f"VRAM: {props.total_memory / 1e9:.1f} GB")

print("STEP2: Importing DualARTransformer...")
from fish_speech.models.text2semantic.llama import DualARTransformer
print("STEP3: Importing init_model...")
from fish_speech.models.text2semantic.inference import init_model
print("STEP4: Importing load_codec_model...")
from fish_speech.models.text2semantic.inference import load_codec_model
print("STEP5: All imports OK")

print("STEP6: Loading model to GPU with bfloat16...")
model, decode_fn = init_model(
    checkpoint_path="/root/fish-speech/checkpoints/fishaudio/s2-pro",
    device="cuda",
    precision=torch.bfloat16,
    compile=False,
)
print("STEP7: Model loaded!")

if torch.cuda.is_available():
    alloc = torch.cuda.memory_allocated() / 1e9
    reserved = torch.cuda.max_memory_reserved() / 1e9
    print(f"VRAM allocated: {alloc:.2f} GB")
    print(f"VRAM reserved: {reserved:.2f} GB")

print("STEP8: Setting up caches...")
with torch.device("cuda"):
    model.setup_caches(
        max_batch_size=1,
        max_seq_len=model.config.max_seq_len,
        dtype=next(model.parameters()).dtype,
    )
print("STEP9: Caches ready!")

print("STEP10: Loading codec model...")
codec = load_codec_model(
    codec_checkpoint_path="/root/fish-speech/checkpoints/fishaudio/s2-pro/codec.pth",
    device="cuda",
    precision=torch.bfloat16,
)
print("STEP11: Codec loaded!")

if torch.cuda.is_available():
    alloc = torch.cuda.memory_allocated() / 1e9
    reserved = torch.cuda.max_memory_reserved() / 1e9
    print(f"FINAL VRAM allocated: {alloc:.2f} GB")
    print(f"FINAL VRAM reserved: {reserved:.2f} GB")

print("SUCCESS: Model loading complete!")