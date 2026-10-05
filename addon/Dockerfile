FROM ghcr.io/home-assistant/base-python:3.13-alpine3.22@sha256:5acf09473efb414f4949d08e81c4ef325e03b888d9644ac8b86c9acd0d0e8ef8

ARG BUILD_VERSION=0.1.13

RUN apk add --no-cache bash bluez bluez-deprecated dbus

COPY rootfs /
COPY bridge /opt/prizma-link
RUN pip3 install --no-cache-dir --require-hashes -r /opt/prizma-link/requirements.lock

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="aarch64|amd64" \
  org.opencontainers.image.title="Prizma Link" \
  org.opencontainers.image.description="Local Bluetooth Classic SPP bridge for selected Prizma devices" \
  org.opencontainers.image.source="https://github.com/smartathomeat/prizma-link" \
  org.opencontainers.image.licenses="MIT"
