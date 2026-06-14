#Requires -Version 5.1
<#
.SYNOPSIS
    验证运行 digital_combination.json 工作流所需的 ComfyUI 环境。
.DESCRIPTION
    检查自定义节点、关键模型文件和 ComfyUI 版本是否满足要求。
#>

$ComfyUIPath = "D:\FLUX Redux"
$ModelsPath = Join-Path $ComfyUIPath "models"
$NodesPath = Join-Path $ComfyUIPath "custom_nodes"

$RequiredNodes = @(
    "ComfyUI-WanVideoWrapper",
    "audio-separation-nodes-comfyui",
    "ComfyUI-GetAudioDuration",
    "ComfyUI-VideoHelperSuite",
    "ComfyUI-Easy-Use",
    "ComfyUI-KJNodes",
    "ComfyUI_LayerStyle"
)

$RequiredModels = @(
    @{ Path = "vae\Wan2_1_VAE_bf16.safetensors"; Alias = @("wan_2.1_vae.safetensors") },
    @{ Path = "text_encoders\umt5-xxl-enc-bf16.safetensors"; Alias = @("umt5_xxl_fp8_e4m3fn_scaled.safetensors") },
    @{ Path = "diffusion_models\Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors"; Alias = @() },
    @{ Path = "loras\lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors"; Alias = @() },
    @{ Path = "diffusion_models\InfiniteTalk\Wan2_1-InfiniTetalk-Single_fp16.safetensors"; Alias = @() },
    @{ Path = "clip_vision\clip_vision_vit_h.safetensors"; Alias = @("clip_vision_h.safetensors") }
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "digital_combination.json 环境验证脚本" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 ComfyUI 版本
$versionFile = Join-Path $ComfyUIPath "comfyui_version.py"
if (Test-Path $versionFile) {
    $verContent = Get-Content $versionFile -Raw
    if ($verContent -match "__version__\s*=\s*[`"']([^`"']+)[`"']") {
        Write-Host "ComfyUI 版本: $($matches[1])" -ForegroundColor Green
    }
} else {
    Write-Host "无法读取 ComfyUI 版本" -ForegroundColor Red
}
Write-Host ""

# 2. 检查自定义节点
Write-Host "[1/3] 自定义节点检查" -ForegroundColor Yellow
$allNodesOk = $true
foreach ($node in $RequiredNodes) {
    $nodeDir = Join-Path $NodesPath $node
    if (Test-Path $nodeDir -PathType Container) {
        Write-Host "  [OK] $node" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $node" -ForegroundColor Red
        $allNodesOk = $false
    }
}
Write-Host ""

# 3. 检查模型文件
Write-Host "[2/3] 关键模型文件检查" -ForegroundColor Yellow
$allModelsOk = $true
foreach ($model in $RequiredModels) {
    $fullPath = Join-Path $ModelsPath $model.Path
    $exists = Test-Path $fullPath -PathType Leaf
    $foundAlias = $null
    if (-not $exists) {
        foreach ($alias in $model.Alias) {
            $aliasPath = Join-Path (Split-Path $fullPath -Parent) $alias
            if (Test-Path $aliasPath -PathType Leaf) {
                $foundAlias = $alias
                break
            }
        }
    }
    if ($exists) {
        $size = (Get-Item $fullPath).Length / 1GB
        Write-Host "  [OK] $($model.Path) ($([math]::Round($size,2)) GB)" -ForegroundColor Green
    } elseif ($foundAlias) {
        Write-Host "  [ALIAS] $($model.Path) 未找到，但存在别名: $foundAlias（建议复制重命名）" -ForegroundColor Yellow
        $allModelsOk = $false
    } else {
        Write-Host "  [MISSING] $($model.Path)" -ForegroundColor Red
        $allModelsOk = $false
    }
}
Write-Host ""

# 4. 检查 Wav2Vec（特殊处理，可能是目录）
Write-Host "[3/3] Wav2Vec 模型检查" -ForegroundColor Yellow
$wav2vecPaths = @(
    Join-Path $ModelsPath "audio_encoders\chinese-wav2vec2-base",
    Join-Path $env:USERPROFILE ".cache\huggingface\hub\TencentGameMate_chinese-wav2vec2-base"
)
$wav2vecFound = $false
foreach ($wp in $wav2vecPaths) {
    if (Test-Path $wp) {
        Write-Host "  [OK] 找到 Wav2Vec: $wp" -ForegroundColor Green
        $wav2vecFound = $true
        break
    }
}
if (-not $wav2vecFound) {
    Write-Host "  [INFO] Wav2Vec 未预先放置，运行时会自动下载" -ForegroundColor Yellow
}
Write-Host ""

# 5. 总结
Write-Host "============================================" -ForegroundColor Cyan
if ($allNodesOk -and $allModelsOk) {
    Write-Host "结论：环境检查通过，可尝试加载工作流。" -ForegroundColor Green
} else {
    Write-Host "结论：环境未就绪，请参考诊断报告进行修复。" -ForegroundColor Red
}
Write-Host "============================================" -ForegroundColor Cyan

pause
