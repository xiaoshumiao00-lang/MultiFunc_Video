import os
os.environ['QUIET'] = '1'

print("加载模型...")
from qwen_tts import Qwen3TTSModel

model_path = r"D:\陈潘HBEU\Desktop\MultiFunc_Video\Qwen3_TTS\Qwen3-TTS-12Hz-1___7B-Base"
model = Qwen3TTSModel.from_pretrained(model_path, device_map="cuda", dtype="bfloat16")

speakers = model.get_supported_speakers()
print(f"\n支持的音色数: {len(speakers)}")
print(f"音色列表: {speakers}")