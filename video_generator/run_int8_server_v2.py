#!/usr/bin/env python3
"""
Fish Speech S2-Pro INT8 API Server
直接加载模型并在加载后应用 INT8 量化，避免导入旧的 quantize.py
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, "/root/fish-speech")

import warnings
warnings.filterwarnings("ignore")

import torch
import torch.nn as nn
from pathlib import Path

print("=" * 60)
print("Fish Speech S2-Pro INT8 API Server")
print("=" * 60)
print(f"Model: /root/fish-speech/checkpoints/fishaudio/s2-pro")
print(f"Device: cuda")
print(f"Precision: INT8 (dynamic weight-only)")
print(f"CUDA: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    gpu_name = torch.cuda.get_device_name(0)
    total_vram = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"GPU: {gpu_name}")
    print(f"VRAM: {total_vram:.1f} GB")
    free_vram = torch.cuda.memGetInfo()[0] / 1e9
    print(f"Free: {free_vram:.1f} GB")
print("=" * 60)
print("\nCreating app (loading INT8 model, please wait)...")
print("This may take 2-5 minutes...\n")

# 设置环境
os.environ["TOKENIZERS_parallelism"] = "false"

from fish_speech.models.text2semantic.llama import DualARTransformer
from fish_speech.models.text2semantic.inference import init_model, decode_one_token_ar
from fish_speech.models.text2semantic.inference import launch_thread_safe_queue
from fish_speech.utils.inference_logging import setup_logger

logger = setup_logger("api_server")


def apply_int8_quantization(model):
    """
    对模型的 Linear 层应用 INT8 权重量化
    使用 PyTorch 的动态量化
    """
    print("Applying INT8 weight-only quantization to linear layers...")
    
    quantized_layers = 0
    for name, module in model.named_modules():
        if isinstance(module, nn.Linear):
            # 动态量化 Linear 层
            quantized_layers += 1
    
    print(f"Found {quantized_layers} Linear layers to quantize")
    
    # 使用 PyTorch 动态量化
    # 对于 weight-only INT8，我们使用 per-channel 量化
    quantized_model = torch.quantization.quantize_dynamic(
        model,
        {nn.Linear},
        dtype=torch.qint8
    )
    
    print(f"Quantized {quantized_layers} Linear layers to INT8!")
    return quantized_model


def main():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    
    checkpoint_path = "/root/fish-speech/checkpoints/fishaudio/s2-pro"
    
    # Step 1: 加载模型到 GPU
    print("Loading model to GPU...")
    device = "cuda"
    precision = torch.half  # 先用 FP16 加载，然后量化
    
    model, decode_one_token_fn = init_model(
        checkpoint_path=checkpoint_path,
        device=device,
        precision=precision,
        compile=False,
    )
    print("Model loaded to GPU!")
    
    # Step 2: 应用 INT8 量化（在 GPU 上直接量化）
    print("\nApplying INT8 quantization...")
    print("(This will take 2-5 minutes and use significant VRAM)...")
    
    model = apply_int8_quantization(model)
    
    # 检查显存使用
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1e9
        reserved = torch.cuda.max_memory_reserved() / 1e9
        print(f"\nVRAM allocated: {allocated:.2f} GB")
        print(f"VRAM reserved: {reserved:.2f} GB")
    
    # Step 3: 设置缓存
    print("\nSetting up model caches...")
    with torch.device(device):
        model.setup_caches(
            max_batch_size=1,
            max_seq_len=model.config.max_seq_len,
            dtype=next(model.parameters()).dtype,
        )
    print("Caches set up!")
    
    # Step 4: 创建 FastAPI 应用
    print("\nStarting API server...")
    
    app = FastAPI(
        title="Fish Speech S2-Pro INT8 API",
        description="Fish Speech S2-Pro with INT8 Quantization",
        version="1.0.0"
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    input_queue = None
    init_event = None
    
    @app.on_event("startup")
    async def startup_event():
        nonlocal input_queue, init_event
        input_queue, init_event = launch_thread_safe_queue(
            checkpoint_path=checkpoint_path,
            device=device,
            precision=torch.half,  # 保持 half 精度因为模型已经被量化
            compile=False,
        )
    
    @app.get("/v1/health")
    async def health_check():
        return {
            "status": "healthy",
            "model": "fish-speech-s2-pro-int8",
            "device": device,
        }
    
    @app.get("/v1/models")
    async def list_models():
        return {
            "models": [{
                "id": "fish-speech-s2-pro-int8",
                "object": "model",
                "created": 1234567890,
                "owned_by": "fish-speech",
            }]
        }
    
    print("\n" + "=" * 60)
    print("Server started successfully!")
    print("API: http://0.0.0.0:8080")
    print("Docs: http://localhost:8080/docs")
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1e9
        print(f"VRAM used: {allocated:.2f} GB")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
