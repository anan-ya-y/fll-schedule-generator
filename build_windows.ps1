$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildEnvironment = Join-Path $ProjectRoot "build_venv"
$Python = Join-Path $BuildEnvironment "Scripts\python.exe"
$SupportedVersions = @("3.13", "3.12", "3.11", "3.10")

Set-Location $ProjectRoot

if (-not (Test-Path $Python)) {
    $BaseCommand = $null
    $BasePrefix = @()

    foreach ($Version in $SupportedVersions) {
        try {
            & py "-$Version" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $BaseCommand = "py"
                $BasePrefix = @("-$Version")
                Write-Host "Using Python $Version from the Python launcher."
                break
            }
        }
        catch {
            # Continue to the next supported interpreter candidate.
        }
    }

    if (-not $BaseCommand) {
        try {
            $DefaultVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $SupportedVersions -contains $DefaultVersion.Trim()) {
                $BaseCommand = "python"
                Write-Host "Using Python $DefaultVersion from PATH."
            }
        }
        catch {
            # The actionable error below covers a missing PATH interpreter too.
        }
    }

    if (-not $BaseCommand) {
        throw "No supported Python was found. Install 64-bit Python 3.13 or 3.12 from python.org, including the Python launcher, then run this script again."
    }

    Write-Host "Creating the Windows build environment..."
    & $BaseCommand @BasePrefix -m venv $BuildEnvironment
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Python)) {
        throw "Python could not create $BuildEnvironment. Check the preceding error and remove any incomplete build_venv folder before retrying."
    }
}

Write-Host "Installing build dependencies..."
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Could not upgrade pip in the build environment."
}
& $Python -m pip install -r requirements-windows.txt
if ($LASTEXITCODE -ne 0) {
    throw "Could not install the Windows build dependencies."
}

Write-Host "Building the standalone application..."
& $Python -m PyInstaller --noconfirm --clean fll-scheduler-gui.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller could not build the application."
}

$Executable = Join-Path $ProjectRoot "dist\FLL Schedule Generator.exe"
if (-not (Test-Path $Executable)) {
    throw "The build finished without creating the expected executable: $Executable"
}

Write-Host ""
Write-Host "Build complete:"
Write-Host $Executable
