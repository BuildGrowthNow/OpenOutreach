# Windows Build Guide for Developers

## Prerequisites

### Required
- Python 3.11+
- Windows 10 (build 17763) or Windows 11
- Git Bash or PowerShell

### Optional (for packaging)
- **Windows SDK** (for MSIX): https://developer.microsoft.com/windows/downloads/windows-sdk/
- **NSIS** (for installer): https://nsis.sourceforge.io/ or `choco install nsis`
- **Code Signing Certificate** (optional, removes SmartScreen warning)

## Quick Start

### 1. Setup Development Environment

```bash
# Clone repository
git clone https://github.com/openoutreach/openoutreach.git
cd openoutreach

# Install dependencies
pip install -r desktop/requirements.txt
```

### 2. Build Executable

```bash
# Build standalone exe
python desktop/build.py

# Output: desktop/dist/OpenOutreach.exe
```

### 3. Create Installer (Recommended)

```bash
# Install NSIS first
choco install nsis -y

# Build exe + NSIS installer
python desktop/build.py --installer

# Output: desktop/dist/OpenOutreach-{version}-Setup.exe
```

### 4. Create MSIX Package

```bash
# Requires Windows SDK
python desktop/build.py --msix

# Output: desktop/dist/OpenOutreach-{version}.msix
```

### 5. Build Everything

```bash
python desktop/build.py --all

# Creates:
# - OpenOutreach.exe (standalone)
# - OpenOutreach-{version}.msix (Store package)
# - OpenOutreach-{version}-Setup.exe (installer)
```

## Build Commands Reference

```bash
# Clean build artifacts
python desktop/build.py --clean

# Build exe only
python desktop/build.py

# Build + create NSIS installer
python desktop/build.py --installer

# Build + create MSIX
python desktop/build.py --msix

# Build all formats
python desktop/build.py --all

# Regenerate icons only
python desktop/build.py --icons

# Use existing build (skip rebuild)
python desktop/build.py --no-build --installer
python desktop/build.py --no-build --msix

# Show help
python desktop/build.py --help
```

## Directory Structure

```
desktop/
├── build.py                    # Main build script
├── openoutreach.spec          # PyInstaller configuration
├── requirements.txt           # Build dependencies
├── build/                     # Build artifacts (temporary)
├── dist/                      # Output directory
└── windows/                   # Windows-specific files
    ├── README.md              # Overview
    ├── BUILD_GUIDE.md         # This file
    ├── INSTALLATION.md        # User installation guide
    ├── sign.ps1               # Code signing script
    └── register_protocol.reg  # Manual protocol registration

openoutreach/desktop/
├── app.py                     # Main tray application
├── auth.py                    # Authentication manager
├── config.py                  # Configuration
├── updater.py                 # Update checker
├── protocol_handler.py        # Protocol handler
├── __version__.py             # Version number
└── assets/
    ├── icon.png               # Master icon (512x512)
    ├── icon.ico               # Windows icon
    ├── icon-*.png             # Various sizes
    └── generate_icon.py       # Icon generator script
```

## Code Signing

### Setup Certificate

```powershell
# Set environment variables (PowerShell)
$env:SIGN_CERT_PATH = "C:\path\to\cert.pfx"
$env:SIGN_CERT_PASS = "your_password"

# Or use system environment variables (persistent)
[System.Environment]::SetEnvironmentVariable('SIGN_CERT_PATH', 'C:\path\to\cert.pfx', 'User')
[System.Environment]::SetEnvironmentVariable('SIGN_CERT_PASS', 'your_password', 'User')
```

### Sign Executable

```powershell
# Using provided script
.\desktop\windows\sign.ps1

# Or sign specific file
.\desktop\windows\sign.ps1 -FilePath "desktop\dist\OpenOutreach.exe"

# Manual signing
signtool sign /f cert.pfx /p password /t http://timestamp.digicert.com /fd SHA256 desktop\dist\OpenOutreach.exe

# Verify signature
signtool verify /pa /v desktop\dist\OpenOutreach.exe
```

### Sign MSIX

```powershell
signtool sign /f cert.pfx /p password /fd SHA256 desktop\dist\OpenOutreach-1.0.0.msix
```

## Testing Build

### Local Testing

```bash
# Run directly
desktop/dist/OpenOutreach.exe

# Test protocol handler
start openoutreach://auth?token=test

# Check version
desktop/dist/OpenOutreach.exe --version

# View help
desktop/dist/OpenOutreach.exe --help
```

### Test Installer

```bash
# Install
desktop/dist/OpenOutreach-1.0.0-Setup.exe

# Check installation
dir "C:\Program Files\OpenOutreach"

# Test launch
& "C:\Program Files\OpenOutreach\OpenOutreach.exe"

# Uninstall
& "C:\Program Files\OpenOutreach\Uninstall.exe"
```

### Test MSIX

