"""测试ComfyUI文生图功能"""
import sys
import os

# 添加项目路径
sys.path.insert(0, r"c:\Users\Administrator\WorkBuddy\20260324112324\video-generator")

from utils.comfyui_api import ComfyUIAPI
import httpx
import json
import time

def test_comfyui_basic():
    """测试ComfyUI基本连接"""
    print("=" * 50)
    print("测试1: ComfyUI基本连接")
    print("=" * 50)

    api = ComfyUIAPI("http://127.0.0.1:8188")

    # 检查系统状态
    r = api.client.get("{}/system_stats".format(api.base_url))
    print("[OK] System stats: {}".format(r.status_code))
    data = r.json()
    print("  - ComfyUI版本: {}".format(data.get('system', {}).get('comfyui_version')))
    print("  - 显卡: {}".format(data.get('devices', [{}])[0].get('name', 'N/A')))

    return api

def test_model_list(api):
    """测试模型列表"""
    print("\n" + "=" * 50)
    print("测试2: 检查可用模型")
    print("=" * 50)

    # 获取object_info查看可用的节点
    r = api.client.get(f"{api.base_url}/object_info")
    if r.status_code == 200:
        info = r.json()
        print("[OK] 可用节点数: {}".format(len(info)))

    # 检查unet模型
    unet_path = r"D:\FLUX Redux\models\unet"
    if os.path.exists(unet_path):
        files = os.listdir(unet_path)
        print("[OK] UNet模型: {}".format(files))

    # 检查vae模型
    vae_path = r"D:\FLUX Redux\models\vae"
    if os.path.exists(vae_path):
        files = os.listdir(vae_path)
        print("[OK] VAE模型: {}".format(files))

    return True

def test_simple_prompt():
    """测试简单的prompt API"""
    print("\n" + "=" * 50)
    print("测试3: 提交简单Prompt")
    print("=" * 50)

    api = ComfyUIAPI("http://127.0.0.1:8188")

    # 构建一个非常简单的工作流
    # 使用秋叶整合包可能需要的节点
    workflow = {
        "3": {
            "inputs": {
                "ckpt_name": "flux1_dev_fp8.safetensors"
            },
            "class_type": "CheckpointLoaderSimple"
        }
    }

    # 尝试提交
    data = {
        "prompt": workflow,
        "prompt_id": "test-123",
        "number": 1
    }

    # 尝试不同的端点
    for endpoint in ["/prompt", "/v1/prompt", "/api/prompt"]:
        try:
            r = api.client.post(
                f"{api.base_url}{endpoint}",
                json=data,
                headers={"Content-Type": "application/json"}
            )
            print("  {}: {}".format(endpoint, r.status_code))
            if r.status_code == 200:
                print("  响应: {}".format(r.text[:200]))
                return True, r.json()
        except Exception as e:
            print("  {}: Error - {}".format(endpoint, e))

    return False, None

def test_generate_with_workflow():
    """测试使用完整工作流生成"""
    print("\n" + "=" * 50)
    print("测试4: 使用FLUX工作流生成图片")
    print("=" * 50)

    prompt_text = "一个穿着汉服的美丽女孩，精致五官，梦幻背景，高质量，8K"

    api = ComfyUIAPI("http://127.0.0.1:8188")

    # 构建FLUX工作流
    workflow = {
        "1": {
            "inputs": {"ckpt_name": "flux1_dev_fp8.safetensors"},
            "class_type": "CheckpointLoaderSimple"
        },
        "2": {
            "inputs": {
                "text": prompt_text,
                "clip": ["1", 0]
            },
            "class_type": "CLIPTextEncode"
        },
        "3": {
            "inputs": {
                "width": 1024,
                "height": 1024,
                "batch_size": 1
            },
            "class_type": "EmptyLatentImage"
        },
        "4": {
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["8", 0],
                "latent_image": ["3", 0],
                "seed": 42,
                "steps": 20,
                "cfg": 3.5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0
            },
            "class_type": "KSampler"
        },
        "5": {
            "inputs": {
                "samples": ["4", 0],
                "vae": ["1", 2]
            },
            "class_type": "VAEDecode"
        },
        "6": {
            "inputs": {
                "images": ["5", 0],
                "filename_prefix": "test_flux"
            },
            "class_type": "SaveImage"
        },
        "8": {
            "inputs": {
                "text": "",
                "clip": ["1", 0]
            },
            "class_type": "CLIPTextEncode"
        }
    }

    # 提交
    data = {"prompt": workflow, "prompt_id": "flux-test-001"}

    print("提交Prompt: {}...".format(prompt_text[:30]))

    for endpoint in ["/prompt", "/v1/prompt", "/api/prompt"]:
        try:
            r = api.client.post(
                "{}{}".format(api.base_url, endpoint),
                json=data,
                headers={"Content-Type": "application/json"}
            )
            print("  {}: {}".format(endpoint, r.status_code))
            if r.status_code == 200:
                result = r.json()
                prompt_id = result.get("prompt_id")
                print("  [OK] Prompt ID: {}".format(prompt_id))

                # 等待完成
                print("  等待生成完成...")
                time.sleep(3)

                # 获取历史
                history_r = api.client.get("{}/api/history/{}".format(api.base_url, prompt_id))
                if history_r.status_code == 200:
                    history = history_r.json()
                    if prompt_id in history:
                        status = history[prompt_id].get("status", {})
                        print("  状态: {}".format(status))
                        return True, prompt_id

                return True, prompt_id
            else:
                print("  响应: {}".format(r.text[:200]))
        except Exception as e:
            print("  Error: {}".format(e))

    return False, None

def main():
    print("ComfyUI API 测试")
    print("=" * 50)

    # 测试1: 基本连接
    api = test_comfyui_basic()

    # 测试2: 模型列表
    test_model_list(api)

    # 测试3: 简单Prompt
    success, result = test_simple_prompt()
    if not success:
        print("\n[WARNING] Prompt API可能需要不同的格式")
        print("请检查ComfyUI是否开启了API模式")

    # 测试4: 完整工作流
    success, prompt_id = test_generate_with_workflow()

    if success:
        print("\n[OK] ComfyUI API 测试成功！")
    else:
        print("\n[WARNING] 请在ComfyUI界面中开启'启用API'选项")

if __name__ == "__main__":
    main()
