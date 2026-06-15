"""
配置文件 - 抖音短视频批量生成工具
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()

# 输出目录
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
IMAGES_DIR = OUTPUTS_DIR / "images"
AUDIO_DIR = OUTPUTS_DIR / "audio"
VIDEOS_DIR = OUTPUTS_DIR / "videos"

# 创建输出目录
for d in [OUTPUTS_DIR, IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============ 可配置参数 ============

# 视频设置
VIDEO_SETTINGS = {
    "width": 1920,           # 宽度（16:9横屏）
    "height": 1080,          # 高度
    "fps": 30,               # 帧率
    "bitrate": "10M",        # 视频码率
    "duration_min": 15,      # 最小视频时长（秒）
}

# 水印设置
WATERMARK = {
    "text": "大学学业篇",    # 右上角显示的文字
    "position": "top_right", # 位置
    "font_size": 36,
    "color": (255, 255, 255),  # 白色
    "outline_color": (0, 0, 0),  # 黑色描边
    "margin_x": 30,
    "margin_y": 30,
}

# 字幕设置
SUBTITLE_SETTINGS = {
    "font_size": 42,
    "color": (255, 255, 255),
    "outline_color": (0, 0, 0),
    "outline_width": 3,
    "position": "bottom",   # 底部居中
    "margin_bottom": 150,
}

# 语音设置 - TTS模式选择
TTS_MODE = "qwen_tts"  # 可选: "edge" (Edge-TTS免费版), "gpt_sovits" (GPT-SoVITS), "qwen_tts" (Qwen3-TTS)

# Edge-TTS 语音设置
EDGE_TTS_SETTINGS = {
    "voice": "zh-CN-XiaoxiaoNeural",  # 默认音色
    "rate": "+0%",    # 语速调整
    "volume": "+100%",  # 音量调整（增大100%）
    "pitch": "+0Hz",  # 音调调整
}

# GPT-SoVITS 设置
GPT_SOVITS_SETTINGS = {
    "api_url": "http://127.0.0.1:9880",  # GPT-SoVITS API地址
    "root_path": "D:/陈潘HBEU/Desktop/本地生成视频/GPT-SoVITS-1007-cu124/GPT-SoVITS-1007-cu124",  # GPT-SoVITS根目录（外部依赖，需自行安装）
    "ref_audio_path": str(PROJECT_ROOT / "voices/第三.mp3"),  # 克隆声音参考音频
    "prompt_text": "第三，给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。",  # 参考音频文本
    "ref_lang": "zh",   # 参考音频语言: zh(中文)/en(英文)/auto
    "text_lang": "zh",   # 合成文本语言: zh(中文)/en(英文)/auto
    "speed": 1.05,        # 语速: 0.5-2.0
    # 混响效果设置（降低AI味）
    "reverb": {
        "enabled": True,        # 是否启用混响
        "size": 0.8,            # 空间大小 0.5-1.0
        "damping": 0.7,         # 高频衰减 0.5-1.0
        "wet": 0.25,            # 混响比例 0.2-0.35（太高考会发闷）
        "width": 1.0,           # 立体声宽度
    },
}

# Qwen3-TTS 设置
QWEN_TTS_SETTINGS = {
    "model_path": str(PROJECT_ROOT.parent / "Qwen3_TTS/Qwen3-TTS-12Hz-1___7B-Base"),  # Base 版本（已迁入项目）
    "ref_audio_path": str(PROJECT_ROOT / "voices/第三.mp3"),  # 语音克隆参考音频
    "prompt_text": "第三，给分的人比学分重要，和老师处好关系，期末那一下，比你复习一周都管用。",  # 参考音频文本
    "speaker": None,  # 预定义音色（None=自动选择第一个，或指定如 "Annie"）
    "language": "Auto",  # 语言: Auto/zh/en
    "speed": 1.0,  # 语速: 0.5-2.0
    "device": "cuda",  # 设备: cuda/cpu
}

# 预置音色列表（用户可自定义添加）
PRESET_VOICES = {
    "默认女声": {
        "ref_audio": str(PROJECT_ROOT / "voices/nv_default.wav"),
        "prompt_text": "今天天气真好，我们一起去公园散步吧"
    },
    "温柔女声": {
        "ref_audio": str(PROJECT_ROOT / "voices/nv_wenrou.wav"),
        "prompt_text": "欢迎来到我的频道，这里有更多精彩内容"
    },
    "阳光男声": {
        "ref_audio": str(PROJECT_ROOT / "voices/nan_yangguang.wav"),
        "prompt_text": "大家好，我是你们的好朋友小明"
    },
    "知性女声": {
        "ref_audio": str(PROJECT_ROOT / "voices/nv_zhixing.wav"),
        "prompt_text": "欢迎收听今天的节目，我们将为大家带来"
    },
    "活力少年": {
        "ref_audio": str(PROJECT_ROOT / "voices/shao_huoli.wav"),
        "prompt_text": "加油，我们一定可以做到的，冲冲冲"
    },
}

# 兼容性别名（用于代码中统一调用）
AVAILABLE_VOICES = {
    "zh-CN-XiaoxiaoNeural": "晓晓 - 女声(Edge-TTS默认)",
    "zh-CN-YunxiNeural": "云希 - 男声(年轻)",
    "zh-CN-YunyangNeural": "云扬 - 男声(资讯)",
    "zh-CN-XiaoyiNeural": "小艺 - 女声(情感)",
}

# Stable Diffusion 设置 (如需本地部署)
SD_SETTINGS = {
    "host": "http://127.0.0.1:7860",
    "sd_model": "animefull-final-pruned",  # 可更换模型
    "steps": 30,
    "cfg_scale": 7.5,
    "negative_prompt": "low quality, blurry, bad anatomy, watermark, text",
}

# ============ 默认模型设置 ============
DEFAULT_IMAGE_MODEL = "zimage"  # 可选: "flux" (FLUX.1 Dev), "zimage" (阿里Z-Image-Turbo)

# ComfyUI FLUX 设置 (秋叶整合包)
COMFYUI_SETTINGS = {
    "api_url": "http://127.0.0.1:8188",
    "workflow": "flux",  # 使用FLUX工作流
    "model": "flux1_dev_fp8.safetensors",
    "vae": "ae.safetensors",
    "clip1": "t5xxl_fp8_e4m3fn.safetensors",
    "clip2": "clip_l.safetensors",
    "clip_type": "flux",
    "steps": 25,
    "guidance": 3.5,
    "model_type": "flux"
}

# ComfyUI Z-Image-Turbo 设置 (阿里通义)
ZIMAGE_SETTINGS = {
    "api_url": "http://127.0.0.1:8188",
    "model": "z_image_turbo_bf16.safetensors",  # 主扩散模型
    "vae": "ae.safetensors",
    "text_encoder": "qwen_3_4b.safetensors",      # 文本编码器
    "steps": 8,                                  # Z-Image-Turbo 只需8步
    "guidance": 1.0,
    "model_type": "zimage"
}

# 根据 DEFAULT_IMAGE_MODEL 自动选择的当前图片模型配置
if DEFAULT_IMAGE_MODEL == "zimage":
    IMAGE_SETTINGS = ZIMAGE_SETTINGS.copy()
else:
    IMAGE_SETTINGS = COMFYUI_SETTINGS.copy()

# 视频主题预设 - 六种指定类别
VIDEO_THEMES = {
    "大学生活篇": {
        "watermark": "大学生活篇",
        "style": "校园生活",
    },
    "大学学业篇": {
        "watermark": "大学学业篇",
        "style": "学术学习",
    },
    "大学规划篇": {
        "watermark": "大学规划篇",
        "style": "学业规划",
    },
    "大学就业篇": {
        "watermark": "大学就业篇",
        "style": "职业就业",
    },
    "大学认知篇": {
        "watermark": "大学认知篇",
        "style": "认知成长",
    },
    "大学心理篇": {
        "watermark": "大学心理篇",
        "style": "心理健康",
    },
}
