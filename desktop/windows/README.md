# Windows Distribution

## Build Requirements

### For MSIX (Microsoft Store)
- Windows SDK (includes `makeappx.exe`)
- Install from: https://developer.microsoft.com/windows/downloads/windows-sdk/

### For NSIS Installer (Direct Download)
- NSIS (Nullsoft Scriptable Install System)
- Install from: https://nsis.sourceforge.io/

## Building

### 1. Build the executable
```bash
python desktop/build.py
```

Output: `desktop/dist/Lengrowth.exe`

### 2. Create MSIX package (Microsoft Store)
```bash
python desktop/build.py --msix
```

Output: `desktop/dist/Lengrowth-{version}.msix`

### 3. Create NSIS installer (Direct Download)
```bash
python desktop/build.py --installer
```

Output: `desktop/dist/Lengrowth-{version}-Setup.exe`

### 4. Build all formats
```bash
python desktop/build.py --all
```

## Code Signing (Optional)

### Sign with certificate
```bash
# Set environment variables
set SIGN_CERT_PATH=C:\path\to\certificate.pfx
set SIGN_CERT_PASS=your_password

# Sign the executable with an HTTPS timestamp
signtool sign /f "%SIGN_CERT_PATH%" /p "%SIGN_CERT_PASS%" /tr https://timestamp.digicert.com /td SHA256 /fd SHA256 desktop\dist\Lengrowth.exe
```

### Sign the MSIX
```bash
signtool sign /f "%SIGN_CERT_PATH%" /p "%SIGN_CERT_PASS%" /tr https://timestamp.digicert.com /td SHA256 /fd SHA256 desktop\dist\Lengrowth-{version}.msix
```

## Microsoft Store Submission

1. Create Microsoft Partner Center account (free)
2. Create new app submission
3. Upload the signed MSIX package
4. Fill in app details, screenshots, and description
5. Submit for review

## Protocol Handler

The installer automatically registers the `lengrowth://` protocol handler for OAuth callbacks.

Registry entries:
- `HKEY_CLASSES_ROOT\lengrowth`
- Command: `"%LOCALAPPDATA%\Programs\Lengrowth Outreach\Lengrowth.exe" "%1"`

## SmartScreen Warning

For unsigned builds, users will see Windows SmartScreen:
1. Click "More info"
2. Click "Run anyway"

This warning disappears after the app gains reputation (~10-20 downloads from different users).

## Uninstallation

### NSIS Installer
- Via "Add or Remove Programs"
- Or run: `"%LOCALAPPDATA%\Programs\Lengrowth Outreach\Uninstall.exe"`

### MSIX
- Via "Add or Remove Programs"
- Or: Settings → Apps → Lengrowth Outreach → Uninstall