```bash
# Enable Developer Mode first: Settings → For developers → Developer mode

# Install
Add-AppxPackage -Path desktop\dist\OpenOutreach-1.0.0.msix

# List installed
Get-AppxPackage | Where-Object {$_.Name -like "*OpenOutreach*"}

# Uninstall
Remove-AppxPackage OpenOutreach.Desktop_1.0.0.0_x64__XXXXX
```

## Troubleshooting

### Build Issues

**PyInstaller fails:**
```bash
# Clean and retry
python desktop/build.py --clean
pip install --upgrade pyinstaller
python desktop/build.py
```

**Icon errors:**
```bash
# Regenerate icons
python desktop/build.py --icons

# Or manually
cd openoutreach/desktop/assets
python generate_icon.py
```

**Import errors:**
```bash
# Check hidden imports in openoutreach.spec
# Add missing modules to hiddenimports list
```

### MSIX Issues

**makeappx.exe not found:**
- Install Windows SDK
- Check paths in build.py (tries multiple SDK versions)
- Or specify manually: `$env:MAKEAPPX = "C:\path\to\makeappx.exe"`

**Invalid manifest:**
- Check version format (must be X.X.X.X)
- Verify Publisher matches certificate

### NSIS Issues

**makensis.exe not found:**
```bash
# Install via Chocolatey
choco install nsis -y

# Or download installer from nsis.sourceforge.io
```

**Icon not found:**
- Check `openoutreach/desktop/assets/icon.ico` exists
- Run `python desktop/build.py --icons` first

### Signing Issues

**Certificate not found:**
```bash
# Check path
$env:SIGN_CERT_PATH

# Test certificate
certutil -dump cert.pfx
```

**signtool not found:**
```bash
# Find Windows SDK install
dir "C:\Program Files (x86)\Windows Kits" /s /b | findstr signtool

# Add to PATH
$env:PATH += ";C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64"
```

**Timestamp server fails:**
- Retry (sometimes servers are slow)
- Try alternative: `-t http://timestamp.comodoca.com`

## Size Optimization

Current build size: ~20-30MB

### Reduce Size:
1. **Exclude unused packages:** Edit `excludes` in `openoutreach.spec`
2. **UPX compression:** Already enabled (`upx=True`)
3. **Strip debug symbols:** Already enabled (`strip=False` for Windows compatibility)
4. **Remove unused files:** Add to `excludes` list

### What's Included:
- Python runtime (~8MB)
- Core dependencies (httpx, pystray, keyring, Pillow)
- OpenOutreach modules (daemon, browser_detect, remote_client)

### What's Excluded:
- Playwright (not bundled, uses system browser)
- MongoDB drivers (desktop connects to backend API only)
- FastAPI (not needed on client)
- Heavy ML libraries (numpy, pandas, etc.)

## Version Management

### Update Version

Edit `openoutreach/desktop/__version__.py`:
```python
__version__ = "1.0.1"
```

This version is automatically used in:
- Executable version info
- MSIX manifest
- NSIS installer
- Update checker
- GitHub release

### Release Process

1. Update version in `__version__.py`
2. Commit changes
3. Tag release:
   ```bash
   git tag desktop-v1.0.1
   git push origin desktop-v1.0.1
   ```
4. GitHub Actions will automatically:
   - Build Windows exe
   - Create MSIX package
   - Create NSIS installer
   - Upload artifacts
   - Create GitHub release

## CI/CD

GitHub Actions workflow: `.github/workflows/desktop-build.yml`

**Triggers:**
- Push tags: `desktop-v*`
- Manual workflow dispatch

**Outputs:**
- `OpenOutreach.exe` (standalone)
- `OpenOutreach-{version}.msix` (if SDK available)
- `OpenOutreach-{version}-Setup.exe` (via Chocolatey NSIS)

**Local simulation:**
```bash
# Install dependencies
pip install -r desktop/requirements.txt

# Build all
python desktop/build.py --all

# Artifacts in desktop/dist/
```

## Development Tips

### Hot Reload Development

For developing the desktop app itself:
```bash
# Run directly (not built)
python openoutreach/desktop/app.py

# Or via module
python -m openoutreach.desktop.app
```

### Debug Build

For debugging, create debug build:
```bash
# Edit openoutreach.spec:
# debug=True
# console=True  # Shows console window

python desktop/build.py
```

### Test Without Building

```bash
# Test individual components
python openoutreach/core/browser_detect.py
python openoutreach/core/remote_client.py
python openoutreach/desktop/updater.py
```

### Modify Build Configuration

Edit `desktop/openoutreach.spec`:
- `hiddenimports`: Add missing imports
- `excludes`: Remove unused packages
- `datas`: Include additional files
- `console`: Show/hide console window
- `icon`: Change app icon

## Support

- Build issues: Check `desktop/build/` logs
- Runtime issues: Check Windows Event Viewer
- Questions: Open GitHub issue
- Docs: `docs/DESKTOP_APP.md`
