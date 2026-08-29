# OpenOutreach Desktop App

Secure-v2 desktop application for running supported outreach automation locally using your residential IP and browser.

## Features

- **System tray icon** - Always accessible from taskbar/menu bar
- **Automatic browser detection** - Uses your Chrome, Edge, or Safari
- **Secure credential storage** - System keychain integration (Keyring)
- **Background daemon** - Executes tasks while you work
- **Active hours** - Respects your configured schedule
- **Local browser persistence** - Maintains provider session state locally; no
  server cookies or database credentials are downloaded
- **Scoped desktop enrollment** - Select LinkedIn profiles, WhatsApp numbers,
  and mailboxes from Settings; revoke registered devices at any time
- **Auto-updates** - Check for new releases
- **Protocol handler** - `lengrowth://` URL callbacks for login

## Requirements

See `desktop/requirements.txt`:
- Python 3.9+
- pystray (system tray)
- Pillow (icons)
- keyring (credential storage)
- httpx (API communication)
- playwright and playwright-stealth (local browser execution)
- pyinstaller (packaging)

## Development

```bash
# Install dependencies
pip install -r desktop/requirements.txt

# Run locally after device enrollment (daemon tokens are held in the OS keychain)
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

Output: `desktop/dist/Lengrowth-2.1.2.dmg`

**First launch:** Users must right-click → Open (unsigned app)

### Windows

```bash
python desktop/build.py
```

Output: `desktop/dist/Lengrowth.exe`

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
   - Sign in to the web dashboard and choose **Connect this desktop**.
   - Select only the profiles and channels this device may operate.
   - Enter the one-time enrollment code in the desktop.
   - The desktop creates an OS-protected device key and stores only the
     rotating daemon refresh credential in the OS credential store.
   - Human login, browser challenges, and reauthentication happen interactively
     in the local browser; server passwords and cookies are never returned.

2. **Auto-start daemon**
   - On subsequent launches, daemon starts automatically
   - Tray icon turns green (running) or gray (stopped)
   - Daemon polls backend for tasks
   - Executes tasks using local browser
   - Submits bounded typed receipts after each task

3. **Control**
   - Start/Stop automation from tray menu
   - Open Dashboard opens web app
   - Logout clears stored credentials
   - Quit stops daemon and closes app

## Protocol Registration

**Windows:** Automatic on first launch via registry:
```
HKEY_CURRENT_USER\Software\Classes\lengrowth\shell\open\command
```

**macOS:** Handled by app bundle's `Info.plist`:
```xml
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLSchemes</key>
        <array><string>lengrowth</string></array>
    </dict>
</array>
```

## File Locations

**macOS:**
- Config: `~/Library/Application Support/OpenOutreach/config.json`
- Daemon ID: `~/Library/Application Support/OpenOutreach/daemon_id`
- Browser data: `~/Library/Application Support/OpenOutreach/browser_data/`
- Daemon credentials: macOS Keychain; browser state: local browser profile

**Windows:**
- Config: `%LOCALAPPDATA%\OpenOutreach\config.json`
- Daemon ID: `%LOCALAPPDATA%\OpenOutreach\daemon_id`
- Browser data: `%LOCALAPPDATA%\OpenOutreach\browser_data\`
- Daemon credentials: Windows Credential Manager; browser state: local browser profile

## Distribution

App size: approximately 102MB for the current Windows one-file build; browser
engines are not bundled and the user’s installed Chrome/Edge is used.

**Free distribution:**
- macOS: Direct download (.dmg)
- Windows: Microsoft Store (free) or direct download (.exe)

**Optional signing:**
- macOS: Apple Developer account ($99/yr) for notarization
- Windows: Code signing certificate (~$200-500/yr) to remove SmartScreen
