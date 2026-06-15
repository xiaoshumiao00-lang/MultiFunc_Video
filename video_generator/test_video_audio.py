"""
测试视频合成时音频是否正确嵌入
"""
import subprocess
from pathlib import Path
import os

# 测试文件路径
image_path = r'C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\outputs\images\test_final3.png'
audio_path = r'C:\test_gpt_output.wav'  # 刚才生成的音频
output_path = r'C:\test_video_with_audio.mp4'

print("=" * 60)
print("测试视频合成 - 音频嵌入")
print("=" * 60)
print(f"图片: {image_path} (存在: {os.path.exists(image_path)})")
print(f"音频: {audio_path} (存在: {os.path.exists(audio_path)})")
print(f"输出: {output_path}")
print()

# 获取音频时长
try:
    from pydub import AudioSegment
    audio = AudioSegment.from_file(audio_path)
    duration = len(audio) / 1000.0
    print(f"音频时长: {duration:.2f}秒")
except Exception as e:
    print(f"无法读取音频: {e}")
    duration = 2.0

print("\n执行FFmpeg命令...")

# 构建简单的FFmpeg命令（无滤镜）
cmd = [
    "ffmpeg", "-y",
    "-loop", "1",
    "-i", image_path,
    "-i", audio_path,
    "-t", str(duration),
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "192k",
    output_path
]

print(f"命令: {' '.join(cmd)}")
print()

try:
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    
    if result.returncode == 0:
        print("[OK] FFmpeg执行成功")
        
        # 检查输出视频
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"[OK] 视频文件已生成: {size} bytes")
            
            # 用ffmpeg检查视频
            check_cmd = ["ffmpeg", "-i", output_path]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True, errors='ignore')
            
            if "Audio:" in check_result.stderr:
                print("[OK] 视频包含音频流")
            else:
                print("[FAIL] 视频没有音频流！")
                
            if "Duration:" in check_result.stderr:
                # 提取时长
                import re
                match = re.search(r'Duration: (\d+:\d+:\d+\.\d+)', check_result.stderr)
                if match:
                    print(f"[OK] 视频时长: {match.group(1)}")
            
            print(f"\n视频文件: {output_path}")
            print("请手动播放测试是否有声音")
        else:
            print("[FAIL] 视频文件未生成")
    else:
        print(f"[FAIL] FFmpeg错误:\n{result.stderr[:500]}")
        
except Exception as e:
    print(f"[FAIL] 执行异常: {e}")
