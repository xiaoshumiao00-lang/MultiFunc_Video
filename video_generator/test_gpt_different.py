"""测试GPT-SoVITS - 不同参数"""
import requests
import wave
import struct

ref_audio = r'C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\voices\my_voice.mp3'
prompt_text = "第三：给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。"

def test_audio(text, filename):
    print(f"\n测试: {filename}")
    print(f"文本: {text[:30]}...")

    data = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": ref_audio,
        "prompt_text": prompt_text,
        "prompt_lang": "zh",
        "top_k": 5,
        "top_p": 0.9,
        "temperature": 0.9,
        "speed_factor": 1.0,
        "repetition_penalty": 1.35,
    }

    r = requests.post('http://127.0.0.1:9880/tts', json=data, timeout=300)
    print(f"Status: {r.status_code}")

    output = rf'C:\{filename}.wav'
    with open(output, 'wb') as f:
        f.write(r.content)

    with wave.open(output, 'rb') as w:
        frames = w.getnframes()
        rate = w.getframerate()
        duration = frames / rate

        data_bytes = w.readframes(frames)
        rms = 0
        count = 0
        for i in range(0, len(data_bytes), 2):
            try:
                sample = struct.unpack('h', data_bytes[i:i+2])[0]
                rms += sample * sample
                count += 1
            except:
                pass
        if count > 0:
            rms = (rms / count) ** 0.5

        print(f"音频: {duration:.2f}秒, RMS: {rms:.2f}")
        if rms < 100:
            print(">>> 音频太安静！")
        elif rms > 30000:
            print(">>> 音频可能失真！")
        else:
            print(">>> 音频正常")

# 测试不同文本
test_audio("第三：给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。", "test1")
test_audio("你好，这是一个测试。", "test2")
test_audio("今天天气真好。", "test3")
