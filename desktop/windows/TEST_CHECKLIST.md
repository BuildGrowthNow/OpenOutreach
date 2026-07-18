# Windows Distribution Testing Checklist

## Pre-Build Testing

### Environment Setup
- [ ] Windows 10 (build 17763+) or Windows 11
- [ ] Python 3.11+ installed
- [ ] Git installed
- [ ] Repository cloned

### Dependencies
- [ ] `pip install -r desktop/requirements.txt` runs successfully
- [ ] PyInstaller installed: `python -m PyInstaller --version`
- [ ] Pillow installed: `python -c "import PIL; print(PIL.__version__)"`

### Assets
- [ ] `openoutreach/desktop/assets/icon.png` exists (512x512)
- [ ] `openoutreach/desktop/assets/icon.ico` exists (Windows icon)
- [ ] Icon generator works: `cd openoutreach/desktop/assets && python generate_icon.py`

## Build Testing

### Basic Build
- [ ] `python desktop/build.py` completes without errors
- [ ] `desktop/dist/OpenOutreach.exe` created
- [ ] File size is 20-30MB
- [ ] Exe has version info (right-click → Properties → Details)

### MSIX Build
- [ ] Windows SDK installed (makeappx.exe available)
- [ ] `python desktop/build.py --msix` completes
- [ ] `desktop/dist/OpenOutreach-{version}.msix` created
- [ ] MSIX opens with App Installer (double-click)

### NSIS Installer Build
- [ ] NSIS installed: `where makensis` or `choco install nsis`
- [ ] `python desktop/build.py --installer` completes
- [ ] `desktop/dist/OpenOutreach-{version}-Setup.exe` created
- [ ] Installer runs without errors

### All Formats
- [ ] `python desktop/build.py --all` builds all three formats
- [ ] All artifacts present in `desktop/dist/`

### Clean Build
- [ ] `python desktop/build.py --clean` removes build/dist directories
- [ ] Rebuild succeeds after clean

## Functional Testing - Standalone .exe

### Launch
- [ ] Double-click `OpenOutreach.exe`
- [ ] SmartScreen appears (if unsigned)
- [ ] "More info" → "Run anyway" works
- [ ] Application launches
- [ ] System tray icon appears

### Authentication
- [ ] "Login to OpenOutreach" menu item visible
- [ ] Click opens browser to login page
- [ ] URL includes `?desktop=true&callback=openoutreach://auth`
- [ ] Login flow completes
- [ ] Callback redirects to `openoutreach://` (if protocol registered)
- [ ] App receives auth token
- [ ] Menu changes to show "Status: Running"

### Menu Items
- [ ] Status displays correctly
- [ ] "Start Automation" / "Stop Automation" toggle works
- [ ] "Open Dashboard" opens web browser
- [ ] "Logout" clears credentials
- [ ] "Quit" exits application

### Daemon Operation
- [ ] Daemon starts successfully
- [ ] Browser detection works (Chrome/Edge)
- [ ] Browser launches (if credentials configured)
- [ ] Heartbeat sends to backend
- [ ] Tasks claimed and executed

### Credential Storage
- [ ] Credentials stored in Windows Credential Manager
- [ ] Check: Control Panel → Credential Manager → Windows Credentials → "OpenOutreach"
- [ ] Logout removes credentials

