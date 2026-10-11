# Živý obraz lokálne — ESPink v2 / GDEY075Z08

Firmware vychádza z [MultiTricker/zivyobraz-fw v3.2](https://github.com/MultiTricker/zivyobraz-fw/tree/v3.2),
commit `6d0af579ddf4b1ff85debad7dcfefab6449633ac`. Zachovaná atribúcia a licencia
**CC BY-NC-SA 4.0**; úpravy aj add-on sú pod rovnakou licenciou.
Bundlované knižnice v `firmware/lib` si ponechávajú vlastné licencie.

## Hardvér identifikovaný cez USB

Sériový JSON bežiaceho zariadenia (115200 baud): `ESPink_V2`, `GDEY075Z08`,
`800×480`, `3C`, senzor `SHT4X`. ROM hlási ESP32-D0WD-V3, 16 MB flash.
Tieto parametre **nepoužívať naslepo pre iný rámik**.

## Zmeny firmwaru

- WiFiManager má pole `Server host`: hostname alebo IPv4, voliteľne `:port`.
  Nezadávať `https://`, cestu, IPv6 ani query string.
- NVS: namespace `zivyobraz`, nový kľúč `serverHost`; chýbajúca alebo prázdna
  hodnota používa `cdn.zivyobraz.eu`. API PIN a Wi-Fi sa nemenia.
- Zmena hosta resetuje RTC timestamp na 0, aby sa nový zdroj prekreslil.
- Bez automatického fallbacku na CDN. V lokálnom režime sa HTTP klient pripája
  **iba na nastavený host**; v1 add-on neposiela OTA redirect ani cloudový odkaz.
- HTTPS zostáva predvolené. Overovanie certifikátu je `setInsecure()` rovnako
  ako v upstream; preto funguje lokálny self-signed certifikát. To nie je
  autentifikácia servera: dôveruj LAN, port nevystavuj do internetu.
- Dekódovanie, timestamp check, sleep, OTA, rotácia, partial refresh a senzory
  zostávajú v pôvodných cestách. Add-on v1 neposiela Rotate/PartialRefresh/OTA.
  Zachovanie kódu nie je tvrdením, že všetky tieto funkcie boli HW otestované.
- Upstream build flags zostávajú nezmenené. Nové prostredie je
  `espink_local_3c`, platforma `espressif32@6.10.0`, Arduino-ESP32 2.0.17.
- Iba lokálny build má `FAST_CONNECT_SAFE_RESTART`: po neúspešnom fast connect
  odstráni BSSID/channel hinty (nie SSID/heslo), invaliduje cache a reštartuje
  do čistého WiFiManager fallbacku. Pôvodný aj prvý upravený firmware pri deinit
  padali v `scan_parse_beacon`; pokus bez deinit zase zostával v `sta is connecting`.
  Táto úprava je oddelená od endpoint konfigurácie; neúspešný fast connect stojí
  jeden riadený reštart navyše, nie panic. Bežný úspešný fast connect sa nemení.

## Build a bezpečné flashovanie

Príkazy spúšťaj z adresára `zivyobraz-local/firmware`:

```sh
pio run -e espink_local_3c
```

Pred prvým flashom zálohuj **celú flash**. Záloha obsahuje Wi-Fi heslo a PIN;
nesmie byť v Gite, verejných logoch ani zdieľanom archíve. Over jej veľkosť/hash.

```sh
python3 -m esptool --chip esp32 --port /dev/ttyACM0 --baud 921600 read_flash 0 0x1000000 /tmp/opencode/zivyobraz-original-flash.bin
chmod 600 /tmp/opencode/zivyobraz-original-flash.bin
sha256sum /tmp/opencode/zivyobraz-original-flash.bin
pio run -e espink_local_3c -t upload --upload-port /dev/ttyACM0
pio device monitor --port /dev/ttyACM0 --baud 115200
```

Nerob `erase_flash`. Upload zachová NVS. Neprekopíruj API PIN/Wi-Fi do zdrojákov.
Pri inom partition layoute najprv porovnaj zálohovanú tabuľku na 0x8000 s
`.pio/build/espink_local_3c/partitions.bin`. Prerušený backup nie je záloha.

### Konfiguračný portál bez resetovania Wi-Fi

Lokálny build pri USB/reset boote, **nie pri prebudení z deep sleep**, čaká 3 s
po pripojení Wi-Fi na znak `c` cez sériový port. Otvorí WiFiManager na LAN
`http://IP_RÁMIKA/param` na najviac 120 s, zavrie ho po úspešnom uložení.
Je neautentifikovaný, aktivuj ho iba v dôveryhodnej LAN a cez fyzický USB prístup.
Pri neplatnom hoste sa stará hodnota zachová; platný formulár ulož znova.

Skript to vykoná cez **skutočné pole portálu**, bez vymazania Wi-Fi:

```sh
python3 ../tools/configure.py HA_IP:8443 --log /tmp/opencode/zivyobraz-local-serial.log
```

Alternatíva: sériový monitor, reset tlačidlom, poslať `c` po výzve, otvoriť
vypísanú adresu a uložiť pole. V bežnom AP portáli pri chýbajúcom Wi-Fi je pole
tiež dostupné. Pôvodný dlhý stisk tlačidla maže Wi-Fi; na zmenu hosta ho netreba.

## Inštalácia HA add-onu (HAOS / supervised)

Ide o **lokálny add-on**, bez potreby publikovať repozitár alebo prebuilt image.
Na HA musí byť dostupný zápis do `/addons` (napr. cez SSH/Terminal add-on,
ktorému ho dovolíš). SSH prístup netreba sprístupniť internetu.

1. Skopíruj obsah `zivyobraz-local/addon/` do `/addons/zivyobraz_local/` na HA.
   `config.yaml`, `Dockerfile`, `server.py`, `LICENSE`, `NOTICE.md` musia byť
   priamo v tomto adresári, nie vnorené do ďalšieho podadresára.
2. Nastavenia → Doplnky → Obchod s doplnkami → menu → **Skontrolovať aktualizácie**.
   V sekcii Lokálne doplnky vyber **Živý obraz Local**, nainštaluj.
3. V konfigurácii nastav `api_key` na **existujúci 8-miestny PIN rámika**
   (reťazec). Vidno ho v pôvodnej konfigurácii/sériových logoch. Nikam ho
   neposielaj; do Gitu patria iba prázdne defaulty.
4. Ponechaj `image_source: test`, `accent: red`, `sleep_seconds: 360`.
   Spusť doplnok; log má hlásiť `listening on HTTPS :8443; source=test`.
5. V sieťových nastaveniach doplnku sprístupni `8443/tcp` na LAN porte 8443
   (alebo inom voľnom porte). Nastav rámiku `HA_IP:8443` pomocou portálu.
   Použi IP hostiteľa HA, nie interný hostname add-onu ani HA Core port 8123.
6. Zapni automatické spustenie a rezervuj HA IP v DHCP. Neinštaluj/nenahrádzaj
   žiadnu existujúcu e-ink integráciu či doplnok.

Certifikát a kľúč sa vytvoria v `/data` a prežijú reštart. Doplnok nepotrebuje
HA API token, Supervisor API ani host networking. `/share` je iba na čítanie.

### Statický obrázok

- **Súbor:** `image_source: file`, `image_file: /share/zivyobraz/image.png`.
  Nahraj obrázok do HA `/share/zivyobraz/`; cesty mimo `/share` sú odmietnuté.
- **URL:** `image_source: url`, `image_url: http://LOKÁLNY_SERVER/image.png`.
  HTTP(S), timeout 10 s, najviac 20 MiB; URL cache 60 s. API PIN sa URL zdroju
  nikdy neposiela. Pre plne offline režim použi súbor/test alebo **lokálnu URL**.
- Škálovanie drží pomer strán, doplní biele okraje a kvantizuje na
  biela/čierna/červená (`accent: yellow` pre žltý panel). Výstup je nepriehľadné
  RGB PNG bez interlacingu. Po zmene konfigurácie reštartuj add-on.
- Chybný zdroj vráti 502 bez timestampu, nie úspešný náhradný obrázok.

## Protokol a curl dôkazy

POST `/index.php?timestampCheck=0|1`, `X-API-Key`, JSON `display.width`,
`display.height`, `display.colorType: "3C"`. Obidva varianty vracajú celý PNG,
`Timestamp`, `PreciseSleep`, `Content-Length`, `Connection: close`, status 200.
**Pri `timestampCheck=1` nesmie byť telo prázdne:** firmware 3.2 ho používa
priamo na streaming. Timestamp je stabilný nenulový 31-bit hash PNG;
zmena výsledných pixelov ho zmení. Bez zmeny rámik nerefreshuje.

PIN zadávaj interaktívne, nie do histórie shellu (nevytváraj verejný verbose log):

```sh
read -rs -p 'PIN rámika: ' FRAME_PIN
export FRAME_PIN
python3 - <<'PY'
import os, pathlib
p = pathlib.Path('/tmp/opencode/zivyobraz-curl-auth.conf')
p.write_text('header = "X-API-Key: ' + os.environ['FRAME_PIN'] + '"\n')
p.chmod(0o600)
PY
unset FRAME_PIN
curl -ksS --fail --config /tmp/opencode/zivyobraz-curl-auth.conf \
  -H 'Content-Type: application/json' \
  --data '{"display":{"type":"GDEY075Z08","width":800,"height":480,"colorType":"3C"}}' \
  -D /tmp/opencode/check-1.headers -o /tmp/opencode/check-1.png \
  'https://HA_IP:8443/index.php?timestampCheck=1'
curl -ksS --fail --config /tmp/opencode/zivyobraz-curl-auth.conf \
  -H 'Content-Type: application/json' \
  --data '{"display":{"type":"GDEY075Z08","width":800,"height":480,"colorType":"3C"}}' \
  -D /tmp/opencode/check-0.headers -o /tmp/opencode/check-0.png \
  'https://HA_IP:8443/index.php?timestampCheck=0'
file /tmp/opencode/check-1.png /tmp/opencode/check-0.png
cat /tmp/opencode/check-1.headers /tmp/opencode/check-0.headers
```

`-k` je kvôli self-signed certifikátu. Autentifikačný súbor po teste odstráň.
Log add-onu nevypisuje PIN ani JSON s SSID/MAC. Sériový upstream log ich
obsahuje: zdieľaj iba redigovaný záznam (`tools/configure.py` to robí).

## Návrat na pôvodnú službu

```sh
python3 ../tools/configure.py cdn.zivyobraz.eu --log /tmp/opencode/zivyobraz-cloud-serial.log
```

Tým sa obnoví pôvodný HTTPS host/port 443 a zachová pôvodný API PIN, Wi-Fi,
senzory aj panel. Žiadny reflash nie je potrebný. V logu skontroluj úspešný
download z CDN. Potom znovu nastav HA host. Ak treba úplný návrat firmwaru,
privátnu **kompletnú** zálohu možno nahrať na adresu 0 pomocou esptool
`write_flash`; tým sa obnoví aj pôvodné NVS, preto to nerob na novšej konfigurácii.

## Testy a stav overenia

```sh
python3 -m pip install -r addon/requirements-dev.txt
python3 -m unittest discover -s addon/tests -v
docker build -t zivyobraz-local:0.1.0 addon
```

Aktuálne dôkazy a otvorené body sú v [EVIDENCE.md](EVIDENCE.md).
Úspešný build/curl **nie je** dôkaz fyzického zobrazenia či nasadenia na HA.

## Minimalistické komponenty obsahu

Na následné želanie vznikol samostatný [návrh komponentov](design/README.md)
inšpirovaný Weatherman: počasie, tri úseky predpovede, domáce merania,
upozornenie a čas aktualizácie. [PNG náhľad](design/preview.png) používa iba
ukážkové hodnoty a je tak označený. Zatiaľ nečíta živé HA dáta.
