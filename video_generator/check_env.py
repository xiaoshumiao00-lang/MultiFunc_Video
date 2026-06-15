#!/usr/bin/env python3
import sys
print("STEP1: Python OK", sys.version)

try:
    import torch
    print(f"STEP2: PyTorch OK: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"VRAM: {vram:.1f} GB")
except ImportError as e:
    print(f"PyTorch not found: {e}")
    sys.exit(1)

try:
    import transformers
    print(f"STEP3: transformers OK: {transformers.__version__}")
except ImportError:
    print("STEP3: transformers NOT installed")
    print("Will need to install transformers>=4.37.0")

try:
    import soundfile
    print("STEP4: soundfile OK")
except ImportError:
    print("STEP4: soundfile NOT installed")

try:
    import accelerate
    print(f"STEP5: accelerate OK: {accelerate.__version__}")
except ImportError:
    print("STEP5: accelerate NOT installed")

print("\n=== Environment check complete ===")
