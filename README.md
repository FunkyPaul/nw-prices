# NW Prices – trading post price database

*Deutsche Anleitung: [README.de.md](README.de.md)*

A small web app that reads captures from the `nw_capture` tool, extracts every trading post
listing and turns them into a searchable price database. For each item you can set a
**shop price** (for a single-player shop later on) and export the result as JSON/CSV.
The interface is in English by default; the **EN / DE** toggle in the top right switches to German
(the choice is remembered in the browser).

## Features

- **Upload** capture ZIPs (or a bare `ledger.bin`) in the browser, several at once. Only the prices
  are stored, not the raw capture. Duplicate uploads are detected.
- **Item overview** with in-game item names: min, 25th percentile, median, quantity-weighted average,
  max, number of listings and total quantity per item. Filter by name, category, tier and period;
  every column sorts.
- **Categories like in the game**: next to the table is the trading post's category navigation (icon
  rail, back button, number of listings per entry) with the in-game names in English and German. Order
  and names come from the game data and from a recorded click history (`ORDER` in
  `app/categories.py`, item order in `app/item_order.json`); entries that were not recorded follow
  alphabetically. The table's "Category" column sorts in the same order.
- **Full screen width and mobile view**: on large screens the table fills the page. On tablets and
  phones the header wraps, the categories can be folded in and out, and the item overview turns into
  cards instead of a table.
- **Settings** (top menu): show or hide each column of the item overview (everything except the item
  name). The choice is saved in the respective browser only.
- **Item detail**: every listing with gear score, perks and listing time, a chart (gear: price by
  gear score or price ladder; resources: market depth) and the price history across captures.
- **Perks** with names and effect text in English or German, values calculated for the item's
  gear score exactly like the game does (incl. weapon-class gear score bonuses). "Prices by perk"
  shows how many listings carry each perk and what they cost; click a perk to see only listings
  with it (several perks combine).
- **In-game preview**: every item shows a tooltip card styled like the game (rarity header, icon,
  gear score, weapon/armor stats, perks with icons, flavor text, tier, attribute scaling, weight –
  original tooltip graphics and fonts via nw-buddy). On the item page the card sits on the right;
  click a listing to show its card, hover a listing or an item in the overview for a floating preview.
  Base damage is the weapon's own value – in-game that line includes your character's level and
  attributes, which the capture doesn't contain.
- **Servers**: every capture belongs to a server (chosen on upload; preset: Nysa · EU Central,
  Valhalla · US East, El Dorado · US West, Devaloka · SA East, Delos · AP Southeast – the admin can
  rename, add or delete servers and move captures under **Captures**). The selector in the top bar
  switches overview, item pages and exports between servers or "All servers"; each item page has a
  "Prices by server" comparison. Shop prices are shared across all servers.
- **Shop prices**: type them straight into the table (Enter jumps to the next row) or apply
  min/median/… with one click on the detail page. "Suggest shop prices …" fills all filtered items
  at once, e.g. "median × 1.2, keep existing".
- **Export** (menu top right): shop prices as JSON/CSV, item overview as CSV, all listings as CSV
  (including perk names). CSVs use `;` and open directly in Excel/LibreOffice.

Prices are always **gold per unit**. If the same contract appears in several captures, only the
most recent observation counts.

## Install on a VPS (Docker)

Requirements: Docker with the Compose plugin, a (sub)domain whose A record points at the VPS,
ports 80 and 443 free.

```sh
scp nwprices.zip user@vps:~ && ssh user@vps
unzip nwprices.zip && cd nwprices

cp .env.example .env
nano .env            # set NWP_DOMAIN, NWP_USER and a long NWP_PASSWORD (admin login)

docker compose up -d --build
```

The site is then available at `https://<your-domain>`; Caddy fetches the HTTPS certificate
automatically.

### Access

- **Everyone can view** the site: items, prices, tooltip cards, captures and exports.
- **Only the admin can change things** – upload/rename/delete captures and set shop prices. Click
  "Admin login" (top right) and use `NWP_USER` / `NWP_PASSWORD` from `.env`. The server checks every
  change, so hiding the buttons is not the only protection.
- The login stays valid for 14 days (cookie, HTTPS only); "Log out" ends it. Changing `NWP_PASSWORD`
  logs out all existing sessions.
- After 5 wrong passwords from one address, login is blocked for 10 minutes.
- `NWP_PRIVATE=1` in `.env` makes the whole site visible only after login.
- Without `NWP_PASSWORD` there is no admin login – the web interface is read-only (importing still
  works via the command line). Generate a strong password with `openssl rand -base64 24`.

### If a reverse proxy is already running (nginx, Caddy, Traefik …)

Start only the app; it listens on `127.0.0.1:8000`:

