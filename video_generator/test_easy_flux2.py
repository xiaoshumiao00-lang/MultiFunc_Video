"""测试秋叶easy fluxLoader工作流 - 带VAE解码"""
import httpx
import json
import time

api = 'http://127.0.0.1:8188'

# 使用秋叶easy fluxLoader - 完整工作流
workflow = {
    '1': {
        'inputs': {
            'ckpt_name': 'flux1_dev_fp8.safetensors',
            'vae_name': 'ae.safetensors',
            'lora_name': 'None',
            'lora_model_strength': 1.0,
            'lora_clip_strength': 1.0,
            'resolution': '1024 x 1024'
        },
        'class_type': 'easy fluxLoader'
    },
    '2': {
        'inputs': {
            'width': 1024,
            'height': 1024,
            'batch_size': 1
        },
        'class_type': 'EmptyLatentImage'
    },
    '3': {
        'inputs': {
            'model': ['1', 1],  # MODEL
            'positive': ['4', 0],
            'negative': ['5', 0],
            'latent_image': ['2', 0],
            'seed': 42,
            'steps': 20,
            'cfg': 1.0,
            'sampler_name': 'euler',
            'scheduler': 'simple',
            'denoise': 1.0
        },
        'class_type': 'KSampler'
    },
    '4': {
        'inputs': {
            'text': 'a beautiful girl, high quality, 8k'
        },
        'class_type': 'easy positive'
    },
    '5': {
        'inputs': {
            'text': ''
        },
        'class_type': 'easy negative'
    },
    '6': {
        'inputs': {
            'samples': ['3', 0],
            'vae': ['1', 2]  # VAE
        },
        'class_type': 'VAEDecode'
    },
    '7': {
        'inputs': {
            'images': ['6', 0],
            'filename_prefix': 'test_easy_flux'
        },
        'class_type': 'SaveImage'
    }
}

print('Testing easy fluxLoader workflow with VAE decode...')
data = {'prompt': workflow, 'prompt_id': 'easy-flux-test-002'}
r = httpx.post('{}/prompt'.format(api), json=data, headers={'Content-Type': 'application/json'}, timeout=30)
print('Status:', r.status_code)

if r.status_code != 200:
    print('Error Response:', r.text[:1500])
else:
    result = r.json()
    print('[OK] Prompt ID:', result.get('prompt_id'))

    print('Waiting for generation...')
    time.sleep(25)

    history_r = httpx.get('{}/api/history/{}'.format(api, result.get('prompt_id')), timeout=10)
    history = history_r.json()

    if result.get('prompt_id') in history:
        status = history[result.get('prompt_id')].get('status', {})
        print('Status:', status)

        if 'outputs' in history[result.get('prompt_id')]:
            outputs = history[result.get('prompt_id')]['outputs']
            print('Outputs keys:', list(outputs.keys()))

            # 检查图片
            for node_id, output in outputs.items():
                if 'images' in output:
                    for img in output['images']:
                        print('Generated image:', img.get('filename'))
