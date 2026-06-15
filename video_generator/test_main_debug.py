"""调试main.py的视频生成"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import VIDEO_SETTINGS, WATERMARK, SUBTITLE_SETTINGS
from utils.video import create_video_with_subtitles

# 模拟main.py的参数
image_path = Path(r"C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\outputs\images\test_complete.png")
audio_path = Path(r"C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\outputs\audio\test_complete.wav")
subtitle_path = Path(r"C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\outputs\audio\test_complete.ass")
video_path = Path(r"C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\output\test_complete_debug.mp4")
watermark_text = "大学学业篇"

print(f"当前工作目录: {os.getcwd()}")
print(f"\n参数:")
print(f"  image_path: {image_path}")
print(f"  audio_path: {audio_path}")
print(f"  subtitle_path: {subtitle_path}")
print(f"  output_path: {video_path}")
print(f"  watermark_text: {watermark_text}")

print(f"\n文件存在:")
print(f"  图片: {image_path.exists()}")
print(f"  音频: {audio_path.exists()}")
print(f"  字幕: {subtitle_path.exists()}")

try:
    result = create_video_with_subtitles(
        image_path=str(image_path),
        audio_path=str(audio_path),
        subtitle_path=str(subtitle_path),
        output_path=str(video_path),
        watermark_text=watermark_text,
        video_settings=VIDEO_SETTINGS,
        watermark_settings=WATERMARK,
        subtitle_settings=SUBTITLE_SETTINGS
    )
    print(f"\n成功: {result}")
except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()