# Lokálny endpoint pre Živý obraz

Server číta vybrané entity z Home Assistanta a vykresľuje PNG pre pôvodný
`MultiTricker/zivyobraz-fw`. Obsahuje základný dashboard s dátumom, hodnotami
a časom poslednej úspešnej aktualizácie. Má slovenskú diakritiku a čiernu,
bielu a červenú paletu; pre BW displej používa iba čiernu a bielu.

Predvolené entity v konfigurácii sú **príklady**. Nahraď ich vlastnými ID.
Predpoveď počasia zatiaľ nie je implementovaná; možno zobraziť hodnotu
už existujúceho senzorového alebo template senzora v HA.

## Nasadenie ako HA add-on

Vyžaduje Home Assistant OS alebo inú inštaláciu so Supervisorom. Samostatný
Home Assistant Container/Core nemá add-ony; použi samostatný server nižšie.

1. Skopíruj tento priečinok do `/addons/eink-ha` na HA stroji. V obchode
   add-onov obnov zoznam lokálnych add-onov a nainštaluj **Lokálny e-ink dashboard**.
   Pri testovaní feature vetvy pridaj do obchodu add-onov repozitár
   `https://github.com/jsuchal/iot-home#feat/local-eink-ha`.
   Po zlúčení do main použi `https://github.com/jsuchal/iot-home` bez prípony.
   Root `repository.yaml` obsahuje metadáta repozitára.
2. V konfigurácii nastav `device_key` na existujúci PIN/API kľúč displeja
   a uprav `metrics` podľa ID entít v HA. Nezadávaj kľúče do Git repozitára.
3. Spusti add-on. Prístup k HA API zabezpečuje automaticky `SUPERVISOR_TOKEN`;
   do ESP32 sa HA token neposiela. `sleep_seconds` je interval zobudenia
   displeja a `refresh_seconds` minimálny interval načítania nových údajov.
4. Vo firmware s nastaviteľným endpointom zadaj **lokálnu IP HA stroja**,
   port **8080** a cestu **`/index.php`**. Potrebuješ firmware zostavený
   s `USE_CLIENT_HTTP`; nastavenie portu samo neprepína HTTP/HTTPS.

Add-on je určený pre `amd64` a `aarch64`. Endpoint používa HTTP v domácej sieti;
nevystavuj ho internetu. HTTPS možno doplniť cez lokálny reverse proxy a
zodpovedajúce HTTPS zostavenie firmware.

## Aktualizácie v konkrétnych časoch

V konfigurácii add-onu možno namiesto pravidelného intervalu nastaviť denné
časy v 24-hodinovom formáte `HH:MM`:

```yaml
timezone: Europe/Bratislava
update_times:
  - "07:00"
  - "12:30"
  - "19:00"
```

Po zmene reštartuj add-on. Server po každej požiadavke vypočíta `PreciseSleep`
do najbližšieho zadaného času, aj cez polnoc. Pri novom plánovanom čase načíta
čerstvé údaje bez ohľadu na `refresh_seconds`. Medzi časmi ponecháva ten istý
obrázok. Prvé pripojenie po spustení servera vytvorí obrázok okamžite.

Prázdne `update_times: []` zachová pôvodné intervalové správanie.
Časy sa interpretujú v nastavenom `timezone`. Pri prechode na letný čas sa
neexistujúci čas preskočí; pri návrate na zimný čas sa opakovaná hodina použije
iba pri prvom výskyte. Zariadenie dostane nový plán až pri ďalšom spojení;
server nevie zobudiť spiaci displej. Presnosť ovplyvňuje čas sťahovania,
obnovy e-inku a hodín ESP32, preto je aktualizácia približná, nie presne na sekundu.

## Samostatný server a demo

Vyžaduje Python 3.12+, fonty DejaVu Sans a systémovú databázu časových pásiem.
Na Debiane/Ubuntu ich poskytujú balíky `fonts-dejavu-core` a `tzdata`.

