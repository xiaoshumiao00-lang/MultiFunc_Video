import torch
print("PyTorch version:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("Compute capability:", torch.cuda.get_device_capability(0))
    print("Total VRAM: {:.1f} GB".format(torch.cuda.get_device_properties(0).total_memory / 1024**3))

# Test tensor creation
try:
    x = torch.randn(1000, 1000, device='cuda')
    y = torch.randn(1000, 1000, device='cuda')
    z = torch.matmul(x, y)
    print("GPU computation test: PASSED")
except Exception as e:
    print("GPU computation test: FAILED")
    print("Error:", e)