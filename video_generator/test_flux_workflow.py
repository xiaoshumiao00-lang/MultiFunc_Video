"""测试FLUX工作流"""
import httpx
import json
import time

api = 'http://127.0.0.1:8188'

# 使用正确的Nunchaku FLUX工作流
workflow = {
    '1': {
        'inputs': {
            'model_path': 'flux1_dev_fp8.safetensors',
            'cache_threshold': 0,
            'attention': 'nunchaku-fp16',
            'cpu_offload': 'auto',
            'device_id': 0,
            'data_type': 'float16'
        },
        'class_type': 'NunchakuFluxDiTLoader'
    },
    '2': {
        'inputs': {
            'clip_name': 'clip_l.safetensors',
            'type': 'sd3'
        },
        'class_type': 'CLIPLoader'
    },
    '3': {
        'inputs': {
            'vae_name': 'ae.safetensors'
        },
        'class_type': 'VAELoader'
    },
    '4': {
        'inputs': {
            'clip': ['2', 0],
            'clip_l': 'a beautiful girl, high quality, 8k',
            't5xxl': 'a beautiful girl, high quality, 8k',
            'guidance': 3.5
        },
        'class_type': 'CLIPTextEncodeFlux'
    },
    '5': {
        'inputs': {
            'width': 1024,
            'height': 1024,
            'batch_size': 1
        },
        'class_type': 'EmptyLatentImage'
    },
    '6': {
        'inputs': {
            'model': ['1', 0],
            'max_shift': 1.15,
            'base_shift': 0.5,
            'width': 1024,
            'height': 1024
        },
        'class_type': 'ModelSamplingFlux'
    },
    '7': {
        'inputs': {
            'model': ['6', 0],
            'positive': ['4', 0],
            'negative': ['4', 0],
            'latent_image': ['5', 0],
            'seed': 42,
            'steps': 20,
            'cfg': 1.0,
            'sampler_name': 'euler',
            'scheduler': 'simple',
            'denoise': 1.0
        },
        'class_type': 'KSampler'
    },
    '8': {
        'inputs': {
            'samples': ['7', 0],
            'vae': ['3', 0]
        },
        'class_type': 'VAEDecode'
    },
    '9': {
        'inputs': {
            'images': ['8', 0],
            'filename_prefix': 'test_flux'
        },
        'class_type': 'SaveImage'
    }
}

print('Testing FLUX workflow...')
data = {'prompt': workflow, 'prompt_id': 'flux-test-005'}
r = httpx.post('{}/prompt'.format(api), json=data, headers={'Content-Type': 'application/json'}, timeout=30)
print('Status:', r.status_code)

if r.status_code != 200:
    print('Response:', r.text[:1000])
else:
    result = r.json()
    print('[OK] Prompt ID:', result.get('prompt_id'))

    # 等待生成
    print('Waiting for generation...')
    time.sleep(20)

    # 获取历史
    history_r = httpx.get('{}/api/history/{}'.format(api, result.get('prompt_id')), timeout=10)
    history = history_r.json()

    if result.get('prompt_id') in history:
        status = history[result.get('prompt_id')].get('status', {})
        print('Status:', status)

        if 'outputs' in history[result.get('prompt_id')]:
            outputs = history[result.get('prompt_id')]['outputs']
            print('Outputs keys:', list(outputs.keys()))

            # 检查是否有图片
            for node_id, output in outputs.items():
                if 'images' in output:
                    print('Generated {} images'.format(len(output['images'])))
