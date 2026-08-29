# Windows Code Signing Script
# Usage: .\desktop\windows\sign.ps1 [executable_path]

param(
    [Parameter(Mandatory=$false)]
    [string]$FilePath = "desktop\dist\Lengrowth.exe",
    [string]$CertPath = $env:SIGN_CERT_PATH,
    [string]$CertPass = $env:SIGN_CERT_PASS,
    [string]$Timestamp = "https://timestamp.digicert.com"
)

if (-not $CertPath) {
    Write-Host "Error: SIGN_CERT_PATH environment variable not set" -ForegroundColor Red
    Write-Host "Set it to the path of your code signing certificate (.pfx)" -ForegroundColor Yellow
    exit 1
}

if (-not $CertPass) {
    Write-Host "Error: SIGN_CERT_PASS environment variable not set" -ForegroundColor Red
    Write-Host "Set it to your certificate password" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $CertPath)) {
    Write-Host "Error: Certificate not found at: $CertPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $FilePath)) {
    Write-Host "Error: File not found: $FilePath" -ForegroundColor Red
    exit 1
}

# Resolve signtool from PATH or an installed Windows SDK.
$signToolCommand = Get-Command signtool.exe -ErrorAction SilentlyContinue
$signTool = if ($signToolCommand) { $signToolCommand.Source } else {
    $sdkRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    $candidate = Get-ChildItem -LiteralPath $sdkRoot -Filter signtool.exe -File -Recurse -ErrorAction SilentlyContinue |
        Sort-Object -Property FullName -Descending |
        Select-Object -First 1
    if ($candidate) { $candidate.FullName }
}
if (-not $signTool) {
    Write-Host "Error: signtool.exe not found in PATH or Windows SDK" -ForegroundColor Red
    exit 1
}

Write-Host "Signing: $FilePath" -ForegroundColor Cyan
Write-Host "Certificate: $CertPath" -ForegroundColor Cyan

# Sign with SHA256
$signResult = & $signTool sign /f "$CertPath" /p "$CertPass" /t "$Timestamp" /fd SHA256 /v "$FilePath" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Successfully signed: $FilePath" -ForegroundColor Green

    # Verify signature
    Write-Host "`nVerifying signature..." -ForegroundColor Cyan
    & $signTool verify /pa /v "$FilePath"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Signature verified successfully!" -ForegroundColor Green
    } else {
        Write-Host "Error: Signature verification failed" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Error: Code signing failed" -ForegroundColor Red
    Write-Host $signResult -ForegroundColor Red
    exit 1
}
