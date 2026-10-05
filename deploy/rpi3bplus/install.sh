#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Bitte mit sudo ausführen." >&2
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

apt-get update
apt-get install -y bluez python3 python3-pip python3-venv rfkill

install -d -m 0755 /opt/prizma-link
python3 -m venv /opt/prizma-link/venv
/opt/prizma-link/venv/bin/python -m pip install --require-hashes -r "$PROJECT_DIR/requirements.lock"
rm -rf /opt/prizma-link/app/src
install -d -m 0755 /opt/prizma-link/app
cp -R "$PROJECT_DIR/src" /opt/prizma-link/app/src
install -m 0755 "$SCRIPT_DIR/prizma-link" /usr/local/bin/prizma-link

install -d -m 0700 /etc/prizma-link
if [ ! -e /etc/prizma-link/config.yaml ]; then
  install -m 0600 "$SCRIPT_DIR/config.example.yaml" /etc/prizma-link/config.yaml
fi
if [ ! -e /etc/prizma-link/prizma-link.env ]; then
  install -m 0600 "$SCRIPT_DIR/prizma-link.env.example" /etc/prizma-link/prizma-link.env
fi

install -d -m 0755 /usr/local/lib/prizma-link/tools
install -m 0755 "$PROJECT_DIR/tools/onsite_preflight.py" /usr/local/lib/prizma-link/tools/onsite_preflight.py
install -d -m 0755 /usr/local/share/doc
install -m 0644 "$SCRIPT_DIR/README.md" /usr/local/share/doc/prizma-link-rpi3bplus.md
install -m 0644 "$SCRIPT_DIR/prizma-link.service" /etc/systemd/system/prizma-link.service
install -m 0644 "$SCRIPT_DIR/prizma-link-weekly-restart.service" \
  /etc/systemd/system/prizma-link-weekly-restart.service
install -m 0644 "$SCRIPT_DIR/prizma-link-weekly-restart.timer" \
  /etc/systemd/system/prizma-link-weekly-restart.timer

systemctl daemon-reload
systemctl disable prizma-link.service >/dev/null 2>&1 || true
systemctl disable --now prizma-link-weekly-restart.timer >/dev/null 2>&1 || true

echo "Installation fertig. Konfiguration und MQTT-Zugangsdaten lokal eintragen."
echo "Bridge-Dienst und Wochen-Timer wurden aus Sicherheitsgründen weder aktiviert noch gestartet."
