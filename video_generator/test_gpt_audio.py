"""
测试GPT-SoVITS API是否能正常生成音频
"""
import requests
import os

# 测试文本
text = "第三：给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。"
ref_audio = r'C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\voices\my_voice.mp3'
prompt_text = "第三：给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。"

print("=" * 60)
print("测试GPT-SoVITS API")
print("=" * 60)
print(f"文本: {text}")
print(f"参考音频: {ref_audio}")
print(f"参考音频存在: {os.path.exists(ref_audio)}")
print()

# 检查参考音频时长
try:
    from pydub import AudioSegment
    ref = AudioSegment.from_file(ref_audio)
    print(f"参考音频时长: {len(ref)/1000:.2f}秒")
except Exception as e:
    print(f"无法读取参考音频: {e}")

print()
print("发送API请求...")

data = {
    'text': text,
    'text_lang': 'zh',
    'ref_audio_path': ref_audio,
    'prompt_text': prompt_text,
    'prompt_lang': 'zh',
    'top_k': 15,
    'top_p': 0.9,
    'temperature': 1.0,
    'speed': 1.0,
}

try:
    r = requests.post('http://127.0.0.1:9880/tts', json=data, timeout=300)
    print(f"状态码: {r.status_code}")
    print(f"Content-Type: {r.headers.get('Content-Type')}")
    print(f"Content-Length: {len(r.content)} bytes")
    
    if r.status_code == 200:
        # 保存音频
        output_path = r'C:\test_gpt_output.wav'
        with open(output_path, 'wb') as f:
            f.write(r.content)
        print(f"\n音频已保存: {output_path}")
        
        # 检查生成的音频
        try:
            audio = AudioSegment.from_file(output_path)
            duration = len(audio) / 1000.0
            print(f"生成音频时长: {duration:.2f}秒")
            
            if duration < 1.0:
                print("⚠️ 警告: 音频时长过短，可能生成失败！")
            else:
                print("✅ 音频生成正常")
                
            # 播放测试（如果有播放器）
            print(f"\n你可以手动播放此文件测试: {output_path}")
            
        except Exception as e:
            print(f"无法读取生成的音频: {e}")
    else:
        print(f"API请求失败: {r.text}")
        
except Exception as e:
    print(f"请求异常: {e}")
