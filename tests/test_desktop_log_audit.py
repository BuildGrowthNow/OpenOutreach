import json
import subprocess
import sys

from scripts.audit_desktop_log import audit


def test_desktop_log_audit_reports_aggregates_without_content(tmp_path):
    path = tmp_path / "daemon.log"
    path.write_text(
        "callback lengrowth://auth?token=do-not-print\n"
        "normal line\n"
        "password field name only\n",
        encoding="utf-8",
    )

    result = audit(path)

    assert result["exists"] is True
    assert result["lines"] == 3
    assert result["callback_token_lines"] == 1
    assert result["sensitive_marker_lines"] == 1


def test_desktop_log_audit_cli_is_non_content_and_fails_on_callback(tmp_path):
    path = tmp_path / "daemon.log"
    path.write_text("lengrowth://auth?token=secret-value\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "scripts/audit_desktop_log.py", "--path", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "secret-value" not in completed.stdout
    report = json.loads(completed.stdout)
    assert report["callback_token_lines"] == 1
