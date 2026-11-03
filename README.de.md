# NW Prices – Trading-Post-Preisdatenbank

*English: [README.md](README.md)*

Kleine Web-App, die Captures aus dem `nw_capture`-Tool einliest, alle Trading-Post-Angebote daraus
extrahiert und sie als durchsuchbare Preisdatenbank anzeigt. Pro Item kannst du einen
**Shop-Preis** festlegen (für den späteren Singleplayer-Shop) und als JSON/CSV exportieren.
Die Oberfläche ist standardmäßig Englisch; mit dem Umschalter **EN / DE** oben rechts geht es auf
Deutsch (die Wahl merkt sich der Browser).

## Was die App kann

- **Upload** der Capture-ZIP (oder einer nackten `ledger.bin`) im Browser, mehrere auf einmal.
  Es werden nur die Preise gespeichert, nicht der Rohmitschnitt. Doppelte Uploads werden erkannt.
- **Item-Übersicht** mit den Item-Namen aus dem Spiel: Min, 25-%-Quantil, Median,
  mengengewichteter Durchschnitt, Max, Angebotsanzahl und Gesamtmenge pro Item. Filter nach Name,
  Kategorie, Tier und Zeitraum; jede Spalte sortierbar.
- **Kategorien wie im Spiel**: Links neben der Tabelle steht die Kategorie-Navigation des Trading Posts
  (Symbolleiste, Zurück-Knopf, Anzahl Angebote je Eintrag), mit den Namen aus dem Spiel auf Deutsch und
  Englisch. Reihenfolge und Namen kommen aus den Spieldaten bzw. einem aufgezeichneten Klickverlauf
  (`ORDER` in `app/categories.py`, Item-Reihenfolge in `app/item_order.json`); nicht aufgezeichnete
  Einträge folgen alphabetisch. Die Spalte „Kategorie“ der Tabelle sortiert in derselben Reihenfolge.
- **Einstellungen** (Menüpunkt oben): Spalten der Item-Übersicht einzeln ein- und ausblenden (alles außer dem
  Item-Namen). Die Auswahl wird nur im jeweiligen Browser gespeichert.
- **Item-Detail**: alle Angebote mit Gear Score, Perks und Einstellzeit, Diagramm (Ausrüstung: Preis
  nach Gear Score bzw. Preisleiter; Ressourcen: Angebotstiefe) und Preisverlauf über Captures.
- **Perks** mit Namen und Wirkungstext auf Deutsch oder Englisch. Die Werte werden für den Gear
  Score des Items genau wie im Spiel berechnet (inkl. Waffenklassen-Bonus). „Preise nach Perk“ zeigt,
  wie viele Angebote einen Perk haben und was sie kosten; Klick auf einen Perk zeigt nur Angebote
  mit diesem Perk (mehrere lassen sich kombinieren).
- **Vorschau wie im Spiel**: Jedes Item hat eine Tooltip-Karte im Stil des Spiels (Seltenheits-Header,
  Icon, Gear Score, Waffen-/Rüstungswerte, Perks mit Icons, Flavor-Text, Rang, Attribut-Skalierung,
  Gewicht – mit den originalen Tooltip-Grafiken und Fonts über nw-buddy). Auf der Item-Seite steht die
  Karte rechts; Klick auf ein Angebot zeigt dessen Karte, beim Drüberfahren über ein Angebot oder ein
  Item in der Übersicht erscheint sie als schwebende Vorschau. Der Basisschaden ist der Wert der Waffe
  selbst – im Spiel enthält diese Zeile Stufe und Attribute deines Charakters, die nicht im Capture stehen.
- **Server**: Jeder Capture gehört zu einem Server (Auswahl beim Hochladen; vorbelegt: Nysa · EU Central,
  Valhalla · US East, El Dorado · US West, Devaloka · SA East, Delos · AP Southeast – der Admin kann Server
  unter **Captures** umbenennen, hinzufügen, löschen und Captures verschieben). Die Auswahl oben in der
  Leiste schaltet Übersicht, Item-Seiten und Exporte zwischen den Servern oder „Alle Server“ um; jede
  Item-Seite hat einen Vergleich „Preise nach Server“. Shop-Preise gelten für alle Server gemeinsam.
