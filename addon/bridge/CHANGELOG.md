# Changelog

## Unreleased

- Öffentliche Erstveröffentlichung vorbereitet: Kundendaten ausgeschlossen, Community-Doku,
  Sicherheitsrichtlinie und reproduzierbare CI ergänzt.
- Nicht eindeutig lizenzierbare Referenzimplementierungen entfernt; die öffentliche Fassung
  enthält nur den unabhängig vor Ort belegten PRIZSALT+-Pfad.
- Optionalen systemd-Wartungs-Timer ergänzt: Ein laufender Bridge-Dienst kann sonntags um
  03:30 Uhr neu gestartet werden, ohne den Raspberry Pi neu zu booten. Ein bewusst gestoppter
  Dienst bleibt aus; verpasste Termine werden zum Schutz des Kundenbetriebs nicht tagsüber
  nachgeholt.

## 0.1.13

- Unbekannte Werte für MQTT-Number- und Select-Entitäten werden nicht mehr als ungültiger
  Textzustand veröffentlicht; dadurch bleiben die Live-Statuspolls ohne Log-Spam.
- START/STOP-Protokoll, Sicherheitsgates und alle Geräteschreibrechte bleiben unverändert.

## 0.1.12

- Live bestätigte PRIZSALT+-Aktionen START (`%st,1;`) und STOP (`%st,0;`) eng begrenzt freigegeben.
- Modell-, Frame-, Safe-Mode-, Zustands- und START-Gates bleiben kumulativ aktiv; Pause und alle Parameterwrites bleiben gesperrt.
- Geprüfte Raspberry-Pi-3B+-Installation mit BlueZ, systemd, lokalem Secret-File und Zwei-Geräte-Check ergänzt.

## 0.1.11

- Native macOS-IOBluetooth-Bridge mit festem Read-only-Gate für `%ms;` ergänzt.
- Reale PRIZSALT+-Antwort als Regressionstest aufgenommen; der Parser bleibt bis zur Feldzuordnung unverifiziert.
- Verbindungen werden beim Reconnect und Herunterfahren vollständig asynchron geschlossen.

## 0.1.10

- MQTT-Publishes serialisiert und mit Flush-/Fehler-Gate abgesichert.

## 0.1.9

- Offizielle Home-Assistant-s6/Bashio-AppArmor-Mindestregeln ergänzt; Docker-Socket bleibt gesperrt.

## 0.1.8

- Striktes Modell-Gate verhindert Schreibfreigabe durch bloße Sonic-Frame-Ähnlichkeit.
- Zwei Geräte bleiben bei Pairing-, Zustands-, MQTT- und Reconnect-Fehlern voneinander isoliert.
- Read-only-Vor-Ort-Preflight und beschriftete JSONL-Statuscaptures ergänzt.
- Offline-Suite auf 93 Tests erweitert.

## 0.1.0

- Initiale sichere Implementierung mit BlueZ Profile1, RFCOMM-Framing, MQTT Discovery und Tests.
- Unbekannte PRIZSALT+/multiSALT-Telegramme bleiben vollständig read-only.
