import requests
import time

text = '测试音频是否正常播放'
ref_audio = r'C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\voices\my_voice.mp3'
prompt_text = '第三：给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。'

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

r = requests.post('http://127.0.0.1:9880/tts', json=data, timeout=300)
print(f'Status: {r.status_code}')
print(f'Content-Type: {r.headers.get("Content-Type")}')
print(f'Content-Length: {len(r.content)} bytes')

# 保存并检查
output_path = r'C:\test_tts.wav'
with open(output_path, 'wb') as f:
    f.write(r.content)
print(f'Saved to: {output_path}')
