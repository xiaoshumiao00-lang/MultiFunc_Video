# digital_combination.json 16GB 显存适配方案

> 检测时间：2026-06-13  
> ComfyUI 路径：`D:\FLUX Redux`  
> 原始工作流：`digital_combination.json`

---

## 重要前提：不存在 Wan2.1 I2V 1.3B 官方模型

你提到的“换小模型”思路是对的，但有一个关键事实需要先明确：

**阿里巴巴官方只发布了以下 Wan2.1 模型：**
- `Wan2.1-T2V-1.3B`（文生视频，1.3B）
- `Wan2.1-T2V-14B`（文生视频，14B）
- `Wan2.1-I2V-14B-480P`（图生视频，14B）
- `Wan2.1-I2V-14B-720P`（图生视频，14B）

**官方没有发布 `Wan2.1-I2V-1.3B`。** 因此当前工作流使用的 `ComfyUI-WanVideoWrapper`（Kijai 版）也没有对应的 1.3B I2V 模型文件。Kijai 的 HuggingFace 仓库里只有 14B I2V 模型。

所以：**不能直接把工作流里的 14B 模型换成 1.3B I2V。** 要么换整个工作流架构（改用 ComfyUI 原生 T2V 1.3B），要么对现有 14B 工作流做显存优化。

---

## 我为你准备的两个方案

基于以上现实，我生成了两个可直接加载的 JSON 工作流：

| 文件 | 方案 | 特点 | 预计 16GB 表现 |
|------|------|------|----------------|
| `digital_combination_optimized_16gb.json` | **14B 优化版** | 保留 MultiTalk 对口型，降低分辨率/帧数，开启 VAE tiling | 较紧张，可能能跑 |
| `digital_combination_lite_no_multitalk.json` | **14B 轻量版** | 去掉 MultiTalk/InfiniteTalk，仅保留图像输入 + 音频叠加 | 明显更稳，推荐先试 |

---

## 方案 A：14B 优化版（保留对口型）

### 改动内容

与原工作流相比，调整了以下参数：

| 节点 | 参数 | 原值 | 修改后 | 目的 |
|------|------|------|--------|------|
| `WanVideoImageToVideoMultiTalk` | width / height | 832 / 480 | **720 / 416** | 降低显存占用 |
| `WanVideoImageToVideoMultiTalk` | frame_window_size | 81 | **49** | 减少生成帧数 |
| `WanVideoImageToVideoMultiTalk` | motion_frame | 25 | **16** | 减少运动帧 |
| `WanVideoImageToVideoMultiTalk` | tiled_vae | false | **true** | VAE 编码分块 |
| `WanVideoDecode` | enable_vae_tiling | false | **true** | VAE 解码分块 |
| `WanVideoBlockSwap` | blocks_to_swap | 30 | **35** | 更多层放内存 |
| `WanVideoBlockSwap` | offload_img_emb / offload_txt_emb | false | **true** | 卸载嵌入 |
| `WanVideoTorchCompileSettings` | compile_transformer_blocks_only | true | **false** | 关闭 torch.compile |
| `AudioCrop` | end_time | 2:00 | **0:02** | 测试用短音频 |

### 仍需下载的模型

与原版相同：
- `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors`（~15 GB）
- `InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors`（~5 GB）
- `Wan2_1_VAE_bf16.safetensors`（~0.3 GB）
- `umt5-xxl-enc-bf16.safetensors`（~10 GB，可 offload 到内存）
- `clip_vision_vit_h.safetensors`（~1.7 GB）
- `TencentGameMate/chinese-wav2vec2-base`（~0.3 GB）
- `lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors`（LoRA，可选）

### 16GB 可行性

- **显存峰值**：Wan 14B fp8（~12–14 GB）+ InfiniteTalk（~5 GB）+ VAE/CLIP（~2 GB）≈ **18–20 GB 峰值需求**
- 由于 `block_swap=35` 和 `offload` 机制，部分权重会转移到内存，**有一定概率能跑起来**
- 如果仍然 OOM，请改用方案 B

---

## 方案 B：14B 轻量版（去掉对口型，仅图像输入 + 音频叠加）

### 改动内容

这是更稳的方案。去掉了整个 MultiTalk / InfiniteTalk / Wav2Vec / 音频分析分支：

**删除的节点：**
- `MultiTalkModelLoader`（InfiniteTalk 模型加载器）
- `DownloadAndLoadWav2VecModel`
- `MultiTalkWav2VecEmbeds`
- `AudioSeparation`
- `RH_GetAudioDuration`
- `ToInt`、`Int`、`SimpleMath+`
- `easy showAnything`（调试节点）

**替换的节点：**
- `WanVideoImageToVideoMultiTalk` → **`WanVideoImageToVideoEncode`**

**保留的功能：**
- 上传图片作为首帧
- 上传音频作为背景音
- 使用 Wan 14B fp8 生成视频
- 最后把视频和音频合并输出

**失去的功能：**
- **口型同步（lip-sync）**。视频里的人物不会跟着音频对口型，只是画面运动 + 背景音乐。

### 参数设置

