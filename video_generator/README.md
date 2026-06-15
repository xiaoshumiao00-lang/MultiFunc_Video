# 抖音短视频批量生成工具

本地部署的AI视频生成工具，完全免费，支持批量生成。

## 功能特性

- **文本转语音（TTS）**: 使用微软Edge-TTS，本地免费，支持多种中文音色
- **图片生成**: 支持Stable Diffusion WebUI本地文生图（可选）
- **视频合成**: FFmpeg强大合成能力，支持字幕、时间轴同步
- **批量生成**: CSV批量导入，一键生成多个视频
- **可配置**: 水印文字、音色、语速等参数可调整

## 系统要求

- Windows 10/11 或 macOS 10.14+
- Python 3.10 或更高版本
- FFmpeg（用于视频合成）
- 可选：Stable Diffusion WebUI（用于图片生成）

## 安装步骤

### 1. 安装Python依赖

```bash
cd video-generator
pip install -r requirements.txt
```

### 2. 安装FFmpeg

**Windows:**
```bash
# 使用winget
winget install ffmpeg

# 或下载预编译包并添加到PATH
# https://ffmpeg.org/download.html
```

**macOS:**
```bash
brew install ffmpeg
```

### 3. （可选）安装Stable Diffusion WebUI

如果你需要AI文生图功能：

1. 下载 [AUTOMATIC1111 WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
2. 启动时加上API参数：
```bash
python launch.py --api --listen
```

## 使用方法

### 方法一：命令行单条生成

```bash
# 基本用法
python main.py --text "你的文案内容"

# 指定主题和音色
python main.py --text "文案内容" --theme 大学学业篇 --voice zh-CN-YunxiNeural

# 指定输出文件名
python main.py --text "文案内容" --output my_video
```

### 方法二：命令行批量生成

1. 准备CSV文件（参考sample_tasks.csv格式）:

```csv
id,text,image_prompt,output_name
001,大学生活中学习是最重要的事情之一,university student studying,video_001
002,掌握高效的学习方法让你的成绩突飞猛进,books on desk studying,video_002
```

2. 执行批量生成:

```bash
python main.py --batch tasks.csv --theme 大学学业篇
```

### 方法三：图形界面

```bash
python main.py --gui
```

然后在浏览器打开 http://localhost:7860

## 配置说明

### 可用音色

| ShortName | 说明 |
|-----------|------|
| zh-CN-XiaoxiaoNeural | 晓晓 - 女声(默认) |
| zh-CN-YunxiNeural | 云希 - 男声(年轻) |
| zh-CN-YunyangNeural | 云扬 - 男声(资讯) |
| zh-CN-XiaoyiNeural | 小艺 - 女声(情感) |
| zh-CN-liaoning-XiaobeiNeural | 小北 - 女声(东北) |
| zh-CN-shaanxi-XiaoniNeural | 小妮 - 女声(陕西) |

### 可用主题

- 大学学业篇
- 考研攻略篇
- 就业指导篇
- 校园生活篇

### 修改config.py调整默认设置

```python
# 视频尺寸（抖音竖屏9:16）
VIDEO_SETTINGS = {
    "width": 1080,
    "height": 1920,
    "fps": 30,
}

# 水印设置
WATERMARK = {
    "text": "大学学业篇",  # 右上角文字
    "font_size": 36,
}
```

## 目录结构

```
video-generator/
├── main.py              # 主程序
├── config.py            # 配置文件
├── requirements.txt     # 依赖
├── utils/               # 工具模块
│   ├── tts.py          # 语音合成
│   ├── video.py        # 视频合成
│   ├── subtitle.py     # 字幕处理
│   └── sd_api.py       # SD API封装
├── scripts/             # 脚本
│   ├── generate_audio.py
│   ├── generate_video.py
│   └── batch_process.py
└── outputs/             # 输出目录
    ├── images/
    ├── audio/
    └── videos/
```

## 常见问题

### Q: 提示"ffmpeg未找到"
A: 确保FFmpeg已安装并添加到系统PATH。重启终端后重试。

### Q: 语音生成失败
A: 检查网络连接，Edge-TTS需要访问微软服务器下载音色文件。

### Q: 视频合成报错
A: 确保音频和图片文件完整，且路径不包含中文字符或特殊符号。

### Q: 如何更换语音音色？
A: 使用 `--voice` 参数指定，或在 config.py 中修改 `TTS_SETTINGS["voice"]`。

## 技术支持

如遇到问题，请检查：
1. Python版本（需3.10+）
2. FFmpeg是否正确安装（运行 `ffmpeg -version`）
3. 依赖包是否完整安装
