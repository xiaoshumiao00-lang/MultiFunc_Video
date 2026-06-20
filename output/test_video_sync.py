# -*- coding: utf-8 -*-
"""测试视频合成与声画同步（使用合成音频代替 TTS，启用 ComfyUI 图片生成）"""

import sys
import asyncio
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from utils.smart_video import SmartVideoGenerator, ShotSegment
from utils.university_template import create_university_video

OUTPUT_NAME = "sync_test"
OUTPUT_FOLDER = config.VIDEOS_DIR / OUTPUT_NAME
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# 构造 3 个分镜
texts = [
    "大学学业篇。第一件事，提前修学分。",
    "大一大二可以提前修大三大四的学分。",
    "这是最好的战略机遇期。"
]

shots = []
audio_files = []
for i, text in enumerate(texts):
    # 生成 3 秒测试音频（1kHz 正弦波）
    audio_path = config.AUDIO_DIR / f"{OUTPUT_NAME}_tone_{i}.wav"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=3.0",
        "-c:a", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        str(audio_path)
    ]
    subprocess.run(cmd, capture_output=True)
    audio_files.append(str(audio_path))

    shot = ShotSegment(
        index=i,
        cap=text,
        desc_prompt="",
        desc_keywords=["测试"],
        scene_prompt="生动的大学生校园场景",
        audio_path=str(audio_path),
        image_path=None,  # 让 _generate_images 生成
        duration=3.0
    )
    shots.append(shot)

# 计算时间戳
current_time = 0.0
for shot in shots:
    shot.start_time = current_time
    shot.end_time = current_time + shot.duration
    current_time = shot.end_time

# 使用 ComfyUI 生成图片（如果 ComfyUI 不可用则 fallback）
gen = SmartVideoGenerator(theme="大学学业篇", tts_mode="edge", use_comfyui=True, use_local_llm=False, auto_classify=False)
asyncio.run(gen._generate_images(shots, "", OUTPUT_NAME))

# 检查图片是否生成
for i, shot in enumerate(shots):
    print(f"Shot {i} image: {shot.image_path}")

# 合并音频
merged_audio = asyncio.run(gen._merge_audios(shots, OUTPUT_NAME))
print(f"Merged audio: {merged_audio}")

# 合成视频
shot_data = []
for i, shot in enumerate(shots):
    keyword = shot.desc_keywords[0] if shot.desc_keywords else "测试"
    shot_data.append({
        "image_path": shot.image_path,
        "keyword": keyword,
        "subtitle": shot.cap,
        "duration": shot.duration
    })

video_path = OUTPUT_FOLDER / "video.mp4"
create_university_video(
    shots=shot_data,
    theme="大学学业篇",
    audio_path=merged_audio,
    output_path=str(video_path),
    main_title=texts[0]
)

print(f"Video saved: {video_path}")
print(f"Total duration: {current_time:.2f}s")

# 验证视频时长
result = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
    capture_output=True, text=True
)
if result.returncode == 0:
    video_duration = float(result.stdout.strip())
    print(f"Actual video duration: {video_duration:.2f}s")
    print(f"Audio duration match: {abs(video_duration - current_time) < 0.5}")