- 分辨率：720 × 416
- 帧数：49 帧
- VAE tiling：开启
- Block swap：35
- Torch compile：关闭
- LoRA 连接已断开（可选，VRAM 紧张时建议不连）

### 仍需下载的模型

不需要 InfiniteTalk 和 Wav2Vec：
- `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors`（~15 GB）
- `Wan2_1_VAE_bf16.safetensors`（~0.3 GB）
- `umt5-xxl-enc-bf16.safetensors`（~10 GB，可 offload）
- `clip_vision_vit_h.safetensors`（~1.7 GB）

### 16GB 可行性

- **显存峰值**：Wan 14B fp8（~12–14 GB）+ VAE/CLIP（~2 GB）≈ **14–16 GB**
- 开启 block swap 和 offload 后，**大概率能稳定运行**
- 生成速度：约 **1–3 分钟 / 段**（49 帧 720p）

---

## 推荐操作步骤

### 第一步：先跑方案 B（轻量版）

1. 把 `digital_combination_lite_no_multitalk.json` 拖进 ComfyUI
2. 按之前的诊断报告安装缺失节点：`ComfyUI-WanVideoWrapper`、`audio-separation-nodes-comfyui`、`ComfyUI-GetAudioDuration`
   - 轻量版其实不需要 `ComfyUI-GetAudioDuration`，但保留安装也无害
3. 下载上述 4 个模型
4. 上传图片和音频，点击运行
5. 如果能稳定跑通，说明 16GB 环境 OK

### 第二步：再试方案 A（优化版）

如果方案 B 跑得稳，且你需要对口型效果：
1. 额外下载 InfiniteTalk 模型和 Wav2Vec 模型
2. 加载 `digital_combination_optimized_16gb.json`
3. 运行测试
4. 如果 OOM，把 `WanVideoBlockSwap` 的 `blocks_to_swap` 从 35 提到 39

---

## 如何恢复对口型？

如果你以后升级到 24GB 显存，可以直接用回原版 `digital_combination.json`，或者把轻量版中的 `WanVideoImageToVideoEncode` 重新替换为 `WanVideoImageToVideoMultiTalk`，并补回 MultiTalk 相关节点。

---

## 常见问题

### 加载轻量版后节点显示红色怎么办？

轻量版把 `WanVideoImageToVideoMultiTalk` 替换成了标准 `WanVideoImageToVideoEncode` 节点。如果 ComfyUI 加载后该节点显示红色，或连接线位置不对，说明输入端口的顺序需要微调。修复方法：

1. 删除显示红色的 `WanVideoImageToVideoEncode` 节点
2. 右键 → `Add Node` → `WanVideo` → `WanVideoImageToVideoEncode`
3. 手动连接：
   - `vae` ← `WanVideoVAELoader`
   - `clip_embeds` ← `WanVideoClipVisionEncode`
   - `start_image` ← `LayerUtility: ImageScaleByAspectRatio V2` 的 image
   - `width` / `height` ← `LayerUtility: ImageScaleByAspectRatio V2` 的 width / height
   - `image_embeds` → `WanVideoSampler` 的 `image_embeds`
4. 设置参数：width=720, height=416, num_frames=49, force_offload=true, tiled_vae=true

### Q1：为什么 1.3B 不能用？
A：官方没有发布 Wan2.1 I2V 1.3B 模型。Kijai 的 ComfyUI-WanVideoWrapper 只支持 14B I2V。T2V 1.3B 是存在的，但那是文生视频，不能用于你这张图生视频+对口型的场景。

### Q2：对口型和没对口型差别大吗？
A：如果视频主体是人物说话，差别很大。如果只是画面运动 + BGM，没差别。

### Q3：还能不能再快点？
A：可以进一步降到 640×360、33 帧，或者使用 Lightx2V 4 步 LoRA（已在优化版里连接）。但要先保证不 OOM。

### Q4：为什么 14B 还叫“小模型”？
A：严格来说不是小模型，而是通过去掉 InfiniteTalk 这个大模块，让整体显存占用降下来。这是在不换模型架构的前提下最实际的优化。

---

## 附：模型下载命令

```powershell
# 主模型（14B fp8 scaled）
huggingface-cli download Kijai/WanVideo_comfy Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors --local-dir "D:\FLUX Redux\models\diffusion_models"

# VAE
huggingface-cli download Kijai/WanVideo_comfy Wan2_1_VAE_bf16.safetensors --local-dir "D:\FLUX Redux\models\vae"

# Text Encoder
huggingface-cli download Kijai/WanVideo_comfy umt5-xxl-enc-bf16.safetensors --local-dir "D:\FLUX Redux\models\text_encoders"

# CLIP Vision
huggingface-cli download Comfy-Org/Wan_2.1_ComfyUI_repackaged split_files/clip_vision/clip_vision_h.safetensors --local-dir "D:\FLUX Redux\models\clip_vision"

# InfiniteTalk（仅方案 A 需要）
huggingface-cli download Kijai/WanVideo_comfy InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors --local-dir "D:\FLUX Redux\models\diffusion_models"
```
