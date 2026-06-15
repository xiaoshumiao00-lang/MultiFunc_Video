"""
ComfyUI API 调用模块
用于通过API调用ComfyUI(秋叶整合包)生成图片
支持 FLUX.1 Dev 和 Z-Image-Turbo 模型
"""

import httpx
import json
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List


class ComfyUIAPI:
    """ComfyUI API 客户端 - 支持多种模型工作流"""

    def __init__(self, base_url: str = "http://127.0.0.1:8188"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=300)

    def is_alive(self) -> bool:
        """检查ComfyUI是否运行"""
        try:
            r = self.client.get(f"{self.base_url}/system_stats", timeout=5)
            return r.status_code == 200
        except:
            return False

    def get_system_info(self) -> Dict:
        """获取系统信息"""
        try:
            r = self.client.get(f"{self.base_url}/system_stats", timeout=5)
            if r.status_code == 200:
                return r.json()
        except:
            return {}

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 768,
        height: int = 1024,
        steps: int = 25,
        seed: int = 0,
        output_path: Optional[str] = None,
        model: str = "flux1_dev_fp8.safetensors",
        vae: str = "ae.safetensors",
        clip1: str = "t5xxl_fp8_e4m3fn.safetensors",
        clip2: str = "clip_l.safetensors",
        model_type: str = "flux"
    ) -> Dict[str, Any]:
        """
        通过ComfyUI 生成图片

        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            width: 图片宽度
            height: 图片高度
            steps: 采样步数
            seed: 随机种子(0表示随机)
            output_path: 输出路径
            model: 主模型文件名
            vae: VAE模型名
            clip1: CLIP模型1名
            clip2: CLIP模型2名
            model_type: 模型类型 "flux" 或 "zimage"

        Returns:
            包含生成结果的字典
        """
        # 生成随机种子
        if seed == 0:
            seed = int(time.time() * 1000) % 2147483647

        # 根据模型类型构建工作流
        if model_type == "zimage":
            workflow = self._build_zimage_workflow(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=steps,
                seed=seed,
                model=model,
                vae=vae,
                text_encoder=clip1
            )
            prompt_id_prefix = "zimage"
        else:
            # 构建FLUX工作流
            workflow = self._build_flux_workflow(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=steps,
                seed=seed,
                model=model,
                vae=vae,
                clip1=clip1,
                clip2=clip2
            )
            prompt_id_prefix = "flux"

        # 提交任务
        prompt_id = f"{prompt_id_prefix}-{uuid.uuid4().hex[:8]}"
        data = {"prompt": workflow, "prompt_id": prompt_id}

        r = self.client.post(
            f"{self.base_url}/prompt",
            json=data,
            headers={"Content-Type": "application/json"}
        )

        if r.status_code != 200:
            return {
                "success": False,
                "error": r.text,
                "prompt_id": prompt_id
            }

        result = r.json()

        # 等待完成
        max_wait = 300  # 5分钟超时
        poll_interval = 1.0

        for _ in range(int(max_wait / poll_interval)):
            time.sleep(poll_interval)

            history_r = self.client.get(
                f"{self.base_url}/api/history/{prompt_id}",
                timeout=10
            )

            if history_r.status_code == 200:
                history = history_r.json()
                if prompt_id in history:
                    status = history[prompt_id].get("status", {})
                    if status.get("completed"):
                        # 生成成功
                        images = []
                        filenames = []
                        if "outputs" in history[prompt_id]:
                            for node_id, node_output in history[prompt_id]["outputs"].items():
                                if "images" in node_output:
                                    for img in node_output["images"]:
                                        images.append(img)
                                        filenames.append(img.get("filename", ""))

                        # 保存图片
                        saved_paths = []
                        if output_path and images:
                            saved_paths = self._save_images(images, output_path)

                        return {
                            "success": True,
                            "prompt_id": prompt_id,
                            "images": images,
                            "filenames": filenames,
                            "saved_paths": saved_paths,
                            "status": status
                        }
                    elif "error" in str(status):
                        return {
                            "success": False,
                            "error": str(status),
                            "prompt_id": prompt_id
                        }

        return {
            "success": False,
            "error": "Timeout waiting for generation",
            "prompt_id": prompt_id
        }

    def _build_flux_workflow(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        seed: int,
        model: str,
        vae: str,
        clip1: str,
        clip2: str
    ) -> Dict:
        """构建FLUX工作流"""

        workflow = {
            # UNETLoader - 加载Flux UNet模型
            "1": {
                "inputs": {
                    "unet_name": model,
                    "weight_dtype": "fp8_e4m3fn"
                },
                "class_type": "UNETLoader"
            },
            # DualCLIPLoader - 加载CLIP模型
            "2": {
                "inputs": {
                    "clip_name1": clip1,
                    "clip_name2": clip2,
                    "type": "flux",
                    "device": "default"
                },
                "class_type": "DualCLIPLoader"
            },
            # VAELoader - 加载VAE
            "3": {
                "inputs": {
                    "vae_name": vae
                },
                "class_type": "VAELoader"
            },
            # EmptyLatentImage - 空白潜空间
            "4": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1
                },
                "class_type": "EmptyLatentImage"
            },
            # CLIPTextEncode - 正向提示词
            "5": {
                "inputs": {
                    "clip": ["2", 0],
                    "text": prompt
                },
                "class_type": "CLIPTextEncode"
            },
            # CLIPTextEncode - 负向提示词
            "6": {
                "inputs": {
                    "clip": ["2", 0],
                    "text": negative_prompt if negative_prompt else ""
                },
                "class_type": "CLIPTextEncode"
            },
            # KSampler - 采样
            "7": {
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["5", 0],
                    "negative": ["6", 0],
                    "latent_image": ["4", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": 1.0,  # FLUX通常用1.0
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0
                },
                "class_type": "KSampler"
            },
            # VAEDecode - 解码
            "8": {
                "inputs": {
                    "samples": ["7", 0],
                    "vae": ["3", 0]
                },
                "class_type": "VAEDecode"
            },
            # SaveImage - 保存
            "9": {
                "inputs": {
                    "images": ["8", 0],
                    "filename_prefix": f"flux_{seed}"
                },
                "class_type": "SaveImage"
            }
        }

        return workflow

    def _build_zimage_workflow(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        seed: int,
        model: str,
        vae: str,
        text_encoder: str
    ) -> Dict:
        """
        构建 Z-Image-Turbo 工作流

        Z-Image-Turbo 使用 S3-DiT 架构，与 FLUX 不同
        - 使用 Qwen 3B 作为文本编码器
        - 仅需 8 步即可生成高质量图片
        """

        workflow = {
            # 1. UNETLoader - 加载 Z-Image-Turbo 主模型
            "1": {
                "inputs": {
                    "unet_name": model,
                    "weight_dtype": "default"
                },
                "class_type": "UNETLoader"
            },
            # 2. CLIPLoader - 加载 Qwen 文本编码器
            "2": {
                "inputs": {
                    "clip_name": text_encoder,
                    "type": "lumina2"
                },
                "class_type": "CLIPLoader"
            },
            # 3. VAELoader - 加载 VAE
            "3": {
                "inputs": {
                    "vae_name": vae
                },
                "class_type": "VAELoader"
            },
            # 4. EmptySD3LatentImage - 空白潜空间图像 (Z-Image 用 SD3 类型)
            "4": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1
                },
                "class_type": "EmptySD3LatentImage"
            },
            # 5. CLIPTextEncode - 正向提示词编码
            "5": {
                "inputs": {
                    "text": prompt,
                    "clip": ["2", 0]
                },
                "class_type": "CLIPTextEncode"
            },
            # 6. ConditioningZeroOut - 负向条件 (清零)
            "6": {
                "inputs": {
                    "conditioning": ["5", 0]
                },
                "class_type": "ConditioningZeroOut"
            },
            # 7. ModelSamplingAuraFlow - 模型采样适配
            "7": {
                "inputs": {
                    "model": ["1", 0],
                    "shift": 3
                },
                "class_type": "ModelSamplingAuraFlow"
            },
            # 8. KSampler - 采样器 (Z-Image-Turbo 通常用 8 步)
            "8": {
                "inputs": {
                    "model": ["7", 0],
                    "positive": ["5", 0],
                    "negative": ["6", 0],
                    "latent_image": ["4", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": 1.0,
                    "sampler_name": "res_multistep",
                    "scheduler": "simple",
                    "denoise": 1.0
                },
                "class_type": "KSampler"
            },
            # 9. VAEDecode - VAE 解码
            "9": {
                "inputs": {
                    "samples": ["8", 0],
                    "vae": ["3", 0]
                },
                "class_type": "VAEDecode"
            },
            # 10. SaveImage - 保存图片
            "10": {
                "inputs": {
                    "images": ["9", 0],
                    "filename_prefix": f"zimage_{seed}"
                },
                "class_type": "SaveImage"
            }
        }

        return workflow

    def _save_images(self, images: List[Dict], output_path: str) -> List[str]:
        """保存生成的图片"""
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = []
        for img_info in images:
            filename = img_info.get("filename", "output.png")
            subfolder = img_info.get("subfolder", "")
            img_type = img_info.get("type", "output")

            # 从ComfyUI获取图片
            r = self.client.get(
                f"{self.base_url}/view",
                params={
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": img_type
                },
                timeout=30
            )

            if r.status_code == 200:
                save_path = output_dir / filename
                with open(save_path, "wb") as f:
                    f.write(r.content)
                saved_paths.append(str(save_path))

        return saved_paths

    def get_generated_images(self, prompt_id: str) -> List[Dict]:
        """获取指定prompt生成的图片"""
        r = self.client.get(f"{self.base_url}/api/history/{prompt_id}", timeout=10)
        if r.status_code == 200:
            history = r.json()
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                images = []
                for node_id, output in outputs.items():
                    if "images" in output:
                        images.extend(output["images"])
                return images
        return []


# 全局实例
_comfyui_api: Optional[ComfyUIAPI] = None


def get_comfyui_api() -> ComfyUIAPI:
    """获取ComfyUI API实例"""
    global _comfyui_api
    if _comfyui_api is None:
        _comfyui_api = ComfyUIAPI()
    return _comfyui_api


def generate_image(prompt: str, **kwargs) -> Dict[str, Any]:
    """快捷函数：生成图片"""
    api = get_comfyui_api()
    return api.generate_image(prompt, **kwargs)


def generate_zimage(prompt: str, **kwargs) -> Dict[str, Any]:
    """快捷函数：使用 Z-Image-Turbo 生成图片"""
    api = get_comfyui_api()
    return api.generate_image(prompt, model_type="zimage", **kwargs)


if __name__ == "__main__":
    # 测试
    api = ComfyUIAPI()

    # 检查连接
    print("Checking ComfyUI connection...")
    if api.is_alive():
        info = api.get_system_info()
        print(f"[OK] ComfyUI is running")
        print(f"  Version: {info.get('system', {}).get('comfyui_version')}")
        print(f"  Device: {info.get('devices', [{}])[0].get('name', 'N/A')}")
    else:
        print("[ERROR] ComfyUI is not responding")
