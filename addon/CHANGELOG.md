# Changelog

## 0.1.13

- Unbekannte Number-/Select-Werte werden erst veröffentlicht, sobald ein gültiger Wert
  dekodiert wurde. Dies verhindert wiederholte MQTT-Konvertierungsfehler in Home Assistant.
- START/STOP und sämtliche Sicherheitsgrenzen bleiben unverändert.

## 0.1.12

- START und STOP für den live bestätigten 32-Zeichen-PRIZSALT+-Rahmen hinter allen Sicherheitsgates freigegeben.
- Pause, Programme, Dauer, Lüfter und Salzintervalle bleiben unverändert gesperrt.
- Nach jedem Schaltbefehl wird der Gerätestatus erneut abgefragt.

## 0.1.11

- Gemeinsamen Bridge-Kern auf sauberes asynchrones Schließen der RFCOMM-Verbindung umgestellt.
- Live-PRIZSALT+-Statusrahmen als strikt read-only Regressionstest aufgenommen.

## 0.1.10

- MQTT-Discovery und Zustände werden geordnet über genau einen Publisher übertragen; Publish-Spitzen bei einem oder zwei Geräten entfallen.
- MQTT-Publish-Fehler werden gesammelt, geloggt und am Flush-Gate gemeldet.

## 0.1.9

- AppArmor-Profil an das offizielle Home-Assistant-s6/Bashio-Minimum angeglichen, einschließlich `/usr/lib/bashio/**`, Signal- und Legacy-Service-Rechten.
- Docker-Socket bleibt ausdrücklich gesperrt.

## 0.1.8

- Schreibfreigabe an ein ausdrücklich konfiguriertes und passendes Modell gebunden; `auto`, PRIZSALT+ und multiSALT bleiben auch bei Sonic-ähnlichen Frames read-only.
- Zwei-Geräte-Start toleriert einen vorübergehend nicht erreichbaren Generator, ohne den anderen zu blockieren.
- Read-only-Vor-Ort-Preflight und erweiterte Flotten-, Framing-, Reconnect- und Konfigurationstests ergänzt.

## 0.1.7

- Erlaubt s6 die benötigten containerinternen Laufzeitverzeichnisse unter `/run`; der Docker-Socket bleibt gesperrt.

## 0.1.6

- Nutzt das standardmäßige s6-Service-Layout der Home-Assistant-Add-on-Basis, damit Supervisor- und MQTT-Dienstumgebung korrekt initialisiert werden.

## 0.1.5

- Deklariert den benötigten Supervisor-API-Zugriff für die Bashio-MQTT-Dienstabfrage und entfernt den nicht vorhandenen s6-Umgebungsfallback.

## 0.1.4

- Liest die s6-Supervisor-Umgebung intern ein, ohne sensible Werte zu protokollieren, damit Bashio die MQTT-Dienstinformationen abrufen kann.

## 0.1.3

- Verwendet Bashio direkt als Skript-Interpreter, damit die Supervisor-Servicefunktionen ohne s6-Wrapper verfügbar sind.

## 0.1.2

- Startet das schlanke Entrypoint-Skript direkt mit Bash und vermeidet damit die nicht benötigte s6-Interpreter-Schicht.

## 0.1.1

- Erlaubt den s6/Bashio-Entrypoint explizit im AppArmor-Profil.
- Führt vor dem Bridge-Start ein auf die konfigurierten Geräte beschränktes Pairing/Trust-Bootstrap aus.

## 0.1.0

- Erste lokale Bluetooth-Classic-SPP-Bridge.
- Safe Mode, zehn Frames umfassendes Read-only-Gate und MQTT Discovery.
- Schreibzugriffe für PRIZSALT+ und multiSALT bleiben bis zur Protokollverifikation gesperrt.