```sh
docker compose up -d --build app
```

nginx example:

```nginx
server {
    server_name prices.example.com;
    client_max_body_size 500m;
    location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; proxy_read_timeout 300s; }
    # + your usual listen/ssl lines (certbot)
}
```

### Update, backup, logs

```sh
docker compose up -d --build                                   # after code changes
docker compose cp app:/data/prices.db ./backup-$(date +%F).db  # back up the database
docker compose logs -f app                                     # logs
```

The database lives in the Docker volume `nwp_data` and survives restarts and updates.
Restore: `docker compose cp backup.db app:/data/prices.db && docker compose restart app`.

## Run locally (without Docker)

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py import ~/Downloads/capture.zip --server Nysa   # optional, via command line
flask --app app.web run --port 8000                       # http://127.0.0.1:8000
```

Without `NWP_PASSWORD` the web interface is read-only; for local testing set e.g. `NWP_PASSWORD=test`.

Command line (locally, or in the container via `docker compose exec app python manage.py …`;
output language via `NWP_LANG=en|de`):

| Command | Purpose |
|---|---|
| `python manage.py import a.zip b.zip --server Nysa --name "Name"` | import captures for a server |
| `python manage.py servers` | list servers |
| `python manage.py list` | list captures |
| `python manage.py delete 3` | delete capture #3 and its listings |
| `python manage.py export shop.json` | export shop prices |

## Capture tips

- A capture tool you can use: [linux-capture](https://github.com/openworldserver/linux-capture)
  (Linux only).
- A search returns **at most 100 listings per page**. For complete prices, click through
  categories as finely as possible (e.g. *Weapons → 1-Handed → Rapiers* instead of just *Weapons*)
  and page through or re-sort when there are many results. The **Captures** page shows "returned"
  vs. "total matches" per search, so you can see where something is missing.
- Many short captures are fine – they are merged, and the price history shows how prices change
  between captures.

## Game data (item names and perks)

Item names and perks come from [nw-buddy](https://github.com/giniedp/nw-buddy-data) and are bundled
in `app/gamedata/` (≈1 MB). In the capture, perks are only transmitted as the CRC32 of their
lower-case perk ID (e.g. `e0575826` = `PerkID_Gem_EmptyGemSlot`); the app looks them up there.
Perk values use nw-buddy's formula (`1 + Σ rate × gear score range + class bonus × rate`) and are
truncated to one decimal like in-game; checked against an in-game tooltip (Musket GS 191:
"Accelerating Traps +11 % … Bleed 6.9 %").

To refresh the game data (e.g. for a private server with changed data):

```sh
git clone --depth 1 --filter=blob:none --sparse https://github.com/giniedp/nw-buddy-data
cd nw-buddy-data && git sparse-checkout set --no-cone '/live/localization/en-us.json' \
    '/live/localization/de-de.json' '/live/datatables/javelindata_perks*.json' \
    '/live/datatables/javelindata_itemdefinitions_*.json' '/live/datatables/javelindata_weapontiers.json' \
    '/live/datatables/javelindata_housingitems*.json' '/live/datatables/mtx/javelindata_housingitems_mtx.json'
cd .. && python nwprices/tools/build_gamedata.py nw-buddy-data/live
```

Without the files in `app/gamedata/` the app still works, just with internal IDs and perk hashes.

**Icons** are not bundled. The server fetches each icon once from nw-buddy's CDN
(`cdn.nw-buddy.de`) and caches it in the data volume (`/data/icons`); the browser only ever talks to
your server. Settings in `.env`: `NWP_ICON_CDN=off` disables downloading (cards then show without
icons), `NWP_ICON_CDN=https://…` points to another source, `NWP_ICON_CACHE` changes the cache
folder. You can also copy icons there yourself (path like `lyshineui/images/icons/items/weapon/2hmuskett2.webp`).
Tooltip frames and fonts (Nimbus Sans L, GPL; Caslon Antique, free license) are in `app/static/nw/`.


## How decoding works

`app/decoder.py` reads `ledger.bin` (NWDL records → LZ4 packets → chunks/fragments → RPCs) and looks
for the trading post RPCs **864** (search request) and **2538**
(`ContractsComponentClientFacet_OnSearchContracts`, result list). For each contract it reads item ID,
category, tier, gear score, price, quantity, perk hashes and listing time. Every entry is
cross-checked against fields stored twice (gear score, quantity); unreadable entries are skipped and
counted as "unreadable" on import.

Known limitations:

- Attribute perks on armor (e.g. "+X Strength") show name and description, but no number – those
  values aren't in the perk tables.
- Tested with weapons and resources. If another category (armor, housing …) uses a different format,
  its entries show up as "unreadable" on import – send the capture and the decoder can be adjusted.
