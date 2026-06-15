"""测试修复后的GPT-SoVITS"""
import requests
import wave
import struct

text = "第三：给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。"
ref_audio = r'C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\voices\my_voice.mp3'
prompt_text = "第三：给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。"

print("测试修复后的GPT-SoVITS...")

data = {
    "text": text,
    "text_lang": "zh",
    "ref_audio_path": ref_audio,
    "prompt_text": prompt_text,
    "prompt_lang": "zh",
    "top_k": 15,
    "top_p": 0.9,
    "temperature": 1.0,
    "speed_factor": 1.0,  # 使用正确参数名
}

r = requests.post('http://127.0.0.1:9880/tts', json=data, timeout=300)
print(f"Status: {r.status_code}")

output = r'C:\test_gpt_fixed.wav'
with open(output, 'wb') as f:
    f.write(r.content)

# 检查音频
with wave.open(output, 'rb') as w:
    frames = w.getnframes()
    rate = w.getframerate()
    duration = frames / rate
    print(f'音频: {frames}帧, {rate}Hz, 时长{duration:.2f}秒')

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
    print(f'音频RMS值: {rms:.2f}')

    if rms < 100:
        print('WARNING: 音频太安静或是噪声！')
    elif rms > 30000:
        print('WARNING: 音频可能失真！')
    else:
        print('音频强度正常')

print(f"文件: {output}")
