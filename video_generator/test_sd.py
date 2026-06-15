"""测试SD文生图"""
import httpx
import base64
import time

print("测试 Stable Diffusion 文生图...")
print("=" * 50)

# 检查SD服务
sd_url = "http://127.0.0.1:7860"

try:
    print(f"1. 检查SD服务状态: {sd_url}")
    response = httpx.get(f"{sd_url}/sdapi/v1/options", timeout=10)
    print(f"   状态码: {response.status_code}")
    if response.status_code == 200:
        print("   SD服务正常运行")
except Exception as e:
    print(f"   错误: {e}")
    print("\nSD服务未启动，请先启动SD WebUI")
    exit(1)

# 测试生成图片
print("\n2. 测试文生图...")
prompt = "a beautiful anime girl studying in a university library, warm lighting, high quality"
negative = "low quality, blurry, bad anatomy, watermark, text"

payload = {
    "prompt": prompt,
    "negative_prompt": negative,
    "width": 512,
    "height": 512,
    "steps": 20,
    "cfg_scale": 7.5,
    "sampler_index": "DPM++ 2M Karras",
}

try:
    with httpx.Client(timeout=120) as client:
        start = time.time()
        response = client.post(f"{sd_url}/sdapi/v1/txt2img", json=payload)
        elapsed = time.time() - start
        print(f"   生成耗时: {elapsed:.1f}秒")

    if response.status_code == 200:
        result = response.json()
        if "images" in result and result["images"]:
            image_data = result["images"][0]

            # 保存图片
            output_path = r"C:\Users\Administrator\WorkBuddy\20260324112324\video-generator\outputs\images\test_sd.png"
            if "," in image_data:
                image_data = image_data.split(",", 1)[1]
            image_bytes = base64.b64decode(image_data)
            with open(output_path, "wb") as f:
                f.write(image_bytes)

            print(f"   图片已保存: {output_path}")
            print(f"   图片大小: {len(image_bytes) / 1024:.1f} KB")

            # 获取seed
            if "parameters" in result and "seed" in result["parameters"]:
                print(f"   Seed: {result['parameters']['seed']}")
            else:
                # 从info中解析
                try:
                    info = result.get("info", "{}")
                    import json
                    info_obj = json.loads(info)
                    if "seed" in info_obj:
                        print(f"   Seed: {info_obj['seed']}")
                except:
                    pass

            print("\n✅ SD文生图测试成功！")
        else:
            print("   错误: 未返回图片")
            print(f"   响应: {result}")
    else:
        print(f"   错误: {response.status_code}")
        print(f"   响应: {response.text[:500]}")

except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()
