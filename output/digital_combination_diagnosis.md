# digital_combination.json 本地运行诊断报告

## 工作流信息

| 项目 | 值 |
|------|-----|
| 工作流文件 | `D:/陈潘HBEU/Desktop/Pixelle-Video-v0.1.15-win64/Pixelle-Video/workflows/selfhost/digital_combination.json` |
| JSON 版本 | 0.4 |
| 节点数 | 28 |
| 连接数 | 33 |
| 前端版本 | 1.23.0 |
| 目标 ComfyUI | `http://127.0.0.1:8188`（本地运行实例：D:/FLUX Redux） |
| ComfyUI 版本 | 0.18.1 |

## 执行状态

| 步骤 | 状态 | 备注 |
|------|------|------|
| 诊断工作流依赖 | 已完成 | 识别出 2 个缺失节点包、6 个缺失模型 |
| 安装 `ComfyUI-WanVideoWrapper` | 已完成 | 已克隆并安装依赖（opencv-python 已存在，跳过重装） |
| 安装 `audio-separation-nodes-comfyui` | 已完成 | 已克隆并安装依赖 |
| 重启 ComfyUI | 待用户操作 | 新节点需要重启后才能加载 |
| 下载缺失模型 | 待用户操作 | 模型文件较大，需手动下载 |
| 加载并运行工作流 | 未完成 | 需完成上述两步后 |

## 自定义节点包状态

| 包名 | 工作流中节点数 | 本地状态 | 仓库地址 |
|------|---------------|----------|----------|
| ComfyUI-WanVideoWrapper | 14 | 已克隆/待重启 | https://github.com/kijai/ComfyUI-WanVideoWrapper |
| audio-separation-nodes-comfyui | 2 | 已克隆/待重启 | https://github.com/christian-byrne/audio-separation-nodes-comfyui |
| comfyui-videohelpersuite | 1 | 已安装 | https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite |
| comfyui-kjnodes | 1 | 已安装 | https://github.com/kijai/ComfyUI-KJNodes |
| comfy-core | 2 | 已内置 | - |

## 引用模型状态

| 工作流中引用路径 | 类型 | 本地状态 | 建议放置目录 |
|-----------------|------|----------|--------------|
| `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` | 扩散模型 | **缺失** | `models/diffusion_models/` |
| `Wan2_1_VAE_bf16.safetensors` | VAE | **缺失** | `models/vae/` |
| `umt5-xxl-enc-bf16.safetensors` | 文本编码器 | **缺失** | `models/text_encoders/` |
| `clip_vision_vit_h.safetensors` | CLIP Vision | **缺失** | `models/clip_vision/` |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors` | LoRA / 蒸馏模型 | **缺失** | `models/loras/` 或 `models/diffusion_models/` |
| `InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors` | 语音驱动模型 | **缺失** | `models/checkpoints/` 或 `models/diffusion_models/` |
| `TencentGameMate/chinese-wav2vec2-base` | 音频编码器（Transformers） | **缺失** | `models/LLM/` 或 Transformers 缓存目录 |
| `video/h264-mp4` | 视频格式 | 已内置 | - |

### 本地已有的可替代模型（供参考）

> 这些模型内容可能与工作流期望的接近，但文件名不同。ComfyUI 下拉框通常要求精确匹配文件名，因此建议按工作流要求下载或复制一份别名。

| 已有模型 | 可能替代 | 说明 |
|---------|---------|------|
| `models/diffusion_models/wan2.1_i2v_480p_14B_fp8_e4m3fn.safetensors` | `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` | 同为 Wan2.1 I2V 14B 480p fp8，但 scaling 版本可能不同 |
| `models/vae/wan_2.1_vae.safetensors` | `Wan2_1_VAE_bf16.safetensors` | 同名 VAE 不同精度/文件名 |
| `models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `umt5-xxl-enc-bf16.safetensors` | 精度不同 |
| `models/clip_vision/clip_vision_h.safetensors` | `clip_vision_vit_h.safetensors` | 通常可互换 |

## 修复步骤

### 1. 安装缺失的自定义节点（已完成）

以下节点已自动克隆到 `D:/FLUX Redux/custom_nodes` 并安装依赖：

- `ComfyUI-WanVideoWrapper`
- `audio-separation-nodes-comfyui`

> 说明：由于 ComfyUI 正在运行，`opencv-python` 文件被占用，因此跳过了该包的重装（环境中已存在 OpenCV 4.11.0，满足要求）。

**你需要手动重启 ComfyUI**，新节点才会出现在 `object_info` 中。

### 2. 下载缺失模型

以下是 huggingface-cli 下载命令示例。如果没有 `huggingface-cli`，可用浏览器下载后放到对应目录。

