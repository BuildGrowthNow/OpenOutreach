# Windows Code Signing Script
# Usage: .\desktop\windows\sign.ps1 [executable_path]

param(
    [Parameter(Mandatory=$false)]
    [string]$FilePath = "desktop\dist\OpenOutreach.exe",
    [string]$CertPath = $env:SIGN_CERT_PATH,
    [string]$CertPass = $env:SIGN_CERT_PASS,
    [string]$Timestamp = "http://timestamp.digicert.com"
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

Write-Host "Signing: $FilePath" -ForegroundColor Cyan
Write-Host "Certificate: $CertPath" -ForegroundColor Cyan

# Sign with SHA256
$signResult = & signtool sign /f "$CertPath" /p "$CertPass" /t "$Timestamp" /fd SHA256 /v "$FilePath" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Successfully signed: $FilePath" -ForegroundColor Green

    # Verify signature
    Write-Host "`nVerifying signature..." -ForegroundColor Cyan
    & signtool verify /pa /v "$FilePath"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Signature verified successfully!" -ForegroundColor Green
    } else {
        Write-Host "Warning: Signature verification failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "Error: Code signing failed" -ForegroundColor Red
    Write-Host $signResult -ForegroundColor Red
    exit 1
}
