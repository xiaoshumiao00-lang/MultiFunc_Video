#!/usr/bin/env python3
"""
Fish Speech S2-Pro INT8 动态量化 + API 服务器
直接在模型加载后动态应用 INT8 量化，无需预量化文件
"""
import os
import sys
import json
import socket
import time

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:256"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
torch.backends.cudnn.benchmark = False
torch.cuda.empty_cache()

# 模型路径
MODEL_PATH = "/root/fish-speech/checkpoints/fishaudio/s2-pro"
CODEC_PATH = os.path.join(MODEL_PATH, "codec.pth")

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return False
        except:
            return True

print("=" * 60)
print("Fish Speech S2-Pro INT8 API Server")
print("=" * 60)
print(f"Model: {MODEL_PATH}")
print(f"Device: cuda")
print(f"Precision: INT8 (dynamic)")
print(f"CUDA: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    print(f"Free: {torch.cuda.mem_get_info()[0] / 1024**3:.1f} GB")
print("=" * 60)
print()

# Monkey-patch init_model to apply INT8 after loading
import fish_speech.models.text2semantic.inference as inference_module
original_init_model = inference_module.init_model

def patched_init_model(checkpoint_path, device, precision, compile=False):
    """Apply INT8 quantization after model loading"""
    from tools.llama.quantize import WeightOnlyInt8QuantHandler
    
    print("Loading model with INT8 quantization...")
    model = inference_module.DualARTransformer.from_pretrained(checkpoint_path, load_weights=True)
    
    # Apply INT8 quantization BEFORE moving to GPU (saves memory)
    print("Applying INT8 weight-only quantization...")
    quant_handler = WeightOnlyInt8QuantHandler(model)
    model = quant_handler.convert_for_runtime()
    print("INT8 quantization applied!")
    
    # Now move to GPU
    model = model.to(device=device, dtype=precision)
    print(f"Model moved to {device} with {precision}")
    
    if hasattr(torch.cuda, 'synchronize'):
        torch.cuda.synchronize()
    
    logger = __import__('loguru').logger
    logger.info(f"Restored model from checkpoint (INT8 quantized)")
    logger.info(f"VRAM used: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")

    if isinstance(model, inference_module.DualARTransformer):
        decode_one_token = inference_module.decode_one_token_ar
        logger.info("Using DualARTransformer")
    else:
        raise ValueError("Unsupported model type")

    model.fixed_temperature = torch.tensor(0.7, device=device, dtype=torch.float)
    model.fixed_top_p = torch.tensor(0.7, device=device, dtype=torch.float)
    model.fixed_repetition_penalty = torch.tensor(1.5, device=device, dtype=torch.float)
    model._cache_setup_done = False

    if compile:
        logger.info("Compiling function...")
        decode_one_token = torch.compile(
            decode_one_token,
            backend="inductor" if torch.cuda.is_available() else "aot_eager",
            mode="default" if torch.cuda.is_available() else None,
            fullgraph=True,
        )

    return model.eval(), decode_one_token

# Apply the patch
inference_module.init_model = patched_init_model

# Setup API args
args_dict = {
    "llama_checkpoint_path": MODEL_PATH,
    "decoder_checkpoint_path": CODEC_PATH,
    "decoder_config_name": "modded_dac_vq",
    "device": "cuda",
    "half": True,
    "compile": False,
    "listen": "0.0.0.0:8080",
    "workers": 1,
    "api_key": None,
    "mode": "tts",
    "max_text_length": 0
}

os.environ['FISH_API_SERVER_ARGS'] = json.dumps(args_dict)
os.chdir('/root/fish-speech')

# Check port
port = 8080
if is_port_in_use(port):
    print(f"Port {port} in use, killing old process...")
    os.system("pkill -f 'python.*int8' || true")
    time.sleep(2)

print("Creating app (loading INT8 model, please wait)...")
print("This may take 2-5 minutes...\n")

try:
    from tools.api_server import create_app
    app = create_app()
    print("\nServer started successfully!")
    print(f"API: http://0.0.0.0:8080")
    print(f"Docs: http://localhost:8080/docs")
    if torch.cuda.is_available():
        print(f"VRAM used: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
    print("\n" + "=" * 60)

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
