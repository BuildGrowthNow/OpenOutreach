"""Desktop tray + webview application.

Opens outreach.lengrowth.com in a native window (pywebview) on launch.
Tray icon controls the automation daemon and lets the user show/hide the window.
"""

import asyncio
import ctypes
import logging
import sys
import threading
from pathlib import Path
from typing import Optional

import pystray
import webview
from PIL import Image, ImageDraw
from pystray import MenuItem as Item

from openoutreach.core.daemon_remote import RemoteDaemon
from openoutreach.desktop.__version__ import __version__
from openoutreach.desktop.auth import AuthManager
from openoutreach.desktop.config import AppConfig
from openoutreach.desktop.protocol_handler import (
    handle_protocol_url,
    register_protocol_handler,
)
from openoutreach.desktop.updater import (
    apply_update_windows,
    can_auto_update,
    check_for_updates,
    clear_pending_update,
    download_update,
    load_pending_update,
    prompt_update,
    save_pending_update,
)

logger = logging.getLogger(__name__)

_AUTOSTART_NAME = "LengrowthOutreach"
_MACOS_LAUNCHAGENT_LABEL = "io.lengrowth.outreach"

_WINDOW_TITLE = "Lengrowth"
_WINDOW_W = 1480
_WINDOW_H = 1020

# Injected into every page load:
# 1. Sets window.__LENGROWTH_DESKTOP__ so the frontend badge persists across navigation
# 2. Intercepts window.location.href = 'lengrowth://...' so the auth callback is
#    handled by Python instead of causing a failed navigation inside the webview
_INJECT_JS = """
(function() {
    window.__LENGROWTH_DESKTOP__ = true;

    var _origDesc = Object.getOwnPropertyDescriptor(Location.prototype, 'href');
    if (_origDesc && _origDesc.set) {
        Object.defineProperty(Location.prototype, 'href', {
            get: _origDesc.get,
            set: function(url) {
                if (typeof url === 'string' && url.indexOf('lengrowth://') === 0) {
                    var _poll = function(tries) {
                        if (window.pywebview && window.pywebview.api) {
                            window.pywebview.api.handle_lengrowth_url(url);
                        } else if (tries > 0) {
                            setTimeout(function() { _poll(tries - 1); }, 50);
                        }
                    };
                    _poll(20);
                    return;
                }
                _origDesc.set.call(this, url);
            },
            configurable: true,
            enumerable: true
        });
    }
})();
"""


# ---------------------------------------------------------------------------
# Auto-start helpers
# ---------------------------------------------------------------------------

def _register_autostart() -> None:
    if sys.platform == "win32":
        _autostart_windows(enable=True)
    elif sys.platform == "darwin":
        _autostart_macos(enable=True)


def _unregister_autostart() -> None:
    if sys.platform == "win32":
        _autostart_windows(enable=False)
    elif sys.platform == "darwin":
        _autostart_macos(enable=False)


