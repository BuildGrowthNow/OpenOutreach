# Windows Installation Guide

## Download Options

### Option 1: NSIS Installer (Recommended)
**Best for:** Most users who want a traditional installer experience

1. Download `OpenOutreach-{version}-Setup.exe` from the latest release
2. Run the installer
3. If Windows SmartScreen appears:
   - Click "More info"
   - Click "Run anyway"
4. Follow the installation wizard:
   - Choose installation directory (default: `C:\Program Files\OpenOutreach`)
   - Installer will create Start Menu shortcuts and desktop icon
   - Protocol handler (`openoutreach://`) is registered automatically
5. Launch OpenOutreach from Start Menu or desktop icon
6. Log in with your OpenOutreach account

**What gets installed:**
- Application: `C:\Program Files\OpenOutreach\OpenOutreach.exe`
- Start Menu shortcuts
- Desktop shortcut
- Protocol handler registration
- Uninstaller: `C:\Program Files\OpenOutreach\Uninstall.exe`

### Option 2: Standalone Executable
**Best for:** Users who prefer portable apps without installation

1. Download `OpenOutreach.exe` from the latest release
2. Move it to your preferred location (e.g., `C:\Tools\OpenOutreach\`)
3. If Windows SmartScreen appears:
   - Click "More info"
   - Click "Run anyway"
4. Double-click to run
5. Log in with your OpenOutreach account

**Note:** Protocol handler must be registered manually (see below)

### Option 3: Microsoft Store (MSIX)
**Best for:** Enterprise users or those who prefer Store apps

The MSIX package is available for:
- Sideloading (requires Developer Mode)
- Microsoft Store submission (when available)

**To sideload:**
1. Enable Developer Mode: Settings → Update & Security → For developers → Developer mode
2. Download `OpenOutreach-{version}.msix`
3. Double-click the MSIX file
4. Click "Install"
5. Launch from Start Menu

## SmartScreen Warning

### Why does it appear?
Windows SmartScreen shows a warning for apps that don't have enough download reputation. This is normal for new or unsigned applications.

### Is it safe?
Yes! OpenOutreach is open-source and built from the GitHub repository. The warning will disappear automatically after the app gains reputation (~10-20 downloads from different users).

### How to bypass:
1. Click "More info"
2. Click "Run anyway"

This only needs to be done once on first launch.

## Manual Protocol Handler Registration

If using the standalone executable, register the protocol handler manually:

### Method 1: Registry File
1. Download `desktop/windows/register_protocol.reg`
2. Edit the paths to match your installation location
3. Double-click the .reg file
4. Click "Yes" to confirm

### Method 2: PowerShell
```powershell
# Run as Administrator
New-Item -Path "HKCR:\openoutreach" -Force
Set-ItemProperty -Path "HKCR:\openoutreach" -Name "(Default)" -Value "URL:OpenOutreach Protocol"
Set-ItemProperty -Path "HKCR:\openoutreach" -Name "URL Protocol" -Value ""
New-Item -Path "HKCR:\openoutreach\shell\open\command" -Force
Set-ItemProperty -Path "HKCR:\openoutreach\shell\open\command" -Name "(Default)" -Value '"C:\Path\To\OpenOutreach.exe" "%1"'
```

## Auto-Start on Login

### NSIS Installer
The installer creates a Start Menu shortcut. To auto-start:
1. Press `Win+R`
2. Type: `shell:startup`
3. Create a shortcut to `C:\Program Files\OpenOutreach\OpenOutreach.exe`

### Standalone
1. Press `Win+R`
2. Type: `shell:startup`
3. Copy `OpenOutreach.exe` or create a shortcut to it

## Uninstallation

### NSIS Installer
**Via Settings:**
1. Settings → Apps → Apps & features
2. Find "OpenOutreach"
3. Click "Uninstall"

**Via Start Menu:**
1. Start → OpenOutreach → Uninstall

**Via Command Line:**
```cmd
"C:\Program Files\OpenOutreach\Uninstall.exe"
```

### Standalone
Simply delete the executable and remove any shortcuts you created.

### MSIX
1. Settings → Apps → Apps & features
2. Find "OpenOutreach"
3. Click "Uninstall"

## Troubleshooting

### SmartScreen blocks the app
- Make sure you clicked "More info" then "Run anyway"
- If still blocked, right-click the file → Properties → Check "Unblock" → Apply

### App doesn't start
- Check if antivirus is blocking it (add exception)
- Run as Administrator (right-click → Run as administrator)
- Check Windows Event Viewer for errors

### Protocol handler not working
- Verify registration: Run `reg query HKCR\openoutreach\shell\open\command`
- Re-run the registration steps above
- Restart browser after registration

### Tray icon not showing
- Check system tray settings: Settings → Personalization → Taskbar → Select which icons appear on taskbar
- Enable "OpenOutreach"

### Can't find browser
- Install Chrome or Edge
- Make sure browser is installed in default location:
  - Chrome: `C:\Program Files\Google\Chrome\Application\chrome.exe`
  - Edge: `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`

## Data Storage

### Application data location:
- Config: `%APPDATA%\Local\OpenOutreach\config.json`
- Browser data: `%APPDATA%\Local\OpenOutreach\browser_data\`
- Daemon ID: `%APPDATA%\Local\OpenOutreach\daemon_id`

### Credentials
Stored securely in Windows Credential Manager under "OpenOutreach"

## System Requirements

- **OS:** Windows 10 (build 17763) or Windows 11
- **Architecture:** 64-bit (x64)
- **RAM:** 2GB minimum, 4GB recommended
- **Disk:** 100MB for app + 200MB for browser data
- **Browser:** Chrome or Edge (must be installed separately)

## Security

### Code Signing
Current releases are unsigned (SmartScreen warning appears). Future releases may be signed to remove this warning.

### Open Source
- Source code: https://github.com/openoutreach/openoutreach
- Build reproducible via GitHub Actions
- No telemetry or tracking

### Permissions
The app requires:
- **Internet access:** To connect to OpenOutreach backend
- **System tray:** For tray icon
- **User data access:** To store config in AppData
- **Browser control:** To automate LinkedIn via your installed browser

## Updates

The app checks for updates on startup. When a new version is available:
1. A notification appears in the system tray menu
2. Click to open the download page
3. Download and install the new version
4. The installer will upgrade in place (settings preserved)

## Support

- Documentation: https://docs.openoutreach.io
- Issues: https://github.com/openoutreach/openoutreach/issues
- Email: support@openoutreach.io