### Data Persistence
- [ ] Config saved to `%APPDATA%\Local\OpenOutreach\config.json`
- [ ] Daemon ID saved to `%APPDATA%\Local\OpenOutreach\daemon_id`
- [ ] Browser data saved to `%APPDATA%\Local\OpenOutreach\browser_data\`
- [ ] Data persists across app restarts

## Functional Testing - NSIS Installer

### Installation
- [ ] Run `OpenOutreach-{version}-Setup.exe`
- [ ] SmartScreen appears (if unsigned)
- [ ] Installer launches
- [ ] Select installation directory (default: `C:\Program Files\OpenOutreach`)
- [ ] Installation completes
- [ ] Start Menu folder created: "OpenOutreach"
- [ ] Desktop shortcut created

### Installed Files
- [ ] Executable: `C:\Program Files\OpenOutreach\OpenOutreach.exe`
- [ ] Uninstaller: `C:\Program Files\OpenOutreach\Uninstall.exe`
- [ ] Start Menu shortcuts work
- [ ] Desktop shortcut works

### Protocol Handler
- [ ] Registry key exists: `HKEY_CLASSES_ROOT\openoutreach`
- [ ] Test URL: `start openoutreach://auth?token=test`
- [ ] App launches and receives URL

### Uninstallation
- [ ] Run Uninstaller from Start Menu
- [ ] Or: Settings → Apps → OpenOutreach → Uninstall
- [ ] All files removed from Program Files
- [ ] Start Menu shortcuts removed
- [ ] Desktop shortcut removed
- [ ] Registry keys remain (Windows behavior)
- [ ] AppData remains (user data preserved)

## Functional Testing - MSIX Package

### Prerequisites
- [ ] Developer Mode enabled: Settings → For developers → Developer mode
- [ ] Or: Enterprise environment with sideloading policy

### Installation
- [ ] Double-click `OpenOutreach-{version}.msix`
- [ ] App Installer opens
- [ ] Click "Install"
- [ ] Installation completes
- [ ] App appears in Start Menu

### MSIX Specifics
- [ ] App runs in sandboxed environment
- [ ] Data stored in app-specific location
- [ ] Protocol handler works

### Uninstallation
- [ ] Settings → Apps → OpenOutreach → Uninstall
- [ ] Or: PowerShell: `Remove-AppxPackage`
- [ ] App removed completely (including data)

## Protocol Handler Testing

### Manual Registration (Standalone Only)
- [ ] Registry file: `desktop/windows/register_protocol.reg`
- [ ] Edit paths to match installation
- [ ] Double-click to import
- [ ] Registry keys created

### Testing
- [ ] Command: `start openoutreach://auth?token=abc123`
- [ ] App launches (if not running)
- [ ] App receives callback
- [ ] Token parsed correctly

### Browser Integration
- [ ] Click `openoutreach://` link in browser
- [ ] Browser prompts to open OpenOutreach
- [ ] Allow and app launches
- [ ] Subsequent clicks open automatically

## Code Signing Testing (Optional)

### Setup
- [ ] Code signing certificate (.pfx) obtained
- [ ] Set environment: `$env:SIGN_CERT_PATH = "path\to\cert.pfx"`
- [ ] Set environment: `$env:SIGN_CERT_PASS = "password"`

### Signing
- [ ] Run: `.\desktop\windows\sign.ps1`
- [ ] Signature applied successfully
- [ ] Verify: `signtool verify /pa /v desktop\dist\OpenOutreach.exe`

### Results
- [ ] Right-click exe → Properties → Digital Signatures tab shows signature
- [ ] SmartScreen warning does NOT appear
- [ ] Exe runs without "More info" step

## CI/CD Testing

### GitHub Actions
- [ ] Workflow file valid: `.github/workflows/desktop-build.yml`
- [ ] Create tag: `git tag desktop-v1.0.0-test`
- [ ] Push tag: `git push origin desktop-v1.0.0-test`
- [ ] Workflow triggers automatically

### Build Job
- [ ] Windows build job starts
- [ ] Dependencies install successfully
- [ ] PyInstaller build completes
- [ ] MSIX creation succeeds (or skips gracefully)
- [ ] NSIS installation succeeds (via Chocolatey)

### Artifacts
- [ ] Three artifacts uploaded:
  - `OpenOutreach-Windows-{version}` (exe)
  - `OpenOutreach-Windows-MSIX-{version}` (msix)
  - `OpenOutreach-Windows-Installer-{version}` (setup.exe)

