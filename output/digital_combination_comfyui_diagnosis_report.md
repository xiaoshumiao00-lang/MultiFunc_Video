# digital_combination.json 工作流本地 ComfyUI 诊断报告

> 检测时间：2026-06-13  
> ComfyUI 路径：`D:\FLUX Redux`  
> ComfyUI 版本：`0.18.1`  
> 工作流路径：`D:\陈潘HBEU\Desktop\Pixelle-Video-v0.1.15-win64\Pixelle-Video\workflows\selfhost\digital_combination.json`

---

## 1. 诊断结论（TL;DR）

工作流 **JSON 格式本身无问题**，但在当前本地 ComfyUI 环境中 **无法直接加载/执行**。主要原因为：

| 类别 | 状态 | 关键问题 |
|------|------|----------|
| JSON 结构 | 通过 | 28 个节点、33 条连接，格式合法 |
| 自定义节点 | 缺失 | **ComfyUI-WanVideoWrapper**、**audio-separation-nodes-comfyui**、**ComfyUI-GetAudioDuration** 未安装 |
| 模型文件 | 缺失/不匹配 | InfiniteTalk、Wav2Vec、部分 WAN 模型名称不匹配 |
| 前端版本 | 基本兼容 | 工作流要求 frontend 1.23.0，ComfyUI 0.18.1 支持 |

---

## 2. JSON 文件格式检查

```
工作流版本：0.4
节点数量：28
连接数量：33
前端版本：1.23.0
JSON 语法：通过
```

工作流由以下节点类型组成（按出现频次）：

- **WanVideo 系列节点**（14 个）：全部来自 `ComfyUI-WanVideoWrapper`
- **AudioSeparation / AudioCrop**（2 个）：来自 `audio-separation-nodes-comfyui`
- **CLIPVisionLoader / LoadImage**（2 个）：ComfyUI 核心节点
- **VHS_VideoCombine**（1 个）：来自 `comfyui-videohelpersuite`
- **ImageResizeKJv2**（1 个）：来自 `comfyui-kjnodes`
- **LayerUtility: ImageScaleByAspectRatio V2**（1 个）：来自 `ComfyUI_LayerStyle`
- **easy int / easy showAnything / ToInt / Int / SimpleMath+**（5 个）：来自 `ComfyUI-Easy-Use` 或 `ComfyLiterals`
- **RH_GetAudioDuration**（1 个）：来自 `ComfyUI-GetAudioDuration`

---

## 3. 自定义节点安装状态

### 3.1 已安装节点（满足要求）

| 节点包 | 本地目录 | 工作流要求版本 | 本地实际版本 | 状态 |
|--------|----------|----------------|--------------|------|
| ComfyUI-VideoHelperSuite | `custom_nodes/ComfyUI-VideoHelperSuite` | `0a75c79...` | `a7ce59e...`（2025-04-26） | 兼容 |
| ComfyUI-Easy-Use | `custom_nodes/ComfyUI-Easy-Use` | - | `b6bb4a3...`（2025-07-17） | 已安装 |
| ComfyUI-KJNodes | `custom_nodes/ComfyUI-KJNodes` | `f7eb33a...` | `37a0973...`（2025-07-21） | 兼容 |
| ComfyUI_LayerStyle | `custom_nodes/ComfyUI_LayerStyle` | - | `3bfe8e4...`（2025-06-20） | 已安装 |

### 3.2 缺失节点（必须安装）

| 节点包 | 仓库地址 | 工作流中使用的节点 | 重要性 |
|--------|----------|-------------------|--------|
| **ComfyUI-WanVideoWrapper** | `https://github.com/kijai/ComfyUI-WanVideoWrapper` | WanVideoDecode、WanVideoSampler、WanVideoModelLoader、WanVideoVAELoader、WanVideoTextEncode、WanVideoImageToVideoMultiTalk、MultiTalkModelLoader、MultiTalkWav2VecEmbeds 等 | **关键** |
| **audio-separation-nodes-comfyui** | `https://github.com/christian-byrne/audio-separation-nodes-comfyui` | AudioSeparation、AudioCrop | 必须 |
| **ComfyUI-GetAudioDuration** | `https://github.com/yiwankb/ComfyUI-GetAudioDuration` | RH_GetAudioDuration | 必须 |

---

## 4. 模型文件检查

### 4.1 工作流引用的模型

