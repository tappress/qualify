# Qualify installer for Windows
# Usage: powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/tappress/qualify/main/install.ps1 | iex"

$Repo    = "tappress/qualify"
$BinDir  = "$env:LOCALAPPDATA\qualify"
$Binary  = "$BinDir\qualify.exe"
$Asset   = "qualify-windows-x86_64.exe"

function Write-Info  { Write-Host "-> $args" -ForegroundColor Blue }
function Write-Ok    { Write-Host "v  $args" -ForegroundColor Green }
function Write-Err   { Write-Host "x  $args" -ForegroundColor Red; exit 1 }

# Resolve version
if ($env:VERSION) {
    $Tag = $env:VERSION
} else {
    Write-Info "Fetching latest release..."
    try {
        $Release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
        $Tag = $Release.tag_name
    } catch {
        Write-Err "Could not fetch latest release. Set `$env:VERSION = 'vX.Y.Z'` to override."
    }
}

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

if ($env:QUALIFY_BIN_PATH) {
    # Use a locally built binary (development / CI)
    if (-not (Test-Path $env:QUALIFY_BIN_PATH)) { Write-Err "File not found: $env:QUALIFY_BIN_PATH" }
    Write-Info "Installing from local path: $env:QUALIFY_BIN_PATH"
    Copy-Item $env:QUALIFY_BIN_PATH -Destination $Binary
} else {
    Write-Info "Installing Qualify $Tag..."
    $Url = "https://github.com/$Repo/releases/download/$Tag/$Asset"
    Invoke-WebRequest -Uri $Url -OutFile $Binary -UseBasicParsing
}

Write-Ok "Installed to $Binary"

# Add to PATH for current user if not already there
$CurrentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($CurrentPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$CurrentPath;$BinDir", "User")
    Write-Info "Added $BinDir to your PATH. Restart your terminal to use 'qualify'."
} else {
    Write-Ok "Run 'qualify' to start."
}