- **Shop-Preise**: direkt in der Tabelle eintippen (Enter springt zur nächsten Zeile) oder auf der
  Detailseite mit einem Klick Min/Median/… übernehmen. „Shop-Preise vorschlagen …“ füllt alle
  gefilterten Items auf einmal, z. B. „Median × 1,2, vorhandene nicht überschreiben“.
- **Export** (Menü oben rechts): Shop-Preise als JSON/CSV, Item-Übersicht als CSV, alle Angebote als
  CSV (inkl. Perk-Namen). Die CSVs nutzen `;` und öffnen sich direkt in Excel/LibreOffice.

Preise sind immer **Gold pro Stück**. Taucht derselbe Contract in mehreren Captures auf, zählt nur
die jüngste Beobachtung.

## Auf dem VPS installieren (Docker)

Voraussetzungen: Docker mit Compose-Plugin, eine (Sub-)Domain, deren A-Record auf den VPS zeigt,
Ports 80 und 443 frei.

```sh
scp nwprices.zip user@vps:~ && ssh user@vps
unzip nwprices.zip && cd nwprices

cp .env.example .env
nano .env            # NWP_DOMAIN, NWP_USER und ein langes NWP_PASSWORD (Admin-Login) eintragen

docker compose up -d --build
```

Danach ist die Seite unter `https://<deine-domain>` erreichbar; Caddy holt das HTTPS-Zertifikat
automatisch.

### Zugang

- **Ansehen kann jeder**: Items, Preise, Tooltip-Karten, Captures und Exporte.
- **Ändern kann nur der Admin** – Captures hochladen/umbenennen/löschen und Shop-Preise setzen. Oben
  rechts auf „Admin-Login“ klicken und `NWP_USER` / `NWP_PASSWORD` aus der `.env` eingeben. Der Server
  prüft jede Änderung; ausgeblendete Knöpfe sind nicht der einzige Schutz.
- Der Login gilt 14 Tage (Cookie, nur über HTTPS); „Abmelden“ beendet ihn. Wird `NWP_PASSWORD`
  geändert, sind alle bestehenden Logins ungültig.
- Nach 5 falschen Passwörtern von einer Adresse ist der Login 10 Minuten gesperrt.
- `NWP_PRIVATE=1` in der `.env` macht die ganze Seite nur nach Login sichtbar.
- Ohne `NWP_PASSWORD` gibt es keinen Admin-Login – die Weboberfläche ist dann nur lesbar (Import per
  Kommandozeile geht weiter). Ein starkes Passwort erzeugt `openssl rand -base64 24`.

### Es läuft schon ein Reverse Proxy (nginx, Caddy, Traefik …)

Dann nur die App starten; sie hört auf `127.0.0.1:8000`:

```sh
docker compose up -d --build app
```

nginx-Beispiel:

```nginx
server {
    server_name preise.example.de;
    client_max_body_size 500m;
    location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; proxy_read_timeout 300s; }
    # + deine üblichen listen/ssl-Zeilen (certbot)
}
```

### Aktualisieren, Backup, Logs

```sh
docker compose up -d --build                                   # nach Code-Änderungen
docker compose cp app:/data/prices.db ./backup-$(date +%F).db  # Backup der Datenbank
docker compose logs -f app                                     # Logs
```

Die Datenbank liegt im Docker-Volume `nwp_data` und übersteht Neustarts und Updates.
Zurückspielen: `docker compose cp backup.db app:/data/prices.db && docker compose restart app`.

