"""测试智能视频生成"""
import asyncio
import sys
sys.path.insert(0, '.')

from utils.smart_video import SmartVideoGenerator

content = """传统教学模式太低效，AI递归学习法才是王炸。目前普遍的教学方式是从基础理论到高级应用，就像是建楼房，地基没打好就不让你搬砖。"""

async def main():
    generator = SmartVideoGenerator(
        theme="AI学习篇",
        tts_mode="gpt_sovits",
        use_comfyui=True
    )

    result = await generator.generate(
        content=content,
        output_name="test_ai_learning"
    )

    print("\n" + "=" * 60)
    print("生成完成!")
    print(f"视频: {result['video_path']}")
    print(f"字幕: {result['subtitle_path']}")
    print(f"总时长: {result['total_duration']:.1f}秒")
    print(f"分镜数: {len(result['shots'])}")

if __name__ == "__main__":
    asyncio.run(main())
