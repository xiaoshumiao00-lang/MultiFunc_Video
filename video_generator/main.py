"""
抖音短视频批量生成工具 - 主程序
支持ComfyUI FLUX图片生成 + Edge-TTS/GPT-SoVITS语音 + FFmpeg视频合成
"""

import sys
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from config import (
    OUTPUTS_DIR, IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR,
    VIDEO_SETTINGS, WATERMARK, SUBTITLE_SETTINGS,
    VIDEO_THEMES, AVAILABLE_VOICES,
    TTS_MODE, EDGE_TTS_SETTINGS, GPT_SOVITS_SETTINGS, PRESET_VOICES,
    COMFYUI_SETTINGS, ZIMAGE_SETTINGS, DEFAULT_IMAGE_MODEL, IMAGE_SETTINGS
)
from utils.tts import TTsgenerator
from utils.subtitle import generate_ass_subtitle
from utils.gpt_sovits import GPTSoVITSTTS
from utils.video import create_simple_video, create_video_with_subtitles
from utils.subtitle import SubtitleGenerator
from scripts.batch_process import VideoBatchProcessor
from utils.smart_video import SmartVideoGenerator

# 导入ComfyUI API
try:
    from utils.comfyui_api import get_comfyui_api
    COMFYUI_AVAILABLE = True
except ImportError:
    COMFYUI_AVAILABLE = False
    print("[WARNING] ComfyUI API not available")


