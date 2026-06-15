"""简化版视频合成测试"""
import subprocess
import os
from pathlib import Path

def get_audio_duration(audio_path):
    """获取音频时长"""
    from pydub import AudioSegment
    audio = AudioSegment.from_file(audio_path)
    return len(audio) / 1000.0

image_path = r"c:\Users\Administrator\WorkBuddy\20260324112324\video-generator\outputs\images\test_clone_final.png"
audio_path = r"c:\Users\Administrator\WorkBuddy\20260324112324\video-generator\outputs\audio\test_clone_final.wav"
output_path = r"c:\Users\Administrator\WorkBuddy\20260324112324\video-generator\output\test_simple_video.mp4"

# 检查文件
print(f"Image exists: {os.path.exists(image_path)}")
print(f"Audio exists: {os.path.exists(audio_path)}")

# 获取音频时长
duration = get_audio_duration(audio_path)
print(f"Audio duration: {duration:.2f}s")

# 简单FFmpeg命令（无字幕）
cmd = [
    "ffmpeg", "-y",
    "-loop", "1",
    "-i", image_path,
    "-i", audio_path,
    "-c:v", "libx264",
    "-preset", "fast",
    "-t", str(duration),
    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
    "-c:a", "aac",
    "-b:a", "192k",
    "-shortest",
    output_path
]

print(f"\nRunning FFmpeg command...")
result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')

if result.returncode == 0:
    print(f"[OK] Video created: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")
else:
    print(f"[FAIL] FFmpeg error:")
    print(result.stderr[:2000])