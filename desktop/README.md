# OpenOutreach Desktop App

Production-ready desktop application for running LinkedIn automation locally using your residential IP and browser.

## Features

- **System tray icon** - Always accessible from taskbar/menu bar
- **Automatic browser detection** - Uses your Chrome, Edge, or Safari
- **Secure credential storage** - System keychain integration (Keyring)
- **Background daemon** - Executes tasks while you work
- **Active hours** - Respects your configured schedule
- **Cookie persistence** - Maintains LinkedIn session
- **Auto-updates** - Check for new releases
- **Protocol handler** - `openoutreach://` URL callbacks for login

## Requirements

See `desktop/requirements.txt`:
- Python 3.9+
- pystray (system tray)
- Pillow (icons)
- keyring (credential storage)
- httpx (API communication)
- pyinstaller (packaging)

## Development

```bash
# Install dependencies
pip install -r desktop/requirements.txt

# Run locally (needs token and profile ID)
python -m openoutreach.desktop.app

# Build executable
python desktop/build.py

# macOS: Build .dmg
python desktop/build.py --dmg
```

## Building

### macOS

```bash
python desktop/build.py --dmg
```

Output: `desktop/dist/OpenOutreach.dmg`

**First launch:** Users must right-click → Open (unsigned app)

### Windows

```bash
python desktop/build.py
```

Output: `desktop/dist/OpenOutreach.exe`

**MSIX packaging for Microsoft Store:**
```powershell
makeappx pack /d desktop\dist /p desktop\dist\OpenOutreach.msix
```

## Architecture

```
openoutreach/desktop/
├── __init__.py          # Module init
├── app.py               # Main tray application
├── config.py            # App configuration (API URL)
├── auth.py              # Auth manager (keychain)
├── protocol_handler.py  # URL callback handler
├── updater.py           # Auto-update checker
└── assets/
    ├── icon.png         # Tray icon
    └── generate_icon.py # Icon generator
```

## Usage Flow

1. **First launch**
   - App shows login menu item
   - Click "Login to OpenOutreach"
   - Browser opens to web app login
   - After login, redirects to `openoutreach://auth?token=xxx&profile_id=yyy`
   - Protocol handler stores credentials in system keychain

2. **Auto-start daemon**
   - On subsequent launches, daemon starts automatically
   - Tray icon turns green (running) or gray (stopped)
   - Daemon polls backend for tasks
   - Executes tasks using local browser
   - Syncs cookies after each task

3. **Control**
   - Start/Stop automation from tray menu
   - Open Dashboard opens web app
   - Logout clears stored credentials
   - Quit stops daemon and closes app

## Protocol Registration

**Windows:** Automatic on first launch via registry:
```
HKEY_CURRENT_USER\Software\Classes\openoutreach\shell\open\command
```

**macOS:** Handled by app bundle's `Info.plist`:
```xml
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLSchemes</key>
        <array><string>openoutreach</string></array>
    </dict>
</array>
```

## File Locations

**macOS:**
- Config: `~/Library/Application Support/OpenOutreach/config.json`
- Daemon ID: `~/Library/Application Support/OpenOutreach/daemon_id`
- Browser data: `~/Library/Application Support/OpenOutreach/browser_data/`
- Credentials: macOS Keychain

**Windows:**
- Config: `%LOCALAPPDATA%\OpenOutreach\config.json`
- Daemon ID: `%LOCALAPPDATA%\OpenOutreach\daemon_id`
- Browser data: `%LOCALAPPDATA%\OpenOutreach\browser_data\`
- Credentials: Windows Credential Manager

## Distribution

App size: ~20-30MB (no bundled browser)

**Free distribution:**
- macOS: Direct download (.dmg)
- Windows: Microsoft Store (free) or direct download (.exe)

**Optional signing:**
- macOS: Apple Developer account ($99/yr) for notarization
- Windows: Code signing certificate (~$200-500/yr) to remove SmartScreen
