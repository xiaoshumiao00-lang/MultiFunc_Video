"""测试 Z-Image-Turbo 完整视频生成流程"""
import sys
import asyncio
sys.path.insert(0, r"c:\Users\Administrator\WorkBuddy\20260324112324\video-generator")

import config
from utils.comfyui_api import ComfyUIAPI
from utils.gpt_sovits import GPTSoVITSTTS
from utils.subtitle import generate_ass_subtitle
from utils.video import create_video_with_subtitles
from pathlib import Path


def test_zimage_video():
    """测试 Z-Image-Turbo 完整视频生成"""
    print("=" * 60)
    print("Z-Image-Turbo 完整视频生成测试")
    print("=" * 60)

    # 测试文案
    test_text = "大学是人生中最重要的阶段之一，在这里我们将开启人生的新篇章。"
    output_name = "zimage_video_test"

    # 1. 检查 ComfyUI 连接
    print("\n[1/4] 检查 ComfyUI 连接...")
    api = ComfyUIAPI(config.COMFYUI_SETTINGS["api_url"])
    if not api.is_alive():
        print("[ERROR] ComfyUI 未响应")
        return
    print("[OK] ComfyUI 运行中")

    # 2. 生成图片
    print("\n[2/4] 生成图片 (Z-Image-Turbo)...")
    prompt = "A beautiful Chinese university student in a modern campus library, reading a book, warm afternoon sunlight, Chinese colorful illustration style, pure white background, textbook hand-drawn style, clean and smooth lines, vivid and natural student figure, bright contrasting colors, high quality, 8K"

    result = api.generate_image(
        prompt=prompt,
        width=768,
        height=1024,
        steps=config.ZIMAGE_SETTINGS["steps"],  # 8步
        seed=12345,
        output_path=str(config.IMAGES_DIR),
        model=config.ZIMAGE_SETTINGS["model"],
        vae=config.ZIMAGE_SETTINGS["vae"],
        clip1=config.ZIMAGE_SETTINGS["text_encoder"],
        model_type="zimage"
    )

    if not result["success"]:
        print(f"[ERROR] 图片生成失败: {result.get('error')}")
        return

    image_path = result["saved_paths"][0]
    print(f"[OK] 图片已生成: {image_path}")

    # 3. 生成音频 (使用 GPT-SoVITS)
    print("\n[3/4] 生成音频...")
    audio_path = config.AUDIO_DIR / f"{output_name}.wav"
    subtitle_path = config.AUDIO_DIR / f"{output_name}.ass"

    try:
        gpt_tts = GPTSoVITSTTS(api_url=config.GPT_SOVITS_SETTINGS["api_url"])
        audio_result = gpt_tts.generate_with_timestamps(
            text=test_text,
            ref_audio_path=config.GPT_SOVITS_SETTINGS["ref_audio_path"],
            prompt_text=config.GPT_SOVITS_SETTINGS["prompt_text"],
            ref_lang=config.GPT_SOVITS_SETTINGS["ref_lang"],
            text_lang=config.GPT_SOVITS_SETTINGS["text_lang"],
            output_path=str(audio_path),
            speed=config.GPT_SOVITS_SETTINGS["speed"]
        )
        print(f"[OK] 音频已生成: {audio_path}")
        print(f"     时长: {audio_result['duration']:.2f}秒")
    except Exception as e:
        print(f"[ERROR] 音频生成失败: {e}")
        return

    # 生成字幕
    generate_ass_subtitle(audio_result["words"], str(subtitle_path))
    print(f"[OK] 字幕已生成: {subtitle_path}")

    # 4. 合成视频
    print("\n[4/4] 合成视频...")
    video_path = config.VIDEOS_DIR / f"{output_name}.mp4"
    video_settings = config.VIDEO_SETTINGS.copy()

    try:
        create_video_with_subtitles(
            image_path=image_path,
            audio_path=str(audio_path),
            subtitle_path=str(subtitle_path),
            output_path=str(video_path),
            watermark_text="大学学业篇",
            video_settings=video_settings,
            watermark_settings=config.WATERMARK,
            subtitle_settings=config.SUBTITLE_SETTINGS
        )
        print(f"[OK] 视频已生成: {video_path}")
    except Exception as e:
        print(f"[ERROR] 视频合成失败: {e}")
        return

    print("\n" + "=" * 60)
    print("✅ 测试完成!")
    print("=" * 60)
    print(f"\n输出文件:")
    print(f"  视频: {video_path}")
    print(f"  图片: {image_path}")
    print(f"  音频: {audio_path}")
    print(f"  字幕: {subtitle_path}")


if __name__ == "__main__":
    test_zimage_video()