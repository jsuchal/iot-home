# Dôkazy a chýbajúce overenia

Stav: **čiastočne overené, nie hotové nasadenie na Home Assistant**.
Práca je na vetve `zivyobraz-local`; `main` nebol upravovaný.

## Potvrdené

- Pred úpravami USB `/dev/ttyACM0`, 115200 baud, serial JSON:
  `ESPink_V2`, `GDEY075Z08`, `800×480`, `3C`, `SHT4X`, firmware `3.2`.
- esptool: ESP32-D0WD-V3, revision v3.0, 16 MB flash.
- Kompletná privátna záloha `/tmp/opencode/zivyobraz-original-flash.bin`:
  **16 777 216 bajtov**, SHA256
  `c20596620aa0e90c0ba5e43884e3ca9594f78f95c4719b89779a6e6569f5ff41`.
  Súbor má mód 0600, nie je v Gite. Prvý pokus pri 460800 baud bol prerušený
  po 180 s; opakovaný backup 921600 baud dokončený za 228,9 s.
- Partition layout na zariadení a v builde zhodný:
  NVS `0x9000/0x5000`, otadata `0xe000/0x2000`, app0 `0x10000/0x140000`,
  app1 `0x150000/0x140000`, spiffs `0x290000/0x160000`, coredump `0x3f0000/0x10000`.
- PlatformIO lokálny build úspešný; upload úspešný s `Hash of data verified`.
  RAM 98724/327680 B (30,1 %), app flash 1217033/1310720 B (92,9 %).
  Nahratý `firmware.bin` SHA256:
  `d2e1bdfe91880ff6722c0485f8d86580afc3c81fa5579bf474d1b0a1b6fd3c6c`.
- Kompilácia všetkých siedmich upstream prostredí úspešná:
  `espink`, `espink_v3`, `es3ink`, `MakerBadge`, `seeedstudio_xiao_esp32c3`,
  `sverio_paperboard_spi`, `sverio_paperboard_epdiy`. Ich build flags ostali pôvodné.
- Add-on Docker build úspešný na amd64. 9 serverových testov prešlo na hoste
  aj v skutočnom kontajneri (vrátane autentifikácie, oboch timestampCheck,
  palety/škálovania, transparentnosti, zmien súboru, URL cache a chyby zdroja).
- Dočasný kontajner rovnakého add-on servera beží na **pracovnom počítači**,
  `https://192.168.1.196:8443`, nie na HA.
  Po testoch bol jeho interval v privátnych options obnovený zo 60 na 360 s
  a kontajner reštartovaný; rámik stále smeruje na tento dočasný lokálny server.
  Kým sa nenainštaluje HA add-on, tento počítač musí byť dostupný na LAN.
- Host bol nastavený cez skutočné pole WiFiManager `/param` → POST `/paramsave`.
  PIN aj Wi-Fi boli zachované. NVS hodnota prežila reštart.
- Sériové logy lokálneho prenosu: `Connecting to: https://192.168.1.196:8443`,
  `PNG Processing (direct streaming mode)`, **2906 bajtov / 384000 pixelov**,
  `Going to sleep`. Prvý server nekorektne ukončoval TLS; doplnený `close_notify`
  odstránil SSL chybu aj falošný jeden bajt navyše v počítadle upstream čítačky.
- Na ďalšom deep-sleep wake sa zachoval timestamp `1767206305`, log:
  `No screen reload, still at current timestamp`, `No update needed`, sleep 60 s.
  Senzor sa použil z cache; nameraný refresh ~17453 ms.
- Finálny záznam obsahuje **tri dokončené sleep cykly**, lokálny download,
  následný unchanged timestamp bez refreshu a ďalší download po riadenom
  Wi-Fi fallback reštarte. Žiadny panic v tomto zázname. USB zostalo otvorené;
  opätovné otvorenie tohto USB prevodníka môže resetovať ESP32 a skresliť wake test.
- Curl na **pracovný počítač**, obe hodnoty `timestampCheck=0|1`:

  ```text
  HTTP/1.1 200 OK
  Content-Type: image/png
  Content-Length: 2906
  Connection: close
  Timestamp: 1767206305
  PreciseSleep: 60
  ```

  Pillow úspešne dekódoval obidva PNG: RGB, 800×480,
  iba `(255,255,255)`, `(0,0,0)`, `(255,0,0)`.
- Používateľ **fyzicky potvrdil správne zobrazený testovací obrázok** s čiernym,
  bielym a červeným blokom. Fotografia nebola dodaná; PNG náhľad nie je fotka rámika.
