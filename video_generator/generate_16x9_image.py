"""生成16:9比例的中式插画风格图片"""
import sys
sys.path.insert(0, '.')

from utils.comfyui_api import get_comfyui_api
from config import IMAGE_SETTINGS, DEFAULT_IMAGE_MODEL, IMAGES_DIR

positive_prompt = """中式彩色插画，纯白色背景，课本手绘风格，线条简洁流畅，学生造型，人物生动自然，有场景互动感，配色对比鲜明"""

negative_prompt = """缺乏四肢，不干净的画面，真实人物，真实物品，黑色的人物，黑色背景，杂乱，无场景，背景颜色，人物无配色"""

def main():
    api = get_comfyui_api()

    print("Checking ComfyUI connection...")
    if not api.is_alive():
        print("[ERROR] ComfyUI is not running!")
        return

    print(f"[OK] ComfyUI connected")
    print(f"Model: {IMAGE_SETTINGS['model']} ({DEFAULT_IMAGE_MODEL.upper()})")
    print()

    print("Generating 16:9 image...")
    print(f"Prompt: {positive_prompt}")
    print(f"Negative: {negative_prompt}")
    print()

    # 16:9比例 - 1920x1080
    result = api.generate_image(
        prompt=positive_prompt,
        negative_prompt=negative_prompt,
        width=1920,   # 16:9 横屏
        height=1080,  # 16:9
        steps=IMAGE_SETTINGS.get("steps", 8 if DEFAULT_IMAGE_MODEL == "zimage" else 25),
        seed=0,
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
            print(f"Saved:")
            for path in result["saved_paths"]:
                print(f"  {path}")
    else:
        print(f"\n[ERROR] Failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()
