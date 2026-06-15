"""测试 Qwen3-TTS 语音克隆"""
import os
os.environ['QUIET'] = '1'

from config import QWEN_TTS_SETTINGS
from utils.qwen_tts import Qwen3TTSTTS

print("=" * 50)
print("Qwen3-TTS 语音克隆测试")
print("=" * 50)

model_path = QWEN_TTS_SETTINGS.get("model_path", "")
ref_audio = QWEN_TTS_SETTINGS.get("ref_audio_path", "")
prompt_text = QWEN_TTS_SETTINGS.get("prompt_text", "")

print(f"模型路径: {model_path}")
print(f"参考音频: {ref_audio}")
print(f"参考文本: {prompt_text}")
print()

tts = Qwen3TTSTTS(model_path=model_path)

if not tts.is_available():
    print("错误: Qwen3-TTS 模型加载失败")
    exit(1)

info = tts.get_model_info()
print(f"模型类型: {info['tts_model_type']}")
print()

test_text = "大学生活中，学习是最重要的事情之一。掌握科学的学习方法，让你的成绩突飞猛进。"

print(f"合成文本: {test_text}")
print()

try:
    result = tts.generate_with_timestamps(
        text=test_text,
        ref_audio_path=ref_audio,
        prompt_text=prompt_text,
        output_path="outputs/audio/test_clone.wav"
    )

    print(f"[OK] 语音克隆成功!")
    print(f"  音频文件: {result['audio_path']}")
    print(f"  时长: {result['duration']:.2f}秒")
    print(f"  采样率: {result['sample_rate']}Hz")
    print(f"  音色: cloned")

except Exception as e:
    print(f"[FAIL] 语音克隆失败: {e}")
    import traceback
    traceback.print_exc()