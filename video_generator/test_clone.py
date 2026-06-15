"""测试GPT-SoVITS声音克隆"""
import requests
import time
import os
from pydub import AudioSegment

API_URL = 'http://127.0.0.1:9880'
REF_AUDIO = r'c:\Users\Administrator\WorkBuddy\20260324112324\video-generator\voices\my_voice.mp3'
PROMPT_TEXT = '第三：给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。'

def test_post():
    """POST方式测试"""
    data = {
        "text": PROMPT_TEXT,
        "text_lang": "en",
        "ref_audio_path": REF_AUDIO,
        "prompt_text": PROMPT_TEXT,
        "prompt_lang": "en",
        "top_k": 15,
        "top_p": 0.9,
        "temperature": 1.0,
        "speed": 1.0,
    }

    print("Testing with POST method...")

    start = time.time()
    r = requests.post(f'{API_URL}/tts', json=data, timeout=300)
    elapsed = time.time() - start

    print(f"Status: {r.status_code}, Time: {elapsed:.2f}s")

    if r.status_code == 200:
        output_path = r'c:\Users\Administrator\WorkBuddy\20260324112324\video-generator\output\cloned_voice_post.wav'
        with open(output_path, 'wb') as f:
            f.write(r.content)
        print(f"[OK] Audio saved: {output_path}")
        print(f"Size: {os.path.getsize(output_path)} bytes")

        a = AudioSegment.from_file(output_path)
        print(f"Duration: {len(a)/1000:.2f} seconds")
        return output_path
    else:
        print(f"Error: {r.text[:500]}")
        return None

def test_get():
    """GET方式测试"""
    params = {
        "text": PROMPT_TEXT,
        "text_lang": "en",
        "ref_audio_path": REF_AUDIO,
        "prompt_text": PROMPT_TEXT,
        "prompt_lang": "en",
        "top_k": 15,
        "top_p": 0.9,
        "temperature": 1.0,
        "speed_factor": 1.0,
    }

    print("\nTesting with GET method...")

    start = time.time()
    r = requests.get(f'{API_URL}/tts', params=params, timeout=300)
    elapsed = time.time() - start

    print(f"Status: {r.status_code}, Time: {elapsed:.2f}s")

    if r.status_code == 200:
        output_path = r'c:\Users\Administrator\WorkBuddy\20260324112324\video-generator\output\cloned_voice_get.wav'
        with open(output_path, 'wb') as f:
            f.write(r.content)
        print(f"[OK] Audio saved: {output_path}")
        print(f"Size: {os.path.getsize(output_path)} bytes")

        a = AudioSegment.from_file(output_path)
        print(f"Duration: {len(a)/1000:.2f} seconds")
        return output_path
    else:
        print(f"Error: {r.text[:500]}")
        return None

if __name__ == "__main__":
    print("="*50)
    print("GPT-SoVITS Voice Cloning Test")
    print("="*50)
    print(f"Reference audio: {REF_AUDIO}")
    print(f"Prompt text: {PROMPT_TEXT}")
    print()

    test_post()
    test_get()