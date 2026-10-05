# Prizma Link – Bedienung und Sicherheit

Prizma Link verbindet ausgewählte Prizma-Trockensalzgeneratoren lokal über Bluetooth Classic
RFCOMM/SPP mit Home Assistant. Das Projekt ist eine unabhängige Community-Integration von
smartathome® und keine offizielle Hersteller-Software.

## Vor der ersten Verbindung

1. Ein vollständiges Home-Assistant-Backup erstellen.
2. Generator einschalten und in Funkreichweite bringen.
3. Die Hersteller-App auf allen Telefonen vollständig schließen; der Generator kann nur eine
   Steuerverbindung gleichzeitig akzeptieren.
4. Den Kandidaten `PSN_IF-*` höchstens 30 Sekunden suchen.
5. Die SPP-UUID `00001101-0000-1000-8000-00805F9B34FB` nachweisen. Ohne SPP nicht fortfahren.
6. Nur die konfigurierte Bluetooth-Adresse koppeln. Bei unterstützten PRIZSALT+-Geräten ist der
   werkseitige PIN typischerweise `1234`; im Zweifel die Herstellerunterlagen verwenden.
7. `model: auto`, `safe_mode: true` und `allow_start: false` beibehalten.

## Read-only-Gate

Die Bridge sendet zunächst ausschließlich `%ms;` und benötigt zehn gültige, gleichartig geformte
Statusantworten. Fragmentierte Pakete werden am Semikolon getrennt; Nicht-ASCII-, Teil- und
Überlängenframes werden verworfen.

Eine automatisch erkannte Rahmenform erlaubt niemals Schreibzugriff. Nur für den unabhängig
vor Ort bestätigten 32-Zeichen-PRIZSALT+-Rahmen und ein ausdrücklich konfiguriertes
`model: prizsalt` sind START (`%st,1;`) und STOP (`%st,0;`) implementiert. `safe_mode` und
`allow_start` bleiben zusätzliche Sperren. multiSALT und unbekannte Rahmen bleiben read-only.

Pause, Programme, Dauer, Lüfter und Salzintervalle werden nicht geschrieben. Die App startet
niemals selbstständig eine Sitzung.

## Konfiguration

- `devices`: Geräte mit eigenem Namen, eigener Bluetooth-Adresse, Modell und PIN
- `safe_mode`: blockiert alle Schreibtelegramme; Standard `true`
- `allow_start`: zusätzliche START-Sperre; Standard `false`
- `poll_interval`: Sekunden zwischen Statusabfragen
- `command_timeout`: Zeitlimit für Befehl plus Statusbestätigung
- `reconnect_max_seconds`: maximaler exponentieller Reconnect-Abstand
- `log_level`: `debug`, `info`, `warning` oder `error`
- `mqtt_discovery_prefix`: normalerweise `homeassistant`

Die PIN ist ein Passwortfeld. MQTT-Zugangsdaten kommen ausschließlich aus dem Supervisor-Service
und werden weder in Discovery-Payloads noch in Logs geschrieben.

Die App benötigt `host_dbus: true`, damit sie ausschließlich über den System-D-Bus mit BlueZ
kommunizieren kann, sowie `hassio_api: true`, um die lokalen Mosquitto-Dienstdaten über Bashio zu
lesen. Sie fordert weder Docker-Zugriff noch `full_access` oder zusätzliche Linux-Capabilities an;
das mitgelieferte AppArmor-Profil begrenzt Datei-, D-Bus- und Netzwerkzugriffe.

Bei mehreren Geräten bleiben Pairing, Verbindung, Status, Reconnect und MQTT-Topics getrennt.
Ist ein Generator beim Start nicht erreichbar, darf der andere weiterlaufen.

## Entitäten

Status: verbunden, gekoppelt, Protokoll verifiziert, Safe Mode, Betriebsstatus, Restlaufzeit,
Fehlercode/-text, letzte Aktualisierung, Protokoll und Gerätekennung.

START, Pause/Fortsetzen, STOP, Statusaktualisierung und Reconnect werden als Buttons angelegt.
Nicht unterstützte Schreibaktionen werden von der Bridge blockiert; bei PRIZSALT+ bleiben Pause
und alle Parameteränderungen gesperrt. Diagnosewerte wie Rohframe, Reconnect-Zähler,
Befehlsfehler und Antwortlatenz sind standardmäßig deaktiviert.

## MQTT und Verbindungsverhalten

Der offizielle Mosquitto Broker ist Voraussetzung. Discovery und bestätigte Zustände dürfen
retained sein; Command Topics sind immer non-retained. Nach einem MQTT-Reconnect werden nur
Discovery und bestätigter Zustand veröffentlicht. Nach einem Bluetooth-Reconnect sendet die App
ausschließlich `%ms;`, leert alte Queues und setzt das Gerät bei Ausfall auf `unavailable`.

## Fehlerbehebung

- Hersteller-App schließen und nur eine Bridge-Verbindung zulassen.
- Funkreichweite prüfen; Metall, Wände und Schaltschränke dämpfen Bluetooth Classic.
- Bei Fehlercode ungleich null zuerst die Hardware prüfen. START bleibt blockiert.
- Fehlt der MQTT-Service, Mosquitto Broker installieren und die MQTT-Integration prüfen.
- Fehlt SPP, nicht auf BLE ausweichen. Diagnose mit NO-GO beenden.

## Update, Backup und Entfernung

Vor jedem Update ein Backup erstellen. Die App nach einem Update zuerst im Safe Mode testen.
Zur Entfernung die App stoppen/deinstallieren und nur die konkrete Generator-Kopplung mit
`bluetoothctl remove <ADRESSE>` löschen. Niemals pauschal alle Bluetooth-Kopplungen entfernen.

Eine reale Sitzung wird durch Diagnose, Installation oder Reconnect nicht automatisch gestartet.
Der erste echte START bleibt einer Person unter direkter Sichtkontrolle vorbehalten.
