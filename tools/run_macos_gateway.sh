#!/bin/zsh
set -euo pipefail

prizma_root="${0:A:h:h}"
cd "$prizma_root"

export PRIZMA_MQTT_PASSWORD
PRIZMA_MQTT_PASSWORD="$(security find-generic-password \
  -a prizmalink \
  -s io.smartathome.prizma-link.mqtt \
  -w)"
export PYTHONPATH="$prizma_root/src"

exec .venv/bin/python -m prizma_link.cli run --config config.macos.local.yaml
