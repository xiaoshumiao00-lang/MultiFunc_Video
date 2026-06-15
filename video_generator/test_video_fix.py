"""测试视频生成修复"""
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from utils.video import create_video_with_subtitles

# 测试参数
image_path = r"C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\outputs\images\test_complete.png"
audio_path = r"C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\outputs\audio\test_complete.wav"
subtitle_path = r"C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\outputs\audio\test_complete.ass"
output_path = r"C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\output\test_complete.mp4"

print(f"图片: {image_path}")
print(f"音频: {audio_path}")
print(f"字幕: {subtitle_path}")
print(f"输出: {output_path}")

print(f"\n文件存在检查:")
print(f"  图片: {os.path.exists(image_path)}")
print(f"  音频: {os.path.exists(audio_path)}")
print(f"  字幕: {os.path.exists(subtitle_path)}")

try:
    result = create_video_with_subtitles(
        image_path=image_path,
        audio_path=audio_path,
        subtitle_path=subtitle_path,
        output_path=output_path,
        watermark_text="大学学业篇"
    )
    print(f"\n成功! 输出: {result}")
except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()