```sh
cd eink-ha
python3 -m venv /tmp/eink-ha-venv
/tmp/eink-ha-venv/bin/pip install -r requirements.txt
cp config.example.json config.local.json
/tmp/eink-ha-venv/bin/python app.py --config config.local.json --demo
```

Demo nepoužíva HA a je označené priamo na obrázku. Na skutočnú prevádzku uprav
`ha_url`, entity a `device_key` v ignorovanom `config.local.json`, nastav
`HA_TOKEN` cez chránenú konfiguráciu služby a vynechaj `--demo`.
Token potrebuje právo čítať požadované entity. Názvy entít v príklade
nemusia existovať v tvojej inštalácii. Server nevyžaduje internet pre renderovanie;
zdroje samotných HA senzorov môžu internet používať.

Obrázok z demo servera možno stiahnuť do súboru:

```sh
curl --fail 'http://127.0.0.1:8080/index.php?timestampCheck=1' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: 12345678' \
  --data '{"display":{"width":800,"height":480,"colorType":"3C"}}' \
  --output demo.png
```

`12345678` je iba demo kľúč z príkladu. Server možno spustiť aj v kontajneri:

```sh
docker build -t iot-home-eink .
docker run --rm -p 8080:8080 \
  --mount type=bind,src="$(pwd)/config.local.json",dst=/data/options.json,readonly \
  iot-home-eink python app.py --demo
```

Pri prevádzke proti HA vynechaj `python app.py --demo` a odovzdaj `HA_TOKEN`
cez chránený env súbor alebo konfiguráciu kontajnera. HA URL musí byť dostupná
z kontajnera; `localhost` v ňom označuje samotný kontajner.

## Kompatibilita a správanie

- `POST /index.php?timestampCheck=1` aj `timestampCheck=0` vracajú `200 OK`,
  `image/png` a telo obrázka. Prvý request môže firmware využiť priamo na
  sťahovanie. Pri nezmenenom `Timestamp` vie firmware vynechať obnovu.
- Hlavičky `Timestamp`, `PreciseSleep` a `ShowNoWifiError` zachovávajú presné
  názvy očakávané firmware. Odpoveď má `Content-Length`, bez chunked encoding.
- Timestamp je nenulový 31-bitový odtlačok výsledného PNG. Neoznačuje čas;
  firmware používa porovnanie rovnosti. Čas aktualizácie je v obrázku.
- Sťahovanie s `timestampCheck=0` používa rovnaký snapshot ako predchádzajúca
  kontrola; obsah sa nemení medzi jednotlivými stránkami renderovania.
- Pri výpadku HA sa ponechá posledný obrázok s pôvodným timestampom a časom.
  Cache je v RAM. Ak ešte neexistuje platný obrázok, server vráti `503`.
- Chýbajúca/nedostupná entita sa zobrazuje ako „Nedostupné“. Neplatný HA token
  je chyba zdroja, nie úspešne načítaná hodnota.
- Server neposiela OTA hlavičky ani kontaktuje Živý obraz. SSID, MAC a ostatná
  telemetria prijatá od displeja sa neukladá ani nevypisuje do logu.
- `GET /health` overuje len bežiaci proces, nie dostupnosť HA alebo displeja.
- Jedna konfigurácia je určená pre jeden displej. Súčasné používanie viacerých
  displejov s rovnakým kľúčom a rozmermi nie je podporované.

Rozmery sa berú z requestu zariadenia. Úvodný layout je navrhnutý pre 800×480;
konkrétny model displeja a jeho obnovu treba overiť na hardvéri. Nepodporuje
LaskaKit variant s BMP dekóderom. Testovaná kompatibilita vychádza zo zdrojákov
MultiTricker firmware 3.2, commit `3d7a5a518df8deec32d5f53bd784c099857deeb8`.

## Testy

```sh
python -m unittest discover -s tests -v
```

Testy používajú skutočné lokálne HTTP spojenia, simulované HA API a dekódovanie
vráteného PNG. Overujú autentifikáciu, formát a paletu obrázka, snapshoty,
výpadok HA, zmenu timestampu a odmietnutie neplatných requestov.
