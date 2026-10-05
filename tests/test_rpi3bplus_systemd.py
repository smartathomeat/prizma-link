from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/rpi3bplus"


def test_weekly_restart_timer_uses_closed_hours_without_catch_up() -> None:
    timer = (DEPLOY / "prizma-link-weekly-restart.timer").read_text(encoding="utf-8")
    assert "OnCalendar=Sun *-*-* 03:30:00" in timer
    assert "Persistent=false" in timer
    assert "RandomizedDelaySec=0" in timer
    assert "Unit=prizma-link-weekly-restart.service" in timer
    assert "WantedBy=timers.target" in timer


def test_weekly_restart_only_restarts_bridge_service() -> None:
    service = (DEPLOY / "prizma-link-weekly-restart.service").read_text(encoding="utf-8")
    assert "Type=oneshot" in service
    assert "ExecStart=/usr/bin/systemctl try-restart prizma-link.service" in service
    assert "reboot" not in service.lower()
    assert "bluetooth.service" not in service


def test_installer_copies_but_does_not_enable_weekly_timer() -> None:
    installer = (DEPLOY / "install.sh").read_text(encoding="utf-8")
    assert 'install -m 0644 "$SCRIPT_DIR/prizma-link-weekly-restart.service"' in installer
    assert 'install -m 0644 "$SCRIPT_DIR/prizma-link-weekly-restart.timer"' in installer
    assert "systemctl disable --now prizma-link-weekly-restart.timer" in installer
    assert "enable --now prizma-link-weekly-restart.timer" not in installer
    assert '--require-hashes -r "$PROJECT_DIR/requirements.lock"' in installer
    assert "pip install --upgrade pip" not in installer
    assert 'install -m 0755 "$SCRIPT_DIR/prizma-link" /usr/local/bin/prizma-link' in installer


def test_rpi_service_uses_the_pinned_source_wrapper() -> None:
    service = (DEPLOY / "prizma-link.service").read_text(encoding="utf-8")
    wrapper = DEPLOY / "prizma-link"
    assert "ExecStart=/usr/local/bin/prizma-link run" in service
    assert wrapper.stat().st_mode & 0o111
    text = wrapper.read_text(encoding="utf-8")
    assert "PYTHONPATH=/opt/prizma-link/app/src" in text
    assert "python -m prizma_link.cli" in text