### Release
- [ ] Release created automatically
- [ ] Release notes generated
- [ ] All artifacts attached
- [ ] Release title: "OpenOutreach Desktop v{version}"

### Download & Test
- [ ] Download artifacts from release
- [ ] Test each format as above

## Performance Testing

### Resource Usage (Idle)
- [ ] CPU usage < 1%
- [ ] Memory usage < 50MB
- [ ] Check: Task Manager → Details → OpenOutreach.exe

### Resource Usage (Running)
- [ ] CPU usage < 5%
- [ ] Memory usage < 150MB
- [ ] No memory leaks over 1 hour

### Startup Time
- [ ] Launch time < 2 seconds
- [ ] Tray icon appears quickly

### Disk Usage
- [ ] Exe size: 20-30MB
- [ ] Installed size: < 50MB
- [ ] Browser data: ~200MB (grows over time)

## Security Testing

### SmartScreen
- [ ] Warning appears for unsigned builds
- [ ] Bypass works ("More info" → "Run anyway")
- [ ] No warning for signed builds

### Antivirus
- [ ] Windows Defender allows execution
- [ ] No false positives
- [ ] Add exception if blocked

### Credential Storage
- [ ] Credentials encrypted in Windows Credential Manager
- [ ] Not visible in plain text
- [ ] Accessible only to current user

### Network Security
- [ ] HTTPS connections to backend
- [ ] Certificate validation enabled
- [ ] No insecure connections

## Compatibility Testing

### Windows Versions
- [ ] Windows 10 (build 17763)
- [ ] Windows 10 (latest)
- [ ] Windows 11

### Browsers
- [ ] Chrome detected and launches
- [ ] Edge detected and launches
- [ ] Preference: Chrome > Edge

### System Configurations
- [ ] Standard user account (not admin)
- [ ] Admin account
- [ ] Enterprise environment
- [ ] Domain-joined machine

## Error Handling

### Missing Browser
- [ ] Error message if Chrome/Edge not installed
- [ ] Message directs user to install browser
- [ ] App doesn't crash

### Network Errors
- [ ] Graceful handling of API unavailable
- [ ] Retry logic works
- [ ] Error shown in tray menu

### Credential Errors
- [ ] Invalid credentials rejected
- [ ] Logout works
- [ ] Re-login prompts correctly

### Daemon Errors
- [ ] Daemon restarts on crash
- [ ] Errors logged appropriately
- [ ] User notified via tray

## Documentation Verification

### User Documentation
- [ ] `INSTALLATION.md` accurate and complete
- [ ] SmartScreen instructions clear
- [ ] Protocol registration steps work
- [ ] Troubleshooting section helpful

### Developer Documentation
- [ ] `BUILD_GUIDE.md` accurate
- [ ] Build commands work as documented
- [ ] Prerequisites list complete
- [ ] Troubleshooting covers common issues

### README Files
- [ ] `desktop/windows/README.md` accurate
- [ ] Quick start commands work
- [ ] Links to other docs valid

## Final Checks

### File Structure
- [ ] All files in correct locations
- [ ] No temporary files in dist
- [ ] No sensitive data in builds

### Version Numbers
- [ ] Version in `__version__.py` correct
- [ ] Version in exe properties matches
- [ ] Version in MSIX manifest matches
- [ ] Version in installer matches

### Cleanup
- [ ] Build artifacts can be cleaned
- [ ] Rebuild works after clean
- [ ] No leftover temporary files

## Sign-Off

### Checklist Summary
- Total items: ~180
- Completed: ___
- Failed: ___
- Skipped: ___

### Issues Found
List any issues discovered:
1. 
2. 
3. 

### Recommendation
- [ ] Ready for production
- [ ] Needs fixes (list above)
- [ ] Needs re-testing

### Tested By
- Name: _______________
- Date: _______________
- Environment: _______________

### Notes
Additional observations or comments:

