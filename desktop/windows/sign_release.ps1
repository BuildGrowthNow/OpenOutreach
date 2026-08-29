# Sign and verify all Windows release artifacts.
# Required environment variables:
#   WINDOWS_SIGNING_CERT_BASE64
#   WINDOWS_SIGNING_CERT_PASSWORD

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$FilePath,
    [string]$Timestamp = "https://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

if (-not $env:WINDOWS_SIGNING_CERT_BASE64) {
    throw "WINDOWS_SIGNING_CERT_BASE64 is not set"
}
if (-not $env:WINDOWS_SIGNING_CERT_PASSWORD) {
    throw "WINDOWS_SIGNING_CERT_PASSWORD is not set"
}

$signToolCommand = Get-Command signtool.exe -ErrorAction SilentlyContinue
$signTool = if ($signToolCommand) { $signToolCommand.Source } else {
    $sdkRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    $candidate = Get-ChildItem -LiteralPath $sdkRoot -Filter signtool.exe -File -Recurse |
        Sort-Object -Property FullName -Descending |
        Select-Object -First 1
    if ($candidate) { $candidate.FullName }
}
if (-not $signTool) {
    throw "signtool.exe was not found"
}

$certificatePath = Join-Path $env:RUNNER_TEMP "lengrowth-signing.pfx"
try {
    [IO.File]::WriteAllBytes(
        $certificatePath,
        [Convert]::FromBase64String($env:WINDOWS_SIGNING_CERT_BASE64)
    )

    foreach ($path in $FilePath) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Release artifact not found: $path"
        }
        & $signTool sign /f $certificatePath /p $env:WINDOWS_SIGNING_CERT_PASSWORD `
            /fd SHA256 /tr $Timestamp /td SHA256 /as $path
        if ($LASTEXITCODE -ne 0) {
            throw "Signing failed for $path"
        }
        & $signTool verify /pa /v $path
        if ($LASTEXITCODE -ne 0) {
            throw "Signature verification failed for $path"
        }
    }
}
finally {
    Remove-Item -LiteralPath $certificatePath -Force -ErrorAction SilentlyContinue
}