## Lokal ausprobieren (ohne Docker)

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py import ~/Downloads/capture.zip --server Nysa   # optional per Kommandozeile
flask --app app.web run --port 8000                       # http://127.0.0.1:8000
```

Ohne `NWP_PASSWORD` ist die Weboberfläche nur lesbar; zum lokalen Testen z. B. `NWP_PASSWORD=test` setzen.

Kommandozeile (lokal oder im Container mit `docker compose exec app python manage.py …`;
Ausgabesprache mit `NWP_LANG=de`):

| Befehl | Zweck |
|---|---|
| `python manage.py import a.zip b.zip --server Nysa --name "Name"` | Captures für einen Server importieren |
| `python manage.py servers` | Server auflisten |
| `python manage.py list` | Captures auflisten |
| `python manage.py delete 3` | Capture #3 samt Angeboten löschen |
| `python manage.py export shop.json` | Shop-Preise exportieren |

## Tipps zum Capturen

- Ein Capture-Tool, das du verwenden kannst: [linux-capture](https://github.com/openworldserver/linux-capture)
  (nur für Linux).
- Eine Suche liefert **höchstens 100 Angebote pro Seite**. Für vollständige Preise also möglichst
  feine Kategorien anklicken (z. B. *Weapons → 1-Handed → Rapiers* statt nur *Weapons*) und bei
  vielen Treffern weiterblättern bzw. anders sortieren. Unter **Captures** siehst du pro Suche
  „geliefert“ vs. „Treffer gesamt“ und erkennst, wo noch etwas fehlt.
- Mehrere kurze Captures sind kein Problem – sie werden zusammengeführt, und der Preisverlauf zeigt,
  wie sich die Preise zwischen den Captures verändern.

## Spieldaten (Item-Namen und Perks)

Item-Namen und Perks stammen aus [nw-buddy](https://github.com/giniedp/nw-buddy-data) und liegen
fertig in `app/gamedata/` (≈1 MB). Im Capture stehen Perks nur als CRC32 der kleingeschriebenen
Perk-ID (z. B. `e0575826` = `PerkID_Gem_EmptyGemSlot`); die App schlägt sie dort nach. Die
Perk-Werte nutzen die Formel von nw-buddy (`1 + Σ Steigung × GS-Abschnitt + Klassenbonus × Steigung`)
und werden wie im Spiel auf eine Nachkommastelle abgeschnitten; abgeglichen mit einem Tooltip aus
dem Spiel (Muskete GS 191: „Accelerating Traps +11 % … Bleed 6,9 %“).

Spieldaten aktualisieren (z. B. für einen Private Server mit geänderten Daten):

```sh
git clone --depth 1 --filter=blob:none --sparse https://github.com/giniedp/nw-buddy-data
cd nw-buddy-data && git sparse-checkout set --no-cone '/live/localization/en-us.json' \
    '/live/localization/de-de.json' '/live/datatables/javelindata_perks*.json' \
    '/live/datatables/javelindata_itemdefinitions_*.json' '/live/datatables/javelindata_weapontiers.json' \
    '/live/datatables/javelindata_housingitems*.json' '/live/datatables/mtx/javelindata_housingitems_mtx.json'
cd .. && python nwprices/tools/build_gamedata.py nw-buddy-data/live
```

Ohne die Dateien in `app/gamedata/` läuft die App trotzdem, zeigt dann aber interne IDs und Perk-Hashes.

**Icons** liegen nicht in der ZIP. Der Server lädt jedes Icon einmal vom CDN von nw-buddy
(`cdn.nw-buddy.de`) und speichert es im Datenvolume (`/data/icons`); der Browser spricht nur mit
deinem Server. Einstellungen in der `.env`: `NWP_ICON_CDN=off` schaltet das Laden ab (Karten dann ohne
Icons), `NWP_ICON_CDN=https://…` nimmt eine andere Quelle, `NWP_ICON_CACHE` ändert den Cache-Ordner.
Du kannst Icons auch selbst dort ablegen (Pfad z. B. `lyshineui/images/icons/items/weapon/2hmuskett2.webp`).
Tooltip-Rahmen und Fonts (Nimbus Sans L, GPL; Caslon Antique, freie Lizenz) liegen in `app/static/nw/`.


## Wie die Dekodierung funktioniert

`app/decoder.py` liest die `ledger.bin` (NWDL-Records → LZ4-Pakete → Chunks/Fragmente → RPCs) und
sucht die Trading-Post-RPCs **864** (Suchanfrage) und **2538**
(`ContractsComponentClientFacet_OnSearchContracts`, Ergebnisliste). Pro Contract werden Item-ID,
Kategorie, Tier, Gear Score, Preis, Menge, Perk-Hashes und Einstellzeit gelesen. Jeder Eintrag wird
über doppelt gespeicherte Felder (Gear Score, Menge) gegengeprüft; nicht lesbare Einträge werden
übersprungen und beim Import als „unlesbar“ gezählt.

Bekannte Grenzen:

- Attribut-Perks auf Rüstungen (z. B. „+X Stärke“) zeigen Name und Beschreibung, aber keine Zahl –
  diese Werte stehen nicht in den Perk-Tabellen.
- Getestet mit Waffen und Ressourcen. Sollte eine andere Kategorie (Rüstung, Housing …) ein
  abweichendes Format haben, erscheinen deren Einträge beim Import als „unlesbar“ – dann den Capture
  schicken, dann wird der Decoder angepasst.
