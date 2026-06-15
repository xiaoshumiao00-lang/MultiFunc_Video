"""
音频生成脚本 - 使用Edge-TTS生成配音
"""

import asyncio
import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.tts import TTsgenerator, generate_srt_subtitle
from config import AUDIO_DIR, TTS_SETTINGS, AVAILABLE_VOICES


async def generate_audio(text: str, output_audio: str, voice: str = None,
                        rate: str = None, pitch: str = None) -> dict:
    """
    生成配音和字幕

    Args:
        text: 文案文本
        output_audio: 音频输出路径
        voice: 音色
        rate: 语速
        pitch: 音调

    Returns:
        包含音频信息和字幕路径的字典
    """
    # 使用配置或指定参数
    voice = voice or TTS_SETTINGS["voice"]
    rate = rate or TTS_SETTINGS["rate"]
    pitch = pitch or TTS_SETTINGS["pitch"]

    print(f"正在生成音频...")
    print(f"  音色: {voice} ({AVAILABLE_VOICES.get(voice, '未知')})")
    print(f"  语速: {rate}")
    print(f"  音调: {pitch}")

    # 创建TTS生成器
    tts = TTsgenerator(voice=voice, rate=rate, pitch=pitch)

    # 生成音频和时间戳
    result = await tts.generate_audio_with_timestamps(text, output_audio)

    # 生成SRT字幕
    output_srt = output_audio.replace(".mp3", ".srt")
    generate_srt_subtitle(result["words"], output_srt)

    print(f"音频已生成: {output_audio}")
    print(f"字幕已生成: {output_srt}")
    print(f"时长: {result['duration']:.2f}秒")

    return {
        "audio_path": output_audio,
        "subtitle_path": output_srt,
        "duration": result["duration"],
        "voice": voice
    }


def generate_audio_sync(text: str, output_audio: str, voice: str = None,
                       rate: str = None, pitch: str = None) -> dict:
    """同步版本的音频生成"""
    return asyncio.run(generate_audio(text, output_audio, voice, rate, pitch))


async def list_voices():
    """列出所有可用的中文音色"""
    import edge_tts

    voices = await edge_tts.list_voices()
    chinese_voices = [v for v in voices if v["Locale"].startswith("zh-")]

    print("=" * 60)
    print("可用的中文语音音色：")
    print("=" * 60)

    for voice in chinese_voices:
        print(f"\n名称: {voice['Name']}")
        print(f"  ShortName: {voice['ShortName']}")
        print(f"  性别: {voice['Gender']}")
        print(f"  语言: {voice['Locale']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="音频生成工具")
    parser.add_argument("--text", "-t", type=str, help="要转换的文本")
    parser.add_argument("--output", "-o", type=str, help="输出音频路径")
    parser.add_argument("--voice", "-v", type=str,
                       choices=list(AVAILABLE_VOICES.keys()),
                       help="选择音色")
    parser.add_argument("--rate", "-r", type=str, help="语速调整，如 +10%")
    parser.add_argument("--pitch", "-p", type=str, help="音调调整，如 +5Hz")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有可用音色")

    args = parser.parse_args()

    if args.list:
        asyncio.run(list_voices())
    elif args.text and args.output:
        # 确保输出目录存在
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)

        result = asyncio.run(generate_audio(
            args.text, args.output, args.voice, args.rate, args.pitch
        ))

        print("\n" + "=" * 60)
        print("生成完成！")
        print(f"音频文件: {result['audio_path']}")
        print(f"字幕文件: {result['subtitle_path']}")
    else:
        parser.print_help()
        print("\n" + "=" * 60)
        print("示例用法：")
        print("  python generate_audio.py -t '你好世界' -o output/audio.mp3")
        print("  python generate_audio.py -t '你好世界' -o output/audio.mp3 -v zh-CN-YunxiNeural")
        print("  python generate_audio.py --list  # 列出所有可用音色")