def _autostart_windows(enable: bool) -> None:
    import winreg
    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
            else:
                try:
                    winreg.DeleteValue(key, _AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
    except Exception as e:
        logger.warning("Auto-start (Windows) failed: %s", e)


def _autostart_macos(enable: bool) -> None:
    plist_path = (
        Path.home() / "Library" / "LaunchAgents" / f"{_MACOS_LAUNCHAGENT_LABEL}.plist"
    )
    if enable:
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{_MACOS_LAUNCHAGENT_LABEL}</string>
    <key>ProgramArguments</key><array><string>{sys.executable}</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><false/>
</dict>
</plist>"""
        try:
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            plist_path.write_text(plist)
        except Exception as e:
            logger.warning("Auto-start (macOS) failed: %s", e)
    else:
        try:
            plist_path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("Auto-start removal (macOS) failed: %s", e)


# ---------------------------------------------------------------------------
# Single-instance lock
# ---------------------------------------------------------------------------

_IPC_PIPE_NAME = r"\\.\pipe\LengrowthOutreach" if sys.platform == "win32" else str(Path.home() / ".lengrowth" / "ipc.sock")


def _acquire_single_instance_lock():
    if sys.platform == "win32":
        handle = ctypes.windll.kernel32.CreateMutexW(None, True, "LengrowthOutreachSingleInstance")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return None
        return handle
    else:
        import fcntl
        lock_path = Path.home() / ".lengrowth" / "app.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock_path, "w")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except OSError:
            fh.close()
            return None


def _ipc_send(url: str) -> None:
    """Forward a protocol URL to the already-running instance via IPC."""
    try:
        if sys.platform == "win32":
            import win32file  # type: ignore[import]
            handle = win32file.CreateFile(
                _IPC_PIPE_NAME,
                win32file.GENERIC_WRITE,
                0, None,
                win32file.OPEN_EXISTING,
                0, None,
            )
            win32file.WriteFile(handle, url.encode())
            win32file.CloseHandle(handle)
        else:
            import socket as _socket
            sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            sock.connect(_IPC_PIPE_NAME)
            sock.sendall(url.encode())
            sock.close()
    except Exception as e:
        logger.warning("IPC send failed: %s", e)


def _ipc_listen(callback) -> threading.Thread:
    """Start a background thread that waits for protocol URLs from new instances."""

    def _serve():
        if sys.platform == "win32":
            import pywintypes  # type: ignore[import]
            import win32pipe  # type: ignore[import]
            import win32file  # type: ignore[import]
            while True:
                try:
                    pipe = win32pipe.CreateNamedPipe(
                        _IPC_PIPE_NAME,
                        win32pipe.PIPE_ACCESS_INBOUND,
                        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                        1, 65536, 65536, 0, None,
                    )
                    win32pipe.ConnectNamedPipe(pipe, None)
                    _, data = win32file.ReadFile(pipe, 65536)
                    win32file.CloseHandle(pipe)
                    url = data.decode(errors="replace").strip()
                    if url:
                        callback(url)
                except pywintypes.error:
                    break
                except Exception as e:
                    logger.warning("IPC listen error: %s", e)
        else:
            import socket as _socket
            sock_path = Path(_IPC_PIPE_NAME)
            sock_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                sock_path.unlink()
            except FileNotFoundError:
                pass
            server = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            server.bind(str(sock_path))
            server.listen(1)
            while True:
                try:
                    conn, _ = server.accept()
                    data = conn.recv(65536)
                    conn.close()
                    url = data.decode(errors="replace").strip()
                    if url:
                        callback(url)
                except Exception as e:
                    logger.warning("IPC listen error: %s", e)

    t = threading.Thread(target=_serve, daemon=True, name="ipc-listener")
    t.start()
    return t


# ---------------------------------------------------------------------------
# TrayApp
# ---------------------------------------------------------------------------

class DesktopAPI:
    """Python API exposed to the webview via window.pywebview.api.*"""

    def __init__(self, app: "TrayApp"):
        self._app = app

    def handle_lengrowth_url(self, url: str) -> None:
        """Called by JS when window.location.href is set to lengrowth://..."""
        logger.info("Protocol callback received: %s", url[:80])
        if handle_protocol_url(url, self._app.auth):
            self._app._update_menu()
            self._app._pending_login_notification = False
            if self._app.icon:
                self._app.icon.notify("Login successful", "Lengrowth is ready")
            if self._app.auth.is_logged_in():
                self._app._start_daemon()

    def confirm_auth(self, user_id: str) -> None:
        """Called by the frontend after successful initialize() to signal the daemon can start."""
        logger.info("Frontend confirmed auth for user: %s", user_id)
        if not self._app._is_running():
            self._app._start_daemon()

    def get_keychain_refresh_token(self) -> Optional[str]:
        """Return the stored refresh token so the frontend can re-authenticate after restart."""
        return self._app.auth.get_refresh_token()


class TrayApp:
    def __init__(self):
        self.config = AppConfig.load()
        self.auth = AuthManager(self.config)
        self.daemon: Optional[RemoteDaemon] = None
        self.daemon_thread: Optional[threading.Thread] = None
        self.icon: Optional[pystray.Icon] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stopping = False
        self._pending_update: Optional[dict] = None
        self._update_check_thread: Optional[threading.Thread] = None
        self._pending_login_notification = False
        self._window: Optional[webview.Window] = None
        self._window_thread: Optional[threading.Thread] = None
        self._token_valid: Optional[bool] = None  # None = not yet checked

    # ------------------------------------------------------------------
    # Icon helpers
    # ------------------------------------------------------------------

    def _create_icon(self) -> Image.Image:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent.parent))
        icon_path = base / "openoutreach" / "desktop" / "assets" / "icon.png"
        if not icon_path.exists():
            icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception as e:
                logger.warning("Failed to load icon: %s", e)
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        color = (34, 197, 94) if self._is_running() else (156, 163, 175)
        draw.ellipse([8, 8, 56, 56], fill=color)
        return img

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def _platform_url(self) -> str:
        url = self.config.api_url
        if "outreach-api." in url:
            return url.replace("outreach-api.", "outreach.")
        if "linkedin-api." in url:
            return url.replace("linkedin-api.", "linkedin.")
        return url

    def _app_url(self, path: str = "") -> str:
        base = self._platform_url().rstrip("/")
        suffix = f"/{path.lstrip('/')}" if path else ""
        return f"{base}{suffix}"

    # ------------------------------------------------------------------
    # Tray menu
    # ------------------------------------------------------------------

    def _create_menu(self) -> pystray.Menu:
        daemon_label = "Stop Automation" if self._is_running() else "Start Automation"
        status_label = f"Status: {'Running ●' if self._is_running() else 'Stopped ○'}"
        autostart_label = "Start on Login ✓" if self.config.autostart else "Start on Login"

        items = [
            Item(f"Lengrowth v{__version__}", None, enabled=False),
            Item(status_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
            Item("Open Lengrowth", self._on_show_window),
            pystray.Menu.SEPARATOR,
            Item(daemon_label, self._on_toggle_daemon, enabled=self.auth.is_logged_in()),
            Item(autostart_label, self._on_toggle_autostart),
        ]

        if self._pending_update:
            ver = self._pending_update["version"]
            # If we have a downloaded exe on disk, offer restart; otherwise offer download
            pending = load_pending_update()
            if pending and pending.get("version") == ver:
                label = f"↑ Restart to update v{ver}"
                action = self._on_apply_update
            else:
                label = f"Update Available: v{ver}"
                action = self._on_download_update
            items.extend([
                pystray.Menu.SEPARATOR,
                Item(label, action),
            ])

        items.extend([
            pystray.Menu.SEPARATOR,
            Item("Check for Updates", self._on_check_for_updates),
            Item("Quit", self._on_quit),
        ])

        return pystray.Menu(*items)

    def _update_menu(self):
        if self.icon:
            self.icon.menu = self._create_menu()
            self.icon.icon = self._create_icon()

    # ------------------------------------------------------------------
    # Window
    # ------------------------------------------------------------------

    def _start_window(self):
        """Create and show the pywebview window. Blocks until the window closes."""
        if self.auth.is_logged_in() and self._token_valid is not False:
            token = self.auth.get_token()
            url = (self._app_url("dashboard") + f"?desktop_token={token}") if token else self._app_url("dashboard")
        else:
            url = self._app_url("login") + "?desktop=true&callback=lengrowth%3A%2F%2Fauth"
        logger.info("Opening window: %s", url)

        api = DesktopAPI(self)

        win = webview.create_window(
            title=_WINDOW_TITLE,
            url=url,
            width=_WINDOW_W,
            height=_WINDOW_H,
            min_size=(800, 600),
            resizable=True,
            on_top=False,
            background_color="#09090b",  # zinc-950 matches the dark theme
            js_api=api,
        )
        self._window = win
        assert win is not None
        win.events.closed += self._on_window_closed
        win.events.loaded += self._on_loaded

        # Persist WebView2/WKWebView profile across restarts so the HTTP-only
        # refresh_token cookie survives.  Without a fixed path, Edge WebView2 on
        # Windows uses a per-process temp dir that is wiped on exit.
        if sys.platform == "win32":
            _wv_data = Path.home() / "AppData" / "Local" / "Lengrowth" / "WebView2"
        elif sys.platform == "darwin":
            _wv_data = Path.home() / "Library" / "Application Support" / "Lengrowth" / "WebView2"
        else:
            _wv_data = Path.home() / ".lengrowth" / "webview2"
        _wv_data.mkdir(parents=True, exist_ok=True)

        # pywebview.start() is blocking - run in current thread
        # user_data_path was added in pywebview 5.x; guard for frozen builds on 4.x
        _wv_ver = getattr(webview, "__version__", "4.0")
        _wv_major = int(str(_wv_ver).split(".")[0])
        if _wv_major >= 5:
            webview.start(debug=False, user_data_path=str(_wv_data))  # type: ignore[call-arg]
        else:
            webview.start(debug=False)  # type: ignore[call-arg]

    def _on_loaded(self):
        """Called after each page navigation - re-inject the desktop globals."""
        if self._window:
            try:
                self._window.evaluate_js(_INJECT_JS)
            except Exception as e:
                logger.debug("JS inject failed: %s", e)

    def _on_window_closed(self):
        """Called when the user closes the window - hide it, don't quit."""
        self._window = None
        logger.info("Window closed")

    def _on_show_window(self):
        """Show or restore the main window."""
        if self._window is not None:
            try:
                self._window.show()
                return
            except Exception:
                pass

        # Window was closed - open a new one in a background thread so the tray
        # keeps running.  Guard with _window_thread so we never call
        # webview.start() twice concurrently (pywebview doesn't support that).
        if self._window_thread is not None and self._window_thread.is_alive():
            return
        self._window_thread = threading.Thread(target=self._start_window, daemon=True, name="webview-window")
        self._window_thread.start()

    # ------------------------------------------------------------------
    # Tray callbacks
    # ------------------------------------------------------------------

    def _on_quit(self):
        self._stopping = True
        self._stop_daemon()
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
        if self.icon:
            self.icon.stop()

    def _on_toggle_daemon(self):
        if self._is_running():
            self._stop_daemon()
        else:
            self._start_daemon()
        self._update_menu()

    def _on_check_for_updates(self):
        """Tray: manually trigger an update check and download."""
        self._start_background_update_check()

    def _on_download_update(self):
        if self._pending_update:
            prompt_update(self._pending_update)

    def _on_apply_update(self):
        """Tray: apply a previously downloaded update - replace exe and restart."""
        if not can_auto_update():
            if self._pending_update:
                prompt_update(self._pending_update)
            return
        pending = load_pending_update()
        if pending:
            exe_path = pending.get("exe_path", "")
            download_url = pending.get("download_url", "")
            if exe_path and Path(exe_path).exists():
                self._stopping = True
                self._stop_daemon()
                if self._window:
                    try:
                        self._window.destroy()
                    except Exception:
                        pass
                # apply_update_windows calls os._exit - never returns
                apply_update_windows(exe_path, download_url=download_url)
                return
        # exe gone - fall back to browser download
        if self._pending_update:
            prompt_update(self._pending_update)

    def _on_toggle_autostart(self):
        self.config.autostart = not self.config.autostart
        self.config.save()
        if self.config.autostart:
            _register_autostart()
        else:
            _unregister_autostart()
        self._update_menu()

    # ------------------------------------------------------------------
    # Tray setup
    # ------------------------------------------------------------------

    def _on_setup(self, icon):
        icon.visible = True

        if self._pending_login_notification:
            self._pending_login_notification = False
            icon.notify("Login successful", "Lengrowth is ready")

        # Daemon start is deferred until the frontend calls confirm_auth() after
        # successful login/initialize - avoids starting with stale credentials if
        # the user switches accounts.

        if self.config.autostart:
            _register_autostart()
        else:
            _unregister_autostart()
        self._start_periodic_update_checker()

    # ------------------------------------------------------------------
    # Daemon
    # ------------------------------------------------------------------

    def _is_running(self) -> bool:
        return (
            self.daemon is not None
            and self.daemon.running
            and self.daemon_thread is not None
            and self.daemon_thread.is_alive()
        )

    def _start_daemon(self):
        if self._is_running():
            return
        if not self.auth.is_logged_in():
            return

        token = self.auth.get_token()
        refresh_token = self.auth.get_refresh_token()

        if not token:
            return

        # Always resolve fresh profile_id so a credential delete+recreate doesn't
        # leave a stale ID in the keychain causing 404s on every daemon start.
        # _resolve_profile_id may refresh the token internally on 401 - re-read
        # token afterwards so the daemon gets the latest one.
        resolved = self._resolve_profile_id(token)
        token = self.auth.get_token() or token  # pick up refreshed token if any
        if resolved:
            cached = self.auth.get_profile_id()
            if resolved != cached:
                logger.info("Profile ID changed (%s → %s), updating keychain", cached, resolved)
                self.auth.login(token, resolved, refresh_token=refresh_token)
            profile_id = resolved
        else:
            # API unreachable - fall back to keychain so we can still start offline
            profile_id = self.auth.get_profile_id()

        if not profile_id:
            logger.error("No outreach profile found")
            if self.icon:
                self.icon.notify("No Profile Found", "Add a LinkedIn or WhatsApp profile in the dashboard first.")
            return

        def on_token_refresh(new_token: str):
            self.auth.update_token(new_token)

        def run_daemon():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            def on_started():
                # Fires from inside the async start() after subscription check passes
                self._update_menu()

            self.daemon = RemoteDaemon(
                api_url=self.config.api_url,
                token=token,
                linkedin_profile_id=profile_id,
                refresh_token=refresh_token,
                on_token_refresh=on_token_refresh,
                on_started=on_started,
            )
            try:
                self._loop.run_until_complete(self.daemon.start())
            except KeyboardInterrupt:
                pass
            except Exception as e:
                from openoutreach.core.daemon_remote import BrowserNotFoundError
                logger.exception("Daemon error: %s", e)
                msg = "No supported browser found." if isinstance(e, BrowserNotFoundError) else "Daemon error - check logs."
                if self.icon:
                    self.icon.notify("Daemon Error", msg)
            finally:
                self._loop.close()
                self._loop = None
                # Clear daemon reference so _is_running() returns False and any
                # held browser/session resources are released for GC.
                self.daemon = None
                self.daemon_thread = None
                # Update menu so tray shows "Stopped"
                self._update_menu()

        self.daemon_thread = threading.Thread(target=run_daemon, daemon=True)
        self.daemon_thread.start()

    def _try_refresh_token(self, refresh_token: str) -> Optional[str]:
        """Exchange a refresh token for a new access token. Returns new token or None."""
        import json
        import urllib.error
        import urllib.request
        try:
            body = json.dumps({"refresh_token": refresh_token}).encode()
            req = urllib.request.Request(
                f"{self.config.api_url.rstrip('/')}/api/auth/refresh/",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                new_token = data.get("access_token")
                if new_token:
                    logger.info("Access token refreshed at startup")
                    self.auth.update_token(new_token)
                    return new_token
        except urllib.error.HTTPError as e:
            if e.code == 401:
                logger.warning("Startup token refresh failed: refresh token expired")
                # Clear the dead credentials so next startup goes straight to login
                self.auth.logout()
                self._token_valid = False
            else:
                logger.warning("Startup token refresh failed: HTTP Error %d: %s", e.code, e.reason)
        except Exception as e:
            logger.warning("Startup token refresh failed: %s", e)
        return None

    def _resolve_profile_id(self, token: str) -> Optional[str]:
        import json
        import urllib.error
        import urllib.request

        def _fetch(t: str) -> Optional[str]:
            req = urllib.request.Request(
                f"{self.config.api_url.rstrip('/')}/api/linkedin-profiles",
                headers={"Authorization": f"Bearer {t}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                profiles = data if isinstance(data, list) else data.get("profiles", [])
                if profiles:
                    pid = profiles[0].get("id") or profiles[0].get("_id")
                    return str(pid) if pid else None
            return None

        try:
            return _fetch(token)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                # Token expired - try refreshing before giving up
                refresh_token = self.auth.get_refresh_token()
                if refresh_token:
                    new_token = self._try_refresh_token(refresh_token)
                    if new_token:
                        try:
                            return _fetch(new_token)
                        except Exception as e2:
                            logger.error("Failed to resolve profile_id after refresh: %s", e2)
                logger.error("Failed to resolve profile_id: token expired and refresh unavailable")
                self._token_valid = False
            else:
                logger.error("Failed to resolve profile_id: %s", e)
        except Exception as e:
            logger.error("Failed to resolve profile_id: %s", e)
        return None

    def _stop_daemon(self):
        if not self._is_running():
            return
        loop = self._loop
        daemon = self.daemon
        thread = self.daemon_thread
        if loop and daemon:
            try:
                asyncio.run_coroutine_threadsafe(daemon.stop(), loop).result(timeout=10)
            except Exception as e:
                logger.warning("Error stopping daemon: %s", e)
        # run_daemon's finally block clears self.daemon/self.daemon_thread after the
        # loop exits.  Join the thread directly so we don't race on the attribute.
        if thread and thread.is_alive():
            thread.join(timeout=5)
        self.daemon = None
        self.daemon_thread = None
        self._update_menu()

    # ------------------------------------------------------------------
    # Update checker
    # ------------------------------------------------------------------

    def _run_startup_update_check(self) -> None:
        """Force-apply a pending update if one was downloaded during a previous session.

        On Windows frozen exe: if a pending update exe is on disk, apply it immediately
        (PowerShell replace + restart) before the window opens.
        If no pending update exists, start the background checker - the app opens normally
        and the download happens silently in the background.
        """
        # Phase 1: apply any previously downloaded update
        if can_auto_update():
            pending = load_pending_update()
            if pending:
                exe_path = pending.get("exe_path", "")
                ver = pending.get("version", "?")
                try:
                    from packaging import version as _v
                    is_upgrade = _v.parse(ver) > _v.parse(__version__)
                except Exception:
                    is_upgrade = False
                if not is_upgrade:
                    # Pending is same or older than running version - discard
                    logger.info("Discarding stale pending_update.json (pending v%s <= running v%s)", ver, __version__)
                    clear_pending_update()
                else:
                    logger.info("Applying previously downloaded update v%s from %s", ver, exe_path)
                    download_url = pending.get("download_url", "")
                    apply_update_windows(exe_path, download_url=download_url)
                    # apply_update_windows calls os._exit - never reaches here

        # Phase 2: non-blocking background download (app opens immediately)
        self._start_background_update_check()

    def _start_background_update_check(self) -> None:
        """Start a one-shot background thread that checks for and silently downloads an update.

        On Windows frozen exe: downloads silently, saves to disk, shows OS toast.
        On other platforms: just checks and stores info for the tray notification.
        """
        async def _background():
            try:
                info = await check_for_updates()
                if not info:
                    return
                ver = info["version"]
                if can_auto_update():
                    logger.info("Update v%s available - downloading in background", ver)
                    path = await download_update(info["download_url"], version=ver)
                    if path:
                        save_pending_update(info, path)
                        self._pending_update = info
                        self._update_menu()
                        if self.icon:
                            self.icon.notify(
                                f"Lengrowth v{ver} ready to install",
                                "Click 'Restart to update' in the tray menu.",
                            )
                    else:
                        self._pending_update = info
                        self._update_menu()
                else:
                    self._pending_update = info
                    self._update_menu()
            except Exception as e:
                logger.warning("Background update check failed: %s", e)

        def run():
            lp = asyncio.new_event_loop()
            asyncio.set_event_loop(lp)
            try:
                lp.run_until_complete(_background())
            finally:
                lp.close()

        t = threading.Thread(target=run, daemon=True)
        t.start()

    def _start_periodic_update_checker(self):
        """Start the background 6-hour update poll (called from tray setup)."""
        if self._update_check_thread and self._update_check_thread.is_alive():
            return

        async def periodic_loop():
            while not self._stopping:
                await asyncio.sleep(3600 * 6)
                if self._stopping:
                    break
                try:
                    info = await check_for_updates()
                    if info and not self._pending_update:
                        ver = info["version"]
                        if can_auto_update():
                            logger.info("Periodic check: update v%s available - downloading in background", ver)
                            path = await download_update(info["download_url"], version=ver)
                            if path:
                                save_pending_update(info, path)
                                self._pending_update = info
                                self._update_menu()
                                if self.icon:
                                    self.icon.notify(
                                        f"Lengrowth v{ver} ready to install",
                                        "Click 'Restart to update' in the tray menu.",
                                    )
                            else:
                                self._pending_update = info
                                self._update_menu()
                                if self.icon:
                                    self.icon.notify(f"Update Available: v{ver}", "Click the tray icon to download")
                        else:
                            self._pending_update = info
                            self._update_menu()
                            if self.icon:
                                self.icon.notify(f"Update Available: v{ver}", "Click the tray icon to download")
                except Exception as e:
                    logger.warning("Periodic update check failed: %s", e)

        def run():
            lp = asyncio.new_event_loop()
            asyncio.set_event_loop(lp)
            try:
                lp.run_until_complete(periodic_loop())
            finally:
                lp.close()

        self._update_check_thread = threading.Thread(target=run, daemon=True)
        self._update_check_thread.start()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _on_ipc_url(self, url: str) -> None:
        """Handle a protocol URL forwarded from a second instance."""
        logger.info("IPC: received protocol URL from second instance")
        if handle_protocol_url(url, self.auth):
            self._token_valid = True
            self._update_menu()
            if self.icon:
                self.icon.notify("Login successful", "Lengrowth is ready")
            if not self._is_running():
                self._start_daemon()

    def run(self, pending_protocol_url: Optional[str] = None):
        # Handle protocol callback that arrived before the window existed
        if pending_protocol_url:
            if handle_protocol_url(pending_protocol_url, self.auth):
                self._pending_login_notification = True
                self._token_valid = True  # fresh login, token is definitely valid

        # Eagerly validate the stored token before opening the window so
        # _start_window knows whether to open /dashboard or /login.
        # This must run synchronously here - _on_setup fires in a background
        # thread (tray) and can race with _start_window otherwise.
        if self.auth.is_logged_in() and self._token_valid is None:
            refresh_token = self.auth.get_refresh_token()
            if refresh_token:
                new_token = self._try_refresh_token(refresh_token)
                if new_token:
                    self._token_valid = True
                # 401 path: _try_refresh_token already set _token_valid=False and cleared auth

        # Listen for protocol URLs forwarded from a second instance (e.g. login callback)
        _ipc_listen(lambda url: self._on_ipc_url(url))

        # Check for a previously-downloaded pending update (force-apply it) or
        # kick off a background download check.  On Windows this may call os._exit.
        self._run_startup_update_check()

        # Start tray icon in background thread (pystray owns its own loop)
        tray_icon = pystray.Icon(
            "Lengrowth",
            self._create_icon(),
            "Lengrowth",
            menu=self._create_menu(),
        )
        self.icon = tray_icon
        tray_thread = threading.Thread(
            target=lambda: tray_icon.run(setup=self._on_setup),
            daemon=True,
        )
        tray_thread.start()

        # Open the main window - this blocks until the app quits
        self._start_window()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    from openoutreach.desktop.config import AppConfig
    log_dir = AppConfig._config_path().parent
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon.log"

    import sys
    from logging.handlers import RotatingFileHandler

    handlers: list = [
        RotatingFileHandler(str(log_file), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"),
    ]
    # stdout is unavailable when running as a PyInstaller windowed (no-console) exe
    try:
        stream = open(1, "w", encoding="utf-8", closefd=False)
        handlers.append(logging.StreamHandler(stream=stream))
    except OSError:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info("Starting Lengrowth desktop app v%s", __version__)

    _lock = _acquire_single_instance_lock()
    if _lock is None:
        # Forward any protocol URL to the running instance before exiting
        if len(sys.argv) > 1 and sys.argv[1].startswith("lengrowth://"):
            logger.info("Forwarding protocol URL to running instance")
            _ipc_send(sys.argv[1])
        else:
            logger.info("Another instance is already running. Exiting.")
        sys.exit(0)

    register_protocol_handler()

    pending_protocol_url = None
    if len(sys.argv) > 1 and sys.argv[1].startswith("lengrowth://"):
        pending_protocol_url = sys.argv[1]

    app = TrayApp()
    try:
        app.run(pending_protocol_url=pending_protocol_url)
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
