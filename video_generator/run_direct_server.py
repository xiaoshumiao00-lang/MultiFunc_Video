#!/usr/bin/env python3
"""
Fish Speech S2-Pro API Server - 稳定版
使用 bfloat16 + 显存优化
"""
import os
import sys
import gc
sys.path.insert(0, "/root/fish-speech")

os.environ["TOKENIZERS_PARALLELISM"] = "false"

import warnings
warnings.filterwarnings("ignore")

import torch
torch.cuda.empty_cache()
gc.collect()

print("=" * 60)
print("Fish Speech S2-Pro API Server")
print("=" * 60)
print(f"PyTorch: {torch.__version__}")
print(f"CUDA: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    props = torch.cuda.get_device_properties(0)
    print(f"VRAM: {props.total_memory / 1e9:.1f} GB")
print("=" * 60)

from fish_speech.models.text2semantic.llama import DualARTransformer
from fish_speech.models.text2semantic.inference import init_model, load_codec_model

checkpoint = "/root/fish-speech/checkpoints/fishaudio/s2-pro"

# ─── 1. 加载 Transformer 模型 ───
print("\n[1/3] Loading Transformer model (bfloat16)...")
model, decode_one_token = init_model(
    checkpoint_path=checkpoint,
    device="cuda",
    precision=torch.bfloat16,
    compile=False,
)

if torch.cuda.is_available():
    alloc = torch.cuda.memory_allocated() / 1e9
    reserved = torch.cuda.max_memory_reserved() / 1e9
    print(f"  Transformer loaded! VRAM: {alloc:.2f} GB allocated / {reserved:.2f} GB reserved")

# ─── 2. 设置缓存 ───
print("\n[2/3] Setting up KV caches...")
with torch.cuda.device("cuda"):
    model.setup_caches(
        max_batch_size=1,
        max_seq_len=model.config.max_seq_len,
        dtype=torch.bfloat16,
    )

if torch.cuda.is_available():
    alloc = torch.cuda.memory_allocated() / 1e9
    reserved = torch.cuda.max_memory_reserved() / 1e9
    print(f"  Caches ready! VRAM: {alloc:.2f} GB")

# ─── 3. 加载 Codec 模型 ───
print("\n[3/3] Loading codec model...")
codec = load_codec_model(
    codec_checkpoint_path=f"{checkpoint}/codec.pth",
    device="cuda",
    precision=torch.bfloat16,
)

if torch.cuda.is_available():
    alloc = torch.cuda.memory_allocated() / 1e9
    reserved = torch.cuda.max_memory_reserved() / 1e9
    total = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"  Codec loaded!")
    print(f"\n{'='*60}")
    print(f"  ALL LOADED SUCCESSFULLY!")
    print(f"  VRAM: {alloc:.2f} GB / {total:.1f} GB ({100*alloc/total:.0f}%)")
    print(f"{'='*60}")

# ─── 4. FastAPI 服务器 ───
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Fish Speech S2-Pro API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

class TTSRequest(BaseModel):
    text: str
    max_new_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9

@app.get("/v1/health")
async def health():
    vram = 0
    if torch.cuda.is_available():
        vram = torch.cuda.memory_allocated() / 1e9
    return {"status": "ok", "model": "fish-speech-s2-pro", "vram_gb": round(vram, 2)}

@app.get("/v1/models")
async def models():
    return {"models": [{"id": "fish-speech-s2-pro", "object": "model"}]}

@app.post("/v1/tts")
async def tts(req: TTSRequest):
    return {"message": "TTS ready", "text": req.text}

print("\nAPI: http://0.0.0.0:8080")
print("Docs: http://localhost:8080/docs\n")

uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")