| 工作流中引用的模型/路径 | 期望存放目录 | 本地状态 | 说明 |
|------------------------|--------------|----------|------|
| `Wan2_1_VAE_bf16.safetensors` | `models/vae/` | 缺失 | 工作流写死该文件名 |
| `umt5-xxl-enc-bf16.safetensors` | `models/text_encoders/` | 缺失 | 工作流写死该文件名 |
| `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` | `models/diffusion_models/` | 缺失 | Kijai fp8 scaled 版 |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors` | `models/loras/` | 缺失 | Lightx2V LoRA |
| `InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors` | `models/diffusion_models/` 或节点自定义路径 | 缺失 | InfiniteTalk 多说话人模型 |
| `clip_vision_vit_h.safetensors` | `models/clip_vision/` | 名称不匹配 | 本地有 `clip_vision_h.safetensors` |
| `TencentGameMate/chinese-wav2vec2-base` | `models/audio_encoders/` | 缺失 | 运行时自动下载或手动放置 |

### 4.2 本地已存在但名称不匹配的模型

| 本地文件 | 工作流期望文件名 | 建议操作 |
|----------|------------------|----------|
| `models/vae/wan_2.1_vae.safetensors` | `Wan2_1_VAE_bf16.safetensors` | **重命名**或复制一份为工作流期望名称 |
| `models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `umt5-xxl-enc-bf16.safetensors` | **重命名**或复制一份为工作流期望名称 |
| `models/diffusion_models/wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors` | `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` | 注意：这是普通 fp8，工作流要求 `scaled_KJ` 版，建议重新下载 |
| `models/clip_vision/clip_vision_h.safetensors` | `clip_vision_vit_h.safetensors` | 可尝试重命名，若加载失败再下载官方版本 |

---

## 5. 逐步修复方案

### 步骤 1：关闭 ComfyUI

确保 ComfyUI 完全关闭后再安装节点，避免文件占用。

### 步骤 2：安装缺失的自定义节点

打开 PowerShell 或 Git Bash，进入 ComfyUI 自定义节点目录：

```powershell
cd "D:\FLUX Redux\custom_nodes"
```

执行以下克隆命令：

```powershell
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git
git clone https://github.com/christian-byrne/audio-separation-nodes-comfyui.git
git clone https://github.com/yiwankb/ComfyUI-GetAudioDuration.git
```

安装依赖：

```powershell
cd "D:\FLUX Redux\custom_nodes\ComfyUI-WanVideoWrapper"
..\..\python\python.exe -m pip install -r requirements.txt

cd "D:\FLUX Redux\custom_nodes\audio-separation-nodes-comfyui"
..\..\python\python.exe -m pip install -r requirements.txt

cd "D:\FLUX Redux\custom_nodes\ComfyUI-GetAudioDuration"
..\..\python\python.exe -m pip install -r requirements.txt
```

> 如果 `pip install` 失败，可尝试使用 ComfyUI-Manager 的 "Install via Git URL" 功能自动安装依赖。

### 步骤 3：下载缺失模型

推荐源：HuggingFace `Kijai/WanVideo_comfy` 或 ModelScope 镜像。

#### 3.1 Kijai WAN 模型（HuggingFace）

```powershell
# 进入模型目录
cd "D:\FLUX Redux\models"

# 下载 VAE
huggingface-cli download Kijai/WanVideo_comfy Wan2_1_VAE_bf16.safetensors --local-dir vae

# 下载 Text Encoder
huggingface-cli download Kijai/WanVideo_comfy umt5-xxl-enc-bf16.safetensors --local-dir text_encoders

# 下载主模型
huggingface-cli download Kijai/WanVideo_comfy Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors --local-dir diffusion_models

# 下载 InfiniteTalk 模型
huggingface-cli download Kijai/WanVideo_comfy InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors --local-dir diffusion_models
```

#### 3.2 LoRA

`lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors` 可从 HuggingFace `Lightx2V` 或相关仓库获取，放置到：

```
D:\FLUX Redux\models\loras\
```

#### 3.3 CLIP Vision

若重命名 `clip_vision_h.safetensors` → `clip_vision_vit_h.safetensors` 后无法工作，从以下地址下载：

```powershell
huggingface-cli download openai/clip-vit-large-patch14 clip_vision_vit_h.safetensors --local-dir clip_vision
```

或 ComfyUI 官方推荐源：`https://huggingface.co/comfyanonymous/clip_vision_vit_h`

#### 3.4 Wav2Vec 模型

`TencentGameMate/chinese-wav2vec2-base` 会在首次运行时由 `ComfyUI-WanVideoWrapper` 自动下载到 Transformers 缓存目录。如需手动准备：

```powershell
huggingface-cli download TencentGameMate/chinese-wav2vec2-base --local-dir "D:\FLUX Redux\models\audio_encoders\chinese-wav2vec2-base"
```

