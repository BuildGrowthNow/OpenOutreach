from pathlib import Path


ROOT = Path(__file__).parents[2]
SPEC = ROOT / "desktop" / "openoutreach.spec"
DESKTOP_REQUIREMENTS = ROOT / "desktop" / "requirements.txt"
ENTRYPOINT = ROOT / "openoutreach" / "desktop" / "app.py"


def test_desktop_spec_excludes_server_database_modules():
    spec = SPEC.read_text(encoding="utf-8")
    hidden = spec.split("hiddenimports = [", 1)[1].split("]", 1)[0]
    excluded = spec.split("excludes = [", 1)[1].split("]", 1)[0]
    forbidden = ("pymongo", "motor", "beanie", "openoutreach.mongodb")

    assert all(module not in hidden for module in forbidden)
    assert all(module in excluded for module in forbidden)


def test_desktop_requirements_do_not_declare_database_drivers():
    requirements = DESKTOP_REQUIREMENTS.read_text(encoding="utf-8").lower()
    assert "pymongo" not in requirements
    assert "motor" not in requirements


def test_desktop_entrypoint_selects_secure_daemon_only():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "from openoutreach.desktop.secure_daemon import SecureRemoteDaemon as RemoteDaemon" in source
    assert "openoutreach.core.daemon_remote" not in source
    assert "openoutreach.core.remote_client" not in source
    assert "openoutreach.mongodb" not in source


def test_desktop_auth_logging_never_includes_tokens_or_callback_urls():
    app_source = ENTRYPOINT.read_text(encoding="utf-8")
    protocol_source = (
        ROOT / "openoutreach" / "desktop" / "protocol_handler.py"
    ).read_text(encoding="utf-8")

    assert 'logger.info("Opening window: %s", url)' not in app_source
    assert 'logger.info("Protocol callback received: %s", url[:80])' not in app_source
    assert 'logger.error("Failed to store credentials: %s", e)' not in protocol_source
    assert 'logger.error("Failed to parse auth callback: %s", e)' not in protocol_source


def test_desktop_restart_does_not_put_access_tokens_in_urls():
    app_source = ENTRYPOINT.read_text(encoding="utf-8")
    auth_store = (
        ROOT / "frontend" / "src" / "lib" / "authStoreV2.ts"
    ).read_text(encoding="utf-8")
    proxy = (ROOT / "frontend" / "src" / "proxy.ts").read_text(encoding="utf-8")

    assert "desktop_token" not in app_source
    assert "desktop_token" not in auth_store
    assert "desktop_token" not in proxy
    assert "?desktop=true" in app_source


def test_desktop_login_does_not_fallback_to_protocol_token_transport():
    login_page = (
        ROOT / "frontend" / "src" / "app" / "(auth)" / "login" / "page.tsx"
    ).read_text(encoding="utf-8")

    assert "encodeURIComponent(accessToken)" not in login_page
    assert "window.location.href = `${callback}" not in login_page
    assert "handle_lengrowth_url" not in login_page
    assert "store_auth_tokens" in login_page

    operator_docs = "\n".join(
        (
            ROOT / "desktop" / "windows" / name
        ).read_text(encoding="utf-8")
        for name in ("TEST_CHECKLIST.md", "BUILD_GUIDE.md")
    )
    assert "auth?token=" not in operator_docs

    admin_user_page = (
        ROOT / "frontend" / "src" / "app" / "(admin)" / "admin" / "users"
        / "[id]" / "page.tsx"
    ).read_text(encoding="utf-8")
    impersonation_page = (
        ROOT / "frontend" / "src" / "app" / "impersonate" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "impersonate?token" not in admin_user_page
    assert "postMessage({ type: 'lengrowth-impersonation-token', token }, origin)" in admin_user_page
    assert "event.origin !== origin" in admin_user_page
    assert "event.origin !== origin" in impersonation_page
