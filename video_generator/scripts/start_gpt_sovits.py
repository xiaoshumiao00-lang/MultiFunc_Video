"""
GPT-SoVITS 启动脚本
自动检测并启动GPT-SoVITS API服务
"""

import subprocess
import sys
import os
from pathlib import Path
import time
import httpx


def find_gpt_sovits():
    """查找GPT-SoVITS安装目录"""
    possible_paths = [
        # 用户桌面上可能的GPT-SoVITS位置
        Path("D:/陈潘HBEU/Desktop/GPT-SoVITS-1007-cu124/GPT-SoVITS-1007-cu124"),  # 用户的实际路径
        Path(os.path.expanduser("~/Desktop")) / "GPT-SoVITS",
        Path(os.path.expanduser("~/Desktop")) / "GPT-SoVITS-v2",
        Path(os.path.expanduser("~/Desktop")) / "GPT-SoVITS-v4",
        Path(os.path.expanduser("~/Desktop")) / "GPT-SoVITS-1007-cu124",
        Path(os.path.expanduser("~/Downloads")) / "GPT-SoVITS",
        # 常见安装位置
        Path("C:/GPT-SoVITS"),
        Path("D:/GPT-SoVITS"),
        Path("E:/GPT-SoVITS"),
        # 当前项目目录下
        Path(__file__).parent.parent / "GPT-SoVITS",
    ]

    for path in possible_paths:
        if path.exists():
            # 检查是否包含必要的文件
            if (path / "api_v2.py").exists() or (path / "go-webui.bat").exists():
                return path

    return None


def check_api_running(api_url: str = "http://127.0.0.1:9880") -> bool:
    """检查API服务是否正在运行"""
    try:
        response = httpx.get(f"{api_url}/", timeout=2)
        return response.status_code == 200
    except:
        return False


def start_api_server(gpt_sovits_path: Path):
    """启动GPT-SoVITS API服务"""
    api_script = gpt_sovits_path / "api_v2.py"

    if not api_script.exists():
        print(f"错误: 找不到API脚本 {api_script}")
        return False

    print(f"正在启动GPT-SoVITS API服务...")
    print(f"路径: {gpt_sovits_path}")

    # 设置环境
    env = os.environ.copy()

    # Windows上使用bat启动
    if sys.platform == "win32":
        # 创建启动脚本
        startup_script = gpt_sovits_path / "start_api.bat"
        startup_script.write_text(f'''@echo off
cd /d "{gpt_sovits_path}"
call go-webui.bat --api-only
''')

        # 启动
        subprocess.Popen(
            ["cmd", "/c", "start", "GPT-SoVITS API", str(startup_script)],
            cwd=str(gpt_sovits_path),
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        # Linux/Mac
        subprocess.Popen(
            [sys.executable, "api_v2.py"],
            cwd=str(gpt_sovits_path),
            env=env
        )

    # 等待服务启动
    print("等待服务启动...", end="", flush=True)
    for i in range(30):
        time.sleep(2)
        print(".", end="", flush=True)
        if check_api_running():
            print("\n✓ GPT-SoVITS API 服务已启动!")
            print(f"  API地址: http://127.0.0.1:9880")
            print(f"  文档地址: http://127.0.0.1:9880/docs")
            return True

    print("\n✗ 服务启动超时，请手动启动")
    return False


def main():
    print("=" * 60)
    print("GPT-SoVITS 启动工具")
    print("=" * 60)

    # 检查是否已运行
    if check_api_running():
        print("✓ GPT-SoVITS API 服务已在运行!")
        print(f"  地址: http://127.0.0.1:9880")
        return

    # 查找GPT-SoVITS
    print("\n正在查找GPT-SoVITS安装目录...")
    gpt_sovits_path = find_gpt_sovits()

    if gpt_sovits_path:
        print(f"✓ 找到GPT-SoVITS: {gpt_sovits_path}")
        start_api_server(gpt_sovits_path)
    else:
        print("✗ 未找到GPT-SoVITS")
        print("\n请选择以下方式之一:")
        print("  1. 将GPT-SoVITS文件夹放到桌面")
        print("  2. 将GPT-SoVITS文件夹重命名为'GPT-SoVITS'并放到以下位置:")
        print("     - 桌面")
        print("     - 下载文件夹")
        print("  3. 手动启动GPT-SoVITS后运行 api_v2.py")
        print("\n手动启动命令:")
        print("  cd [GPT-SoVITS目录]")
        print("  python api_v2.py")


if __name__ == "__main__":
    main()
