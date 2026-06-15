"""测试ComfyUI FLUX图片生成"""
import sys
sys.path.insert(0, r"c:\Users\Administrator\WorkBuddy\20260324112324\video-generator")

from utils.comfyui_api import ComfyUIAPI
import config

def test_flux_generation():
    print("=" * 50)
    print("ComfyUI FLUX 图片生成测试")
    print("=" * 50)

    api = ComfyUIAPI(config.COMFYUI_SETTINGS["api_url"])

    # 检查连接
    print("\n[1] 检查ComfyUI连接...")
    if api.is_alive():
        info = api.get_system_info()
        print("[OK] ComfyUI运行中")
        print("    版本:", info.get('system', {}).get('comfyui_version'))
        print("    显卡:", info.get('devices', [{}])[0].get('name', 'N/A'))
    else:
        print("[ERROR] ComfyUI未响应")
        return

    # 生成测试图片
    print("\n[2] 生成测试图片...")
    prompt = "一个穿着汉服的美丽女孩，精致五官，梦幻背景，高质量，8K"

    result = api.generate_image(
        prompt=prompt,
        width=768,
        height=1024,
        steps=25,
        seed=12345,
        output_path=str(config.IMAGES_DIR)
    )

    print("    Prompt:", prompt[:30], "...")

    if result["success"]:
        print("[OK] 生成成功!")
        print("    Prompt ID:", result["prompt_id"])
        print("    保存路径:", result.get("saved_paths", []))

        # 检查图片
        if result.get("saved_paths"):
            from PIL import Image
            import os
            img_path = result["saved_paths"][0]
            if os.path.exists(img_path):
                img = Image.open(img_path)
                print("    图片尺寸:", img.size)
    else:
        print("[ERROR] 生成失败:", result.get("error"))

    print("\n" + "=" * 50)

if __name__ == "__main__":
    test_flux_generation()
