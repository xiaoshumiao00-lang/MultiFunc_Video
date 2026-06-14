#Requires -Version 5.1
# Verify digital_combination.json workflow environment

$ComfyRoot = "D:/FLUX Redux"
$NodesDir = Join-Path $ComfyRoot "custom_nodes"
$ModelsDir = Join-Path $ComfyRoot "models"

$requiredNodes = @(
    "ComfyUI-WanVideoWrapper",
    "audio-separation-nodes-comfyui",
    "ComfyUI-VideoHelperSuite",
    "ComfyUI-KJNodes",
    "ComfyUI-GetAudioDuration",
    "ComfyUI-Basic-Math"
)

function Test-NodePackage {
    param([string]$Package)
    $variants = @($Package, $Package.Replace("-", "_"), $Package.Replace("_", "-"))
    foreach ($v in $variants) {
        if (Test-Path (Join-Path $NodesDir $v) -PathType Container) {
            return $true
        }
    }
    return $false
}

function Test-ModelFile {
    param([string]$FileName, [string[]]$SearchDirs)
    # InfiniteTalk model is loaded from diffusion_models by MultiTalkModelLoader
    $infPath = Join-Path (Join-Path $ModelsDir "diffusion_models") (Join-Path "InfiniteTalk" $FileName)
    if (Test-Path $infPath -PathType Leaf) {
        return $infPath
    }
    foreach ($dir in $SearchDirs) {
        $path = Join-Path (Join-Path $ModelsDir $dir) $FileName
        if (Test-Path $path -PathType Leaf) {
            return $path
        }
    }
    return $null
}

Write-Host "digital_combination.json environment verification" -ForegroundColor Cyan

$allOk = $true

Write-Host "`n[Custom Nodes]" -ForegroundColor Yellow
foreach ($node in $requiredNodes) {
    if (Test-NodePackage -Package $node) {
        Write-Host "  [OK]   $node" -ForegroundColor Green
    } else {
        Write-Host "  [MISS] $node" -ForegroundColor Red
        $allOk = $false
    }
}

Write-Host "`n[Models]" -ForegroundColor Yellow
$models = @(
    @{ Name = "Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors"; Dirs = @("diffusion_models") },
    @{ Name = "Wan2_1_VAE_bf16.safetensors"; Dirs = @("vae") },
    @{ Name = "umt5-xxl-enc-bf16.safetensors"; Dirs = @("text_encoders") },
    @{ Name = "clip_vision_vit_h.safetensors"; Dirs = @("clip_vision") },
    @{ Name = "lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors"; Dirs = @("loras", "diffusion_models") },
    @{ Name = "Wan2_1-InfiniTetalk-Single_fp16.safetensors"; Dirs = @("diffusion_models", "checkpoints") }
)
foreach ($m in $models) {
    $found = Test-ModelFile -FileName $m.Name -SearchDirs $m.Dirs
    if ($found) {
        Write-Host "  [OK]   $($m.Name)" -ForegroundColor Green
    } else {
        Write-Host "  [MISS] $($m.Name)" -ForegroundColor Red
        $allOk = $false
    }
}

$audioPath = Join-Path $ModelsDir "transformers/TencentGameMate/chinese-wav2vec2-base"
if (Test-Path $audioPath -PathType Container) {
    Write-Host "  [OK]   transformers/TencentGameMate/chinese-wav2vec2-base" -ForegroundColor Green
} else {
    Write-Host "  [MISS] transformers/TencentGameMate/chinese-wav2vec2-base" -ForegroundColor Red
    $allOk = $false
}

Write-Host ""
if ($allOk) {
    Write-Host "All checks passed. Restart ComfyUI and load the workflow." -ForegroundColor Green
} else {
    Write-Host "Missing items found. See digital_combination_diagnosis.md." -ForegroundColor Red
}
