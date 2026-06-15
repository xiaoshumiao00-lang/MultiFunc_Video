# GPT-SoVITS 本地部署指南

本项目支持使用 **GPT-SoVITS** 作为本地TTS引擎，效果比Edge-TTS更好，支持语音克隆。

---

## 一、GPT-SoVITS 简介

GPT-SoVITS 是目前优秀的开源本地TTS项目，具有以下特点：

| 特性 | 说明 |
|------|------|
| 语音克隆 | 只需3-10秒参考音频即可克隆任意音色 |
| 零样本合成 | 支持未见过的文本即时合成 |
| 多语言支持 | 中文、日文、英文等 |
| 完全本地 | 无需联网，完全免费 |
| 高质量输出 | 音质可达专业级别 |

---

## 二、安装步骤

### 1. 下载GPT-SoVITS整合包

**方式一：从ModelScope下载**
```
https://www.modelscope.cn/models/aihobbyist/GPT-SoVITS-Inference/files
```

**方式二：从百度网盘下载**
- 访问 [ai-hobbyist.com](https://www.ai-hobbyist.com/) 获取网盘链接
- 选择适合你显卡的版本（非50系显卡选 cu124 后缀）

**方式三：从GitHub下载**
```
https://github.com/Soundario/GPT-SoVITS-TTS
```

### 2. 安装依赖

整合包已包含大部分依赖，只需确保：

1. **Python 3.10+**
2. **FFmpeg**（已集成在整合包中）
3. **CUDA**（如有NVIDIA显卡）

### 3. 下载模型文件

GPT-SoVITS需要两个模型文件：

| 模型类型 | 文件格式 | 存放目录 |
|---------|---------|---------|
| GPT模型 | `.ckpt` | `GPT_weights_vX/` |
| SoVITS模型 | `.pth` | `SoVITS_weights_vX/` |

**获取模型的方式：**
1. 使用整合包自带的预训练模型
2. 从社区下载别人训练好的模型
3. 自己训练模型（需要数据）

### 4. 配置模型路径

编辑 `GPT_SoVITS/configs/tts_infer.yaml`：

```yaml
t2s_weights_path: "你的GPT模型路径.ckpt"
vits_weights_path: "你的SoVITS模型路径.pth"
version: v4  # 与模型版本一致
```

---

## 三、启动GPT-SoVITS API

### 方式一：使用启动脚本（推荐）

```bash
cd video-generator
python scripts/start_gpt_sovits.py
```

### 方式二：手动启动

```bash
# 1. 进入GPT-SoVITS目录
cd [你的GPT-SoVITS路径]

# 2. Windows用户双击运行
api_v2.bat

# 或命令行运行
python api_v2.py
```

### 方式三：WebUI模式

```bash
# 启动带WebUI的版本
go-webui.bat
# 然后在WebUI中开启API功能
```

### 验证服务状态

服务启动后会显示：
```
INFO:     Uvicorn running on http://127.0.0.1:9880
```

打开浏览器访问：`http://127.0.0.1:9880/docs` 查看API文档

---

## 四、准备参考音频

### 参考音频要求

| 项目 | 要求 |
|------|------|
| 时长 | 3-10秒 |
| 格式 | WAV（推荐）或MP3 |
| 音质 | 清晰、无混响、无背景音乐 |
| 内容 | 单人语音，语速适中 |

### 获取参考音频的方法

1. **使用整合包自带的示例音频**
2. **从B站/抖音下载**喜欢的声音片段
3. **自己录音**：使用Audacity录制并降噪
4. **AI克隆**：用他人声音训练模型（需授权）

### 配置参考音频

将参考音频放到项目目录：

```
video-generator/
└── voices/
    └── my_voice.wav    ← 你的参考音频
```

然后编辑 `config.py`：

```python
GPT_SOVITS_SETTINGS = {
    "api_url": "http://127.0.0.1:9880",
    "ref_audio_path": "voices/my_voice.wav",  # 你的参考音频路径
    "prompt_text": "参考音频对应的文本内容",   # 重要！
    "ref_lang": "ch",
    "text_lang": "ch",
    "speed": 1.0,
}
```

---

## 五、使用GPT-SoVITS生成语音

### 命令行单条生成

```bash
cd video-generator

python -c "
from utils.gpt_sovits import GPTSoVITSTTS
from utils.subtitle import generate_srt_subtitle
from config import GPT_SOVITS_SETTINGS, AUDIO_DIR

tts = GPTSoVITSTTS()
result = tts.generate_with_timestamps(
    text='你好，这是一段测试语音。',
    ref_audio_path=GPT_SOVITS_SETTINGS['ref_audio_path'],
    prompt_text=GPT_SOVITS_SETTINGS['prompt_text'],
    output_path=str(AUDIO_DIR / 'test.wav')
)

# 生成字幕
generate_srt_subtitle(result['words'], str(AUDIO_DIR / 'test.srt'))
print(f'音频: {result[\"audio_path\"]}')
print(f'时长: {result[\"duration\"]:.2f}秒')
"
```

### 修改主程序使用GPT-SoVITS

编辑 `config.py`：

```python
TTS_MODE = "gpt_sovits"  # 改为使用GPT-SoVITS
```

然后正常运行：

```bash
python main.py --text "你的文案内容"
```

---

## 六、API接口详解

### 主接口：合成语音

```
GET /tts
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| text | string | ✓ | 要合成的文本 |
| text_lang | string | ✓ | 文本语言：ch/ja/en |
| ref_audio_path | string | ✓ | 参考音频路径 |
| prompt_text | string | ✓ | 参考音频文本 |
| prompt_lang | string | ✓ | 参考音频语言：ch/ja/en |
| text_split_method | string | | 切割方式：cut5/rough/jieba |
| batch_size | int | | 批量大小 |
| media_type | string | | 输出格式：wav/mp3 |
| streaming_mode | bool | | 是否流式输出 |

**Python调用示例：**

```python
import requests

response = requests.get("http://127.0.0.1:9880/tts", params={
    "text": "你好，这是一段测试语音。",
    "text_lang": "ch",
    "ref_audio_path": "voices/ref.wav",
    "prompt_text": "今天天气真好",
    "prompt_lang": "ch",
    "media_type": "wav"
})

with open("output.wav", "wb") as f:
    f.write(response.content)
```

---

## 七、常见问题

### Q1: 启动api_v2.py报错"缺少模块"

确保在GPT-SoVITS目录下运行，并安装必要依赖：

```bash
pip install -r requirements.txt
```

### Q2: 模型加载失败

检查 `tts_infer.yaml` 中的路径是否正确：

```yaml
t2s_weights_path: "D:\\GPT-SoVITS\\GPT_weights_v4\\model.ckpt"
vits_weights_path: "D:\\GPT-SoVITS\\SoVITS_weights_v4\\model.pth"
```

Windows路径使用双反斜杠 `\\`。

### Q3: 合成的声音不像参考音频

可能原因：
1. 参考音频太短（建议5秒以上）
2. 参考音频有背景音乐
3. 模型与语言不匹配（中文模型合成英文）

### Q4: 如何更换音色？

准备新的参考音频，然后修改 `config.py` 中的 `ref_audio_path` 和 `prompt_text`。

### Q5: 可以克隆任何人的声音吗？

技术上可以，但建议：
- 仅克隆自己或已授权的声音
- 不要用于侵犯他人权益的用途
- 遵守当地法律法规

---

## 八、性能优化

### 加速推理

1. **使用GPU**：确保安装了CUDA和对应版本的PyTorch
2. **减少步数**：在 `tts_infer.yaml` 中调整
3. **批处理**：一次性合成多段文本

### 提升质量

1. 使用高质量参考音频
2. 避免参考音频中有多个说话人
3. 保持参考音频和目标文本语言一致

---

## 九、相关资源

- [GPT-SoVITS官方文档](https://github.com/Soundario/GPT-SoVITS-TTS)
- [ModelScope模型下载](https://www.modelscope.cn/models/aihobbyist/GPT-SoVITS-Inference/files)
- [官方教程视频](https://www.bilibili.com/video/BV1bUwezvE4T/)

---

## 十、完整使用流程

```
1. 下载安装GPT-SoVITS
   ↓
2. 下载模型文件到对应目录
   ↓
3. 配置 config.py（参考音频路径+文本）
   ↓
4. 启动GPT-SoVITS API服务
   python scripts/start_gpt_sovits.py
   ↓
5. 运行主程序
   python main.py --text "你的文案"
   ↓
6. 在 outputs/videos/ 获取最终视频
```

---

如需更多帮助，请查看GPT-SoVITS官方文档或提交Issue。
