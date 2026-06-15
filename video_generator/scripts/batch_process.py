"""
批量处理脚本 - 批量生成短视频
支持从CSV或JSON导入文案列表
"""

import sys
import json
import csv
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    OUTPUTS_DIR, IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR,
    EDGE_TTS_SETTINGS, GPT_SOVITS_SETTINGS, WATERMARK, VIDEO_SETTINGS, VIDEO_THEMES, TTS_MODE
)
from utils.tts import TTsgenerator, generate_srt_subtitle
from utils.video import create_simple_video, create_video_with_subtitles
from utils.sd_api import SDGenerator


class VideoBatchProcessor:
    """批量视频处理器"""

    def __init__(self, theme: str = "大学学业篇", voice: str = None):
        """
        初始化处理器

        Args:
            theme: 视频主题
            voice: 配音音色
        """
        self.theme = theme
        self.watermark_text = VIDEO_THEMES.get(theme, {}).get("watermark", theme)
        self.voice = voice or TTS_SETTINGS["voice"]
        self.tts = TTsgenerator(voice=self.voice)

        # 统计
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "start_time": None
        }

    def load_tasks_from_csv(self, csv_path: str) -> List[Dict]:
        """从CSV文件加载任务"""
        tasks = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tasks.append(row)
        return tasks

    def load_tasks_from_json(self, json_path: str) -> List[Dict]:
        """从JSON文件加载任务"""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("tasks", [])

    async def process_single_task(self, task: Dict) -> Optional[str]:
        """
        处理单个任务

        Args:
            task: 任务字典，包含 text, image_prompt 等字段

        Returns:
            生成的视频路径，失败返回None
        """
        task_id = task.get("id", datetime.now().strftime("%Y%m%d%H%M%S"))
        text = task.get("text", "")
        image_prompt = task.get("image_prompt", "")
        output_name = task.get("output_name", f"video_{task_id}")

        if not text:
            print(f"  警告: 任务 {task_id} 缺少文本内容，跳过")
            return None

        print(f"\n  处理任务 {task_id}...")

        # 1. 生成音频
        audio_path = AUDIO_DIR / f"{output_name}.mp3"
        try:
            result = await self.tts.generate_audio_with_timestamps(text, str(audio_path))
            subtitle_path = AUDIO_DIR / f"{output_name}.srt"
            generate_srt_subtitle(result["words"], str(subtitle_path))
        except Exception as e:
            print(f"  音频生成失败: {e}")
            return None

        # 2. 处理图片（如果已提供本地路径或SD可用）
        image_path = task.get("image_path")
        if not image_path:
            # 尝试使用SD生成
            try:
                sd = SDGenerator()
                if sd.is_available():
                    sd_image_path = IMAGES_DIR / f"{output_name}.png"
                    sd.generate_with_styles(
                        prompt=image_prompt or text,
                        style="anime"
                    )
                    image_path = str(sd_image_path)
                else:
                    # 使用默认占位图
                    image_path = self._create_placeholder_image(output_name)
            except Exception as e:
                print(f"  图片生成失败: {e}")
                image_path = self._create_placeholder_image(output_name)

        # 3. 合成视频
        video_path = VIDEOS_DIR / f"{output_name}.mp4"
        try:
            create_video_with_subtitles(
                image_path=image_path,
                audio_path=str(audio_path),
                subtitle_path=str(subtitle_path),
                output_path=str(video_path),
                watermark_text=self.watermark_text,
                video_settings=VIDEO_SETTINGS
            )
        except Exception as e:
            print(f"  视频合成失败: {e}")
            return None

        return str(video_path)

    def _create_placeholder_image(self, name: str) -> str:
        """创建简单的占位图片"""
        from PIL import Image, ImageDraw, ImageFont

        img_path = IMAGES_DIR / f"{name}_placeholder.png"
        img = Image.new('RGB', (1080, 1920), color=(50, 50, 80))
        draw = ImageDraw.Draw(img)

        # 添加文字
        try:
            font = ImageFont.truetype("arial.ttf", 60)
        except:
            font = ImageFont.load_default()

        text = "AI Generated"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (1080 - text_width) // 2
        y = (1920 - text_height) // 2
        draw.text((x, y), text, fill=(255, 255, 255), font=font)

        img.save(img_path)
        return str(img_path)

    async def run_batch(self, tasks: List[Dict], output_callback=None) -> Dict:
        """
        运行批量处理

        Args:
            tasks: 任务列表
            output_callback: 每完成一个任务的回调函数

        Returns:
            处理统计结果
        """
        self.stats["total"] = len(tasks)
        self.stats["start_time"] = datetime.now()

        print("=" * 60)
        print(f"批量处理开始")
        print(f"  主题: {self.theme}")
        print(f"  水印: {self.watermark_text}")
        print(f"  音色: {self.voice}")
        print(f"  任务数: {len(tasks)}")
        print("=" * 60)

        for i, task in enumerate(tasks, 1):
            print(f"\n[{i}/{len(tasks)}]", end="")

            try:
                result = await self.process_single_task(task)
                if result:
                    self.stats["success"] += 1
                    print(f" ✓ 成功")
                    if output_callback:
                        output_callback(result)
                else:
                    self.stats["failed"] += 1
                    print(f" ✗ 失败")
            except Exception as e:
                self.stats["failed"] += 1
                print(f" ✗ 错误: {e}")

        elapsed = (datetime.now() - self.stats["start_time"]).total_seconds()
        self.stats["elapsed"] = elapsed

        return self.stats


