"""测试Edge-TTS作为对比"""
import asyncio
import edge_tts
import wave
import struct
import os

async def test_edge_tts():
    text = "第三：给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。"
    output = r"C:\test_edge_tts.wav"

    print("测试Edge-TTS...")
    print(f"文本: {text}")

    # 生成音频
    communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
    await communicate.save(output)

    print(f"音频已保存: {output}")

    # 检查音频
    with wave.open(output, 'rb') as w:
        frames = w.getnframes()
        rate = w.getframerate()
        duration = frames / rate
        print(f"音频信息: {frames}帧, {rate}Hz, 时长{duration:.2f}秒")

        data = w.readframes(frames)
        rms = 0
        for i in range(0, len(data), 2):
            try:
                sample = struct.unpack('h', data[i:i+2])[0]
                rms += sample * sample
            except:
                pass
        rms = (rms / (len(data) // 2)) ** 0.5
        print(f"音频RMS值: {rms:.2f}")

        if rms < 100:
            print("WARNING: 音频太安静！")
        elif rms > 30000:
            print("WARNING: 音频可能失真！")
        else:
            print("音频强度正常")

    return output

asyncio.run(test_edge_tts())
