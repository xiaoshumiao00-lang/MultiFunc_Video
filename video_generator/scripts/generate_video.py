"""
视频合成脚本 - 使用FFmpeg合成最终视频
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.video import create_simple_video, create_video_with_subtitles
from config import VIDEO_SETTINGS, WATERMARK, SUBTITLE_SETTINGS


def synthesize_video(image_path: str, audio_path: str, output_path: str,
                    watermark_text: str = None, subtitle_path: str = None,
                    video_settings: dict = None) -> str:
    """
    合成视频

    Args:
        image_path: 背景图片路径
        audio_path: 配音音频路径
        output_path: 输出视频路径
        watermark_text: 水印文字（右上角）
        subtitle_path: SRT字幕文件路径
        video_settings: 视频设置

    Returns:
        生成的视频路径
    """
    # 使用配置或指定参数
    watermark_text = watermark_text or WATERMARK["text"]
    video_settings = video_settings or VIDEO_SETTINGS

    print(f"正在合成视频...")
    print(f"  图片: {image_path}")
    print(f"  音频: {audio_path}")
    print(f"  水印: {watermark_text}")

    # 确保输出目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 调用视频合成函数
    if subtitle_path and Path(subtitle_path).exists():
        output = create_video_with_subtitles(
            image_path=image_path,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            watermark_text=watermark_text,
            video_settings=video_settings,
            watermark_settings=WATERMARK,
            subtitle_settings=SUBTITLE_SETTINGS
        )
    else:
        output = create_simple_video(
            image_path=image_path,
            audio_path=audio_path,
            output_path=output_path,
            watermark_text=watermark_text
        )

    print(f"视频已生成: {output}")
    return output


def batch_synthesize(tasks: list) -> list:
    """
    批量合成视频

    Args:
        tasks: 任务列表，每项包含 image_path, audio_path, output_path, watermark_text, subtitle_path

    Returns:
        成功生成的视频路径列表
    """
    results = []

    print(f"开始批量合成，共 {len(tasks)} 个任务")
    print("=" * 60)

    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}] 正在处理...")

        try:
            output = synthesize_video(
                image_path=task["image_path"],
                audio_path=task["audio_path"],
                output_path=task["output_path"],
                watermark_text=task.get("watermark_text"),
                subtitle_path=task.get("subtitle_path")
            )
            results.append(output)
            print(f"✓ 成功: {output}")
        except Exception as e:
            print(f"✗ 失败: {e}")

    print("\n" + "=" * 60)
    print(f"批量合成完成！成功 {len(results)}/{len(tasks)} 个")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="视频合成工具")
    parser.add_argument("--image", "-i", type=str, required=True, help="背景图片路径")
    parser.add_argument("--audio", "-a", type=str, required=True, help="配音音频路径")
    parser.add_argument("--output", "-o", type=str, required=True, help="输出视频路径")
    parser.add_argument("--watermark", "-w", type=str, help="水印文字（右上角）")
    parser.add_argument("--subtitle", "-s", type=str, help="SRT字幕文件路径")

    args = parser.parse_args()

    try:
        output = synthesize_video(
            image_path=args.image,
            audio_path=args.audio,
            output_path=args.output,
            watermark_text=args.watermark,
            subtitle_path=args.subtitle
        )

        print("\n" + "=" * 60)
        print("视频合成完成！")
        print(f"输出文件: {output}")
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)