def create_sample_csv(output_path: str):
    """创建示例CSV文件"""
    sample_data = [
        {
            "id": "001",
            "text": "大学生活中，学习是最重要的事情之一。",
            "image_prompt": "university student studying in library, warm lighting",
            "output_name": "sample_001"
        },
        {
            "id": "002",
            "text": "掌握高效的学习方法，让你的成绩突飞猛进。",
            "image_prompt": "books and notebook on desk, studying scene",
            "output_name": "sample_002"
        },
        {
            "id": "003",
            "text": "考研复习需要科学的规划和坚持不懈的努力。",
            "image_prompt": "person reading books, focused expression",
            "output_name": "sample_003"
        },
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sample_data[0].keys())
        writer.writeheader()
        writer.writerows(sample_data)

    print(f"示例CSV已创建: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量视频生成工具")
    parser.add_argument("--input", "-i", type=str, help="输入文件 (CSV或JSON)")
    parser.add_argument("--theme", "-t", type=str, default="大学学业篇",
                       choices=list(VIDEO_THEMES.keys()),
                       help="视频主题")
    parser.add_argument("--voice", "-v", type=str, help="配音音色")
    parser.add_argument("--sample", "-s", action="store_true",
                       help="创建示例CSV文件")

    args = parser.parse_args()

    if args.sample:
        create_sample_csv("sample_tasks.csv")
    elif args.input:
        processor = VideoBatchProcessor(theme=args.theme, voice=args.voice)

        # 加载任务
        input_path = Path(args.input)
        if input_path.suffix.lower() == ".csv":
            tasks = processor.load_tasks_from_csv(str(input_path))
        elif input_path.suffix.lower() == ".json":
            tasks = processor.load_tasks_from_json(str(input_path))
        else:
            print("错误: 输入文件必须是 CSV 或 JSON 格式")
            sys.exit(1)

        # 运行批量处理
        async def run():
            stats = await processor.run_batch(tasks)
            print("\n" + "=" * 60)
            print("处理完成！")
            print(f"  总任务: {stats['total']}")
            print(f"  成功: {stats['success']}")
            print(f"  失败: {stats['failed']}")
            print(f"  用时: {stats.get('elapsed', 0):.1f}秒")
            print(f"  输出目录: {VIDEOS_DIR}")

        asyncio.run(run())
    else:
        parser.print_help()
        print("\n" + "=" * 60)
        print("示例用法：")
        print("  python batch_process.py -i tasks.csv --theme 大学学业篇")
        print("  python batch_process.py -i tasks.json --voice zh-CN-YunxiNeural")
        print("  python batch_process.py --sample  # 创建示例CSV")
