#Requires -Version 5.1
# Install missing custom nodes for digital_combination.json

$ComfyRoot = "D:/FLUX Redux"
$NodesDir = Join-Path $ComfyRoot "custom_nodes"

$packages = @(
    @{ Name = "ComfyUI-WanVideoWrapper"; Url = "https://github.com/kijai/ComfyUI-WanVideoWrapper.git" },
    @{ Name = "audio-separation-nodes-comfyui"; Url = "https://github.com/christian-byrne/audio-separation-nodes-comfyui.git" }
)

function Find-ComfyPython {
    $candidates = @(
        "$ComfyRoot/python/python.exe",
        "$ComfyRoot/venv/Scripts/python.exe",
        "$ComfyRoot/.venv/Scripts/python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    return $null
}

$python = Find-ComfyPython
if (-not $python) {
    Write-Warning "ComfyUI Python interpreter not found. Please install node requirements manually."
}

foreach ($pkg in $packages) {
    $target = Join-Path $NodesDir $pkg.Name
    if (Test-Path $target -PathType Container) {
        Write-Host "[$($pkg.Name)] already exists, skipping clone." -ForegroundColor Green
    } else {
        Write-Host "[$($pkg.Name)] cloning..." -ForegroundColor Cyan
        git clone $pkg.Url $target
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to clone $($pkg.Name)."
            continue
        }
    }

    $req = Join-Path $target "requirements.txt"
    if ($python -and (Test-Path $req)) {
        Write-Host "[$($pkg.Name)] installing requirements..." -ForegroundColor Cyan
        & $python -m pip install -r $req
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to install requirements for $($pkg.Name). If ComfyUI is running, restart it and try again."
        }
    }
}

Write-Host ""
Write-Host "Node installation complete. Please restart ComfyUI." -ForegroundColor Green
Write-Host "Model files still need to be downloaded manually. See digital_combination_diagnosis.md." -ForegroundColor Yellow