- Návrat endpointu cez portál na `cdn.zivyobraz.eu` úspešne overený s tým istým
  upraveným firmware: HTTPS :443, Timestamp `101109`, PreciseSleep `1680`,
  Z2 streaming, **22952 bajtov / 384000 pixelov**, úspešný sleep 1664 s.

## Zistené problémy a vykonané pokusy

- Pôvodný firmware pri zlyhaní fast connect padal v `scan_parse_beacon` počas
  deinit Wi-Fi. Rovnaký problém sa zopakoval po samotnej zmene endpointu.
- Pokus ponechať driver zapnutý odstránil panic, ale niekedy skončil v
  `sta is connecting` a AP portáli. **Tento pokus nie je finálna implementácia.**
- Finálny lokálny build používa `FAST_CONNECT_SAFE_RESTART`: pri neúspešnom
  fast connect vymaže iba BSSID/channel hinty a cache, zachová SSID/heslo/PIN,
  urobí riadený reštart. V cloud rollback teste bola táto cesta reálne vyvolaná:
  `Restarting for clean WiFiManager fallback` → autoConnect SUCCESS → download.
- Nepodaril sa packet capture: tcpdump na Wi-Fi odmietnutý (`Operation not
  permitted`), `sudo -n` vyžaduje heslo. Zdroj má jediný image connect volajúci
  uložený host, bez CDN fallbacku; lokálne sériové logy ukazujú iba lokálny host.
  **To nie je úplný packet-level dôkaz na AP/routeri.**
- Pri prvom viac-cyklovom teste skript opakovane otváral portál po riadenom
  reštarte, ale formulár už neposlal; preto dosiahol timeout. Skript bol opravený
  na jednorazové otvorenie a opakovaný finálny trojcyklový test úspešný.

## Presne chýba k pôvodnej definícii „hotovo“

1. Používateľ zvolil ručnú inštaláciu add-onu do HA, ale ešte neposkytol bežiaci
   HA endpoint. Treba obsah `addon/` skopírovať do `/addons/zivyobraz_local`,
   nainštalovať/spustiť, nastaviť pôvodný PIN a oznámiť **HA IP + port** (nie PIN).
2. Potom vykonať curl oboch timestampCheck **na HA**, prepnúť rámik na HA,
   zaznamenať serial download aj požiadavku v **HA add-on logoch**.
3. Potvrdiť obraz pri smerovaní na HA; ideálne priložiť fotku.
4. Pre nezávislý dôkaz nulovej cloudovej komunikácie spraviť capture alebo
   firewall/DNS log na AP/routeri počas lokálneho cyklu. Host capture všetkých
   spojení iného Wi-Fi klienta by sám osebe nebol úplný dôkaz.

OTA, Rotate a PartialRefresh parser/cesty ostali nezmenené, kompilujú sa,
ale nebol vykonaný živý OTA update ani HW test rotácie/partial refresh.
Iné upstream dosky boli overené kompiláciou, nie fyzicky.

## Súbory dôkazov

Sanitizované logy a výsledky sú v `evidence/`. Privátne raw logy s PIN/Wi-Fi,
flash záloha, autentifikačné curl options a TLS kľúče ostávajú mimo Gitu v
`/tmp/opencode`; tieto súbory **nezdieľať**. Build binárky ostávajú v ignorovanom
`firmware/.pio/build/espink_local_3c/`.

## Nová požiadavka na minimalistický obsah

`design/preview.png` bol vizuálne skontrolovaný, je platný 800×480 RGB PNG
s iba tromi farbami. `design/render.py` má samostatné komponenty počasie,
predpoveď, domáce merania a upozornenie. **Nie je napojený na živé dáta HA**;
všetky ukážkové hodnoty sú explicitne označené. Používateľ vybral počasie a
predpoveď; náhľad má vpravo vietor a pravdepodobnosť dažďa namiesto domáceho
CO₂/teploty. Prešli 2 testy renderera (paleta/rozmery a chýbajúce/dlhé hodnoty).
Prvý priamy MCP dotaz `GetLiveContext(domain="weather")` vrátil
`No exposed entities found in domain(s): weather`; weather entitu treba
bolo sprístupniť. Používateľ ju následne sprístupnil a opakovaný dotaz už
vrátil **Forecast Home** s aktuálnym stavom/teplotou/vlhkosťou. Hodinová/denná
predpoveď ani presné entity_id nie sú v MCP výsledku a nástroj pre
`weather.get_forecasts` nie je dostupný. Na živú predpoveď teda treba read-only
prístup k tejto HA službe. Agent žiadnu HA konfiguráciu nemenil.