```powershell
# 当前环境 huggingface-cli 不在 PATH 中，可用 Python 模块方式调用：
$py = "D:/FLUX Redux/python/python.exe"

# Wan2.1 I2V 14B 480p fp8 scaled (Kijai 版)
& $py -m huggingface_hub.cli download Kijai/WanVideo_models Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors --local-dir "D:/FLUX Redux/models/diffusion_models"

# Wan2.1 VAE bf16
& $py -m huggingface_hub.cli download Kijai/WanVideo_models Wan2_1_VAE_bf16.safetensors --local-dir "D:/FLUX Redux/models/vae"

# umt5-xxl 文本编码器 bf16
& $py -m huggingface_hub.cli download Kijai/WanVideo_models umt5-xxl-enc-bf16.safetensors --local-dir "D:/FLUX Redux/models/text_encoders"

# CLIP Vision ViT-H
& $py -m huggingface_hub.cli download openai/clip-vit-large-patch14 model.safetensors --local-dir "D:/FLUX Redux/models/clip_vision" --local-dir-use-symlinks False
# 下载后重命名为 clip_vision_vit_h.safetensors

# lightx2v I2V 蒸馏 LoRA
& $py -m huggingface_hub.cli download lightx2v/Wan2.1-I2V-14B-480P-CFG-Step-Distill-Rank128-BF16 lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors --local-dir "D:/FLUX Redux/models/loras"

# InfiniteTalk Wan2.1 语音驱动模型（MultiTalkModelLoader 从 diffusion_models 加载）
& $py -m huggingface_hub.cli download InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16 Wan2_1-InfiniTetalk-Single_fp16.safetensors --local-dir "D:/FLUX Redux/models/diffusion_models"

# chinese-wav2vec2-base 音频编码器（DownloadAndLoadWav2VecModel 从 models/transformers 加载）
& $py -m huggingface_hub.cli download TencentGameMate/chinese-wav2vec2-base --local-dir "D:/FLUX Redux/models/transformers/TencentGameMate/chinese-wav2vec2-base" --local-dir-use-symlinks False
```

> 注意：
> - 上述模型文件较大（总计约 30-50 GB），请确保磁盘空间充足并有稳定网络。
> - 下载命令中的仓库 ID 和文件名仅供参考，exact 链接请以上游仓库 README 为准。
> - 如果 `huggingface_hub` 未安装，可先执行 `"D:/FLUX Redux/python/python.exe" -m pip install huggingface_hub`。
> - 国内用户如遇 HuggingFace 访问问题，可改用镜像站或浏览器手动下载。

### 3. 验证

运行附件中的 `verify_workflow.ps1` 脚本，检查节点和模型是否就位。

## 已知问题与解决方案

1. **节点显示红色 / 缺失**
   - 确保 `ComfyUI-WanVideoWrapper` 和 `audio-separation-nodes-comfyui` 已克隆并安装依赖，然后重启 ComfyUI。

2. **模型下拉框为空**
   - ComfyUI 启动时扫描模型目录。新增模型后需重启 ComfyUI 才能在下拉框中看到。

3. **文件名不匹配**
   - Windows 文件名大小写不敏感，但 ComfyUI 下拉框保存的是工作流中的字符串。建议保持文件名一致，或用复制/硬链接创建别名。

4. **显存不足**
   - Wan2.1 I2V 14B fp8 在 480p 下建议至少 16-24 GB 显存。可在 `WanVideoDecode` 节点开启 `enable_vae_tiling` 并减小 tile 尺寸。

5. **ComfyUI 版本差异**
   - 当前 ComfyUI 版本为 0.18.1，工作流前端版本为 1.23.0。若加载工作流出现前端兼容性提示，通常不影响执行。

## 资源估算

| 资源 | 估算 |
|------|------|
| 磁盘空间（仅节点 + 依赖） | < 1 GB |
| 磁盘空间（全部模型） | 约 30-50 GB |
| 显存（14B 480p I2V） | 建议 16-24 GB |
| 内存 | 建议 32 GB+ |

## 新增问题与修复（运行阶段）

### Pixelle-Video 本地调用 Bug

症状：`Workflow file does not exist: {'id': 'a7a252ea...'}`

根因：Pixelle-Video 代码把本地工作流 JSON 内容字符串传给 ComfyKit，而 ComfyKit 要求传入文件路径。

已修复文件：
- `Pixelle-Video/web/pipelines/digital_human.py`
- `Pixelle-Video/pixelle_video/services/teaching_composer.py`

### 工作流格式错误

症状：`Submit workflow failed: [500] Server got itself in trouble`

根因：`digital_combination.json` 是 ComfyUI UI 格式（含 `nodes`/`links`），Pixelle-Video/ComfyKit 需要 API 格式（`node_id -> {inputs, class_type, _meta}`）。

已处理：
- 使用 `output/convert_ui_to_api.py` 将 UI 格式转换为 API 格式。
- 原文件备份为 `workflows/selfhost/digital_combination_ui.json`。
- API 格式文件已替换为 `workflows/selfhost/digital_combination.json`。
- 两个 16GB 优化版本也已转换为 API 格式，位于 `output/` 目录（`.api.json` 后缀）。

### 缺失 `RH_GetAudioDuration` 节点

症状：`Node 'RH_GetAudioDuration' not found`

已安装：`D:/FLUX Redux/custom_nodes/ComfyUI-GetAudioDuration`

## 当前状态

| 检查项 | 状态 |
|--------|------|
| `ComfyUI-WanVideoWrapper` | ✅ 已安装 |
| `audio-separation-nodes-comfyui` | ✅ 已安装 |
| `ComfyUI-VideoHelperSuite` | ✅ 已安装 |
| `ComfyUI-KJNodes` | ✅ 已安装 |
| `ComfyUI-GetAudioDuration` | ✅ 已安装 |
| `ComfyUI-Basic-Math` | ✅ 已安装 / 待重启加载 |
| 6 个模型文件 | ✅ 已就位 |
| 工作流 API 格式 | ✅ 已转换 |
| Pixelle-Video 路径 Bug | ✅ 已修复 |

## 下一步

1. **重启 ComfyUI**，加载 `RH_GetAudioDuration` 节点。
2. **重启 Pixelle-Video**（确保代码修复生效）。
3. 重新运行数字人工作流。
4. 若 16GB 显存不足，将 `output/digital_combination_optimized_16gb.api.json` 复制到 `workflows/selfhost/digital_combination.json` 后重试。

