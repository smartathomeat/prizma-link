# PRIZMA Link auf Raspberry Pi 3B+

Diese Variante ersetzt das temporäre Mac-Gateway durch eine dauerhaft vor Ort laufende
Bluetooth-Classic-SPP-Bridge. Der Raspberry Pi 3B+ verwendet zunächst sein eingebautes
Bluetooth. Der gekaufte USB-Dongle ist nur ein Reichweiten-Fallback und wird erst verwendet,
wenn Raspberry Pi OS ihn tatsächlich als BlueZ-Adapter erkennt.

## Benötigt

- Raspberry Pi 3B+ oder neuer, Raspberry Pi OS Lite 64-bit (Trixie empfohlen)
- stabile microSD und offizielles/ausreichendes 5-V-Netzteil
- WLAN oder Ethernet im selben Netz wie Home Assistant
- Mosquitto-Benutzer nur für PRIZMA Link; Kennwort ausschließlich lokal eintragen
- Generator eingeschaltet, Hersteller-App auf allen Telefonen vollständig geschlossen

## Installation

Das gesamte Repository auf den Pi kopieren und dort ausführen:

```bash
cd prizma-link
sudo ./deploy/rpi3bplus/install.sh
sudo nano /etc/prizma-link/config.yaml
sudo nano /etc/prizma-link/prizma-link.env
```

In `config.yaml` werden nur die beiden echten Bluetooth-Adressen lokal eingetragen. In
`prizma-link.env` kommen MQTT-Benutzer und -Kennwort. Beide Dateien bleiben mit Modus `0600`
lokal auf dem Pi.

## Sichere Vor-Ort-Reihenfolge

1. Beide Generatoren einzeln einschalten und mit `bluetoothctl --timeout 30 scan on` sichtbar
   machen. Keine vollständige Adresse fotografieren oder in Chats kopieren.
2. Zunächst `safe_mode: true`, `allow_start: false` und `model: auto` verwenden.
3. Exakt die konfigurierte Adresse koppeln:

   ```bash
   sudo /usr/local/bin/prizma-link pair \
     --config /etc/prizma-link/config.yaml --address AA:BB:CC:DD:EE:FF
   ```

4. Den read-only Flottencheck ausführen:

   ```bash
   sudo /opt/prizma-link/venv/bin/python \
     /usr/local/lib/prizma-link/tools/onsite_preflight.py \
     --config /etc/prizma-link/config.yaml --expect-devices 2
   ```

5. Pro Gerät mindestens zehn gültige Statusantworten prüfen. Erst beim bestätigten
   32-Zeichen-PRIZSALT+-Rahmen `model: prizsalt` setzen.
6. Den Dienst im Safe Mode starten und Home-Assistant-Status prüfen:

   ```bash
   sudo systemctl start prizma-link
   sudo systemctl status prizma-link --no-pager
   sudo journalctl -u prizma-link -n 80 --no-pager
   ```

7. Jedes Gerät separat unter Sichtkontrolle STOP → START → STOP prüfen. Erst wenn alle
   Geräte eindeutig zugeordnet sind, `safe_mode: false` und `allow_start: true`
   setzen, den Dienst neu starten und dauerhaft aktivieren. Der Wartungs-Timer startet nur den
   Bridge-Dienst sonntags um 03:30 Uhr neu; der Raspberry Pi selbst wird nicht neu gestartet:

   ```bash
   sudo systemctl enable --now prizma-link
   sudo systemctl enable --now prizma-link-weekly-restart.timer
   systemctl list-timers prizma-link-weekly-restart.timer --no-pager
   ```

Der Dienst wird vom Installer absichtlich weder aktiviert noch gestartet. Dadurch kann ein
Neustart des Pi vor der Vor-Ort-Abnahme keinen Generator ansprechen. Die dauerhafte Aktivierung
ist der letzte Schritt nach MQTT-Test, Pairing, Status-Probe und Sichtkontrolle. Auch der
Wochen-Timer bleibt bis zu diesem Schritt deaktiviert.

## Wöchentlicher Wartungsneustart

`prizma-link-weekly-restart.timer` startet ausschließlich einen bereits laufenden
`prizma-link.service` jeden Sonntag um 03:30 Uhr neu. Ein für Wartung bewusst gestoppter
Bridge-Dienst bleibt gestoppt. Bluetooth-Kopplungen, lokale Konfiguration und MQTT-Zugangsdaten
bleiben erhalten. Während des kurzen Wiederanlaufs melden sich beide Geräte in Home Assistant
zunächst offline und anschließend wieder online.

Der Timer verwendet bewusst `Persistent=false`: War der Pi am Sonntag um 03:30 Uhr ausgeschaltet,
wird der verpasste Wartungsneustart nicht später während eines möglichen Kundenbetriebs
nachgeholt. `Restart=on-failure` im Hauptdienst bleibt zusätzlich aktiv, deckt aber keinen noch
laufenden, intern hängenden Prozess ab.

Status und nächsten Termin prüfen:

```bash
systemctl status prizma-link-weekly-restart.timer --no-pager
systemctl list-timers prizma-link-weekly-restart.timer --no-pager
```

Timer bei Bedarf ohne Änderung am Bridge-Dienst wieder entfernen:

```bash
sudo systemctl disable --now prizma-link-weekly-restart.timer
```

## Plattformhinweis

Der Ablauf wurde auf einem Raspberry Pi 3B+ mit 64-bit Raspberry Pi OS und dem eingebauten
Bluetooth-Adapter validiert. Vor einer Kundeninstallation müssen Stromversorgung, Temperatur,
BlueZ-Adapter, Funkreichweite und der read-only Flotten-Preflight auf der konkreten Hardware
erneut geprüft werden.

## Unterstützte Schreibaktionen

Für das live bestätigte PRIZSALT+-Rahmenformat sind ausschließlich `%st,1;` (START) und
`%st,0;` (STOP) freigegeben. Nach jedem Befehl wird `%ms;` abgefragt; es gibt keinen
optimistischen Zustand. Pause, Programme, Dauer, Lüfter und zehn Salzintervalle bleiben
gesperrt.

## USB-Bluetooth-Fallback

Den USB-Dongle nicht parallel blind aktivieren. Zuerst prüfen:

```bash
lsusb
bluetoothctl list
rfkill list bluetooth
```

Wenn zwei Adapter erscheinen, bleibt für den ersten Termin das eingebaute `hci0` aktiv. Ein
Wechsel auf den USB-Adapter wird erst nach einem Reichweitenvergleich vorgenommen; die Bridge
ist derzeit absichtlich auf `hci0` begrenzt.

## Rollback

```bash
sudo systemctl disable --now prizma-link-weekly-restart.timer
sudo systemctl disable --now prizma-link
```

Danach kann die konkrete Kopplung mit `bluetoothctl remove <ADRESSE>` entfernt werden. Niemals
pauschal alle Bluetooth-Kopplungen löschen.
