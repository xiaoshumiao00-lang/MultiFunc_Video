"""生成中式插画风格图片"""
import sys
sys.path.insert(0, '.')

from utils.comfyui_api import get_comfyui_api
from config import IMAGE_SETTINGS, DEFAULT_IMAGE_MODEL, IMAGES_DIR
import os

# 正向提示词
positive_prompt = """中式彩色插画，纯白色背景，课本手绘风格，线条简洁流畅，学生造型，人物生动自然，有场景互动感，配色对比鲜明"""

# 负向提示词
negative_prompt = """缺乏四肢，不干净的画面，真实人物，真实物品，黑色的人物，黑色背景，杂乱，无场景，背景颜色，人物无配色"""

def main():
    api = get_comfyui_api()

    print("检查ComfyUI连接...")
    if not api.is_alive():
        print("[错误] ComfyUI未运行，请先启动秋叶整合包！")
        return

    print(f"[OK] ComfyUI已连接")
    print(f"模型: {IMAGE_SETTINGS['model']} ({DEFAULT_IMAGE_MODEL.upper()})")
    print()

    print("正在生成图片...")
    print(f"提示词: {positive_prompt}")
    print(f"负向词: {negative_prompt}")
    print()

    # 生成图片
    result = api.generate_image(
        prompt=positive_prompt,
        negative_prompt=negative_prompt,
        width=768,
        height=1024,
        steps=IMAGE_SETTINGS.get("steps", 8 if DEFAULT_IMAGE_MODEL == "zimage" else 25),  # Z-Image只需8步
        seed=0,    # 随机种子
        output_path=str(IMAGES_DIR),
        model=IMAGE_SETTINGS["model"],
        vae=IMAGE_SETTINGS["vae"],
        clip1=IMAGE_SETTINGS.get("text_encoder" if DEFAULT_IMAGE_MODEL == "zimage" else "clip1"),
        clip2=IMAGE_SETTINGS.get("clip2"),
        model_type=IMAGE_SETTINGS.get("model_type", DEFAULT_IMAGE_MODEL)
    )

    if result["success"]:
        print("\n[OK] Generate success!")
        print(f"Prompt ID: {result['prompt_id']}")
        if result.get("saved_paths"):
            print(f"Saved paths:")
            for path in result["saved_paths"]:
                print(f"  {path}")
    else:
        print(f"\n[ERROR] Generate failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()
