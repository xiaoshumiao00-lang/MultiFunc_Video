# Qwen3 本地部署指南

## 概述

通过 Ollama 在本地运行 Qwen3 大模型，将 AI 分镜生成功能集成到视频生成项目中。

---

## 一、硬件配置参考

| 模型 | 参数量 | 内存需求(FP16) | 量化后(Q4) | 推荐场景 |
|------|--------|---------------|-----------|---------|
| Qwen3-0.6B | 6亿 | ~1.2GB | ~0.5GB | 测试/CPU运行 |
| Qwen3-1.7B | 17亿 | ~3.4GB | ~1.4GB | 轻量使用 |
| **Qwen3-4B** | 40亿 | ~8GB | ~2.5GB | **推荐(平衡)** |
| Qwen3-8B | 80亿 | ~16GB | ~5.2GB | 较高质量 |
| Qwen3-14B | 140亿 | ~28GB | ~9GB | 高质量需求 |

**您的配置估算**：
- 16GB RAM + 有N卡：推荐 **Qwen3-4B** 或 **Qwen3-8B**
- 仅CPU：推荐 **Qwen3-1.7B** 或 **Qwen3-4B**

---

## 二、安装 Ollama

### 1. 下载安装

访问 https://ollama.com/download 下载 Windows 版本

或使用命令行：
```powershell
# Windows PowerShell
Invoke-WebRequest -Uri https://ollama.com/install.ps1 -OutFile install.ps1
.\install.ps1
```

### 2. 验证安装

```powershell
ollama --version
```

---

## 三、下载并运行 Qwen3 模型

### 推荐命令

```powershell
# 4B 模型（推荐 - 平衡质量和速度）
ollama run qwen3:4b

# 8B 模型（更高质量，需要更多内存）
ollama run qwen3:8b

# 1.7B 模型（CPU友好，快速响应）
ollama run qwen3:1.7b
```

### Ollama 常用命令

```powershell
# 查看已下载的模型
ollama list

# 拉取模型（不运行）
ollama pull qwen3:4b

# 删除模型
ollama rm qwen3:4b

# 复制模型（创建自定义版本）
ollama cp qwen3:4b my-qwen3:custom
```

---

## 四、配置环境变量

Ollama 默认在 `http://localhost:11434` 运行 API。

设置环境变量（可选，推荐）：
```powershell
# 永久设置（管理员权限）
[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0", "User")
```

---

## 五、测试 API 调用

Ollama 提供与 OpenAI 兼容的 API：

```powershell
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3:4b",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

---

## 六、集成到视频生成项目

### 1. 修改 ShotGenerator 类

在 `utils/smart_video.py` 中添加本地 Ollama 支持：

```python
class ShotGenerator:
    """AI分镜生成器 - 支持本地Ollama"""

    def __init__(self, use_local: bool = True):
        self.use_local = use_local
        if use_local:
            # 本地 Ollama 配置
            self.api_url = "http://localhost:11434/v1/chat/completions"
            self.model = "qwen3:4b"  # 可改为 qwen3:8b 或 qwen3:1.7b
        else:
            # 云端 MiniMax 配置
            self.api_url = "https://api.minimax.chat/v1"
            self.api_key = None  # 需要配置

    async def generate_shots(self, content: str) -> List[ShotSegment]:
        """调用AI生成分镜"""
        import httpx

        prompt = self._build_prompt(content)

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                if self.use_local:
                    # 本地 Ollama API
                    response = await client.post(
                        self.api_url,
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "system", "content": "你是一位专业且富有创意的视频分镜描述专家。"},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.7,
                            "stream": False
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        text = result["choices"][0]["message"]["content"]
                        return self._parse_shots(text)
                else:
                    # 云端 API (MiniMax)
                    response = await client.post(
                        f"{self.api_url}/text/chatcompletion_v2",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "MiniMax-Text-01",
                            "messages": [
                                {"role": "system", "content": "你是一位专业且富有创意的视频分镜描述专家。"},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.7
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        text = result["choices"][0]["message"]["content"]
                        return self._parse_shots(text)
        except Exception as e:
            print(f"[ERROR] 分镜生成失败: {e}")
            return self._fallback_shots(content)

        return self._fallback_shots(content)
```

### 2. 在 SmartVideoGenerator 中启用本地模式

```python
class SmartVideoGenerator:
    def __init__(self, theme: str = "大学学业篇",
                 tts_mode: str = TTS_MODE,
                 use_comfyui: bool = True,
                 use_local_llm: bool = True):  # 新增参数
        # ...
        self.use_local_llm = use_local_llm
        self.shot_generator = ShotGenerator(use_local=use_local_llm)
```

### 3. 修改 main.py 添加参数

```python
parser.add_argument("--local-llm", action="store_true",
                   help="使用本地Ollama运行LLM（需先安装Ollama并下载模型）")
```

---

## 七、使用示例

### 命令行使用

```powershell
# 本地 Ollama 模式
python main.py --smart-gen --text "你的文案内容" --theme "大学学业篇" --local-llm

# 云端 MiniMax 模式（默认）
python main.py --smart-gen --text "你的文案内容" --theme "大学学业篇"
```

---

## 八、常见问题

### Q1: Ollama 服务无法启动
```powershell
# 检查服务状态
ollama serve

# 如果端口被占用
netstat -ano | findstr 11434
```

### Q2: 模型下载慢
使用镜像或手动下载 GGUF 文件

### Q3: 内存不足
- 减小模型大小（用 qwen3:1.7b 代替 qwen3:4b）
- 关闭其他占用内存的程序
- 增加系统虚拟内存

### Q4: 生成速度慢
- 使用量化模型（Q4_K_M）
- 确保有足够显存
- 减小上下文长度

---

## 九、性能对比

| 模型 | 生成速度(字/秒) | 内存占用 | 分镜质量 |
|------|---------------|---------|---------|
| Qwen3-1.7B | ~30 | 2GB | 基础可用 |
| Qwen3-4B | ~20 | 6GB | 良好 |
| Qwen3-8B | ~12 | 10GB | 优秀 |

---

## 十、下一步优化

1. **流式输出**：实时显示生成进度
2. **批量生成**：一次生成多个视频
3. **提示词优化**：根据反馈调整系统提示词
4. **缓存机制**：避免重复生成分镜