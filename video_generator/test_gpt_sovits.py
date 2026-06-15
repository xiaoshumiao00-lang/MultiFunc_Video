"""GPT-SoVITS API 测试脚本"""
import requests
import json
import base64
import time
import os

API_URL = "http://127.0.0.1:9880"
REF_AUDIO = r"D:\陈潘HBEU\Desktop\Kimi_Agent_AI短视频批量生成\video_generator\assets\output\test_audio.wav"
PROMPT_TEXT = "这是一个测试音频"
OUTPUT_DIR = r"c:\Users\Administrator\WorkBuddy\20260324112324\video-generator\output"

def check_api():
    """检查API是否可用"""
    try:
        r = requests.get(f"{API_URL}/docs", timeout=5)
        print(f"API文档页面: {r.status_code}")
        return True
    except Exception as e:
        print(f"API连接失败: {e}")
        return False

def test_tts_get():
    """使用GET方式测试TTS"""
    if not os.path.exists(REF_AUDIO):
        print(f"错误: 参考音频不存在: {REF_AUDIO}")
        return None

    print(f"参考音频: {REF_AUDIO}")
    print(f"参考文本: {PROMPT_TEXT}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 使用GET方式，直接传递参数
    params = {
        "text": "大学生活中，学习是最重要的事情之一。掌握科学的学习方法，让你的成绩突飞猛进。",
        "text_lang": "en",
        "ref_audio_path": REF_AUDIO,
        "prompt_text": PROMPT_TEXT,
        "prompt_lang": "en",
        "top_k": 15,
        "top_p": 0.9,
        "temperature": 1.0,
        "speed_factor": 1.0,
    }

    print("\n" + "="*50)
    print("测试GPT-SoVITS (GET方式)...")
    print(f"输入文本: {params['text']}")
    print("="*50)

    try:
        start = time.time()
        r = requests.get(f"{API_URL}/tts", params=params, timeout=300)
        elapsed = time.time() - start

        print(f"\n响应状态: {r.status_code}")
        print(f"耗时: {elapsed:.2f}秒")
        print(f"Content-Type: {r.headers.get('Content-Type', 'unknown')}")

        if r.status_code == 200:
            content_type = r.headers.get('Content-Type', '')
            if 'audio' in content_type or 'wav' in content_type or 'octet' in content_type:
                # 保存音频文件
                output_path = os.path.join(OUTPUT_DIR, "test_gpt_sovits_get.wav")
                with open(output_path, 'wb') as f:
                    f.write(r.content)
                print(f"音频已保存: {output_path}")
                print(f"文件大小: {os.path.getsize(output_path)} bytes")
                return output_path
            else:
                print(f"响应内容: {r.text[:500]}")
                return None
        else:
            print(f"错误: {r.text}")
            return None
    except Exception as e:
        print(f"请求失败: {e}")
        return None

def test_tts_post():
    """使用POST方式测试TTS"""
    if not os.path.exists(REF_AUDIO):
        print(f"错误: 参考音频不存在: {REF_AUDIO}")
        return None

    print(f"\n参考音频: {REF_AUDIO}")
    print(f"参考文本: {PROMPT_TEXT}")

    # POST请求 - 尝试不同的语言组合
    test_cases = [
        {"text_lang": "en", "prompt_lang": "en"},
        {"text_lang": "en", "prompt_lang": "zh"},
        {"text_lang": "zh", "prompt_lang": "en"},
        {"text_lang": "auto", "prompt_lang": "en"},
    ]

    for i, tc in enumerate(test_cases):
        print(f"\n--- 测试 {i+1}: text_lang={tc['text_lang']}, prompt_lang={tc['prompt_lang']} ---")

        data = {
            "text": "大学生活中，学习是最重要的事情之一。掌握科学的学习方法，让你的成绩突飞猛进。",
            "text_lang": tc["text_lang"],
            "ref_audio_path": REF_AUDIO,
            "prompt_text": PROMPT_TEXT,
            "prompt_lang": tc["prompt_lang"],
            "top_k": 15,
            "top_p": 0.9,
            "temperature": 1.0,
        }

        try:
            start = time.time()
            r = requests.post(f"{API_URL}/tts", json=data, timeout=300)
            elapsed = time.time() - start

            print(f"  响应状态: {r.status_code}, 耗时: {elapsed:.2f}秒")

            if r.status_code == 200:
                content_type = r.headers.get('Content-Type', '')
                if 'audio' in content_type or 'wav' in content_type or 'octet' in content_type or 'json' not in content_type:
                    output_path = os.path.join(OUTPUT_DIR, f"test_gpt_sovits_post_{i+1}.wav")
                    with open(output_path, 'wb') as f:
                        f.write(r.content)
                    print(f"  [OK] 音频已保存: {output_path}, 大小: {os.path.getsize(output_path)} bytes")
                    return output_path
                else:
                    result = r.json()
                    print(f"  JSON响应: {result}")
            else:
                try:
                    error = r.json()
                    print(f"  错误: {error.get('message', error)}")
                except:
                    print(f"  响应: {r.text[:200]}")

        except Exception as e:
            print(f"  请求失败: {e}")

    return None

if __name__ == "__main__":
    print("="*50)
    print("GPT-SoVITS API 测试")
    print("="*50)

    if check_api():
        print("\n--- 测试1: GET方式 ---")
        result1 = test_tts_get()

        print("\n\n--- 测试2: POST方式 ---")
        result2 = test_tts_post()

        if result1 or result2:
            print("\n\n" + "="*50)
            print("[OK] GPT-SoVITS 测试成功!")
            if result1:
                print(f"GET方式输出: {result1}")
            if result2:
                print(f"POST方式输出: {result2}")
        else:
            print("\n\n[FAIL] 所有测试失败")