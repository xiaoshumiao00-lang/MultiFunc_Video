"""
Stable Diffusion API 封装模块
用于调用本地部署的 Stable Diffusion WebUI 进行文生图
"""

import httpx
import base64
import json
from pathlib import Path
from typing import Optional, Dict, List


class SDGenerator:
    """Stable Diffusion 图片生成器"""

    def __init__(self, host: str = "http://127.0.0.1:7860"):
        """
        初始化SD生成器

        Args:
            host: Stable Diffusion WebUI 的 API 地址
        """
        self.host = host.rstrip("/")
        self.api_url = f"{self.host}/sdapi/v1"
        self.timeout = 300  # 5分钟超时

    def is_available(self) -> bool:
        """检查SD服务是否可用"""
        try:
            response = httpx.get(f"{self.api_url}/options", timeout=5)
            return response.status_code == 200
        except:
            return False

    def generate_image(self, prompt: str, negative_prompt: str = "",
                     width: int = 1080, height: int = 1920,
                     steps: int = 30, cfg_scale: float = 7.5,
                     seed: int = -1, output_path: Optional[str] = None) -> Dict:
        """
        生成图片

        Args:
            prompt: 正向提示词
            negative_prompt: 负面提示词
            width: 图片宽度
            height: 图片高度
            steps: 生成步数
            cfg_scale: CFG比例
            seed: 随机种子，-1表示随机
            output_path: 可选的输出路径

        Returns:
            包含图片信息的字典
        """
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "seed": seed if seed != -1 else -1,
            "sampler_index": "DPM++ 2M Karras",
        }

        # 调用 txt2img API
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.api_url}/txt2img", json=payload)
            response.raise_for_status()
            result = response.json()

        # 处理返回结果
        if "images" in result and len(result["images"]) > 0:
            image_data = result["images"][0]

            # 如果指定了输出路径，保存图片
            if output_path:
                self._save_image(image_data, output_path)

            return {
                "image_data": image_data,
                "image_path": output_path,
                "seed": result.get("parameters", {}).get("seed", -1),
                "info": result.get("info", "")
            }

        raise RuntimeError("图片生成失败：未返回有效结果")

    def _save_image(self, image_data: str, output_path: str) -> str:
        """保存Base64编码的图片"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 解码Base64
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        image_bytes = base64.b64decode(image_data)
        output_file.write_bytes(image_bytes)

        return str(output_file)

    def generate_with_styles(self, prompt: str, style: str = "anime",
                           negative_prompt: Optional[str] = None) -> Dict:
        """
        使用预设风格生成图片

        Args:
            prompt: 提示词
            style: 风格名称 (anime, photo, illustration, etc.)
            negative_prompt: 负面提示词

        Returns:
            生成结果
        """
        # 风格预设
        style_prompts = {
            "anime": {
                "prompt_add": "anime style, high quality, detailed",
                "negative": "realistic, photo, human, person, 3d render"
            },
            "photo": {
                "prompt_add": "photorealistic, high detail, 8k, professional photography",
                "negative": "anime, cartoon, illustration, drawing, painting"
            },
            "illustration": {
                "prompt_add": "digital illustration, artstation, concept art",
                "negative": "photo, realistic, photograph"
            },
            "study": {
                "prompt_add": "studying, books, desk, warm lighting, cozy atmosphere",
                "negative": "person, human, dirty, messy"
            },
            "campus": {
                "prompt_add": "university campus, buildings, greenery, sunny day",
                "negative": "crowded, dirty"
            }
        }

        style_config = style_prompts.get(style, style_prompts["anime"])

        full_prompt = f"{prompt}, {style_config['prompt_add']}"
        neg_prompt = negative_prompt or style_config['negative']

        return self.generate_image(full_prompt, neg_prompt)


def generate_simple_image(prompt: str, output_path: str,
                          sd_host: str = "http://127.0.0.1:7860") -> str:
    """
    简单接口生成单张图片

    Args:
        prompt: 提示词
        output_path: 输出路径
        sd_host: SD服务地址

    Returns:
        生成的图片路径
    """
    sd = SDGenerator(host=sd_host)

    if not sd.is_available():
        raise RuntimeError(
            "Stable Diffusion 服务未启动！\n"
            "请先启动 SD WebUI：\n"
            "  python launch.py --api --listen"
        )

    result = sd.generate_image(prompt, output_path=output_path)
    return result["image_path"]


if __name__ == "__main__":
    # 测试代码
    sd = SDGenerator()

    if sd.is_available():
        print("SD服务已连接")
        print("可用选项:", sd.api_url)
    else:
        print("SD服务未连接，请启动 SD WebUI")