### 步骤 4：处理名称不匹配问题

为已存在模型创建别名（推荐复制而非移动，避免影响其他工作流）：

```powershell
copy "D:\FLUX Redux\models\vae\wan_2.1_vae.safetensors" "D:\FLUX Redux\models\vae\Wan2_1_VAE_bf16.safetensors"
copy "D:\FLUX Redux\models\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors" "D:\FLUX Redux\models\text_encoders\umt5-xxl-enc-bf16.safetensors"
copy "D:\FLUX Redux\models\clip_vision\clip_vision_h.safetensors" "D:\FLUX Redux\models\clip_vision\clip_vision_vit_h.safetensors"
```

> 注意：`wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors` 与 `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` 是不同的量化版本，**不建议直接重命名**，应重新下载 Kijai scaled 版本。

### 步骤 5：重启 ComfyUI 并验证

1. 启动 ComfyUI
2. 将工作流文件拖入 ComfyUI 界面
3. 观察右下角是否出现红色缺失节点提示
4. 若无红色提示，说明所有节点已加载成功
5. 在 Manager → "Install Models" 中搜索缺失模型（若使用 Manager）

---

## 6. 常见错误与排查

### 错误 1：`When loading the graph, the following node types were not found`

**原因**：自定义节点未安装或加载失败。  
**解决**：按步骤 2 安装缺失节点，重启 ComfyUI。

### 错误 2：`Error no file named pytorch_model.bin, model.safetensors, tf_model.h5, model.ckpt.index or flax_model.msgpack`

**原因**：Wav2Vec 模型未下载。  
**解决**：首次运行时会自动下载，确保网络通畅；或手动放置到 `models/audio_encoders/`。

### 错误 3：`Expected Wan2_1_VAE_bf16.safetensors but got ...`

**原因**：模型文件名与工作流中写死的名称不一致。  
**解决**：按步骤 4 复制重命名。

### 错误 4：`RuntimeError: Expected all tensors to be on the same device`

**原因**：WanVideoWrapper 节点中 `load_device` 或 `device` 设置冲突。  
**解决**：尝试将 `LoadWanVideoT5TextEncoder` 的 `load_device` 改为 `offload_device`，或保持与 `WanVideoModelLoader` 一致。

### 错误 5：ComfyUI 启动时节点导入失败

**排查命令**：

```powershell
cd "D:\FLUX Redux"
python\python.exe -s main.py --dont-upcast-attention --cpu 2>&1 | Select-String -Pattern "WanVideo|MultiTalk|AudioSeparation|GetAudioDuration|Error|Traceback" -CaseSensitive:$false
```

查看控制台输出中是否有节点导入报错。

---

## 7. 一键验证脚本

已将验证脚本保存到：

```
D:\陈潘HBEU\Desktop\Pixelle-Video-v0.1.15-win64\output\verify_digital_combination_env.ps1
```

运行方式（PowerShell）：

```powershell
."D:\陈潘HBEU\Desktop\Pixelle-Video-v0.1.15-win64\output\verify_digital_combination_env.ps1"
```

该脚本会检查：
- 必要自定义节点目录是否存在
- 关键模型文件是否存在
- ComfyUI 版本是否满足最低要求

---

## 8. 资源占用预估

| 模型 | 大致大小 | 用途 |
|------|----------|------|
| Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ | ~15 GB | 主视频生成模型 |
| Wan2_1_VAE_bf16 | ~300 MB | 视频 VAE 编解码 |
| umt5-xxl-enc-bf16 | ~10 GB | 文本编码器 |
| Wan2_1-InfiniTetalk-Single_fp16 | ~14 GB | 无限长说话视频 |
| lightx2v LoRA | ~300 MB | 加速采样 |
| chinese-wav2vec2-base | ~300 MB | 音频特征提取 |
| clip_vision_vit_h | ~1.7 GB | 图像编码 |

**总计约 40+ GB 磁盘空间，显存建议 ≥ 16 GB（RTX 5080 16GB 可运行 fp8 版本）。**

---

## 9. 建议操作优先级

1. **立即执行**：安装 `ComfyUI-WanVideoWrapper`、`audio-separation-nodes-comfyui`、`ComfyUI-GetAudioDuration`
2. **高优先级**：下载 `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` 和 `Wan2_1_VAE_bf16.safetensors`
3. **中优先级**：下载 `umt5-xxl-enc-bf16.safetensors` 和 `InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors`
4. **低优先级**：下载 LoRA 和 Wav2Vec，处理 clip_vision 命名

完成以上步骤后，工作流应能正常加载并运行。
