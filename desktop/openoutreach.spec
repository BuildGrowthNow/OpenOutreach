# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Lengrowth Linkedin desktop app.

Output: ~20-30MB executable (no bundled browser)

Build commands:
    pyinstaller --clean --noconfirm desktop/openoutreach.spec
    python desktop/build.py
    python desktop/build.py --dmg  # macOS only
    python desktop/build.py --msix  # Windows only
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent
ASSETS_DIR = PROJECT_ROOT / "openoutreach" / "desktop" / "assets"

# Read version from source
version_file = PROJECT_ROOT / "openoutreach" / "desktop" / "__version__.py"
__version__ = "1.0.0"
if version_file.exists():
    with open(version_file) as f:
        for line in f:
            if line.startswith("__version__"):
                __version__ = line.split("=")[1].strip().strip('"\'')
                break

# Data files to include
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
datas = [
    (str(ASSETS_DIR), "openoutreach/desktop/assets"),
    (str(PROJECT_ROOT / "linkedin_cli"), "linkedin_cli"),
    (str(PROJECT_ROOT / "openoutreach"), "openoutreach"),
]
# Include playwright_stealth JS files (read at runtime via pathlib)
datas += collect_data_files("playwright_stealth")
# genai_prices reads its own version via importlib.metadata at import time;
# include dist-info so it doesn't raise PackageNotFoundError in the frozen exe.
datas += copy_metadata("genai_prices")

# Platform-specific hidden imports
hiddenimports = [
    "keyring.backends.Windows" if sys.platform == "win32" else "keyring.backends.macOS",
    "pystray._win32" if sys.platform == "win32" else "pystray._darwin",
    "PIL._tkinter_finder",
    "zoneinfo",
    # Desktop app modules
    "openoutreach.desktop.__version__",
    "openoutreach.desktop.app",
    "openoutreach.desktop.auth",
    "openoutreach.desktop.config",
    "openoutreach.desktop.updater",
    "openoutreach.desktop.protocol_handler",
    # Daemon core
    "openoutreach.core.daemon_remote",
    "openoutreach.core.remote_client",
    "openoutreach.core.browser_detect",
    "openoutreach.core.scheduler",
    "openoutreach.core.models",
    "openoutreach.core.conf",
    # LinkedIn automation (runs locally on user's browser)
    "linkedin_cli",
    "linkedin_cli.auth",
    "linkedin_cli.conf",
    "linkedin_cli.actions",
    "linkedin_cli.actions.search",
    "linkedin_cli.actions.connect",
    "linkedin_cli.browser",
    "linkedin_cli.exceptions",
    "playwright",
    "playwright.sync_api",
    "playwright_stealth",
    # MongoDB (task queue, rate limiting)
    "pymongo",
    "pymongo.errors",
    "bson",
    # OpenOutreach models
    "openoutreach.mongodb",
    "openoutreach.mongodb.connection",
    "openoutreach.mongodb.models",
    "openoutreach.mongodb.models_extended",
    "openoutreach.linkedin.models",
    "openoutreach.linkedin.tasks",
    "openoutreach.linkedin.tasks.connect",
    "openoutreach.linkedin.tasks.check_pending",
    "openoutreach.linkedin.tasks.follow_up",
    "openoutreach.linkedin.tasks.send_manual_message",
    "openoutreach.linkedin.pipeline",
    "openoutreach.linkedin.pipeline.search",
    "openoutreach.linkedin.pipeline.search_keywords",
    "openoutreach.linkedin.pipeline.qualify",
    "openoutreach.linkedin.pipeline.pools",
    "openoutreach.linkedin.db",
    "openoutreach.linkedin.ml",
    "openoutreach.crm",
    "openoutreach.crm.models",
    "openoutreach.crm.models.deal",
    # HTTP / networking
    "httpx",
    "httpx._transports",
    "httpx._transports.default",
    "httpcore",
    "h11",
    "certifi",
    "idna",
    "sniffio",
    "anyio",
    "anyio._backends",
    "anyio._backends._asyncio",
    # pywebview
    "webview",
    "webview.platforms.winforms" if sys.platform == "win32" else "webview.platforms.cocoa",
    "clr",
    "pythonnet",
    # LLM (for keyword generation)
    "pydantic_ai",
    "jinja2",
]

# Packages to completely exclude (heavy/unused in desktop context)
excludes = [
    "matplotlib",
    "pandas",
    "scipy",
    "tensorflow",
    "torch",
    "tkinter",
    "cv2",
    "IPython",
    "jupyter",
    "notebook",
    "sphinx",
    "pytest",
    "black",
    "ruff",
    "mypy",
    "pyright",
    "motor",
    "beanie",
    "uvicorn",
    "fastapi",
    "starlette",
]

a = Analysis(
    [str(PROJECT_ROOT / "openoutreach" / "desktop" / "app.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Windows-specific version info
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    version_parts = [int(x) for x in __version__.split(".")[:3]]
    while len(version_parts) < 4:
        version_parts.append(0)

    version_info = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=tuple(version_parts),
            prodvers=tuple(version_parts),
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "Lengrowth"),
                            StringStruct("FileDescription", "Lengrowth Linkedin Desktop"),
                            StringStruct("FileVersion", __version__),
                            StringStruct("InternalName", "Lengrowth"),
                            StringStruct("LegalCopyright", "Copyright Lengrowth"),
                            StringStruct("OriginalFilename", "Lengrowth.exe"),
                            StringStruct("ProductName", "Lengrowth Linkedin"),
                            StringStruct("ProductVersion", __version__),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )
else:
    version_info = None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Lengrowth",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS_DIR / "icon.ico") if sys.platform == "win32" else None,
    version=version_info,
)

# macOS app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Lengrowth.app",
        icon=str(ASSETS_DIR / "icon.icns"),
        bundle_identifier="io.lengrowth.linkedin",
        info_plist={
            "CFBundleDisplayName": "Lengrowth Linkedin",
            "CFBundleName": "Lengrowth",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "CFBundlePackageType": "APPL",
            "CFBundleSignature": "????",
            "NSHighResolutionCapable": True,
            "NSSupportsAutomaticGraphicsSwitching": True,
            "LSBackgroundOnly": False,
            "LSUIElement": False,
            "LSMinimumSystemVersion": "10.15.0",
            "NSRequiresAquaSystemAppearance": False,
            "CFBundleURLTypes": [
                {
                    "CFBundleURLSchemes": ["lengrowth"],
                    "CFBundleURLName": "Lengrowth Auth",
                    "CFBundleTypeRole": "Viewer",
                }
            ],
        },
    )