class VideoGenerator:
    """视频生成器主类"""

    def __init__(self, theme: str = "大学学业篇", voice: str = None,
                 ref_audio: str = None, prompt_text: str = None,
                 tts_mode: str = None,
                 use_comfyui: bool = True,
                 positive_prompt: str = None,
                 negative_prompt: str = ""):
        """
        初始化视频生成器

        Args:
            theme: 视频主题（决定水印文字）
            voice: 配音音色（仅Edge-TTS模式使用）
            ref_audio: 参考音频路径（GPT-SoVITS模式使用）
            prompt_text: 参考音频文本（GPT-SoVITS模式使用）
            tts_mode: TTS模式，可选 "edge" 或 "gpt_sovits"
            use_comfyui: 是否使用ComfyUI生成图片
            positive_prompt: 图片正向提示词
            negative_prompt: 图片负向提示词
        """
        self.theme = theme
        self.watermark_text = VIDEO_THEMES.get(theme, {}).get("watermark", theme)
        self.tts_mode = tts_mode or TTS_MODE
        self.use_comfyui = use_comfyui and COMFYUI_AVAILABLE
        self.positive_prompt = positive_prompt
        self.negative_prompt = negative_prompt

        if self.tts_mode == "gpt_sovits":
            self.ref_audio = ref_audio or GPT_SOVITS_SETTINGS["ref_audio_path"]
            self.prompt_text = prompt_text or GPT_SOVITS_SETTINGS["prompt_text"]
            print(f"Using GPT-SoVITS mode")
            print(f"  Ref audio: {self.ref_audio}")
        else:
            self.voice = voice or EDGE_TTS_SETTINGS["voice"]
            print(f"Using Edge-TTS mode")
            print(f"  Voice: {self.voice}")

        if self.use_comfyui:
            model_name = ZIMAGE_SETTINGS["model"] if DEFAULT_IMAGE_MODEL == "zimage" else COMFYUI_SETTINGS["model"]
            print(f"Using ComfyUI {DEFAULT_IMAGE_MODEL.upper()} for image generation (model: {model_name})")

    async def generate_single(self, text: str, image_prompt: str = None,
                            output_name: str = None) -> Dict:
        """
        生成单个视频

        Args:
            text: 文案文本
            image_prompt: 图片生成提示词（可选，为空时使用默认提示词）
            output_name: 输出文件名（不含扩展名）

        Returns:
            包含各文件路径的字典
        """
        output_name = output_name or f"video_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        print("=" * 60)
        print(f"Generating video: {output_name}")
        print("=" * 60)

        # 1. 生成音频和字幕
        print("\n[1/4] Generating audio...")

        if self.tts_mode == "gpt_sovits":
            audio_path = AUDIO_DIR / f"{output_name}.wav"
            subtitle_path = AUDIO_DIR / f"{output_name}.ass"

            gpt_tts = GPTSoVITSTTS(api_url=GPT_SOVITS_SETTINGS["api_url"])
            audio_result = gpt_tts.generate_with_timestamps(
                text=text,
                ref_audio_path=self.ref_audio,
                prompt_text=self.prompt_text,
                ref_lang=GPT_SOVITS_SETTINGS["ref_lang"],
                text_lang=GPT_SOVITS_SETTINGS["text_lang"],
                output_path=str(audio_path),
                speed=GPT_SOVITS_SETTINGS["speed"]
            )
        else:
            audio_path = AUDIO_DIR / f"{output_name}.mp3"
            subtitle_path = AUDIO_DIR / f"{output_name}.ass"

            tts = TTsgenerator(voice=self.voice)
            audio_result = await tts.generate_audio_with_timestamps(text, str(audio_path))

        generate_ass_subtitle(audio_result["words"], str(subtitle_path))

        print(f"  Audio: {audio_path}")
        print(f"  Subtitle: {subtitle_path}")
        print(f"  Duration: {audio_result['duration']:.2f}s")

        # 2. 生成图片
        print("\n[2/4] Generating image...")

        if self.use_comfyui:
            image_path = await self._generate_comfyui_image(
                text=text,
                image_prompt=image_prompt,
                output_name=output_name
            )
        else:
            image_path = self._create_text_image(text[:50], output_name)

        print(f"  Image: {image_path}")

        # 3. 合成视频
        print("\n[3/4] Synthesizing video...")

        # 调整视频尺寸
        video_settings = VIDEO_SETTINGS.copy()

        video_path = VIDEOS_DIR / f"{output_name}.mp4"

        create_video_with_subtitles(
            image_path=str(image_path),
            audio_path=str(audio_path),
            subtitle_path=str(subtitle_path),
            output_path=str(video_path),
            watermark_text=self.watermark_text,
            video_settings=video_settings,
            watermark_settings=WATERMARK,
            subtitle_settings=SUBTITLE_SETTINGS
        )

        print(f"  Video: {video_path}")

        # 4. 完成
        print("\n[4/4] Complete!")

        return {
            "video_path": str(video_path),
            "audio_path": str(audio_path),
            "subtitle_path": str(subtitle_path),
            "image_path": str(image_path),
            "duration": audio_result["duration"]
        }

    async def _generate_comfyui_image(self, text: str, image_prompt: str,
                                     output_name: str) -> Path:
        """使用ComfyUI FLUX生成图片"""
        api = get_comfyui_api()

        if not api.is_alive():
            print("  [WARNING] ComfyUI not available, using text image")
            return self._create_text_image(text[:50], output_name)

        # 确定提示词
        if image_prompt:
            pos_prompt = image_prompt
        elif self.positive_prompt:
            pos_prompt = self.positive_prompt
        else:
            # 默认提示词
            pos_prompt = f"插画风格，简洁背景，学生形象，人物生动，配色鲜明"

        neg_prompt = self.negative_prompt or "low quality, blurry, bad anatomy"

        # 获取视频尺寸
        width = VIDEO_SETTINGS.get("width", 1080)
        height = VIDEO_SETTINGS.get("height", 1920)

        # 获取当前图片模型配置
        if DEFAULT_IMAGE_MODEL == "zimage":
            img_settings = ZIMAGE_SETTINGS
        else:
            img_settings = COMFYUI_SETTINGS

        # 生成图片
        result = api.generate_image(
            prompt=pos_prompt,
            negative_prompt=neg_prompt,
            width=width,
            height=height,
            steps=img_settings.get("steps", 8 if DEFAULT_IMAGE_MODEL == "zimage" else 25),
            seed=0,
            output_path=str(IMAGES_DIR),
            model=img_settings.get("model"),
            vae=img_settings.get("vae"),
            clip1=img_settings.get("text_encoder" if DEFAULT_IMAGE_MODEL == "zimage" else "clip1"),
            clip2=img_settings.get("clip2"),
            model_type=img_settings.get("model_type", "flux" if DEFAULT_IMAGE_MODEL == "flux" else "zimage")
        )

        if result["success"] and result.get("saved_paths"):
            return Path(result["saved_paths"][0])
        else:
            print(f"  [WARNING] ComfyUI failed: {result.get('error', 'Unknown')}")
            return self._create_text_image(text[:50], output_name)

    def _create_text_image(self, text: str, output_name: str) -> Path:
        """创建文字图片（备用方案）"""
        from PIL import Image, ImageDraw, ImageFont

        img_path = IMAGES_DIR / f"{output_name}.png"
        width = VIDEO_SETTINGS.get("width", 1080)
        height = VIDEO_SETTINGS.get("height", 1920)

        img = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(img)

        # 渐变背景
        for y in range(height):
            ratio = y / height
            r = int(30 + 20 * ratio)
            g = int(30 + 30 * ratio)
            b = int(80 + 40 * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # 添加标题
        try:
            title_font = ImageFont.truetype("arial.ttf", 72)
            body_font = ImageFont.truetype("arial.ttf", 42)
        except:
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        title = self.watermark_text
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_width) // 2, 200), title,
                 fill=(255, 255, 255), font=title_font)

        # 正文
        display_text = text[:40] + "..." if len(text) > 40 else text
        body_bbox = draw.textbbox((0, 0), display_text, font=body_font)
        body_width = body_bbox[2] - body_bbox[0]
        draw.text(((width - body_width) // 2, height // 2),
                display_text, fill=(200, 200, 200), font=body_font)

        img.save(img_path)
        return img_path

    def generate_sync(self, text: str, image_prompt: str = None,
                    output_name: str = None) -> Dict:
        """同步版本"""
        return asyncio.run(self.generate_single(text, image_prompt, output_name))


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="抖音短视频批量生成工具 - 本地部署，完全免费，智能模式自动识别视频类别",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # ============ 智能模式（推荐：只需传入文案，自动识别类别） ============
  python main.py --smart-gen --text "你的文案内容"

  # 指定TTS引擎
  python main.py --smart-gen --text "你的文案" --tts edge

  # ============ Edge-TTS Mode (Fast & Free) ============
  python main.py --text "Your script content"

  # Specify voice
  python main.py --text "Script" --voice zh-CN-YunxiNeural

  # ============ GPT-SoVITS Mode (High Quality Clone) ============
  # 1. Start GPT-SoVITS service first:
  python scripts/start_gpt_sovits.py

  # 2. Run main program:
  python main.py --text "Script" --tts gpt_sovits

  # ============ ComfyUI Image Generation ============
  # ComfyUI FLUX is automatically used if available
  # Configure in config.py -> COMFYUI_SETTINGS

  # ============ Batch Processing ============
  python main.py --batch tasks.csv

  # ============ Other ============
  python main.py --gui        # Launch GUI
  python main.py --check      # Check services status
        """
    )

    parser.add_argument("--text", "-t", type=str, help="Script text for single video")
    parser.add_argument("--output", "-o", type=str, help="Output filename (without ext)")
    parser.add_argument("--theme", type=str, default=None,
                       choices=list(VIDEO_THEMES.keys()) + [None],
                       help="Video theme (auto-detected if not specified)")
    parser.add_argument("--voice", "-v", type=str,
                       choices=list(AVAILABLE_VOICES.keys()),
                       help="Voice (Edge-TTS only)")
    parser.add_argument("--batch", "-b", type=str, help="Batch process CSV file")

    # Image generation
    parser.add_argument("--image-prompt", type=str,
                       help="Custom image prompt for ComfyUI")
    parser.add_argument("--no-comfyui", action="store_true",
                       help="Disable ComfyUI image generation")

    # TTS settings
    parser.add_argument("--tts", type=str, default=TTS_MODE,
                       choices=["edge", "gpt_sovits"],
                       help="TTS engine mode")
    parser.add_argument("--ref-audio", type=str,
                       help="GPT-SoVITS reference audio path")
    parser.add_argument("--prompt-text", type=str,
                       help="GPT-SoVITS reference audio text")

    # Other
    parser.add_argument("--gui", "-g", action="store_true", help="Launch GUI")
    parser.add_argument("--smart-gen", action="store_true",
                       help="智能模式：自动分段、自动识别类别、自动生成图片（推荐）")
    parser.add_argument("--shot-preview", action="store_true",
                       help="Preview shots only (no video generation)")
    parser.add_argument("--check", action="store_true", help="Check services status")

    # LLM settings
    parser.add_argument("--local-llm", action="store_true",
                       help="使用本地Ollama模型生成分镜（需先安装Ollama并下载模型）")
    parser.add_argument("--llm-model", type=str, default="qwen3.5:9b",
                       help="本地模型名称（默认qwen3.5:9b）")

    args = parser.parse_args()

    # Ensure output directories exist
    for d in [OUTPUTS_DIR, IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # Check services
    if args.check:
        check_services()
        return

    # Launch GUI
    if args.gui:
        try:
            import gradio as gr
            launch_gradio_interface()
        except ImportError:
            print("Error: Please install gradio: pip install gradio")
            sys.exit(1)

    # Batch mode
    elif args.batch:
        processor = VideoBatchProcessor(
            theme=args.theme,
            voice=args.voice,
            use_comfyui=not args.no_comfyui
        )
        tasks = processor.load_tasks_from_csv(args.batch)

        async def run():
            stats = await processor.run_batch(tasks)
            print("\n" + "=" * 60)
            print("Batch processing complete!")
            print(f"  Total: {stats['total']}")
            print(f"  Success: {stats['success']}")
            print(f"  Failed: {stats['failed']}")
            print(f"  Output: {VIDEOS_DIR}")

        asyncio.run(run())

    # Smart generation mode
    elif args.text and args.smart_gen:
        generator = SmartVideoGenerator(
            theme=None,  # 自动识别类别
            tts_mode=args.tts,
            use_comfyui=not args.no_comfyui,
            use_local_llm=args.local_llm,  # 需加 --local-llm 才生成摘要
            local_llm_model=args.llm_model,
            auto_classify=True  # 开启自动分类
        )

        result = generator.generate_sync(
            content=args.text,
            output_name=args.output,
            positive_prompt=args.image_prompt
        )

        print("\n" + "=" * 60)
        print("Smart video generated successfully!")
        print(f"  Video: {result['video_path']}")
        print(f"  Subtitle: {result['subtitle_path']}")
        if result.get('cover_path'):
            print(f"  Cover: {result['cover_path']}")
        print(f"  Duration: {result['total_duration']:.1f}s")
        print(f"  Shots: {len(result['shots'])}")

    # Single video generation
    elif args.text:
        generator = VideoGenerator(
            theme=args.theme,
            voice=args.voice,
            ref_audio=args.ref_audio,
            prompt_text=args.prompt_text,
            tts_mode=args.tts,
            use_comfyui=not args.no_comfyui
        )
        result = generator.generate_sync(
            text=args.text,
            image_prompt=args.image_prompt,
            output_name=args.output
        )

        print("\n" + "=" * 60)
        print("Video generated successfully!")
        print(f"  Video: {result['video_path']}")
        print(f"  Audio: {result['audio_path']}")
        print(f"  Subtitle: {result['subtitle_path']}")
        print(f"  Image: {result['image_path']}")
        print(f"  Duration: {result['duration']:.2f}s")
    else:
        parser.print_help()
        print("\n" + "=" * 60)
        print(f"Current TTS Mode: {'GPT-SoVITS' if TTS_MODE == 'gpt_sovits' else 'Edge-TTS'}")
        print("\nAvailable voices (Edge-TTS):")
        for voice_id, voice_name in AVAILABLE_VOICES.items():
            print(f"  {voice_id}: {voice_name}")
        print("\nPreset voices (GPT-SoVITS):")
        for voice_id, voice_info in PRESET_VOICES.items():
            print(f"  {voice_id}: {voice_info['ref_audio']}")
        print("\n可用视频类别（智能模式会自动识别，无需手动选择）：")
        for theme_id in VIDEO_THEMES.keys():
            print(f"  {theme_id}")
        print("\nComfyUI status:", "Available" if COMFYUI_AVAILABLE else "Not available")
        print(f"Default image model: {DEFAULT_IMAGE_MODEL.upper()} ({IMAGE_SETTINGS['model']})")


def check_services():
    """Check all service statuses"""
    print("=" * 60)
    print("Service Status Check")
    print("=" * 60)

    # Check ComfyUI
    current_model = DEFAULT_IMAGE_MODEL.upper()
    model_name = ZIMAGE_SETTINGS["model"] if DEFAULT_IMAGE_MODEL == "zimage" else COMFYUI_SETTINGS["model"]
    print(f"\n[ComfyUI {current_model}] (Default: {DEFAULT_IMAGE_MODEL})")
    if COMFYUI_AVAILABLE:
        api = get_comfyui_api()
        if api.is_alive():
            info = api.get_system_info()
            print(f"  OK - Running at {IMAGE_SETTINGS['api_url']}")
            print(f"  Model: {model_name}")
        else:
            print(f"  ERROR - Not responding")
            print(f"  Start: Run D:/FLUX Redux/run.bat")
    else:
        print("  Not available")

    # Check Edge-TTS
    print("\n[Edge-TTS]")
    try:
        import edge_tts
        print("  OK - edge-tts installed")
    except ImportError:
        print("  ERROR - edge-tts not installed")
        print("  Install: pip install edge-tts")

    # Check GPT-SoVITS
    print("\n[GPT-SoVITS]")
    gpt_tts = GPTSoVITSTTS(api_url=GPT_SOVITS_SETTINGS["api_url"])
    if gpt_tts.is_available():
        print(f"  OK - Running at {GPT_SOVITS_SETTINGS['api_url']}")
    else:
        print(f"  WARNING - Not running")
        print(f"  Start: python scripts/start_gpt_sovits.py")

    # Check FFmpeg
    print("\n[FFmpeg]")
    import subprocess
    try:
        result = subprocess.run(["ffmpeg", "-version"],
                               capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.split("\n")[0]
            print(f"  OK - {version}")
    except FileNotFoundError:
        print("  ERROR - FFmpeg not found")
        print("  Install: choco install ffmpeg")

    # Check TTS mode
    print(f"\nCurrent TTS Mode: {TTS_MODE}")
    if TTS_MODE == "gpt_sovits":
        ref_audio = GPT_SOVITS_SETTINGS["ref_audio_path"]
        if Path(ref_audio).exists():
            print(f"  OK - Ref audio: {ref_audio}")
        else:
            print(f"  WARNING - Ref audio not found: {ref_audio}")
    else:
        print(f"  OK - Using Edge-TTS")


def launch_gradio_interface():
    """Launch Gradio GUI"""
    import gradio as gr

    def generate_video(text, theme, tts_mode, image_prompt):
        if not text:
            return "Please enter script content", None

        try:
            if tts_mode == "gpt_sovits":
                gen = VideoGenerator(
                    theme=theme,
                    ref_audio=GPT_SOVITS_SETTINGS["ref_audio_path"],
                    prompt_text=GPT_SOVITS_SETTINGS["prompt_text"],
                    tts_mode=tts_mode
                )
            else:
                gen = VideoGenerator(
                    theme=theme,
                    voice=EDGE_TTS_SETTINGS["voice"],
                    tts_mode=tts_mode
                )
            result = gen.generate_sync(text, image_prompt=image_prompt)
            return f"Success! Duration: {result['duration']:.2f}s", result['video_path']
        except Exception as e:
            return f"Failed: {e}", None

    theme_options = list(VIDEO_THEMES.keys())
    tts_options = ["edge", "gpt_sovits"]

    interface = gr.Interface(
        fn=generate_video,
        title="Video Generator - 视频生成器",
        description="Local deployment, free, supports batch processing",
        inputs=[
            gr.Textbox(label="Script / 文案", placeholder="Enter your script...",
                     lines=5),
            gr.Dropdown(choices=theme_options, value="大学学业篇",
                       label="Theme / 主题"),
            gr.Dropdown(choices=tts_options, value=TTS_MODE,
                       label="TTS Engine / 语音引擎"),
            gr.Textbox(label="Image Prompt / 图片提示词 (Optional)",
                     placeholder="Custom image style..."),
        ],
        outputs=[
            gr.Textbox(label="Status / 状态"),
            gr.Video(label="Generated Video / 生成的视频")
        ],
        examples=[
            ["大学生活中，学习是最重要的事情之一。掌握科学的学习方法，让你的成绩突飞猛进。", "大学学业篇", "edge", ""],
            ["考研复习需要科学的规划和坚持不懈的努力。每天进步一点点，最终成功就在眼前。", "考研攻略篇", "edge", ""],
        ]
    )

    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )


if __name__ == "__main__":
    main()
