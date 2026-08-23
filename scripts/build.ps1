param(
    [switch]$Install
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BuildRoot = Join-Path $ProjectRoot "build"
$DistRoot = Join-Path $ProjectRoot "dist"
$PlatformTools = Join-Path $DistRoot "platform-tools"
$SourceRoot = Join-Path $ProjectRoot "src"

if ($env:CONDA_DEFAULT_ENV -ne "f407cp") {
    $conda = Get-Command conda.exe -ErrorAction SilentlyContinue
    if ($conda) {
        Write-Host "Activating 'f407cp' conda environment..." -ForegroundColor Yellow
        $installArg = if ($Install) { "-Install" } else { "" }
        & conda run --no-capture-output -n f407cp powershell -NoProfile -ExecutionPolicy Bypass -File "$PSCommandPath" $installArg
        exit $LASTEXITCODE
    }
    Write-Host "Conda environment 'f407cp' not active; using current Python." -ForegroundColor Yellow
}

function Invoke-PyInstallerSpec {
    param(
        [Parameter(Mandatory = $true)][string]$SpecPath,
        [Parameter(Mandatory = $true)][string]$DistPath,
        [Parameter(Mandatory = $true)][string]$WorkName
    )

    $WorkPath = Join-Path (Join-Path $BuildRoot "pyinstaller") $WorkName
    New-Item -ItemType Directory -Path $WorkPath -Force | Out-Null

    $Arguments = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath", $DistPath,
        "--workpath", $WorkPath,
        $SpecPath
    )
    Write-Host "python $($Arguments -join ' ')" -ForegroundColor Cyan
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed for $SpecPath with exit code $LASTEXITCODE"
    }
}

try {
    & python -c "import PyInstaller, cv2, numpy"
    if ($LASTEXITCODE -ne 0) {
        throw "Missing build dependency. Run: python -m pip install -r requirement.txt"
    }

    if (Test-Path $BuildRoot) {
        Remove-Item $BuildRoot -Recurse -Force
    }
    if (Test-Path $DistRoot) {
        Remove-Item $DistRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $PlatformTools -Force | Out-Null

    Invoke-PyInstallerSpec `
        -SpecPath (Join-Path $SourceRoot "tvidtool\tvidtool.spec") `
        -DistPath $PlatformTools `
        -WorkName "tvidtool"

    $Tool = Join-Path $PlatformTools "tvidtool.exe"
    if (-not (Test-Path $Tool -PathType Leaf)) {
        throw "Expected output was not generated: $Tool"
    }
    & $Tool --version | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "$Tool version test failed."
    }

    if ($Install) {
        if (-not $env:CONDA_PREFIX) {
            throw "No active Conda environment. Activate 'f407cp' before using -Install."
        }
        $ScriptsDir = Join-Path $env:CONDA_PREFIX "Scripts"
        New-Item -ItemType Directory -Path $ScriptsDir -Force | Out-Null
        Copy-Item $Tool $ScriptsDir -Force
        Write-Host "Installed tvidtool.exe to $ScriptsDir" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Build complete:" -ForegroundColor Green
    Write-Host "  dist\platform-tools\tvidtool.exe"
}
catch {
    Write-Error $_
    exit 1
}
