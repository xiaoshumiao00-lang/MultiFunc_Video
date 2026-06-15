"""使用秋叶FLUX工作流的正确格式"""
import httpx
import json
import time

api = 'http://127.0.0.1:8188'

# 根据秋叶工作流构建API格式
workflow = {
    "12": {  # UNETLoader - 加载Flux UNet
        "inputs": {
            "unet_name": "flux1_dev_fp8.safetensors",
            "weight_dtype": "fp8_e4m3fn"
        },
        "class_type": "UNETLoader"
    },
    "11": {  # DualCLIPLoader - 加载CLIP
        "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors",
            "type": "flux",
            "device": "default"
        },
        "class_type": "DualCLIPLoader"
    },
    "10": {  # VAELoader - 加载VAE
        "inputs": {
            "vae_name": "ae.safetensors"
        },
        "class_type": "VAELoader"
    },
    "5": {  # EmptyLatentImage
        "inputs": {
            "width": 768,
            "height": 1024,
            "batch_size": 1
        },
        "class_type": "EmptyLatentImage"
    },
    "6": {  # CLIPTextEncode - 正向提示词
        "inputs": {
            "clip": ["11", 0],  # DualCLIPLoader的CLIP输出
            "text": "1girl, solo, perfect face, long hair, realistic, high quality, 8k"
        },
        "class_type": "CLIPTextEncode"
    },
    "25": {  # RandomNoise
        "inputs": {
            "noise_seed": 73998681636965,
            "randomize": True
        },
        "class_type": "RandomNoise"
    },
    "16": {  # KSamplerSelect
        "inputs": {
            "sampler_name": "euler"
        },
        "class_type": "KSamplerSelect"
    },
    "17": {  # BasicScheduler
        "inputs": {
            "model": ["12", 0],  # UNETLoader的MODEL输出
            "scheduler": "simple",
            "steps": 25,
            "denoise": 1.0
        },
        "class_type": "BasicScheduler"
    },
    "22": {  # BasicGuider
        "inputs": {
            "model": ["17", 0],  # BasicScheduler的SIGMAS输出后接model
            "conditioning": ["6", 0]  # CLIPTextEncode的CONDITIONING输出
        },
        "class_type": "BasicGuider"
    },
    "13": {  # SamplerCustomAdvanced
        "inputs": {
            "noise": ["25", 0],
            "guider": ["22", 0],
            "sampler": ["16", 0],
            "sigmas": ["17", 0],
            "latent_image": ["5", 0]
        },
        "class_type": "SamplerCustomAdvanced"
    },
    "8": {  # VAEDecode
        "inputs": {
            "samples": ["13", 0],
            "vae": ["10", 0]
        },
        "class_type": "VAEDecode"
    },
    "9": {  # SaveImage
        "inputs": {
            "images": ["8", 0],
            "filename_prefix": "test_aki_flux"
        },
        "class_type": "SaveImage"
    }
}

# 简化版工作流 - 使用Standard节点
simple_workflow = {
    "1": {
        "inputs": {"unet_name": "flux1_dev_fp8.safetensors", "weight_dtype": "fp8_e4m3fn"},
        "class_type": "UNETLoader"
    },
    "2": {
        "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors", "type": "flux"},
        "class_type": "DualCLIPLoader"
    },
    "3": {
        "inputs": {"vae_name": "ae.safetensors"},
        "class_type": "VAELoader"
    },
    "4": {
        "inputs": {"width": 768, "height": 1024, "batch_size": 1},
        "class_type": "EmptyLatentImage"
    },
    "5": {
        "inputs": {"clip": ["2", 0], "text": "1girl, solo, perfect face, high quality, 8k"},
        "class_type": "CLIPTextEncode"
    },
    "6": {
        "inputs": {"model": ["1", 0], "positive": ["5", 0], "negative": ["5", 0], "latent_image": ["4", 0], "seed": 42, "steps": 25, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0},
        "class_type": "KSampler"
    },
    "7": {
        "inputs": {"samples": ["6", 0], "vae": ["3", 0]},
        "class_type": "VAEDecode"
    },
    "8": {
        "inputs": {"images": ["7", 0], "filename_prefix": "test_flux"},
        "class_type": "SaveImage"
    }
}

print('Testing AKi FLUX workflow (simplified)...')
data = {'prompt': simple_workflow, 'prompt_id': 'aki-flux-test-001'}
r = httpx.post('{}/prompt'.format(api), json=data, headers={'Content-Type': 'application/json'}, timeout=30)
print('Status:', r.status_code)

if r.status_code != 200:
    print('Error Response:', r.text[:1500])
else:
    result = r.json()
    print('[OK] Prompt ID:', result.get('prompt_id'))

    print('Waiting for generation...')
    time.sleep(30)

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
