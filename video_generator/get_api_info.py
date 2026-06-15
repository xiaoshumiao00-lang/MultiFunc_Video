"""获取GPT-SoVITS API详细信息"""
import requests
import json

API_URL = "http://127.0.0.1:9880"

def get_openapi_schema():
    """获取OpenAPI schema"""
    try:
        r = requests.get(f"{API_URL}/openapi.json", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"获取失败: {e}")
    return None

def main():
    schema = get_openapi_schema()
    if schema:
        print("="*60)
        print("GPT-SoVITS 组件schemas")
        print("="*60)

        # 打印components/schemas
        schemas = schema.get("components", {}).get("schemas", {})
        for name, details in schemas.items():
            print(f"\n--- {name} ---")
            print(json.dumps(details, indent=2, ensure_ascii=False)[:1000])

if __name__ == "__main__":
    main()